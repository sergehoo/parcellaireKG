# parcelaire/services/crm_lot_sync.py
from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from django.core.exceptions import ImproperlyConfigured
from django.db import models, transaction
from django.utils import timezone

from parcelaire.models import Parcel
from parcelaire.services.crm_projection import ParcelCRMProjectionService

logger = logging.getLogger(__name__)


class KaydanCRMLotSyncService:
    """
    Synchronise les données CRM des lots/parcelles.

    Règles métier :

    1) SINGLE / Villa
       - une seule ligne CRM
       - les champs métier de la ligne représentent l'actif lui-même
       - les champs unitaire_* correspondent au parent, mais dans ce cas ils recouvrent
         généralement les mêmes valeurs

    2) BUILDING / Immeuble / Bloc
       - plusieurs lignes CRM pour une même parcelle terrain
       - la parcelle terrain est identifiée par :
            * unitaire_code_projet
            * unitaire_ilot
            * unitaire_lot
       - les champs unitaire_* = données parent agrégées de l'immeuble
       - les champs non unitaire_* = données individualisées de chaque appartement / unité

    Important :
    - le champ `lot` d'une ligne CRM peut correspondre au lot d'un appartement et non
      au lot de la parcelle terrain ; il ne doit donc pas être utilisé en priorité
      pour la cartographie lorsqu'unitaire_lot est disponible.
    """
    def env_required(name):

        value = os.getenv(name)

        if not value:
            raise ImproperlyConfigured(f"La variable d'environnement {name} est requise.")

        return value

    EXTERNAL_LOTS_API_URL = env_required("EXTERNAL_LOTS_API_URL")
    EXTERNAL_LOTS_API_KEY = env_required("EXTERNAL_LOTS_API_KEY")
    EXTERNAL_LOTS_API_USERNAME = env_required("EXTERNAL_LOTS_API_USERNAME")
    EXTERNAL_LOTS_API_PASSWORD = env_required("EXTERNAL_LOTS_API_PASSWORD")
    TIMEOUT = 20
    CHUNK_SIZE = 20

    BUILDING_KEYWORDS = (
        "BLOC",
        "BLOCK",
        "IMMEUBLE",
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.auth = (
            self.EXTERNAL_LOTS_API_USERNAME,
            self.EXTERNAL_LOTS_API_PASSWORD,
        )
        self.session.headers.update(
            {
                "X-API-KEY": self.EXTERNAL_LOTS_API_KEY,
                "Accept": "application/json",
            }
        )

    # =========================================================
    # SAFE HELPERS
    # =========================================================

    def chunk_list(self, values: List[str], size: Optional[int] = None) -> List[List[str]]:
        size = size or self.CHUNK_SIZE
        if size <= 0:
            size = self.CHUNK_SIZE
        return [values[i: i + size] for i in range(0, len(values), size)]

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        try:
            return str(value).strip()
        except Exception:
            return ""

    def _safe_decimal(self, value: Any, default: str = "0") -> Decimal:
        try:
            if value in [None, ""]:
                return Decimal(default)
            return Decimal(str(value).replace(",", ".").strip())
        except (InvalidOperation, TypeError, ValueError, AttributeError):
            return Decimal(default)

    def _safe_decimal_2(self, value: Any, default: str = "0.00") -> Decimal:
        return self._safe_decimal(value, default=default).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def _safe_float(self, value: Any) -> float:
        try:
            if value in [None, ""]:
                return 0.0
            return float(str(value).replace(",", ".").strip())
        except Exception:
            return 0.0

    def _safe_int(self, value: Any, default: int = 0) -> int:
        try:
            if value in [None, ""]:
                return default
            return int(float(str(value).replace(",", ".").strip()))
        except Exception:
            return default

    def _decimal_to_str(self, value: Decimal) -> str:
        try:
            return str(
                value.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
            )
        except Exception:
            return "0.00"

    def _unique_preserve_order(self, values: Iterable[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            item = self._safe_str(value)
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def normalize_code(self, value: Any) -> str:
        value = self._safe_str(value)
        if not value:
            return ""

        try:
            return str(int(float(value)))
        except Exception:
            return value.upper()

    def normalize_text_key(self, value: Any) -> str:
        text = self._safe_str(value).upper()
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def get_code_projet(self, parcel: Parcel) -> str:
        try:
            if parcel.program and getattr(parcel.program, "code", None):
                return self._safe_str(parcel.program.code)

            if parcel.program and getattr(parcel.program, "project", None):
                project = parcel.program.project
                if getattr(project, "code", None):
                    return self._safe_str(project.code)
        except Exception:
            pass

        return ""

    def get_lot_value(self, parcel: Parcel) -> str:
        try:
            if getattr(parcel, "lot_number", None):
                return self.normalize_code(parcel.lot_number)

            if getattr(parcel, "parcel_code", None):
                return self.normalize_code(parcel.parcel_code)
        except Exception:
            pass

        return ""

    def get_ilot_value(self, parcel: Parcel) -> str:
        try:
            if parcel.block and getattr(parcel.block, "code", None):
                return self.normalize_code(parcel.block.code)
        except Exception:
            pass
        return ""

    def is_building_label(self, label: Any) -> bool:
        text = self.normalize_text_key(label)
        if not text:
            return False
        return any(keyword in text for keyword in self.BUILDING_KEYWORDS)

    def get_parent_project_code(self, item: dict, fallback_code_projet: str = "") -> str:
        return (
            self._safe_str(item.get("unitaire_code_projet"))
            or self._safe_str(item.get("code_projet"))
            or self._safe_str(fallback_code_projet)
        )

    def get_parent_lot(self, item: dict) -> str:
        # priorité à la parcelle terrain
        return self.normalize_code(item.get("unitaire_lot")) or self.normalize_code(item.get("lot"))

    def get_parent_ilot(self, item: dict) -> str:
        # priorité à la parcelle terrain
        return self.normalize_code(item.get("unitaire_ilot")) or self.normalize_code(item.get("ilot"))

    # =========================================================
    # BUILD BATCHES
    # =========================================================

    def build_batches(
        self,
        parcels: Iterable[Parcel],
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
        if not isinstance(data, dict) or not data.get("status"):
            return []

        info_lot = data.get("infoLot")
        if not info_lot or info_lot is False:
            return []

        if not isinstance(info_lot, list):
            return []

        return info_lot

    # =========================================================
    # CRM GROUPING / NORMALIZATION
    # =========================================================

    def build_parent_group_key(self, item: dict, fallback_code_projet: str) -> Tuple[str, str, str]:
        """
        Clé terrain / parent.
        On utilise impérativement unitaire_* si disponible.
        """
        code_retour = self.get_parent_project_code(item, fallback_code_projet)
        ilot = self.get_parent_ilot(item)
        lot = self.get_parent_lot(item)
        return code_retour, ilot, lot

    def build_unit_identity_key(self, item: dict, fallback_code_projet: str) -> Tuple[str, str, str, str, str, str, str]:
        """
        Clé de déduplication d'une unité / ligne CRM.
        Ne doit PAS utiliser unitaire_lot pour distinguer les appartements.
        """
        parent_code, parent_ilot, parent_lot = self.build_parent_group_key(item, fallback_code_projet)

        raw_lot = self.normalize_code(item.get("lot"))
        raw_ilot = self.normalize_code(item.get("ilot"))
        nom = self.normalize_text_key(item.get("nom"))
        prenom = self.normalize_text_key(item.get("prenom"))
        cout_actif = self._decimal_to_str(self._safe_decimal_2(item.get("cout_actif")))
        versement_client = self._decimal_to_str(self._safe_decimal_2(item.get("versement_client")))

        return (
            parent_code,
            parent_ilot,
            parent_lot,
            raw_ilot,
            raw_lot,
            f"{prenom} {nom}".strip(),
            f"{cout_actif}|{versement_client}",
        )

    def is_building_group(self, rows: List[dict]) -> bool:
        if len(rows) > 1:
            return True

        if not rows:
            return False

        label = self._safe_str(rows[0].get("unitaire_libelle_type_lot"))
        return self.is_building_label(label)

    def group_info_lots(self, code_projet: str, info_lots: List[dict]) -> Dict[Tuple[str, str, str], List[dict]]:
        """
        Groupe les réponses CRM par parcelle parent (unitaire_code_projet, unitaire_ilot, unitaire_lot).
        À l'intérieur d'un groupe :
        - plusieurs lignes => immeuble / appartements
        - une ligne => single ou building mono-ligne, selon unitaire_libelle_type_lot
        """
        grouped: Dict[Tuple[str, str, str], Dict[Tuple[str, str, str, str, str, str, str], dict]] = defaultdict(dict)

        for item in info_lots:
            parent_key = self.build_parent_group_key(item, code_projet)
            code_retour, ilot, lot = parent_key

            if not code_retour or not lot:
                continue

            row_key = self.build_unit_identity_key(item, code_projet)
            existing = grouped[parent_key].get(row_key)

            if not existing:
                grouped[parent_key][row_key] = item
                continue

            current_paid = self._safe_decimal_2(item.get("versement_client"))
            existing_paid = self._safe_decimal_2(existing.get("versement_client"))

            current_cost = self._safe_decimal_2(item.get("cout_actif"))
            existing_cost = self._safe_decimal_2(existing.get("cout_actif"))

            current_score = (current_paid, current_cost)
            existing_score = (existing_paid, existing_cost)

            if current_score >= existing_score:
                grouped[parent_key][row_key] = item

        return {key: list(rows.values()) for key, rows in grouped.items()}

    # =========================================================
    # CRM PAYLOAD BUILDERS
    # =========================================================

    def build_single_unit_payload(
        self,
        *,
        item: dict,
        code_projet: str,
        lot: str,
        ilot: str,
        unit_index: int = 1,
    ) -> Dict[str, Any]:
        valeur_hypothecaire = self._safe_decimal_2(item.get("valeur_hypothecaire"))
        avancement_travaux_mois = self._safe_float(item.get("avancement_travaux_mois"))
        cout_actif = self._safe_decimal_2(item.get("cout_actif"))
        versement_client = self._safe_decimal_2(item.get("versement_client"))
        ecart_status = self._safe_decimal_2(item.get("ecart_status"))

        nom = self._safe_str(item.get("nom"))
        prenom = self._safe_str(item.get("prenom"))
        client_nom_complet = " ".join([x for x in [prenom, nom] if x]).strip()

        unit_lot = self.normalize_code(item.get("lot"))
        unit_ilot = self.normalize_code(item.get("ilot"))
        unit_type_label = self._safe_str(item.get("unitaire_libelle_type_lot")) or "Unité"

        return {
            "index": unit_index,
            "lot_parent": lot,
            "ilot_parent": ilot,
            "code_projet_parent": code_projet,
            "lot": unit_lot,
            "ilot": unit_ilot,
            "code_projet": self._safe_str(item.get("code_projet")) or code_projet,
            "client_nom": nom,
            "client_prenom": prenom,
            "client_nom_complet": client_nom_complet,
            "cout_actif": self._decimal_to_str(cout_actif),
            "versement_client": self._decimal_to_str(versement_client),
            "valeur_hypothecaire": self._decimal_to_str(valeur_hypothecaire),
            "avancement_travaux_mois": avancement_travaux_mois,
            "ecart_status": self._decimal_to_str(ecart_status),
            "asset_label": unit_type_label,
            "raw": item,
        }

    def build_building_payload(
        self,
        *,
        items: List[dict],
        code_projet: str,
        lot: str,
        ilot: str,
    ) -> Dict[str, Any]:
        """
        Construit une vue agrégée d'un immeuble.
        Les champs unitaire_* sont considérés comme les valeurs parent agrégées.
        Les champs non unitaire_* décrivent les unités.
        """
        units: List[Dict[str, Any]] = []
        customers: List[str] = []

        first = items[0] if items else {}

        parent_hypo = self._safe_decimal_2(first.get("unitaire_valeur_hypothecaire"))
        parent_paid = self._safe_decimal_2(first.get("unitaire_versement_client"))
        parent_progress = self._safe_float(first.get("unitaire_avancement_travaux_mois"))
        parent_gap = self._safe_decimal_2(first.get("unitaire_ecart_status"))
        parent_type_label = self._safe_str(first.get("unitaire_libelle_type_lot")) or "Immeuble"

        sum_unit_hypo = Decimal("0.00")
        sum_unit_paid = Decimal("0.00")
        sum_unit_cost = Decimal("0.00")
        avg_progress_source: List[float] = []

        for index, item in enumerate(items, start=1):
            unit_payload = self.build_single_unit_payload(
                item=item,
                code_projet=code_projet,
                lot=lot,
                ilot=ilot,
                unit_index=index,
            )

            # libellé unité plus utile
            raw_unit_lot = self.normalize_code(item.get("lot"))
            raw_unit_ilot = self.normalize_code(item.get("ilot"))
            client_label = unit_payload.get("client_nom_complet") or f"Unité {index}"

            if raw_unit_lot and raw_unit_lot != lot:
                unit_payload["label"] = f"Appartement {raw_unit_lot}"
            elif raw_unit_ilot and raw_unit_lot:
                unit_payload["label"] = f"Appartement {raw_unit_ilot}-{raw_unit_lot}"
            else:
                unit_payload["label"] = f"Appartement {index}"

            unit_payload["display_label"] = unit_payload["label"]
            unit_payload["building_label"] = parent_type_label
            units.append(unit_payload)

            sum_unit_hypo += self._safe_decimal_2(item.get("valeur_hypothecaire"))
            sum_unit_paid += self._safe_decimal_2(item.get("versement_client"))
            sum_unit_cost += self._safe_decimal_2(item.get("cout_actif"))
            avg_progress_source.append(self._safe_float(item.get("avancement_travaux_mois")))

            if client_label:
                customers.append(client_label)

        total_hypo = parent_hypo if parent_hypo > 0 else sum_unit_hypo
        total_paid = parent_paid if parent_paid > 0 else sum_unit_paid
        total_cost = sum_unit_cost
        total_progress = parent_progress if parent_progress > 0 else (
            sum(avg_progress_source) / len(avg_progress_source) if avg_progress_source else 0.0
        )
        total_gap = parent_gap

        return {
            "lot": lot,
            "ilot": ilot,
            "code_projet": code_projet,
            "asset_type": "BUILDING",
            "asset_label": parent_type_label,
            "units_count": len(units),
            "customers_count": len(self._unique_preserve_order(customers)),
            "customers": self._unique_preserve_order(customers),
            "summary": {
                "cout_actif_total": self._decimal_to_str(total_cost),
                "versement_client_total": self._decimal_to_str(total_paid),
                "valeur_hypothecaire_totale": self._decimal_to_str(total_hypo),
                "avancement_travaux_mois": total_progress,
                "ecart_status_global": self._decimal_to_str(total_gap),
            },
            "units": units,
            "raw": items,
        }

    def build_sync_payload(
        self,
        *,
        items: List[dict],
        code_projet: str,
        lot: str,
        ilot: str,
        now,
    ) -> Dict[str, Any]:
        is_building = self.is_building_group(items)

        if is_building:
            payload = self.build_building_payload(
                items=items,
                code_projet=code_projet,
                lot=lot,
                ilot=ilot,
            )
        else:
            single = self.build_single_unit_payload(
                item=items[0],
                code_projet=code_projet,
                lot=lot,
                ilot=ilot,
                unit_index=1,
            )

            parent_type_label = self._safe_str(items[0].get("unitaire_libelle_type_lot")) or "Lot"

            payload = {
                "lot": lot,
                "ilot": ilot,
                "code_projet": code_projet,
                "asset_type": "SINGLE",
                "asset_label": parent_type_label,
                "units_count": 1,
                "customers_count": 1 if single.get("client_nom_complet") else 0,
                "customers": [single["client_nom_complet"]] if single.get("client_nom_complet") else [],
                "summary": {
                    "cout_actif_total": single["cout_actif"],
                    "versement_client_total": single["versement_client"],
                    "valeur_hypothecaire_totale": single["valeur_hypothecaire"],
                    "avancement_travaux_mois": single["avancement_travaux_mois"],
                    "ecart_status_global": single["ecart_status"],
                },
                "units": [single],
                "raw": items,
            }

        payload["synced_at"] = now.isoformat()
        payload["crm_rows_count"] = len(items)
        payload["parent_reference"] = {
            "code_projet": code_projet,
            "ilot": ilot,
            "lot": lot,
        }
        return payload

    # =========================================================
    # APPLY TO PARCEL
    # =========================================================

    def get_parcel_decimal_value_from_payload(self, payload: Dict[str, Any]) -> Decimal:
        try:
            summary = payload.get("summary", {}) or {}
            return self._safe_decimal_2(summary.get("valeur_hypothecaire_totale"))
        except Exception:
            return Decimal("0.00")

    def apply_sync_to_parcel(
        self,
        *,
        parcel: Parcel,
        items: List[dict],
        code_projet: str,
        lot: str,
        ilot: str,
        now,
    ) -> Parcel:
        metadata = dict(parcel.metadata or {})

        sync_payload = self.build_sync_payload(
            items=items,
            code_projet=code_projet,
            lot=lot,
            ilot=ilot,
            now=now,
        )

        metadata["crm_lot_sync"] = sync_payload

        parcel.valeur_hypothecaire = self.get_parcel_decimal_value_from_payload(sync_payload)
        parcel.metadata = metadata
        parcel.crm_last_synced_at = now

        update_fields = [
            "valeur_hypothecaire",
            "metadata",
            "crm_last_synced_at",
        ]

        if hasattr(parcel, "updated_at"):
            update_fields.append("updated_at")

        parcel.save(update_fields=update_fields)
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
                "buildings_detected": 0,
                "single_lots_detected": 0,
            }

        updated = 0
        projected = 0
        errors = 0
        skipped = 0
        buildings_detected = 0
        single_lots_detected = 0

        parcels_by_id = {p.id: p for p in parcels}
        now = timezone.now()
        projection_service = ParcelCRMProjectionService()

        for code_projet, lots in grouped.items():
            for chunk in self.chunk_list(lots, size=self.CHUNK_SIZE):
                try:
                    info_lots = self.fetch_for_project(code_projet, chunk)
                    grouped_rows = self.group_info_lots(code_projet, info_lots)

                    logger.info(
                        "CRM sync | project=%s | chunk_size=%s | grouped_rows=%s",
                        code_projet,
                        len(chunk),
                        len(grouped_rows),
                    )

                    with transaction.atomic():
                        for (code_retour, ilot, lot), rows in grouped_rows.items():
                            parcel_id = parcel_lookup.get((code_retour, ilot, lot))
                            if not parcel_id:
                                parcel_id = parcel_lookup_simple.get((code_retour, lot))

                            if not parcel_id:
                                logger.warning(
                                    "CRM sync no match | project=%s | ilot=%s | lot=%s | rows=%s",
                                    code_retour,
                                    ilot,
                                    lot,
                                    len(rows),
                                )
                                skipped += 1
                                continue

                            parcel = parcels_by_id.get(parcel_id)
                            if not parcel:
                                skipped += 1
                                continue

                            if self.is_building_group(rows):
                                buildings_detected += 1
                            else:
                                single_lots_detected += 1

                            self.apply_sync_to_parcel(
                                parcel=parcel,
                                items=rows,
                                code_projet=code_retour,
                                lot=lot,
                                ilot=ilot,
                                now=now,
                            )
                            updated += 1

                            try:
                                projection_service.project_parcel(parcel)
                                projected += 1
                            except Exception as projection_exc:
                                logger.exception(
                                    "CRM projection error | parcel_id=%s | project=%s | ilot=%s | lot=%s | error=%s",
                                    parcel.id,
                                    code_retour,
                                    ilot,
                                    lot,
                                    projection_exc,
                                )

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
            "buildings_detected": buildings_detected,
            "single_lots_detected": single_lots_detected,
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
        models.Q(crm_last_synced_at__isnull=True)
        | models.Q(crm_last_synced_at__lt=threshold)
    ).select_related("program", "program__project", "block")

    return KaydanCRMLotSyncService().sync_queryset(queryset)