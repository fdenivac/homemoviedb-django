# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"""

    DNLA Tools
    Minimal DMC (Digital Media Controler) implementation

"""

from xml.dom import minidom
import upnpclient
import requests


def _XMLGetNodeText(node):
    text = []
    for childNode in node.childNodes:
        if childNode.nodeType == node.TEXT_NODE:
            text.append(childNode.data)
    return ''.join(text)


def extract_metadata(node):
    ''' extract metadata from XML '''
    try:
        obj_id = ''
        for att in node.attributes.items():
            if att[0].lower() == 'id':
                obj_id = att[1]
                break
        if not obj_id:
            return None
        obj_type = node.tagName
        obj_class = ''
        obj_title = ''
        obj_album = ''
        obj_artist = ''
        obj_track = ''
        obj_uri = ''
        obj_protocol_info = ''
        for ch_node in node.childNodes:
            if ch_node.nodeType == ch_node.ELEMENT_NODE:
                val = ch_node.tagName.split(':', 1)[-1].lower()
                if val == 'class':
                    obj_class = '.'.join(_XMLGetNodeText(ch_node).split('.')[:3])
                elif val == 'title':
                    obj_title = _XMLGetNodeText(ch_node)
                elif val == 'album':
                    obj_album = _XMLGetNodeText(ch_node)
                elif val == 'creator':
                    obj_artist = _XMLGetNodeText(ch_node)
                elif val == 'originaltracknumber':
                    obj_track = _XMLGetNodeText(ch_node)
                elif val == 'res':
                    for att in ch_node.attributes.items():
                        if att[0].lower() == 'protocolinfo':
                            obj_protocol_info = att[1]
                    if not obj_uri:
                        obj_uri = _XMLGetNodeText(ch_node)
                    for att in node.attributes.items():
                        if att[0].lower() == 'protocolinfo':
                            if not 'DLNA.ORG_CI=1' in att[1].upper().replace(' ', ''):
                                obj_uri = _XMLGetNodeText(ch_node)
                                break
        return {'id': obj_id, 'type': obj_type, 'class': obj_class, 'uri': obj_uri, 'title': obj_title, 'album': obj_album, 'track': obj_track, 'artist': obj_artist, 'protocol' : obj_protocol_info}
    except Exception:
        return None


class DLNAException(Exception):
    ''' DLNA Exception '''

class DLNA():
    '''
    DLNA Controler / Tools
        dev = DLNA(device_uri|device_instance)

        dev.show_device()

        dev.play_content(content_uri):
    '''

    def __init__(self, **kwargs):
        self.device = None
        if kwargs.get('device_uri', None):
            self.open_from_uri(kwargs.get('device_uri'))
        if kwargs.get('device_instance', None):
            self.device = kwargs.get('device_instance')


    def open_from_uri(self, device_uri):
        ''' Open Device via URI '''
        try:
            self.device = upnpclient.Device(device_uri)
        except requests.exceptions.ConnectTimeout:
            self.device = None


    def show_service(self, service, verbosity):
        ''' Show information on services on server'''
        print("    type: '{}'  id: '{}'".format(service.service_type, service.service_id))
        if verbosity < 2:
            return
        for action in service.actions:
            print("      action '%s'" % (action.name))
            if verbosity < 3:
                continue
            for arg_name, arg_def in action.argsdef_in:
                valid = ', '.join(arg_def['allowed_values']) or '*'
                print("         in: %s (%s): %s" % (arg_name, arg_def['datatype'], valid))
            for arg_name, arg_def in action.argsdef_out:
                valid = ', '.join(arg_def['allowed_values']) or '*'
                print("        out: %s (%s): %s" % (arg_name, arg_def['datatype'], valid))


    def show_device(self, verbosity=0):
        ''' Show device details and services '''
        print("Device Friendly Name: %s" % self.device.friendly_name)
        print("  model description: %s" % self.device.model_description)
        print("  model name: %s" % self.device.model_name)
        print("  location: %s" % self.device.location)
        print("  device name: %s" % self.device.device_name)
        print("  device type: %s" % self.device.device_type)
        if verbosity < 1:
            return
        print("  manufacturer: %s" % self.device.manufacturer)
        print("  model number: %s" % self.device.model_number)
        print("  serial number: %s" % self.device.serial_number)
        print("  services availables:")
        for service in self.device.services:
            self.show_service(service, verbosity)


    def search_title(self, object_id, content_title):
        ''' search a file in directory  '''
        content_title = content_title.lower()
        ret_content = None
        resp = self.device.ContentDirectory.Browse(ObjectID=object_id, BrowseFlag='BrowseDirectChildren', Filter='*', StartingIndex=0, RequestedCount=0, SortCriteria='')
        root_xml = minidom.parseString(resp['Result'])
        for node in root_xml.documentElement.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            content = extract_metadata(node)
            if content['type'] == 'item' and content['title'].lower() == content_title:
                return content
            if content['type'] == 'container':
                content = self.search_title(content['id'], content_title)
                if content:
                    ret_content = content
                    break
        return ret_content


    def search_directory(self, root_id, dirs):
        ''' search for directory from root '''
        if isinstance(dirs, str):
            dirs = dirs.split('/')
        object_id = root_id
        if len(dirs) == 1 and dirs[0] == '':
            return root_id
        for _dir in dirs:
            resp = self.device.ContentDirectory.Browse(ObjectID=object_id, BrowseFlag='BrowseDirectChildren', Filter='*', StartingIndex=0, RequestedCount=0, SortCriteria='')
            root_xml = minidom.parseString(resp['Result'])
            object_id = None
            for node in root_xml.documentElement.childNodes:
                if node.nodeType != node.ELEMENT_NODE:
                    continue
                content = extract_metadata(node)
                if content['type'] == 'item':
                    continue
                if content['title'] == _dir:
                    object_id = content['id']
                    break
        return object_id



    def get_contents(self, dirs, traverse=False):
        '''
        Get contents similarly to os.walk :
        Returns list of 3-tuple for each directory (dirpath, dirnames, filenames)

        '''
        id_dir = self.search_directory(self.root_content_id(), dirs)
        if not id_dir:
            raise DLNAException('Directory not found')
        return self._get_contents([], id_dir, dirs, traverse)


    def _get_contents(self, tree, id_dir, root_dir, traverse=False):
        '''
        tree is [dirpath, dirnames, filenames]
        '''
        directories = []
        files = []
        resp = self.device.ContentDirectory.Browse(ObjectID=id_dir, BrowseFlag='BrowseDirectChildren', Filter='*', StartingIndex=0, RequestedCount=0, SortCriteria='')
        root_xml = minidom.parseString(resp['Result'])
        for node in root_xml.documentElement.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            content = extract_metadata(node)
            if content['type'] == 'item':
                files.append((content['title'], content['uri']))
            if  content['type'] == 'container':
                directories.append(content['title'])
                if traverse:
                    tree = self._get_contents(tree, content['id'], root_dir + '/' + content['title'], traverse)
        tree.append((root_dir, directories, files))
        return tree


    def root_content_id(self):
        ''' return root_id for ContentDirectory '''
        resp = self.device.ContentDirectory.Browse(ObjectID=0, BrowseFlag='BrowseMetadata', Filter='*', StartingIndex=0, RequestedCount=0, SortCriteria='')
        root_xml = minidom.parseString(resp['Result'])
        # TODO case childNodes empty
        for node in root_xml.documentElement.childNodes:
            if node.nodeType == node.ELEMENT_NODE:
                break
        meta = extract_metadata(node)
        return meta['id']


    def play_content(self, content_uri):
        '''
        Play media content
            return tuple (Bool (done), str (reason))
        '''

        try:
            # stop current play
            self.device.AVTransport.Stop(InstanceID=0)
        except upnpclient.soap.SOAPError as _e:
            # ignore error (when not running ?)
            print(_e)
            pass
        try:
            # set content
            self.device.AVTransport.SetAVTransportURI(InstanceID=0, CurrentURI=content_uri, CurrentURIMetaData='')
            # start playing
            self.device.AVTransport.Play(InstanceID=0, Speed='1')
        except AttributeError as _e:
            return (False, str(_e))
        except upnpclient.soap.SOAPError as _e:
            return (False, str(_e))
        return (True, '')



def dlna_discover(discover, timeout, verbosity):
    ''' display DNLA discover '''
    devices = None
    ssdp = upnpclient.ssdp
    devices = ssdp.discover(timeout)
    ndevs = 0
    for dev in sorted(devices, key=lambda d: d.friendly_name):
        if discover == 'smart':
            _t = dev.device_type.split(':')
            if not _t[-2] in ['MediaRenderer', 'MediaServer']:
                continue
        elif discover == 'renderers':
            _t = dev.device_type.split(':')
            if _t[-2] != 'MediaRenderer':
                continue
        elif discover == 'mediaservers':
            _t = dev.device_type.split(':')
            if _t[-2] != 'MediaServer':
                continue
        ndevs += 1
        device = DLNA(device_instance=dev)
        device.show_device(verbosity=verbosity)
    print('Devices listed : {} on {} found'.format(ndevs, len(devices)))
