"""Tâches Celery du module d'alertes (Phase 5).

Approche recommandée du cahier des charges : UNE tâche centrale horaire
(`evaluate_alert_configurations`) qui traite les configurations échues, plutôt
qu'une tâche Beat dynamique par configuration.
"""
import logging
import os

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def capture_daily_snapshots(self, recorded_at=None):
    """Historise les taux du jour (construction/paiement/commercialisation)."""
    from datetime import date

    from alerting.services import snapshot_service
    when = date.fromisoformat(recorded_at) if recorded_at else None
    return snapshot_service.capture_all(recorded_at=when)


@shared_task
def generate_periodic_alert_report(configuration_id, preview=False):
    """Génère (et envoie sauf preview) le rapport d'une configuration."""
    from alerting.models import AlertConfiguration
    from alerting.services import dispatch_service

    cfg = AlertConfiguration.objects.filter(pk=configuration_id, is_active=True).first()
    if cfg is None:
        return None
    dispatch = dispatch_service.run_configuration(cfg, preview=preview)
    return dispatch.id


@shared_task
def evaluate_alert_configurations():
    """Tâche horaire : traite toutes les configurations dont `next_send_at` est
    arrivée. Chaque envoi recalcule sa propre prochaine échéance."""
    from alerting.services import dispatch_service

    due = dispatch_service.due_configurations()
    processed = []
    for cfg in due:
        try:
            generate_periodic_alert_report(cfg.id)
            processed.append(cfg.id)
        except Exception:  # noqa: BLE001 — une config en échec ne bloque pas les autres
            logger.exception("Configuration d'alerte %s en échec", cfg.id)
    return {"due": len(due), "processed": processed}


@shared_task
def retry_failed_alert_dispatches(max_age_hours=24):
    """Relance les configurations dont le dernier envoi a échoué récemment."""
    from datetime import timedelta

    from alerting.models import AlertConfiguration, AlertDispatch, DispatchStatus
    from alerting.services import dispatch_service

    since = timezone.now() - timedelta(hours=max_age_hours)
    cfg_ids = (AlertDispatch.objects
               .filter(status=DispatchStatus.FAILED, is_preview=False, created_at__gte=since,
                       configuration__isnull=False)
               .values_list("configuration_id", flat=True).distinct())
    retried = []
    for cid in set(cfg_ids):
        cfg = AlertConfiguration.objects.filter(pk=cid, is_active=True).first()
        if cfg is None:
            continue
        try:
            dispatch_service.run_configuration(cfg)
            retried.append(cid)
        except Exception:  # noqa: BLE001
            logger.exception("Retry de la configuration %s en échec", cid)
    return {"retried": retried}


@shared_task
def cleanup_old_generated_reports():
    """Supprime les fichiers PDF au-delà de leur durée de rétention."""
    from datetime import timedelta

    from alerting.models import AlertReport

    removed = 0
    now = timezone.now()
    for report in AlertReport.objects.exclude(retention_days=0).exclude(file_path__isnull=True):
        if report.created_at < now - timedelta(days=report.retention_days):
            abs_path = os.path.join(settings.MEDIA_ROOT, report.file_path)
            try:
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            except OSError:
                logger.warning("Impossible de supprimer %s", abs_path)
            report.file_path = None
            report.save(update_fields=["file_path", "updated_at"])
            removed += 1
    return {"removed": removed}
