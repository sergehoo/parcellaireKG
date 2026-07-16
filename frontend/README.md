# Frontend React — parcelaireKG (Carte & Orthophotos)

SPA React (Vite, JavaScript) qui devient l'interface principale, servie
par Django sur **`/app/`** (login requis). Elle remplace progressivement
les templates Django ; à ce stade elle couvre la **cartographie** et la
**gestion des orthophotos**. Le CRUD (projets, ventes, paiements…) reste
sur Django et est atteignable via « Ouvrir la fiche » / le tableau de bord.

## Cartographie (`#/carte`, vue d'accueil)

Carte Leaflet consommant `RealEstateMapAPIView` (`/api/map/assets/`) —
fusionne carte générale et commerciale, le masquage financier/patient
étant appliqué côté serveur selon les permissions (`user_rights`).

- **Parcelles / lots** en polygones GeoJSON colorés par statut (couleur et
  opacité fournies par l'API) ; clic → panneau latéral de détail.
- **Filtres** : projet, programme (dépendant du projet), statut
  (Tous / Disponibles / Réservés / Vendus / En construction), tag,
  recherche — synchronisés dans l'URL (hash query).
- **Couche orthophoto** superposable par programme, avec choix de version
  (timeline) et curseur d'opacité — réutilise les tuiles du pipeline GDAL.
- **Synthèse** (Actifs, Réservés/Vendus, CA potentiel) + légende.
- **Panneau détail** : chiffres clés, détails, métriques, unités (bâtiments
  multi-lots), tags, et lien « Ouvrir la fiche complète » vers Django.

> Les routes Django `/map/` et `/map_commercial` **redirigent** vers
> `#/carte`. Les templates Leaflet historiques restent en repli sous
> `/map/legacy/` et `/map_commercial/legacy/`. La vue 3D (`map_3d.html`)
> n'est pas encore portée — chantier séparé.
>
> **Perf** : la carte charge tout l'ensemble filtré au zoom 15 (géométrie
> incluse, images/timeline exclues car ≥16 = une requête par parcelle,
> trop coûteux en masse). Les photos/historique s'affichent dans la fiche
> Django. Pas de découpage par bbox : le jeu de données tient en mémoire
> et les parcelles d'un programme peuvent être très éloignées.

## Orthophotos (`#/orthophotos`)

- **Liste** : filtres projet / programme / année / mois / statut, recherche,
  pagination, rafraîchissement automatique des traitements en cours.
- **Upload** (`#/orthophotos/upload`) : drag & drop d'un GeoTIFF, envoi
  **multipart direct vers MinIO** via presigned URLs (3 parts en parallèle,
  retries, annulation, gestion du conflit programme/période).
- **Détail** : progression du pipeline GDAL en temps réel (polling 3 s),
  timeline des logs, aperçu Leaflet des tuiles, actions (relancer, définir
  courante, supprimer les tuiles, export logs) — masquées par permission.

## Architecture

```
frontend/src
├── api/
│   ├── client.js        # fetch + session Django + CSRF (401→login, 403→erreur)
│   ├── map.js           # GET /api/map/assets/
│   └── orthophotos.js   # endpoints orthophotos (API DRF + upload)
├── lib/
│   ├── uploadMultipart.js  # découpage + PUT presigned + collecte ETags
│   └── format.js
├── components/
│   ├── map/             # MapCanvas (Leaflet), MapFilters, MapLegend,
│   │                    # FeatureDetailPanel
│   └── …               # Layout, StatusBadge, ProgressBar, LogTimeline,
│                        # FileDropzone, TileMapPreview, Toasts…
└── pages/
    ├── MapView.jsx      # carte (vue d'accueil)
    ├── OrthophotoList.jsx / OrthophotoUpload.jsx / OrthophotoDetail.jsx
```

Côté Django, l'API consommée est :

| Endpoint | Rôle |
|---|---|
| `GET /api/orthophotos/` | liste paginée + filtres |
| `GET /api/orthophotos/<id>/` | détail + 200 derniers logs |
| `POST /api/orthophotos/<id>/retry\|set-current\|delete-tiles/` | actions |
| `GET /api/orthophotos/reference-data/` | projets, programmes, statuts… |
| `GET /api/orthophotos/csrf/` | pose le cookie csrftoken |
| `POST /orthophotos/upload/init\|complete\|abort/` | multipart S3 (existant) |
| `GET /orthophotos/<id>/status/` | polling léger (existant) |

L'authentification est la **session Django** (mêmes cookies que le site) ;
si la session expire, le SPA redirige vers `/accounts/login/?next=…`.

## Développement

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Le serveur Vite proxifie `/api`, `/orthophotos`, `/media` et `/accounts`
vers Django (`http://localhost:8000` par défaut, surchargable :
`DJANGO_URL=http://localhost:8030 npm run dev`).

Connectez-vous d'abord au Django proxifié (http://localhost:5173/accounts/login/)
pour obtenir le cookie de session. L'app est servie en dev sur
http://localhost:5173/static/orthophotos-app/ (même chemin que la prod).

### 100 % local sans Docker (macOS)

Le poste dispose déjà de PostGIS (PostgreSQL EDB sur le port 5433, cf.
`.env`) et des libs Homebrew (GDAL, GEOS, glib pour WeasyPrint) :

```bash
# Django — DYLD_FALLBACK_LIBRARY_PATH est indispensable pour WeasyPrint
# (et doit être posé SANS passer par nohup/env, que SIP purge des DYLD_*).
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib ./venv/bin/python manage.py runserver 8030

# React (autre terminal) — Node ≥ 18 requis (nvm use 22)
cd frontend && DJANGO_URL=http://localhost:8030 npm run dev
```

Dans ce mode, la liste / le détail / la carte fonctionnent sur la base
locale ; **l'upload S3 et le pipeline GDAL nécessitent MinIO + Redis +
worker Celery** (docker compose, ou services locaux équivalents).

> **CORS MinIO** : le PUT des parts va directement du navigateur vers
> MinIO. En dev, l'origine `http://localhost:5173` doit être autorisée
> dans la config CORS du bucket (cf. `_allowed_origins_for_cors()` dans
> `parcelaire/services/storage.py`) avec `ExposeHeaders: ETag`.

## Build production

```bash
cd frontend
npm run build        # écrit dans static/orthophotos-app/ (noms fixes, sans hash)
```

Puis côté Django : `collectstatic` (le cache-busting est géré par le
manifest WhiteNoise). L'app est servie sur **`/app/`** (route `react_app`,
login requis) via `templates/parcelaire/orthophoto/react_app.html`.
`/app/orthophotos/` redirige vers `#/orthophotos` (rétrocompat).

Le routage interne utilise `HashRouter` (`/app/#/carte`,
`/app/#/orthophotos/12`…) : aucune réécriture d'URL serveur n'est
nécessaire.
