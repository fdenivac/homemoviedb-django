# Generated by Django 4.1.7 on 2023-05-31 14:35

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("movie", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Job",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name="Person",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.TextField()),
                ("id_tmdb", models.IntegerField(unique=True)),
                ("url_img", models.TextField(blank=True, null=True)),
            ],
            options={
                "ordering": ("name",),
            },
        ),
        migrations.AlterModelOptions(
            name="team",
            options={"ordering": ("movie__title", "person__name")},
        ),
        migrations.RemoveField(
            model_name="movie",
            name="bitrate",
        ),
        migrations.RemoveField(
            model_name="movie",
            name="duration",
        ),
        migrations.RemoveField(
            model_name="movie",
            name="file",
        ),
        migrations.RemoveField(
            model_name="movie",
            name="file_size",
        ),
        migrations.RemoveField(
            model_name="movie",
            name="file_status",
        ),
        migrations.RemoveField(
            model_name="movie",
            name="movie_format",
        ),
        migrations.RemoveField(
            model_name="movie",
            name="rate",
        ),
        migrations.RemoveField(
            model_name="movie",
            name="screen_size",
        ),
        migrations.RemoveField(
            model_name="movie",
            name="viewed",
        ),
        migrations.AddField(
            model_name="movie",
            name="countries",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="movie",
            name="date_added",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="movie",
            name="language",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="movie",
            name="title_ai",
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name="team",
            name="cast_order",
            field=models.IntegerField(null=True),
        ),
        migrations.CreateModel(
            name="MovieFile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("file", models.TextField(unique=True)),
                ("file_size", models.IntegerField(null=True)),
                ("movie_format", models.TextField(null=True)),
                ("bitrate", models.IntegerField(null=True)),
                ("screen_size", models.TextField(null=True)),
                ("duration", models.IntegerField(default=0)),
                ("file_status", models.TextField()),
                ("date_added", models.DateTimeField(null=True)),
                (
                    "movie",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="movie.movie",
                    ),
                ),
            ],
            options={
                "ordering": ("file",),
            },
        ),
        migrations.AlterUniqueTogether(
            name="team",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="movie",
            name="files",
            field=models.ManyToManyField(related_name="+", to="movie.moviefile"),
        ),
        migrations.AddField(
            model_name="team",
            name="person",
            field=models.ForeignKey(
                default=0,
                on_delete=django.db.models.deletion.CASCADE,
                to="movie.person",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="team",
            name="job",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="movie.job"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="team",
            unique_together={("job", "person", "movie")},
        ),
        migrations.CreateModel(
            name="UserMovie",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("viewed", models.IntegerField(default=0)),
                ("rate", models.IntegerField(default=0)),
                (
                    "movie",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="movie.movie"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("user", "movie")},
            },
        ),
        migrations.RemoveField(
            model_name="team",
            name="name",
        ),
    ]
