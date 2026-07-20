"""
Envoi par e-mail du rapport PDF de pilotage aux destinataires configurés.

Déclenché EXPLICITEMENT (commande `send_dashboard_report` ou tâche Celery
`send_dashboard_report_task`) — aucune planification automatique par défaut :
l'envoi d'e-mails est une action sortante, à activer sciemment une fois le
SMTP configuré (voir settings EMAIL_*). En l'absence de destinataire actif,
la fonction ne tente aucun envoi.

Le PDF est rendu au plus deux fois (avec / sans montants financiers) selon
le drapeau `with_financials` de chaque destinataire, puis mutualisé.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from parcelaire.api.analytics import render_dashboard_pdf
from parcelaire.models import ReportRecipient

logger = logging.getLogger(__name__)


def send_dashboard_report():
    """Envoie le rapport PDF aux destinataires actifs. Renvoie un résumé
    {sent, recipients, skipped}. Ne lève pas si aucun destinataire."""
    recipients = list(ReportRecipient.objects.filter(is_active=True))
    if not recipients:
        logger.info("Rapport de pilotage : aucun destinataire actif — rien à envoyer.")
        return {"sent": 0, "recipients": 0, "detail": "aucun destinataire actif"}

    stamp = timezone.now().strftime("%Y-%m-%d")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

    # PDF mutualisé par variante (avec / sans montants).
    _cache = {}

    def pdf_for(with_financials):
        if with_financials not in _cache:
            _cache[with_financials] = render_dashboard_pdf(
                with_financials, username="Rapport planifié")
        return _cache[with_financials]

    sent = 0
    failed = 0
    for r in recipients:
        # Isolation par destinataire : une adresse invalide ou une erreur SMTP
        # transitoire ne doit NI interrompre le lot, NI (via l'auto-retry Celery)
        # provoquer un ré-envoi aux destinataires déjà servis (doublons).
        try:
            msg = EmailMessage(
                subject=f"Rapport de pilotage — parcelaireKG — {stamp}",
                body=(
                    "Bonjour,\n\nVeuillez trouver ci-joint le rapport de pilotage du "
                    "Centre de commandement (indicateurs, santé des programmes, "
                    "alertes et clients à risque).\n\n— parcelaireKG"
                ),
                from_email=from_email,
                to=[r.email],
            )
            msg.attach(f"tableau-de-bord-{stamp}.pdf", pdf_for(r.with_financials), "application/pdf")
            msg.send(fail_silently=False)
            sent += 1
        except Exception as exc:  # noqa: BLE001 — voir commentaire ci-dessus
            failed += 1
            logger.warning("Rapport de pilotage : échec d'envoi à %s : %s", r.email, exc)

    logger.info("Rapport de pilotage : %s envoyé(s), %s échec(s).", sent, failed)
    return {"sent": sent, "failed": failed, "recipients": len(recipients)}
