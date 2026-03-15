from celery import shared_task

from parcelaire.services.crm_sync import (
    sync_all_parcels,
    sync_program_parcels,
    sync_stale_parcels,
)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_kaydan_all_parcels_task(self):
    return sync_all_parcels()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_kaydan_stale_parcels_task(self):
    return sync_stale_parcels(hours=24)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def sync_kaydan_program_parcels_task(self, program_id):
    return sync_program_parcels(program_id)