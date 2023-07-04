# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"""

    DNLA Tools
    Minimal DMC (Digital Media Controler) implementation

"""

import os
from xml.dom import minidom
import upnpclient
import requests

# map file extension to mime type
EXTENSION_MIME = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mkv" : "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",

}


def _XMLGetNodeText(node):
    text = []
    for childNode in node.childNodes:
        if childNode.nodeType == node.TEXT_NODE:
            text.append(childNode.data)
    return "".join(text)


def extract_metadata(node):
    """extract metadata from XML"""
    try:
        obj_id = ""
        for att in node.attributes.items():
            if att[0].lower() == "id":
                obj_id = att[1]
                break
        if not obj_id:
            return None
        obj_type = node.tagName
        obj_class = ""
        obj_title = ""
        obj_album = ""
        obj_artist = ""
        obj_track = ""
        obj_uri = ""
        obj_protocol_info = ""
        for ch_node in node.childNodes:
            if ch_node.nodeType == ch_node.ELEMENT_NODE:
                val = ch_node.tagName.split(":", 1)[-1].lower()
                if val == "class":
                    obj_class = ".".join(_XMLGetNodeText(ch_node).split(".")[:3])
                elif val == "title":
                    obj_title = _XMLGetNodeText(ch_node)
                elif val == "album":
                    obj_album = _XMLGetNodeText(ch_node)
                elif val == "creator":
                    obj_artist = _XMLGetNodeText(ch_node)
                elif val == "originaltracknumber":
                    obj_track = _XMLGetNodeText(ch_node)
                elif val == "res":
                    for att in ch_node.attributes.items():
                        if att[0].lower() == "protocolinfo":
                            obj_protocol_info = att[1]
                    if not obj_uri:
                        obj_uri = _XMLGetNodeText(ch_node)
                    for att in node.attributes.items():
                        if att[0].lower() == "protocolinfo":
                            if not "DLNA.ORG_CI=1" in att[1].upper().replace(" ", ""):
                                obj_uri = _XMLGetNodeText(ch_node)
                                break
        return {
            "id": obj_id,
            "type": obj_type,
            "class": obj_class,
            "uri": obj_uri,
            "title": obj_title,
            "album": obj_album,
            "track": obj_track,
            "artist": obj_artist,
            "protocol": obj_protocol_info,
        }
    except Exception:
        return None


class DLNAException(Exception):
    """DLNA Exception"""


class DLNA:
    """
    DLNA Controler / Tools
        dev = DLNA(device_uri|device_instance)

        dev.show_device()

        dev.play_content(content_uri):
    """

    def __init__(self, **kwargs):
        self.device = None
        if kwargs.get("device_uri", None):
            self.open_from_uri(kwargs.get("device_uri"))
        if kwargs.get("device_instance", None):
            self.device = kwargs.get("device_instance")

    def open_from_uri(self, device_uri):
        """Open Device via URI"""
        try:
            self.device = upnpclient.Device(device_uri)
        except requests.exceptions.ConnectTimeout:
            self.device = None

    def show_service(self, service, verbosity):
        """Show information on services on server"""
        print(f"    type: '{service.service_type}'  id: '{service.service_id}'")
        if verbosity < 2:
            return
        for action in service.actions:
            print(f"      action '{action.name}'")
            if verbosity < 3:
                continue
            for arg_name, arg_def in action.argsdef_in:
                valid = ", ".join(arg_def["allowed_values"]) or "*"
                print(f'         in: {arg_name} ({arg_def["datatype"]}): {valid}')
            for arg_name, arg_def in action.argsdef_out:
                valid = ", ".join(arg_def["allowed_values"]) or "*"
                print(f'        out: {arg_name} ({arg_def["datatype"]}): {valid}')

    def show_device(self, verbosity=0):
        """Show device details and services"""
        print(f"Device Friendly Name: {self.device.friendly_name}")
        print(f"  model description: {self.device.model_description}")
        print(f"  model name: {self.device.model_name}")
        print(f"  location: {self.device.location}")
        print(f"  device name: {self.device.device_name}")
        print(f"  device type: {self.device.device_type}")
        if verbosity < 1:
            return
        print(f"  manufacturer: {self.device.manufacturer}")
        print(f"  model number: {self.device.model_number}")
        print(f"  serial number: {self.device.serial_number}")
        print("  services availables:")
        for service in self.device.services:
            self.show_service(service, verbosity)

    def search_title(self, object_id, content_title):
        """search a file in directory"""
        content_title = content_title.lower()
        ret_content = None
        resp = self.device.ContentDirectory.Browse(
            ObjectID=object_id,
            BrowseFlag="BrowseDirectChildren",
            Filter="*",
            StartingIndex=0,
            RequestedCount=0,
            SortCriteria="",
        )
        root_xml = minidom.parseString(resp["Result"])
        for node in root_xml.documentElement.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            content = extract_metadata(node)
            if content["type"] == "item" and content["title"].lower() == content_title:
                return content
            if content["type"] == "container":
                content = self.search_title(content["id"], content_title)
                if content:
                    ret_content = content
                    break
        return ret_content

    def search_directory(self, root_id, dirs):
        """search for directory from root"""
        if isinstance(dirs, str):
            if dirs.startswith("/"):
                dirs = dirs[1:]
            dirs = dirs.split("/")
        object_id = root_id
        if len(dirs) == 1 and dirs[0] == "":
            return root_id
        for _dir in dirs:
            resp = self.device.ContentDirectory.Browse(
                ObjectID=object_id,
                BrowseFlag="BrowseDirectChildren",
                Filter="*",
                StartingIndex=0,
                RequestedCount=0,
                SortCriteria="",
            )
            root_xml = minidom.parseString(resp["Result"])
            object_id = None
            for node in root_xml.documentElement.childNodes:
                if node.nodeType != node.ELEMENT_NODE:
                    continue
                content = extract_metadata(node)
                if content["type"] == "item":
                    continue
                if content["title"] == _dir:
                    object_id = content["id"]
                    break
        return object_id

    def get_contents(self, dirs, traverse=False):
        """
        Get contents similarly to os.walk :
        Returns list of 3-tuple for each directory (dirpath, dirnames, filenames)

        """
        id_dir = self.search_directory(self.root_content_id(), dirs)
        if not id_dir:
            raise DLNAException("Directory not found")
        return self._get_contents([], id_dir, dirs, traverse)

    def _get_contents(self, tree, id_dir, root_dir, traverse=False):
        """
        tree is [dirpath, dirnames, filenames]
        """
        directories = []
        files = []
        resp = self.device.ContentDirectory.Browse(
            ObjectID=id_dir,
            BrowseFlag="BrowseDirectChildren",
            Filter="*",
            StartingIndex=0,
            RequestedCount=0,
            SortCriteria="",
        )
        root_xml = minidom.parseString(resp["Result"])
        for node in root_xml.documentElement.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            content = extract_metadata(node)
            if content["type"] == "item":
                files.append((content["title"], content["uri"]))
            if content["type"] == "container":
                directories.append(content["title"])
                if traverse:
                    tree = self._get_contents(
                        tree, content["id"], root_dir + "/" + content["title"], traverse
                    )
        tree.append((root_dir, directories, files))
        return tree

    def root_content_id(self):
        """return root_id for ContentDirectory"""
        resp = self.device.ContentDirectory.Browse(
            ObjectID=0,
            BrowseFlag="BrowseMetadata",
            Filter="*",
            StartingIndex=0,
            RequestedCount=0,
            SortCriteria="",
        )
        root_xml = minidom.parseString(resp["Result"])
        # TODO case childNodes empty
        for node in root_xml.documentElement.childNodes:
            if node.nodeType == node.ELEMENT_NODE:
                break
        meta = extract_metadata(node)
        return meta["id"]

    def play_content(self, movie, content_uri):
        """
        Play media content
            return tuple (Bool (done), str (reason))
        """

        try:
            # stop current play
            self.device.AVTransport.Stop(InstanceID=0)
        except upnpclient.soap.SOAPError as _e:
            # ignore error (when not running ?)
            pass
        try:
            _, ext = os.path.splitext(movie.file)
            ext = ext.lower()
            # build metadatas by device type
            if self.device.manufacturer.lower().startswith("samsung"):
                # ok without metadata
                metadata = ""
                # INFO: video station seems to use succesfully this :
                #   metadata = '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns:sec="http://www.sec.co.kr/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/"><item id="302" parentID="@" restricted="1"><dc:title>The Extraordinary Journey of the Fakir.mkv</dc:title><upnp:class>object.item.videoItem</upnp:class><dc:date>2019-03-02T23:40:40</dc:date><res protocolInfo="http-get:*:video/x-matroska:DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000" bitrate="235605" resolution="1280x536" size="1354729574" duration="1:35:50.000">http://192.168.1.23:5000/webman/3rdparty/VideoStation/controller/ui/cgi/vtestreaming.cgi/eyJpZCI6InVwbnA6dXVpZDoxZjA0YjUxMC04OTZhLTljOGQtMzBlYi0xYjcxYjM2N2Y5NWYiLCJtZXRob2QiOiJvcGVuIiwidG9rZW4iOiJEdXZ0eEVhbVlDNU5fMTY3ODQ0MjY2MiIsIngtbWt2IjoxfQo=.mkv</res></item></DIDL-Lite></CurrentURIMetaData>'
            else:
                mime = EXTENSION_MIME[ext] if ext in EXTENSION_MIME else "video/x"
                metadata='<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"; xmlns:sec="http://www.sec.co.kr/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/">'\
                    f'<item id="{movie.id}" parentID="" restricted="1">'\
                    f"<dc:title>{movie.movie.title}</dc:title>"\
                    "<upnp:class>object.item.videoItem</upnp:class>"\
                    f'<res protocolInfo="http-get:*:{mime}:DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000" '\
                        f'bitrate="{movie.bitrate}" resolution="{movie.screen_size}" size="{movie.file_size}" duration="{movie.duration_string()}">{content_uri}</res>'\
                    "</item>"\
                    "</DIDL-Lite>"
            # set content
            self.device.AVTransport.SetAVTransportURI(
                InstanceID=0, CurrentURI=content_uri, CurrentURIMetaData=metadata
            )
            # start playing
            self.device.AVTransport.Play(InstanceID=0, Speed="1")
        except AttributeError as _e:
            return (False, str(_e))
        except upnpclient.soap.SOAPError as _e:
            return (False, str(_e))
        return (True, "")


def dlna_discover(discover, timeout, verbosity):
    """display DNLA discover"""
    devices = None
    ssdp = upnpclient.ssdp
    devices = ssdp.discover(timeout)
    ndevs = 0
    for dev in sorted(devices, key=lambda d: d.friendly_name):
        if discover == "smart":
            _t = dev.device_type.split(":")
            if not _t[-2] in ["MediaRenderer", "MediaServer"]:
                continue
        elif discover == "renderers":
            _t = dev.device_type.split(":")
            if _t[-2] != "MediaRenderer":
                continue
        elif discover == "mediaservers":
            _t = dev.device_type.split(":")
            if _t[-2] != "MediaServer":
                continue
        ndevs += 1
        device = DLNA(device_instance=dev)
        device.show_device(verbosity=verbosity)
    print(f"Devices listed : {ndevs} on {len(devices)} found")
