#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Remote management for MovieDB site

Warning: designed for Windows

"""

import os
import sys
import platform
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

if platform.system() == "Windows":
    import win32api


# base URLs for panosite server
URL_LOGIN = "/accounts/login/"
URL_APPEND = "/api/movie/append"
URL_INFO = "/api/movie/info"
URL_DIR = "/api/movies/dir"
URL_STATUS = "/api/movie/status"

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


def smart_size(size, unit="B"):
    """return int size in string smart form : KB, MB, GB, TB"""
    if isinstance(size, str):
        size = int(size)
    if size > 1000 * 1000 * 1000 * 1000:
        return "%.2f T%s" % (size / (1000 * 1000 * 1000 * 1000.0), unit)
    if size > 1000 * 1000 * 1000:
        return "%.2f G%s" % (size / (1000 * 1000 * 1000.0), unit)
    if size > 1000 * 1000:
        return "%.2f M%s" % (size / (1000 * 1000.0), unit)
    if size > 1000:
        return "%.2f K%s" % (size / (1000.0), unit)
    return "%.2f %s" % (size, unit)


def sec_to_duration(value):
    """convert seconds to duration hh:mm:ss"""
    seconds = float(value)
    return "%02d:%02d:%02d" % (seconds // 3600, (seconds // 60) % 60, seconds % 60)


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
    tmp_fname = "{}.TITLE_FIXED{}".format(base, ext)
    command_array = [
        "ffmpeg",
        "-i",
        fname,
        "-metadata",
        "title={}".format(title),
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
        # TODO not rename but remove :
        os.rename(fname, "{}.bak".format(fname))
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
            "{}".format(fname),
            "--edit",
            "info",
            "--set",
            "title={}".format(title),
        ]
    else:
        command_array = ["mkvpropedit", "{}".format(fname), "--delete", "title"]
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
        "%s: %s" % (codec_type, ", ".join(dstreams[codec_type]))
        for codec_type in codecs
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


class VideoParser:
    """Videos parser"""

    def __init__(self, args):
        self.args = args
        # volumes name online
        self.volumes = get_volumes()
        self.session = None
        self.header = None
        self.cookies = None

    def login(self):
        """initialise login on server"""
        #
        # work in session
        self.session = requests.session()

        #
        # get login page
        response = self.session.get(
            self.args.address + URL_LOGIN, auth=("username", "password")
        )
        if response.status_code != 200:
            print("  == ERROR ==", response.status_code, response.reason)
            return

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
            print("== Login failed == ")
            # the response.reason is "OK" and response.text is the login page
            return

        # prepare headers, cookies
        self.header = {
            "Referer": self.args.address,
            "X-CSRFToken": csrftoken,
        }
        self.cookies = {"csrftoken": csrftoken}

    def parse_append_file(self, fname):
        """Parse movie file"""
        if not self.valid_file(fname):
            return
        # get volume name of file
        moviepath, _ = os.path.split(fname)
        volname, _ = os.path.splitdrive(moviepath)
        if volname.startswith("\\\\"):
            volname = volname.split("\\")[2]
            dbfname = fname.replace("\\\\" + volname, volname + ":")
        else:
            # replace drive letter with volume name
            volname, _ = self.volumes[moviepath.lower()[0]]
            dbfname = volname + fname[1:]

        # get infos
        response = self.session.post(
            url=self.args.address + URL_INFO,
            headers=self.header,
            cookies=self.cookies,
            data={"json": json.dumps({"file": dbfname, "id_tmdb": self.args.idtmdb})},
        )
        datas_resp = response.json()
        if datas_resp["code"] < 0:
            print('  failed with reason "{}"'.format(datas_resp["reason"]))
            return
        exists = datas_resp["code"] == 0

        # if not (not exists or args.force_parsing):
        if exists and not self.args.force_parsing:
            if not self.args.silent_exists:
                print('Parse "{0}" :'.format(fname))
                print("  already exists in DB => skipped")
            return
        print('Parse "{0}" :'.format(fname))
        if exists:
            print("  Already exists in DB => updating")
        else:
            print("  Not found in DB => adding")
        if self.args.verbosity > 0:
            print(json.dumps(datas_resp, indent=4))

        # parse ffmpeg
        ffprobe_result = ffprobe(file_path=fname)
        if ffprobe_result.return_code != 0:
            print("  ERROR ffprobe")
            print(ffprobe_result.error, file=sys.stderr)

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
            "ffprobe": ffprobe_result.json,
        }
        response = self.session.post(
            url=self.args.address + URL_APPEND,
            headers=self.header,
            cookies=self.cookies,
            data={"json": json.dumps(data)},
        )
        datas_resp = response.json()
        if self.args.verbosity > 0:
            print(json.dumps(datas_resp, indent=4))
        if datas_resp["num_movies"] in [0, 1]:
            print("  {}".format(datas_resp["result"]))
            return
        # dialog choose movie number
        if datas_resp["num_movies"] > 1:
            print(
                "  Choose a movie among the {} suggestions (or ENTER to skip)".format(
                    datas_resp["num_movies"]
                )
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
                original_title = (
                    " ({})".format(original_title) if original_title else ""
                )
                print(
                    "    {:2}- {}{} [year: {}]".format(
                        num + 1, title, original_title, release_date.split("-")[0]
                    )
                )
                if overview:
                    lines = textwrap.wrap(overview, 120, break_long_words=False)
                    for line in lines:
                        print("       ", line)
            # loop for choose or skip
            while True:
                try:
                    print(
                        "Choose a movie number ({} to {}, or ENTER to skip) :".format(
                            1, datas_resp["num_movies"]
                        )
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
                        response = self.session.post(
                            url=self.args.address + URL_APPEND,
                            headers=self.header,
                            cookies=self.cookies,
                            data={"json": json.dumps(data)},
                        )
                        datas_resp = response.json()
                        if datas_resp["num_movies"] != 1:
                            print("  {}".format(datas_resp["result"]))
                        break
                except ValueError:
                    pass

    def parse_directory(self, parse_file, thepath):
        """Parse directory"""
        print(
            'Parse directory "%s"%s'
            % (thepath, " and subdirectories" if not self.args.no_recurs else "")
        )
        for root, _, files in os.walk(thepath):
            for filename in files:
                fname = os.path.join(root, filename)
                parse_file(fname)

            # update status for missing files
            # TODO to keep ? self.update_missing_files(root, files)

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
            'Search for missing files in directory "{}" : {} files in database'.format(
                dirpath, datas_resp["num_movies"]
            )
        )
        for movie_file in datas_resp["movies"]:
            print(movie_file)
            _, movie_file = os.path.split(movie_file)
            if not movie_file in files:
                print("Status file to update")
                movie_file = os.path.join(moviedir, movie_file)
                response = self.session.post(
                    url=self.args.address + URL_STATUS,
                    headers=self.header,
                    cookies=self.cookies,
                    data={
                        "json": json.dumps({"file": movie_file, "status": "missing"})
                    },
                )
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

    def parse_file(self, fname):
        """only parse and display"""
        if not self.valid_file(fname):
            return
        # parse ffmpeg
        ffprobe_result = ffprobe(file_path=fname)
        if ffprobe_result.return_code == 0:
            probe = smart_probe(json.loads(ffprobe_result.json))
            title = ' - Title: "{}"'.format(probe["title"]) if probe["title"] else ""
            print('Parse "{}"{}'.format(fname, title))
            print(
                "   container: {0} | {1} , rate: {2}, res: {3}, duration: {5}, filesize: {4}".format(
                    probe["format"]["format_name"],
                    probe["smart_streams"],
                    smart_size(probe["format"]["bit_rate"], "bps"),
                    probe["format"]["screen_size"],
                    smart_size(probe["format"]["size"]),
                    sec_to_duration(probe["format"]["duration"]),
                )
            )

            # warning if title not equal to  filename
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
                        elif self.args.fix_title == "%title%":
                            # TODO : retrieve title from web site
                            print("TODO")
                        else:
                            title = self.args.fix_title
                        if set_video_title(
                            fname, probe["format"]["format_name"], title
                        ):
                            print("  ", "Fix title done")
                        else:
                            print("  ", "FAILED to set title")

        else:
            print('ERROR PARSING "{}"'.format(fname))
            print("  ", ffprobe_result.error, file=sys.stderr)

    def process(self):
        """process all files"""
        if self.args.parse_only:
            parse_file = self.parse_file
        else:
            self.login()
            parse_file = self.parse_append_file

        for glob_name in self.args.filelist:
            glob_name = glob_name.rstrip("\r\n")
            for fname in glob.glob(glob_name):
                if os.path.isfile(fname):
                    parse_file(fname)
                elif os.path.isdir(fname):
                    self.parse_directory(parse_file, fname)


def main():
    """Main entry from command line"""

    if platform.system() != "Windows":
        sys.exit("Sorry, this tool is designed to run only on Windows")

    #
    # command parser
    #
    parser = argparse.ArgumentParser(
        description="Append movies to http MoviesDB site",
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument("filelist", help="Files and Directories", nargs="*")
    parser.add_argument(
        "--idtmdb", type=int, help="TMDB id for unique movie on command line"
    )

    parser.add_argument(
        "-a",
        "--address",
        default="http://diskstation:6062",
        help="MovieDB site url (default=%(default)s)",
    )

    parser.add_argument("-u", "--user", help="Enter your username")
    parser.add_argument(
        "-p", "--password", action=Password, nargs="?", help="Enter your password"
    )

    parser.add_argument(
        "--force-parsing",
        action="store_true",
        help="force parsing, even if file already in database",
    )
    parser.add_argument(
        "--exact-name", action="store_true", help="restrict search to exact movie name"
    )
    parser.add_argument(
        "--no-recurs", action="store_true", help="don't parse sub-directories"
    )
    parser.add_argument(
        "--silent-exists", action="store_true", help="Do not display existant movies"
    )
    #    parser.add_argument('--fix-title', action='store_true', \
    parser.add_argument(
        "--fix-title",
        default="",
        help="Remove title metadata (usefull with DLNA) : %%empty%%, %%filename%%, %%title%%, string ",
    )

    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="parse video files only (without connect to http server)",
    )

    parser.add_argument(
        "-v", "--verbosity", type=int, default=0, help="output verbosity"
    )
    parser.add_argument(
        "--simu", action="store_true", help="don't make any actions = simulation"
    )

    parser.add_argument("--log", help="log on file")
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

    if args.idtmdb and (len(args.filelist) > 1 or os.path.isdir(args.filelist[0])):
        sys.exit('The "idtmdb" option must be used for a unique movie file')

    VideoParser(args).process()


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
        pass
    log.info("ManageMovieDB end")
