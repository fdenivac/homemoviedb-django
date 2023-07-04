# -*- coding: utf-8 -*-
# pylint: disable=imported-auth-user
"""
    The views
"""

from sys import version as python_version
from platform import platform as os_platform
import ipaddress
import ntpath
import os
import platform
from datetime import datetime, timedelta
from collections import Counter
from urllib.parse import urlparse
import unidecode
import pycountry

from django import VERSION as django_version
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Count, Q, OuterRef, Subquery, Sum
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import make_aware
from django_sendfile import sendfile

from .models import Movie, MovieFile, Poster, Team, UserMovie

ALL_JOBS = "<All Jobs>"


def get_volume_alias(label):
    """return volume alias from volume label"""
    for vol_label, vol_alias, _, _ in settings.VOLUMES:
        if label.lower() == vol_label.lower():
            return vol_alias
    return None


def get_client_ip(request):
    """get client adress from request"""
    # found on web :
    # x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    # if x_forwarded_for:
    #     ip_client = x_forwarded_for.split(',')[0]
    # else ...
    # but with current gunicorn/nginx config :
    ip_client = request.META.get("HTTP_X_REAL_IP")
    if ip_client:
        return ip_client
    ip_client = request.META.get("REMOTE_ADDR")
    return ip_client


def is_dlnable(request):
    """true if can use dlna : client in local adress or superuser"""
    return request.user.is_superuser or ipaddress.ip_address(
        get_client_ip(request)
    ) in ipaddress.ip_network(settings.DLNA_NETWORK)


def set_order(order):
    """process order for movie file"""
    check_order = order[1:] if order.startswith("-") else order
    if check_order not in [
        "movie__title",
        "movie__release_year",
        "duration",
        "file_size",
        "rate",
        "date_added",
    ]:
        order = "movie__title"
    if check_order in ["movie__release_year", "rate"]:
        order = f"{order},movie__title"
    return order.split(",")


def paginate(request, objects):
    """prepare pagination"""
    paginator = Paginator(
        objects, request.COOKIES.get("movies_per_page", settings.MOVIES_PER_PAGE)
    )
    page = request.GET.get("page")
    if not page:
        page = 1
    return (paginator, paginator.get_page(page), page)


def annotate_usernotes(qs, request, outref="movie"):
    """annotate queryset with notes"""
    return qs.annotate(
        rate=Subquery(
            UserMovie.objects.filter(
                movie=OuterRef(outref), user__username=request.user.get_username()
            ).values("rate")
        )
    ).annotate(
        viewed=Subquery(
            UserMovie.objects.filter(
                movie=OuterRef(outref), user__username=request.user.get_username()
            ).values("viewed")
        )
    )


def home(request):
    """main page"""
    counts = []
    for vol_label, vol_alias, _, _ in settings.VOLUMES:
        qvar = Q(file_status="OK")
        if vol_label == settings.ALL_VOLUMES:
            vol_label = ""
        else:
            qvar &= Q(file__istartswith=vol_label)
        nbmovies = MovieFile.objects.filter(qvar).count()
        if not nbmovies:
            continue
        size = MovieFile.objects.filter(qvar).aggregate(Sum("file_size"))
        counts.append((vol_label, vol_alias, (nbmovies, size["file_size__sum"])))

    # extract all languages from DB
    languages = set()
    langs = [
        l
        for l in Movie.objects.all()
        .order_by("language")
        .values_list("language", flat=True)
        .distinct()
    ]
    languages = []
    for lang in langs:
        try:
            languages.append((lang, pycountry.languages.get(alpha_2=lang).name))
        except AttributeError:
            pass
    languages.sort(key=lambda i: i[1])

    # extract all countries from DB
    countries_set = set()
    for country in (
        Movie.objects.all().order_by().values_list("countries", flat=True).distinct()
    ):
        myset = set(country.split(", "))
        countries_set = countries_set.union(myset)
    countries = []
    for country in countries_set:
        try:
            countries.append(
                (country, pycountry.countries.get(alpha_2=country.strip()).name)
            )
        except AttributeError:
            pass
    countries.sort(key=lambda i: i[1])

    jobs = (
        Team.objects.all()
        .order_by("job__name")
        .values_list("job__name", flat=True)
        .distinct()
    )
    jobs = [ALL_JOBS] + [j for j in jobs]

    context = {
        "mainvolume": settings.MAIN_VOLUME,
        "nbmovies": Movie.objects.all().count(),
        "nbfiles": MovieFile.objects.all().count(),
        "nbteams": Team.objects.all().count(),
        "nbpeople": Team.objects.all().values_list("person__name").distinct().count(),
        "nbposter": Poster.objects.all().count(),
        "counts": counts,
        "jobs": jobs,
        "languages": languages,
        "countries": countries,
        "dlnable": is_dlnable(request),
        "versions": [os_platform(), python_version, django_version],
    }
    context = add_context_bar(request, context)
    return render(request, "movie/home.html", context)


def all_movies(request):
    """show all movies"""
    movies = MovieFile.objects.all().order_by("movie__title")
    paginator, movies, page = paginate(request, annotate_usernotes(movies, request))
    context = {
        "table_type": f"The {paginator.count} Movies  (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(request, "movie/movie.html", add_context_bar(request, context))


@staff_member_required
def missing(request):
    """movies missing on volumes"""
    movies = MovieFile.objects.filter(file_status="missing").order_by("movie__title")
    movies = annotate_usernotes(movies, request)
    context = {
        "table_type": "Movies File not found",
        "movies": movies,
    }
    return render(request, "movie/movie.html", add_context_bar(request, context))


@staff_member_required
def duplicated(request):
    """Shows duplicated movie"""
    # build duplicated Movie in MovieFile
    movies_ids = (
        MovieFile.objects.values("movie__id_tmdb")
        .annotate(total=Count("movie__id_tmdb"))
        .filter(total__gt=1)
    )
    duplicates = [t["movie__id_tmdb"] for t in movies_ids]
    # movies selection
    movies = MovieFile.objects.filter(
        file_status="OK", movie__id_tmdb__in=duplicates
    ).order_by("movie__title")
    paginator, movies, page = paginate(request, annotate_usernotes(movies, request))
    context = {
        "table_type": f"{paginator.count} Duplicated Movies (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


@staff_member_required
def orphan_movies(request):
    """Shows orphan Movies"""
    movies_ids = MovieFile.objects.values("movie__id_tmdb")
    ids = [t["movie__id_tmdb"] for t in movies_ids]
    # movies selection
    movies = Movie.objects.filter(~Q(id_tmdb__in=ids)).order_by("title")
    paginator, movies, page = paginate(request, movies)
    context = {
        "table_type": f"{paginator.count} Orphan Movies (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(
        request, "movie/m_movies_found.html", add_context_bar(request, context)
    )


@staff_member_required
def without_poster(request):
    """Shows movie without poster"""
    movies = (
        MovieFile.objects.filter(file_status="OK")
        .annotate(images=Count("movie__poster"))
        .filter(images=0)
        .order_by("movie__title")
    )
    paginator, movies, page = paginate(request, annotate_usernotes(movies, request))
    context = {
        "table_type": f"{paginator.count} Movies without Poster (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def no_viewed(request, volume, order):
    """movies not viewed"""
    order = set_order(order)
    request.session["order"] = order[0]
    movies = MovieFile.objects.filter(
        file_status="OK", file__istartswith=volume
    ).exclude(
        movie__id__in=UserMovie.objects.filter(
            user__username=request.user.get_username(),
            viewed__gt=0,
        ).values("movie")
    )
    movies = annotate_usernotes(movies, request)
    movies = movies.order_by(*order)
    paginator, movies, page = paginate(request, movies)
    vol_label = get_volume_alias(volume)
    onwhere = f'on "{vol_label}"' if vol_label else ""
    context = {
        "table_type": f"{paginator.count} Movies not viewed {onwhere} (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def no_viewed_genres(request, volume, order):
    """movies not viewed"""
    order = set_order(order)
    request.session["volume"] = volume
    request.session["order"] = order[0]
    genres = {}
    qsgenres = (
        MovieFile.objects.filter(file_status="OK", file__istartswith=volume)
        .exclude(
            movie__id__in=UserMovie.objects.filter(
                user__username=request.user.get_username(),
                viewed__gt=0,
            ).values("movie")
        )
        .values("movie__genres")
        .distinct()
    )
    for dgenres in qsgenres:
        movie_genres = dgenres["movie__genres"].split(", ")
        for genre in movie_genres:
            if not genre:
                continue
            genres[genre] = 1 if not genre in genres else genres[genre] + 1
    # convert genres dict in list
    genres = [(genre, genres[genre]) for genre in sorted(genres.keys())]
    context = {
        "table_type": "Movies not viewed by genre",
        "genres": genres,
    }
    return render(
        request, "movie/movies_genres.html", add_context_bar(request, context)
    )


def ajax_no_viewed_genre(request):
    """AJAX movies not viewed for a genre"""
    genre = request.POST["genre"]
    volume = request.session["volume"]
    order = request.session["order"]
    # movies for genre wanted
    movies = (
        MovieFile.objects.filter(
            file_status="OK", file__istartswith=volume, movie__genres__contains=genre
        )
        .exclude(
            movie__id__in=UserMovie.objects.filter(
                user__username=request.user.get_username(),
                viewed__gt=0,
            ).values("movie")
        )
        .order_by(*order)
    )
    movies = annotate_usernotes(movies, request)
    movies = movies.order_by(*order)
    context = {
        "table_type": f'Genre "{genre}"',
        "movies": movies,
    }
    html = render_to_string(
        "movie/ajax_movies_found.html", add_context_bar(request, context)
    )
    data = {
        "code": 0,
        "html": html,
    }
    return JsonResponse(data)


def movies_viewed(request, volume, order):
    """movies already viewed"""
    order = set_order(order)
    request.session["order"] = order[0]
    movies = MovieFile.objects.filter(
        file_status="OK",
        file__istartswith=volume,
        movie__id__in=UserMovie.objects.filter(
            user__username=request.user.get_username(),
            viewed__gt=0,
        ).values("movie"),
    )
    movies = annotate_usernotes(movies, request)
    movies = movies.order_by(*order)
    paginator, movies, page = paginate(request, annotate_usernotes(movies, request))
    vol_label = get_volume_alias(volume)
    onwhere = f'on "{vol_label}"' if vol_label else ""
    context = {
        "table_type": f"{paginator.count} Movies already viewed {onwhere} (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def movies_count_genres(request, order):
    """number of movies by genre"""
    order = set_order(order)
    request.session["order"] = order[0]
    # build duplicated titles
    genres_movies = MovieFile.objects.values("movie__genres")
    num_genres = {}
    for entry in genres_movies:
        for genre in entry["movie__genres"].split(","):
            genre = genre.strip()
            if not genre:
                continue
            if genre in num_genres:
                num_genres[genre] += 1
            else:
                num_genres[genre] = 1
    # convert to list (genre, count)
    num_genres = [(genre, num_genres[genre]) for genre in sorted(num_genres.keys())]
    context = {
        "genres": num_genres,
    }
    return render(request, "movie/genres_count.html", add_context_bar(request, context))


def movies_genre(request, genre, order):
    """movies for a genre"""
    order = set_order(order)
    request.session["order"] = order[0]
    movies = MovieFile.objects.filter(movie__genres__contains=genre, file_status="OK")
    movies = annotate_usernotes(movies, request)
    movies = movies.order_by(*order)
    paginator, movies, page = paginate(request, movies)
    context = {
        "table_type": f'{paginator.count} movies for genre "{genre}" (page {page} on {paginator.num_pages})',
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def movies_count_countries(request, order):
    """number of movies by production countries"""
    order = set_order(order)
    request.session["order"] = order[0]
    countries_movies = MovieFile.objects.values("movie__countries")
    num_countries = {}
    for entry in countries_movies:
        for country in entry["movie__countries"].split(","):
            country = country.strip()
            if not country:
                continue
            if country in num_countries:
                num_countries[country] += 1
            else:
                num_countries[country] = 1
    num_countries = [
        (country, pycountry.countries.get(alpha_2=country).name, num_countries[country])
        for country in sorted(num_countries.keys())
    ]
    num_countries.sort(key=lambda i: i[1])
    context = {
        "countries": num_countries,
    }
    return render(
        request, "movie/countries_count.html", add_context_bar(request, context)
    )


def movies_country(request, country, order):
    """movies by country"""
    order = set_order(order)
    request.session["order"] = order[0]
    movies = MovieFile.objects.filter(
        movie__countries__contains=country, file_status="OK"
    )
    movies = annotate_usernotes(movies, request)
    movies = movies.order_by(*order)
    paginator, movies, page = paginate(request, movies)
    context = {
        "table_type": f'{paginator.count} movies for country "{pycountry.countries.get(alpha_2=country.strip()).name}" (page {page} on {paginator.num_pages})',
        "movies": movies,
        "volumes": settings.VOLUMES,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def movies_language(request, language, order):
    """movies by language"""
    order = set_order(order)
    request.session["order"] = order[0]
    movies = MovieFile.objects.filter(
        movie__language__contains=language, file_status="OK"
    )
    annotate_usernotes(movies, request)
    movies = movies.order_by(*order)
    paginator, movies, page = paginate(request, movies)
    context = {
        "table_type": f'{paginator.count} movies for language "{pycountry.languages.get(alpha_2=language).name}" (page {page} on {paginator.num_pages})',
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def searchbypath(request, volume, query, order):
    """Search existant movies"""
    order = set_order(order)
    request.session["order"] = order[0]
    query_ai = unidecode.unidecode(query.lower())
    qvar = Q(file_status="OK")
    if query:
        qvar &= Q(movie__title_ai__contains=query_ai) | Q(
            movie__original_title__contains=query
        )
    if volume not in [None, "", settings.ALL_VOLUMES]:
        qvar &= Q(file__istartswith=volume)
    movies = annotate_usernotes(MovieFile.objects.filter(qvar), request)
    movies = movies.order_by(*order)
    paginator, movies, page = paginate(request, movies)
    vol_label = get_volume_alias(volume)
    onwhere = f'on "{vol_label}"' if vol_label else ""
    onquery = f'with "{query}" in title ' if query else ""
    context = {
        "table_type": f"{paginator.count} Movies {onquery}{onwhere} (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def searchmovies(request):
    """Search Movies"""
    query = request.session["query"] = request.GET.get(
        "query", request.session.get("query", "")
    )
    volume = request.session["vol"] = request.GET.get(
        "vol", request.session.get("vol", "")
    )
    order = request.session["order"] = request.GET.get(
        "order", request.session.get("order", "")
    )
    return HttpResponseRedirect(reverse("searchbypath", args=[volume, query, order]))


def add_context_bar(request, context):
    """add context values for toolbar (volume, query, order)"""
    context.update(
        {
            "query": request.GET.get("query", request.session.get("query", "")),
            "volume": request.GET.get("vol", request.session.get("vol", "")),
            "order": request.GET.get("order", request.session.get("order", "")),
            "volumes": settings.VOLUMES,
            "hidden_fields": request.session.get(
                "hidden_fields", settings.HIDDEN_FIELDS
            ),
        }
    )
    return context


def persons_most_credited(request, jobcriter):
    """Actors most credited in database"""
    persons = (
        Team.objects.filter(job__name=jobcriter)
        .values("person__name", "person__url_img")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    context = {
        "table_type": f"Top {len(persons[: settings.NUM_TOP])} of {jobcriter} (total of {len(persons)})",
        "jobcriter": jobcriter,
        "people": persons[: settings.NUM_TOP],
    }
    return render(
        request, "movie/people_num_movies.html", add_context_bar(request, context)
    )


def num_people(request, job, name):
    """page for movies number by person"""
    jobcriter = "Name"
    qvar = Q()
    if job and job != ALL_JOBS:
        jobcriter = job
        qvar &= Q(job__name=job)
    if name:
        qvar &= Q(person__name__contains=name)
    people = (
        Team.objects.filter(qvar)
        .values("person__name", "person__url_img", "job__name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    show_job = not (job and job != ALL_JOBS)
    forjob = f'in job "{job}"' if job else ""
    context = {
        "table_type": f'{len(people)} persons with name "{name}" {forjob}',
        "jobcriter": jobcriter,
        "people": people,
        "show_job": show_job,
    }
    return render(
        request, "movie/people_num_movies.html", add_context_bar(request, context)
    )


def movie_details(request, idmovie):
    """movie (MovieFile object)  details"""
    movie = MovieFile.objects.get(id=idmovie)
    # load user notes on movie
    try:
        notes_user = UserMovie.objects.get(
            user__username=request.user.get_username(), movie=movie.movie
        )
    except ObjectDoesNotExist:
        notes_user = UserMovie(viewed=0, rate=0)
    #
    volume, _ = ntpath.split(movie.file)
    volume = volume.split(":")[0]
    # check subtitle
    basename = movie.file
    fsubtitle = None
    if movie.file.lower().startswith(settings.DOWNLOADABLE_PATTERN.lower()):
        basename = movie.file[len(settings.DOWNLOADABLE_PATTERN) :]
        if platform.system() == "Linux":
            basename = basename.replace("\\", "/")
        # get subtitle file if any
        base, _ = ntpath.splitext(basename)
        fsubtitle = os.path.join(settings.SENDFILE_ROOT, base + ".srt")
        if not os.path.exists(fsubtitle):
            fsubtitle = None
    context = {
        "movie": movie,
        "notes_user": notes_user,
        "show_job": True,
        "downloadable": movie.file.lower().startswith(
            settings.DOWNLOADABLE_PATTERN.lower()
        ),
        "subtitle": fsubtitle,
        "playable": is_dlnable(request),  # for admin or client in local network
    }
    return render(
        request, "movie/movie_details.html", add_context_bar(request, context)
    )


def m_movie_details(request, idmovie):
    """movie (Movie object)  details"""
    movie = Movie.objects.get(id=idmovie)
    context = {
        "movie": movie,
    }
    return render(
        request, "movie/m_movie_details.html", add_context_bar(request, context)
    )


def movies_count_by_resolution(request):
    """count movies by screen resolution"""
    resolutions = {}
    res = MovieFile.objects.all().values("screen_size")
    resolutions = []
    for movie in res:
        width, height = movie["screen_size"].split("x")
        width = int(width)
        height = int(height)
        if height > width:
            width, height = height, width
        resolutions.append((width, height))
    count = Counter(resolutions)
    resolutions = sorted(count.items(), key=lambda item: (item[0], item[1]))
    context = {
        "resolutions": resolutions,
    }
    return render(request, "movie/movies_res.html", add_context_bar(request, context))


def movies_by_resolution(request, width, height):
    """movies by screen resolution"""
    if not height:
        movies = MovieFile.objects.filter(screen_size__startswith=f"{width}x").order_by(
            "movie__release_year"
        )
    else:
        movies = MovieFile.objects.filter(screen_size=f"{width}x{height}").order_by(
            "movie__release_year"
        )
    paginator, movies, page = paginate(request, annotate_usernotes(movies, request))
    context = {
        "table_type": f"{paginator.count} Movies with resolution {width}x{height} (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def movie_download(request, idmovie):
    """
    Download movie identified by id database
        use django-sendfile2
    """
    movie = get_object_or_404(MovieFile, pk=idmovie)
    basename = movie.file
    if movie.file.lower().startswith(settings.DOWNLOADABLE_PATTERN.lower()):
        basename = movie.file[len(settings.DOWNLOADABLE_PATTERN) :]
        if platform.system() == "Linux":
            basename = basename.replace("\\", "/")
    _, ext = ntpath.splitext(movie.file)
    videoname = f"{movie.movie.title}.{movie.movie.release_year}{ext}"
    return sendfile(
        request,
        basename,
        attachment=True,
        attachment_filename=videoname,
        mimetype="video/*",
    )


def subtitle_download(request, idmovie):
    """
    Download subtitles file for movie identified by id database
        use django-sendfile2
    """
    movie = get_object_or_404(MovieFile, pk=idmovie)
    basename = movie.file
    if movie.file.lower().startswith(settings.DOWNLOADABLE_PATTERN.lower()):
        basename = movie.file[len(settings.DOWNLOADABLE_PATTERN) :]
        if platform.system() == "Linux":
            basename = basename.replace("\\", "/")
    #    _, ext = ntpath.splitext(movie.file)
    basename, _ = ntpath.splitext(basename)
    basename = basename + ".srt"
    subtitle_name = f"{movie.movie.title}.{movie.movie.release_year}.srt"
    return sendfile(
        request,
        basename,
        attachment=True,
        attachment_filename=subtitle_name,
        mimetype="text/plain",
    )


def movies_jobperson(request, job, person):
    """movies for (job, person)"""
    qvar = Q(file_status="OK")
    if job and job != ALL_JOBS:
        qvar &= Q(movie__team__job__name=job)
    if person:
        qvar &= Q(movie__team__person__name__contains=person)
    movies = MovieFile.objects.filter(qvar).order_by("movie__title").distinct()
    paginator, movies, page = paginate(request, annotate_usernotes(movies, request))
    forjob = f'in job "{job}"' if job else ""
    context = {
        "table_type": f'{paginator.count} Movies with name "{person}" {forjob} (page {page} on {paginator.num_pages})',
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


def searchmoviesbyperson(request):
    """Search movies for job and person"""
    return HttpResponseRedirect(
        reverse(
            movies_jobperson, args=[request.GET.get("job"), request.GET.get("name")]
        )
    )


def searchpeople(request):
    """Search for job and person"""
    return HttpResponseRedirect(
        reverse(num_people, args=[request.GET.get("job"), request.GET.get("name")])
    )


def searchcountries(request):
    """Search for production country"""
    return HttpResponseRedirect(
        reverse(movies_country, args=[request.GET.get("countries"), ""])
    )


def searchlanguage(request):
    """Search for language"""
    return HttpResponseRedirect(
        reverse(movies_language, args=[request.GET.get("language"), ""])
    )


def change_movie(request):
    """form change some attribute for movie"""
    idmovie = request.GET.get("idmovie")
    viewed = request.GET.get("viewed")
    rate = request.GET.get("rate")
    try:
        notes_user = UserMovie.objects.get(
            user__username=request.user.get_username(), movie__id=idmovie
        )
        notes_user.viewed = viewed
        notes_user.rate = rate
    except ObjectDoesNotExist:
        notes_user = UserMovie(
            movie=Movie.objects.get(id=idmovie),
            user=User.objects.get(username=request.user.get_username()),
            viewed=viewed,
            rate=rate,
        )
    notes_user.save()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


def remove_poster(request):
    """form remove a poster object from movie"""
    idposter = request.GET.get("idposter")
    poster = get_object_or_404(Poster, id=idposter)
    poster.delete()
    if os.path.exists(poster.poster.path):
        os.remove(poster.poster.path)
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


def set_renderer(request):
    """set renderer from form"""
    renderer = request.GET.get("renderers")
    request.session["default_renderer"] = renderer
    # return to home rather than "request.META.get('HTTP_REFERER')"
    return HttpResponseRedirect(reverse("home"))


def dlna_tools(request):
    """display DNLA discover"""
    context = {
        "mediaservers": [vol[0] for vol in settings.VOLUMES if vol[3][0]],
    }
    return render(request, "movie/dlna.html", add_context_bar(request, context))


def options(request):
    """user options"""
    renderer_uri = request.session.get(
        "default_renderer", settings.DLNA_RENDERERS[0][0]
    )
    context = {
        "volumes": settings.VOLUMES,
        "playable": is_dlnable(request),
        "renderers": settings.DLNA_RENDERERS,
        "renderer_uri": renderer_uri,
        "movies_per_page": request.COOKIES.get(
            "movies_per_page", settings.MOVIES_PER_PAGE
        ),
    }
    return render(request, "movie/options.html", add_context_bar(request, context))


def set_hidden_fields(request):
    """set hidden field from form"""
    request.session["hidden_fields"] = list(request.GET.dict().keys())
    # return to home rather than "request.META.get('HTTP_REFERER')"
    return HttpResponseRedirect(reverse("home"))


def set_movies_per_page(request):
    """set movies per page from form"""
    try:
        movies_per_page = int(request.POST["movies_per_page"])
    except ValueError:
        movies_per_page = 0
    if movies_per_page <= 0:
        return JsonResponse({"result": "Need integer value > 0"})
    response = JsonResponse({"result": "done"})
    response.set_cookie("movies_per_page", movies_per_page)
    return response


def advanced_search(request):
    """advanced search"""
    if request.method != "POST":
        context = {
            "volumes": settings.VOLUMES,
        }
        if "adv_search" in request.session:
            # set previous query
            for key in request.session["adv_search"].keys():
                if key == "csrfmiddlewaretoken":
                    continue
                context[key] = request.session["adv_search"][key]
        return render(
            request, "movie/advsearch.html", add_context_bar(request, context)
        )

    # build request
    request.session["adv_search"] = request.POST
    query = request.POST["query"]
    qvar = Q()
    if "title" in request.POST:
        qvar |= Q(movie__title_ai__contains=query)
    if "title_orig" in request.POST:
        qvar |= Q(movie__original_title__contains=query)
    if "overview" in request.POST:
        qvar |= Q(movie__overview__contains=query)
    if "format" in request.POST:
        qvar |= Q(movie_format__contains=query)
    if "file" in request.POST:
        qvar |= Q(file__contains=query)
    if "people" in request.POST:
        qvar |= Q(movie__team__name__contains=query)
    if "character" in request.POST:
        qvar |= Q(movie__team__extension__contains=query)
    volume = request.POST["vol"]
    if volume not in [None, "", settings.ALL_VOLUMES]:
        qvar &= Q(file__istartswith=volume)
    qvar &= Q(file_status="OK")
    order = set_order(request.POST["order"])
    request.session["order"] = order[0]
    movies = MovieFile.objects.filter(qvar).distinct()
    movies = annotate_usernotes(movies, request)
    movies = movies.order_by(*order)
    paginator, movies, page = paginate(request, movies)
    vol_label = get_volume_alias(volume)
    onwhere = f'on "{vol_label}"' if vol_label else ""
    onquery = f'"{query}" ' if query else ""
    context = {
        "table_type": f"{paginator.count} movies searching {onquery}{onwhere} (page {page} on {paginator.num_pages})",
        "movies": movies,
    }
    return render(request, "movie/movies_found.html", add_context_bar(request, context))


@staff_member_required
def test_mailing(request, days):
    """test mail template"""
    if days and days.isdigit():
        days = int(days)
    else:
        days = 7
    date_from = datetime.now() - timedelta(days=days)
    movies = MovieFile.objects.filter(
        file_status="OK",
        file__istartswith=settings.MAIN_VOLUME[0],
        date_added__gte=make_aware(date_from),
    ).order_by("movie__title")
    admin_users = User.objects.filter(is_staff=1)
    siteloc = urlparse(request.build_absolute_uri())
    context = {
        "mainvolume": settings.MAIN_VOLUME,
        "user": admin_users[0].username.capitalize(),
        "siteloc": f"{siteloc.scheme}://{siteloc.netloc}",
        "days": days,
        "movies": movies,
    }
    html = render_to_string("movie/mail_newmovies.html", context)
    text = render_to_string("movie/mail_newmovies.txt", context)

    return render(
        request,
        "movie/test_mail_newmovies.html",
        {"mail_html": html, "mail_text": text},
    )
