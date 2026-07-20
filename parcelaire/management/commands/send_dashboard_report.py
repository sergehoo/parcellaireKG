"""Envoie le rapport PDF de pilotage aux destinataires actifs (e-mail).

À déclencher manuellement, ou à planifier explicitement par un opérateur
(cron / Celery beat) UNE FOIS le SMTP configuré (settings EMAIL_*). Aucune
planification n'est activée par défaut : l'envoi est une action sortante.
"""
from django.core.management.base import BaseCommand

from parcelaire.services.reports import send_dashboard_report


class Command(BaseCommand):
    help = "Envoie le rapport PDF de pilotage par e-mail aux destinataires actifs."

    def handle(self, *args, **options):
        result = send_dashboard_report()
        self.stdout.write(self.style.SUCCESS(f"Envoi rapport de pilotage : {result}"))
