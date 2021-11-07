# -*- coding: utf-8 -*-
'''
    MovieDB API

'''

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
from movie.models import Movie
from movie.dlna import DLNA, dlna_discover as discover


def makedir(directory):
    '''
    Create complete path directories
    '''
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except OSError as excpt:
            if excpt.errno == errno.EEXIST:
                return True
            else:
                print(excpt)
                return False
    return True




@staff_member_required
def append_movie(request):
    '''
    AJAX append movie to DB
        - movie format (tracks, rate...) must be parsed by source
    '''

    datas_json = json.loads(request.POST['json'])
    options = json.loads(datas_json['options'])
    id_tmdb = datas_json['id_tmdb']
    movie_file = datas_json['file']
    _, basename = ntpath.split(movie_file)
    title = datas_json['title']
    year = datas_json['year']
    movie_format = json.loads(datas_json['ffprobe'])
    # add smart infos to original ffmpeg probe
    container = smart_probe(movie_format)

    manage = Command()
    # set options in Command
    manage.options = {}
    for option in options:
        manage.options[option] = options[option]
    manage.open_tmdb()

    if id_tmdb:
        movies = manage.get_tmdb(id_tmdb)
        if not movies:
            return JsonResponse({'code':-1, 'num_movies':0, 'result':'TMDB id not found'})
        id_movie, title, original_title, release_date, overview, genres, original_language = movies[0]
        fmt = container['format']
        movie = manage.add_or_update_movie(movie_file, 'OK', fmt["size"], 'container: %s | %s' % (fmt["format_name"], container['smart_streams']), fmt["bit_rate"], \
                            fmt['screen_size'], int(float(fmt["duration"])), title, original_title, release_date.split('-')[0], overview, genres, id_movie)
        manage.add_or_update_team(movie)
        manage.add_or_update_poster(movie, original_language)
        return JsonResponse({'code':0, 'num_movies':1, 'result':'Append/update done'})

    # determine movie title, year
    moviename, _ = os.path.splitext(basename)
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
    movies = manage.search_tmdb(moviename, year=year)

    if len(movies) == 0:
        return JsonResponse({'code':1, 'num_movies':0, 'result':'None suggestions'})

    if len(movies) > 1 and options['exact_name']:
        # check if exact title exists in list
        exact_movies = []
        for num, (_, title, original_title, _, _, _, _) in enumerate(movies):
            if moviename.lower() == title.lower():
                exact_movies.append(movies[num])
            else:
                if f' (titre original: {moviename.lower()})' == original_title.lower():
                    exact_movies.append(movies[num])
        if len(exact_movies) == 1:
            movies = exact_movies

    if len(movies) > 1:
        result = '{} suggestions'.format(len(movies))
        return JsonResponse({'code':2, 'num_movies':len(movies), 'result':result, 'movies':movies})

    # here, we have an unique movie
    id_movie = movies[0][0]
    id_movie, title, original_title, release_date, overview, genres, original_language = manage.get_tmdb(id_movie)[0]
    fmt = container['format']
    movie = manage.add_or_update_movie(movie_file, 'OK', fmt["size"], 'container: %s | %s' % (fmt["format_name"], container['smart_streams']), fmt["bit_rate"], \
                        fmt['screen_size'], int(float(fmt["duration"])), title, original_title, release_date.split('-')[0], overview, genres, id_movie)
    manage.add_or_update_team(movie)
    manage.add_or_update_poster(movie, original_language)
    return JsonResponse({'code':0, 'num_movies':1, 'result':'Append/update done'})




#@staff_member_required
def movie_info(request):
    ''' get movie info '''
    try:
        data_req = json.loads(request.POST['json'])
    except KeyError:
        return JsonResponse({'code':-2})

    movie_file = data_req['file']
    # check if file exists in database
    try:
        movie = Movie.objects.get(file__iexact='%s' % movie_file)
    except ObjectDoesNotExist:
        return JsonResponse({'code':1, 'reason':'not found'})
    except Exception as _e:
        return JsonResponse({'code':-2, 'reason':str(_e)})

    data_resp = {
        'code' : 0,
        'reason':'ok',
        'title' : movie.title,
        'original_title': movie.original_title,
        'release_year': movie.release_year,
        'duration': movie.duration,
        'format': movie.movie_format,
        'screen_size': movie.screen_size,
        'movie_format': movie.movie_format,
    }

    return JsonResponse(data_resp)



#@staff_member_required
def movies_dir(request):
    ''' return movies in directory '''
    try:
        data_req = json.loads(request.POST['json'])
    except KeyError:
        return JsonResponse({'code':-2})
    directory = data_req['dir']
    recurs = data_req['recurs']
    movies = Movie.objects.filter(file__istartswith=directory)
    if recurs:
        results = [movie.file for movie in movies]
    else:
        results = []
        # remove sub-directories
        for movie in movies:
            moviefile = movie.file[len(directory)+1:]
            pathleft, _ = ntpath.split(moviefile)
            if pathleft:
                continue
            results.append(movie.file)
    return JsonResponse({'code':0, 'num_movies':len(movies), 'movies':results})



#@staff_member_required
def set_movie_status(request):
    ''' set movie file status '''
    try:
        data_req = json.loads(request.POST['json'])
    except KeyError:
        return JsonResponse({'code':-2})
    movie_file = data_req['file']
    status = data_req['status']
    try:
        movie = Movie.objects.get(file__iexact='%s' % movie_file)
        movie.file_status = status
        movie.save()
        return JsonResponse({'code':0, 'reason':'ok'})
    except ObjectDoesNotExist:
        return JsonResponse({'code':1, 'reason':'not found'})



#@staff_member_required
def movie_play(request):
    ''' play movie content (id database)
        '''
    try:
        movie_id = request.POST['id']
    except KeyError:
        return JsonResponse({'code':-2, 'reason':'no json'})

    try:
        movie = Movie.objects.get(id=movie_id)
    except ObjectDoesNotExist:
        return JsonResponse({'code':1, 'reason':'not found'})
    volume, basename = ntpath.split(movie.file)
    volume = volume.split(':')[0]
    basename, _ = ntpath.splitext(basename)

     # Get configured media server for volume
    if not volume in settings.DLNA_MEDIASERVERS:
        return JsonResponse({'code':1, 'reason':'volume not configured'})
    dlna_uri, dlna_path = settings.DLNA_MEDIASERVERS[volume]
    if not dlna_uri:
        return JsonResponse({'code':1, 'reason':'no media server configured for volume'})
    mediaserver = DLNA(device_uri=dlna_uri)
    if not mediaserver.device:
        return JsonResponse({'code':1, 'reason':'no media server'})


    # Get configured renderer
    renderer_uri = request.session.get('default_renderer', settings.DLNA_RENDERERS[0][0])
    renderer = DLNA(device_uri=renderer_uri)
    if not renderer.device:
        return JsonResponse({'code':1, 'reason':'no renderer'})

    # ROOT_ID path of media server
    root_id = mediaserver.root_content_id()

    # get configured movie path in media server
    path = mediaserver.search_directory(root_id, dlna_path)

    # search for base name without path and extension
    content = mediaserver.search_title(path, basename)
    if not content:
        return JsonResponse({'code':1, 'reason':'no content found'})

    # play
    done, reason = renderer.play_content(content['uri'])
    if not done:
        return JsonResponse({'code':1, 'reason':'failed to play [{}]'.format(reason)})
    return JsonResponse({'code':0, 'reason':'done'})


def dlna_discover(request):
    ''' display DNLA discover '''
    verbosity = int(request.POST.get('verbosity', '1'))
    mode = request.POST.get('devices', 'all')
    timeout = int(request.POST.get('timeout', 2))

    # redirect dnla_discover output in string
    old_stdout = sys.stdout
    sys.stdout = strout = StringIO()
    discover(mode, timeout, verbosity)
    sys.stdout = old_stdout
    print(strout.getvalue())

    return JsonResponse({'result':strout.getvalue()})


def dlna_browse(request):
    ''' display browse directory in mediaserver'''
    device = request.POST.get('mediaserver')
    dlna_uri, _ = settings.DLNA_MEDIASERVERS[device]
    mediaserver = DLNA(device_uri=dlna_uri)
    if not mediaserver.device:
        return JsonResponse({'code':1, 'result':'no media server'})

    directory = request.POST.get('directory', '')
    if directory:
        if not mediaserver.search_directory(0, directory):
            return JsonResponse({'code':1, 'result':'no path'})

    subdirs = request.POST.get('subdirs') == 'on'
    contents = mediaserver.get_contents(directory, subdirs)
    contents = sorted(contents, key=lambda x: x[0])
    html = render_to_string('movie/table_dlnabrowse.html', {'contents': contents})
    return JsonResponse({'result':html})
