# vs-offline-download

Small utility to download Visual Studio 2019.

## The Problem

The Visual Studio 2019 Installer can, in fact, create a offline installation, but the behavior of the installer is not suitable for very slow internet collection. 

* It does not retries partial downloads
* Uses several parallel download threads

Besides that, it is a Windows only tool, requiring a dedicaded Windows (Deskptop or Server) in order to be able to update the VS2019 layout

## The solution (partial)

This is a multiplatform tool written in python >= 3.6, that allows to download most of the layout files.

* Only uses one download thread
* Each file download is retried 10 times
* After the download is completed the files are checked against its declared sha256sum
* The partially downloaded files are resumed once the tool is re executed
* It has a cleanup option that after the download part removes all the old components

## Whats missing

* Individual payloads or components selections
* Allow to select another VS language
...

## How to use this tool

1. Clone this repo to a local filesystem
   ```
   git clone https://github.com/ypupo2002/vs-offline-download.git 
   ```
2. Install the required python dependencies
   ```
   pip3 install -r requirements.txt
   ```
3. Execute the tool:
   ```
   pyhton3 main.py ....arguments....
   ```
   Arguments:

   `-p` : [Optional] Specifies the product version to download, allowed values: `Community`, `Professional`, `Enterprise`
   
   `-c` : [Optional] Performs a cleanup of old files after the download 

   `-l` : [Required] Specifies the location of the layout

After the tool execution and before the use of the VS2019 offline installer it is required to execute a final step: Download the corresponding VS2019 installer (community, Professional or Enterprise) and perform a layout operation:
   ```
   {installer}.exe --layout "<layout path>" -lang en-US
   ```
This step must be performed on a Windows machine, and it should download a few missing files (not a lot of MBs)

