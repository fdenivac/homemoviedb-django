# -*- coding: utf-8 -*-
"""
TMDb access
"""
from tmdbv3api import (
    TMDb,
    TV as TMDbTV,
    Search as TMDbSearch,
    Configuration,
    Season as TMDbSeason,
    Episode as TMDbEpisode,
    Movie as TMDbMovie,
    Person as TMDbPerson,
)
from tmdbv3api.exceptions import TMDbException


class TMDB_Api:
    """store TMDB api, handles"""

    def __init__(self, api_key, language):
        self.tmdb = TMDb()
        self.tmdb.api_key = api_key
        self.tmdb.language = language
        self.config = Configuration().info()
        self.serie = TMDbTV()
        self.season = TMDbSeason()
        self.episode = TMDbEpisode()
        self.search = TMDbSearch()
        self.movie = TMDbMovie()
        self.person = TMDbPerson()
        self.cache_serie_details = {}
        self.cache_season_details = {}

    def get_serie_details(self, id_tmdb):
        """get serie details"""
        if id_tmdb in self.cache_serie_details:
            return self.cache_serie_details[id_tmdb]
        try:
            serie_details = self.serie.details(
                id_tmdb, append_to_response="credits,images"
            )
            # print(f"  Get serie details({id_tmdb})")
            self.cache_serie_details[id_tmdb] = serie_details
        except TMDbException:
            serie_details = None
        return serie_details

    def get_season_details(self, id_tmdb, season: int):
        """get season details from TMDb"""
        key = f"{id_tmdb}-{season}"
        if key in self.cache_season_details:
            return self.cache_season_details[key]
        try:
            season_details = self.season.details(
                id_tmdb,
                season,
                append_to_response="credits,images",
            )
            # print(f"  Get season details({key})")
            self.cache_season_details[key] = season_details
        except TMDbException:
            season_details = None
        return season_details

    def get_episode_details(self, id_tmdb, season: int, episode: int):
        """get episode details from TMDb"""
        try:
            episode_details = self.episode.details(
                id_tmdb,
                season,
                episode,
                append_to_response="credits,images",
            )
        except TMDbException:
            episode_details = None
        return episode_details

    def search_serie(self, seriename: str, year=None):
        """search for serie name"""
        try:
            results = self.search.tv_shows(
                {"query": seriename, "first_air_date_year": year}
            )
        except TMDbException:
            results = None
        return results
