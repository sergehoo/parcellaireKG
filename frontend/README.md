# Frontend React — parcelaireKG

SPA React (Vite, JavaScript), interface publique principale de l'application.
En production, son build est servi à la racine par un conteneur Nginx dédié.
Django reste privé sur le réseau Docker et fournit les API, l'authentification,
l'administration et les médias.

Le frontend couvre la cartographie, les tableaux de bord, les notifications,
les orthophotos et les écrans de consultation CRUD. Les projets, programmes et
clients disposent également des formulaires React de création/modification.

## Cartographie premium (`#/carte`, vue d'accueil)

Carte Leaflet **premium** (glassmorphism + Framer Motion) consommant
`RealEstateMapAPIView` (`/api/map/assets/`) — fusionne carte générale et
commerciale, masquage financier/patient appliqué côté serveur (`user_rights`).

Composants (`src/components/map/`) :
- **MapToolbar** (verre dépoli) : marque KAYDAN, **recherche intelligente**
  à suggestions instantanées (biens/programmes/projets + commandes de statut
  qui pilotent les filtres), filtres projet/programme/statut.
- **ControlRail** : rail flottant animé — zoom ±, vue initiale, ma position
  (géoloc), plein écran, **mesure distance/surface** (Turf.js), mini-carte
  (`leaflet-minimap`), impression/PDF.
- **ViewSelector** : **fonds de carte** Standard (OSM) / Clair·Sombre (CARTO) /
  Satellite (Esri) / Relief (OpenTopoMap) ; **calque parcelles** Polygones /
  Noms lots / Repères (clustering `leaflet.markercluster`, pastilles animées) /
  Aucun ; bascule **Orthophoto**.
- **FeatureDetailPanel** : panneau animé (spring) — chiffres clés, détails,
  métriques, unités, tags, lien vers la fiche React complète.
- **MapLegend** : synthèse (Actifs/Réservés-Vendus/CA) + légende adaptative
  (priorité travaux en mode Noms lots, statut sinon).

> **Fonds externes & CSP** : les hôtes Esri (`server.arcgisonline.com`) et
> OpenTopoMap (`*.tile.opentopomap.org`) sont ajoutés à `img-src` dans la CSP
> (`settings/base.py`). Le changement de fond ne retire l'ancien qu'une fois
> le nouveau chargé : si un fournisseur ne répond pas, la carte garde le fond
> courant (jamais de carte vide). *Note : le navigateur de prévisualisation
> interne ne charge de façon fiable que les tuiles OSM ; satellite/relief/
> sombre se valident dans un vrai navigateur.*
>
> **Différé** (nécessite données/services externes non présents, non simulés) :
> vue 3D immersive (Cesium/MapLibre/deck.gl), météo temps réel, couche
> chantier live (grues/ouvriers/VRD/stocks), assistant IA type LLM, timeline.
> La recherche intelligente inclut déjà un interpréteur de **commandes** léger
> (rule-based, pas un LLM) qui applique des filtres à partir de mots-clés.

> Les anciennes routes Django `/map/` et `/map_commercial` **redirigent** vers
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
frontend/
├── Dockerfile           # build Vite puis image Nginx
├── nginx.conf           # SPA + proxy des routes backend vers Django
└── src/
    ├── api/
    │   ├── client.js        # fetch + session Django + CSRF
    │   ├── map.js           # GET /api/map/assets/
    │   └── orthophotos.js   # endpoints orthophotos
    ├── lib/
    │   ├── uploadMultipart.js
    │   └── format.js
    ├── components/
    │   ├── map/             # composants Leaflet
    │   └── …                # layout, toasts, contrôles…
    └── pages/
        ├── MapView.jsx
        ├── ResourceListPage.jsx / ResourceDetailPage.jsx / ResourceFormPage.jsx
        └── OrthophotoList.jsx / OrthophotoUpload.jsx / OrthophotoDetail.jsx
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

Connectez-vous au Django proxifié via
`http://localhost:5173/accounts/login/` pour obtenir le cookie de session.
L'application React est servie sur `http://localhost:5173/`.

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
docker compose build frontend
```

Le premier stage construit le bundle Vite dans `dist/`; le second le copie
dans l'image Nginx. Dans Dockploy, le domaine principal doit cibler le service
`frontend` sur le port `80`, jamais `parcelaireweb`.

Le routage interne utilise `HashRouter` (`/#/carte`,
`/#/orthophotos/12`…) : aucune réécriture d'URL serveur n'est
nécessaire.
