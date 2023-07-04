from django.contrib import admin

# Register your models here.
from .models import Movie, MovieFile, Team, Poster, UserMovie, Person, Job


class MovieAdmin(admin.ModelAdmin):
    search_fields = ["id", "title"]


admin.site.register(Movie, MovieAdmin)


class MovieFileAdmin(admin.ModelAdmin):
    search_fields = ["movie__id", "movie__title", "file"]


admin.site.register(MovieFile, MovieFileAdmin)


class PosterAdmin(admin.ModelAdmin):
    search_fields = ["movie__id", "movie__title"]


admin.site.register(Poster, PosterAdmin)


class UserMovieAdmin(admin.ModelAdmin):
    search_fields = ["movie__id", "movie__title"]


admin.site.register(UserMovie, UserMovieAdmin)


class PersonAdmin(admin.ModelAdmin):
    search_fields = ["name"]


admin.site.register(Person, PersonAdmin)


class TeamAdmin(admin.ModelAdmin):
    search_fields = ["movie__id", "movie__title", "person__name"]


admin.site.register(Team, TeamAdmin)

admin.site.register(Job)
