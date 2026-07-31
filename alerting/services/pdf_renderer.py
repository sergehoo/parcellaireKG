"""Rendu PDF du rapport (Phase 4) — WeasyPrint sur template HTML/CSS, hors-ligne."""
import hashlib
import os
from datetime import date

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.text import slugify


def render_report_pdf(context):
    """Renvoie les octets PDF du rapport à partir du contexte (report_builder)."""
    from weasyprint import HTML
    html = render_to_string("alerting/report.html", context)
    return HTML(string=html).write_pdf()


def report_filename(context):
    progs = context.get("programs") or []
    scope = slugify(progs[0]["program"]) if len(progs) == 1 else "portefeuille"
    p0 = context.get("period_start")
    p1 = context.get("period_end")
    return f"rapport_alertes_{scope}_{p0}_{p1}.pdf"


def save_report_pdf(pdf_bytes, filename):
    """Écrit le PDF dans un répertoire dédié sous MEDIA_ROOT/alert_reports/ et
    renvoie (chemin_relatif, chemin_absolu, checksum sha256)."""
    rel_dir = os.path.join("alert_reports", date.today().strftime("%Y/%m"))
    abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    os.makedirs(abs_dir, exist_ok=True)
    rel_path = os.path.join(rel_dir, filename)
    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    with open(abs_path, "wb") as fh:
        fh.write(pdf_bytes)
    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    return rel_path, abs_path, checksum
