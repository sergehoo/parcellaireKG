import os
import sys
from datetime import timedelta
from pathlib import Path
from decouple import config

# SECRET_KEY = os.getenv('SECRET_KEY')

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = config('SECRET_KEY')
# Build paths inside the project like this: BASE_DIR / 'subdir'.
LOG_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "cache"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "urapweb",
    "laboipci.com",
    "www.laboipci.com",
    "192.168.1.4",
]

CSRF_TRUSTED_ORIGINS = [
    "https://laboipci.com",
    "https://www.laboipci.com",
    "https://localhost",
    "http://localhost",
    "http://192.168.1.4:9091",
    "http://192.168.1.4",
]

CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://localhost",
    "http://192.168.160.1:8000",
    "https://laboipci.com",
    "https://www.laboipci.com",
    "http://192.168.1.4:9091",
    "http://192.168.1.4",
]

# Si tu veux tout autoriser temporairement :
# CORS_ALLOW_ALL_ORIGINS = True
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

INSTALLED_APPS = [
    'dal',
    'dal_select2',
    # 'grappelli',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_unicorn',
    'django.contrib.sites',
    'axes',
    'allauth',
    'allauth.account',
    'rest_framework',
    'rest_framework.authtoken',
    'import_export',
    'mathfilters',
    'django_select2',
    'slick_reporting',
    'widget_tweaks',
    'sync',
    # 'autocomplete_light',
    'import_export_extensions',
    'tinymce',
    'simple_history',
    'django_prometheus',
    'num2words',
    'urap',
    'laboratory',
    'django_filters',
    'qr_code',
    'notifications',
    'weasyprint',
    "csp",
    'drf_spectacular',
    'corsheaders',

]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    "corsheaders.middleware.CorsMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'urapap.middleware.AuditRequestMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "csp.middleware.CSPMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    'simple_history.middleware.HistoryRequestMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

AUTH_USER_MODEL = "auth.User"
ROOT_URLCONF = 'urapap.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'urap.context_processors.analyses_processor',
                'urap.context_processors.labo_processor',
                'urap.context_processors.analysis_requests_nbrb_counts',
                'urap.context_processors.analysis_request_counts',
                'urap.context_processors.patient_reccord_counts',
                'urap.context_processors.invoice_reccord_counts',
                'urap.context_processors.paid_reccord_counts',
                'urap.context_processors.delivered_equipment_count',
                'urap.context_processors.check_administration_group',
                'urap.context_processors.check_daf_group',
                'urap.context_processors.check_pre_traitement_group',
                'urap.context_processors.check_publi_resultats_group',
                'urap.context_processors.check_support_group',
                'urap.context_processors.check_accueil_group',
                'urap.context_processors.check_facturation_group',
                'urap.context_processors.check_logistique_group',
                'urap.context_processors.check_prelevement_group',
                'urap.context_processors.check_laboratoire_group',
                'urap.context_processors.check_resultats_group',
                'urap.context_processors.get_sidebar_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'urapap.wsgi.application'

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Mon SIH National API",
    "DESCRIPTION": "API de gestion de laboratoire et SIH avec endpoints sécurisés JWT.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,  # Déjà exposé via /api/schema/

    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "PREPROCESSING_HOOKS": [],

    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
    },
}

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',

    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',

    # `allauth` specific authentication methods, such as login by email
    'allauth.account.auth_backends.AuthenticationBackend',

]


# django-csp v4+ (NOUVEAU FORMAT)
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),

        "script-src": (
            "'self'",
            "'unsafe-inline'",   # car tu as du JS inline (tailwind config, tinymce init, etc.)
            "'unsafe-eval'",     # ✅ nécessaire pour alpine cdn.min.js (x-data, etc.)
            "https://cdn.jsdelivr.net",
            "https://unpkg.com",
            "https://code.jquery.com",
            "https://cdnjs.cloudflare.com",
            "https://maps.googleapis.com",
            "https://maps.google.com",
            "https://cdn.tiny.cloud",
        ),

        "style-src": (
            "'self'",
            "'unsafe-inline'",
            "https://fonts.googleapis.com",
            "https://cdnjs.cloudflare.com",
        ),

        "font-src": (
            "'self'",
            "https://fonts.gstatic.com",
            "https://cdnjs.cloudflare.com",
            "data:",
        ),

        "img-src": (
            "'self'",
            "data:",
            "blob:",
            "https:",
        ),

        "connect-src": ("'self'", "https:", "wss:"),

        "frame-src": ("'self'", "https://www.google.com"),

        "object-src": ("'none'",),
    }
}

CONTENT_SECURITY_POLICY_REPORT_ONLY = False

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
ACCOUNT_ADAPTER = 'urap.account_adapter.NoNewUsersAccountAdapter'
# ACCOUNT_ADAPTER = 'urap.account_adapter.CustomAccountAdapter'

LOGOUT_REDIRECT_URL = 'account_login'
LOGIN_REDIRECT_URL = 'home'
# ACCOUNT_USER_IS_STAFF = True
# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'fr-FR'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

PHONENUMBER_DEFAULT_REGION = 'CI'
PHONENUMBER_DB_FORMAT = 'NATIONAL'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = Path(os.environ.get('STATIC_ROOT', '/app/static_root'))
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', '/app/media'))

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(MEDIA_ROOT)},
    },
}

# ROOT_URLCONF = "graphite.urls_prometheus_wrapper"
# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGES = [
    ('fr', 'Français'),
    ('en', 'English'),
]


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "TIMEOUT": 300,
    }
}


AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # en heures
AXES_CACHE = "default"
# Tell select2 which cache configuration to use:
# SELECT2_CACHE_BACKEND = "select2"

import os
# 1) Override explicite (systemd, env, etc.)
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=None)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=None)

if not CELERY_BROKER_URL:
    # 2) Fallback: build via REDIS_* (docker ou host)
    REDIS_HOST = config("REDIS_HOST", default="127.0.0.1")     # <= important
    REDIS_PORT = config("REDIS_PORT", default="6379")
    REDIS_PASSWORD = config("REDIS_PASSWORD", default="")

    if REDIS_PASSWORD:
        CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
        CELERY_RESULT_BACKEND = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
    else:
        CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
        CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# 3) si backend pas défini, on le colle au broker
if not CELERY_RESULT_BACKEND:
    CELERY_RESULT_BACKEND = CELERY_BROKER_URL

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Tell select2 which cache configuration to use:
# SELECT2_CACHE_BACKEND = "select2"

SITE_ID = 1
USE_L10N = True
USE_THOUSAND_SEPARATOR = True

IMPORT_EXPORT_USE_TRANSACTIONS = True

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')  # Numéro Twilio
TWILIO_MESSAGING_SERVICE_SID = os.environ.get('TWILIO_MESSAGING_SERVICE_SID')

CACHES = {
    "default": {
        "BACKEND": "django_prometheus.cache.backends.filebased.FileBasedCache",
        "LOCATION": str(CACHE_DIR),
    },
}
LOG_DIR = os.environ.get("LOG_DIR", str(BASE_DIR / "logs"))
ENABLE_FILE_LOGS = os.environ.get("ENABLE_FILE_LOGS", "False").lower() == "true"
if ENABLE_FILE_LOGS:
    os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
                     "datefmt": "%Y-%m-%d %H:%M:%S"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": sys.stdout,
        },
        **({
            "file": {
                "level": "INFO",
                "class": "logging.FileHandler",
                "formatter": "standard",
                "filename": os.path.join(LOG_DIR, "sms.log"),
            }
        } if ENABLE_FILE_LOGS else {})
    },
    "loggers": {
        "django": {"handlers": ["console"] + (["file"] if ENABLE_FILE_LOGS else []), "level": "INFO", "propagate": True},
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "": {"handlers": ["console"] + (["file"] if ENABLE_FILE_LOGS else []), "level": "DEBUG", "propagate": True},
    },
}

ORANGE_SMS_CLIENT_ID = config("ORANGE_SMS_CLIENT_ID")
ORANGE_SMS_CLIENT_SECRET = config("ORANGE_SMS_CLIENT_SECRET")
ORANGE_SMS_SENDER = config("ORANGE_SMS_SENDER")

TINYMCE_DEFAULT_CONFIG = {
    "height": 400,
    "width": "100%",
    "menubar": True,
    "branding": False,
    "statusbar": True,

    # 🔹 Plugins (image activé)
    "plugins": """
        advlist autolink lists link image charmap preview
        searchreplace visualblocks code fullscreen
        insertdatetime media table paste help wordcount
    """,

    # 🔹 Toolbar avec image
    "toolbar": """
        undo redo | blocks |
        bold italic underline |
        alignleft aligncenter alignright |
        bullist numlist |
        link image media table |
        removeformat | code fullscreen
    """,

    # 🔹 Style
    "content_style": "body { font-family:Inter, sans-serif; font-size:14px }",

    # 🔹 Images
    "image_title": True,
    "automatic_uploads": True,
    "images_upload_url": "/tinymce/upload/",
    "images_reuse_filename": True,

    # 🔹 Coller images depuis le presse-papier
    "paste_data_images": True,

    # 🔹 Sécurité / UX
    "relative_urls": False,
    "remove_script_host": False,
    "convert_urls": True,

    # 🔹 Langue
    "language": "fr_FR",
}


SYNC_SITE_CODE = config("SYNC_SITE_CODE", default=None)
SYNC_API_KEY = config("SYNC_API_KEY", default=None)

SYNC_SITE_ID = config("SYNC_SITE_ID", default=None)  # UUID str
SYNC_CLOUD_SITE_ID = config("SYNC_CLOUD_SITE_ID", default=None)  # UUID str

SYNC_CLOUD_PUSH_URL = config("SYNC_CLOUD_PUSH_URL", default=None)
SYNC_CLOUD_PULL_URL = config("SYNC_CLOUD_PULL_URL", default=None)

SYNC_PULL_LIMIT = config("SYNC_PULL_LIMIT", default=1000, cast=int)
SYNC_PUSH_LIMIT = config("SYNC_PUSH_LIMIT", default=500, cast=int)
SYNC_TIMEOUT = config("SYNC_TIMEOUT", default=30, cast=int)

# Optionnel mais recommandé
SYNC_CONFLICT_POLICY = config("SYNC_CONFLICT_POLICY", default="versioned")