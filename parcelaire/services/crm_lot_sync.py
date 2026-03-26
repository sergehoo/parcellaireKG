# parcelaire/services/crm_lot_sync.py
from __future__ import annotations

import json
import logging
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Tuple

import requests
from django.db import models, transaction
from django.utils import timezone

from parcelaire.models import Parcel
from parcelaire.services.crm_projection import ParcelCRMProjectionService

logger = logging.getLogger(__name__)


class KaydanCRMLotSyncService:
    EXTERNAL_LOTS_API_URL = "https://mykaydan.kaydangroupe.com/api/crm/lots"
    EXTERNAL_LOTS_API_KEY = "5632d76ece5711436d3084a628f2afb03388a373"
    EXTERNAL_LOTS_API_USERNAME = "admin"
    EXTERNAL_LOTS_API_PASSWORD = "D@t@rium@1545#"

    TIMEOUT = 20
    CHUNK_SIZE = 20

    def __init__(self):
        self.session = requests.Session()
        self.session.auth = (
            self.EXTERNAL_LOTS_API_USERNAME,
            self.EXTERNAL_LOTS_API_PASSWORD,
        )
        self.session.headers.update({
            "X-API-KEY": self.EXTERNAL_LOTS_API_KEY,
            "Accept": "application/json",
        })

    # =========================================================
    # HELPERS
    # =========================================================

    def chunk_list(self, values: List[str], size: int | None = None) -> List[List[str]]:
        size = size or self.CHUNK_SIZE
        return [values[i:i + size] for i in range(0, len(values), size)]

    def _safe_str(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _safe_decimal(self, value, default: str = "0") -> Decimal:
        try:
            if value in [None, ""]:
                return Decimal(default)
            return Decimal(str(value).replace(",", ".").strip())
        except (InvalidOperation, TypeError, ValueError, AttributeError):
            return Decimal(default)

    def _safe_decimal_2(self, value, default: str = "0.00") -> Decimal:
        return self._safe_decimal(value, default=default).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def _safe_float(self, value) -> float:
        try:
            if value in [None, ""]:
                return 0.0
            return float(str(value).replace(",", ".").strip())
        except Exception:
            return 0.0

    def normalize_code(self, value) -> str:
        value = self._safe_str(value)
        if not value:
            return ""

        try:
            return str(int(float(value)))
        except Exception:
            return value.upper()

    def get_code_projet(self, parcel: Parcel) -> str:
        if parcel.program and getattr(parcel.program, "code", None):
            return self._safe_str(parcel.program.code)

        if parcel.program and getattr(parcel.program, "project", None):
            project = parcel.program.project
            if getattr(project, "code", None):
                return self._safe_str(project.code)

        return ""

    def get_lot_value(self, parcel: Parcel) -> str:
        if parcel.lot_number:
            return self.normalize_code(parcel.lot_number)

        if parcel.parcel_code:
            return self.normalize_code(parcel.parcel_code)

        return ""

    def get_ilot_value(self, parcel: Parcel) -> str:
        if parcel.block and getattr(parcel.block, "code", None):
            return self.normalize_code(parcel.block.code)
        return ""

    # =========================================================
    # BUILD BATCHES
    # =========================================================

    def build_batches(
        self,
        parcels,
    ) -> Tuple[
        Dict[str, List[str]],
        Dict[Tuple[str, str, str], int],
        Dict[Tuple[str, str], int],
    ]:
        grouped: Dict[str, List[str]] = defaultdict(list)
        parcel_lookup: Dict[Tuple[str, str, str], int] = {}
        parcel_lookup_simple: Dict[Tuple[str, str], int] = {}

        for parcel in parcels:
            code_projet = self.get_code_projet(parcel)
            ilot = self.get_ilot_value(parcel)
            lot = self.get_lot_value(parcel)

            if not code_projet or not lot:
                continue

            grouped[code_projet].append(lot)
            parcel_lookup[(code_projet, ilot, lot)] = parcel.id
            parcel_lookup_simple[(code_projet, lot)] = parcel.id

        for code_projet, lots in grouped.items():
            grouped[code_projet] = list(dict.fromkeys(lots))

        return grouped, parcel_lookup, parcel_lookup_simple

    # =========================================================
    # FETCH CRM
    # =========================================================

    def fetch_for_project(self, code_projet: str, lots: List[str]) -> List[dict]:
        payload = {
            "lots": json.dumps(lots),
            "codeProjet": code_projet,
        }

        logger.info("CRM lots fetch | project=%s | lots_count=%s", code_projet, len(lots))

        response = self.session.post(
            self.EXTERNAL_LOTS_API_URL,
            data=payload,
            timeout=self.TIMEOUT,
        )

        logger.info(
            "CRM lots response | project=%s | status=%s",
            code_projet,
            response.status_code,
        )

        response.raise_for_status()

        data = response.json()
        if not data or not data.get("status"):
            return []

        info_lot = data.get("infoLot")
        if not info_lot or info_lot is False:
            return []

        return info_lot

    def dedupe_info_lots(self, code_projet: str, info_lots: List[dict]) -> List[dict]:
        deduped: Dict[Tuple[str, str, str], dict] = {}

        for item in info_lots:
            lot = self.normalize_code(item.get("lot"))
            ilot = self.normalize_code(item.get("ilot"))
            code_retour = self._safe_str(item.get("code_projet")) or code_projet

            if not lot:
                continue

            key = (code_retour, ilot, lot)

            if key not in deduped:
                deduped[key] = item
                continue

            current_value = self._safe_decimal_2(item.get("valeur_hypothecaire"))
            existing_value = self._safe_decimal_2(deduped[key].get("valeur_hypothecaire"))

            if current_value >= existing_value:
                deduped[key] = item

        return list(deduped.values())

    # =========================================================
    # CRM PAYLOAD
    # =========================================================

    def build_crm_sync_payload(self, item: dict, code_projet: str, lot: str, ilot: str, now):
        valeur_hypothecaire = self._safe_decimal_2(item.get("valeur_hypothecaire"))
        avancement_travaux_mois = self._safe_float(item.get("avancement_travaux_mois"))

        cout_actif = self._safe_decimal_2(item.get("cout_actif"))
        versement_client = self._safe_decimal_2(item.get("versement_client"))
        ecart_status = self._safe_decimal_2(item.get("ecart_status"))

        nom = self._safe_str(item.get("nom"))
        prenom = self._safe_str(item.get("prenom"))
        client_nom_complet = " ".join([x for x in [prenom, nom] if x]).strip()

        return {
            "lot": lot,
            "ilot": ilot,
            "code_projet": code_projet,
            "valeur_hypothecaire": str(valeur_hypothecaire),
            "avancement_travaux_mois": avancement_travaux_mois,
            "nom": nom,
            "prenom": prenom,
            "client_nom_complet": client_nom_complet,
            "cout_actif": str(cout_actif),
            "versement_client": str(versement_client),
            "ecart_status": str(ecart_status),
            "synced_at": now.isoformat(),
            "raw": item,
        }

    # =========================================================
    # APPLY TO PARCEL
    # =========================================================

    def apply_sync_to_parcel(
        self,
        *,
        parcel: Parcel,
        item: dict,
        code_projet: str,
        lot: str,
        ilot: str,
        now,
    ) -> Parcel:
        metadata = parcel.metadata or {}

        sync_payload = self.build_crm_sync_payload(
            item=item,
            code_projet=code_projet,
            lot=lot,
            ilot=ilot,
            now=now,
        )

        metadata["crm_lot_sync"] = sync_payload

        # correction clé : on quantize avant sauvegarde du champ DecimalField
        parcel.valeur_hypothecaire = self._safe_decimal_2(sync_payload.get("valeur_hypothecaire"))
        parcel.metadata = metadata
        parcel.crm_last_synced_at = now

        parcel.save(update_fields=[
            "valeur_hypothecaire",
            "metadata",
            "crm_last_synced_at",
            "updated_at",
        ])
        return parcel

    # =========================================================
    # MAIN SYNC
    # =========================================================

    def sync_queryset(self, queryset):
        parcels = list(
            queryset.select_related("program", "program__project", "block")
        )

        grouped, parcel_lookup, parcel_lookup_simple = self.build_batches(parcels)
        if not grouped:
            return {
                "updated": 0,
                "projected": 0,
                "errors": 0,
                "skipped": len(parcels),
            }

        updated = 0
        projected = 0
        errors = 0
        skipped = 0

        parcels_by_id = {p.id: p for p in parcels}
        now = timezone.now()
        projection_service = ParcelCRMProjectionService()

        for code_projet, lots in grouped.items():
            for chunk in self.chunk_list(lots, size=self.CHUNK_SIZE):
                try:
                    info_lots = self.fetch_for_project(code_projet, chunk)
                    info_lots = self.dedupe_info_lots(code_projet, info_lots)

                    logger.info(
                        "CRM sync | project=%s | chunk_size=%s | rows_after_dedupe=%s",
                        code_projet,
                        len(chunk),
                        len(info_lots),
                    )

                    with transaction.atomic():
                        for item in info_lots:
                            lot = self.normalize_code(item.get("lot"))
                            ilot = self.normalize_code(item.get("ilot"))
                            code_retour = self._safe_str(item.get("code_projet")) or code_projet

                            parcel_id = parcel_lookup.get((code_retour, ilot, lot))
                            if not parcel_id:
                                parcel_id = parcel_lookup_simple.get((code_retour, lot))

                            if not parcel_id:
                                logger.warning(
                                    "CRM sync no match | project=%s | ilot=%s | lot=%s",
                                    code_retour,
                                    ilot,
                                    lot,
                                )
                                skipped += 1
                                continue

                            parcel = parcels_by_id.get(parcel_id)
                            if not parcel:
                                skipped += 1
                                continue

                            self.apply_sync_to_parcel(
                                parcel=parcel,
                                item=item,
                                code_projet=code_retour,
                                lot=lot,
                                ilot=ilot,
                                now=now,
                            )
                            updated += 1

                            projection_service.project_parcel(parcel)
                            projected += 1

                except Exception as exc:
                    errors += 1
                    logger.exception(
                        "CRM sync error | project=%s | chunk=%s | error=%s",
                        code_projet,
                        chunk,
                        exc,
                    )

        return {
            "updated": updated,
            "projected": projected,
            "errors": errors,
            "skipped": skipped,
        }

    # =========================================================
    # ENTRYPOINTS
    # =========================================================

    def sync_all_active_parcels(self):
        queryset = Parcel.objects.filter(
            is_active=True,
            program__is_active=True,
        ).select_related("program", "program__project", "block")

        return self.sync_queryset(queryset)


def sync_all_parcels():
    return KaydanCRMLotSyncService().sync_all_active_parcels()


def sync_program_parcels(program_id):
    queryset = Parcel.objects.filter(
        is_active=True,
        program__is_active=True,
        program_id=program_id,
    ).select_related("program", "program__project", "block")

    return KaydanCRMLotSyncService().sync_queryset(queryset)


def sync_stale_parcels(hours=24):
    threshold = timezone.now() - timezone.timedelta(hours=hours)

    queryset = Parcel.objects.filter(
        is_active=True,
        program__is_active=True,
    ).filter(
        models.Q(crm_last_synced_at__isnull=True) |
        models.Q(crm_last_synced_at__lt=threshold)
    ).select_related("program", "program__project", "block")

    return KaydanCRMLotSyncService().sync_queryset(queryset)

# # parcelaire/services/crm_lot_sync.py
# from __future__ import annotations
#
# import json
# from collections import defaultdict
# from decimal import Decimal
# from typing import Dict, List, Tuple
#
# import requests
# from django.db import models, transaction
# from django.utils import timezone
#
# from parcelaire.models import Parcel
# from parcelaire.services.crm_projection import ParcelCRMProjectionService
#
#
# class KaydanCRMLotSyncService:
#     EXTERNAL_LOTS_API_URL = "https://mykaydan.kaydangroupe.com/api/crm/lots"
#     EXTERNAL_LOTS_API_KEY = "5632d76ece5711436d3084a628f2afb03388a373"
#     EXTERNAL_LOTS_API_USERNAME = "admin"
#     EXTERNAL_LOTS_API_PASSWORD = "D@t@rium@1545#"
#
#     TIMEOUT = 20
#     CHUNK_SIZE = 20
#
#     def __init__(self):
#         self.session = requests.Session()
#         self.session.auth = (
#             self.EXTERNAL_LOTS_API_USERNAME,
#             self.EXTERNAL_LOTS_API_PASSWORD,
#         )
#         self.session.headers.update({
#             "X-API-KEY": self.EXTERNAL_LOTS_API_KEY,
#             "Accept": "application/json",
#         })
#
#     def chunk_list(self, values: List[str], size: int | None = None) -> List[List[str]]:
#         size = size or self.CHUNK_SIZE
#         return [values[i:i + size] for i in range(0, len(values), size)]
#
#     def _safe_str(self, value) -> str:
#         if value is None:
#             return ""
#         return str(value).strip()
#
#     def _safe_decimal(self, value) -> Decimal:
#         try:
#             if value in [None, ""]:
#                 return Decimal("0")
#             return Decimal(str(value))
#         except Exception:
#             return Decimal("0")
#
#     def _safe_float(self, value) -> float:
#         try:
#             if value in [None, ""]:
#                 return 0.0
#             return float(value)
#         except Exception:
#             return 0.0
#
#     def normalize_code(self, value) -> str:
#         value = self._safe_str(value)
#         if not value:
#             return ""
#
#         try:
#             return str(int(value))
#         except Exception:
#             return value.upper()
#
#     def get_code_projet(self, parcel: Parcel) -> str:
#         if parcel.program and getattr(parcel.program, "code", None):
#             return self._safe_str(parcel.program.code)
#
#         if parcel.program and getattr(parcel.program, "project", None):
#             project = parcel.program.project
#             if getattr(project, "code", None):
#                 return self._safe_str(project.code)
#
#         return ""
#
#     def get_lot_value(self, parcel: Parcel) -> str:
#         if parcel.lot_number:
#             return self.normalize_code(parcel.lot_number)
#
#         if parcel.parcel_code:
#             return self.normalize_code(parcel.parcel_code)
#
#         return ""
#
#     def get_ilot_value(self, parcel: Parcel) -> str:
#         if parcel.block and getattr(parcel.block, "code", None):
#             return self.normalize_code(parcel.block.code)
#         return ""
#
#     def build_batches(
#         self,
#         parcels,
#     ) -> Tuple[
#         Dict[str, List[str]],
#         Dict[Tuple[str, str, str], int],
#         Dict[Tuple[str, str], int],
#     ]:
#         grouped: Dict[str, List[str]] = defaultdict(list)
#         parcel_lookup: Dict[Tuple[str, str, str], int] = {}
#         parcel_lookup_simple: Dict[Tuple[str, str], int] = {}
#
#         for parcel in parcels:
#             code_projet = self.get_code_projet(parcel)
#             ilot = self.get_ilot_value(parcel)
#             lot = self.get_lot_value(parcel)
#
#             if not code_projet or not lot:
#                 continue
#
#             grouped[code_projet].append(lot)
#             parcel_lookup[(code_projet, ilot, lot)] = parcel.id
#             parcel_lookup_simple[(code_projet, lot)] = parcel.id
#
#         for code_projet, lots in grouped.items():
#             grouped[code_projet] = list(dict.fromkeys(lots))
#
#         return grouped, parcel_lookup, parcel_lookup_simple
#
#     def fetch_for_project(self, code_projet: str, lots: List[str]) -> List[dict]:
#         payload = {
#             "lots": json.dumps(lots),
#             "codeProjet": code_projet,
#         }
#
#         print("[CRM AUTH]", self.session.auth)
#         print("[CRM HEADERS]", {
#             "X-API-KEY": self.session.headers.get("X-API-KEY"),
#             "Accept": self.session.headers.get("Accept"),
#         })
#         print("[CRM REQUEST]", payload)
#
#         response = self.session.post(
#             self.EXTERNAL_LOTS_API_URL,
#             data=payload,
#             timeout=self.TIMEOUT,
#         )
#
#         print("[CRM STATUS]", response.status_code)
#         print("[CRM TEXT]", response.text)
#
#         response.raise_for_status()
#
#         data = response.json()
#         if not data or not data.get("status"):
#             return []
#
#         info_lot = data.get("infoLot")
#         if not info_lot or info_lot is False:
#             return []
#
#         return info_lot
#
#     def dedupe_info_lots(self, code_projet: str, info_lots: List[dict]) -> List[dict]:
#         deduped: Dict[Tuple[str, str, str], dict] = {}
#
#         for item in info_lots:
#             lot = self.normalize_code(item.get("lot"))
#             ilot = self.normalize_code(item.get("ilot"))
#             code_retour = self._safe_str(item.get("code_projet")) or code_projet
#
#             if not lot:
#                 continue
#
#             key = (code_retour, ilot, lot)
#
#             if key not in deduped:
#                 deduped[key] = item
#                 continue
#
#             current_value = self._safe_decimal(item.get("valeur_hypothecaire"))
#             existing_value = self._safe_decimal(deduped[key].get("valeur_hypothecaire"))
#
#             if current_value >= existing_value:
#                 deduped[key] = item
#
#         return list(deduped.values())
#
#     def build_crm_sync_payload(self, item: dict, code_projet: str, lot: str, ilot: str, now):
#         valeur_hypothecaire = self._safe_decimal(item.get("valeur_hypothecaire"))
#         avancement_travaux_mois = self._safe_float(item.get("avancement_travaux_mois"))
#
#         cout_actif = self._safe_decimal(item.get("cout_actif"))
#         versement_client = self._safe_decimal(item.get("versement_client"))
#         ecart_status = self._safe_decimal(item.get("ecart_status"))
#
#         nom = self._safe_str(item.get("nom"))
#         prenom = self._safe_str(item.get("prenom"))
#         client_nom_complet = " ".join([x for x in [prenom, nom] if x]).strip()
#
#         return {
#             "lot": lot,
#             "ilot": ilot,
#             "code_projet": code_projet,
#
#             "valeur_hypothecaire": str(valeur_hypothecaire),
#             "avancement_travaux_mois": avancement_travaux_mois,
#
#             "nom": nom,
#             "prenom": prenom,
#             "client_nom_complet": client_nom_complet,
#
#             "cout_actif": str(cout_actif),
#             "versement_client": str(versement_client),
#             "ecart_status": str(ecart_status),
#
#             "synced_at": now.isoformat(),
#             "raw": item,
#         }
#
#     def sync_queryset(self, queryset):
#         parcels = list(
#             queryset.select_related("program", "program__project", "block")
#         )
#
#         grouped, parcel_lookup, parcel_lookup_simple = self.build_batches(parcels)
#         if not grouped:
#             return {
#                 "updated": 0,
#                 "projected": 0,
#                 "errors": 0,
#                 "skipped": len(parcels),
#             }
#
#         updated = 0
#         projected = 0
#         errors = 0
#         skipped = 0
#
#         parcels_by_id = {p.id: p for p in parcels}
#         now = timezone.now()
#         projection_service = ParcelCRMProjectionService()
#
#         for code_projet, lots in grouped.items():
#             for chunk in self.chunk_list(lots, size=self.CHUNK_SIZE):
#                 try:
#                     info_lots = self.fetch_for_project(code_projet, chunk)
#                     info_lots = self.dedupe_info_lots(code_projet, info_lots)
#
#                     print(f"[SYNC] code_projet={code_projet} chunk={chunk} total_chunk={len(chunk)}")
#                     print(f"[SYNC] API returned {len(info_lots)} rows after dedupe")
#
#                     with transaction.atomic():
#                         for item in info_lots:
#                             lot = self.normalize_code(item.get("lot"))
#                             ilot = self.normalize_code(item.get("ilot"))
#                             code_retour = self._safe_str(item.get("code_projet")) or code_projet
#
#                             parcel_id = parcel_lookup.get((code_retour, ilot, lot))
#                             if not parcel_id:
#                                 parcel_id = parcel_lookup_simple.get((code_retour, lot))
#
#                             if not parcel_id:
#                                 print(f"[NO MATCH] code={code_retour}, ilot={ilot}, lot={lot}")
#                                 skipped += 1
#                                 continue
#
#                             parcel = parcels_by_id.get(parcel_id)
#                             if not parcel:
#                                 skipped += 1
#                                 continue
#
#                             metadata = parcel.metadata or {}
#                             metadata["crm_lot_sync"] = self.build_crm_sync_payload(
#                                 item=item,
#                                 code_projet=code_retour,
#                                 lot=lot,
#                                 ilot=ilot,
#                                 now=now,
#                             )
#
#                             parcel.metadata = metadata
#                             parcel.crm_last_synced_at = now
#                             parcel.save(update_fields=["metadata", "crm_last_synced_at", "updated_at"])
#                             updated += 1
#
#                             projection_service.project_parcel(parcel)
#                             projected += 1
#
#                 except Exception as exc:
#                     errors += 1
#                     print(f"[KaydanCRMLotSyncService] Erreur projet {code_projet}, chunk={chunk}: {exc}")
#
#         return {
#             "updated": updated,
#             "projected": projected,
#             "errors": errors,
#             "skipped": skipped,
#         }
#
#     def sync_all_active_parcels(self):
#         queryset = Parcel.objects.filter(
#             is_active=True,
#             program__is_active=True,
#         ).select_related("program", "program__project", "block")
#
#         return self.sync_queryset(queryset)
#
#
# def sync_all_parcels():
#     return KaydanCRMLotSyncService().sync_all_active_parcels()
#
#
# def sync_program_parcels(program_id):
#     queryset = Parcel.objects.filter(
#         is_active=True,
#         program__is_active=True,
#         program_id=program_id,
#     ).select_related("program", "program__project", "block")
#
#     return KaydanCRMLotSyncService().sync_queryset(queryset)
#
#
# def sync_stale_parcels(hours=24):
#     threshold = timezone.now() - timezone.timedelta(hours=hours)
#
#     queryset = Parcel.objects.filter(
#         is_active=True,
#         program__is_active=True,
#     ).filter(
#         models.Q(crm_last_synced_at__isnull=True) |
#         models.Q(crm_last_synced_at__lt=threshold)
#     ).select_related("program", "program__project", "block")
#
#     return KaydanCRMLotSyncService().sync_queryset(queryset)
#
