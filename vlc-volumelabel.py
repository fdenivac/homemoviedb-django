"""
Play video in VLC on Windows

    The video filename starts with the volume label.
    This label must be replaced by the letter of the volume in line


"""

import sys
import platform
import subprocess

if platform.system() == "Windows":
    import win32api
else:
    sys.exit("Platform unsupported")

video_file = sys.argv[1]
volume_label = video_file.split(":")[0]

# search for volume label in line
volume_letter = None
drives = win32api.GetLogicalDriveStrings()
drives = drives.split("\000")[:-1]
for drive in drives:
    try:
        volinfos = win32api.GetVolumeInformation(drive)
        if volinfos[0].lower() == volume_label.lower():
            volume_letter = drive
    except win32api.error:
        pass
if not volume_letter:
    sys.exit("Volume not inline")

# replace volume label with volume letter
video_file = video_file.replace(volume_label, volume_letter[0])
# why a '/' is added to file parameter ?
if video_file[-1] == "/":
    video_file = video_file[:-1]
# launch VLC
subprocess.Popen(["C:\\Program Files\\VideoLAN\\VLC\\vlc.exe", video_file])
