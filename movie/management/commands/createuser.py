# -*- coding: utf-8 -*-
# pylint: disable=imported-auth-user
'''
Administration : create user without password

'''

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import IntegrityError



class Command(BaseCommand):
    '''
    class Command
    '''
    help = 'Create a user without password'

    def add_arguments(self, parser):
        parser.add_argument('-u', '--username', \
            help='Username to create')


    def handle(self, *args, **options):
        '''
        Handle command

            Warning : must return None or string, else Exception
        '''
        if not options['username']:
            return 'Provide a username with "-u" parameter'
        try:
            User.objects.create(username=options['username'])
        except IntegrityError:
            return 'This username already exists'
        return
