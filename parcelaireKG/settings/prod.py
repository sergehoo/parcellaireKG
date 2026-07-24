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

# ---------------------------------------------------------------------
# Celery / Redis — base.py code en dur `127.0.0.1` (dev sans Docker).
# En prod, le broker/back-end DOIVENT être lus depuis l'env, sinon le
# worker et beat (détection d'alertes planifiée, e-mails de rapport)
# ne joignent jamais le conteneur Redis.
# ---------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# ---------------------------------------------------------------------
# Cache Django sur Redis. Sans cache partagé, le rate-limit de login
# (allauth) et les throttles DRF vivent dans un LocMemCache PAR PROCESSUS :
# avec plusieurs workers gunicorn, les compteurs ne sont pas globaux et les
# limites sont diluées. DB 1 pour ne pas collisionner avec le broker (DB 0).
# ---------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("CACHE_URL", "redis://redis:6379/1"),
    }
}

# ---------------------------------------------------------------------
# E-mail (rapports exécutifs, notifications) — piloté par l'environnement.
# Sans EMAIL_HOST configuré, aucun envoi n'est tenté (les rapports restent
# consultables/téléchargeables dans l'app).
# ---------------------------------------------------------------------
_bool = lambda name, default: os.environ.get(name, default).lower() in {"1", "true", "yes", "on"}
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.dummy.EmailBackend",
)
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _bool("EMAIL_USE_TLS", "True")
EMAIL_USE_SSL = _bool("EMAIL_USE_SSL", "False")
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "20"))
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "KAYDAN Parcellaire <no-reply@datarium-dev.com>"
)
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)