import sys
import getopt
import requests
import json
import hashlib
import os
import shutil
from py_linq import Enumerable
from pathlib import Path
from pathlib import PureWindowsPath

location = "."
manifest = {}
downloadedPackages = {}
lang = "en-US"

def help():
    print("Usage:")

def verifyFile(file, sha256sum):
    if not os.path.exists(file):
        return False
    try:
        sha256_hash = hashlib.sha256()
        with open(file,"rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096),b""):
                sha256_hash.update(byte_block)
            return sha256sum.lower() == sha256_hash.hexdigest().lower()
    except:
        return False

def downloadResumableFile(url, file, totalSize):
    try:
        startPos = 0
        if totalSize != 0 and os.path.exists(file):
            startPos = os.path.getsize(file) 
            if startPos == totalSize:
                print("File already downloaded")
                return True
            outputFile = open(file, "ab")
            resume_header = {'Range': 'bytes=%d-' % startPos}
        else:
            outputFile = open(file,  "wb")
            resume_header = {}

        response = requests.get(url, stream=True, headers=resume_header, allow_redirects=True)
        total_length = response.headers.get('content-length')

        if total_length is None: # no content length header
            outputFile.write(response.content)
        else:
            dl = 0
            total_length = int(total_length)
            for data in response.iter_content(chunk_size=4096):
                dl += len(data)
                outputFile.write(data)
                done = int(100 * dl / total_length)
                sys.stdout.write("\r[%s%s]" % 
                ('=' * done, ' ' * (100-done)) )
                sys.stdout.write(f" {done}% => {dl} / {total_length}")    
                sys.stdout.flush()
    except:
        return False
    
    return True
    

def downloadFile(url, file, sha256sum=None, totalSize=0, retries=10):
    #print(f'Downloading {url} to {file} with sha256 [{sha256sum}]')
    if (sha256sum != None):
        if verifyFile(file, sha256sum):
            #print("File already present and sha256sum is valid")
            return
    else:
        print(f'No sha256sum provided')

    currentTry = 0
    success = False
    dir, _ = os.path.split(file)
    Path(dir).mkdir(parents=True, exist_ok=True)
    while currentTry<retries and not success:
        success = downloadResumableFile(url, file, totalSize)
        if not success:
            currentTry = currentTry+1

    print()
    if (success):
        if (sha256sum != None) and not verifyFile(file, sha256sum):
            print(f"Error verifying sha256sum {sha256sum} of file {file} downloades from {url}, removing existing file")
            os.remove(file)
            downloadFile(url, file, sha256sum, totalSize, retries)
    else:
        raise f"Error downloadong file {file} from {url}"

def downloadChannel(version, channel):
    print(f'Downloading VS channel {version} {channel}')
    url = f'https://aka.ms/vs/{version}/{channel}/channel'
    downloadFile(url, 'temp/channel.json')
    
def downloadManifest(channel):
    global manifest
    print("Downloading VS manifest")

    vsItemId = "Microsoft.VisualStudio.Manifests.VisualStudio"
    if channel == "pre":
        vsItemId = "Microsoft.VisualStudio.Manifests.VisualStudioPreview"

    with open('temp/channel.json', encoding='utf-8') as channelFile:
        data = json.load(channelFile)
        print(f'Product ID: {data["info"]["id"]}')

        manifestItem = Enumerable(data["channelItems"]).where(lambda item: item["id"] == vsItemId).first()

        downloadFile(manifestItem["payloads"][0]["url"], "temp/manifest.json")

        with open('temp/manifest.json', encoding='utf-8') as manifestFile:
            manifest = json.load(manifestFile)

def downloadPackageDependencies(package):
    if "dependencies" not in package:
        return

    for dep in package["dependencies"]:
        downloadPackage(dep)

def getPackagePath(package):
    packagePath = f'{package["id"]},version={package["version"]}'
    if "chip" in package:
        packagePath = f'{packagePath},chip={package["chip"]}'
    if "language" in package:
        packagePath = f'{packagePath},language={package["language"]}'
    
    return packagePath

def downloadPackagePayload(package):
    if ("payloads" not in package):
        return

    packagePath = getPackagePath(package)
    

    for payload in package["payloads"]:
        if package["type"].lower() == "vsix":
            filePath = "payload.vsix"
        else:    
            filePath = PureWindowsPath(payload["fileName"]).as_posix()
        file = os.path.join(location, packagePath, filePath)
        downloadFile(payload["url"], file, payload["sha256"], payload["size"])

def downloadPackage(packageName):
    global downloadedPackages
    global lang
    if (packageName in downloadedPackages):
        return

    package = Enumerable(manifest["packages"]).where(lambda item: item["id"].lower() == packageName.lower() and ("language" not in item or item["language"].lower() in ["neutral", lang.lower()])).first_or_default()
    if package == None:
        if not packageName.lower().endswith(".resources"):
            print(f"package {packageName} not found in manifest")
        return

    print(f"Downloading package {getPackagePath(package)}")

    downloadedPackages[packageName] = package

    downloadPackagePayload(package)

    downloadPackageDependencies(package)

def downloadProduct(product):
    product = f'Microsoft.VisualStudio.Product.{product}'
    downloadPackage(product)

def savePackageSelection():
    with open('temp/packages.json', 'w') as file:
        json.dump(downloadedPackages, file)

def loadPackageSelection():
    global downloadedPackages
    if downloadedPackages != {}:
        return
    with open('temp/packages.json') as file:
        downloadedPackages = json.load(file)

def cleanup():
    print("Cleanup filesystem")
    folders = [dI for dI in os.listdir(location) if os.path.isdir(os.path.join(location,dI))]
    for folder in folders:
        dirname = os.path.basename(os.path.normpath(folder))
        parts = dirname.split(',')
        packageName = parts[0]
        version = None
        chip = None
        lang = None
        langs = ["neutral"]
        for part in parts[1:]:
            if part.lower().startswith('version'):
                version = part.lower().replace('version=', '')
            if part.lower().startswith('chip'):
                chip = part.lower().replace('chip=', '')
            if part.lower().startswith('language'):
                lang = part.lower().replace('language=', '')
                langs.append(lang.lower())
        if version == None:
            continue

        package = Enumerable(manifest["packages"]).where(lambda item: item["id"].lower() == packageName.lower() and ("language" not in item or item["language"].lower() in langs) and (item["version"] == version)).first_or_default()
        exists = False
        if not package == None:
            exists = True
            exists = exists and (version != None and package["version"] == version)
            # exists = exists and (chip == None or (chip != None and package["chip"].lower() == chip.lower()))
            exists = exists and (lang == None or (lang != None and package["language"].lower() == lang.lower()))

        if not exists:
            print(f"cleanup {dirname}")
            print(package)
            # shutil.rmtree(os.path.join(location, dirname))

def main(argv):
    print("VS Offline installer")
    try:
        opts, args = getopt.getopt(argv,"hcw:v:l:p:", ["help", "location", "version", "preview"])
    except getopt.GetoptError:
        help()
        sys.exit(2)
    
    version = "16"
    clean = False
    channel = "release"
    product = "Community"
    global location
    for opt, arg in opts:
        if opt == '-h' or opt == "--help":
            help()
            sys.exit()
        elif opt == '-c':
            clean = True
        elif opt == '-v' or opt == "--version":
            version = arg
        elif opt == '-w' or opt == "--preview":
            channel = "pre"    
        elif opt == '-l' or opt == "--location":
            location = arg
        elif opt == '-p':
            product = arg
    
    downloadChannel(version, channel)
    downloadManifest(channel)
    downloadProduct(product)
    savePackageSelection()
    if clean:
        loadPackageSelection()
        cleanup()

if __name__ == "__main__":
    main(sys.argv[1:])