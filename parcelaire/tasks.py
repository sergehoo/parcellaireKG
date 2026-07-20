import logging
from pathlib import Path
from typing import Optional

from celery import shared_task
from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.db import transaction
from django.utils import timezone

from parcelaire.services.alerts import generate_alerts as _generate_alerts
from parcelaire.services.reports import send_dashboard_report as _send_dashboard_report
from parcelaire.services.crm_sync import (
    sync_all_parcels,
    sync_program_parcels,
    sync_stale_parcels,
)
from parcelaire.services.orthophoto import (
    OrthophotoPipeline,
    OrthophotoProcessingError,
    build_paths,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_kaydan_all_parcels_task(self):
    return sync_all_parcels()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_kaydan_stale_parcels_task(self):
    return sync_stale_parcels(hours=24)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_kaydan_program_parcels_task(self, program_id):
    return sync_program_parcels(program_id)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_alerts_task(self):
    """Recalcule et persiste les alertes métier (centre de notifications).

    Idempotent : chaque passage réconcilie les alertes actives avec l'état
    réel et auto-résout celles dont l'anomalie a disparu. Planifié via
    CELERY_BEAT_SCHEDULE (settings) ; déclenchable à la demande avec
    generate_alerts_task.delay().
    """
    return _generate_alerts()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_dashboard_report_task(self):
    """Envoie le rapport PDF de pilotage par e-mail aux destinataires actifs.

    Action SORTANTE : volontairement NON planifiée par défaut dans
    CELERY_BEAT_SCHEDULE. Un opérateur l'active explicitement (beat/cron) une
    fois le SMTP configuré ; sinon on la déclenche à la demande via
    send_dashboard_report_task.delay().
    """
    return _send_dashboard_report()


# =====================================================================
# Pipeline orthophoto (GDAL → tuiles XYZ)
# =====================================================================


@shared_task(bind=True, max_retries=0)
def process_orthophoto(self, orthophoto_id: int):
    """
    Orchestre le pipeline complet pour une orthophoto.

    Étapes — alignées sur le brief :
        1. Préparation des dossiers (PROCESSING, 5 %)
        2. Reprojection en EPSG:3857 (gdalwarp)
        3. Lecture gdalinfo (extraction métadonnées)
        4. Génération des overviews (gdaladdo)
        5. Détection palette → VRT RGBA si besoin
        6. Génération des tuiles XYZ (gdal2tiles.py)
        7. Finalisation (DONE, 100 %, processed_at, is_current ...)

    En cas d'échec : statut FAILED + error_message + log ERROR ; pas de
    retry automatique (un opérateur doit relancer manuellement via le
    bouton "Relancer le traitement" → c'est plus sûr pour des process
    qui peuvent durer 30+ minutes).
    """
    from parcelaire.models import ProgramOrthophoto, OrthophotoProcessingLog

    try:
        ortho = ProgramOrthophoto.objects.select_related("program").get(pk=orthophoto_id)
    except ProgramOrthophoto.DoesNotExist:
        logger.error("Orthophoto introuvable id=%s", orthophoto_id)
        return {"status": "MISSING", "id": orthophoto_id}

    # ----------------------------------------------------------
    # Helper de log : écrit dans le model + remonte au logger Django
    # ----------------------------------------------------------
    def log(level: str, message: str, command: Optional[str] = None):
        try:
            OrthophotoProcessingLog.objects.create(
                orthophoto=ortho,
                level=level,
                message=str(message)[:5000],
                command=(command or "")[:2000] or None,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Échec écriture log orthophoto %s", ortho.pk)
        logger.log(
            {"INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}.get(level, logging.INFO),
            "[orthophoto %s] %s",
            ortho.pk,
            message,
        )

    def update(**fields):
        """Mise à jour atomique d'un sous-ensemble de champs."""
        ProgramOrthophoto.objects.filter(pk=ortho.pk).update(**fields)
        for k, v in fields.items():
            setattr(ortho, k, v)

    # --------------------------------------------------------------
    # Récupération du TIFF source.
    # Le fichier source peut être :
    #   (a) directement dans `source_file` (FileField local — workflow
    #       classique ou ancien upload chunked sur disque) ;
    #   (b) stocké sur MinIO/S3 (workflow presigned multipart : la clé
    #       est dans `metadata.s3_object.key`). On télécharge alors la
    #       clé S3 dans le filesystem local et on l'attache à
    #       `source_file` pour la suite du pipeline (et l'historique).
    # --------------------------------------------------------------
    if not ortho.source_file:
        s3_obj = (ortho.metadata or {}).get("s3_object") or {}
        s3_key = s3_obj.get("key")
        if s3_key:
            try:
                from parcelaire.services import storage as _s3
                local_dir = Path(settings.MEDIA_ROOT) / "orthophotos" / "sources" / str(ortho.pk)
                local_dir.mkdir(parents=True, exist_ok=True)
                local_path = local_dir / Path(s3_key).name
                update(current_step=f"Téléchargement S3 ({Path(s3_key).name})")
                log("INFO", f"Téléchargement depuis S3 : {s3_key} → {local_path}")
                _s3.download_to_path(s3_key, local_path)
                rel = local_path.relative_to(settings.MEDIA_ROOT)
                update(source_file=str(rel))
                log("INFO", f"Source téléchargée ({local_path.stat().st_size} octets).")
            except Exception as exc:  # noqa: BLE001
                update(status="FAILED", error_message=f"Téléchargement S3 KO : {exc}", current_step="Échec S3")
                log("ERROR", f"Téléchargement S3 KO : {exc}")
                return {"status": "FAILED", "id": ortho.pk, "error": str(exc)}
        else:
            update(status="FAILED", error_message="Aucun fichier source.", current_step="—")
            log("ERROR", "Aucun fichier source associé à l'orthophoto.")
            return {"status": "FAILED", "id": ortho.pk}

    # ----------------------------------------------------------
    # Étape 1 — préparation
    # ----------------------------------------------------------
    program_slug = (ortho.program.slug or "program").lower()
    year = int(ortho.reference_year or timezone.now().year)
    month = int(ortho.reference_month or timezone.now().month)
    paths = build_paths(program_slug, year, month, media_root=Path(settings.MEDIA_ROOT))

    update(
        status="PROCESSING",
        progress_percent=5,
        current_step="Préparation des dossiers",
        error_message=None,
        processed_at=None,
    )
    log("INFO", f"Démarrage pipeline → {paths['subpath']}")

    pipeline = OrthophotoPipeline(
        work_dir=paths["work_dir"],
        tiles_dir=paths["tiles_dir"],
        log=log,
        gdal_processes=int(getattr(settings, "ORTHOPHOTO_GDAL_PROCESSES", 4)),
    )

    source_path = Path(ortho.source_file.path)
    if not source_path.exists():
        update(status="FAILED", error_message=f"Fichier source introuvable : {source_path}")
        log("ERROR", f"Fichier source introuvable : {source_path}")
        return {"status": "FAILED", "id": ortho.pk}

    try:
        # ------------------------------------------------------
        # Étape 2 — reprojection EPSG:3857
        # ------------------------------------------------------
        update(progress_percent=15, current_step="Reprojection EPSG:3857")
        reprojected = paths["work_dir"] / f"{program_slug}_{year}{month:02d}_3857.tif"
        pipeline.reproject_to_3857(source_path, reprojected)
        rel_processed = reprojected.relative_to(settings.MEDIA_ROOT)
        update(
            processed_file=str(rel_processed),
            progress_percent=30,
        )

        # ------------------------------------------------------
        # Étape 3 — gdalinfo
        # ------------------------------------------------------
        update(current_step="Lecture des métadonnées (gdalinfo)")
        info = pipeline.inspect(reprojected)

        # Bounds GEOS si dispo (Polygon en WGS84 4326)
        if info.bounds:
            minx, miny, maxx, maxy = info.bounds
            update(
                bounds=Polygon.from_bbox((minx, miny, maxx, maxy)),
                progress_percent=40,
            )

        # ------------------------------------------------------
        # Étape 4 — overviews
        # ------------------------------------------------------
        update(progress_percent=50, current_step="Génération des overviews")
        pipeline.build_overviews(reprojected)

        # ------------------------------------------------------
        # Étape 5 — détection palette → VRT
        # ------------------------------------------------------
        tile_source = reprojected
        if info.has_palette:
            update(progress_percent=60, current_step="Expansion palette → RGBA")
            vrt_path = paths["work_dir"] / f"{program_slug}_{year}{month:02d}_rgba.vrt"
            pipeline.expand_palette_to_rgba(reprojected, vrt_path)
            tile_source = vrt_path
            update(vrt_file=str(vrt_path.relative_to(settings.MEDIA_ROOT)))

        # ------------------------------------------------------
        # Étape 6 — tuiles XYZ
        # ------------------------------------------------------
        update(progress_percent=70, current_step="Génération des tuiles XYZ")
        pipeline.generate_tiles(
            tile_source,
            paths["tiles_dir"],
            min_zoom=int(ortho.min_zoom or 15),
            max_zoom=int(ortho.max_zoom or 22),
        )

        # ------------------------------------------------------
        # Étape 7 — finalisation
        # ------------------------------------------------------
        update(
            progress_percent=95,
            current_step="Finalisation",
            tiles_folder=paths["subpath"],
            tiles_url=paths["tiles_url"],
        )

        with transaction.atomic():
            if ortho.is_current:
                ProgramOrthophoto.objects.filter(program_id=ortho.program_id).exclude(pk=ortho.pk).update(is_current=False)
            update(
                status="DONE",
                progress_percent=100,
                current_step="Terminé",
                processed_at=timezone.now(),
            )

        log("INFO", f"Pipeline terminé avec succès — tuiles : {paths['tiles_url']}")
        return {"status": "DONE", "id": ortho.pk, "tiles_url": paths["tiles_url"]}

    except OrthophotoProcessingError as exc:
        update(
            status="FAILED",
            error_message=str(exc)[:5000],
            current_step="Échec",
        )
        log("ERROR", f"Pipeline GDAL échoué : {exc}", getattr(exc, "command", None))
        return {"status": "FAILED", "id": ortho.pk, "error": str(exc)}

    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur inattendue pipeline orthophoto %s", ortho.pk)
        update(
            status="FAILED",
            error_message=f"Erreur inattendue : {exc}",
            current_step="Échec",
        )
        log("ERROR", f"Exception non gérée : {exc}")
        return {"status": "FAILED", "id": ortho.pk, "error": str(exc)}