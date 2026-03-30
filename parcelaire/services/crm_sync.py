# parcelaire/services/crm_sync_runner.py
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from parcelaire.models import Parcel
from parcelaire.services.crm_lot_sync import KaydanCRMLotSyncService


def _base_queryset():
    """
    Queryset de base pour la synchronisation CRM.
    """
    return (
        Parcel.objects.filter(
            is_active=True,
            program__is_active=True,
        )
        .select_related(
            "program",
            "program__project",
            "block",
            "phase",
            "dataset",
        )
    )


def sync_all_parcels():
    """
    Synchronise toutes les parcelles actives des programmes actifs.
    """
    service = KaydanCRMLotSyncService()
    return service.sync_queryset(_base_queryset())


def sync_program_parcels(program_id):
    """
    Synchronise toutes les parcelles actives d'un programme donné.
    """
    service = KaydanCRMLotSyncService()

    queryset = _base_queryset().filter(program_id=program_id)

    return service.sync_queryset(queryset)


def sync_stale_parcels(hours=24):
    """
    Synchronise uniquement les parcelles non encore synchronisées
    ou dont la dernière synchro CRM est plus ancienne que `hours`.
    """
    service = KaydanCRMLotSyncService()

    try:
        hours = int(hours)
    except (TypeError, ValueError):
        hours = 24

    if hours <= 0:
        hours = 24

    queryset = _base_queryset()

    if hasattr(Parcel, "crm_last_synced_at"):
        limit = timezone.now() - timezone.timedelta(hours=hours)
        queryset = queryset.filter(
            Q(crm_last_synced_at__isnull=True) |
            Q(crm_last_synced_at__lt=limit)
        )

    return service.sync_queryset(queryset)