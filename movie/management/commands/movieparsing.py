# -*- coding: utf-8 -*-
# pylint: disable=no-member, attribute-defined-outside-init, imported-auth-user
"""
Administration : parse movies an add/update in database

"""


import os
import sys
import json
import glob
import locale
import platform
import textwrap
from datetime import datetime
import requests

import unidecode

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.timezone import make_aware


from movie.models import MovieFile, Movie, Team, Poster, Person, Job
from movie.moviedesc import MovieDescription
from moviedb.tmdb import TMDB_Api
from moviedb.ffprobe import ffprobe, smart_probe
from moviedb.common import get_volumes, build_dbfilename


class Command(BaseCommand):
    """
    class Command
    """

    args = "Parse file or directories for update movies"
    help = "Parse file or directories for adding / updating database movies. Metadatas are takem from TMDB"

    def add_arguments(self, parser):
        parser.add_argument(
            "filelist", nargs="+", help="files or directories list to parse"
        )
        parser.add_argument(
            "--show-only",
            action="store_true",
            help="only show movies parsed or to be parsed, don't update database",
        )
        parser.add_argument(
            "--force-parsing",
            action="store_true",
            help="force parsing, even if file already in database",
        )
        parser.add_argument(
            "--skip-choosing",
            action="store_true",
            help="skip movie choosing in list (no input)",
        )
        parser.add_argument(
            "--exact-name",
            action="store_true",
            help="restrict search to exact movie name",
        )
        parser.add_argument(
            "--no-recurs",
            action="store_true",
            help="don't parse sub-directories (no recursivity)",
        )
        parser.add_argument(
            "--simu",
            action="store_true",
            help="don't make any modifications on database",
        )
        parser.add_argument(
            "--set-id",
            type=int,
            help="Set TMDB id on movie file (specify only one file)",
        )
        parser.add_argument(
            "--silent-exists",
            action="store_true",
            help="Do not display existant movies",
        )

    def maintenance(self):
        """some maintenance on database"""
        return

    def get_moviefile(self, fname):
        """check if file already in database"""
        try:
            if fname.isdigit():
                return MovieFile.objects.get(pk=fname)
            else:
                return MovieFile.objects.get(file__iexact=fname)
        except ObjectDoesNotExist:
            return None

    def add_or_update_moviedesc(self, moviedesc):
        """
        Add or update Movie entry
        """
        try:
            movie = Movie.objects.get(id_tmdb=moviedesc.id_tmdb)
            if not self.options["force_parsing"]:
                return movie
        except ObjectDoesNotExist:
            movie = Movie(id_tmdb=moviedesc.id_tmdb)
        movie.title = moviedesc.title
        movie.title_ai = unidecode.unidecode(moviedesc.title.lower())
        movie.original_title = moviedesc.original_title
        movie.release_year = moviedesc.release_date
        movie.overview = moviedesc.overview
        movie.genres = moviedesc.genres
        movie.countries = moviedesc.countries
        movie.language = moviedesc.original_language
        if not movie.date_added:
            movie.date_added = make_aware(datetime.now())
        if not self.options["simu"]:
            movie.save()
        return movie

    def add_or_update_moviefile(
        self,
        fname,
        status,
        file_size,
        movie_format,
        bitrate,
        screen_size,
        duration,
        movie_desc,
    ):
        """
        Add or update Movie entry
        """
        movie = self.get_moviefile(fname)
        if not movie:
            movie = MovieFile(file=fname)
        movie.file_status = status
        movie.file_size = file_size
        movie.movie_format = movie_format
        movie.bitrate = bitrate
        movie.screen_size = screen_size
        movie.duration = duration
        movie.movie = movie_desc

        if not movie.date_added:
            movie.date_added = make_aware(datetime.now())
        if not self.options["simu"]:
            movie.save()
        return movie

    def add_or_update_team(self, movie):
        """
        Add or update team in database
        """
        if self.options["force_parsing"]:
            for team in Team.objects.filter(movie_id=movie.id):
                if not self.options["simu"]:
                    team.delete()
        creds = self.tmdb.movie.credits(movie.id_tmdb)
        job, created = Job.objects.get_or_create(name="Actor")
        if created:
            job.save()

        for cast in creds.cast:
            person, created = Person.objects.get_or_create(
                name=cast.name, id_tmdb=cast.id
            )
            if created:
                person.url_img = cast.profile_path
                if not person.url_img:
                    images = self.tmdb.person.images(person.id_tmdb)
                    if images.profiles:
                        person.url_img = images.profiles[-1].file_path
                person.save()

            if self.options["simu"]:
                continue
            team, created = Team.objects.get_or_create(
                movie=movie, person=person, job=job
            )
            team.extension = cast.character
            team.cast_order = cast.order
            team.save()

        for crew in creds.crew:
            if crew.job in ["Writer", "Original Film Writer"]:
                jobname = "Writer"
            elif crew.job in ["Music", "Compositor", "Original Music Composer"]:
                jobname = "Music"
            elif crew.job in [
                "Director",
                "Director of Photography",
                "Novel",
                "Musician",
            ]:
                jobname = crew.job
            else:
                continue

            job, created = Job.objects.get_or_create(name=jobname)
            if created:
                job.save()

            if self.options["simu"]:
                continue
            person, created = Person.objects.get_or_create(
                name=crew.name, id_tmdb=crew.id
            )
            if created:
                person.url_img = crew.profile_path
                if not person.url_img:
                    images = self.tmdb.person.images(person.id_tmdb)
                    if images.profiles:
                        person.url_img = images.profiles[-1].file_path
                person.save()

            team, created = Team.objects.get_or_create(
                movie=movie, person=person, job=job
            )
            team.cast_order = None
            team.save()

    def add_or_update_poster(self, movie, original_language):
        """
        Add or update movie poster
        """
        posters = Poster.objects.filter(movie_id=movie.id)
        if len(posters) > 0:
            if self.options["force_parsing"]:
                for poster in posters:
                    if not self.options["simu"]:
                        poster.delete()
                        if os.path.exists(poster.poster.path):
                            os.remove(poster.poster.path)
            else:
                print("  Posters already in datadase")
                return
        images = self.tmdb.movie.images(movie.id_tmdb)
        if not images["posters"]:
            # no result : try original language + english + no language
            images = self.tmdb.movie.images(
                movie.id_tmdb, include_image_language=original_language + ",en,null"
            )
            if not images["posters"]:
                print("  None TMDB posters")
                return
        if len(images["posters"]) > settings.MAX_POSTERS:
            print(
                f"  Ignore {len(images['posters']) - settings.MAX_POSTERS} on {len(images['posters'])}"
            )
        for num, poster in enumerate(images["posters"][: settings.MAX_POSTERS]):
            try:
                rel_path = poster["file_path"]
                url = f'{self.tmdb.config["images"]["base_url"]}{"w500"}{rel_path}'
                req = requests.get(url, timeout=60)
                # Warning : jpg format forced, must be :
                #   filetype = rq.headers['content-type'].split('/')[-1]
                filename = f"{movie.release_year}/{movie.title}_{num + 1}.jpg"
                poster = Poster(movie=movie, url_tmdb=url)
                if not self.options["simu"]:
                    poster.poster.save(filename, ContentFile(req.content))
                    poster.save()
            except IntegrityError as _e:
                print(_e)
                continue

    def parse_file(self, fname):
        """Parse movie file"""
        _, ext = os.path.splitext(fname)
        if ext.lower() in [
            ".srt",
            ".jpg",
            ".vsmeta",
            ".db",
            ".idx",
            ".nfo",
        ]:
            if self.options["verbosity"] > 1:
                print("Skip extension", ext)
            return

        dbfname = build_dbfilename(fname, self.volumes)

        if not self.options["force_parsing"]:
            # check if movie already in database
            movie = self.get_moviefile(dbfname)
            if movie:
                if not self.options["silent_exists"]:
                    print(f'Parse file "{fname}" :  ALREADY in database')
                    # print(f"  ->  {movie.movie.title} (format : {movie.movie_format})")
                # set status 'OK' if necessary
                if movie.file_status != "OK":
                    movie.file_status = "OK"
                    movie.save()
                return

        print(
            f'Parse file "{fname}"',
            " :  TO BE PARSED" if self.options["show_only"] else "",
        )

        # parse ffmpeg
        ffprobe_result = ffprobe(file_path=fname)
        if ffprobe_result.return_code != 0:
            print("ERROR")
            print(ffprobe_result.error, file=sys.stderr)
            return
        # add smart infos to original ffmpeg probe
        container = smart_probe(json.loads(ffprobe_result.json))
        fmt = container["format"]
        # Print the raw json string
        if self.options["verbosity"] > 1:
            print(ffprobe_result.json)

        #
        # search in TMDB base filename
        #
        if self.options["set_id"]:
            # set TMDB id on unique file
            if not (self.ndirectories == 0 and self.nfiles == 1):
                sys.exit('FAILED: Specify only ONE movie when using option "--set-id"')
            movies = [MovieDescription.from_id(self.tmdb.movie, self.options["set_id"])]
        else:
            # standard search
            _, moviename = os.path.split(fname)
            moviename, _ = os.path.splitext(moviename)
            # get optionnal year after title (ex: "Hollow man.2000")
            year = None
            words = moviename.split(".")
            if len(words) > 1:
                for _id in range(len(words) - 1, 0, -1):
                    year = words[_id]
                    if year.isnumeric() and int(year) > 1900 and int(year) < 2100:
                        moviename = " ".join(words[:_id])
                        break
            # replace various characters
            moviename = moviename.replace(".", " ").replace("_", " ")
            # and research in TBDB
            movies = MovieDescription.from_search(
                self.tmdb.search, moviename, year=year
            )
        if len(movies) == 0:
            print(f'  NO SUGGESTIONS for "{fname}"')
            return
        if len(movies) > 1:
            # check if exact exist in list
            exact_movies = []
            for num, moviedesc in enumerate(movies):
                if moviename.lower() == moviedesc.title.lower():
                    exact_movies.append(movies[num])
                else:
                    if (
                        f" (titre original: {moviename.lower()})"
                        == moviedesc.original_title.lower()
                    ):
                        exact_movies.append(movies[num])
            if len(exact_movies) == 1:
                print("  FOUND unique exact movie name in list")
                movies = exact_movies
            else:
                if self.options["exact_name"]:
                    movies = exact_movies
                if len(movies) == 0:
                    print(f'  NO SUGGESTIONS (with --exact-name) for "{fname}"')
                    return
        if len(movies) > 1 and not self.options["show_only"]:
            for num, moviedesc in enumerate(movies):
                original_title = (
                    f" ({moviedesc.original_title})"
                    if moviedesc.original_title != moviedesc.title
                    else ""
                )
                print(
                    f"    {(num + 1):2}- {moviedesc.title}{original_title} [year: {moviedesc.release_date}]"
                )
                if moviedesc.overview:
                    lines = textwrap.wrap(
                        moviedesc.overview, 120, break_long_words=False
                    )
                    for line in lines:
                        print("       ", line)

        if len(movies) > 1 and not self.options["show_only"]:
            if self.options["skip_choosing"]:
                return
            while True:
                try:
                    print(
                        f"Choose a movie number (1 to {len(movies)}, or ENTER to skip) :"
                    )
                    sel = input()
                    if not sel:
                        return
                    sel = int(sel) - 1
                    if sel >= 0 and sel < len(movies):
                        movies = [movies[sel]]
                        break
                except ValueError:
                    pass

        if self.options["show_only"]:
            if len(movies) > 1:
                movies[0].title = f"Title to select in {len(movies)} movies"
            print(
                f'  ->  {movies[0].title} (format : {fmt["format_name"]} | {container["smart_streams"]})'
            )
            return

        #
        # save movie in db
        #
        print("  ", "Simulates" if self.options["simu"] else "", "Store in database")
        # MovieDescription.from_search doesn't return genres/, so update
        moviedesc = movies[0]
        moviedesc.get_full_description(self.tmdb.movie)
        # create Movie description from TMDB data
        movie_db = self.add_or_update_moviedesc(moviedesc)
        self.add_or_update_team(movie_db)
        self.add_or_update_poster(movie_db, moviedesc.original_language)

        # fix some incorrect screen_size
        screen_size = fmt["screen_size"]
        width, height = screen_size.split("x")
        width = int(width)
        height = int(height)
        if width < height:
            width, height = height, width
            screen_size = f"{width}x{height}"

        if self.options["simu"]:
            return
        moviefile = self.add_or_update_moviefile(
            dbfname,
            "OK",
            fmt["size"],
            f'container: {fmt["format_name"]} | {container["smart_streams"]}',
            fmt["bit_rate"],
            screen_size,
            int(float(fmt["duration"])),
            movie_db,
        )
        # add moviefile to Movie
        moviefile.movie.files.add(moviefile)

    def parse_directory(self, thepath):
        """Parse directory"""
        print(
            f'Parse directory "{thepath}"{" and subdirectories" if not self.options["no_recurs"] else ""}'
        )
        for root, _, files in os.walk(thepath):
            for filename in files:
                fname = os.path.join(root, filename)
                self.parse_file(fname)
            # continue in sub-directories ?
            if self.options["no_recurs"]:
                # right when topdown option is True (default)
                break

    def open_tmdb(self):
        """open TMBD instances"""
        if not hasattr(self, "tmdb"):
            self.tmdb = TMDB_Api(settings.TMDB_API_KEY, settings.TMDB_API_LANG)

    def handle(self, *args, **options):
        """
        Handle command

        Warning : must return None or string, else Exception
        """
        locale.setlocale(locale.LC_ALL, "")

        if len(options["filelist"]) == 0:
            print("FAILED : Need list of files or directories")
            return "FAILED"

        self.options = options

        # get mapping letter volumes to volume name
        if platform.system() == "Windows":
            self.volumes = get_volumes()

        # prepare TMDb API
        self.open_tmdb()

        # some maintenance code if necessary
        self.maintenance()

        # run only on Windows
        if platform.system() != "Windows":
            sys.exit(
                "Adding movies can be only done on Windows system.\nUse manage_moviesite.py for remote management from Windows."
            )

        # count files in glob
        self.ndirectories = self.nfiles = 0
        for glob_name in options["filelist"]:
            glob_name = glob_name.rstrip("\r\n")
            for fname in glob.glob(glob_name):
                if os.path.isfile(fname):
                    self.nfiles += 1
                elif os.path.isdir(fname):
                    self.ndirectories += 1

        # and go jobs
        for glob_name in options["filelist"]:
            glob_name = glob_name.rstrip("\r\n")
            for fname in glob.glob(glob_name):
                if os.path.isfile(fname):
                    self.parse_file(fname)
                elif os.path.isdir(fname):
                    self.parse_directory(fname)
                else:
                    continue
        return None
