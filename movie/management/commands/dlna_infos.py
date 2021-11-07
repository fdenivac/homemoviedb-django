# -*- coding: utf-8 -*-
'''
Administration : parse movies an add/update in database

'''


import sys
import locale
import upnpclient

from django.core.management.base import BaseCommand

from movie.dlna import DLNA



class Command(BaseCommand):
    '''
    class Command
    '''
    args = 'DNLA Tools'
    help = 'List available DLNA devices, list media contents.'

    def add_arguments(self, parser):
        # subparsers = parser.add_subparsers(title="DevicesList",
        #                                    dest="subcommand",
        #                                    required=True)


        parser.add_argument('--discover', action='store_true', \
            help='discover DLNA equipments')
        parser.add_argument('--smart_discover', action='store_true', \
            help='discover only pertinent DLNA equipments')
        parser.add_argument('--renderers', action='store_true', \
            help='discover renderers')
        parser.add_argument('--mediaservers', action='store_true', \
            help='discover media servers')
        parser.add_argument('--contents', default=None, \
            help='show contents in DEVICENAME:PATH (ex: --contents=http://192.168.1.3:50001/desc/device.xml;Vidéo/Films')

    def handle(self, *args, **options):
        '''
        Handle command

        Warning : must return None or string, else Exception
        '''
        locale.setlocale(locale.LC_ALL, '')

        devices = None
        if options['discover'] or options['smart_discover'] or options['renderers'] or options['mediaservers']:
            ssdp = upnpclient.ssdp
            devices = ssdp.discover(2)
            for dev in devices:
                if options['smart_discover']:
                    _t = dev.device_type.split(':')
                    if not _t[-2] in ['MediaRenderer', 'MediaServer']:
                        continue
                if options['renderers']:
                    _t = dev.device_type.split(':')
                    if _t[-2] != 'MediaRenderer':
                        continue
                if options['mediaservers']:
                    _t = dev.device_type.split(':')
                    if _t[-2] != 'MediaServer':
                        continue
                device = DLNA(device_instance=dev)
                device.show_device(verbosity=options['verbosity'])

        if options['contents']:
            try:
                dev_uri, content_path = options['contents'].split(';')
            except ValueError:
                print('ERROR: invalid "--contents" argument')
            device = DLNA(device_uri=dev_uri)
            if not device.device:
                sys.exit('ERROR: Device not found for "{}"'.format(dev_uri))
            contents = sorted(device.get_contents(content_path, True), key=lambda x: x[0])
            print('{} contents in "{}" for device "{}" : '.format(len(contents), content_path, device.device.friendly_name))
            for rootdir, dirs, components in contents:
                for name, uri in components:
                    print('{}  {}  {}'.format(rootdir, name, uri))
                for _dir in dirs:
                    print('{}'.format(_dir))

        return None
