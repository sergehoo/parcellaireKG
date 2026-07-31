"""Envoi de l'e-mail d'alerte (Phase 4) — HTML responsive + PDF en pièce jointe."""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def build_subject(context, template=None):
    progs = context.get("programs") or []
    scope = progs[0]["program"] if len(progs) == 1 else "Portefeuille"
    default = (f"[ALERTE PARCELLAIRE] Rapport paiement vs construction — {scope} — "
               f"du {context['period_start']} au {context['period_end']}")
    if template:
        try:
            return template.format(scope=scope, period_start=context["period_start"],
                                   period_end=context["period_end"],
                                   report_id=context.get("report_id", ""))
        except (KeyError, IndexError, ValueError):
            return default
    return default


def send_report_email(context, pdf_bytes=None, pdf_filename=None, recipients=None,
                      subject_template=None, from_email=None):
    """Envoie le rapport aux `recipients` (liste d'e-mails). Renvoie le nombre
    de messages envoyés. Le PDF, s'il est fourni, est joint."""
    recipients = [r for r in (recipients or []) if r]
    if not recipients:
        return 0
    subject = build_subject(context, subject_template)
    html_body = render_to_string("alerting/email.html", context)
    text_body = render_to_string("alerting/email.txt", context)
    from_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None)

    sent = 0
    for to in recipients:
        msg = EmailMultiAlternatives(subject, text_body, from_email, [to])
        msg.attach_alternative(html_body, "text/html")
        if pdf_bytes and pdf_filename:
            msg.attach(pdf_filename, pdf_bytes, "application/pdf")
        sent += msg.send()
    return sent
