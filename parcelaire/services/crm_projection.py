# parcelaire/services/crm_projection.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from parcelaire.models import (
    Parcel,
    ConstructionProject,
    ConstructionUpdate, Customer, SaleFile, Payment,
)


# class ParcelCRMProjectionService:
#     PROJECT_STATUS = "IN_PROGRESS"
#     UPDATE_STAGE = "OTHER"
#     UPDATE_SUMMARY = "Synchronisation CRM"
#     UPDATE_RECORDED_BY = "CRM_SYNC"
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
#     def _quantize_2(self, value) -> Decimal:
#         return self._safe_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
#
#     def _crm_data(self, parcel: Parcel) -> dict:
#         return (parcel.metadata or {}).get("crm_lot_sync", {}) or {}
#
#     def _project_code(self, parcel: Parcel) -> str:
#         program_code = getattr(parcel.program, "code", None) or "PRG"
#         lot_code = parcel.lot_number or parcel.parcel_code or str(parcel.id)
#         return f"CRM-{program_code}-{lot_code}-{parcel.id}"
#
#     def _project_title(self, parcel: Parcel) -> str:
#         lot = parcel.lot_number or parcel.parcel_code or str(parcel.id)
#         return f"Suivi CRM lot {lot}"
#
#     def _build_update_details(self, parcel: Parcel, crm: dict, valeur_hypothecaire: Decimal, progress_raw: Decimal) -> str:
#         ilot = crm.get("ilot") or (parcel.block.code if parcel.block else "")
#         lot = crm.get("lot") or parcel.lot_number or parcel.parcel_code or ""
#         code_projet = crm.get("code_projet") or getattr(parcel.program, "code", "")
#
#         return (
#             f"Synchronisation CRM du {timezone.localdate():%d/%m/%Y}\n"
#             f"Lot: {lot}\n"
#             f"Îlot: {ilot}\n"
#             f"Code projet: {code_projet}\n"
#             f"Valeur hypothécaire: {valeur_hypothecaire}\n"
#             f"Avancement travaux mois: {progress_raw}"
#         )
#
#     @transaction.atomic
#     def project_parcel(self, parcel: Parcel) -> dict:
#         crm = self._crm_data(parcel)
#         if not crm:
#             return {
#                 "parcel_id": parcel.id,
#                 "project_created": False,
#                 "project_updated": False,
#                 "update_created": False,
#                 "update_updated": False,
#                 "parcel_updated": False,
#                 "skipped": True,
#             }
#
#         now = timezone.now()
#         today = now.date()
#
#         valeur_hypothecaire = self._quantize_2(crm.get("valeur_hypothecaire"))
#         progress_raw = self._safe_decimal(crm.get("avancement_travaux_mois"))
#         progress_percent = self._quantize_2(crm.get("avancement_travaux_mois"))
#
#         parcel_updated = False
#         parcel_fields = []
#
#         if parcel.valeur_hypothecaire != valeur_hypothecaire:
#             parcel.valeur_hypothecaire = valeur_hypothecaire
#             parcel_fields.append("valeur_hypothecaire")
#
#         parcel.crm_last_synced_at = now
#         parcel_fields.append("crm_last_synced_at")
#
#         if parcel_fields:
#             parcel_fields.append("updated_at")
#             parcel.save(update_fields=parcel_fields)
#             parcel_updated = True
#
#         project, project_created = ConstructionProject.objects.get_or_create(
#             parcel=parcel,
#             code=self._project_code(parcel),
#             defaults={
#                 "title": self._project_title(parcel),
#                 "description": "Projet technique généré automatiquement depuis les données CRM.",
#                 "status": self.PROJECT_STATUS,
#                 "progress_percent": progress_percent,
#                 "actual_start_date": today,
#                 "metadata": {
#                     "source": "crm_sync",
#                     "crm_snapshot": crm,
#                 },
#             },
#         )
#
#         project_updated = False
#         project_fields = []
#
#         if project.title != self._project_title(parcel):
#             project.title = self._project_title(parcel)
#             project_fields.append("title")
#
#         if project.status != self.PROJECT_STATUS:
#             project.status = self.PROJECT_STATUS
#             project_fields.append("status")
#
#         if self._safe_decimal(project.progress_percent or 0) != progress_percent:
#             project.progress_percent = progress_percent
#             project_fields.append("progress_percent")
#
#         project_metadata = project.metadata or {}
#         new_project_metadata = {
#             **project_metadata,
#             "source": "crm_sync",
#             "crm_snapshot": crm,
#         }
#
#         if project.metadata != new_project_metadata:
#             project.metadata = new_project_metadata
#             project_fields.append("metadata")
#
#         if not project.actual_start_date:
#             project.actual_start_date = today
#             project_fields.append("actual_start_date")
#
#         if project_fields:
#             project_fields.append("updated_at")
#             project.save(update_fields=project_fields)
#             project_updated = True
#
#         update_obj, update_created = ConstructionUpdate.objects.update_or_create(
#             construction_project=project,
#             report_date=today,
#             recorded_by=self.UPDATE_RECORDED_BY,
#             defaults={
#                 "stage": self.UPDATE_STAGE,
#                 "progress_percent": progress_percent,
#                 "summary": self.UPDATE_SUMMARY,
#                 "details": self._build_update_details(parcel, crm, valeur_hypothecaire, progress_raw),
#                 "issues": "",
#                 "next_actions": "",
#                 "weather_notes": "",
#                 "asset": None,
#             },
#         )
#
#         update_updated = not update_created
#
#         return {
#             "parcel_id": parcel.id,
#             "project_created": project_created,
#             "project_updated": project_updated,
#             "update_created": update_created,
#             "update_updated": update_updated,
#             "parcel_updated": parcel_updated,
#             "skipped": False,
#         }
#
#     def project_queryset(self, queryset):
#         results = []
#         for parcel in queryset:
#             results.append(self.project_parcel(parcel))
#         return results

class ParcelCRMProjectionService:
    PROJECT_STATUS = "IN_PROGRESS"
    UPDATE_STAGE = "OTHER"
    UPDATE_SUMMARY = "Synchronisation CRM"
    UPDATE_RECORDED_BY = "CRM_SYNC"

    CRM_PAYMENT_METHOD = "OTHER"
    CRM_PAYMENT_STATUS = "CONFIRMED"

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

    def _safe_str(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

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

    def _normalize_name(self, value: str) -> str:
        return " ".join(self._safe_str(value).upper().split())

    def _model_field_names(self, model_class):
        return {f.name for f in model_class._meta.fields}

    def _instance_set_if_field(self, instance, field_name, value, updated_fields: list):
        if field_name in self._model_field_names(instance.__class__):
            current = getattr(instance, field_name, None)
            if current != value:
                setattr(instance, field_name, value)
                updated_fields.append(field_name)

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
        ilot = crm.get("ilot") or (parcel.block.code if parcel.block else "")
        lot = crm.get("lot") or parcel.lot_number or parcel.parcel_code or ""
        code_projet = crm.get("code_projet") or getattr(parcel.program, "code", "")
        return (
            f"Synchronisation CRM du {timezone.localdate():%d/%m/%Y}\n"
            f"Lot: {lot}\n"
            f"Îlot: {ilot}\n"
            f"Code projet: {code_projet}\n"
            f"Client: {customer_name or '—'}\n"
            f"Valeur hypothécaire: {valeur_hypothecaire}\n"
            f"Avancement travaux mois: {progress_raw}\n"
            f"Coût actif: {cout_actif}\n"
            f"Cumul versements client: {versement_client}\n"
            f"Delta paiement intégré: {payment_delta}\n"
            f"Ecart status: {ecart_status}"
        )

    def _find_existing_customer(self, crm: dict):
        nom = self._normalize_name(crm.get("nom"))
        prenom = self._normalize_name(crm.get("prenom"))

        if not nom and not prenom:
            return None

        qs = Customer.objects.filter(is_active=True)

        # recherche stricte d'abord
        customer = qs.filter(
            customer_type="INDIVIDUAL",
            first_name__iexact=prenom,
            last_name__iexact=nom,
        ).first()
        if customer:
            return customer

        # fallback si nom/prénom ont été inversés quelque part
        customer = qs.filter(
            customer_type="INDIVIDUAL",
            first_name__iexact=nom,
            last_name__iexact=prenom,
        ).first()
        if customer:
            return customer

        # fallback plus souple
        conditions = Q()
        if prenom:
            conditions &= Q(first_name__icontains=prenom)
        if nom:
            conditions &= Q(last_name__icontains=nom)

        if conditions:
            customer = qs.filter(customer_type="INDIVIDUAL").filter(conditions).first()
            if customer:
                return customer

        return None

    def _get_or_create_customer(self, parcel: Parcel, crm: dict):
        nom = self._safe_str(crm.get("nom"))
        prenom = self._safe_str(crm.get("prenom"))

        if not nom and not prenom:
            return None, False, False

        customer = self._find_existing_customer(crm)
        created = False
        updated = False

        if not customer:
            customer = Customer.objects.create(
                customer_type="INDIVIDUAL",
                first_name=prenom or None,
                last_name=nom or None,
                notes=f"Client créé automatiquement via synchronisation CRM pour la parcelle {parcel.id}.",
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

    def _generate_sale_number(self, parcel: Parcel) -> str:
        lot = parcel.lot_number or parcel.parcel_code or parcel.id
        program_code = getattr(parcel.program, "code", None) or "PRG"
        return f"SALE-CRM-{program_code}-{lot}-{parcel.id}"

    def _generate_payment_number(self, sale_file: SaleFile, cumulative_amount: Decimal) -> str:
        cumulative_str = str(int(cumulative_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
        return f"PAY-CRM-{sale_file.id}-{cumulative_str}"

    def _sale_defaults_from_crm(self, parcel: Parcel, customer: Customer | None, crm: dict):
        field_names = self._model_field_names(SaleFile)
        cout_actif = self._quantize_2(crm.get("cout_actif"))
        defaults = {}

        if "sale_number" in field_names:
            defaults["sale_number"] = self._generate_sale_number(parcel)

        if "program" in field_names:
            defaults["program"] = parcel.program

        if "customer" in field_names:
            defaults["customer"] = customer

        # ⚠️ NE PAS remettre "parcel" ici
        # if "parcel" in field_names:
        #     defaults["parcel"] = parcel

        if "sale_date" in field_names:
            defaults["sale_date"] = timezone.localdate()

        if "agreed_price" in field_names:
            defaults["agreed_price"] = cout_actif

        if "net_price" in field_names:
            defaults["net_price"] = cout_actif

        if "notes" in field_names:
            defaults["notes"] = "Dossier créé automatiquement via synchronisation CRM."

        if "metadata" in field_names:
            defaults["metadata"] = {
                "source": "crm_sync",
                "crm_snapshot": crm,
            }

        return defaults

    def _get_or_create_sale_file(self, parcel: Parcel, customer: Customer | None, crm: dict):
        created = False
        updated = False

        sale = (
            SaleFile.objects.filter(parcel=parcel, is_active=True)
            .select_related("customer", "program", "parcel")
            .order_by("-created_at")
            .first()
        )

        cout_actif = self._quantize_2(crm.get("cout_actif"))

        if not sale:
            defaults = self._sale_defaults_from_crm(parcel, customer, crm)

            # si sale_number existe et est obligatoire, on l’envoie
            create_kwargs = {}
            field_names = self._model_field_names(SaleFile)

            if "parcel" in field_names:
                create_kwargs["parcel"] = parcel

            sale = SaleFile.objects.create(**defaults, **create_kwargs)
            return sale, True, False

        update_fields = []
        field_names = self._model_field_names(SaleFile)

        if "customer" in field_names and customer and sale.customer_id != customer.id:
            sale.customer = customer
            update_fields.append("customer")

        if "program" in field_names and parcel.program and sale.program_id != parcel.program_id:
            sale.program = parcel.program
            update_fields.append("program")

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
            }
            if metadata != new_metadata:
                sale.metadata = new_metadata
                update_fields.append("metadata")

        if update_fields:
            update_fields.append("updated_at")
            sale.save(update_fields=update_fields)
            updated = True

        return sale, created, updated

    def _previous_cumulative_paid(self, project: ConstructionProject) -> Decimal:
        metadata = project.metadata or {}
        tracking = metadata.get("crm_payment_tracking", {}) or {}
        return self._quantize_2(tracking.get("last_cumulative_paid"))

    def _update_project_payment_tracking(self, project: ConstructionProject, cumulative_paid: Decimal):
        metadata = project.metadata or {}
        tracking = metadata.get("crm_payment_tracking", {}) or {}
        tracking["last_cumulative_paid"] = str(cumulative_paid)
        tracking["updated_at"] = timezone.now().isoformat()

        metadata["crm_payment_tracking"] = tracking
        metadata["source"] = "crm_sync"

        project.metadata = metadata
        project.save(update_fields=["metadata", "updated_at"])

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

        valeur_hypothecaire = self._quantize_2(crm.get("valeur_hypothecaire"))
        progress_raw = self._safe_decimal(crm.get("avancement_travaux_mois"))
        progress_percent = self._quantize_2(crm.get("avancement_travaux_mois"))
        cout_actif = self._quantize_2(crm.get("cout_actif"))
        versement_client = self._quantize_2(crm.get("versement_client"))
        ecart_status = self._quantize_2(crm.get("ecart_status"))

        customer, customer_created, customer_updated = self._get_or_create_customer(parcel, crm)
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

        customer_name = ""
        if customer:
            customer_name = str(customer)

        new_projection_meta = {
            **projection_meta,
            "customer_name": customer_name,
            "cout_actif": str(cout_actif),
            "versement_client": str(versement_client),
            "ecart_status": str(ecart_status),
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
            # baisse de cumul côté CRM : on ne crée pas de paiement négatif
            payment_delta = Decimal("0.00")

        payment_obj, payment_created = self._create_payment_from_delta(
            sale_file=sale_file,
            payment_delta=payment_delta,
            cumulative_paid=versement_client,
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
            "crm_customer": {
                "nom": self._safe_str(crm.get("nom")),
                "prenom": self._safe_str(crm.get("prenom")),
                "display": customer_name,
                "customer_id": customer.id if customer else None,
            },
            "crm_finance": {
                "cout_actif": str(cout_actif),
                "versement_client": str(versement_client),
                "ecart_status": str(ecart_status),
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

        update_obj, update_created = ConstructionUpdate.objects.update_or_create(
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
                    customer_name=customer_name,
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