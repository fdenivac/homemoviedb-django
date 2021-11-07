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
if platform.system() == 'Windows':
    import win32api


# base URLs for panosite server
URL_LOGIN = '/accounts/login/'
URL_APPEND = '/api/movie/append'
URL_INFO = '/api/movie/info'
URL_DIR = '/api/movies/dir'
URL_STATUS = '/api/movie/status'

# pylint: disable=invalid-name
log = logging.getLogger()



def get_volumes():
    '''
    Returns volumes dictionary keyed by letter :
        volumes[KEY] = (volume_name, serial_number), (...) ]
    '''
    volumes = {}
    drives = win32api.GetLogicalDriveStrings()
    drives = drives.lower().split('\000')[:-1]
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
    ''' ffmpeg probe result'''
    return_code: int
    json: str
    error: str

def ffprobe(file_path) -> FFProbeResult:
    ''' return ffprobe in json format '''
    command_array = ["ffprobe",
                     "-v", "quiet",
                     "-print_format", "json",
                     "-show_format",
                     "-show_streams",
                     file_path]
    try:
        result = subprocess.run(command_array, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf8', check=True)
    except (UnicodeDecodeError, subprocess.CalledProcessError) as _e:
        return FFProbeResult(return_code=1212, json='', error=str(_e))
    return FFProbeResult(return_code=result.returncode,
                         json=result.stdout,
                         error=result.stderr)



class Password(argparse.Action):
    ''' action ArgumentParser for Password '''
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            values = getpass.getpass()
        setattr(namespace, self.dest, values)



def main():
    ''' Main entry from command line  '''

    if platform.system() != 'Windows':
        sys.exit('Sorry, this tool is designed to run only on Windows')

    #
    # command parser
    #
    parser = argparse.ArgumentParser(description='Append movies to http MoviesDB site',
                                     formatter_class=RawTextHelpFormatter)

    parser.add_argument('filelist', help='Files and Directories', nargs='*')
    parser.add_argument('--idtmdb', type=int, \
        help='TMDB id for unique movie on command line')

    parser.add_argument('-a', '--address', default='http://localhost:8000', \
        help='MovieDB site url (default=%(default)s)')

    parser.add_argument('-u', '--user',\
        help='Enter your username')
    parser.add_argument('-p', '--password', action=Password, nargs='?',\
        help='Enter your password')

    parser.add_argument('--force-parsing', action='store_true', \
            help='force parsing, even if file already in database')
    parser.add_argument('--exact-name', action='store_true', \
            help='restrict search to exact movie name')
    parser.add_argument('--no-recurs', action='store_true', \
        help='don\'t parse sub-directories (no recursivity)')
    parser.add_argument('--silent-exists', action='store_true', \
        help='Do not display existant movies')
    parser.add_argument('-v', '--verbosity', type=int, default=0, \
        help='don\'t make any actions = simulation')

    parser.add_argument('--simu', action='store_true', \
        help='don\'t make any actions = simulation')

    parser.add_argument('--log', help='log on file')
    args = parser.parse_args()

    #
    # logging
    if args.log:
        # basicConfig doesn't support utf-8 encoding yet (?)
        #   logging.basicConfig(filename=args.log, level=logging.INFO, encoding='utf-8')
        # use work-around :
        log.setLevel(logging.INFO)
        handler = logging.FileHandler(args.log, 'a', 'utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        log.addHandler(handler)
    log.info('ManageMovieDB start')
    log.info('arguments: %s', ' '.join(sys.argv[1:]))

    #
    # server urls
    url_login = args.address + URL_LOGIN
    url_append = args.address + URL_APPEND
    url_infos = args.address + URL_INFO
    url_dir = args.address + URL_DIR
    url_status = args.address + URL_STATUS


    # volumes name inline
    volumes = get_volumes()

    #
    # work in session
    session = requests.session()

    #
    # get login page
    response = session.get(url_login, auth=('username', 'password'))
    if response.status_code != 200:
        print('  == ERROR ==', response.status_code, response.reason)
        return

    # memorize csrf cookie
    csrftoken = response.cookies['csrftoken']
    # memorize url login in response for login check
    url_login_resp = response.url

    # fill username, password for this login page
    payload = {'username': args.user, 'password': args.password, 'csrfmiddlewaretoken':csrftoken}
    # prepare header
    header = {
        'Referer' : args.address,
        'Content-Type':'application/x-www-form-urlencoded',
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
    }
    response = session.post(url_login, data=payload, headers=header)
    # detection login failed or not
    if response.url == url_login_resp:
        print('== Login failed == ')
        # the response.reason is "OK" and response.text is the login page
        return

    #
    #  options for remote, from arguments line
    options = {
        'simu' : args.simu,
        'force_parsing' : args.force_parsing,
        'exact_name' : args.exact_name,
    }


    # prepare headers, cookies
    header = {
        'Referer' : args.address,
        'X-CSRFToken' : csrftoken,
    }
    cookies = {'csrftoken' : csrftoken}


    def parse_file(fname):
        ''' Parse movie file '''
        # get volume name of file
        moviepath, _ = os.path.split(fname)
        volname, _ = os.path.splitdrive(moviepath)
        if volname.startswith('\\\\'):
            volname = volname.split('\\')[2]
            dbfname = fname.replace('\\\\' + volname, volname + ':')
        else:
            # replace drive letter with volume name
            volname, _ = volumes[moviepath.lower()[0]]
            dbfname = volname + fname[1:]

        # get infos
        response = session.post(
            url=url_infos,
            headers=header,
            cookies=cookies,
            data={'json': json.dumps({'file':dbfname, 'id_tmdb':args.idtmdb})}
        )
        datas_resp = response.json()
        if datas_resp['code'] < 0:
            print('  failed with reason "{}"'.format(datas_resp['reason']))
            return
        exists = datas_resp['code'] == 0


        #if not (not exists or args.force_parsing):
        if exists and not args.force_parsing:
            if not args.silent_exists:
                print('Parse "{0}" :'.format(fname))
                print('  already exists in DB => skipped')
            return
        print('Parse "{0}" :'.format(fname))
        if exists:
            print('  Already exists in DB => updating')
        else:
            print('  Not found in DB => adding')
        if args.verbosity > 0:
            print(json.dumps(datas_resp, indent=4))


        # parse ffmpeg
        ffprobe_result = ffprobe(file_path=fname)
        if ffprobe_result.return_code != 0:
            print('  ERROR ffprobe')
            print(ffprobe_result.error, file=sys.stderr)

        # request append/update
        data = {
            'options': json.dumps(options),
            'file' : dbfname,
            'id_tmdb': args.idtmdb,
            'title':'',
            'year':'',
            'ffprobe':ffprobe_result.json
        }
        response = session.post(
            url=url_append,
            headers=header,
            cookies=cookies,
            data={'json': json.dumps(data)}
        )
        datas_resp = response.json()
        if args.verbosity > 0:
            print(json.dumps(datas_resp, indent=4))
        if datas_resp['num_movies'] in [0, 1]:
            print('  {}'.format(datas_resp['result']))
            return
        # dialog choose movie number
        if datas_resp['num_movies'] > 1:
            print('  Choose a movie among the {} suggestions (or ENTER to skip)'.format(datas_resp['num_movies']))
            for num, (id_movie, title, original_title, release_date, overview, _, _) in enumerate(datas_resp['movies']):
                original_title = ' ({})'.format(original_title) if original_title else ''
                print('    {:2}- {}{} [year: {}]'.format(num+1, title, original_title, release_date.split('-')[0]))
                if overview:
                    lines = textwrap.wrap(overview, 120, break_long_words=False)
                    for line in lines:
                        print('       ', line)
            # loop for choose or skip
            while True:
                try:
                    print('Choose a movie number ({} to {}, or ENTER to skip) :'.format(1, datas_resp['num_movies']))
                    sel = input()
                    if not sel:
                        return
                    sel = int(sel) - 1
                    if sel >= 0 and sel < datas_resp['num_movies']:
                        id_movie = datas_resp['movies'][sel][0]
                        # request append/update
                        data = {
                            'options': json.dumps(options),
                            'file' : dbfname,
                            'id_tmdb': id_movie,
                            'title':'',
                            'year':'',
                            'ffprobe':ffprobe_result.json
                        }
                        response = session.post(
                            url=url_append,
                            headers=header,
                            cookies=cookies,
                            data={'json': json.dumps(data)}
                        )
                        datas_resp = response.json()
                        if datas_resp['num_movies'] != 1:
                            print('  {}'.format(datas_resp['result']))
                        break
                except ValueError:
                    pass




    def update_missing_files(dirpath, files):
        ''' update database for missing files in directory '''
        volname, _ = os.path.splitdrive(dirpath)
        if volname.startswith('\\\\'):
            volname = volname.split('\\')[2]
            moviedir = dirpath.replace('\\\\' + volname, volname + ':')
        else:
            # replace drive letter with volume name
            volname, _ = volumes[dirpath.lower()[0]]
            moviedir = volname + dirpath[1:]

        # get movie files in this directory from database
        response = session.post(
            url=url_dir,
            headers=header,
            cookies=cookies,
            data={'json': json.dumps({'dir':moviedir, 'recurs':False})}
        )
        datas_resp = response.json()
        print('Search for missing files in directory "{}" : {} files in database'.format(dirpath, datas_resp['num_movies']))
        for movie_file in datas_resp['movies']:
            print(movie_file)
            _, movie_file = os.path.split(movie_file)
            if not movie_file in files:
                print('Status file to update')
                movie_file = os.path.join(moviedir, movie_file)
                response = session.post(
                    url=url_status,
                    headers=header,
                    cookies=cookies,
                    data={'json': json.dumps({'file':movie_file, 'status':'missing'})}
                )
                datas_resp = response.json()
                print('Status updated : ', datas_resp['reason'])




    def parse_directory(thepath):
        ''' Parse directory '''
        print('Parse directory "%s"%s' % (thepath, ' and subdirectories' if not args.no_recurs else ''))
        for root, _, files in os.walk(thepath):
            for filename in files:
                fname = os.path.join(root, filename)
                _, ext = os.path.splitext(fname)
                if ext.lower() in ['.srt', '.jpg', '.vsmeta', '.db', '.idx', '.nfo', '.srt']:
                    if args.verbosity > 1:
                        print('Skip extension', ext)
                    continue
                parse_file(fname)

            # update status for missing files
            update_missing_files(root, files)

            # continue in sub-directories ?
            if args.no_recurs:
                # right when topdown option is True (default)
                break


    if args.idtmdb and (len(args.filelist) > 1 or os.path.isdir(args.filelist[0])):
        sys.exit('The "idtmdb" option must be used for a unique movie file')

    # and go jobs
    for glob_name in args.filelist:
        glob_name = glob_name.rstrip("\r\n")
        # print(glob_name)
        for fname in glob.glob(glob_name):
            if os.path.isfile(fname):
                parse_file(fname)
            elif os.path.isdir(fname):
                parse_directory(fname)
            else:
                continue






if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.ConnectionError as _e:
        print(_e)
    # protect main from IOError occuring with a pipe command
    except IOError as _e:
        if _e.errno not in [22, 32]:
            raise _e
    except SystemExit as _e:
        print(_e)
    log.info('ManageMovieDB end')
