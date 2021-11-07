# -*- coding: utf-8 -*-
# pylint: disable=no-member, attribute-defined-outside-init
'''
Administration : parse movies an add/update in database

'''


import os
import sys
import json
import subprocess
import glob
import locale
from typing import NamedTuple
import platform
import textwrap
import requests

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.core.files.base import ContentFile

from tmdbv3api import TMDb, Movie as TMDbMovie, Search as TMDbSearch, Configuration

from movie.models import Movie, Team, Poster

if platform.system() == 'Windows':
    import win32api


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


def smart_probe(ffmpeg_json):
    ''' add smart infos to original ffmpeg probe '''
    streams = ffmpeg_json.get("streams", [])
    dstreams = {'video':[], 'audio':[], 'subtitle':[]}
    screen_size = ''
    for stream in streams:
        language = f'({stream.get("tags").get("language")})' if (stream.get("tags") and stream.get("tags").get("language")) else ''
        codec_type = stream.get("codec_type", "unknown")
        if codec_type in ['video', 'audio', 'subtitle']:
            dstreams[codec_type].append(f'{stream.get("codec_name")} {language}')
        if codec_type == 'video':
            screen_size = f'{stream.get("width", "?")}x{stream.get("height", "?")}'
    codecs = []
    for codec_type in ['video', 'audio', 'subtitle']:
        if dstreams[codec_type]:
            codecs.append(codec_type)
    streams = ['%s: %s' % (codec_type, ", ".join(dstreams[codec_type])) for codec_type in codecs]
    streams = ' | '.join(streams)
    ffmpeg_json['smart_streams'] = streams
    ffmpeg_json['format']['screen_size'] = screen_size
    return ffmpeg_json



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



def smart_size(size, unit='B'):
    ''' return int size in string smart form : KB, MB, GB, TB '''
    if isinstance(size, str):
        size = int(size)
    if size > 1000*1000*1000*1000:
        return '%.2f T%s' % (size/(1000*1000*1000*1000.), unit)
    if size > 1000*1000*1000:
        return '%.2f G%s' % (size/(1000*1000*1000.), unit)
    if size > 1000*1000:
        return '%.2f M%s' % (size/(1000*1000.), unit)
    if size > 1000:
        return '%.2f K%s' % (size/(1000.), unit)



class Command(BaseCommand):
    '''
    class Command
    '''
    args = 'Parse file or directories for update movies'
    help = 'Parse file or directories for adding / updating database movies. Metadatas are takem from TMDB'

    def add_arguments(self, parser):
        parser.add_argument('filelist', nargs='+', \
            help='files or directories list to parse')
        parser.add_argument('--show-only', action='store_true', \
            help='only show movies parsing, don\'t use database')
        parser.add_argument('--force-parsing', action='store_true', \
            help='force parsing, even if file already in database')
        parser.add_argument('--skip-choosing', action='store_true', \
            help='skip movie choosing in list (no input)')
        parser.add_argument('--exact-name', action='store_true', \
            help='restrict search to exact movie name')
        parser.add_argument('--no-recurs', action='store_true', \
            help='don\'t parse sub-directories (no recursivity)')
        parser.add_argument('--simu', action='store_true', \
            help='don\'t make any modifications on database')
        parser.add_argument('--set-id', type=int, \
            help='Set TMDB id on movie file (specify only one file)')
        parser.add_argument('--silent-exists', action='store_true', \
            help='Do not display existant movies')


    def maintenance(self):
        ''' some maintenance on database '''
        return


    def get_movie_by_filename(self, fname):
        ''' check if file already in database '''
        try:
            return Movie.objects.get(file__iexact='%s' % fname)
        except ObjectDoesNotExist:
            return None


    def add_or_update_movie(self, fname, status, file_size, movie_format, bitrate, screen_size, duration, \
                        title, original_title, release_year, overview, genres, id_tmdb):
        '''
        Add or update Movie entry
        '''
        movie = self.get_movie_by_filename(fname)
        if not movie:
            movie = Movie(file=fname)
        movie.file_status = status
        movie.file_size = file_size
        movie.movie_format = movie_format
        movie.bitrate = bitrate
        movie.screen_size = screen_size
        movie.duration = duration
        movie.title = title
        movie.original_title = original_title
        movie.release_year = release_year
        movie.overview = overview
        movie.genres = genres
        movie.id_tmdb = id_tmdb
        if not self.options['simu']:
            movie.save()
        return movie


    def add_or_update_team(self, movie):
        '''
        Add or update team in database
        '''
        if self.options['force_parsing']:
            for team in Team.objects.filter(movie_id=movie.id):
                team.delete()
        creds = self.tmdb_movie.credits(movie.id_tmdb)
        for cast in creds.cast:
            try:
                team = Team(movie=movie, job='Actor', name=cast.name, extension=cast.character)
                if not self.options['simu']:
                    team.save()
            except IntegrityError:
                continue

        for crew in creds.crew:
            if crew.job in ['Writer', 'Original Film Writer']:
                job = 'Writer'
            elif crew.job in ['Music', 'Compositor', 'Original Music Composer']:
                job = 'Music'
            elif crew.job in ['Director', 'Director of Photography', 'Novel', 'Musician']:
                job = crew.job
            else:
                continue
            try:
                team = Team(movie=movie, job=job, name=crew.name)
                if not self.options['simu']:
                    team.save()
            except IntegrityError:
                continue


    def add_or_update_poster(self, movie, original_language):
        '''
        Add or update movie poster
        '''
        posters = Poster.objects.filter(movie_id=movie.id)
        if len(posters) > 0:
            if self.options['force_parsing']:
                for poster in posters:
                    poster.delete()
                    if os.path.exists(poster.poster.path):
                        os.remove(poster.poster.path)
            else:
                print('  Posters already in datadase')
                return
        images = self.tmdb_movie.images(movie.id_tmdb)
        if not images['posters']:
            # no result : try original language + english + no language
            images = self.tmdb_movie.images(movie.id_tmdb, include_image_language=original_language + ',en,null')
            if not images['posters']:
                print('  None TMDB posters')
                return
        if len(images['posters']) > 4:
            print("  Ignore {0} on {1}".format(len(images['posters']) - 4, len(images['posters'])))
        for num, poster in enumerate(images['posters'][:4]):
            try:
                rel_path = poster['file_path']
                url = "{0}{1}{2}".format(self.config['images']['base_url'], 'w500', rel_path)
                req = requests.get(url)
                # Warning : jpg format forced, must be :
                #   filetype = rq.headers['content-type'].split('/')[-1]
                filename = 'poster_{1}_{0}.jpg'.format(num+1, movie.title)
                poster = Poster(movie=movie, url_tmdb=url)
                if not self.options['simu']:
                    poster.poster.save(filename, ContentFile(req.content))
                    poster.save()
            except IntegrityError as _e:
                print(_e)
                continue



    def search_tmdb(self, moviename, year=None):
        ''' search name in TMDB '''
        results = self.tmdb_search.movies({'query':moviename, 'year':year})
        movies = []
        for res in results:
            original_title = res.original_title if res.title.lower() != res.original_title.lower() else ''
            release_date = res.release_date if hasattr(res, 'release_date') else ''
            movies.append([res.id, res.title, original_title, release_date, res.overview, None, res.original_language])
        return movies


    def get_tmdb(self, idmovie):
        ''' get TMDB movie by id '''
        results = self.tmdb_movie.details(str(idmovie))
        movies = []
        original_title = results.original_title if results.title.lower() != results.original_title.lower() else ''
        release_date = results.release_date if hasattr(results, 'release_date') else ''
        genres = ', '.join([genre.name for genre in results.genres])
        movies.append([results.id, results.title, original_title, release_date, results.overview, genres, results.original_language])
        return movies


    def parse_file(self, fname):
        ''' Parse movie file '''
        if not (self.options['show_only'] or self.options['force_parsing']):
            # check if movie already in database
            movie = self.get_movie_by_filename(fname)
            if movie:
                if not self.options['silent_exists']:
                    print('Parse file', fname, ' :  ALREADY in database')
                # set status 'OK' if necessary
                if movie.file_status != 'OK':
                    movie.file_status = 'OK'
                    movie.save()
                return

        print('Parse file', fname)

        # parse ffmpeg
        ffprobe_result = ffprobe(file_path=fname)
        if ffprobe_result.return_code != 0:
            print("ERROR")
            print(ffprobe_result.error, file=sys.stderr)
            return
        # add smart infos to original ffmpeg probe
        container = smart_probe(json.loads(ffprobe_result.json))
        # Print the raw json string
        if self.options['verbosity'] > 1:
            print(ffprobe_result.json)

        #
        # search in TMDB base filename
        #
        if self.options['set_id']:
            # set TMDB id on unique file
            if not (self.ndirectories == 0 and self.nfiles == 1):
                sys.exit('FAILED: Specify only ONE movie when using option "--set-id"')
            movies = self.get_tmdb(self.options['set_id'])
        else:
            # standard search
            moviepath, moviename = os.path.split(fname)
            moviename, _ = os.path.splitext(moviename)
            # get optionnal year after title (ex: "Hollow man.2000")
            year = None
            words = moviename.split('.')
            if len(words) > 1:
                last_word = words[-1]
                if last_word.isnumeric() and int(last_word) > 1900:
                    year = last_word
                    moviename = ' '.join(words[:-1])
            # replace various characters
            moviename = moviename.replace('.', ' ').replace('_', ' ')
            # and research in TBDB
            movies = self.search_tmdb(moviename, year=year)
        if len(movies) == 0:
            print('  NO SUGGESTIONS for "%s"' % fname)
            return
        if len(movies) > 1:
            # check if exact exist in list
            exact_movies = []
            for num, (id_movie, title, original_title, release_date, overview, genres, _) in enumerate(movies):
                if moviename.lower() == title.lower():
                    exact_movies.append(movies[num])
                else:
                    if f' (titre original: {moviename.lower()})' == original_title.lower():
                        exact_movies.append(movies[num])
            if len(exact_movies) == 1:
                print('  FOUND unique exact movie name in list')
                movies = exact_movies
            else:
                if self.options['exact_name']:
                    movies = exact_movies
        if  len(movies) == 1:
            id_movie, title, original_title, release_date, overview, _, _ = movies[0]
        if len(movies) > 1:
            for num, (id_movie, title, original_title, release_date, overview, _, _) in enumerate(movies):
                original_title = ' ({})'.format(original_title) if original_title else ''
                print('    {:2}- {}{} [year: {}]'.format(num+1, title, original_title, release_date.split('-')[0]))
                if overview:
                    lines = textwrap.wrap(overview, 120, break_long_words=False)
                    for line in lines:
                        print('       ', line)

        if len(movies) > 1:
            if self.options['skip_choosing']:
                return
            while True:
                try:
                    print('Choose a movie number ({} to {}, or ENTER to skip) :'.format(1, len(movies)))
                    sel = input()
                    if not sel:
                        return
                    sel = int(sel) - 1
                    if sel >= 0 and sel < len(movies):
                        break
                except ValueError:
                    pass

        #
        # save movie in db
        #
        print('  Store in database')
        # search.movies doesn't return genres, so get movie by id
        id_movie, title, original_title, release_date, overview, genres, original_language = self.get_tmdb(id_movie)[0]
        fmt = container['format']
        moviepath, _ = os.path.split(fname)
        if not moviepath.startswith('\\\\'):
            # replace drive letter with volume name
            volname, _ = self.volumes[moviepath.lower()[0]]
            moviepath = volname + moviepath[1:]
        movie = self.add_or_update_movie(fname, 'OK', fmt["size"], 'container: %s | %s' % (fmt["format_name"], container['smart_streams']), fmt["bit_rate"], \
                            fmt['screen_size'], int(float(fmt["duration"])), title, original_title, release_date.split('-')[0], overview, genres, id_movie)
        self.add_or_update_team(movie)
        self.add_or_update_poster(movie, original_language)



    def parse_directory(self, thepath):
        ''' Parse directory '''
        print('Parse directory "%s"%s' % (thepath, ' and subdirectories' if not self.options['no_recurs'] else ''))
        for root, _, files in os.walk(thepath):
            for filename in files:
                fname = os.path.join(root, filename)
                _, ext = os.path.splitext(fname)
                if ext.lower() in ['.srt', '.jpg', '.vsmeta', '.db', '.idx', '.nfo', '.srt']:
                    if self.options['verbosity'] > 1:
                        print('Skip extension', ext)
                    continue
                self.parse_file(fname)
            # continue in sub-directories ?
            if self.options['no_recurs']:
                # right when topdown option is True (default)
                break


    def open_tmdb(self):
        ''' open TMBD instance'''
        self.tmdb = TMDb()
        self.tmdb.api_key = '092c5483aa631958806cec9ec4e252e1'
        self.tmdb.language = 'fr'

        self.config = Configuration().info()
        self.tmdb_movie = TMDbMovie()
        self.tmdb_search = TMDbSearch()



    def handle(self, *args, **options):
        '''
        Handle command

        Warning : must return None or string, else Exception
        '''
        locale.setlocale(locale.LC_ALL, '')

        if len(options['filelist']) == 0:
            print('FAILED : Need list of files or directories')
            return 'FAILED'

        self.options = options

        # some maintenance code if necessary
        self.maintenance()

        # run only on Windows
        if platform.system() != 'Windows':
            sys.exit('Adding movies can be only done on Windows system.\nUse manage_moviesite.py for remote management from Windows.')

        # get mapping letter volumes to volume name
        self.volumes = get_volumes()

        # open TMDb
        self.open_tmdb()

        # count files in glob
        self.ndirectories = self.nfiles = 0
        for glob_name in options['filelist']:
            glob_name = glob_name.rstrip("\r\n")
            for fname in glob.glob(glob_name):
                if os.path.isfile(fname):
                    self.nfiles += 1
                elif os.path.isdir(fname):
                    self.ndirectories += 1

        # and go jobs
        for glob_name in options['filelist']:
            glob_name = glob_name.rstrip("\r\n")
            for fname in glob.glob(glob_name):
                if os.path.isfile(fname):
                    self.parse_file(fname)
                elif os.path.isdir(fname):
                    self.parse_directory(fname)
                else:
                    continue
        return None
