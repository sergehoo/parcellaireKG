# =====================================================================
# Stage 1 — Build du CSS Tailwind
# =====================================================================
# On compile static/src/tailwind.css → static/css/tailwind.css avec la
# CLI Tailwind, dans un container Node léger. Ainsi l'image finale Python
# n'a pas besoin de Node ni de node_modules.
# =====================================================================
FROM node:20-alpine AS frontend
WORKDIR /app

# Cache npm (lock-file optionnel)
COPY package.json ./
COPY package-lock.json* ./

RUN if [ -f package-lock.json ]; then \
        npm ci --no-audit --no-fund ; \
    else \
        npm install --no-audit --no-fund ; \
    fi

# Tout ce qui doit être scanné par Tailwind (templates + sources Python
# qui peuvent contenir des classes CSS dans les widgets/forms).
COPY tailwind.config.js ./
COPY static/src ./static/src
COPY templates ./templates
COPY parcelaire ./parcelaire
COPY ai_construction ./ai_construction

# Compilation minifiée
RUN npx tailwindcss -i ./static/src/tailwind.css -o ./static/css/tailwind.css --minify


# =====================================================================
# Stage 2 — Image applicative Python / Django
# =====================================================================
FROM python:3.11-slim AS app

LABEL authors="ogahserge"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Empêche `manage.py` d'échouer pendant `collectstatic` à cause des secrets
# manquants au moment du build (DB, etc.) — on fournit des dummies.
ENV DJANGO_SETTINGS_MODULE=parcelaireKG.settings
ENV SECRET_KEY=build-time-dummy-key
ENV DEBUG=False
ENV ALLOWED_HOSTS=*

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        libpq-dev \
        # --- GDAL / GIS ---
        gdal-bin \
        libgdal-dev \
        # `python3-gdal` fournit notamment `gdal2tiles.py` utilisé par le
        # pipeline orthophoto (sinon : "command not found").
        python3-gdal \
        binutils \
        libproj-dev \
        proj-data \
        proj-bin \
        libgeos-dev \
        # --- WeasyPrint ---
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libcairo2-dev \
        libffi-dev \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Code applicatif
COPY . /app/

# Récupère le CSS Tailwind compilé du stage frontend.
COPY --from=frontend /app/static/css/tailwind.css /app/static/css/tailwind.css

# `collectstatic` matérialise STATIC_ROOT (par défaut /app/staticfiles).
# Sans cette étape, en DEBUG=False Django ne sert plus aucun fichier
# statique → CSS Tailwind 404 → page sans style.
#
# Dummies DB : settings/dev.py exige DB_NAME/DB_USER/DB_PASSWORD via
# decouple. Le `.env` est (volontairement) exclu de l'image par
# .dockerignore — les vraies valeurs arrivent au runtime via compose.
# collectstatic n'ouvre aucune connexion DB, les dummies suffisent.
RUN DB_NAME=build-dummy DB_USER=build-dummy DB_PASSWORD=build-dummy \
    DB_HOST=localhost DB_PORT=5432 \
    python manage.py collectstatic --noinput --clear

EXPOSE 8000
