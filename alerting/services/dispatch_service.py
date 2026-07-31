"""Orchestration d'un envoi complet (Phase 5).

`run_configuration` : le cœur réutilisable — crée un AlertDispatch, persiste les
détections, construit le contexte, génère le PDF, l'archive, envoie les e-mails,
trace le résultat par destinataire, puis recalcule `next_send_at`. Appelé par les
tâches Celery ET par la génération manuelle (Phase 6).
"""
import logging
from datetime import timedelta

from django.utils import timezone

from alerting.models import (
    AlertConfiguration, AlertDispatch, AlertDispatchRecipient, AlertReport,
    DispatchStatus, Retention,
)
from alerting.services import alert_detector, email_sender, pdf_renderer, report_builder

logger = logging.getLogger(__name__)


def resolve_recipients(configuration):
    """Destinataires e-mail actifs (recipients + membres des groupes), dédupliqués."""
    found = {}
    def add(iterable):
        for r in iterable:
            if r.is_active and r.receive_email and r.email:
                found[r.id] = r
    add(configuration.recipients.all())
    for group in configuration.recipient_groups.filter(is_active=True):
        add(group.recipients.all())
    return list(found.values())


def run_configuration(configuration, reference_date=None, window_days=7, preview=False,
                      recipients_override=None, can_fin=True, reschedule=True):
    """Exécute une configuration → AlertDispatch (persisté). `preview` génère sans
    envoyer. Recalcule `next_send_at` après un envoi réel (sauf `reschedule=False`,
    p.ex. une génération MANUELLE qui ne doit pas décaler la cadence planifiée)."""
    now = timezone.now()
    reference_date = reference_date or now.date()
    period_start = reference_date - timedelta(days=window_days)

    dispatch = AlertDispatch.objects.create(
        configuration=configuration, period_start=period_start, period_end=reference_date,
        status=DispatchStatus.GENERATING, started_at=now, is_preview=preview)

    try:
        # Persiste les détections de la période (idempotent).
        alert_detector.run_detection(configuration, reference_date, window_days, persist=True)

        ctx = report_builder.build_report_context(
            configuration, reference_date, window_days,
            generated_at=timezone.localtime(now).strftime("%d/%m/%Y %H:%M"), can_fin=can_fin)
        dispatch.subject = email_sender.build_subject(
            ctx, getattr(configuration, "email_subject_template", None))

        pdf_bytes = pdf_name = None
        if configuration.include_pdf:
            pdf_bytes = pdf_renderer.render_report_pdf(ctx)
            pdf_name = pdf_renderer.report_filename(ctx)
            rel, _abs, checksum = pdf_renderer.save_report_pdf(pdf_bytes, pdf_name)
            report = AlertReport.objects.create(
                title=dispatch.subject or "Rapport d'alertes",
                period_start=period_start, period_end=reference_date,
                file_path=rel, checksum=checksum, retention_days=Retention.D90,
                generated_by=configuration.created_by)
            report.programs.set([m["program_id"] for m in ctx["programs"]])
            dispatch.report = report
            dispatch.attachment_path = rel
            dispatch.checksum = checksum

        if preview:
            dispatch.status = DispatchStatus.READY
            dispatch.completed_at = timezone.now()
            dispatch.save()
            return dispatch

        # Résolution destinataires + envoi.
        recip_objs = []
        if recipients_override is not None:
            emails = list(recipients_override)
        else:
            recip_objs = resolve_recipients(configuration)
            emails = [r.email for r in recip_objs]

        if not emails:
            dispatch.status = DispatchStatus.FAILED
            dispatch.error_message = "Aucun destinataire actif pour cette configuration."
            dispatch.completed_at = timezone.now()
            dispatch.save()
            if reschedule:
                _reschedule(configuration)
            return dispatch

        dispatch.status = DispatchStatus.SENDING
        dispatch.save(update_fields=["status", "subject", "report", "attachment_path",
                                     "checksum", "updated_at"])
        sent = email_sender.send_report_email(
            ctx, pdf_bytes=pdf_bytes, pdf_filename=pdf_name, recipients=emails,
            subject_template=getattr(configuration, "email_subject_template", None))

        for r in recip_objs:
            AlertDispatchRecipient.objects.create(
                dispatch=dispatch, recipient=r, email=r.email,
                status=(AlertDispatchRecipient.DeliveryStatus.SENT if sent
                        else AlertDispatchRecipient.DeliveryStatus.FAILED),
                sent_at=timezone.now() if sent else None)

        dispatch.email_count = sent
        if sent == 0:
            dispatch.status = DispatchStatus.FAILED
        elif sent < len(emails):
            dispatch.status = DispatchStatus.PARTIAL
        else:
            dispatch.status = DispatchStatus.SENT
        dispatch.sent_at = timezone.now()
        dispatch.completed_at = timezone.now()
        dispatch.save()

        if reschedule:
            _reschedule(configuration)
        return dispatch

    except Exception as exc:  # noqa: BLE001
        logger.exception("Échec du dispatch d'alerte (config %s)", getattr(configuration, "id", None))
        dispatch.status = DispatchStatus.FAILED
        dispatch.error_message = str(exc)[:2000]
        dispatch.completed_at = timezone.now()
        dispatch.save()
        raise


def _reschedule(configuration):
    configuration.last_sent_at = timezone.now()
    configuration.next_send_at = configuration.compute_next_send_at()
    configuration.save(update_fields=["last_sent_at", "next_send_at", "updated_at"])


def due_configurations(now=None):
    """Configurations dont l'échéance d'envoi est arrivée."""
    from alerting.models import Frequency
    now = now or timezone.now()
    return list(AlertConfiguration.objects
                .filter(is_active=True, next_send_at__isnull=False, next_send_at__lte=now)
                .exclude(frequency=Frequency.MANUAL))
