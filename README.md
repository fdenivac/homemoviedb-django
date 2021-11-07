# Home Movie Catalog

A basic web site built around django and a sqlite database. The purpose is to find and describe movies available on various locations in a home environment.
  
Movies are parsed by ffmeg and metadata taken from TMBD site via API (movie name guessed from filename) and stored in a local database.

The site acts as a DLNA controler : videos stored on DLNA devices (as synology) can be played on DLNA renderer (as TV).

Each volume disk label is used in place of windows drive letter, so, they must be unique.

Tested environment :
- Web site installed on Linux (Synology)
- Command management tool (manage_moviesite.py) on Windows
- DLNA Samsung TV
    
***
## Install

- install python dependencies
    pip install -r requirements.txt

- install ffmpeg and accessible in command path

- configure settings.py :
    
  - Modify Internationalization section as needed

  - Set VOLUMES variable for declare volumes used and DLNA infos

    For find DLNA informations use

        python manage.py dlna_infos --smart_discover -v 0
    
    Example :

        python manage.py dlna_infos --smart_discover -v 0
        Device Friendly Name: DiskStation
            model description: Synology DLNA/UPnP Media Server
            model name: DS218
            location: http://192.168.1.23:50001/desc/device.xml
            device name: http://192.168.1.23:50001/desc/device.xml
            device type: urn:schemas-upnp-org:device:MediaServer:1
        Device Friendly Name: [TV]UE46D6500
            model description: Samsung TV DMR
            model name: UE46D6500
            location: http://192.168.1.15:52235/dmr/SamsungMRDesc.xml
            device name: http://192.168.1.15:52235/dmr/SamsungMRDesc.xml
            device type: urn:schemas-upnp-org:device:MediaRenderer:1

    ... and declare volume label to used, and DLNA device names :

        VOLUMES = [
            # for each volume :
            #   (volume_label, volume_alias, volume_type, (DLNA device name, root for movies))
            (ALL_VOLUMES, ALL_VOLUMES, ''),
            ('DiskStation', 'Synology', 'network', ('http://192.168.1.23:50001/desc/device.xml', 'Vidéo/Films')),
            ('OldMedias', 'Archives', 'harddisk'),
        ]

        DLNA_RENDERERS = [
            # for each renderer :
            #   (DLNA Device name, Smart name)
            ('http://192.168.1.15:52235/dmr/SamsungMRDesc.xml', 'Bedroom'),
            ('http://192.168.1.17:52235/dmr/SamsungMRDesc.xml', 'Living Room'),
        ]

  - Modify home page (movie/templates/movie/home.html) for correct links (disk labels, ...)

  - Initialize django :

        python manage.py migrate
        ...
        python manage.py createsuperuser
        ...
 
 - Add movies to database :

        python manage.py movieparsing  G:\\Films

    or remotely, if  server is not installed locally (use superuser created):

        python manage_moviesite.py --password --user=john  "G:\Movies" "\\DiskStation\video\Movies"

 - For testing

        python manage.py runserver

