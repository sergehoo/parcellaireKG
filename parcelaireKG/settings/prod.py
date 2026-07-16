"""
Configuration de production.

Tout secret/identifiant doit provenir de l'environnement.
Voir docker-compose.yml et le `.env` (à NE PAS committer).
"""
import os

from .base import *  # noqa: F401,F403

# SECURITY: jamais True en production. Piloté par l'env (même logique
# que base.py) avec False par défaut — un `DEBUG = True` codé en dur
# exposait les stack traces et la config au public en cas d'erreur.
DEBUG = os.environ.get("DEBUG", "False").lower() in {"1", "true", "yes", "on"}

# Les secrets viennent toujours de l'env (pas de fallback ici).
SECRET_KEY = os.environ["SECRET_KEY"]

# ALLOWED_HOSTS et CSRF_TRUSTED_ORIGINS sont déjà lus depuis l'env dans base.py.

# ---------------------------------------------------------------------
# Renforcement HTTPS / cookies
# ---------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # le front lit le token CSRF pour les fetch POST
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ.get('DB_HOST', 'parcelairedb'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

STATIC_URL = '/static/'
STATIC_ROOT = Path(os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles'))
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []