# -*- coding: utf-8 -*-
"""
    The views
"""

import os
import ntpath

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse

from .models import Movie, Team, Poster


def get_volume_alias(label):
    """return volume alias from volume label"""
    for vol_label, vol_alias, _, _ in settings.VOLUMES:
        if label.lower() == vol_label.lower():
            return vol_alias
    return None


def set_order(order):
    """process order"""
    check_order = order[1:] if order.startswith("-") else order
    if check_order not in ["title", "release_year", "duration", "file_size", "rate"]:
        order = "title"
    if check_order in ["release_year", "rate"]:
        order = "{},title".format(order)
    return order.split(",")


def paginate(request, objects):
    """prepare pagination"""
    paginator = Paginator(objects, settings.MOVIES_PER_PAGE)
    page = request.GET.get("page")
    if not page:
        page = 1
    return (paginator, paginator.get_page(page), page)


def home(request):
    """main page"""
    renderer_uri = request.session.get(
        "default_renderer", settings.DLNA_RENDERERS[0][0]
    )
    context = {
        "volumes": settings.VOLUMES,
        "renderers": settings.DLNA_RENDERERS,
        "renderer_uri": renderer_uri,
    }
    return render(request, "movie/home.html", context)


def all_movies(request):
    """show all movies"""
    movies = Movie.objects.all().order_by("title")
    paginator, movies, page = paginate(request, movies)
    context = {
        "table_type": "The {2} Movies  (page {0} on {1})".format(
            page, paginator.num_pages, paginator.count
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
    }
    return render(request, "movie/movie.html", context)


def missing(request):
    """movies missing on volumes"""
    movies = Movie.objects.filter(file_status="missing").order_by("title")
    return render(
        request,
        "movie/movie.html",
        {
            "table_type": "Movies not found",
            "movies": movies,
            "volumes": settings.VOLUMES,
        },
    )


def duplicated(request):
    """Shows duplicated movie titles"""
    # build duplicated titles
    titles = (
        Movie.objects.filter(file_status="OK")
        .values(dtitle=Lower("title"))
        .annotate(num_titles=Count("title"))
        .filter(num_titles__gt=1)
        .order_by("title")
    )
    titles = [t["dtitle"] for t in titles]
    # and select movies
    movies = (
        Movie.objects.filter(file_status="OK")
        .annotate(dtitle=Lower("title"))
        .filter(dtitle__in=titles)
        .order_by("title")
    )
    paginator, movies, page = paginate(request, movies)
    context = {
        "table_type": "{2} Duplicated Movies (page {0} on {1})".format(
            page, paginator.num_pages, paginator.count
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": "",
        "query": "",
    }
    return render(request, "movie/movies_found.html", context)


def without_poster(request):
    """Shows movie without poster"""
    movies = (
        Movie.objects.filter(file_status="OK")
        .annotate(images=Count("poster"))
        .filter(images=0)
        .order_by("title")
    )
    paginator, movies, page = paginate(request, movies)
    context = {
        "table_type": "{2} Movies without Poster (page {0} on {1})".format(
            page, paginator.num_pages, paginator.count
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": "",
        "query": "",
    }
    return render(request, "movie/movies_found.html", context)


def no_viewed(request, volume, order):
    """movies not viewed"""
    order = set_order(order)
    movies = Movie.objects.filter(
        file_status="OK", file__istartswith=volume, viewed=0
    ).order_by(*order)
    paginator, movies, page = paginate(request, movies)
    vol_label = get_volume_alias(volume)
    onwhere = 'on "{}"'.format(vol_label) if vol_label else ""
    context = {
        "table_type": "{2} Movies not viewed {3} (page {0} on {1})".format(
            page, paginator.num_pages, paginator.count, onwhere
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": volume,
        "query": "",
        "order": order[0],
    }
    return render(request, "movie/movies_found.html", context)


def no_viewed_genres(request, volume, order):
    """movies not viewed"""
    order = set_order(order)
    request.session["volume"] = volume
    request.session["order"] = order

    genres = {}
    qsgenres = (
        Movie.objects.filter(file_status="OK", file__istartswith=volume, viewed=0)
        .values("genres")
        .distinct()
    )
    for dgenres in qsgenres:
        movie_genres = dgenres["genres"].split(", ")
        for genre in movie_genres:
            if not genre:
                continue
            genres[genre] = 1 if not genre in genres else genres[genre] + 1
    # convert genres dict in list
    genres = [(genre, genres[genre]) for genre in sorted(genres.keys())]

    context = {
        "table_type": "Movies not viewed by genre",
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "genres": genres,
        "volumes": settings.VOLUMES,
        "volume": volume,
        "query": "",
        "order": order[0],
    }
    return render(request, "movie/movies_genres.html", context)


def ajax_no_viewed_genre(request):
    """AJAX movies not viewed for a genre"""
    genre = request.POST["genre"]
    volume = request.session["volume"]
    order = request.session["order"]

    # movies for genre wanted
    movies = Movie.objects.filter(
        file_status="OK", file__istartswith=volume, viewed=0, genres__contains=genre
    ).order_by(*order)
    print(len(movies))

    context = {
        "table_type": 'Genre "{0}"'.format(genre),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": volume,
        "query": "",
    }
    html = render_to_string("movie/ajax_movies_found.html", context)
    data = {
        "code": 0,
        "html": html,
    }
    return JsonResponse(data)


def movies_viewed(request, volume, order):
    """movies already viewed"""
    order = set_order(order)
    movies = Movie.objects.filter(
        file_status="OK", file__istartswith=volume, viewed__gt=0
    ).order_by(*order)
    paginator, movies, page = paginate(request, movies)
    vol_label = get_volume_alias(volume)
    onwhere = 'on "{}"'.format(vol_label) if vol_label else ""
    context = {
        "table_type": "{2} Movies already viewed {3} (page {0} on {1})".format(
            page, paginator.num_pages, paginator.count, onwhere
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": volume,
        "query": "",
        "order": order[0],
    }
    return render(request, "movie/movies_found.html", context)


def movies_genres(request, order):
    """number of movies by genre"""
    order = set_order(order)
    # build duplicated titles
    genres_movies = Movie.objects.values("genres")
    num_genres = {}
    for entry in genres_movies:
        for genre in entry["genres"].split(","):
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
        "volumes": settings.VOLUMES,
        "volume": "",
        "query": "",
        "order": order,
    }
    return render(request, "movie/genres_count.html", context)


def movies_genre(request, genre, order):
    """movies for a genre"""
    order = set_order(order)
    movies = Movie.objects.filter(genres__contains=genre, file_status="OK").order_by(
        *order
    )
    total_movies = len(movies)
    paginator, movies, page = paginate(request, movies)
    context = {
        "table_type": '{0} movies founded for genre "{3}" (page {1} on {2})'.format(
            total_movies, page, paginator.num_pages, genre
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": "",
        "query": "",
        "order": order[0],
    }
    return render(request, "movie/movies_found.html", context)


def searchbypath(request, volume, query, order):
    """Search existant movies"""
    order = set_order(order)
    if volume in [None, "", settings.ALL_VOLUMES]:
        if query:
            movies = Movie.objects.filter(
                (Q(title__contains=query) | Q(original_title__contains=query))
                & Q(file_status="OK")
            ).order_by(*order)
        else:
            movies = Movie.objects.filter(file_status="OK").order_by(*order)
    else:
        if query:
            movies = Movie.objects.filter(
                Q(
                    file__istartswith=volume,
                )
                & (Q(title__contains=query) | Q(original_title__contains=query))
            ).order_by(*order)
        else:
            movies = Movie.objects.filter(
                file__istartswith=volume, file_status="OK"
            ).order_by(*order)
    paginator, movies, page = paginate(request, movies)
    vol_label = get_volume_alias(volume)
    onwhere = 'on "{}"'.format(vol_label) if vol_label else ""
    onquery = 'with "{}" in title '.format(query) if query else ""
    context = {
        "table_type": "{2} Movies found {4}{3} (page {0} on {1})".format(
            page, paginator.num_pages, paginator.count, onwhere, onquery
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": volume,
        "query": query,
        "order": order[0],
    }
    return render(request, "movie/movies_found.html", context)


def searchmovies(request):
    """Search Movies"""
    query = request.GET.get("query")
    vol = request.GET.get("vol")
    order = request.GET.get("order")
    return searchbypath(request, vol, query, order)


def persons_most_credited(request, jobcriter):
    """Actors most credited in database"""
    persons = (
        Team.objects.filter(job=jobcriter)
        .values("name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    context = {
        "table_type": "Top {} of {} (total of {})".format(
            len(persons[: settings.NUM_TOP]), jobcriter, len(persons)
        ),
        "jobcriter": jobcriter,
        "people": persons[: settings.NUM_TOP],
        "volumes": settings.VOLUMES,
        "volume": "",
        "query": "",
    }
    return render(request, "movie/people_num_movies.html", context)


def num_people(request, job, name):
    """page for movies number by person"""
    if job:
        jobcriter = job
        people = (
            Team.objects.filter(job=job, name__contains=name)
            .values("name", "job")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
    else:
        jobcriter = "Name"
        people = (
            Team.objects.filter(name__contains=name)
            .values("name", "job")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
    forjob = 'in job "{}"'.format(job) if job else ""
    context = {
        "table_type": '{0} persons found with name "{1}" {2}'.format(
            len(people), name, forjob
        ),
        "jobcriter": jobcriter,
        "people": people,
        "show_job": True,
        "volumes": settings.VOLUMES,
        "volume": "",
        "query": "",
    }
    return render(request, "movie/people_num_movies.html", context)


def movie_details(request, idmovie):
    """movie details"""
    movie = Movie.objects.get(id=idmovie)
    volume, _ = ntpath.split(movie.file)
    volume = volume.split(":")[0]
    context = {
        "movie": movie,
        "show_job": True,
        "playable": True,  # always potentially playable with my specific protocol.bat (see https://github.com/stefansundin/vlc-protocol/)
        # 'playable': settings.DLNA_MEDIASERVERS[volume.lower()][0] is not None,
        "volumes": settings.VOLUMES,
        "volume": "",
        "query": "",
    }
    return render(request, "movie/movie_details.html", context)


def movies_jobperson(request, job, person):
    """movies for (job, person)"""
    if job:
        movies = (
            Movie.objects.filter(
                team__job=job, team__name__contains=person, file_status="OK"
            )
            .distinct()
            .order_by("title")
        )
    else:
        movies = (
            Movie.objects.filter(team__name__contains=person, file_status="OK")
            .distinct()
            .order_by("title")
        )
    paginator, movies, page = paginate(request, movies)
    forjob = 'in job "{}"'.format(job) if job else ""
    context = {
        "table_type": '{2} Movies found with name "{3}" {4} (page {0} on {1})'.format(
            page, paginator.num_pages, paginator.count, person, forjob
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": "",
        "query": "",
    }
    return render(request, "movie/movies_found.html", context)


def searchmoviesbyperson(request):
    """Search movies for job and person"""
    job = request.GET.get("job")
    name = request.GET.get("name")
    return movies_jobperson(request, job, name)


def searchpeople(request):
    """Search for job and person"""
    job = request.GET.get("job")
    name = request.GET.get("name")
    return num_people(request, job, name)


def change_movie(request):
    """form change some attribute for movie"""
    idmovie = request.GET.get("idmovie")
    viewed = request.GET.get("viewed")
    rate = request.GET.get("rate")
    movie = get_object_or_404(Movie, pk=idmovie)
    movie.viewed = viewed
    movie.rate = rate
    movie.save()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


def remove_poster(request):
    """form remove a poster object from movie"""
    idposter = request.GET.get("idposter")
    poster = get_object_or_404(Poster, id=idposter)
    print(poster.poster.path)
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
        "volumes": settings.VOLUMES,
        "mediaservers": [vol[0] for vol in settings.VOLUMES if vol[3][0]],
    }
    return render(request, "movie/dlna.html", context)


def options(request):
    """user options"""
    renderer_uri = request.session.get(
        "default_renderer", settings.DLNA_RENDERERS[0][0]
    )
    context = {
        "volumes": settings.VOLUMES,
        "renderers": settings.DLNA_RENDERERS,
        "renderer_uri": renderer_uri,
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
    }
    return render(request, "movie/options.html", context)


def set_hidden_fields(request):
    """set hidden field from form"""
    request.session["hidden_fields"] = list(request.GET.dict().keys())
    # return to home rather than "request.META.get('HTTP_REFERER')"
    return HttpResponseRedirect(reverse("home"))


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
        return render(request, "movie/advsearch.html", context)

    # build request
    request.session["adv_search"] = request.POST
    query = request.POST["query"]
    qvar = Q()
    if "title" in request.POST:
        qvar |= Q(title__contains=query)
    if "title_orig" in request.POST:
        qvar |= Q(original_title__contains=query)
    if "overview" in request.POST:
        qvar |= Q(overview__contains=query)
    if "format" in request.POST:
        qvar |= Q(movie_format__contains=query)
    if "file" in request.POST:
        qvar |= Q(file__contains=query)
    if "people" in request.POST:
        qvar |= Q(team__name__contains=query)
    if "character" in request.POST:
        qvar |= Q(team__extension__contains=query)

    order = set_order(request.POST["order"])
    volume = request.POST["vol"]
    if volume in [None, "", settings.ALL_VOLUMES]:
        if query:
            movies = (
                Movie.objects.filter(qvar & Q(file_status="OK"))
                .distinct()
                .order_by(*order)
            )
        else:
            movies = Movie.objects.filter(file_status="OK").order_by(*order)
    else:
        if query:
            movies = (
                Movie.objects.filter(
                    qvar & Q(file__istartswith=volume) & Q(file_status="OK")
                )
                .distinct()
                .order_by(*order)
            )
        else:
            movies = Movie.objects.filter(
                file__istartswith=volume, file_status="OK"
            ).order_by(*order)
    paginator, movies, page = paginate(request, movies)
    vol_label = get_volume_alias(volume)
    onwhere = 'on "{}"'.format(vol_label) if vol_label else ""
    onquery = '"{}" '.format(query) if query else ""
    context = {
        "table_type": "{2} Movies found searching {4}{3} (page {0} on {1})".format(
            page, paginator.num_pages, paginator.count, onwhere, onquery
        ),
        "hidden_fields": request.session.get("hidden_fields", settings.HIDDEN_FIELDS),
        "movies": movies,
        "volumes": settings.VOLUMES,
        "volume": volume,
        "query": query,
        "order": order[0],
    }
    return render(request, "movie/movies_found.html", context)
