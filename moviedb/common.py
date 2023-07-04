"""
Some functions/classes common to apps
"""

import os
import platform

if platform.system() == "Windows":
    import win32api

    def get_volumes():
        """
        Returns volumes dictionary keyed by letter :
            volumes[KEY] = (volume_name, serial_number), (...) ]
        """
        volumes = {}
        drives = win32api.GetLogicalDriveStrings()
        drives = drives.lower().split("\000")[:-1]
        for drive in drives:
            try:
                volinfos = win32api.GetVolumeInformation(drive)
                volname = volinfos[0]
                volserial = volinfos[1]
                volumes[drive[0]] = (volname, volserial)
            except win32api.error as _e:
                # print('  WARNING: %s for drive %s' % (_e, drive))
                pass
        return volumes

else:

    def get_volumes():
        """
        unavailable on linux :
        """
        raise ImportError("get_volumes unavailable on linux")


def build_dbfilename(fname, volumes):
    """build database filename"""
    # build datase filename
    moviepath, _ = os.path.split(fname)
    volname, _ = os.path.splitdrive(moviepath)
    if volname.startswith("\\\\"):
        volname = volname.split("\\")[2]
        dbfname = fname.replace("\\\\" + volname, volname + ":")
    else:
        # replace drive letter with volume name
        volname, _ = volumes[moviepath.lower()[0]]
        dbfname = volname + fname[1:]
    dbfname = dbfname.replace("/", "\\")
    return dbfname
