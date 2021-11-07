from django.contrib import admin

# Register your models here.
from .models import Movie, Team, Poster

admin.site.register(Movie)
admin.site.register(Team)
admin.site.register(Poster)
