# -*- coding: utf-8 -*-
"""
    MovieDB API

"""

import sys
import os
import errno
import json
import ntpath
from io import StringIO

from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.conf import settings

from movie.management.commands.movieparsing import Command, smart_probe
from movie.models import MovieFile
from movie.moviedesc import MovieDescription
from movie.dlna import DLNA, dlna_discover as discover
from movie.views import is_dlnable


def makedir(directory):
    """
    Create complete path directories
    """
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except OSError as excpt:
            if excpt.errno == errno.EEXIST:
                return True
            else:
                return False
    return True


@staff_member_required
def append_movie(request):
    """
    AJAX append movie to DB
        - movie format (tracks, rate...) must be parsed by source
    Input JSON :
        options : <STRING ARRAY>
        id_tmdb :
        [id_db]
        file
        year
        ffprobe
    Return JSON :
        code: <NUM>,
        num_movies: <NUM>,
        result: <STRING>,
        id_added: <NUM>[OPTIONAL],
    """

    datas_json = json.loads(request.POST["json"])
    options = json.loads(datas_json["options"])
    id_tmdb = datas_json["id_tmdb"]
    id_db = datas_json["id_db"] if "id_db" in datas_json else None
    movie_file = datas_json["file"].replace("/", "\\")
    _, basename = ntpath.split(movie_file)
    year = datas_json["year"]
    movie_format = json.loads(datas_json["ffprobe"])
    # add smart infos to original ffmpeg probe
    if not id_db:
        container = smart_probe(movie_format)

    manage = Command()
    # set options in Command
    manage.options = {}
    for option in options:
        manage.options[option] = options[option]
    manage.open_tmdb()

    if id_db:
        src_movie = manage.get_moviefile(id_db)
        # on copy or move file already in DB
        manage.add_or_update_moviefile(
            movie_file,
            "OK",
            src_movie.file_size,
            src_movie.movie_format,
            src_movie.bitrate,
            src_movie.screen_size,
            src_movie.duration,
            src_movie.movie,
        )
        return JsonResponse(
            {
                "code": 0,
                "num_movies": 1,
                "result": f'Append copy "{src_movie.movie.title}" - {src_movie.movie.release_year} (id {id_db})',
                "id_added": id_db,
            }
        )

    if id_tmdb:
        movie = MovieDescription.from_id(manage.tmdb.movie, id_tmdb)
        if not movie:
            return JsonResponse(
                {"code": -1, "num_movies": 0, "reason": "TMDB id not found"}
            )
        # create/update Movie description, Team and Posters
        movie_desc = manage.add_or_update_moviedesc(movie)
        manage.add_or_update_team(movie_desc)
        manage.add_or_update_poster(movie_desc, movie.original_language)
        # create/update MovieFile
        fmt = container["format"]
        moviefile = manage.add_or_update_moviefile(
            movie_file,
            "OK",
            fmt["size"],
            f'container: {fmt["format_name"]} | {container["smart_streams"]}',
            fmt["bit_rate"],
            fmt["screen_size"],
            int(float(fmt["duration"])),
            movie_desc,
        )
        return JsonResponse(
            {
                "code": 0,
                "num_movies": 1,
                "result": f'Append/update "{movie_desc.title}" - {movie_desc.release_year} (id {moviefile.id})',
                "id_added": moviefile.id,
            }
        )

    # determine movie title, year
    moviename, _ = os.path.splitext(basename)
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
    movies = MovieDescription.from_search(manage.tmdb.search, moviename, year=year)

    if len(movies) == 0:
        return JsonResponse({"code": 0, "num_movies": 0, "result": "None suggestions"})

    if len(movies) > 1 and options["exact_name"]:
        # check if exact title exists in list
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
            movies = exact_movies

    if len(movies) > 1:
        result = f"{len(movies)} suggestions"
        datas = [
            [
                movie.id_tmdb,
                movie.title,
                movie.original_title,
                movie.release_date,
                movie.overview,
                None,
                movie.original_language,
            ]
            for movie in movies
        ]
        return JsonResponse(
            {"code": 0, "num_movies": len(movies), "result": result, "movies": datas}
        )

    # here, we have an unique movie
    moviedesc = movies[0]
    # MovieDescription.from_search doesn't return genres/, so update
    moviedesc.get_full_description(manage.tmdb.movie)
    # create/update Movie description, Team and Posters
    movie_db = manage.add_or_update_moviedesc(moviedesc)
    manage.add_or_update_team(movie_db)
    manage.add_or_update_poster(movie_db, moviedesc.original_language)
    # create/update MovieFile
    fmt = container["format"]
    moviefile = manage.add_or_update_moviefile(
        movie_file,
        "OK",
        fmt["size"],
        f'container: {fmt["format_name"]} | {container["smart_streams"]}',
        fmt["bit_rate"],
        fmt["screen_size"],
        int(float(fmt["duration"])),
        movie_db,
    )
    return JsonResponse(
        {
            "code": 0,
            "num_movies": 1,
            "result": f'Append/update "{movie_db.title}" - {movie_db.release_year} (id {moviefile.id})',
            "id_added": moviefile.id,
        }
    )


@staff_member_required
def movie_info(request):
    """get movie info by id or filename"""
    data_req = json.loads(request.POST["json"])
    # check if file exists in database
    try:
        movie_file = data_req["file"]
        if isinstance(movie_file, int) or movie_file.isdigit():
            movie = MovieFile.objects.get(id=int(movie_file))
        else:
            movie = MovieFile.objects.get(file__iexact=movie_file)
    except ObjectDoesNotExist:
        return JsonResponse({"code": 1, "reason": "not found"})

    data_resp = {
        "code": 0,
        "reason": "ok",
        "id": movie.id,
        "id_tmdb": movie.movie.id_tmdb,
        "file": movie.file,
        "title": movie.movie.title,
        "original_title": movie.movie.original_title,
        "release_year": movie.movie.release_year,
        "duration": movie.duration,
        "screen_size": movie.screen_size,
        "movie_format": movie.movie_format,
    }

    return JsonResponse(data_resp)


@staff_member_required
def movies_dir(request):
    """return movies in directory"""
    try:
        data_req = json.loads(request.POST["json"])
    except KeyError:
        return JsonResponse({"code": -2, "reason": "Key error"})
    directory = data_req["dir"]
    recurs = data_req["recurs"]
    movies = MovieFile.objects.filter(file__istartswith=directory)
    if recurs:
        results = [movie.file for movie in movies]
    else:
        results = []
        # remove sub-directories
        for movie in movies:
            moviefile = movie.file[len(directory) + 1 :]
            pathleft, _ = ntpath.split(moviefile)
            if pathleft:
                continue
            results.append(movie.file)
    return JsonResponse({"code": 0, "num_movies": len(movies), "movies": results})


@staff_member_required
def update_movie(request):
    """update some fields in movie"""
    try:
        data_req = json.loads(request.POST["json"])
    except KeyError:
        return JsonResponse({"code": -2, "reason": "Key error"})
    try:
        movie = MovieFile.objects.get(id=data_req["id"])
    except ObjectDoesNotExist:
        return JsonResponse({"code": 1, "reason": "not found"})

    if "file" in data_req:
        movie.file = data_req["file"]
    if "file_status" in data_req:
        movie.file_status = data_req["file_status"]
    if "viewed" in data_req:
        movie.viewed = data_req["viewed"]
    if "rate" in data_req:
        movie.rate = data_req["rate"]
    try:
        if not data_req.get("simu", False):
            movie.save()
    except Exception as _e:
        return JsonResponse({"code": 1, "reason": _e})
    return JsonResponse({"code": 0})


@staff_member_required
def remove_movie(request):
    """remove MovieFile object"""
    try:
        data_req = json.loads(request.POST["json"])
    except KeyError:
        return JsonResponse({"code": -2, "reason": "key error"})
    try:
        movie = MovieFile.objects.get(id=data_req["id"])
    except ObjectDoesNotExist:
        return JsonResponse({"code": 1, "reason": "not found"})

    try:
        if not data_req.get("simu", False):
            movie.delete()
    except Exception as _e:
        return JsonResponse({"code": 1, "reason": _e})
    return JsonResponse({"code": 0})


def movies_ids(request):
    """return list of column : MovieFile.file, MovieFile.id"""
    try:
        data_req = json.loads(request.POST["json"])
        offset = data_req["offset"]
        count = data_req["count"]
        column = data_req["column"]
    except KeyError:
        return JsonResponse({"code": -2, "reason": "json key error"})
    if column == "file":
        datas = [f for f in MovieFile.objects.all().values_list("file", flat=True)]
    elif column == "idfile":
        datas = [f for f in MovieFile.objects.all().values_list("id", flat=True)]
    else:
        return JsonResponse({"code": -2, "reason": "invalid column"})
    if count == -1:
        end = None
    else:
        end = offset + count
    return JsonResponse(
        {
            "code": 0,
            "num_datas": len(datas[offset:end]),
            "datas": datas[offset:end],
        }
    )


def movie_play(request):
    """
    Play movie content (id database)
        in:
            id : id_movie
        out:
            protocol : 'dlna', 'browser', 'vlc', or '' on error
            result : html if browser, vlc uri if vlc, or error description
    """
    if not is_dlnable(request):
        return JsonResponse({"protocol": "", "result": "permission denied"})
    try:
        movie_id = request.POST["id"]
    except KeyError:
        return JsonResponse({"protocol": "", "result": "no json"})

    try:
        movie = MovieFile.objects.get(id=movie_id)
    except ObjectDoesNotExist:
        return JsonResponse({"protocol": "", "result": "not found"})
    volume, basename = ntpath.split(movie.file)
    volume = volume.split(":")[0]
    basename, _ = ntpath.splitext(basename)

    # Get configured renderer
    renderer_uri = request.session.get(
        "default_renderer", settings.DLNA_RENDERERS[0][0]
    )

    # Get configured media server for volume
    if not volume.lower() in settings.DLNA_MEDIASERVERS:
        return JsonResponse({"protocol": "", "result": "volume not configured"})
    dlna_uri, dlna_path = settings.DLNA_MEDIASERVERS[volume.lower()]
    if not dlna_uri:
        if renderer_uri == "vlc":
            # the vlc-protocol.bat (see https://github.com/stefansundin/vlc-protocol/)
            #  must be replaced by the local version
            return JsonResponse({"protocol": "vlc", "result": "vlc://" + movie.file})
        else:
            return JsonResponse(
                {"protocol": "", "result": "no media server configured for volume"}
            )
    mediaserver = DLNA(device_uri=dlna_uri)
    if not mediaserver.device:
        return JsonResponse({"protocol": "", "result": "no media server"})

    # ROOT_ID path of media server
    root_id = mediaserver.root_content_id()

    # get configured movie path in media server
    path = mediaserver.search_directory(root_id, dlna_path)

    # search for base name without path and extension
    content = mediaserver.search_title(path, basename)
    if not content:
        return JsonResponse({"protocol": "", "result": "no content found"})
    if renderer_uri == "vlc":
        # vlc-protocol.bat must be installed (https://github.com/stefansundin/vlc-protocol/)
        return JsonResponse({"protocol": "vlc", "result": "vlc://" + content["uri"]})

    if renderer_uri == "browser":
        # play in brower
        context = {
            "movie_uri": content["uri"],
            "movie_type": "video/mp4",  # TODO guess type
        }
        html = render_to_string("movie/inc_video.html", context)
        return JsonResponse({"protocol": "browser", "result": html})

    # regular DLNA device
    renderer = DLNA(device_uri=renderer_uri)
    if not renderer.device:
        return JsonResponse({"protocol": "", "result": "no renderer"})
    # DLNA play
    done, reason = renderer.play_content(movie, content["uri"])
    if not done:
        return JsonResponse({"protocol": "", "result": f"failed to play [{reason}]"})
    return JsonResponse({"protocol": "dlna", "result": "done"})


def dlna_discover(request):
    """display DNLA discover"""
    if not is_dlnable(request):
        return JsonResponse({"result": "permission denied"})
    try:
        verbosity = int(request.POST.get("verbosity", "2"))
    except ValueError:
        verbosity = 2
    mode = request.POST.get("devices", "all")
    timeout = int(request.POST.get("timeout", 2))

    # redirect dnla_discover output in string
    old_stdout = sys.stdout
    sys.stdout = strout = StringIO()
    discover(mode, timeout, verbosity)
    sys.stdout = old_stdout

    return JsonResponse({"result": strout.getvalue()})


def dlna_browse(request):
    """display browse directory in mediaserver"""
    if not is_dlnable(request):
        return JsonResponse({"result": "permission denied"})
    device = request.POST.get("mediaserver")
    dlna_uri, _ = settings.DLNA_MEDIASERVERS[device.lower()]
    mediaserver = DLNA(device_uri=dlna_uri)
    if not mediaserver.device:
        return JsonResponse({"code": 1, "reason": "no media server"})

    directory = request.POST.get("directory", "")
    if directory:
        if not mediaserver.search_directory(0, directory):
            return JsonResponse({"code": 1, "reason": "no path"})

    subdirs = request.POST.get("subdirs") == "on"
    contents = mediaserver.get_contents(directory, subdirs)
    contents = sorted(contents, key=lambda x: x[0])
    html = render_to_string("movie/table_dlnabrowse.html", {"contents": contents})
    return JsonResponse({"result": html})


def dlna_check_medias(request):
    """check dlna medias accessibility"""
    if not is_dlnable(request):
        return JsonResponse({"result": "permission denied"})
    device = request.POST.get("mediaserver")
    dlna_uri, dlna_path = settings.DLNA_MEDIASERVERS[device.lower()]
    mediaserver = DLNA(device_uri=dlna_uri)
    if not mediaserver.device:
        return JsonResponse({"code": 1, "reason": "no media server"})
    # get all media server contents
    dlna_contents = mediaserver.get_contents(dlna_path, True)
    dlna_titles = {}
    for _, _, components in dlna_contents:
        for name, uri in components:
            dlna_titles[name] = uri

    contents = []
    movies = MovieFile.objects.filter(file__istartswith=device).order_by("movie__title")
    for movie in movies:
        _, basename = ntpath.split(movie.file)
        basename, _ = ntpath.splitext(basename)

        # search for base name without path and extension
        if basename in dlna_titles:
            uri = dlna_titles[basename]
        else:
            uri = "NOT FOUND"
        contents.append((movie.id, movie.movie.title, movie.file, uri))

    html = render_to_string("movie/inc_table_check_medias.html", {"contents": contents})
    return JsonResponse({"result": html})
