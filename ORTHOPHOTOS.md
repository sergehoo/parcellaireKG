# Module Orthophotos — KAYDAN parcelaireKG

Pipeline d'import et de génération de tuiles XYZ pour les orthophotos
(prises de vue aériennes) du portefeuille immobilier.

## Architecture

```
                ┌─────────────────────┐
                │  Browser  (Alpine)  │
                │  upload TIFF + form │
                └──────────┬──────────┘
                           │ POST /orthophotos/add/
                           ▼
              ┌──────────────────────────┐
              │  Django   (Gunicorn)     │
              │  OrthophotoCreateView    │
              │   ↳ save() PENDING       │
              │   ↳ process_orthophoto.delay(id)
              └──────────┬───────────────┘
                         │ AMQP/Redis
                         ▼
              ┌──────────────────────────┐
              │  Celery worker           │
              │  process_orthophoto      │
              │   ↳ gdalwarp (3857)      │
              │   ↳ gdalinfo             │
              │   ↳ gdaladdo             │
              │   ↳ gdal_translate (VRT) │
              │   ↳ gdal2tiles.py        │
              └──────────┬───────────────┘
                         │ writes
                         ▼
              media/tiles_ortho/<slug>/<year>/<month>/{z}/{x}/{y}.png
                         │
                         │ served by WhiteNoise/Django
                         ▼
              ┌──────────────────────────┐
              │  Leaflet (map.html)      │
              │  L.tileLayer(tiles_url)  │
              └──────────────────────────┘
```

### Modèles

- **`ProgramOrthophoto`** (existant, étendu) : rattaché à `RealEstateProgram`.
  Champs clés : `source_file`, `processed_file`, `vrt_file`, `tiles_folder`,
  `tiles_url`, `min_zoom`, `max_zoom`, `bounds`, `reference_year/month`,
  `status` (PENDING / PROCESSING / DONE / FAILED), `progress_percent`,
  `current_step`, `error_message`, `is_current`, `created_by`, `processed_at`.

  Contraintes :
  - `unique (program, reference_year, reference_month)` quand année/mois définis
  - `unique program where is_current=True` (1 seule courante par programme)

- **`OrthophotoProcessingLog`** (nouveau) : journal structuré du pipeline.
  Chaque commande shell exécutée écrit une ligne (`level`, `message`,
  `command`). Permet la timeline UI sans parser de blob texte.

### Service GDAL — `parcelaire/services/orthophoto.py`

Classe `OrthophotoPipeline` qui encapsule subprocess :

| Méthode | Commande |
|---|---|
| `reproject_to_3857(src, dst)` | `gdalwarp -t_srs EPSG:3857 -r bilinear -multi -wo NUM_THREADS=ALL_CPUS -co TILED=YES -co COMPRESS=DEFLATE -co BIGTIFF=YES` |
| `inspect(path)` | `gdalinfo -json -stats` → `GdalInfo(srs, bounds, color_interps…)` |
| `build_overviews(path)` | `gdaladdo -r average … 2 4 8 16 32` |
| `expand_palette_to_rgba(src, vrt)` | `gdal_translate -of VRT -expand rgba` |
| `generate_tiles(src, dir, min, max)` | `gdal2tiles.py --xyz --processes=N --tiledriver=PNG -z min-max` |
| `purge_tiles()` | `shutil.rmtree(tiles_dir)` |

Chaque méthode lève `OrthophotoProcessingError` (avec stdout/stderr capturés)
en cas d'échec et journalise via un callback `log(level, message, command)`.

### Tâche Celery — `parcelaire/tasks.py::process_orthophoto`

Orchestration en 7 étapes (5 → 100 %) :

```
 5 % préparation des dossiers
15 % reprojection EPSG:3857           (gdalwarp)
30 % processed_file enregistré
40 % gdalinfo + bounds                 (gdalinfo)
50 % overviews                         (gdaladdo)
60 % VRT si palette                    (gdal_translate)
70 % tuiles XYZ                        (gdal2tiles.py)
95 % finalisation
100 % DONE
```

Pas de `autoretry_for` : un pipeline qui dure 30+ min ne doit pas se
rejouer automatiquement. Le bouton "Relancer" en UI déclenche manuellement.

### Vues / URLs

| URL | Vue | Méthode |
|---|---|---|
| `/orthophotos/` | `OrthophotoListView` | GET — liste paginée + filtres |
| `/orthophotos/add/` | `OrthophotoCreateView` | GET/POST — upload TIFF |
| `/orthophotos/<id>/` | `OrthophotoDetailView` | GET — page détail + polling |
| `/orthophotos/<id>/status/` | `OrthophotoStatusAPIView` | GET — JSON pour Alpine.js |
| `/orthophotos/<id>/retry/` | `OrthophotoRetryView` | POST |
| `/orthophotos/<id>/set-current/` | `OrthophotoSetCurrentView` | POST |
| `/orthophotos/<id>/delete-tiles/` | `OrthophotoDeleteTilesView` | POST |
| `/orthophotos/<id>/logs.txt` | `OrthophotoDownloadLogsView` | GET — export texte |

### Frontend

- **`list.html`** : grille de cards avec filtres (projet, programme, année,
  mois, statut), recherche, badges de statut, bouton "Nouvelle orthophoto".
- **`form.html`** : zone drag&drop, sélection projet → programme, période,
  zoom min/max, switches "courante" et "remplacer".
- **`detail.html`** : progress bar, étape courante, timeline des logs,
  actions (retry / set-current / delete-tiles / voir sur la carte / logs).
  Polling `fetch('/orthophotos/<id>/status/')` toutes les 3 s tant que
  `status ∈ {PENDING, PROCESSING}`.

### Intégration carte Leaflet

`RealEstateMapAPIView.serialize_orthophoto` expose pour chaque programme :

```json
{
  "id": 12, "name": "BR Mai 2026",
  "tiles_url": "/media/tiles_ortho/br/2026/05/{z}/{x}/{y}.png",
  "min_zoom": 15, "max_zoom": 22,
  "reference_year": 2026, "reference_month": 5,
  "period_label": "Mai 2026",
  "is_current": true,
  "bounds": {...},
  "status": "DONE",
  "is_ready": true
}
```

Le prefetch (`orthophotos_prefetch()`) filtre désormais `status=DONE`
+ `tiles_url` non vide → on n'expose **jamais** une orthophoto en cours.

Côté frontend (`map.html` → `applyOrthoLayer()`), un `activeOrthoKey`
basé sur `(program_id, period_value, mapMode)` empêche le rechargement
de la couche tant que l'orthophoto active n'a pas changé.

## Installation système

### Dockerfile

Le `Dockerfile` installe :

```dockerfile
gdal-bin       # binaires gdalwarp/gdalinfo/gdaladdo/gdal_translate
libgdal-dev    # headers pour bindings Python
python3-gdal   # fournit gdal2tiles.py
```

### settings

Variables d'environnement disponibles :

```env
ORTHOPHOTO_MAX_BYTES=8589934592      # 8 Go (taille max upload)
ORTHOPHOTO_GDAL_PROCESSES=4          # gdal2tiles parallélisme
```

Les uploads très gros transitent en disque tampon (`/tmp` par défaut)
via `FILE_UPLOAD_MAX_MEMORY_SIZE=10 MiB`.

## Permissions

- **Lire** : `parcelaire.view_programorthophoto` (auto, créée par Django).
- **Importer/Relancer/Supprimer** : `parcelaire.add_programorthophoto`,
  `parcelaire.change_programorthophoto`, `parcelaire.delete_programorthophoto`.

Tous les `LoginRequiredMixin` redirigent vers `/accounts/login/`.

## Mise en route

```bash
# 1. Build & migrations
docker compose build
docker compose up -d parcelairedb redis
docker compose run --rm parcelaireweb python manage.py makemigrations parcelaire
docker compose run --rm parcelaireweb python manage.py migrate

# 2. Lancer web + worker
docker compose up -d parcelaireweb parcelairecelery

# 3. Vérifier que GDAL est OK dans le worker
docker exec parcelairecelery gdalinfo --version
docker exec parcelairecelery gdal2tiles.py --help | head

# 4. Importer une orthophoto via l'UI
#    → http://datarium-dev.com/orthophotos/add/
```

## Diagnostic

```bash
# Suivre le pipeline d'une orthophoto (id = 3)
docker exec parcelaireweb python manage.py shell -c "
from parcelaire.models import ProgramOrthophoto
o = ProgramOrthophoto.objects.get(pk=3)
print(o.status, o.progress_percent, o.current_step)
for log in o.processing_logs.order_by('created_at'):
    print(log.created_at, log.level, log.message[:80])
"

# Logs Celery
docker compose logs -f parcelairecelery

# Forcer une relance
docker exec parcelaireweb python manage.py shell -c "
from parcelaire.tasks import process_orthophoto
process_orthophoto.delay(3)
"
```

## Limites connues / TODO

- `gdal2tiles.py --xyz` n'est dispo qu'à partir de GDAL ≥ 2.4 (la
  version Debian Bookworm est à 3.6 — OK).
- L'extraction de `bounds` repose sur `gdalinfo -json/wgs84Extent` ;
  si le GeoTIFF source n'a pas de SRS valide, `bounds` reste null.
- Pas de checksum côté serveur : un upload corrompu n'est détecté qu'au
  moment de `gdalwarp` (qui plantera → status FAILED). Acceptable.
