# integrations/tasks.py
from celery import shared_task

from parcelaire.sap.business_partner import SAPBusinessPartnerService


# from integrations.sap.business_partner import SAPBusinessPartnerService


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_business_partners_task(self, top=100):
    try:
        service = SAPBusinessPartnerService()
        data = service.list_partners(top=top)
        return data
    except Exception as exc:
        raise self.retry(exc=exc)