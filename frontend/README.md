# Frontend React — Gestion des orthophotos

SPA React (Vite, JavaScript) qui remplace/complète les templates Django
`parcelaire/orthophoto/*` pour la gestion des orthophotos :

- **Liste** : filtres projet / programme / année / mois / statut, recherche,
  pagination, rafraîchissement automatique des traitements en cours.
- **Upload** : drag & drop d'un GeoTIFF, envoi **multipart direct vers
  MinIO** via presigned URLs (3 parts en parallèle, retries, annulation,
  gestion du conflit programme/période avec proposition de remplacement).
- **Détail** : progression du pipeline GDAL en temps réel (polling 3 s),
  timeline des logs, aperçu Leaflet des tuiles générées, actions
  (relancer, définir courante, supprimer les tuiles, export logs).

## Architecture

```
frontend/src
├── api/
│   ├── client.js        # fetch + session Django + CSRF + redirection login
│   └── orthophotos.js   # endpoints (API DRF + endpoints upload existants)
├── lib/
│   ├── uploadMultipart.js  # découpage + PUT presigned + collecte ETags
│   └── format.js
├── components/          # Layout, StatusBadge, ProgressBar, LogTimeline,
│                        # FileDropzone, TileMapPreview (Leaflet), Toasts…
└── pages/
    ├── OrthophotoList.jsx
    ├── OrthophotoUpload.jsx
    └── OrthophotoDetail.jsx
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
`DJANGO_URL=http://localhost:8001 npm run dev`).

Connectez-vous d'abord au Django proxifié (http://localhost:5173/accounts/login/)
pour obtenir le cookie de session.

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
manifest WhiteNoise). L'app est servie sur **`/app/orthophotos/`**
(route `orthophoto_react_app`, login requis) via le template
`templates/parcelaire/orthophoto/react_app.html`.

Le routage interne utilise `HashRouter` (`/app/orthophotos/#/upload`,
`#/orthophotos/12`…) : aucune réécriture d'URL serveur n'est nécessaire.
