"""
Recalcule et persiste les alertes métier. À planifier (cron / Celery beat)
pour un rafraîchissement continu, ou à lancer manuellement.

    python manage.py generate_alerts
"""
from django.core.management.base import BaseCommand

from parcelaire.services.alerts import generate_alerts


class Command(BaseCommand):
    help = "Génère et persiste les alertes métier (idempotent, auto-résolution)."

    def handle(self, *args, **options):
        result = generate_alerts()
        self.stdout.write(self.style.SUCCESS(
            f"Alertes actives={result['active']} | créées={result['created']} "
            f"| mises à jour={result['updated']} | résolues={result['resolved']}"
        ))
