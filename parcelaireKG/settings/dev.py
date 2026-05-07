"""
Configuration de développement.
"""
import os
import sys
from pathlib import Path

from decouple import config

from .base import *  # noqa: F401,F403

# En dev on accepte tous les hosts pour faciliter ngrok / réseau local.
ALLOWED_HOSTS = ['*']

# Chemins GDAL/GEOS : conditionnels selon la plateforme. Permettre à l'env
# de surcharger en priorité, sinon n'imposer un chemin que sur macOS Homebrew.
_GDAL_FROM_ENV = os.environ.get("GDAL_LIBRARY_PATH")
_GEOS_FROM_ENV = os.environ.get("GEOS_LIBRARY_PATH")

if _GDAL_FROM_ENV:
    GDAL_LIBRARY_PATH = _GDAL_FROM_ENV
elif sys.platform == "darwin" and Path("/opt/homebrew/lib/libgdal.dylib").exists():
    GDAL_LIBRARY_PATH = "/opt/homebrew/lib/libgdal.dylib"

if _GEOS_FROM_ENV:
    GEOS_LIBRARY_PATH = _GEOS_FROM_ENV
elif sys.platform == "darwin" and Path("/opt/homebrew/lib/libgeos_c.dylib").exists():
    GEOS_LIBRARY_PATH = "/opt/homebrew/lib/libgeos_c.dylib"

# DEBUG est activé en dev par défaut, mais l'env peut le forcer à False.
DEBUG = os.environ.get("DEBUG", "True").lower() in {"1", "true", "yes", "on"}


DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5433'),
    }
}
MPI_API_KEY = os.environ.get('MPI_API_KEY', default='key')
#

REDIS_HOST = 'localhost'
# CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
# CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'

# Si tu veux pouvoir surcharger directement:
# export CELERY_BROKER_URL=redis://...
# export CELERY_RESULT_BACKEND=redis://...
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "").strip() or None
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "").strip() or None

REDIS_PORT = config("REDIS_PORT", default="6379")
REDIS_PASSWORD = config("REDIS_PASSWORD", default="").strip()

# Détection docker: /.dockerenv existe dans les containers Docker
IN_DOCKER = os.path.exists("/.dockerenv")

# Host par défaut selon l’environnement
# - En docker-compose: service redis = urapredis (comme tu as)
# - Hors docker: redis local = 127.0.0.1
DEFAULT_REDIS_HOST = "urapredis" if IN_DOCKER else "127.0.0.1"
REDIS_HOST = config("REDIS_HOST", default=DEFAULT_REDIS_HOST).strip()

def _redis_url(db="0"):
    if REDIS_PASSWORD:
        return f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{db}"
    return f"redis://{REDIS_HOST}:{REDIS_PORT}/{db}"

# Si pas fourni par env, on construit
if not CELERY_BROKER_URL:
    CELERY_BROKER_URL = _redis_url("0")
if not CELERY_RESULT_BACKEND:
    CELERY_RESULT_BACKEND = _redis_url("0")

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Recommandé (supprime le warning Celery 6+)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

STATIC_URL = '/static/'
STATIC_ROOT = Path(os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles'))
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
# gdal_translate \
#   Ortho_BR1.tif \
#   Ortho_BR1_web.tif \
#   -b 1 -b 2 -b 3 \
#   -ot Byte \
#   -co TILED=YES \
#   -co COMPRESS=JPEG \
#   -co PHOTOMETRIC=YCBCR \
#   -co BIGTIFF=YES\
#   -co resolution =highest