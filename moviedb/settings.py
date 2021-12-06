"""
Django settings for moviedb project.

Generated by 'django-admin startproject' using Django 3.0.8.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""

import os
import platform

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'r8c8cz*!3ein9xxa*f5$+o26#&j0k@x)(-k=43-nll=x9p!40$'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

#
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '192.168.1.23', '192.168.1.36', 'diskstation']


# Application definition

INSTALLED_APPS = [
    'movie.apps.MovieConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'global_login_required.GlobalLoginRequiredMiddleware',      # package django-glrm
]

ROOT_URLCONF = 'moviedb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'moviedb.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'movies.db'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'fr'

TIME_ZONE = 'Europe/Paris'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# locale specification
if platform.system() == 'Linux':
    LOCALE = 'fr_FR.utf8'
else:
    # (windows)
    LOCALE = 'fr'



# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'moviedb/static/')
]

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'


# Media url, path
#
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'


#
# Config Django Global Login Required Middleware (django-glrm)
#
PUBLIC_PATHS = [
    '^%s.*' % MEDIA_URL,# allow public access to any media on your application
    r'^/accounts/.*',   # allow public access to all django-allauth views
]



#
#  Specific settings for this application outside django
#

LOGIN_REDIRECT_URL = 'home'

# Do not use password for login standard users (no admin nor staff)
USE_NO_USER_PASSWORD = True

if USE_NO_USER_PASSWORD:
    # specific athentification backend for login without password
    AUTHENTICATION_BACKENDS = [
        'movie.authentication.NopassAuthBackend'
    ]

# no session expiration before 100 years !
SESSION_COOKIE_AGE = 3600 * 24 * 365 * 100

# number of movies per html page
MOVIES_PER_PAGE = 25

# number in the top pages (top actors, top composers, ...)
NUM_TOP = 100

# string for all volumes
ALL_VOLUMES = 'All Volumes'

# Populate volumes labels in list box, declare MediaServers
VOLUMES = [
    # for each volume :
    #   (volume_label, volume_alias, volume_type, (DLNA_device, DLNA_movie_path))
    (ALL_VOLUMES, ALL_VOLUMES, '', (None, None)),
    ('DiskStation', 'Synology', 'network', ('http://192.168.1.23:50001/desc/device.xml', 'Vidéo/Films')),
    ('Expansion', 'Expansion', 'harddisk', (None, None)),
]
DLNA_MEDIASERVERS = {vol[0].lower():vol[3] for vol in VOLUMES}

DLNA_RENDERERS = [
    # for each device :
    #   (DLNA Device location, a smart name)
    ('http://192.168.1.14:42300/description.xml', 'Orange Decoder'),
    ('http://192.168.1.15:52235/dmr/SamsungMRDesc.xml', 'TV Samsung'),
    # specific name for view on computer :
    ('browser', 'View in Browser'),
    ('vlc', 'View in VLC'),
]

# default hidden fields for movies table (in 'poster, 'screen', 'size', 'file', 'rate', 'format)
HIDDEN_FIELDS = ['size', 'file', 'format']

# Max number of posters to import from TMDB
MAX_POSTERS = 4
