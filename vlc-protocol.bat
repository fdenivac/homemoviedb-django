REM Play video in VLC on Windows
REM
REM  Video filename can be :
REM     "vlc://http://DLNASERVER/VIDEOURL"
REM         -> remove 'vlc://' and start VLC
REM     "vlc://VOLUMELABEL:/PATH/FILE"
REM         -> remove 'vlc:// and call python script for replace volume label with letter of volume in line,
REM            then start VLC
Setlocal EnableDelayedExpansion
set url=%~1
set proto=%url:~0,13%
if "%proto%"=="vlc://http://" (
    set url=!url: =%%20!
    start "VLC" "%~dp0vlc.exe" --open "%url:~6%"
) else (
    start "" "C:\Program Files\VideoLAN\VLC\vlc-volumelabel.py"  "%url:~6%"
)
