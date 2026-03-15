# parcelaire/services/crm_projection.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from parcelaire.models import (
    Parcel,
    ConstructionProject,
    ConstructionUpdate,
)


class ParcelCRMProjectionService:
    PROJECT_STATUS = "IN_PROGRESS"
    UPDATE_STAGE = "OTHER"
    UPDATE_SUMMARY = "Synchronisation CRM"
    UPDATE_RECORDED_BY = "CRM_SYNC"

    def _safe_decimal(self, value) -> Decimal:
        try:
            if value in [None, ""]:
                return Decimal("0")
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _safe_float(self, value) -> float:
        try:
            if value in [None, ""]:
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    def _quantize_2(self, value) -> Decimal:
        return self._safe_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _crm_data(self, parcel: Parcel) -> dict:
        return (parcel.metadata or {}).get("crm_lot_sync", {}) or {}

    def _project_code(self, parcel: Parcel) -> str:
        program_code = getattr(parcel.program, "code", None) or "PRG"
        lot_code = parcel.lot_number or parcel.parcel_code or str(parcel.id)
        return f"CRM-{program_code}-{lot_code}-{parcel.id}"

    def _project_title(self, parcel: Parcel) -> str:
        lot = parcel.lot_number or parcel.parcel_code or str(parcel.id)
        return f"Suivi CRM lot {lot}"

    def _build_update_details(self, parcel: Parcel, crm: dict, valeur_hypothecaire: Decimal, progress_raw: Decimal) -> str:
        ilot = crm.get("ilot") or (parcel.block.code if parcel.block else "")
        lot = crm.get("lot") or parcel.lot_number or parcel.parcel_code or ""
        code_projet = crm.get("code_projet") or getattr(parcel.program, "code", "")

        return (
            f"Synchronisation CRM du {timezone.localdate():%d/%m/%Y}\n"
            f"Lot: {lot}\n"
            f"Îlot: {ilot}\n"
            f"Code projet: {code_projet}\n"
            f"Valeur hypothécaire: {valeur_hypothecaire}\n"
            f"Avancement travaux mois: {progress_raw}"
        )

    @transaction.atomic
    def project_parcel(self, parcel: Parcel) -> dict:
        crm = self._crm_data(parcel)
        if not crm:
            return {
                "parcel_id": parcel.id,
                "project_created": False,
                "project_updated": False,
                "update_created": False,
                "update_updated": False,
                "parcel_updated": False,
                "skipped": True,
            }

        now = timezone.now()
        today = now.date()

        valeur_hypothecaire = self._quantize_2(crm.get("valeur_hypothecaire"))
        progress_raw = self._safe_decimal(crm.get("avancement_travaux_mois"))
        progress_percent = self._quantize_2(crm.get("avancement_travaux_mois"))

        parcel_updated = False
        parcel_fields = []

        if parcel.valeur_hypothecaire != valeur_hypothecaire:
            parcel.valeur_hypothecaire = valeur_hypothecaire
            parcel_fields.append("valeur_hypothecaire")

        parcel.crm_last_synced_at = now
        parcel_fields.append("crm_last_synced_at")

        if parcel_fields:
            parcel_fields.append("updated_at")
            parcel.save(update_fields=parcel_fields)
            parcel_updated = True

        project, project_created = ConstructionProject.objects.get_or_create(
            parcel=parcel,
            code=self._project_code(parcel),
            defaults={
                "title": self._project_title(parcel),
                "description": "Projet technique généré automatiquement depuis les données CRM.",
                "status": self.PROJECT_STATUS,
                "progress_percent": progress_percent,
                "actual_start_date": today,
                "metadata": {
                    "source": "crm_sync",
                    "crm_snapshot": crm,
                },
            },
        )

        project_updated = False
        project_fields = []

        if project.title != self._project_title(parcel):
            project.title = self._project_title(parcel)
            project_fields.append("title")

        if project.status != self.PROJECT_STATUS:
            project.status = self.PROJECT_STATUS
            project_fields.append("status")

        if self._safe_decimal(project.progress_percent or 0) != progress_percent:
            project.progress_percent = progress_percent
            project_fields.append("progress_percent")

        project_metadata = project.metadata or {}
        new_project_metadata = {
            **project_metadata,
            "source": "crm_sync",
            "crm_snapshot": crm,
        }

        if project.metadata != new_project_metadata:
            project.metadata = new_project_metadata
            project_fields.append("metadata")

        if not project.actual_start_date:
            project.actual_start_date = today
            project_fields.append("actual_start_date")

        if project_fields:
            project_fields.append("updated_at")
            project.save(update_fields=project_fields)
            project_updated = True

        update_obj, update_created = ConstructionUpdate.objects.update_or_create(
            construction_project=project,
            report_date=today,
            recorded_by=self.UPDATE_RECORDED_BY,
            defaults={
                "stage": self.UPDATE_STAGE,
                "progress_percent": progress_percent,
                "summary": self.UPDATE_SUMMARY,
                "details": self._build_update_details(parcel, crm, valeur_hypothecaire, progress_raw),
                "issues": "",
                "next_actions": "",
                "weather_notes": "",
                "asset": None,
            },
        )

        update_updated = not update_created

        return {
            "parcel_id": parcel.id,
            "project_created": project_created,
            "project_updated": project_updated,
            "update_created": update_created,
            "update_updated": update_updated,
            "parcel_updated": parcel_updated,
            "skipped": False,
        }

    def project_queryset(self, queryset):
        results = []
        for parcel in queryset:
            results.append(self.project_parcel(parcel))
        return results