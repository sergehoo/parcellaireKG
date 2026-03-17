import json
from datetime import date
from decimal import Decimal

from django.contrib.gis import geometry
from django.contrib.gis.db.backends.base import features
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from parcelaire.models import Reservation, SaleFile, PropertyAsset, Parcel



#code direct ,
def user_can_view_financial_data(user):
    return user.is_superuser or user.has_perm("parcelaire.view_financial_data")


def user_can_view_patient_data(user):
    return user.is_superuser or user.has_perm("parcelaire.view_patient_data")


def user_can_view_construction_data(user):
    return user.is_superuser or user.has_perm("parcelaire.view_construction_data")


class RealEstateMapAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    FILTERS = ["Tous", "Disponibles", "Réservés", "Vendus", "En construction"]

    # =========================
    # PERMISSIONS
    # =========================
    def get_hypotheque_payment_ratio(self, valeur_hypothecaire, montant_paye):
        """
        ratio = ((montant_paye - valeur_hypothecaire) / valeur_hypothecaire) * 100

        Ex:
        - si montant payé est bien en dessous => ratio négatif
        - si montant payé atteint/dépasse => ratio >= 0
        """
        try:
            valeur_hypothecaire = Decimal(valeur_hypothecaire or 0)
            montant_paye = Decimal(montant_paye or 0)

            if valeur_hypothecaire <= 0:
                return {
                    "ratio_value": 0,
                    "ratio_label": "0%",
                    "priority": "LOW",
                    "priority_label": "Priorité faible",
                    "priority_color": "#22c55e",
                    "priority_badge": "bg-emerald-100 text-emerald-700",
                    "priority_dot": "green",
                }

            ratio = ((montant_paye - valeur_hypothecaire) / valeur_hypothecaire) * Decimal("100")
            ratio = round(ratio, 2)

            if ratio <= Decimal("-19"):
                return {
                    "ratio_value": float(ratio),
                    "ratio_label": f"{ratio}%",
                    "priority": "LOW",
                    "priority_label": "Priorité faible",
                    "priority_color": "#22c55e",
                    "priority_badge": "bg-emerald-100 text-emerald-700",
                    "priority_dot": "green",
                }
            elif Decimal("-19") < ratio < Decimal("0"):
                return {
                    "ratio_value": float(ratio),
                    "ratio_label": f"{ratio}%",
                    "priority": "MEDIUM",
                    "priority_label": "Priorité moyenne",
                    "priority_color": "#f59e0b",
                    "priority_badge": "bg-amber-100 text-amber-700",
                    "priority_dot": "orange",
                }
            else:
                return {
                    "ratio_value": float(ratio),
                    "ratio_label": f"{ratio}%",
                    "priority": "HIGH",
                    "priority_label": "Priorité élevée",
                    "priority_color": "#ef4444",
                    "priority_badge": "bg-rose-100 text-rose-700",
                    "priority_dot": "red",
                }

        except Exception:
            return {
                "ratio_value": 0,
                "ratio_label": "0%",
                "priority": "LOW",
                "priority_label": "Priorité faible",
                "priority_color": "#22c55e",
                "priority_badge": "bg-emerald-100 text-emerald-700",
                "priority_dot": "green",
            }
    def get_user_rights(self, request):
        user = request.user
        return {
            "can_view_financial_data": user.is_authenticated and (
                user.is_superuser or user.has_perm("parcelaire.view_financial_data")
            ),
            "can_view_patient_data": user.is_authenticated and (
                user.is_superuser or user.has_perm("parcelaire.view_patient_data")
            ),
            "can_view_construction_data": user.is_authenticated and (
                user.is_superuser or user.has_perm("parcelaire.view_construction_data")
            ),
        }

    # =========================
    # HELPERS UI / FORMAT
    # =========================

    def compute_asset_height(self, asset=None, parcel=None):
        """
        Retourne une hauteur en mètres pour l'extrusion 3D.
        """
        if asset:
            property_type = (asset.property_type.label or "").lower() if asset.property_type else ""
            floors = asset.floors or 0

            if floors > 0:
                return round(floors * 3.2, 2)

            if asset.status == "UNDER_CONSTRUCTION":
                progress = getattr(asset, "construction_progress", 40) or 40
                final_height = 10
                return round(final_height * (progress / 100), 2)

            if "immeuble" in property_type:
                return 18
            if "appartement" in property_type:
                return 12
            if "duplex" in property_type:
                return 8
            if "villa" in property_type:
                return 5
            if "maison" in property_type:
                return 4

            return 2.5

        if parcel:
            area = parcel.official_area_m2 or 0

            if area >= 800:
                return 2.2
            if area >= 400:
                return 1.6
            if area >= 200:
                return 1.2

            return 0.8

        return 1.0

    def compute_base_height(self, asset=None, parcel=None):
        return 0

    def get_3d_type(self, asset=None, parcel=None):
        if asset and asset.property_type:
            return asset.property_type.label
        return "Parcelle"

    def get_status_ui_from_asset_status(self, status):
        mapping = {
            "AVAILABLE": {
                "status": "Disponible",
                "statusKey": "Disponibles",
                "statusBadge": "bg-sky-100 text-sky-700",
                "color": "#38bdf8",
                "fillOpacity": 0.78,
            },
            "RESERVED": {
                "status": "Réservé",
                "statusKey": "Réservés",
                "statusBadge": "bg-amber-100 text-amber-700",
                "color": "#f59e0b",
                "fillOpacity": 0.80,
            },
            "SOLD": {
                "status": "Vendu",
                "statusKey": "Vendus",
                "statusBadge": "bg-emerald-100 text-emerald-700",
                "color": "#10b981",
                "fillOpacity": 0.78,
            },
            "UNDER_CONSTRUCTION": {
                "status": "En construction",
                "statusKey": "En construction",
                "statusBadge": "bg-violet-100 text-violet-700",
                "color": "#8b5cf6",
                "fillOpacity": 0.80,
            },
            "PLANNED": {
                "status": "Planifié",
                "statusKey": "Disponibles",
                "statusBadge": "bg-slate-100 text-slate-700",
                "color": "#94a3b8",
                "fillOpacity": 0.72,
            },
            "DESIGNED": {
                "status": "Conçu",
                "statusKey": "Disponibles",
                "statusBadge": "bg-indigo-100 text-indigo-700",
                "color": "#6366f1",
                "fillOpacity": 0.76,
            },
            "COMPLETED": {
                "status": "Achevé",
                "statusKey": "Vendus",
                "statusBadge": "bg-emerald-100 text-emerald-700",
                "color": "#10b981",
                "fillOpacity": 0.78,
            },
            "BLOCKED": {
                "status": "Bloqué",
                "statusKey": "Réservés",
                "statusBadge": "bg-rose-100 text-rose-700",
                "color": "#f43f5e",
                "fillOpacity": 0.80,
            },
        }
        return mapping.get(
            status,
            {
                "status": status or "Inconnu",
                "statusKey": "Tous",
                "statusBadge": "bg-slate-100 text-slate-700",
                "color": "#94a3b8",
                "fillOpacity": 0.75,
            },
        )

    def get_status_ui_from_parcel_status(self, status):
        mapping = {
            "AVAILABLE": {
                "status": "Disponible",
                "statusKey": "Disponibles",
                "statusBadge": "bg-sky-100 text-sky-700",
                "color": "#38bdf8",
                "fillOpacity": 0.78,
            },
            "OPTIONED": {
                "status": "Réservé",
                "statusKey": "Réservés",
                "statusBadge": "bg-amber-100 text-amber-700",
                "color": "#f59e0b",
                "fillOpacity": 0.80,
            },
            "RESERVED": {
                "status": "Réservé",
                "statusKey": "Réservés",
                "statusBadge": "bg-amber-100 text-amber-700",
                "color": "#f59e0b",
                "fillOpacity": 0.80,
            },
            "SOLD": {
                "status": "Vendu",
                "statusKey": "Vendus",
                "statusBadge": "bg-emerald-100 text-emerald-700",
                "color": "#10b981",
                "fillOpacity": 0.78,
            },
            "BLOCKED": {
                "status": "Bloqué",
                "statusKey": "Réservés",
                "statusBadge": "bg-rose-100 text-rose-700",
                "color": "#f43f5e",
                "fillOpacity": 0.80,
            },
            "LITIGATION": {
                "status": "Bloqué",
                "statusKey": "Réservés",
                "statusBadge": "bg-rose-100 text-rose-700",
                "color": "#f43f5e",
                "fillOpacity": 0.80,
            },
            "ARCHIVED": {
                "status": "Archivé",
                "statusKey": "Tous",
                "statusBadge": "bg-slate-100 text-slate-700",
                "color": "#94a3b8",
                "fillOpacity": 0.65,
            },
        }
        return mapping.get(
            status,
            {
                "status": "Disponible",
                "statusKey": "Disponibles",
                "statusBadge": "bg-sky-100 text-sky-700",
                "color": "#38bdf8",
                "fillOpacity": 0.78,
            },
        )

    def money_display(self, value):
        if value in [None, ""]:
            return "—"
        try:
            value = Decimal(value)
        except Exception:
            return str(value)
        return f"{int(value):,} FCFA".replace(",", " ")

    def percent_display(self, num, den):
        if not den or den == 0:
            return "0%"
        try:
            pct = (Decimal(num or 0) / Decimal(den)) * 100
            return f"{round(pct)}%"
        except Exception:
            return "0%"

    def money_raw(self, value):
        if value in [None, ""]:
            return Decimal("0")
        try:
            return Decimal(value)
        except Exception:
            return Decimal("0")

    def safe_percent_value(self, num, den):
        try:
            num = Decimal(num or 0)
            den = Decimal(den or 0)
            if den <= 0:
                return 0
            return round((num / den) * 100, 2)
        except Exception:
            return 0

    def get_geometry_obj(self, parcel):
        if not parcel or not parcel.geometry:
            return None
        try:
            return json.loads(parcel.geometry.geojson)
        except Exception:
            return None

    def get_center(self, parcel):
        if not parcel or not parcel.centroid:
            return None
        try:
            return [parcel.centroid.y, parcel.centroid.x]
        except Exception:
            return None

    def get_customer_name(self, customer):
        if not customer:
            return "—"
        if getattr(customer, "customer_type", None) == "COMPANY":
            return customer.company_name or "Entreprise"
        full_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip()
        return full_name or "Client"

    def get_sale_payment_progress(self, sale):
        if not sale:
            return "0%"
        total_paid = getattr(sale, "total_paid", Decimal("0")) or Decimal("0")
        net_price = sale.net_price or sale.agreed_price or Decimal("0")
        return self.percent_display(total_paid, net_price)

    def normalize_query(self, request):
        return {
            "program_id": request.GET.get("program"),
            "project_id": request.GET.get("project"),
            "status": request.GET.get("status"),
            "search": (request.GET.get("search") or "").strip(),
        }

    # =========================
    # SAFE / MASKED BLOCKS
    # =========================

    def get_masked_financial_stats(self):
        return {
            "montant_base": "Masqué",
            "montant_base_value": 0,
            "montant_vendu": "Masqué",
            "montant_vendu_value": 0,
            "montant_paye": "Masqué",
            "montant_paye_value": 0,
            "nombre_paiements": 0,
            "taux_paiement": "Masqué",
            "taux_paiement_value": 0,
        }

    def get_masked_construction_stats(self):
        return {
            "taux_avancement": "Masqué",
            "taux_avancement_value": 0,
            "valeur_hypothecaire": "Masqué",
            "valeur_hypothecaire_value": 0,
            "budget_previsionnel": "Masqué",
            "budget_previsionnel_value": 0,
            "cout_reel": "Masqué",
            "cout_reel_value": 0,
            "comparatif_progression": {
                "il_y_a_2_mois": 0,
                "mois_dernier": 0,
                "mois_en_cours": 0,
            },
            "evolution_mensuelle": 0,
            "evolution_mensuelle_label": "Masqué",
        }

    def get_masked_client_name(self):
        return "Masqué"

    # =========================
    # FINANCE / CONSTRUCTION
    # =========================

    def get_sale_financial_stats(self, sale=None, asset=None):
        """
        Retourne:
        - montant_base
        - montant_vendu
        - montant_paye
        - nombre_paiements
        - taux_paiement
        """
        base_amount = Decimal("0")
        sold_amount = Decimal("0")
        amount_paid = Decimal("0")
        payments_count = 0

        if asset and getattr(asset, "sale_price", None):
            base_amount = self.money_raw(asset.sale_price)
        elif asset and getattr(asset, "estimated_cost", None):
            base_amount = self.money_raw(asset.estimated_cost)

        if sale:
            sold_amount = self.money_raw(sale.net_price or sale.agreed_price)
            amount_paid = self.money_raw(getattr(sale, "total_paid", 0))
            try:
                payments_count = sale.payments.count()
            except Exception:
                payments_count = 0

            if not base_amount:
                base_amount = sold_amount

        taux_paiement = self.safe_percent_value(amount_paid, sold_amount or base_amount)

        return {
            "montant_base": self.money_display(base_amount),
            "montant_base_value": float(base_amount),
            "montant_vendu": self.money_display(sold_amount),
            "montant_vendu_value": float(sold_amount),
            "montant_paye": self.money_display(amount_paid),
            "montant_paye_value": float(amount_paid),
            "nombre_paiements": payments_count,
            "taux_paiement": f"{round(taux_paiement)}%",
            "taux_paiement_value": taux_paiement,
        }

    def month_range(self, year, month):
        import calendar
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        return first_day, last_day

    def get_parcel_or_asset_construction_project(self, parcel=None, asset=None):
        """
        Prend le chantier le plus pertinent.
        """
        if parcel:
            qs = parcel.construction_projects.all().order_by("-created_at")
            return qs.first()

        if asset and getattr(asset, "parcel", None):
            qs = asset.parcel.construction_projects.all().order_by("-created_at")
            return qs.first()

        return None

    def get_monthly_progress_value(self, construction_project, year, month):
        if not construction_project:
            return 0

        start_date, end_date = self.month_range(year, month)

        update = (
            construction_project.updates
            .filter(report_date__gte=start_date, report_date__lte=end_date, is_active=True)
            .order_by("-report_date", "-created_at")
            .first()
        )
        if update and update.progress_percent is not None:
            try:
                return float(update.progress_percent)
            except Exception:
                return 0
        return 0

    def get_construction_stats(self, parcel=None, asset=None):
        """
        Retourne:
        - taux_avancement
        - valeur_hypothecaire
        - comparaison 3 mois
        - evolution_mois
        """
        project = self.get_parcel_or_asset_construction_project(parcel=parcel, asset=asset)

        current_progress = 0
        estimated_budget = Decimal("0")
        actual_cost = Decimal("0")

        if project:
            try:
                current_progress = float(project.progress_percent or 0)
            except Exception:
                current_progress = 0

            estimated_budget = self.money_raw(getattr(project, "estimated_budget", 0))
            actual_cost = self.money_raw(getattr(project, "actual_cost", 0))

        today = date.today()

        m0_y, m0_m = today.year, today.month

        if m0_m == 1:
            m1_y, m1_m = m0_y - 1, 12
        else:
            m1_y, m1_m = m0_y, m0_m - 1

        if m1_m == 1:
            m2_y, m2_m = m1_y - 1, 12
        else:
            m2_y, m2_m = m1_y, m1_m - 1

        progress_m2 = self.get_monthly_progress_value(project, m2_y, m2_m)
        progress_m1 = self.get_monthly_progress_value(project, m1_y, m1_m)
        progress_m0 = self.get_monthly_progress_value(project, m0_y, m0_m)

        monthly_delta = round(progress_m0 - progress_m1, 2)

        valeur_hypothecaire = Decimal("0")

        # priorité à la valeur synchronisée sur la parcelle
        if parcel and getattr(parcel, "valeur_hypothecaire", None) not in [None, ""]:
            valeur_hypothecaire = self.money_raw(parcel.valeur_hypothecaire)

        # fallback éventuel si aucune valeur n’est stockée sur la parcelle
        elif estimated_budget > 0 and current_progress > 0:
            valeur_hypothecaire = (
                estimated_budget * Decimal(str(current_progress / 100))
            ).quantize(Decimal("1"))

        return {
            "taux_avancement": f"{round(current_progress)}%",
            "taux_avancement_value": current_progress,
            "valeur_hypothecaire": self.money_display(valeur_hypothecaire),
            "valeur_hypothecaire_value": float(valeur_hypothecaire),
            "budget_previsionnel": self.money_display(estimated_budget),
            "budget_previsionnel_value": float(estimated_budget),
            "cout_reel": self.money_display(actual_cost),
            "cout_reel_value": float(actual_cost),
            "comparatif_progression": {
                "il_y_a_2_mois": progress_m2,
                "mois_dernier": progress_m1,
                "mois_en_cours": progress_m0,
            },
            "evolution_mensuelle": monthly_delta,
            "evolution_mensuelle_label": (
                f"+{round(monthly_delta)}% ce mois" if monthly_delta > 0
                else f"{round(monthly_delta)}% ce mois"
            ),
        }

    # =========================
    # DATA HELPERS
    # =========================

    def get_sales_by_parcel(self, parcel_ids):
        if not parcel_ids:
            return {}

        sales = (
            SaleFile.objects.select_related("customer", "parcel", "program")
            .prefetch_related("payments")
            .filter(parcel_id__in=parcel_ids)
            .annotate(total_paid=Coalesce(Sum("payments__amount"), Decimal("0")))
            .order_by("-sale_date", "-created_at")
        )

        sales_by_parcel = {}
        for sale in sales:
            sales_by_parcel.setdefault(sale.parcel_id, sale)
        return sales_by_parcel

    def get_reservations_by_parcel(self, parcel_ids):
        if not parcel_ids:
            return {}

        reservations = (
            Reservation.objects.select_related("customer", "parcel", "program")
            .filter(parcel_id__in=parcel_ids)
            .order_by("-reservation_date", "-created_at")
        )

        reservations_by_parcel = {}
        for reservation in reservations:
            reservations_by_parcel.setdefault(reservation.parcel_id, reservation)
        return reservations_by_parcel

    def apply_common_filters_assets(self, queryset, params):
        if params["program_id"]:
            queryset = queryset.filter(program_id=params["program_id"])

        if params["project_id"]:
            queryset = queryset.filter(program__project_id=params["project_id"])

        if params["status"]:
            queryset = queryset.filter(status=params["status"])

        if params["search"]:
            q = params["search"]
            queryset = queryset.filter(
                models.Q(label__icontains=q)
                | models.Q(code__icontains=q)
                | models.Q(program__name__icontains=q)
                | models.Q(program__project__nom__icontains=q)
                | models.Q(parcel__lot_number__icontains=q)
                | models.Q(parcel__parcel_code__icontains=q)
                | models.Q(property_type__label__icontains=q)
            )
        return queryset

    def apply_common_filters_parcels(self, queryset, params):
        if params["program_id"]:
            queryset = queryset.filter(program_id=params["program_id"])

        if params["project_id"]:
            queryset = queryset.filter(program__project_id=params["project_id"])

        if params["status"]:
            queryset = queryset.filter(commercial_status=params["status"])

        if params["search"]:
            q = params["search"]
            queryset = queryset.filter(
                models.Q(lot_number__icontains=q)
                | models.Q(parcel_code__icontains=q)
                | models.Q(external_reference__icontains=q)
                | models.Q(program__name__icontains=q)
                | models.Q(program__project__nom__icontains=q)
                | models.Q(block__code__icontains=q)
            )
        return queryset

    # =========================
    # SERIALIZATION HELPERS
    # =========================

    def get_asset_images(self, asset):
        photos = []
        try:
            for photo in asset.photos.all()[:10]:
                image = getattr(photo, "image", None)
                if image:
                    try:
                        photos.append(image.url)
                    except Exception:
                        pass
        except Exception:
            pass

        if not photos and asset.parcel:
            try:
                for doc in asset.parcel.documents.filter(document_type="PHOTO")[:10]:
                    file_obj = getattr(doc, "file", None)
                    if file_obj:
                        try:
                            photos.append(file_obj.url)
                        except Exception:
                            pass
            except Exception:
                pass

        return photos[:10]

    def get_parcel_images(self, parcel):
        photos = []

        try:
            for doc in parcel.documents.filter(document_type="PHOTO")[:10]:
                file_obj = getattr(doc, "file", None)
                if file_obj:
                    try:
                        url = file_obj.url
                        if url not in photos:
                            photos.append(url)
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            for construction_project in parcel.construction_projects.all():
                for photo in construction_project.photos.all()[:10]:
                    image_obj = getattr(photo, "image", None)
                    if image_obj:
                        try:
                            url = image_obj.url
                            if url not in photos:
                                photos.append(url)
                        except Exception:
                            pass
        except Exception:
            pass

        return photos[:10]

    def get_asset_timeline(self, asset, sale=None, reservation=None):
        items = []

        if reservation and reservation.reservation_date:
            items.append(
                {
                    "label": "Réservation",
                    "date": reservation.reservation_date.strftime("%d %b"),
                    "text": "Réservation enregistrée sur l’actif.",
                    "iconBg": "bg-amber-100",
                }
            )

        if sale and sale.sale_date:
            items.append(
                {
                    "label": "Vente actée",
                    "date": sale.sale_date.strftime("%d %b"),
                    "text": "Dossier commercial sécurisé.",
                    "iconBg": "bg-emerald-100",
                }
            )

        try:
            for update in asset.updates.all()[:5]:
                items.append(
                    {
                        "label": update.get_stage_display() if hasattr(update, "get_stage_display") else getattr(update, "stage", "Mise à jour"),
                        "date": update.report_date.strftime("%d %b") if getattr(update, "report_date", None) else "—",
                        "text": getattr(update, "summary", None) or getattr(update, "details", None) or "Mise à jour chantier",
                        "iconBg": "bg-violet-100",
                    }
                )
        except Exception:
            pass

        return items[:6]

    def get_parcel_timeline(self, parcel, sale=None, reservation=None):
        items = [
            {
                "label": "Import parcellaire",
                "date": parcel.created_at.strftime("%d %b") if getattr(parcel, "created_at", None) else "—",
                "text": "Parcelle importée dans le système.",
                "iconBg": "bg-sky-100",
            }
        ]

        if reservation and reservation.reservation_date:
            items.insert(
                0,
                {
                    "label": "Réservation",
                    "date": reservation.reservation_date.strftime("%d %b"),
                    "text": "Réservation enregistrée sur la parcelle.",
                    "iconBg": "bg-amber-100",
                },
            )

        if sale and sale.sale_date:
            items.insert(
                0,
                {
                    "label": "Vente actée",
                    "date": sale.sale_date.strftime("%d %b"),
                    "text": "Vente enregistrée dans le système.",
                    "iconBg": "bg-emerald-100",
                },
            )

        return items[:6]

    # =========================
    # BUILDERS
    # =========================

    def _build_from_assets(self, queryset):
        rights = getattr(self, "user_rights", {})
        can_view_financial = rights.get("can_view_financial_data", False)
        can_view_patient = rights.get("can_view_patient_data", False)
        can_view_construction = rights.get("can_view_construction_data", False)

        parcel_ids = [obj.parcel_id for obj in queryset if obj.parcel_id]
        sales_by_parcel = self.get_sales_by_parcel(parcel_ids)
        reservations_by_parcel = self.get_reservations_by_parcel(parcel_ids)

        assets_payload = []
        total_ca = Decimal("0")
        reserved_or_sold = 0

        for asset in queryset:
            parcel = asset.parcel
            sale = sales_by_parcel.get(parcel.id) if parcel else None
            reservation = reservations_by_parcel.get(parcel.id) if parcel else None

            ui = self.get_status_ui_from_asset_status(asset.status)

            if can_view_patient:
                client_name = (
                    self.get_customer_name(sale.customer)
                    if sale and sale.customer
                    else (
                        self.get_customer_name(reservation.customer)
                        if reservation and reservation.customer
                        else "—"
                    )
                )
            else:
                client_name = self.get_masked_client_name()

            if asset.status in ["RESERVED", "SOLD", "UNDER_CONSTRUCTION", "COMPLETED"]:
                reserved_or_sold += 1

            if can_view_financial and asset.sale_price:
                total_ca += asset.sale_price

            details = [
                {
                    "label": "Projet",
                    "value": asset.program.project.nom if asset.program and getattr(asset.program, "project", None) else "—",
                },
                {"label": "Programme", "value": asset.program.name if asset.program else "—"},
                {"label": "Référence", "value": asset.code or "—"},
                {"label": "Type", "value": asset.property_type.label if asset.property_type else "—"},
                {"label": "Phase", "value": asset.phase.name if asset.phase else "—"},
                {
                    "label": "Parcelle",
                    "value": parcel.lot_number if parcel and parcel.lot_number else (parcel.parcel_code if parcel else "—"),
                },
            ]

            if can_view_patient:
                details.append({"label": "Client", "value": client_name})

            if can_view_financial and can_view_construction:
                details.append({
                    "label": "Ratio hypo / paiements",
                    "value": priority_stats["ratio_label"],
                })
                details.append({
                    "label": "Niveau priorité",
                    "value": priority_stats["priority_label"],
                })

            construction_stats = (
                self.get_construction_stats(parcel=parcel, asset=asset)
                if can_view_construction
                else self.get_masked_construction_stats()
            )

            financial_stats = (
                self.get_sale_financial_stats(sale=sale, asset=asset)
                if can_view_financial
                else self.get_masked_financial_stats()
            )
            if can_view_financial and can_view_construction:
                priority_stats = self.get_hypotheque_payment_ratio(
                    construction_stats.get("valeur_hypothecaire_value", 0),
                    financial_stats.get("montant_paye_value", 0),
                )
            else:
                priority_stats = {
                    "ratio_value": 0,
                    "ratio_label": "Masqué",
                    "priority": "UNKNOWN",
                    "priority_label": "Masqué",
                    "priority_color": "#94a3b8",
                    "priority_badge": "bg-slate-100 text-slate-700",
                    "priority_dot": "gray",
                }
            if can_view_financial:
                details.append({
                    "label": "Valeur hypothécaire",
                    "value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",

                })

            metrics = [
                {"label": "Étages", "value": str(asset.floors or 0)},
                {"label": "Chambres", "value": str(asset.bedrooms or 0)},
                {
                    "label": "Avancement",
                    "value": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
                },
            ]

            if can_view_financial and can_view_construction:
                ui["color"] = priority_stats["priority_color"]
            assets_payload.append(
                {
                    "id": asset.id,
                    "project": asset.program.project.nom if asset.program and getattr(asset.program, "project", None) else "—",
                    "name": asset.label,
                    "program": asset.program.name if asset.program else "—",
                    "type": asset.property_type.label if asset.property_type else "Actif immobilier",
                    "status": ui["status"],
                    "statusKey": ui["statusKey"],
                    "statusBadge": ui["statusBadge"],
                    "color": ui["color"],
                    "fillOpacity": ui["fillOpacity"],
                    "price": self.money_display(asset.sale_price) if can_view_financial else "Masqué",
                    "surface": (
                        f"{asset.built_area_m2} m²"
                        if asset.built_area_m2
                        else (f"{parcel.official_area_m2} m²" if parcel and parcel.official_area_m2 else "—")
                    ),
                    "payment": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
                    "client": client_name,
                    "phase": asset.phase.name if asset.phase else "—",
                    "center": self.get_center(parcel),
                    "images": self.get_asset_images(asset),
                    "details": details,
                    "metrics": metrics,
                    "timeline": self.get_asset_timeline(asset, sale=sale, reservation=reservation),
                    "geometry": self.get_geometry_obj(parcel),
                    "height": self.compute_asset_height(asset=asset, parcel=parcel),
                    "base_height": self.compute_base_height(asset=asset, parcel=parcel),
                    "building_type": self.get_3d_type(asset=asset, parcel=parcel),
                    "financial_stats": financial_stats,
                    "construction_stats": construction_stats,
                    "priority_stats": priority_stats,
                }
            )

        summaries = [
            {"label": "Actifs", "value": str(len(assets_payload))},
            {"label": "Réservés/Vendus", "value": str(reserved_or_sold)},
            {"label": "CA potentiel", "value": self.money_display(total_ca or 0) if can_view_financial else "Masqué"},
        ]

        return Response(
            {
                "source": "property_assets",
                "assets": assets_payload,
                "summaries": summaries,
                "filters": self.FILTERS,
                "user_rights": rights,
            }
        )

    def _build_from_parcels(self, queryset):
        rights = getattr(self, "user_rights", {})
        can_view_financial = rights.get("can_view_financial_data", False)
        can_view_patient = rights.get("can_view_patient_data", False)
        can_view_construction = rights.get("can_view_construction_data", False)

        parcel_ids = list(queryset.values_list("id", flat=True))
        sales_by_parcel = self.get_sales_by_parcel(parcel_ids)
        reservations_by_parcel = self.get_reservations_by_parcel(parcel_ids)

        assets_payload = []
        reserved_or_sold = 0
        total_ca = Decimal("0")

        for parcel in queryset:
            sale = sales_by_parcel.get(parcel.id)
            reservation = reservations_by_parcel.get(parcel.id)

            ui = self.get_status_ui_from_parcel_status(parcel.commercial_status)

            if can_view_patient:
                client_name = (
                    self.get_customer_name(sale.customer)
                    if sale and sale.customer
                    else (
                        self.get_customer_name(reservation.customer)
                        if reservation and reservation.customer
                        else "—"
                    )
                )
            else:
                client_name = self.get_masked_client_name()

            if ui["statusKey"] in ["Réservés", "Vendus"]:
                reserved_or_sold += 1

            if can_view_financial and sale and (sale.net_price or sale.agreed_price):
                total_ca += sale.net_price or sale.agreed_price

            details = [
                {
                    "label": "Projet",
                    "value": parcel.program.project.nom if parcel.program and getattr(parcel.program, "project", None) else "—",
                },
                {"label": "Programme", "value": parcel.program.name if parcel.program else "—"},
                {"label": "Îlot", "value": parcel.block.code if parcel.block else "—"},
                {"label": "Lot", "value": parcel.lot_number or "—"},
                {"label": "Référence", "value": parcel.parcel_code or "—"},
                {"label": "Surface", "value": f"{parcel.official_area_m2} m²" if parcel.official_area_m2 else "—"},
            ]

            if can_view_patient:
                details.append({"label": "Client", "value": client_name})

            financial_stats = (
                self.get_sale_financial_stats(sale=sale, asset=None)
                if can_view_financial
                else self.get_masked_financial_stats()
            )

            construction_stats = (
                self.get_construction_stats(parcel=parcel, asset=None)
                if can_view_construction
                else self.get_masked_construction_stats()
            )
            if can_view_financial and can_view_construction:
                priority_stats = self.get_hypotheque_payment_ratio(
                    construction_stats.get("valeur_hypothecaire_value", 0),
                    financial_stats.get("montant_paye_value", 0),
                )
            else:
                priority_stats = {
                    "ratio_value": 0,
                    "ratio_label": "Masqué",
                    "priority": "UNKNOWN",
                    "priority_label": "Masqué",
                    "priority_color": "#94a3b8",
                    "priority_badge": "bg-slate-100 text-slate-700",
                    "priority_dot": "gray",
                }

            if can_view_financial:
                details.append({
                    "label": "Valeur hypothécaire",
                    "value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
                })

            metrics = [
                {"label": "Accès route", "value": "Oui" if parcel.has_road_access else "Non"},
                {"label": "Angle", "value": "Oui" if parcel.is_corner else "Non"},
                {
                    "label": "Avancement",
                    "value": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
                },
            ]
            if can_view_financial and can_view_construction:
                ui["color"] = priority_stats["priority_color"]
            assets_payload.append(
                {
                    "id": parcel.id,
                    "project": parcel.program.project.nom if parcel.program and getattr(parcel.program, "project", None) else "—",
                    "name": f"Lot {parcel.lot_number or parcel.parcel_code or parcel.id}",
                    "program": parcel.program.name if parcel.program else "—",
                    "type": "Parcelle",
                    "status": ui["status"],
                    "statusKey": ui["statusKey"],
                    "statusBadge": ui["statusBadge"],
                    "color": ui["color"],
                    "fillOpacity": ui["fillOpacity"],
                    "price": self.money_display(sale.net_price or sale.agreed_price) if (sale and can_view_financial) else ("Masqué" if not can_view_financial else "—"),
                    "surface": f"{parcel.official_area_m2} m²" if parcel.official_area_m2 else "—",
                    "payment": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
                    "client": client_name,
                    "phase": parcel.phase.name if parcel.phase else "—",
                    "center": self.get_center(parcel),
                    "images": self.get_parcel_images(parcel),
                    "details": details,
                    "metrics": metrics,
                    "timeline": self.get_parcel_timeline(parcel, sale=sale, reservation=reservation),
                    "geometry": self.get_geometry_obj(parcel),
                    "height": self.compute_asset_height(parcel=parcel),
                    "base_height": self.compute_base_height(parcel=parcel),
                    "building_type": self.get_3d_type(parcel=parcel),
                    "financial_stats": financial_stats,
                    "construction_stats": construction_stats,
                    "priority_stats": priority_stats,
                }
            )

        summaries = [
            {"label": "Actifs", "value": str(len(assets_payload))},
            {"label": "Réservés/Vendus", "value": str(reserved_or_sold)},
            {"label": "CA potentiel", "value": self.money_display(total_ca) if can_view_financial else "Masqué"},
        ]

        return Response(
            {
                "source": "parcels",
                "assets": assets_payload,
                "summaries": summaries,
                "filters": self.FILTERS,
                "user_rights": rights,
            }
        )

    # =========================
    # GET
    # =========================

    def get(self, request, *args, **kwargs):
        self.user_rights = self.get_user_rights(request)
        params = self.normalize_query(request)

        asset_queryset = (
            PropertyAsset.objects.select_related(
                "program",
                "program__project",
                "phase",
                "parcel",
                "property_type",
            )
            .prefetch_related("photos", "updates", "parcel__documents")
            .filter(is_active=True)
            .order_by("code")
        )
        asset_queryset = self.apply_common_filters_assets(asset_queryset, params)

        if asset_queryset.exists():
            return self._build_from_assets(asset_queryset)

        parcel_queryset = (
            Parcel.objects.select_related(
                "program",
                "program__project",
                "phase",
                "block",
            )
            .prefetch_related("documents", "construction_projects__photos", "construction_projects__updates")
            .filter(is_active=True)
            .exclude(geometry__isnull=True)
            .order_by("lot_number", "id")
        )
        parcel_queryset = self.apply_common_filters_parcels(parcel_queryset, params)

        return self._build_from_parcels(parcel_queryset)
