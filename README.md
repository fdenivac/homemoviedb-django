# Home Movie Catalog

A basic web site built around django and a sqlite database. The purpose is to find and describe movies available on various locations in a home environment.

The local sqlite database stores :
- technical informations on video files (audio/video encoding, streams available, duration...), retrieved with ffprobe (ffmpeg tool)
- movie metadatas (title, release year, posters, team, ...), taken from TMBD site (via python api)

The site acts as a DLNA controler : videos stored on DLNA devices (as synology) can be played on DLNA renderer (as TV).
Videos can be played too embeded in web page (but with limited support via HTML 5 _video_ tag), or externally in VLC (require to install [vlc_protocol](https://github.com/stefansundin/vlc-protocol) )


Because the database uses disk labels names instead of disk letters in video filenames, these disk labels names must be unique

Tested environment :
- Web site installed on Linux (Synology)
- Command management tool (manage_moviesite.py) on Windows
- DLNA Samsung TV
    
***
## Install

- install python dependencies
    pip install -r requirements.txt

- install ffmpeg, and add bin folder to the system path

- configure settings.py :
    
  - If user login is not required, comment line "_'global_login_required.GlobalLoginRequiredMiddleware'_" in section MIDDLEWARE

  - Set "_USE_NO_USER_PASSWORD = True_" for user login without password (users created with "_manage.py createuser_")

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

            # specific name for view video on computer :
            ('browser', 'View in Browser'),
            ('vlc', 'View in VLC'),            
        ]

- Modify home page (movie/templates/movie/home.html) for correct links (disk labels, ...)

- Initialize django :

        python manage.py migrate
        ...
        python manage.py collectstatic
        ...        
        python manage.py createsuperuser
        ...
 
- Add movies to database (Windows only):

    locally on web server:

        python manage.py movieparsing  G:\\Films

    or remotely, if server is not installed locally (use superuser created):

        python manage_moviesite.py --password --user=john  "G:\Movies" "\\DiskStation\video\Movies"

- For testing

        python manage.py runserver

- For viewing video on PC, install [vlc_protocol](https://github.com/stefansundin/vlc-protocol) scripts, and next, copy vlc-volumelabel.py and vlc-protocol.bat in VLC directory.

<br>
<br>

# About DLNA

Many DLNA servers use the metadata 'title' of files as content name. If not present, the filename is used as title.

Because "Home video catalog" can play DLNA video only if the video filemane is equal to the DLNA title, 
the _manage_moviesite.py_ has an option **--fix-title** for remove video metadata _title_ from movie.

        manage_moviesite.py --fix-title=%empty% \\\\synology\\video\\Films\\*



