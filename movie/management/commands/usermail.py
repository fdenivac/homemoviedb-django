# -*- coding: utf-8 -*-
"""
Administration : send mails to users for new movies

"""
import sys
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, EmailMultiAlternatives
from django.utils.timezone import make_aware
from django.conf import settings
from django.template.loader import render_to_string

from movie.models import MovieFile


class Command(BaseCommand):
    """
    class Command
    """

    help = "Send mail to all users"

    def add_arguments(self, parser):
        parser.add_argument(
            "-d", "--days", type=int, default=7, help="New movies since DAYS"
        )
        parser.add_argument(
            "-u",
            "--users",
            help="Send mails only to these users, comma separated. Username are case sensitive",
        )
        parser.add_argument(
            "-T",
            "--test",
            choices=["print", "mail"],
            help='Test mode : "print" or "mail" to superusers',
        )
        parser.add_argument(
            "-H", "--html", action="store_true", help="Send mail in html"
        )
        parser.add_argument(
            "-L",
            "--site-location",
            help="site address (e.g. http://mymoviecatalog)",
            default="http://fdevivac.ici",
        )

    def handle(self, *args, **options):
        """
        Handle command

            Warning : must return None or string, else Exception
        """

        # build user list
        filter_users = options["users"].split(",") if options["users"] else []
        if filter_users:
            # check user
            valid_users = [user.username for user in get_user_model().objects.all()]
            for user in filter_users:
                if user not in valid_users:
                    print('"{}" is not a valid user'.format(user), file=sys.stderr)
        recipients = []
        for user in get_user_model().objects.all():
            if filter_users and user.username not in filter_users:
                continue
            if not user.email:
                print('User "{}" has no email'.format(user), file=sys.stderr)
                continue
            if options["test"] and not user.is_superuser:
                continue
            recipients.append((user.username, user.email))
        if not recipients:
            print("Warning : none recipients", file=sys.stderr)
            return

        # list of new movies for the week
        date_from = datetime.now() - timedelta(days=options["days"])
        movies = MovieFile.objects.filter(
            file_status="OK",
            file__istartswith=settings.MAIN_VOLUME[0],
            date_added__gte=make_aware(date_from),
        ).order_by("movie__title")

        if not movies:
            print("No new movies", file=sys.stderr)
            return

        # send mails
        subject = "New movies available this week"
        for user, email in recipients:
            context = {
                "mainvolume": settings.MAIN_VOLUME,
                "siteloc": options["site_location"],
                "user": user.capitalize(),
                "days": options["days"],
                "movies": movies,
            }

            message = render_to_string("movie/mail_newmovies.txt", context)
            if options["test"] == "print":
                print(">>>>\n", message, "\n<<<<")
                return

            if options["html"]:
                html_content = render_to_string("movie/mail_newmovies.html", context)
                mail = EmailMultiAlternatives(
                    subject, message, settings.EMAIL_HOST_USER, [email]
                )
                mail.attach_alternative(html_content, "text/html")
                mail.send()
            else:
                send_mail(subject, message, settings.EMAIL_HOST_USER, [email])

        return
