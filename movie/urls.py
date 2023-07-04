# -*- coding: utf-8 -*-
""" site URLs """

from django.urls import path, re_path
from . import authentication, views, api


urlpatterns = [
    # registration
    re_path(r"^accounts/logout$", authentication.confirm_logout, name="confirm_logout"),
    re_path(r"^accounts/logout-go$", authentication.logout, name="logout"),
    # WARNING path('accounts/login/',..) is added in moviedb.urls on start (this file is included)
    # user pages
    path("", views.home, name="home"),
    re_path(r"^movies/$", views.all_movies, name="movies"),
    re_path(r"^missing/$", views.missing, name="missing"),
    re_path(r"^duplicated/$", views.duplicated, name="duplicated"),
    re_path(r"^noposter/$", views.without_poster, name="noposter"),
    re_path(r"^genres/(.+)/$", views.movies_count_genres, name="genres"),
    re_path(r"^countries/(.+)/$", views.movies_count_countries, name="countries"),
    re_path(r"^orphan/$", views.orphan_movies, name="orphan"),
    re_path(r"^noviewed/(\w*)/([-\w]*)/$", views.no_viewed, name="noviewed"),
    re_path(
        r"^noviewedgenres/(\w*)/([-\w]*)/$",
        views.no_viewed_genres,
        name="noviewedgenres",
    ),
    re_path(r"^noviewgenre/$", views.ajax_no_viewed_genre, name="ajax_noviewed_genre"),
    re_path(r"^viewed/(\w*)/([-\w]*)/$", views.movies_viewed, name="viewed"),
    re_path(
        r"^country/([,\w]*)/([-\w]*)/$", views.movies_country, name="movies_country"
    ),
    re_path(
        r"^language/([,\w]*)/([-\w]*)/$", views.movies_language, name="movies_language"
    ),
    re_path(r"^searchvol/(.*)/(.*)/(.*)/$", views.searchbypath, name="searchbypath"),
    re_path(
        r"^toppersons/(.+)$", views.persons_most_credited, name="persons_most_credited"
    ),
    re_path(r"^people/(.*)/(.*)$", views.num_people, name="people"),
    re_path(
        r"^moviesperson/([\w|\W]*)/(.*)$",
        views.movies_jobperson,
        name="movies_jobperson",
    ),
    re_path(r"^moviesgenre/(.+)/(.*)$", views.movies_genre, name="movies_genre"),
    re_path(r"^movie_details/(\d+)/$", views.movie_details, name="movie_details"),
    re_path(r"^mmovie_details/(\d+)/$", views.m_movie_details, name="mmovie_details"),
    re_path(r"^movie_download/(\d+)/$", views.movie_download, name="movie_download"),
    re_path(
        r"^countmoviesres/$",
        views.movies_count_by_resolution,
        name="movies_count_by_resolution",
    ),
    re_path(
        r"^moviesres/(.+)/(.*)$",
        views.movies_by_resolution,
        name="movies_by_resolution",
    ),
    re_path(
        r"^subtitle_download/(\d+)/$", views.subtitle_download, name="subtitle_download"
    ),
    re_path(r"^dlnatools$", views.dlna_tools, name="dlna_tools"),
    # forms
    re_path(r"^searchmovies/$", views.searchmovies, name="searchmovies"),
    re_path(r"^searchpeople/$", views.searchpeople, name="searchpeople"),
    re_path(
        r"^searchmoviesbyjobperson/$",
        views.searchmoviesbyperson,
        name="searchmoviesbyjobperson",
    ),
    re_path(r"^searchcountries/$", views.searchcountries, name="searchcountries"),
    re_path(r"^searchlanguage/$", views.searchlanguage, name="searchlanguage"),
    re_path(r"^set-details/$", views.change_movie, name="setdetails"),
    re_path(r"^removeposter/$", views.remove_poster, name="removeposter"),
    re_path(r"^set-renderer/$", views.set_renderer, name="set_renderer"),
    re_path(r"^options/$", views.options, name="options"),
    re_path(r"^set-hidden/$", views.set_hidden_fields, name="set_hidden_fields"),
    re_path(r"^set-mpp/$", views.set_movies_per_page, name="set_movies_per_page"),
    re_path(r"^advsearch/$", views.advanced_search, name="advanced_search"),
    # api user
    re_path(r"^api/movie/play$", api.movie_play, name="movie_play"),
    re_path(r"^api/dlna/browe$", api.dlna_browse, name="dlna_browse"),
    # api admin
    re_path(r"^api/movie/append$", api.append_movie, name="append_movie"),
    re_path(r"^api/movie/info$", api.movie_info, name="movie_info"),
    re_path(r"^api/movies/dir$", api.movies_dir, name="movies_dir"),
    re_path(r"^api/movies/indexes$", api.movies_ids, name="movies_ids"),
    re_path(r"^api/movie/update$", api.update_movie, name="update_movie"),
    re_path(r"^api/movie/remove$", api.remove_movie, name="remove_movie"),
    re_path(r"^api/dlna/discover$", api.dlna_discover, name="dlna_discover"),
    re_path(r"^api/dlna/checkmedias$", api.dlna_check_medias, name="dlna_check_medias"),
    # tests
    re_path(r"^test_mail/(\d*)/$", views.test_mailing, name="test_mailing"),
]
