# -*- coding: utf-8 -*-
''' site URLs '''

from django.conf.urls import url
from django.urls import path
from . import authentication, views, api


urlpatterns = [
    # registration
    url(r'^accounts/logout$', authentication.confirm_logout, name='confirm_logout'),
    url(r'^accounts/logout-go$', authentication.logout, name='logout'),
    # WARNING path('accounts/login/',..) is added in moviedb.urls on start (this file is included)

    # user pages
    path('', views.home, name='home'),
    url(r'^movies/$', views.all_movies, name='movies'),
    url(r'^missing/$', views.missing, name='missing'),
    url(r'^duplicated/$', views.duplicated, name='duplicated'),
    url(r'^noposter/$', views.without_poster, name='noposter'),
    url(r'^genres/(.+)/$', views.movies_genres, name='genres'),
    url(r'^noviewed/(\w*)/([-\w]*)/$', views.no_viewed, name='noviewed'),
    url(r'^noviewedgenres/(\w*)/([-\w]*)/$', views.no_viewed_genres, name='noviewedgenres'),
    url(r'^noviewgenre/$', views.ajax_no_viewed_genre, name='ajax_noviewed_genre'),
    url(r'^viewed/(\w*)/([-\w]*)/$', views.movies_viewed, name='viewed'),
    url(r'^searchvol/(\w*)/(\w*)/([-\w]*)/$', views.searchbypath, name='searchbypath'),
    url(r'^toppersons/(.+)$', views.persons_most_credited, name='persons_most_credited'),
    url(r'^people/(\w*)/(.*)$', views.num_people, name='people'),
    url(r'^moviesperson/([\w|\W]*)/(.*)$', views.movies_jobperson, name='movies_jobperson'),
    url(r'^moviesgenre/(.+)/(.*)$', views.movies_genre, name='movies_genre'),
    url(r'^movie_details/(\d+)/$', views.movie_details, name='movie_details'),
    url(r'^dlnatools$', views.dlna_tools, name='dlna_tools'),
    # forms
    url(r'^searchmovies/$', views.searchmovies, name='searchmovies'),
    url(r'^searchpeople/$', views.searchpeople, name='searchpeople'),
    url(r'^searchmoviesbyjobperson/$', views.searchmoviesbyperson, name='searchmoviesbyjobperson'),
    url(r'^set-details/$', views.change_movie, name='setdetails'),
    url(r'^removeposter/$', views.remove_poster, name='removeposter'),
    url(r'^set-renderer/$', views.set_renderer, name='set_renderer'),
    url(r'^options/$', views.options, name='options'),
    url(r'^set-hidden/$', views.set_hidden_fields, name='set_hidden_fields'),
    url(r'^advsearch/$', views.advanced_search, name='advanced_search'),

    # api user
    url(r'^api/movie/play$', api.movie_play, name='movie_play'),
    url(r'^api/dlna/browe$', api.dlna_browse, name='dlna_browse'),
    # api admin
    url(r'^api/movie/append$', api.append_movie, name='append_movie'),
    url(r'^api/movie/info$', api.movie_info, name='movie_info'),
    url(r'^api/movies/dir$', api.movies_dir, name='movies_dir'),
    url(r'^api/movie/status$', api.set_movie_status, name='set_movies_status'),
    url(r'^api/movie/status$', api.set_movie_status, name='set_movies_status'),
    url(r'^api/dlna/discover$', api.dlna_discover, name='dlna_discover'),
    url(r'^api/dlna/checkmedias$', api.dlna_check_medias, name='dlna_check_medias'),
]
