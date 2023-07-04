# -*- coding: utf-8 -*-
# pylint: disable=imported-auth-user
"""

Around data migration

"""


from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from movie.models import Movie, MovieFile


class Command(BaseCommand):
    """
    class Command
    """

    help = "Import/Export Movie datas after db migrate 0026 "

    def add_arguments(self, parser):
        parser.add_argument("-f", "--file", default="export.txt", help="File output")
        parser.add_argument(
            "action",
            choices=["export", "import"],
            default="export",
            help="action to do",
        )

    def handle(self, *args, **options):
        """
        Handle command

            Warning : must return None or string, else Exception
        """

        action = options["action"]

        if action == "export":
            fout = open(
                options["file"],
                "w",
                encoding="utf8",
            )
            for movie in Movie.objects.all():
                sout = "{}||{}||{}||{}||{}||{}||{}||{}||\n".format(
                    movie.id_tmdb,
                    movie.file,
                    movie.file_size,
                    movie.movie_format,
                    movie.bitrate,
                    movie.duration,
                    movie.file_status,
                    movie.screen_size,
                )
                fout.write(sout)
            fout.close()

        if action == "import":
            # import file has been created before migration 0026
            with open(
                options["file"],
                "r",
                encoding="utf8",
                newline="\r\n",
            ) as fin:
                for line in fin:
                    datas = line
                    if not datas:
                        continue
                    # print('"%s"' % datas)
                    (
                        id_tmdb,
                        fname,
                        file_size,
                        movie_format,
                        bitrate,
                        duration,
                        file_status,
                        screen_size,
                        _,
                    ) = datas.split("||")
                    # if int(id_tmdb) == 59:
                    #     print('LA: "%s"' % datas)

                    try:
                        # movie_desc = Movie.objects.get(id_tmdb=id_tmdb)
                        movie_desc = Movie.objects.filter(id_tmdb=id_tmdb)[0]
                    except ObjectDoesNotExist:
                        print("FAILED")
                        continue

                    try:
                        movie = MovieFile.objects.get(file__iexact=fname)
                    except ObjectDoesNotExist:
                        movie = MovieFile(file=fname)
                    movie.file_status = file_status
                    movie.file_size = file_size
                    movie.movie_format = movie_format
                    movie.bitrate = bitrate
                    movie.screen_size = screen_size
                    movie.duration = duration
                    movie.date_added = movie_desc.date_added
                    movie.movie = movie_desc
                    movie.save()
            fin.close()

        return
