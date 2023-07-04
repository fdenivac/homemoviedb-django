#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Remote management for MovieDB site

Warning: designed for Windows

"""

import os
import sys
import platform
import shutil
import glob
import logging
import argparse
import subprocess
import getpass
from argparse import RawTextHelpFormatter
import json
from typing import NamedTuple
import textwrap
import requests

from movie.utils import smart_unit, seconds_tostring

if not platform.system() == "Windows":
    sys.exit("This script must be running on Windows")
import win32api


# base URLs for panosite server
URL_LOGIN = "/accounts/login/"
URL_APPEND = "/api/movie/append"
URL_INFO = "/api/movie/info"
URL_DIR = "/api/movies/dir"
URL_UPDATE = "/api/movie/update"
URL_REMOVE = "/api/movie/remove"
URL_INDEXES = "/api/movies/indexes"

# pylint: disable=invalid-name
log = logging.getLogger()


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


class FFProbeResult(NamedTuple):
    """ffmpeg probe result"""

    return_code: int
    json: str
    error: str


def ffprobe(file_path) -> FFProbeResult:
    """return ffprobe in json format"""
    command_array = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    try:
        result = subprocess.run(
            command_array,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf8",
            check=True,
        )
    except (UnicodeDecodeError, subprocess.CalledProcessError) as _e:
        return FFProbeResult(return_code=1212, json="", error=str(_e))
    return FFProbeResult(
        return_code=result.returncode, json=result.stdout, error=result.stderr
    )


def set_video_title(fname, fmt, title):
    """
    Set video title for various format
    """
    if fmt == "matroska,webm":
        return mkv_set_title(fname, title)
    else:
        return ffmpeg_set_title(fname, title)


def ffmpeg_set_title(fname, title):
    """
    Set title propertie for all formats with ffmpeg
    WARNING: not a efficient solution because the title is not modified in place, but a new file is created
    """
    base, ext = os.path.splitext(fname)
    tmp_fname = f"{base}.TITLE_FIXED{ext}"
    command_array = [
        "ffmpeg",
        "-i",
        fname,
        "-metadata",
        f"title={title}",
        "-c:a",
        "copy",
        "-c:v",
        "copy",
        tmp_fname,
    ]
    try:
        subprocess.run(
            command_array,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf8",
            check=True,
        )
        # warning : file is not deleted but just renamed
        os.rename(fname, f"{fname}.bak")
        os.rename(tmp_fname, fname)
        return True
    except (UnicodeDecodeError, subprocess.CalledProcessError) as _e:
        print(_e)
        return False


def mkv_set_title(fname, title):
    """
    Set title propertie on MKV file
        Use MKVToolNix in global path
    """
    if title:
        command_array = [
            "mkvpropedit",
            fname,
            "--edit",
            "info",
            "--set",
            f"title={title}",
        ]
    else:
        command_array = ["mkvpropedit", fname, "--delete", "title"]
    try:
        subprocess.run(
            command_array,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf8",
            check=True,
        )
        # print(result)
        return True
    except (UnicodeDecodeError, subprocess.CalledProcessError) as _e:
        print(_e)
        return False


def smart_probe(ffmpeg_json):
    """add smart infos to original ffmpeg probe"""
    streams = ffmpeg_json.get("streams", [])
    dstreams = {"video": [], "audio": [], "subtitle": []}
    screen_size = ""
    for stream in streams:
        language = (
            f'({stream.get("tags").get("language")})'
            if (stream.get("tags") and stream.get("tags").get("language"))
            else ""
        )
        codec_type = stream.get("codec_type", "unknown")
        if codec_type in ["video", "audio", "subtitle"]:
            dstreams[codec_type].append(f'{stream.get("codec_name")} {language}')
        if codec_type == "video":
            screen_size = f'{stream.get("width", "?")}x{stream.get("height", "?")}'
    codecs = []
    for codec_type in ["video", "audio", "subtitle"]:
        if dstreams[codec_type]:
            codecs.append(codec_type)
    streams = [
        f'{codec_type}: {", ".join(dstreams[codec_type])}' for codec_type in codecs
    ]
    streams = " | ".join(streams)
    ffmpeg_json["smart_streams"] = streams
    ffmpeg_json["format"]["screen_size"] = screen_size
    # fields can be missing (damaged video file ?): force it
    ffmpeg_json["format"]["bit_rate"] = ffmpeg_json["format"].get("bit_rate", 0)
    ffmpeg_json["format"]["duration"] = ffmpeg_json["format"].get("duration", 0)
    # duplicate title in format field
    ffmpeg_json["title"] = ""
    if "tags" in ffmpeg_json["format"]:
        if "title" in ffmpeg_json["format"]["tags"]:
            ffmpeg_json["title"] = ffmpeg_json["format"]["tags"]["title"]
    return ffmpeg_json


class Password(argparse.Action):
    """action ArgumentParser for Password"""

    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            values = getpass.getpass()
        setattr(namespace, self.dest, values)


class APIException(Exception):
    """an remote API Exception"""


class LoginException(Exception):
    """an Login Exception"""


class ManageException(Exception):
    """an local Exception"""


class WebSession:
    """http session on movie site"""

    def __init__(self, args):
        self.args = args
        self.volumes = get_volumes()
        self.labels = {vol: key for key, (vol, _) in self.volumes.items()}
        self.session = None
        self.header = None
        self.cookies = None

    def login(self):
        """login on server"""
        if self.session:  # already login
            return
        #
        # work in session
        self.session = requests.session()

        #
        # get login page
        response = self.session.get(
            self.args.address + URL_LOGIN, auth=("username", "password")
        )
        if response.status_code != 200:
            raise LoginException(
                f"Failed connection : {response.status_code} - {response.reason}"
            )

        # memorize csrf cookie
        csrftoken = response.cookies["csrftoken"]
        # memorize url login in response for login check
        url_login_resp = response.url

        # fill username, password for this login page
        payload = {
            "username": self.args.user,
            "password": self.args.password,
            "csrfmiddlewaretoken": csrftoken,
        }
        # prepare header
        self.header = {
            "Referer": self.args.address,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36",
        }
        response = self.session.post(
            self.args.address + URL_LOGIN, data=payload, headers=self.header
        )
        # detection login failed or not
        if response.url == url_login_resp:
            # if the response.url is the login page => login failed
            raise LoginException(f"Login failed")

        # prepare headers, cookies
        self.header = {
            "Referer": self.args.address,
            "X-CSRFToken": csrftoken,
        }
        self.cookies = {"csrftoken": csrftoken}

    def api_call(self, data, url):
        """send json data to url server and get response"""
        response = self.session.post(
            url=self.args.address + url,
            headers=self.header,
            cookies=self.cookies,
            data={"json": json.dumps(data)},
        )
        if response.status_code != 200:
            raise APIException(response.reason)
        try:
            resp = response.json()
            if resp["code"] < 0:
                raise APIException(resp["reason"])
            return resp
        except json.JSONDecodeError as _e:
            sys.exit("FAILED calling api ", _e, "(can be a process too long)")

    def is_dbfilename(self, name):
        """Test if filename in DB format : label replacing volume letter"""
        name = os.path.normpath(name)
        parts = name.split(":\\")
        if len(parts) > 1 and len(parts[0]) > 1:
            return True
        return False

    def build_dbfilename(self, fname):
        """return database name from filename"""
        # get volume name of file
        fname = os.path.normpath(fname)
        moviepath, _ = os.path.split(fname)
        volname, _ = os.path.splitdrive(moviepath)
        if volname.startswith("\\\\"):
            volname = volname.split("\\")[2]
            dbfname = fname.replace("\\\\" + volname, volname + ":")
        else:
            # replace drive letter with volume name
            try:
                volname, _ = self.volumes[moviepath.lower()[0]]
            except KeyError as _e:
                raise APIException("Bad File Syntax") from _e
            dbfname = volname + fname[1:]
        return dbfname

    def build_osfilename(self, dbfname):
        """return filesystem filename from filename"""
        if not self.is_dbfilename(dbfname):
            return dbfname
        label = dbfname.split(":")[0]
        if label not in self.labels:
            # suppose it is a network share
            return dbfname.replace(label + ":", "\\\\" + label)
        return dbfname.replace(label, self.labels[label], 1)

    def guess_movie(self, fname):
        """get movie from name in [filename, dbfilename, idmovie, fsubtitle]"""
        # try:
        if fname.isdigit():
            # case movie.id
            dbfname = int(fname)
        else:
            dbfname = self.build_dbfilename(fname)
        movie = self.get_movie_infos(dbfname)
        if movie["code"] != 0:
            raise APIException(movie["reason"])
        if fname.isdigit():
            dbfname = movie["file"]
            fname = self.build_osfilename(dbfname)
        # get subtitle file if any
        base, _ = os.path.splitext(fname)
        fsubtitle = base + ".srt"
        if not os.path.exists(fsubtitle):
            fsubtitle = None
        return (fname, dbfname, movie, fsubtitle)

    def supported_file(self, fname):
        """check file supported"""
        _, ext = os.path.splitext(fname)
        if ext.lower() in [".srt", ".jpg", ".vsmeta", ".db", ".idx", ".nfo", ".bak"]:
            return False
        return True

    def get_movie_infos(self, dbfname):
        """get movie infos"""
        return self.api_call({"file": dbfname}, URL_INFO)

    def update_movie_file(self, idmovie, **kwargs):
        """get movie infos"""
        data = {"id": idmovie, **kwargs}
        return self.api_call(data, URL_UPDATE)

    def append_movie(self, datas, **kwargs):
        """append movie"""
        return self.api_call(datas, URL_APPEND)

    def remove_movie_file(self, idmovie, **kwargs):
        """remove movie file"""
        return self.api_call({"id": idmovie, **kwargs}, URL_REMOVE)

    def get_movies_datas(self, offset, count, column):
        """get movies indexes"""
        return self.api_call(
            {"offset": offset, "count": count, "column": column}, URL_INDEXES
        )


class VideoParser(WebSession):
    """Videos parser"""

    def movie_exists(self, fname):
        """Return True if movie file already exists"""
        if not self.valid_file(fname):
            return False
        dbfname = self.build_dbfilename(fname)
        try:
            datas_resp = self.get_movie_infos(dbfname)
        except APIException as _e:
            return False
        return datas_resp["code"] == 0

    def parse_append_file(self, fname, **kwargs):
        """Parse movie file"""
        if not self.valid_file(fname):
            return
        # build filename for DB
        dbfname = self.build_dbfilename(fname)
        print(f'* "{dbfname}" : ', end="")
        try:
            datas_resp = self.get_movie_infos(dbfname)
        except APIException as _e:
            print("FAILED: ", _e)
            return
        exists = datas_resp["code"] == 0
        if exists:
            print("  Already exists in DB => updating")
        else:
            print("  Not found in DB => adding")
        if self.args.verbosity > 0:
            print(json.dumps(datas_resp, indent=4))

        # parse ffmpeg
        if not kwargs.get("id_db"):
            ffprobe_result = ffprobe(file_path=fname)
            if ffprobe_result.return_code != 0:
                print("  ERROR ffprobe")
                print("  ", ffprobe_result.error, file=sys.stderr)
                return
            probe = ffprobe_result.json
        else:
            probe = json.dumps({"json": {"ffprobe": None}})

        #  remote options from arguments line
        options = {
            "simu": self.args.simu,
            "force_parsing": self.args.force_parsing,
            "exact_name": self.args.exact_name,
        }

        # request append/update
        data = {
            "options": json.dumps(options),
            "file": dbfname,
            "id_tmdb": self.args.idtmdb,
            "title": "",
            "year": "",
            "ffprobe": probe,
        }
        if kwargs.get("id_db"):
            data["id_db"] = kwargs.get("id_db")
        datas_resp = self.append_movie(data)
        if self.args.verbosity > 0:
            print(json.dumps(datas_resp, indent=4))
        if datas_resp["num_movies"] in [0, 1]:
            print(f'  {datas_resp["result"]}')
            return
        # dialog choose movie number
        if datas_resp["num_movies"] > 1:
            print(
                f'  Choose a movie among the {datas_resp["num_movies"]} suggestions (or ENTER to skip)'
            )
            for num, (
                id_movie,
                title,
                original_title,
                release_date,
                overview,
                _,
                _,
            ) in enumerate(datas_resp["movies"]):
                original_title = f" ({original_title})" if original_title else ""
                print(
                    f'    {(num + 1):2}- {title}{original_title} [year: {release_date.split("-")[0]}]'
                )
                if overview:
                    lines = textwrap.wrap(overview, 120, break_long_words=False)
                    for line in lines:
                        print("       ", line)
            # loop for choose or skip
            while True:
                try:
                    print(
                        f'Choose a movie number (1 to {datas_resp["num_movies"]}, or ENTER to skip) :'
                    )
                    sel = input()
                    if not sel:
                        return
                    sel = int(sel) - 1
                    if sel >= 0 and sel < datas_resp["num_movies"]:
                        id_movie = datas_resp["movies"][sel][0]
                        # request append/update
                        data = {
                            "options": json.dumps(options),
                            "file": dbfname,
                            "id_tmdb": id_movie,
                            "title": "",
                            "year": "",
                            "ffprobe": ffprobe_result.json,
                        }
                        datas_resp = self.api_call(data, URL_APPEND)
                        if datas_resp["num_movies"] != 1:
                            print(f'  {datas_resp["result"]}')
                        break
                except ValueError:
                    pass

    def parse_directory(self, parse_file, thepath):
        """Parse directory"""
        print(
            f'Parse directory "{thepath}"{" and subdirectories" if not self.args.no_recurs else ""}'
        )
        for root, _, files in os.walk(thepath):
            for filename in files:
                fname = os.path.join(root, filename)
                if self.movie_exists(fname) and not self.args.force_parsing:
                    if self.args.silent_exists:
                        continue
                    print(f'Skip "{fname}" : already exists in DB')
                    continue
                parse_file(fname)

            # continue in sub-directories ?
            if self.args.no_recurs:
                # right when topdown option is True (default)
                break

    def update_missing_files(self, dirpath, files):
        """update database for missing files in directory"""
        volname, _ = os.path.splitdrive(dirpath)
        if volname.startswith("\\\\"):
            volname = volname.split("\\")[2]
            moviedir = dirpath.replace("\\\\" + volname, volname + ":")
        else:
            # replace drive letter with volume name
            volname, _ = self.volumes[dirpath.lower()[0]]
            moviedir = volname + dirpath[1:]

        # get movie files in this directory from database
        response = self.session.post(
            url=self.args.address + URL_DIR,
            headers=self.header,
            cookies=self.cookies,
            data={"json": json.dumps({"dir": moviedir, "recurs": False})},
        )
        datas_resp = response.json()
        print(
            f'Search for missing files in directory "{dirpath}" : {datas_resp["num_movies"]} files in database'
        )
        for movie_file in datas_resp["movies"]:
            print(movie_file)
            _, movie_file = os.path.split(movie_file)
            if not movie_file in files:
                print("Status file to update")
                movie_file = os.path.join(moviedir, movie_file)
                response = self.update_movie_file(movie_file, **{"status": "missing"})
                datas_resp = response.json()
                print("Status updated : ", datas_resp["reason"])

    def valid_file(self, fname):
        """check file supported"""
        _, ext = os.path.splitext(fname)
        if ext.lower() in [".srt", ".jpg", ".vsmeta", ".db", ".idx", ".nfo", ".bak"]:
            if self.args.verbosity > 1:
                print("Skip extension", ext)
            return False
        return True

    def parse_file(self, fname, **kwargs):
        """only parse and display"""
        fname, _, _, _ = self.guess_movie(fname)
        if not self.valid_file(fname):
            return
        # parse ffmpeg
        ffprobe_result = ffprobe(file_path=fname)
        if ffprobe_result.return_code == 0:
            probe = smart_probe(json.loads(ffprobe_result.json))
            title = f' - Title: "{probe["title"]}"' if probe["title"] else ""
            print(f'Parse "{fname}"{title}')
            print(
                "   container: {0} | {1} , rate: {2}, res: {3}, duration: {5}, filesize: {4}".format(
                    probe["format"]["format_name"],
                    probe["smart_streams"],
                    smart_unit(probe["format"]["bit_rate"], "bps"),
                    probe["format"]["screen_size"],
                    smart_unit(probe["format"]["size"], "B"),
                    seconds_tostring(probe["format"]["duration"]),
                )
            )

            # warning if title not equal to filename
            if probe["title"]:
                _, base = os.path.split(fname)
                base, _ = os.path.splitext(base)
                if base != probe["title"]:
                    print("  ", "WARNING : movie title is different to filename")
                    if self.args.fix_title:
                        if self.args.fix_title == "%filename%":
                            title = base
                        elif self.args.fix_title == "%empty%":
                            title = ""
                        else:
                            title = self.args.fix_title
                        if set_video_title(
                            fname, probe["format"]["format_name"], title
                        ):
                            print("  ", "Fix title done")
                        else:
                            print("  ", "FAILED to set title")

        else:
            print(f'ERROR PARSING "{fname}"')
            print("  ", ffprobe_result.error, file=sys.stderr)

    def check_destdir(self, destdir):
        """check destination directory"""
        destdir = self.build_osfilename(destdir)
        if not os.path.isdir(destdir):
            sys.exit(f'FAILED: destination "{destdir}" is not a directory')
        return destdir

    def move_or_copy(self, fname):
        """copy or move file"""

        def operate(destdir, mode):
            destdir = self.check_destdir(destdir)
            _, basename = os.path.split(fname)
            # get subtitle file
            _base, _ = os.path.splitext(fname)
            fsubtitle = _base + ".srt"
            if not os.path.exists(fsubtitle):
                fsubtitle = None
            # buid destination
            destfile = os.path.join(destdir, basename)
            if os.path.exists(destfile):
                raise ManageException(f"Skip movie : file already exists ({destfile})")
            if mode == "copy":
                print(f'  Copying "{fname}" to "{destdir}" ...', end="")
                if not self.args.simu:
                    shutil.copy(fname, destdir)
                    if fsubtitle:
                        shutil.copy(fsubtitle, destdir)
            elif mode == "move":
                print(f'  Moving "{fname}" to "{destdir}" ...', end="")
                if not self.args.simu:
                    shutil.move(fname, destdir)
                    if fsubtitle:
                        shutil.move(fsubtitle, destdir)
                else:
                    destfile = fname
            print()
            return destfile

        if not (self.args.copy_dest or self.args.move_dest):
            return None
        # move file
        if self.args.copy_dest:
            return operate(self.args.copy_dest, "copy")
        if self.args.move_dest:
            return operate(self.args.move_dest, "move")
        return None

    def process(self):
        """process all files"""
        self.login()
        if self.args.parse_only:
            parse_file = self.parse_file
        else:
            parse_file = self.parse_append_file
        # check parameters
        if self.args.copy_dest:
            self.check_destdir(self.args.copy_dest)
        if self.args.move_dest:
            self.check_destdir(self.args.move_dest)
        args_parse = {}

        for glob_name in self.args.filelist:
            glob_name = glob_name.rstrip("\r\n")
            if glob_name.isdigit():
                # in case of copy or move : for not parsing and search in TMDB
                args_parse["id_db"] = glob_name
                # get real name
                glob_name, _, _, _ = self.guess_movie(glob_name)
            # filename in DB format (label replacing volume letter)
            glob_name = self.build_osfilename(glob_name)
            for fname in glob.glob(glob_name):
                if os.path.isfile(fname):
                    if self.args.copy_dest or self.args.move_dest:
                        pass
                    elif self.movie_exists(fname) and not (
                        self.args.force_parsing or self.args.fix_title
                    ):
                        if self.args.silent_exists:
                            continue
                        print(f'Skip "{fname}" : already exists in DB')
                        continue
                    print(f'Append "{fname}" :')
                    try:
                        dest = self.move_or_copy(fname)
                        if not dest:
                            dest = fname
                    except ManageException as _e:
                        print("  ", _e)
                        continue
                    try:
                        parse_file(dest, **args_parse)
                    except APIException as _e:
                        print("  FAILED:", _e)
                elif os.path.isdir(fname):
                    self.parse_directory(parse_file, fname)


class VideoMover(WebSession):
    """move movie files and update DB"""

    def __init__(self, args):
        super().__init__(args)
        self.dest_dir = None

    def move_file(self, fname):
        """move a file"""
        # move file
        try:
            fname, dbname, movie, fsubtitle = self.guess_movie(fname)
            print(f'Moving "{dbname}" ({fname}) ... ', end="")
            if movie["code"] != 0:
                print('movie not found on server. Use "append" function')
                return
            if not self.args.simu:
                shutil.move(fname, self.dest_dir)
                if fsubtitle:
                    shutil.move(fsubtitle, self.dest_dir)
        except (shutil.SameFileError, shutil.Error) as _e:
            print(f'\n  FAILED to move "{dbname}" : {_e}')
            return
        print(" done")

        # update filename
        _, destname = os.path.split(fname)
        destname = os.path.join(self.dest_dir, destname)
        destname = self.build_dbfilename(destname)
        try:
            self.update_movie_file(
                movie["id"], **{"file": destname, "simu": self.args.simu}
            )
        except APIException as _e:
            print(f'FAILED to update: "{fname}" {_e}')
            return

    def process(self):
        """process moving files"""

        # check destination directory
        self.dest_dir = self.args.dest[0]
        if not os.path.isdir(self.dest_dir):
            # maybe a dbfilename ? try convert to os filename
            self.dest_dir = self.build_osfilename(self.dest_dir)
            if not os.path.isdir(self.dest_dir):
                print(f'FAILED: destination ("{self.dest_dir}") must be a directory')
                return

        # login on server
        self.login()

        # process files
        for glob_name in self.args.filelist:
            glob_name = glob_name.rstrip("\r\n")
            if glob_name.isdigit():
                # movie reference by id
                self.move_file(glob_name)
                continue
            if self.is_dbfilename(glob_name):
                # filename in DB format (label replacing volume letter)
                glob_name = self.build_osfilename(glob_name)
            count = 0
            for fname in glob.glob(glob_name):
                count += 1
                if os.path.isfile(fname):
                    self.move_file(fname)
                elif os.path.isdir(fname):
                    print(f"FAILED: moving directory not supported ({fname})")
                    continue
            if not count:
                print(f'FAILED: no movie found with name "{glob_name}" ')


class VideoRemover(WebSession):
    """remove MovieFile entry"""

    def __init__(self, args):
        super().__init__(args)
        self.dest_dir = None

    def remove_file(self, fname):
        """move a file"""

        # remove MovieFile on server
        try:
            fname, dbfname, movie, fsubtitle = self.guess_movie(fname)
            print(f'Removing file reference from database for "{dbfname}"')
            self.remove_movie_file(movie["id"], **{"simu": self.args.simu})
        except APIException as _e:
            print(f'FAILED to remove "{fname}" : {_e}')
            return
        # remove file from volume
        try:
            if self.args.remove_file:
                print(f'Removing "{fname}"')
                if not self.args.simu:
                    os.remove(fname)
                    if fsubtitle:
                        os.remove(fsubtitle)
        except Exception as _e:
            print(f'\nFAILED: to remove "{fname}" : {_e}')
            return

    def process(self):
        """process files"""
        # login on server
        self.login()

        # process files
        for glob_name in self.args.filelist:
            glob_name = glob_name.rstrip("\r\n")
            if glob_name.isdigit():
                # movie reference by id
                self.remove_file(glob_name)
                continue
            if self.is_dbfilename(glob_name):
                # filename in DB format (label replacing volume letter)
                glob_name = self.build_osfilename(glob_name)
            for fname in glob.glob(glob_name):
                if os.path.isfile(fname):
                    self.remove_file(fname)
                elif os.path.isdir(fname):
                    print(f"FAILED: removing directory not supported ({fname})")
                    continue


class VideoStatus(WebSession):
    """Videos status"""

    def status(self, fname):
        """check file status"""
        if not self.supported_file(fname):
            return
        # build filename for DB
        dbfname = self.build_dbfilename(fname)
        try:
            datas_resp = self.get_movie_infos(dbfname)
        except APIException as _e:
            print("FAILED: ", _e)
            return
        exists = datas_resp["code"] == 0
        if exists:
            print(f'"{fname}" : already exists in DB')
        else:
            print(f'"{fname}" : not found in DB')

    def check_db_movies(self):
        """check all movies files"""
        # get all movies files
        try:
            datas_resp = self.get_movies_datas(0, -1, "file")
        except APIException as _e:
            print("FAILED: ", _e)
            return
        print(f"Total movie files : {datas_resp['num_datas']}")
        for movie_file in datas_resp["datas"]:
            movie_file = self.build_osfilename(movie_file)
            exists = os.path.exists(movie_file)
            print(f'{"OK" if exists else "FAILED"} : "{movie_file}"')

    def process(self):
        """process files"""
        # login on server
        self.login()

        if not self.args.filelist:
            return self.check_db_movies()

        # process files
        for glob_name in self.args.filelist:
            glob_name = glob_name.rstrip("\r\n")
            if glob_name.isdigit():
                # movie reference by id
                self.status(glob_name)
                continue
            if self.is_dbfilename(glob_name):
                # filename in DB format (label replacing volume letter)
                glob_name = self.build_osfilename(glob_name)
            for fname in glob.glob(glob_name):
                if os.path.isfile(fname):
                    self.status(fname)
                elif os.path.isdir(fname):
                    for root, _, files in os.walk(fname):
                        for filename in files:
                            fname = os.path.join(root, filename)
                            # if self.movie_exists(fname) and not self.args.force_parsing:
                            #     if self.args.silent_exists:
                            #         continue
                            #     print(f'Skip "{fname}" : already exists in DB')
                            #     continue
                            self.status(fname)


def main():
    """Main entry from command line"""

    if platform.system() != "Windows":
        sys.exit("Sorry, this tool is designed to run only on Windows")

    #
    # command parser
    #
    parser = argparse.ArgumentParser(
        description="""Home MovieDB remote management
  Examples of Commands :
    # parse
        manage_moviesite.py append --parse-only  "MovieStore:\\video\\Films\\*.mkv"
    # suppress internal name for DLNA
        manage_moviesite.py append --parse-only --fix-title= %empty% 691
    # parse / append
        manage_moviesite.py append --silent-exists --no-recurs "\\\\DiskStation\\video\\Films\\*"
        manage_moviesite.py append "DiskStation:\\video\\Films\\Last Year.mp4"
    # copy / parse / append
        python -u ./manage_moviesite.py append --copy-dest="DiskStation:\\video\\Films" "G:\\Films\\The*.mkv"
    # move / parse / append
        manage_moviesite.py append --move-dest="DiskStation:\\video\\Films" "G:\\Films\\Tranfert\\*"
    # move moviefiles by DB indexes
        manage_moviesite.py move 528 415 535 "I:\\Films"
        manage_moviesite.py move 528 415 535 "MovieStore:\\Films"
    # remove movie files from DB
        manage_moviesite.py remove 804 620
    # remove movie files from DB and disk
        manage_moviesite.py remove 804 620 --remove-file
    # status of movie files
        manage_moviesite.py status
""",
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "-a",
        "--address",
        required=True,
        help="MovieDB site url",
    )
    parser.add_argument("-u", "--user", help="Enter your username")
    parser.add_argument(
        "-p", "--password", action=Password, nargs="?", help="Enter your password"
    )

    parser.add_argument(
        "-v", "--verbosity", type=int, default=0, help="output verbosity"
    )
    parser.add_argument(
        "--simu", action="store_true", help="don't make any actions = simulation"
    )

    parser.add_argument("--log", help="log on file")

    # create subparser
    subparsers = parser.add_subparsers(help=": availables commands", dest="action")

    # subparser: parse dirs for movies append
    sp1 = subparsers.add_parser(
        "append",
        description="Parse movies to http MoviesDB site",
        help=": Parse movies for append to http MoviesDB site",
    )

    sp1.add_argument("filelist", help="Files and Directories", nargs="*")
    sp1.add_argument(
        "--idtmdb", type=int, help="TMDB id for unique movie on command line"
    )

    sp1.add_argument(
        "--force-parsing",
        action="store_true",
        help="force parsing, even if file already in database",
    )
    sp1.add_argument(
        "--exact-name", action="store_true", help="restrict search to exact movie name"
    )
    sp1.add_argument(
        "--no-recurs", action="store_true", help="don't parse sub-directories"
    )
    sp1.add_argument(
        "--silent-exists", action="store_true", help="Do not display existant movies"
    )
    sp1.add_argument(
        "--fix-title",
        default="",
        help="Remove title metadata (usefull with DLNA) : %%empty%%, %%filename%%, %%title%%, string ",
    )
    sp1.add_argument(
        "--copy-dest",
        default="",
        help="Directory where copy video files",
    )
    sp1.add_argument(
        "--move-dest",
        default="",
        help="Directory where move video files",
    )

    sp1.add_argument(
        "--parse-only",
        action="store_true",
        help="parse video files only (without connect to http server)",
    )

    # subparser: move videos present in database
    sp2 = subparsers.add_parser(
        "move",
        description="Move movies referenced in database and update database",
        help=": Move movies and update MoviesDB site",
    )

    sp2.add_argument(
        "filelist",
        nargs="+",
        help="Files and Directories (names can be in DB filename format  (label replacing volume letter), or MovieFile id",
    )
    sp2.add_argument(
        "dest", nargs=1, help="Destination directory (names in DB filename or not)"
    )

    # subparser: remove MovieFile
    sp3 = subparsers.add_parser(
        "remove",
        description='Remove "MovieFile" database entry',
        help=': Remove "MovieFile" database entry',
    )

    sp3.add_argument(
        "filelist",
        nargs="+",
        help="Files and Directories (names can be in DB filename format (label replacing volume letter), or MovieFile id",
    )
    sp3.add_argument(
        "--remove-file", action="store_true", help="Remove movie file from volume"
    )

    # subparser: check movie status
    sp4 = subparsers.add_parser(
        "status",
        description="Get status of movie files",
        help=": Get status of movie files",
    )

    sp4.add_argument(
        "filelist",
        nargs="*",
        help="Files and Directories (names can be in DB filename format (label replacing volume letter), or MovieFile id",
    )

    args = parser.parse_args()

    #
    # logging
    if args.log:
        # basicConfig doesn't support utf-8 encoding yet (?)
        #   logging.basicConfig(filename=args.log, level=logging.INFO, encoding='utf-8')
        # use work-around :
        log.setLevel(logging.INFO)
        handler = logging.FileHandler(args.log, "a", "utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        log.addHandler(handler)
    log.info("ManageMovieDB start")
    log.info("arguments: %s", " ".join(sys.argv[1:]))

    if args.action == "append":
        if args.idtmdb and (len(args.filelist) > 1 or os.path.isdir(args.filelist[0])):
            sys.exit('The "idtmdb" option must be used for a unique movie file')
        VideoParser(args).process()

    elif args.action == "move":
        VideoMover(args).process()

    elif args.action == "remove":
        VideoRemover(args).process()

    elif args.action == "status":
        VideoStatus(args).process()


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError as _e:
        print(_e)
    # protect main from IOError occuring with a pipe command
    except IOError as _e:
        if _e.errno not in [22, 32]:
            raise _e
    except SystemExit as _e:
        print(f"Exit with code {_e}")
    except LoginException as _e:
        print(_e)
    except KeyboardInterrupt as _e:
        print("Interrupt by user !")
    log.info("ManageMovieDB end")
