'''
Database Models
'''

from django.db import models

class Movie(models.Model):
    ''' Movie table  '''
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

    # year
    release_year = models.IntegerField(default=0)
    # original title
    original_title = models.TextField(blank=False, null=False)
    # localized title
    title = models.TextField(blank=False, null=False)
    # movie genres (e.g. "Comédie, Drame")
    genres = models.TextField(blank=True)
    # overwiew
    overview = models.TextField(blank=True)
    # TMDB id
    id_tmdb = models.IntegerField(null=True)

    # number of views
    viewed = models.IntegerField(default=0)
    # local rating
    rate = models.IntegerField(default=0)

    # status (present / moved / deleted ...)
    file_status = models.TextField(blank=False, null=False)

    def __str__(self):
        return u'{} - {} [{}]'.format(self.title, self.release_year, self.id)

    class Meta:
        ordering = ('title', )


class Team(models.Model):
    ''' keys for movie '''
    # movie reference
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='team')
    # job (Actor, Director, ...)
    job = models.TextField(blank=False, null=False)
    # person name
    name = models.TextField(blank=False, null=False)
    # extension: character for actor
    extension = models.TextField(null=True)

    def __str__(self):
        return u'{} - {} - {}'.format(self.movie.title, self.movie.release_year, self.name)

    class Meta:
        unique_together = ('job', 'name', 'movie')
        ordering = ('movie', 'name', )


class Poster(models.Model):
    ''' Movie Posters '''
    # movie reference
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='poster')
    # TMDB url
    url_tmdb = models.TextField(blank=False, null=False)
    # image
    poster = models.ImageField(upload_to='posters/', null=True)

    def __str__(self):
        return u'{} - {} - {}'.format(self.movie.title, self.movie.release_year, self.url_tmdb)

    class Meta:
        ordering = ('movie', )
