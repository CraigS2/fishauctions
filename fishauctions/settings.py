"""
Django settings for fishauctions project.

Generated by 'django-admin startproject' using Django 3.1.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from pathlib import Path
import sys
import os
try:
    from . import customsettings
except:
    pass
import datetime

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

ADMINS = [('Admin', os.environ['ADMIN_EMAIL'])]


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
if os.environ['DEBUG'] == "True":
    DEBUG = True
else:
    DEBUG = False

ALLOWED_HOSTS = ['localhost', '127.0.0.1', os.environ['ALLOWED_HOST_1'], os.environ['ALLOWED_HOST_2'], os.environ['ALLOWED_HOST_3']]
CSRF_TRUSTED_ORIGINS = ['http://localhost', 'http://127.0.0.1', 'https://' + os.environ['ALLOWED_HOST_1'], 'https://' + os.environ['ALLOWED_HOST_2'], 'https://' + os.environ['ALLOWED_HOST_3']]

# Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [("redis://:" + os.environ['REDIS_PASS'] + "@127.0.0.1:6379/0")],
            #"hosts": [('127.0.0.1', 6379)],
            "capacity": 2000,  # default 100
            "expiry": 20,  # default 60
        },
    },
}

# Application definition
INSTALLED_APPS = [
    'auctions',
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    #'site_settings',
    'crispy_forms',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'django_filters',
    'bootstrap_datepicker_plus',
    'el_pagination',
    'easy_thumbnails',
    "post_office",
    'location_field',
    'channels',
    #'debug_toolbar', # having this enabled is handy for sql queries but silences errors in channels
    'markdownfield',
    'qr_code',
    'django_tables2',
    'django_htmx',
]
ASGI_APPLICATION = "fishauctions.asgi.application"
MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',    
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'fishauctions.urls'

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
                'auctions.context_processors.google_analytics',
                'auctions.context_processors.theme',
                'auctions.context_processors.add_location',
                'auctions.context_processors.dismissed_cookies_tos',
                'auctions.context_processors.add_tz',
            ],
        },
    },
]

WSGI_APPLICATION = 'fishauctions.wsgi.application'

LANGUAGE_CODE = 'en-us'

TIME_ZONE = os.environ['TIME_ZONE']

USE_I18N = False

USE_L10N = False

USE_TZ = True

DATETIME_FORMAT = 'M j, Y P e'

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

SITE_ID = 1
SITE_DOMAIN = os.environ['SITE_DOMAIN']


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.environ['STATIC_ROOT']

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',

    # `allauth` specific authentication methods, such as login by e-mail
    'allauth.account.auth_backends.AuthenticationBackend',
]


# Use sqlite for testing
if 'test' in sys.argv:
#if True: # for migrations
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
       
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': os.environ['DATABASE_ENGINE'],
            'NAME': os.environ['DATABASE_NAME'],
            'USER': os.environ['DATABASE_USER'],
            'PASSWORD': os.environ['DATABASE_PASSWORD'],
            'HOST': os.environ['DATABASE_HOST'],
            'PORT': os.environ['DATABASE_PORT'],
            'OPTIONS': {'charset': 'utf8mb4'},
        }
    }

# Base URL to use when referring to full URLs within the Wagtail admin backend -
# e.g. in notification emails. Don't include '/admin' or a trailing slash
BASE_URL = os.environ['BASE_URL']

ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = True
LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/login/"
ACCOUNT_FORMS = {
'signup': 'auctions.forms.CustomSignupForm',
}
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "auction.fish - "
ACCOUNT_DEFAULT_HTTP_PROTOCOL='https'

SESSION_COOKIE_AGE = 1209600*100

EMAIL_BACKEND = 'post_office.EmailBackend'
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # console
#EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

POST_OFFICE = {
    'MAX_RETRIES': 4,
    'RETRY_INTERVAL': datetime.timedelta(minutes=15),  # Schedule to be retried 15 minutes later
}

if os.environ['EMAIL_USE_TLS'] == "True":
    EMAIL_USE_TLS = True
else:
    EMAIL_USE_TLS = False
EMAIL_HOST = os.environ['EMAIL_HOST']
EMAIL_PORT = os.environ['EMAIL_PORT']
EMAIL_HOST_USER = os.environ['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = os.environ['EMAIL_HOST_PASSWORD']
DEFAULT_FROM_EMAIL = os.environ['DEFAULT_FROM_EMAIL']
EMAIL_SUBJECT_PREFIX = ""

CRISPY_TEMPLATE_PACK = 'bootstrap4'
CRISPY_FAIL_SILENTLY = False
BOOTSTRAP4 = {
    'include_jquery': True,
}

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

EL_PAGINATION_PER_PAGE = 20
SITE_URL = os.environ['SITE_URL']

THUMBNAIL_ALIASES = {
    '': {
        'ad': {'size': (250, 150), 'crop': False},
        'lot_list': {'size': (250, 150), 'crop': "smart"},
        'lot_full': {'size': (600, 600), 'crop': False},
    },
}

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'offline',
        }
    }
}

SOCIALACCOUNT_LOGIN_ON_GET=True

INTERNAL_IPS = [
#    '127.0.0.1', # uncomment this to enable the django debug toolbar
]

VIEW_WEIGHT = 1
BID_WEIGHT = 10
WEIGHT_AGAINST_TOP_INTEREST = 20

GOOGLE_MEASUREMENT_ID=os.environ['GOOGLE_MEASUREMENT_ID']
GOOGLE_TAG_ID = os.environ['GOOGLE_TAG_ID']
GOOGLE_ADSENSE_ID = os.environ['GOOGLE_ADSENSE_ID']

LOCATION_FIELD_PATH = STATIC_URL + 'location_field'

LOCATION_FIELD = {
    'map.provider': 'google',
    'map.zoom': 13,

    'search.provider': 'google',
    'search.suffix': '',

    # Google
    'provider.google.api': '//maps.google.com/maps/api/js?sensor=false',
    'provider.google.api_key': os.environ['GOOGLE_MAPS_API_KEY'],
    'provider.google.api_libraries': '',
    'provider.google.map.type': 'ROADMAP',

    # misc
    'resources.root_path': LOCATION_FIELD_PATH,
    'resources.media': {
        'js': (
            LOCATION_FIELD_PATH + '/js/form.js',
        ),
    },
}

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

SEND_WELCOME_EMAIL = True # when a user adds an unverified email address to their auction, send an email about the site

DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000