from .base import *

import os

DEBUG = True

# SECRET_KEY = 'django-insecure-xosdj%%2kmu2yvy5s2ut*r_#+zvp+_tm21h(en$*a0lla-q=4b'


DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

EPIDEMIE_API_REFRESH_URL = "https://veillesanitaire.com/epidemie/api/token/refresh/"
EPIDEMIE_API_TOKEN = os.getenv("EPIDEMIE_API_TOKEN", "VOTRE_TOKEN_JWT")
EPIDEMIE_API_REFRESH = os.getenv("EPIDEMIE_API_REFRESH",
                                 "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc1MDE1MjI3MywiaWF0IjoxNzQ5NTQ3NDczLCJqdGkiOiI4NGY1ZjczNzhhNGM0NTYxYWNkMGVhN2EwNjFmNWY3ZCIsInVzZXJfaWQiOjF9.6jsdHpDd0PF-FIfEFXPRD2ArQ3ncqJCiHTY4rt4Hybw")
EPIDEMIE_API_URL = "https://veillesanitaire.com/epidemie/api/signalement-epidemie/"

REDIS_HOST = os.getenv('REDIS_HOST', 'urapredis')  # nom du service dans docker-compose
# REDIS_PORT = os.getenv('REDIS_PORT', '6379')
# REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
#
# if REDIS_PASSWORD:
#     CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
#     CELERY_RESULT_BACKEND = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
# else:
#     CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
#     CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

MPI_API_KEY = os.environ.get('MPI_API_KEY', default='key')


REDIS_HOST = config('REDIS_HOST', 'urapredis')  # nom du service dans docker-compose
REDIS_PORT = config('REDIS_PORT', '6379')
REDIS_PASSWORD = config('REDIS_PASSWORD', '')

if REDIS_PASSWORD:
    CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
    CELERY_RESULT_BACKEND = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
else:
    CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"