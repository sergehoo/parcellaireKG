from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Tuple

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from parcelaire.models import (
    Parcel,
    ConstructionProject,
    ConstructionUpdate,
    Customer,
    SaleFile,
    Payment,
)


class ParcelCRMProjectionService:
    PROJECT_STATUS = "IN_PROGRESS"
    UPDATE_STAGE = "OTHER"
    UPDATE_SUMMARY = "Synchronisation CRM"
    UPDATE_RECORDED_BY = "CRM_SYNC"

    CRM_PAYMENT_METHOD = "OTHER"
    CRM_PAYMENT_STATUS = "CONFIRMED"

    PLACEHOLDER_CUSTOMER_FIRST_NAME = "CLIENT"
    PLACEHOLDER_CUSTOMER_LAST_NAME_PREFIX = "CRM"

    # =========================================================
    # HELPERS
    # =========================================================

    def _safe_decimal(self, value) -> Decimal:
        try:
            if value in [None, ""]:
                return Decimal("0")
            return Decimal(str(value).replace(",", ".").strip())
        except (InvalidOperation, TypeError, ValueError, AttributeError):
            return Decimal("0")

    def _safe_float(self, value) -> float:
        try:
            if value in [None, ""]:
                return 0.0
            return float(str(value).replace(",", ".").strip())
        except Exception:
            return 0.0

    def _safe_str(self, value) -> str:
        if value is None:
            return ""
        try:
            return str(value).strip()
        except Exception:
            return ""

    def _quantize_2(self, value) -> Decimal:
        return self._safe_decimal(value).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def _crm_data(self, parcel: Parcel) -> dict:
        return (parcel.metadata or {}).get("crm_lot_sync", {}) or {}

    def _summary_data(self, crm: dict) -> dict:
        return (crm or {}).get("summary", {}) or {}

    def _units_data(self, crm: dict) -> List[dict]:
        units = (crm or {}).get("units", []) or []
        return units if isinstance(units, list) else []

    def _asset_type(self, crm: dict) -> str:
        value = self._safe_str((crm or {}).get("asset_type")).upper()
        return value or "SINGLE"

    def _asset_label(self, crm: dict) -> str:
        return self._safe_str((crm or {}).get("asset_label"))

    def _is_building(self, crm: dict) -> bool:
        return self._asset_type(crm) == "BUILDING"

    def _parent_reference(self, parcel: Parcel, crm: dict) -> Dict[str, str]:
        parent_ref = (crm or {}).get("parent_reference", {}) or {}

        lot = (
            self._safe_str(parent_ref.get("lot"))
            or self._safe_str(crm.get("lot"))
            or self._safe_str(parcel.lot_number)
            or self._safe_str(parcel.parcel_code)
            or str(parcel.id)
        )
        ilot = (
            self._safe_str(parent_ref.get("ilot"))
            or self._safe_str(crm.get("ilot"))
            or self._safe_str(getattr(parcel.block, "code", ""))
        )
        code_projet = (
            self._safe_str(parent_ref.get("code_projet"))
            or self._safe_str(crm.get("code_projet"))
            or self._safe_str(getattr(parcel.program, "code", ""))
        )

        return {
            "lot": lot,
            "ilot": ilot,
            "code_projet": code_projet,
        }

    def _project_code(self, parcel: Parcel, crm: dict) -> str:
        parent = self._parent_reference(parcel, crm)
        program_code = getattr(parcel.program, "code", None) or parent["code_projet"] or "PRG"
        lot_code = parent["lot"] or parcel.lot_number or parcel.parcel_code or str(parcel.id)
        asset_kind = "BUILDING" if self._is_building(crm) else "SINGLE"
        return f"CRM-{asset_kind}-{program_code}-{lot_code}-{parcel.id}"

    def _project_title(self, parcel: Parcel, crm: dict) -> str:
        parent = self._parent_reference(parcel, crm)
        lot = parent["lot"] or parcel.lot_number or parcel.parcel_code or str(parcel.id)
        asset_label = self._asset_label(crm)

        if self._is_building(crm):
            return f"Suivi CRM immeuble {asset_label or ''} lot {lot}".strip()
        return f"Suivi CRM lot {lot}"

    def _normalize_name(self, value: str) -> str:
        return " ".join(self._safe_str(value).upper().split())

    def _model_field_names(self, model_class):
        return {f.name for f in model_class._meta.fields}

    def _decimal_str(self, value) -> str:
        return str(self._quantize_2(value))

    def _build_update_details(
        self,
        parcel: Parcel,
        crm: dict,
        valeur_hypothecaire: Decimal,
        progress_raw: Decimal,
        cout_actif: Decimal,
        versement_client: Decimal,
        ecart_status: Decimal,
        payment_delta: Decimal,
        customer_name: str,
    ) -> str:
        parent = self._parent_reference(parcel, crm)
        ilot = parent["ilot"]
        lot = parent["lot"]
        code_projet = parent["code_projet"]
        asset_type = self._asset_type(crm)
        asset_label = self._asset_label(crm)
        units_count = len(self._units_data(crm))
        customers = crm.get("customers") or []

        lines = [
            f"Synchronisation CRM du {timezone.localdate():%d/%m/%Y}",
            f"Type actif CRM: {asset_type}",
            f"Libellé actif: {asset_label or '—'}",
            f"Lot parent: {lot}",
            f"Îlot parent: {ilot or '—'}",
            f"Code projet: {code_projet or '—'}",
            f"Client principal: {customer_name or '—'}",
            f"Valeur hypothécaire: {valeur_hypothecaire}",
            f"Avancement travaux mois: {progress_raw}",
            f"Coût actif: {cout_actif}",
            f"Cumul versements client: {versement_client}",
            f"Delta paiement intégré: {payment_delta}",
            f"Ecart status: {ecart_status}",
        ]

        if self._is_building(crm):
            lines.append(f"Nombre d'unités CRM: {units_count}")
            if customers:
                lines.append(
                    f"Clients CRM: {', '.join([self._safe_str(x) for x in customers if self._safe_str(x)])}"
                )

        return "\n".join(lines)

    def _extract_projection_values(self, crm: dict) -> Dict[str, Any]:
        summary = self._summary_data(crm)

        if summary:
            valeur_hypothecaire = self._quantize_2(summary.get("valeur_hypothecaire_totale"))
            progress_percent = self._quantize_2(summary.get("avancement_travaux_mois"))
            progress_raw = self._safe_decimal(summary.get("avancement_travaux_mois"))
            cout_actif = self._quantize_2(summary.get("cout_actif_total"))
            versement_client = self._quantize_2(summary.get("versement_client_total"))
            ecart_status = self._quantize_2(summary.get("ecart_status_global"))
        else:
            valeur_hypothecaire = self._quantize_2(crm.get("valeur_hypothecaire"))
            progress_percent = self._quantize_2(crm.get("avancement_travaux_mois"))
            progress_raw = self._safe_decimal(crm.get("avancement_travaux_mois"))
            cout_actif = self._quantize_2(crm.get("cout_actif"))
            versement_client = self._quantize_2(crm.get("versement_client"))
            ecart_status = self._quantize_2(crm.get("ecart_status"))

        return {
            "valeur_hypothecaire": valeur_hypothecaire,
            "progress_percent": progress_percent,
            "progress_raw": progress_raw,
            "cout_actif": cout_actif,
            "versement_client": versement_client,
            "ecart_status": ecart_status,
        }

    def _get_primary_unit_data(self, crm: dict) -> dict:
        units = self._units_data(crm)
        if units:
            return units[0] or {}
        return {}

    def _get_customer_candidates(self, crm: dict) -> List[dict]:
        if self._is_building(crm):
            units = self._units_data(crm)
            if units:
                return units
        primary = self._get_primary_unit_data(crm)
        return [primary or crm]

    def _get_display_customer_name_from_crm(self, crm: dict) -> str:
        if self._is_building(crm):
            customers = crm.get("customers") or []
            customers = [self._safe_str(x) for x in customers if self._safe_str(x)]
            if not customers:
                return ""
            if len(customers) == 1:
                return customers[0]
            return f"{len(customers)} clients"

        unit = self._get_primary_unit_data(crm) or crm
        full_name = self._safe_str(unit.get("client_nom_complet"))
        if full_name:
            return full_name

        prenom = self._safe_str(unit.get("client_prenom"))
        nom = self._safe_str(unit.get("client_nom"))
        return " ".join([x for x in [prenom, nom] if x]).strip()

    # =========================================================
    # CUSTOMER
    # =========================================================

    def _find_existing_customer_from_names(self, nom: str, prenom: str):
        nom_normalized = self._normalize_name(nom)
        prenom_normalized = self._normalize_name(prenom)

        if not nom_normalized and not prenom_normalized:
            return None

        qs = Customer.objects.filter(is_active=True)

        customer = qs.filter(
            customer_type="INDIVIDUAL",
            first_name__iexact=prenom_normalized,
            last_name__iexact=nom_normalized,
        ).first()
        if customer:
            return customer

        customer = qs.filter(
            customer_type="INDIVIDUAL",
            first_name__iexact=nom_normalized,
            last_name__iexact=prenom_normalized,
        ).first()
        if customer:
            return customer

        conditions = Q()
        if prenom_normalized:
            conditions &= Q(first_name__icontains=prenom_normalized)
        if nom_normalized:
            conditions &= Q(last_name__icontains=nom_normalized)

        if conditions:
            customer = qs.filter(customer_type="INDIVIDUAL").filter(conditions).first()
            if customer:
                return customer

        return None

    def _find_existing_customer(self, crm: dict):
        for candidate in self._get_customer_candidates(crm):
            nom = self._safe_str(candidate.get("client_nom") or candidate.get("nom"))
            prenom = self._safe_str(candidate.get("client_prenom") or candidate.get("prenom"))
            customer = self._find_existing_customer_from_names(nom, prenom)
            if customer:
                return customer
        return None

    def _build_placeholder_customer_identity(self, parcel: Parcel, crm: dict):
        parent = self._parent_reference(parcel, crm)
        lot = parent["lot"] or parcel.lot_number or parcel.parcel_code or str(parcel.id)
        program_code = getattr(parcel.program, "code", None) or parent["code_projet"] or "PRG"
        suffix = "BUILDING" if self._is_building(crm) else "LOT"
        first_name = self.PLACEHOLDER_CUSTOMER_FIRST_NAME
        last_name = f"{self.PLACEHOLDER_CUSTOMER_LAST_NAME_PREFIX}-{suffix}-{program_code}-{lot}-{parcel.id}"
        return first_name, last_name

    def _get_or_create_placeholder_customer(self, parcel: Parcel, crm: dict):
        first_name, last_name = self._build_placeholder_customer_identity(parcel, crm)

        customer = Customer.objects.filter(
            customer_type="INDIVIDUAL",
            first_name=first_name,
            last_name=last_name,
        ).first()

        if customer:
            return customer, False, False

        label = "immeuble" if self._is_building(crm) else "parcelle"
        customer = Customer.objects.create(
            customer_type="INDIVIDUAL",
            first_name=first_name,
            last_name=last_name,
            notes=(
                "Client placeholder créé automatiquement car le CRM n'a pas fourni "
                f"d'identité exploitable pour la {label} {parcel.id}."
            ),
        )
        return customer, True, False

    def _get_best_customer_identity(self, crm: dict) -> Tuple[str, str]:
        for candidate in self._get_customer_candidates(crm):
            nom = self._safe_str(candidate.get("client_nom") or candidate.get("nom"))
            prenom = self._safe_str(candidate.get("client_prenom") or candidate.get("prenom"))
            if nom or prenom:
                return nom, prenom
        return "", ""

    def _get_or_create_customer(self, parcel: Parcel, crm: dict):
        nom, prenom = self._get_best_customer_identity(crm)

        if not nom and not prenom:
            return self._get_or_create_placeholder_customer(parcel, crm)

        customer = self._find_existing_customer(crm)
        created = False
        updated = False

        if not customer:
            customer = Customer.objects.create(
                customer_type="INDIVIDUAL",
                first_name=prenom or None,
                last_name=nom or None,
                notes=(
                    "Client créé automatiquement via synchronisation CRM "
                    f"pour la parcelle {parcel.id}."
                ),
            )
            return customer, True, False

        update_fields = []

        if not customer.first_name and prenom:
            customer.first_name = prenom
            update_fields.append("first_name")

        if not customer.last_name and nom:
            customer.last_name = nom
            update_fields.append("last_name")

        if update_fields:
            update_fields.append("updated_at")
            customer.save(update_fields=update_fields)
            updated = True

        return customer, created, updated

    # =========================================================
    # SALE FILE
    # =========================================================

    def _generate_sale_number(self, parcel: Parcel, crm: dict) -> str:
        parent = self._parent_reference(parcel, crm)
        lot = parent["lot"] or parcel.lot_number or parcel.parcel_code or parcel.id
        program_code = getattr(parcel.program, "code", None) or parent["code_projet"] or "PRG"
        kind = "BUILDING" if self._is_building(crm) else "LOT"
        return f"SALE-CRM-{kind}-{program_code}-{lot}-{parcel.id}"

    def _generate_payment_number(self, sale_file: SaleFile, cumulative_amount: Decimal) -> str:
        cumulative_str = str(int(cumulative_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
        return f"PAY-CRM-{sale_file.id}-{cumulative_str}"

    def _sale_defaults_from_crm(self, parcel: Parcel, customer: Customer, crm: dict):
        field_names = self._model_field_names(SaleFile)
        values = self._extract_projection_values(crm)
        cout_actif = values["cout_actif"]
        defaults = {}

        if "sale_number" in field_names:
            defaults["sale_number"] = self._generate_sale_number(parcel, crm)

        if "program" in field_names:
            defaults["program"] = parcel.program

        if "customer" in field_names:
            defaults["customer"] = customer

        if "parcel" in field_names:
            defaults["parcel"] = parcel

        if "sale_date" in field_names:
            defaults["sale_date"] = timezone.localdate()

        if "agreed_price" in field_names:
            defaults["agreed_price"] = cout_actif

        if "net_price" in field_names:
            defaults["net_price"] = cout_actif

        if "notes" in field_names:
            if self._is_building(crm):
                defaults["notes"] = "Dossier immeuble créé automatiquement via synchronisation CRM."
            else:
                defaults["notes"] = "Dossier créé automatiquement via synchronisation CRM."

        if "metadata" in field_names:
            defaults["metadata"] = {
                "source": "crm_sync",
                "crm_snapshot": crm,
                "crm_asset_type": self._asset_type(crm),
                "crm_asset_label": self._asset_label(crm),
                "crm_units_count": len(self._units_data(crm)),
                "crm_parent_reference": self._parent_reference(parcel, crm),
            }

        return defaults

    def _get_or_create_sale_file(self, parcel: Parcel, customer: Customer, crm: dict):
        created = False
        updated = False

        sale = (
            SaleFile.objects.filter(parcel=parcel, is_active=True)
            .select_related("customer", "program", "parcel")
            .order_by("-created_at")
            .first()
        )

        values = self._extract_projection_values(crm)
        cout_actif = values["cout_actif"]

        if not sale:
            defaults = self._sale_defaults_from_crm(parcel, customer, crm)
            sale = SaleFile.objects.create(**defaults)
            return sale, True, False

        update_fields = []
        field_names = self._model_field_names(SaleFile)

        if "customer" in field_names and customer and sale.customer_id != customer.id:
            sale.customer = customer
            update_fields.append("customer")

        if "program" in field_names and parcel.program and sale.program_id != parcel.program_id:
            sale.program = parcel.program
            update_fields.append("program")

        if "parcel" in field_names and sale.parcel_id != parcel.id:
            sale.parcel = parcel
            update_fields.append("parcel")

        if "agreed_price" in field_names and cout_actif > 0 and self._safe_decimal(getattr(sale, "agreed_price", 0)) != cout_actif:
            sale.agreed_price = cout_actif
            update_fields.append("agreed_price")

        if "net_price" in field_names and cout_actif > 0 and self._safe_decimal(getattr(sale, "net_price", 0)) != cout_actif:
            sale.net_price = cout_actif
            update_fields.append("net_price")

        if "metadata" in field_names:
            metadata = getattr(sale, "metadata", None) or {}
            new_metadata = {
                **metadata,
                "source": "crm_sync",
                "crm_snapshot": crm,
                "crm_asset_type": self._asset_type(crm),
                "crm_asset_label": self._asset_label(crm),
                "crm_units_count": len(self._units_data(crm)),
                "crm_parent_reference": self._parent_reference(parcel, crm),
            }
            if metadata != new_metadata:
                sale.metadata = new_metadata
                update_fields.append("metadata")

        if update_fields:
            update_fields.append("updated_at")
            sale.save(update_fields=update_fields)
            updated = True

        return sale, created, updated

    # =========================================================
    # PAYMENT
    # =========================================================

    def _previous_cumulative_paid(self, project: ConstructionProject) -> Decimal:
        metadata = project.metadata or {}
        tracking = metadata.get("crm_payment_tracking", {}) or {}
        return self._quantize_2(tracking.get("last_cumulative_paid"))

    def _create_payment_from_delta(self, sale_file: SaleFile, payment_delta: Decimal, cumulative_paid: Decimal):
        if payment_delta <= 0:
            return None, False

        payment_number = self._generate_payment_number(sale_file, cumulative_paid)

        payment, created = Payment.objects.get_or_create(
            payment_number=payment_number,
            defaults={
                "sale_file": sale_file,
                "installment": None,
                "payment_date": timezone.localdate(),
                "amount": payment_delta,
                "payment_method": self.CRM_PAYMENT_METHOD,
                "reference": f"CRM_CUMUL_{str(cumulative_paid)}",
                "status": self.CRM_PAYMENT_STATUS,
                "received_by": self.UPDATE_RECORDED_BY,
                "notes": (
                    f"Paiement généré automatiquement depuis synchronisation CRM. "
                    f"Cumul traité: {cumulative_paid}. Delta intégré: {payment_delta}."
                ),
            },
        )
        return payment, created

    # =========================================================
    # MAIN PROJECTION
    # =========================================================

    @transaction.atomic
    def project_parcel(self, parcel: Parcel) -> dict:
        crm = self._crm_data(parcel)
        if not crm:
            return {
                "parcel_id": parcel.id,
                "asset_type": None,
                "project_created": False,
                "project_updated": False,
                "update_created": False,
                "update_updated": False,
                "parcel_updated": False,
                "customer_created": False,
                "customer_updated": False,
                "sale_created": False,
                "sale_updated": False,
                "payment_created": False,
                "payment_delta": "0.00",
                "skipped": True,
            }

        now = timezone.now()
        today = now.date()

        values = self._extract_projection_values(crm)
        valeur_hypothecaire = values["valeur_hypothecaire"]
        progress_raw = values["progress_raw"]
        progress_percent = values["progress_percent"]
        cout_actif = values["cout_actif"]
        versement_client = values["versement_client"]
        ecart_status = values["ecart_status"]

        customer, customer_created, customer_updated = self._get_or_create_customer(parcel, crm)

        if customer is None:
            customer, placeholder_created, _ = self._get_or_create_placeholder_customer(parcel, crm)
            customer_created = customer_created or placeholder_created

        sale_file, sale_created, sale_updated = self._get_or_create_sale_file(parcel, customer, crm)

        parcel_updated = False
        parcel_fields = []

        if parcel.valeur_hypothecaire != valeur_hypothecaire:
            parcel.valeur_hypothecaire = valeur_hypothecaire
            parcel_fields.append("valeur_hypothecaire")

        parcel.crm_last_synced_at = now
        parcel_fields.append("crm_last_synced_at")

        metadata = parcel.metadata or {}
        projection_meta = metadata.get("crm_projection", {}) or {}

        customer_name = str(customer) if customer else ""
        display_customer_name = self._get_display_customer_name_from_crm(crm)
        units_count = len(self._units_data(crm))
        customers = crm.get("customers") or []
        parent_reference = self._parent_reference(parcel, crm)

        new_projection_meta = {
            **projection_meta,
            "asset_type": self._asset_type(crm),
            "asset_label": self._asset_label(crm),
            "parent_reference": parent_reference,
            "customer_name": customer_name,
            "display_customer_name": display_customer_name or customer_name,
            "customer_id": customer.id if customer else None,
            "customers_count": len(customers) if isinstance(customers, list) else 0,
            "customers": customers if isinstance(customers, list) else [],
            "units_count": units_count,
            "cout_actif": str(cout_actif),
            "versement_client": str(versement_client),
            "ecart_status": str(ecart_status),
            "valeur_hypothecaire": str(valeur_hypothecaire),
            "progress_percent": str(progress_percent),
            "updated_at": now.isoformat(),
        }

        if metadata.get("crm_projection") != new_projection_meta:
            metadata["crm_projection"] = new_projection_meta
            parcel.metadata = metadata
            parcel_fields.append("metadata")

        if parcel_fields:
            parcel_fields.append("updated_at")
            parcel.save(update_fields=parcel_fields)
            parcel_updated = True

        project, project_created = ConstructionProject.objects.get_or_create(
            parcel=parcel,
            code=self._project_code(parcel, crm),
            defaults={
                "title": self._project_title(parcel, crm),
                "description": "Projet technique généré automatiquement depuis les données CRM.",
                "status": self.PROJECT_STATUS,
                "progress_percent": progress_percent,
                "actual_start_date": today,
                "estimated_budget": cout_actif if cout_actif > 0 else None,
                "metadata": {
                    "source": "crm_sync",
                    "crm_snapshot": crm,
                    "crm_asset_type": self._asset_type(crm),
                    "crm_asset_label": self._asset_label(crm),
                    "crm_units_count": units_count,
                    "crm_parent_reference": parent_reference,
                    "crm_payment_tracking": {
                        "last_cumulative_paid": "0.00",
                        "updated_at": now.isoformat(),
                    },
                },
            },
        )

        previous_cumulative = self._previous_cumulative_paid(project)
        payment_delta = versement_client - previous_cumulative

        if payment_delta < 0:
            payment_delta = Decimal("0.00")

        payment_obj, payment_created = self._create_payment_from_delta(
            sale_file=sale_file,
            payment_delta=payment_delta,
            cumulative_paid=versement_client,
        )

        project_updated = False
        project_fields = []

        if project.title != self._project_title(parcel, crm):
            project.title = self._project_title(parcel, crm)
            project_fields.append("title")

        if project.status != self.PROJECT_STATUS:
            project.status = self.PROJECT_STATUS
            project_fields.append("status")

        if self._safe_decimal(project.progress_percent or 0) != progress_percent:
            project.progress_percent = progress_percent
            project_fields.append("progress_percent")

        if "estimated_budget" in self._model_field_names(ConstructionProject):
            current_budget = self._safe_decimal(getattr(project, "estimated_budget", 0))
            if cout_actif > 0 and current_budget != cout_actif:
                project.estimated_budget = cout_actif
                project_fields.append("estimated_budget")

        project_metadata = project.metadata or {}
        primary_unit = self._get_primary_unit_data(crm)

        new_project_metadata = {
            **project_metadata,
            "source": "crm_sync",
            "crm_snapshot": crm,
            "crm_asset_type": self._asset_type(crm),
            "crm_asset_label": self._asset_label(crm),
            "crm_units_count": units_count,
            "crm_parent_reference": parent_reference,
            "crm_customer": {
                "nom": self._safe_str(primary_unit.get("client_nom") or crm.get("nom")),
                "prenom": self._safe_str(primary_unit.get("client_prenom") or crm.get("prenom")),
                "display": display_customer_name or customer_name,
                "customer_id": customer.id if customer else None,
                "customers": customers if isinstance(customers, list) else [],
                "is_placeholder": (
                    customer.first_name == self.PLACEHOLDER_CUSTOMER_FIRST_NAME
                    and str(customer.last_name).startswith(self.PLACEHOLDER_CUSTOMER_LAST_NAME_PREFIX)
                ) if customer else False,
            },
            "crm_finance": {
                "cout_actif": str(cout_actif),
                "versement_client": str(versement_client),
                "ecart_status": str(ecart_status),
                "valeur_hypothecaire": str(valeur_hypothecaire),
            },
            "crm_payment_tracking": {
                "last_cumulative_paid": str(versement_client),
                "updated_at": now.isoformat(),
            },
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

        _, update_created = ConstructionUpdate.objects.update_or_create(
            construction_project=project,
            report_date=today,
            recorded_by=self.UPDATE_RECORDED_BY,
            defaults={
                "stage": self.UPDATE_STAGE,
                "progress_percent": progress_percent,
                "summary": self.UPDATE_SUMMARY,
                "details": self._build_update_details(
                    parcel=parcel,
                    crm=crm,
                    valeur_hypothecaire=valeur_hypothecaire,
                    progress_raw=progress_raw,
                    cout_actif=cout_actif,
                    versement_client=versement_client,
                    ecart_status=ecart_status,
                    payment_delta=payment_delta,
                    customer_name=display_customer_name or customer_name,
                ),
                "issues": "",
                "next_actions": "",
                "weather_notes": "",
                "asset": None,
            },
        )

        update_updated = not update_created

        return {
            "parcel_id": parcel.id,
            "asset_type": self._asset_type(crm),
            "asset_label": self._asset_label(crm),
            "units_count": units_count,
            "project_created": project_created,
            "project_updated": project_updated,
            "update_created": update_created,
            "update_updated": update_updated,
            "parcel_updated": parcel_updated,
            "customer_created": customer_created,
            "customer_updated": customer_updated,
            "sale_created": sale_created,
            "sale_updated": sale_updated,
            "payment_created": payment_created,
            "payment_id": payment_obj.id if payment_obj else None,
            "payment_delta": str(payment_delta),
            "previous_cumulative": str(previous_cumulative),
            "new_cumulative": str(versement_client),
            "skipped": False,
        }

    def project_queryset(self, queryset):
        results = []
        for parcel in queryset:
            results.append(self.project_parcel(parcel))
        return results