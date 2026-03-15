from django.db.models import Q
from django.utils import timezone
from parcelaire.models import Parcel
from parcelaire.services.crm_lot_sync import KaydanCRMLotSyncService


def sync_all_parcels():
    service = KaydanCRMLotSyncService()
    return service.sync_all_active_parcels()


def sync_program_parcels(program_id):
    queryset = Parcel.objects.filter(
        is_active=True,
        program_id=program_id,
        program__is_active=True,
    ).select_related("program", "program__project")

    service = KaydanCRMLotSyncService()
    return service.sync_queryset(queryset)


def sync_stale_parcels(hours=24):
    service = KaydanCRMLotSyncService()

    if hasattr(Parcel, "crm_last_synced_at"):
        limit = timezone.now() - timezone.timedelta(hours=hours)
        queryset = Parcel.objects.filter(
            is_active=True,
            program__is_active=True,
        ).filter(
            Q(crm_last_synced_at__isnull=True) |
            Q(crm_last_synced_at__lt=limit)
        ).select_related("program", "program__project")
    else:
        queryset = Parcel.objects.filter(
            is_active=True,
            program__is_active=True,
        ).select_related("program", "program__project")

    return service.sync_queryset(queryset)