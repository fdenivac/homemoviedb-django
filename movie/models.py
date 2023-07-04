"""
Database Models
"""

from django.conf import settings
from django.db import models


class Movie(models.Model):
    """Movie table : describe movie, datas taken form TMDB"""

    # year
    release_year = models.IntegerField(default=0)
    # original title
    original_title = models.TextField(blank=False, null=False)
    # localized title
    title = models.TextField(blank=False, null=False)
    # title without diacritics (accent insensitive)
    title_ai = models.TextField(blank=False, null=True)
    # movie genres (e.g. "Comédie, Drame")
    genres = models.TextField(blank=True)
    # overwiew
    overview = models.TextField(blank=True)
    # countries in iso_3166_1 (production)
    countries = models.TextField(blank=True)
    # originale language
    language = models.TextField(blank=True)
    # TMDB id
    id_tmdb = models.IntegerField(null=True)
    # append date append
    date_added = models.DateTimeField(blank=False, null=True)
    # various files for this movie
    files = models.ManyToManyField("MovieFile", related_name="+")

    def __str__(self):
        return f"{self.title} - {self.release_year} [{ self.id}]"

    class Meta:
        ordering = ("title",)


class Job(models.Model):
    """Job"""

    # job name
    name = models.TextField(blank=False, null=False)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        ordering = ("name",)


class Person(models.Model):
    """Person of team (casting or crew)"""

    # person name
    name = models.TextField(blank=False, null=False)
    # id tmdb
    id_tmdb = models.IntegerField(null=False, unique=True)
    # url image tmdb
    url_img = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.id_tmdb})"

    class Meta:
        # unique_together = ("name", "id_tmdb")
        # unique_together = ("job", "id_tmdb", "movie")
        ordering = ("name",)


class Team(models.Model):
    """keys for movie"""

    # movie reference
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="team")
    # job (Actor, Director, ...)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=False)
    # person reference
    person = models.ForeignKey(Person, on_delete=models.CASCADE, null=False)
    # order in casting
    cast_order = models.IntegerField(null=True)
    # extension: character for actor
    extension = models.TextField(null=True)

    def __str__(self):
        return f"{self.movie.title} ({self.movie.release_year}) [{ self.movie.id}] - {self.person.name}"

    class Meta:
        unique_together = ("job", "person", "movie")
        # unique_together = ("job", "id_tmdb", "movie")
        ordering = (
            "movie__title",
            "person__name",
        )


class Poster(models.Model):
    """Movie Posters"""

    # movie reference
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="poster")
    # TMDB url
    url_tmdb = models.TextField(blank=False, null=False)
    # image
    poster = models.ImageField(upload_to="posters/", null=True)

    def __str__(self):
        return f"{self.movie.title} - {self.movie.release_year} - {self.url_tmdb}"

    class Meta:
        ordering = ("movie",)


class MovieFile(models.Model):
    """
    MovieFile : movie file
        Note: several movie files can have the same movie description
    """

    # full path of movie file
    file = models.TextField(unique=True, blank=False, null=False)
    # file size
    file_size = models.IntegerField(null=True)
    # movie format (container, streams)
    movie_format = models.TextField(null=True)
    # global bitrate
    bitrate = models.IntegerField(null=True)
    # image size
    screen_size = models.TextField(null=True)
    # duration (seconds)
    duration = models.IntegerField(default=0)

    # status (present / moved / deleted ...)
    file_status = models.TextField(blank=False, null=False)
    # append date append
    date_added = models.DateTimeField(blank=False, null=True)

    # the movie description
    movie = models.ForeignKey(Movie, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.file} - {self.movie.title}"

    class Meta:
        ordering = ("file",)

    # helper functions
    def duration_string(self):
        """helper function formating duration"""
        return f"{(self.duration // 3600):02d}:{((self.duration // 60) % 60):02d}:{(self.duration % 60):02d}"


class UserMovie(models.Model):
    """
    UserMovie : user datas on movie
    """

    # User
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # movie
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    # number of views
    viewed = models.IntegerField(default=0)
    # local rating
    rate = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.movie.title} : views:{self.viewed}, rate:{self.rate}"

    class Meta:
        unique_together = ("user", "movie")
