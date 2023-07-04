# -*- coding: utf-8 -*-
"""
    Compact movie description from TMDB
"""

from tmdbv3api import Movie as TMDbMovie, Search as TMDbSearch

from movie.models import Movie


class MovieDescription:
    """
    Movie description from TMDb
    """

    __slots__ = [
        "fulldesc",
        "id_tmdb",
        "title",
        "original_title",
        "release_date",
        "overview",
        "genres",
        "original_language",
        "countries",
    ]

    def __init__(self, movie: Movie):
        """init from TMDB Movie json"""
        self.fulldesc = True
        self.id_tmdb = movie.id
        self.title = movie.title
        self.original_title = movie.original_title
        self.release_date = (
            movie.release_date.split("-")[0] if hasattr(movie, "release_date") else ""
        )
        self.overview = movie.overview
        if "genres" in movie:
            self.genres = ", ".join([genre.name for genre in movie.genres])
        else:
            self.genres = None
            self.fulldesc = False
        self.original_language = movie.original_language.upper()
        self.countries = (
            ", ".join([country["iso_3166_1"] for country in movie.production_countries])
            if self.fulldesc
            else None
        )

    @classmethod
    def from_search(cls, tmdb_search: TMDbSearch, moviename: str, year=None):
        """search movie title in TMDB, return list"""
        results = tmdb_search.movies({"query": moviename, "year": year})
        return [cls(movie) for movie in results]

    @classmethod
    def from_id(cls, tmdb_movie: TMDbMovie, idmovie: int):
        """get TMDB movie by id"""
        return cls(tmdb_movie.details(str(idmovie)))

    def get_full_description(self, tmdb_movie: TMDbMovie):
        """complete description with details"""
        if self.fulldesc:
            return
        movie = tmdb_movie.details(self.id_tmdb)
        self.genres = ", ".join([genre.name for genre in movie.genres])
        self.countries = ", ".join(
            [country["iso_3166_1"] for country in movie.production_countries]
        )
        self.fulldesc = True
