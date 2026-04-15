import calendar
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.gis.geos import Polygon
from django.db.models import Q, Sum, F
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from parcelaire.models import (
    Parcel,
    PropertyAsset,
    PropertyUnit,
    Reservation,
    SaleFile, ParcelTag,
)


def user_can_view_financial_data(user):
    return user.is_superuser or user.has_perm("parcelaire.view_financial_data")


def user_can_view_patient_data(user):
    return user.is_superuser or user.has_perm("parcelaire.view_patient_data")


def user_can_view_construction_data(user):
    return user.is_superuser or user.has_perm("parcelaire.view_construction_data")
# =========================================================
# TAGS HELPERS
# =========================================================





def get_available_tags_payload(self, params):
    qs = ParcelTag.objects.filter(is_active=True).select_related("program", "program__project")

    if params.get("program_id"):
        qs = qs.filter(program_id=params["program_id"])

    elif params.get("project_id"):
        qs = qs.filter(program__project_id=params["project_id"])

    return [
        self.serialize_tag(tag)
        for tag in qs.order_by("name")
    ]

class RealEstateMapAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    FILTERS = ["Tous", "Disponibles", "Réservés", "Vendus", "En construction"]

    DEFAULT_LIMIT = 1200
    MAX_LIMIT = 2500

    SIDEBAR_MODE_SINGLE = "SINGLE"
    SIDEBAR_MODE_BUILDING = "BUILDING"

    # =========================================================
    # PERMISSIONS
    # =========================================================

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

    # =========================================================
    # QUERY PARAMS / MAP PARAMS
    # =========================================================
    def serialize_tag(self, tag):
        return {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "color": tag.color or "#64748b",
            "program_id": tag.program_id,
            "program_name": getattr(tag.program, "name", ""),
            "project_id": getattr(tag.program, "project_id", None),
            "project_name": getattr(getattr(tag.program, "project", None), "nom", ""),
        }
    def parse_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def parse_bbox(self, value):
        """
        bbox attendu: minLng,minLat,maxLng,maxLat
        """
        if not value:
            return None

        try:
            parts = [float(x.strip()) for x in value.split(",")]
            if len(parts) != 4:
                return None

            min_lng, min_lat, max_lng, max_lat = parts

            if min_lng >= max_lng or min_lat >= max_lat:
                return None

            return Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
        except Exception:
            return None

    def get_geometry_precision_from_zoom(self, zoom):
        if zoom <= 12:
            return None
        if zoom <= 14:
            return 4
        if zoom <= 16:
            return 5
        return 6

    def should_include_geometry(self, zoom):
        return zoom >= 14

    def should_include_images(self, zoom):
        return zoom >= 16

    def should_include_timeline(self, zoom):
        return zoom >= 16

    def should_include_units_preview(self, zoom):
        return zoom >= 16

    def should_include_sales_summary(self, zoom):
        return zoom >= 16

    def normalize_query(self, request):
        zoom = self.parse_int(request.GET.get("zoom"), default=17)
        limit = self.parse_int(request.GET.get("limit"), default=self.DEFAULT_LIMIT)
        if limit <= 0:
            limit = self.DEFAULT_LIMIT
        limit = min(limit, self.MAX_LIMIT)

        return {
            "program_id": request.GET.get("program"),
            "project_id": request.GET.get("project"),
            "status": request.GET.get("status"),
            "tag": (request.GET.get("tag") or "").strip(),
            "search": (request.GET.get("search") or "").strip(),
            "bbox": self.parse_bbox(request.GET.get("bbox")),
            "zoom": zoom,
            "limit": limit,
        }

    # =========================================================
    # DECIMAL / FORMAT HELPERS
    # =========================================================

    def money_raw(self, value):
        if value in [None, ""]:
            return Decimal("0")
        try:
            return Decimal(str(value).replace(",", "."))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    def money_display(self, value):
        if value in [None, ""]:
            return "—"
        try:
            value = Decimal(str(value).replace(",", "."))
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

    def safe_percent_value(self, num, den):
        try:
            num = Decimal(num or 0)
            den = Decimal(den or 0)
            if den <= 0:
                return 0
            return round((num / den) * 100, 2)
        except Exception:
            return 0

    def format_percent_value(self, value):
        try:
            return f"{round(float(value or 0))}%"
        except Exception:
            return "0%"

    def safe_str(self, value, default=""):
        if value is None:
            return default
        try:
            text = str(value).strip()
            return text if text else default
        except Exception:
            return default

    def normalize_code(self, value):
        text = self.safe_str(value, "")
        if not text:
            return ""
        try:
            return str(int(float(text)))
        except Exception:
            return text.upper()

    # =========================================================
    # CRM HELPERS
    # =========================================================

    def get_crm_sync_data(self, parcel):
        try:
            return ((parcel.metadata or {}).get("crm_lot_sync") or {})
        except Exception:
            return {}

    def get_crm_projection_data(self, parcel):
        try:
            return ((parcel.metadata or {}).get("crm_projection") or {})
        except Exception:
            return {}

    def get_crm_units(self, parcel):
        crm = self.get_crm_sync_data(parcel)
        units = crm.get("units", []) or []
        return units if isinstance(units, list) else []

    def get_crm_summary(self, parcel):
        crm = self.get_crm_sync_data(parcel)
        summary = crm.get("summary", {}) or {}
        return summary if isinstance(summary, dict) else {}

    def get_crm_parent_reference(self, parcel):
        crm = self.get_crm_sync_data(parcel)
        parent = crm.get("parent_reference", {}) or {}
        if not isinstance(parent, dict):
            parent = {}
        return {
            "lot": self.safe_str(parent.get("lot") or getattr(parcel, "lot_number", None) or getattr(parcel, "parcel_code", None) or parcel.id),
            "ilot": self.safe_str(parent.get("ilot") or getattr(getattr(parcel, "block", None), "code", "")),
            "code_projet": self.safe_str(parent.get("code_projet") or getattr(getattr(parcel, "program", None), "code", "")),
        }

    def get_crm_asset_type(self, parcel):
        crm = self.get_crm_sync_data(parcel)
        value = self.safe_str(crm.get("asset_type")).upper()
        return value or "SINGLE"

    def get_crm_asset_label(self, parcel):
        crm = self.get_crm_sync_data(parcel)
        return self.safe_str(crm.get("asset_label"), "Lot")

    def is_crm_building(self, parcel):
        return self.get_crm_asset_type(parcel) == "BUILDING"

    def has_crm_payload(self, parcel):
        crm = self.get_crm_sync_data(parcel)
        return bool(crm)

    def get_crm_display_customer_name(self, parcel):
        projection = self.get_crm_projection_data(parcel)
        if projection:
            return self.safe_str(
                projection.get("display_customer_name") or projection.get("customer_name"),
                "—",
            )

        crm = self.get_crm_sync_data(parcel)
        if not crm:
            return "—"

        if self.is_crm_building(parcel):
            customers = crm.get("customers") or []
            customers = [self.safe_str(x) for x in customers if self.safe_str(x)]
            if not customers:
                return "—"
            if len(customers) == 1:
                return customers[0]
            return f"{len(customers)} clients"

        units = self.get_crm_units(parcel)
        unit = units[0] if units else {}
        full_name = self.safe_str(unit.get("client_nom_complet"))
        if full_name:
            return full_name

        return " ".join(
            [x for x in [self.safe_str(unit.get("client_prenom")), self.safe_str(unit.get("client_nom"))] if x]
        ).strip() or "—"

    def get_crm_status_ui(self, parcel):
        crm_type = self.get_crm_asset_type(parcel)
        status = getattr(parcel, "commercial_status", None)

        if crm_type == "BUILDING":
            if status in ["SOLD"]:
                return {
                    "status": "Vendu",
                    "statusKey": "Vendus",
                    "statusBadge": "bg-emerald-100 text-emerald-700",
                    "color": "#10b981",
                    "fillOpacity": 0.78,
                }
            if status in ["OPTIONED", "RESERVED"]:
                return {
                    "status": "Réservé",
                    "statusKey": "Réservés",
                    "statusBadge": "bg-amber-100 text-amber-700",
                    "color": "#f59e0b",
                    "fillOpacity": 0.80,
                }
            return {
                "status": "En construction",
                "statusKey": "En construction",
                "statusBadge": "bg-violet-100 text-violet-700",
                "color": "#8b5cf6",
                "fillOpacity": 0.80,
            }

        return self.get_status_ui_from_parcel_status(status)

    # =========================================================
    # SAFE / MASKED BLOCKS
    # =========================================================

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

    # =========================================================
    # STATUS UI
    # =========================================================

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

    def get_unit_status_ui(self, status):
        mapping = {
            "AVAILABLE": {
                "status": "Disponible",
                "statusBadge": "bg-sky-100 text-sky-700",
            },
            "OPTIONED": {
                "status": "En option",
                "statusBadge": "bg-amber-100 text-amber-700",
            },
            "RESERVED": {
                "status": "Réservé",
                "statusBadge": "bg-amber-100 text-amber-700",
            },
            "SOLD": {
                "status": "Vendu",
                "statusBadge": "bg-emerald-100 text-emerald-700",
            },
            "DELIVERED": {
                "status": "Livré",
                "statusBadge": "bg-emerald-100 text-emerald-700",
            },
            "BLOCKED": {
                "status": "Bloqué",
                "statusBadge": "bg-rose-100 text-rose-700",
            },
            "ARCHIVED": {
                "status": "Archivé",
                "statusBadge": "bg-slate-100 text-slate-700",
            },
            "DRAFT": {
                "status": "Brouillon",
                "statusBadge": "bg-slate-100 text-slate-700",
            },
        }
        return mapping.get(
            status,
            {
                "status": status or "—",
                "statusBadge": "bg-slate-100 text-slate-700",
            }
        )

    # =========================================================
    # PRIORITE HYPO / PAIEMENT
    # =========================================================

    def get_hypotheque_payment_ratio(self, valeur_hypothecaire, montant_paye):
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

    # =========================================================
    # GEOMETRY / CENTER / MEDIA
    # =========================================================

    def get_geometry_obj(self, parcel, zoom=17):
        if not parcel or not getattr(parcel, "geometry", None):
            return None

        if not self.should_include_geometry(zoom):
            return None

        try:
            geometry = parcel.geometry
            precision = self.get_geometry_precision_from_zoom(zoom)

            if precision is not None:
                geojson = geometry.geojson
                data = json.loads(geojson)
                return self.round_geojson_coordinates(data, precision)

            return json.loads(geometry.geojson)
        except Exception:
            return None

    def round_geojson_coordinates(self, geojson_obj, precision=5):
        def round_coords(coords):
            if isinstance(coords, (list, tuple)):
                if len(coords) == 2 and all(isinstance(x, (int, float)) for x in coords):
                    return [round(coords[0], precision), round(coords[1], precision)]
                return [round_coords(c) for c in coords]
            return coords

        data = dict(geojson_obj)
        if "coordinates" in data:
            data["coordinates"] = round_coords(data["coordinates"])
        return data

    def get_center(self, parcel):
        if not parcel or not getattr(parcel, "centroid", None):
            return None
        try:
            return [parcel.centroid.y, parcel.centroid.x]
        except Exception:
            return None

    def get_asset_images(self, asset, zoom=17):
        if not self.should_include_images(zoom):
            return []

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

        if not photos and getattr(asset, "parcel", None):
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

    def get_parcel_images(self, parcel, zoom=17):
        if not self.should_include_images(zoom):
            return []

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
            for cp in parcel.construction_projects.all():
                for photo in cp.photos.all()[:10]:
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

    # =========================================================
    # CUSTOMER HELPERS
    # =========================================================

    def get_customer_name(self, customer):
        if not customer:
            return "—"
        if getattr(customer, "customer_type", None) == "COMPANY":
            return customer.company_name or "Entreprise"
        full_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip()
        return full_name or "Client"

    def serialize_customer(self, customer):
        if not customer:
            return None
        return {
            "id": customer.id,
            "name": self.get_customer_name(customer),
            "type": getattr(customer, "customer_type", None),
            "phone": getattr(customer, "phone", None) or "—",
            "email": getattr(customer, "email", None) or "—",
        }

    # =========================================================
    # TYPE HELPERS
    # =========================================================

    def is_building_asset(self, asset):
        label = ""
        if getattr(asset, "asset_category", None) and getattr(asset.asset_category, "label", None):
            label += f" {asset.asset_category.label.lower()}"
        if getattr(asset, "property_type", None) and getattr(asset.property_type, "label", None):
            label += f" {asset.property_type.label.lower()}"
        label = label.strip()

        keywords = ["immeuble", "résidence", "residence", "appartement", "commerce", "commercial", "mixte", "r+"]
        return any(k in label for k in keywords) or bool(getattr(asset, "is_multi_unit", False))

    def is_villa_asset(self, asset):
        label = ""
        if getattr(asset, "asset_category", None) and getattr(asset.asset_category, "label", None):
            label += f" {asset.asset_category.label.lower()}"
        if getattr(asset, "property_type", None) and getattr(asset.property_type, "label", None):
            label += f" {asset.property_type.label.lower()}"
        label = label.strip()

        keywords = ["villa", "duplex", "triplex", "maison"]
        return any(k in label for k in keywords) and not getattr(asset, "is_multi_unit", False)

    def get_asset_nature_label(self, asset):
        if self.is_building_asset(asset):
            return "Immeuble / actif multi-unités"
        if self.is_villa_asset(asset):
            return "Villa / actif mono-unité"
        return "Actif immobilier"

    def get_sidebar_mode_for_asset(self, asset, units):
        if bool(getattr(asset, "is_multi_unit", False) or units or self.is_building_asset(asset)):
            return self.SIDEBAR_MODE_BUILDING
        return self.SIDEBAR_MODE_SINGLE

    def get_sidebar_mode_for_parcel(self, parcel):
        if self.is_crm_building(parcel):
            return self.SIDEBAR_MODE_BUILDING
        return self.SIDEBAR_MODE_SINGLE

    # =========================================================
    # HEIGHT HELPERS
    # =========================================================

    def compute_asset_height(self, asset=None, parcel=None):
        if asset:
            floors = getattr(asset, "floors", 0) or 0

            if floors > 0:
                return round(floors * 3.2, 2)

            asset_label = ""
            if getattr(asset, "asset_category", None) and getattr(asset.asset_category, "label", None):
                asset_label += f" {asset.asset_category.label.lower()}"
            if getattr(asset, "property_type", None) and getattr(asset.property_type, "label", None):
                asset_label += f" {asset.property_type.label.lower()}"

            if getattr(asset, "status", None) == "UNDER_CONSTRUCTION":
                progress = getattr(asset, "construction_progress", 40) or 40
                final_height = 10
                return round(final_height * (progress / 100), 2)

            if "immeuble" in asset_label or "r+" in asset_label:
                return 18
            if "appartement" in asset_label:
                return 12
            if "duplex" in asset_label:
                return 8
            if "triplex" in asset_label:
                return 10
            if "villa" in asset_label:
                return 5
            if "maison" in asset_label:
                return 4

            return 2.5

        if parcel:
            if self.is_crm_building(parcel):
                units_count = len(self.get_crm_units(parcel))
                if units_count >= 8:
                    return 18
                if units_count >= 4:
                    return 12
                return 9

            area = getattr(parcel, "official_area_m2", 0) or 0
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
        if asset:
            if getattr(asset, "asset_category", None) and getattr(asset.asset_category, "label", None):
                return asset.asset_category.label
            if getattr(asset, "property_type", None) and getattr(asset.property_type, "label", None):
                return asset.property_type.label

        if parcel and self.is_crm_building(parcel):
            return self.get_crm_asset_label(parcel) or "Immeuble"

        return "Parcelle"

    # =========================================================
    # CONSTRUCTION HELPERS
    # =========================================================

    def month_range(self, year, month):
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        return first_day, last_day

    def get_parcel_tags_payload(self, parcel):
        try:
            return [
                self.serialize_tag(tag)
                for tag in parcel.tags.filter(
                    is_active=True,
                    program_id=parcel.program_id,
                ).select_related("program", "program__project").order_by("name")
            ]
        except Exception:
            return []
    def get_parcel_or_asset_construction_project(self, parcel=None, asset=None):
        if asset:
            qs = asset.construction_projects.all().order_by("-created_at")
            project = qs.first()
            if project:
                return project

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
        m1_y, m1_m = (m0_y - 1, 12) if m0_m == 1 else (m0_y, m0_m - 1)
        m2_y, m2_m = (m1_y - 1, 12) if m1_m == 1 else (m1_y, m1_m - 1)

        progress_m2 = self.get_monthly_progress_value(project, m2_y, m2_m)
        progress_m1 = self.get_monthly_progress_value(project, m1_y, m1_m)
        progress_m0 = self.get_monthly_progress_value(project, m0_y, m0_m)

        monthly_delta = round(progress_m0 - progress_m1, 2)

        valeur_hypothecaire = Decimal("0")

        if asset and getattr(asset, "mortgage_value", None) not in [None, ""]:
            valeur_hypothecaire = self.money_raw(asset.mortgage_value)
        elif parcel and getattr(parcel, "valeur_hypothecaire", None) not in [None, ""]:
            valeur_hypothecaire = self.money_raw(parcel.valeur_hypothecaire)
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

    def get_construction_stats_with_crm_fallback(self, parcel=None, asset=None):
        stats = self.get_construction_stats(parcel=parcel, asset=asset)

        if asset:
            return stats

        if not parcel:
            return stats

        crm_summary = self.get_crm_summary(parcel)
        if not crm_summary:
            return stats

        current_progress = 0.0
        valeur_hypothecaire = Decimal("0")

        try:
            current_progress = float(crm_summary.get("avancement_travaux_mois") or 0)
        except Exception:
            current_progress = 0.0

        try:
            valeur_hypothecaire = self.money_raw(crm_summary.get("valeur_hypothecaire_totale") or 0)
        except Exception:
            valeur_hypothecaire = Decimal("0")

        if current_progress > 0:
            stats["taux_avancement"] = f"{round(current_progress)}%"
            stats["taux_avancement_value"] = current_progress

        if valeur_hypothecaire > 0:
            stats["valeur_hypothecaire"] = self.money_display(valeur_hypothecaire)
            stats["valeur_hypothecaire_value"] = float(valeur_hypothecaire)

        return stats

    # =========================================================
    # SALES / RESERVATIONS HELPERS
    # =========================================================

    def get_sales_by_parcel(self, parcel_ids):
        if not parcel_ids:
            return {}

        sales = (
            SaleFile.objects.select_related("customer", "parcel", "program", "unit")
            .prefetch_related("payments", "buyers")
            .filter(parcel_id__in=parcel_ids, is_active=True)
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
            Reservation.objects.select_related("customer", "parcel", "program", "unit")
            .filter(parcel_id__in=parcel_ids, is_active=True)
            .order_by("-reservation_date", "-created_at")
        )

        reservations_by_parcel = {}
        for reservation in reservations:
            reservations_by_parcel.setdefault(reservation.parcel_id, reservation)
        return reservations_by_parcel

    def get_asset_sales_map(self, asset_ids):
        if not asset_ids:
            return {}

        sales = (
            SaleFile.objects.select_related("customer", "unit", "parcel", "program")
            .prefetch_related("payments", "buyers")
            .filter(unit__asset_id__in=asset_ids, is_active=True)
            .annotate(total_paid=Coalesce(Sum("payments__amount"), Decimal("0")))
            .order_by("-sale_date", "-created_at")
        )

        asset_sales = {}
        for sale in sales:
            asset_id = sale.unit.asset_id if sale.unit_id else None
            if asset_id:
                asset_sales.setdefault(asset_id, []).append(sale)
        return asset_sales

    def get_asset_reservations_map(self, asset_ids):
        if not asset_ids:
            return {}

        reservations = (
            Reservation.objects.select_related("customer", "unit", "parcel", "program")
            .filter(unit__asset_id__in=asset_ids, is_active=True)
            .order_by("-reservation_date", "-created_at")
        )

        asset_reservations = {}
        for reservation in reservations:
            asset_id = reservation.unit.asset_id if reservation.unit_id else None
            if asset_id:
                asset_reservations.setdefault(asset_id, []).append(reservation)
        return asset_reservations

    def get_asset_units_map(self, asset_ids):
        if not asset_ids:
            return {}

        units = (
            PropertyUnit.objects.select_related("unit_type", "asset", "program", "parcel")
            .filter(asset_id__in=asset_ids, is_active=True)
            .order_by("floor_number", "code")
        )

        asset_units = {}
        for unit in units:
            asset_units.setdefault(unit.asset_id, []).append(unit)
        return asset_units

    # =========================================================
    # FINANCIAL HELPERS
    # =========================================================

    def get_sale_financial_stats(self, sale=None, asset=None):
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

    def get_asset_aggregated_financial_stats(self, asset, sales=None, units=None):
        sales = sales or []
        units = units or []

        base_amount = Decimal("0")
        sold_amount = Decimal("0")
        amount_paid = Decimal("0")
        payments_count = 0

        if getattr(asset, "is_multi_unit", False) or units:
            for unit in units:
                if getattr(unit, "sale_price", None):
                    base_amount += self.money_raw(unit.sale_price)
                elif getattr(unit, "estimated_cost", None):
                    base_amount += self.money_raw(unit.estimated_cost)

            for sale in sales:
                sold_amount += self.money_raw(sale.net_price or sale.agreed_price)
                amount_paid += self.money_raw(getattr(sale, "total_paid", 0))
                try:
                    payments_count += sale.payments.count()
                except Exception:
                    pass

            if base_amount <= 0 and getattr(asset, "sale_price", None):
                base_amount = self.money_raw(asset.sale_price)
        else:
            primary_sale = sales[0] if sales else None
            return self.get_sale_financial_stats(sale=primary_sale, asset=asset)

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

    def get_unit_financial_stats(self, unit, sale=None):
        base_amount = Decimal("0")
        sold_amount = Decimal("0")
        amount_paid = Decimal("0")
        payments_count = 0

        if getattr(unit, "sale_price", None):
            base_amount = self.money_raw(unit.sale_price)
        elif getattr(unit, "estimated_cost", None):
            base_amount = self.money_raw(unit.estimated_cost)

        if sale:
            sold_amount = self.money_raw(sale.net_price or sale.agreed_price)
            amount_paid = self.money_raw(getattr(sale, "total_paid", 0))
            try:
                payments_count = sale.payments.count()
            except Exception:
                payments_count = 0

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

    def get_crm_financial_stats(self, parcel):
        summary = self.get_crm_summary(parcel)
        projection = self.get_crm_projection_data(parcel)

        base_amount = self.money_raw(summary.get("cout_actif_total") or projection.get("cout_actif") or 0)
        sold_amount = base_amount
        amount_paid = self.money_raw(summary.get("versement_client_total") or projection.get("versement_client") or 0)
        payments_count = 0

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

    def get_asset_unit_summary(self, asset, units, sales, reservations):
        total_units = len(units)
        available_units = 0
        reserved_units = 0
        sold_units = 0
        blocked_units = 0

        for unit in units:
            status = unit.commercial_status
            if status == "AVAILABLE":
                available_units += 1
            elif status in ["OPTIONED", "RESERVED"]:
                reserved_units += 1
            elif status in ["SOLD", "DELIVERED"]:
                sold_units += 1
            elif status == "BLOCKED":
                blocked_units += 1

        return {
            "total_units": total_units,
            "available_units": available_units,
            "reserved_units": reserved_units,
            "sold_units": sold_units,
            "blocked_units": blocked_units,
            "sales_count": len(sales),
            "reservations_count": len(reservations),
        }

    def get_crm_unit_summary(self, parcel):
        units = self.get_crm_units(parcel)
        total_units = len(units)

        sold_units = 0
        reserved_units = 0
        available_units = 0
        blocked_units = 0

        # Le CRM ne fournit pas un vrai statut unitaire ici.
        # On considère par défaut ces unités comme vendues/commercialisées.
        if self.is_crm_building(parcel):
            sold_units = total_units
        else:
            sold_units = 1 if total_units else 0

        return {
            "total_units": total_units,
            "available_units": available_units,
            "reserved_units": reserved_units,
            "sold_units": sold_units,
            "blocked_units": blocked_units,
            "sales_count": 0,
            "reservations_count": 0,
        }

    def get_asset_customer_summary(self, sales, reservations):
        customer_map = {}

        for sale in sales:
            if sale.customer_id:
                customer_map[sale.customer_id] = self.serialize_customer(sale.customer)

            try:
                for buyer in sale.buyers.select_related("customer").all():
                    if buyer.customer_id:
                        customer_map[buyer.customer_id] = self.serialize_customer(buyer.customer)
            except Exception:
                pass

        for reservation in reservations:
            if reservation.customer_id:
                customer_map[reservation.customer_id] = self.serialize_customer(reservation.customer)

        customers = [c for c in customer_map.values() if c]
        return {
            "count": len(customers),
            "items": customers[:20],
        }

    def get_crm_customer_summary(self, parcel):
        customers = self.get_crm_sync_data(parcel).get("customers") or []
        items = []
        for idx, customer_name in enumerate(customers[:20], start=1):
            items.append({
                "id": idx,
                "name": self.safe_str(customer_name, "Client"),
                "type": "CRM",
                "phone": "—",
                "email": "—",
            })
        return {
            "count": len(customers),
            "items": items,
        }

    def get_asset_sales_summary(self, sales):
        items = []
        for sale in sales[:20]:
            items.append({
                "sale_number": sale.sale_number,
                "sale_date": sale.sale_date.strftime("%d/%m/%Y") if sale.sale_date else "—",
                "customer": self.get_customer_name(sale.customer),
                "unit": sale.unit.label if sale.unit_id else "Actif global",
                "net_price": self.money_display(sale.net_price or sale.agreed_price),
                "total_paid": self.money_display(getattr(sale, "total_paid", 0)),
                "payment_progress": self.percent_display(
                    getattr(sale, "total_paid", 0),
                    sale.net_price or sale.agreed_price or 0
                ),
                "status": sale.get_status_display() if hasattr(sale, "get_status_display") else sale.status,
            })
        return items

    def get_crm_sales_summary(self, parcel):
        crm = self.get_crm_sync_data(parcel)
        summary = self.get_crm_summary(parcel)
        units = self.get_crm_units(parcel)

        items = []
        if self.is_crm_building(parcel):
            for unit in units[:20]:
                items.append({
                    "sale_number": "CRM",
                    "sale_date": "—",
                    "customer": self.safe_str(unit.get("client_nom_complet"), "—"),
                    "unit": self.safe_str(unit.get("label") or unit.get("lot"), "Actif global"),
                    "net_price": self.money_display(unit.get("cout_actif")),
                    "total_paid": self.money_display(unit.get("versement_client")),
                    "payment_progress": self.percent_display(
                        self.money_raw(unit.get("versement_client")),
                        self.money_raw(unit.get("cout_actif")),
                    ),
                    "status": "Synchronisé CRM",
                })
        else:
            items.append({
                "sale_number": "CRM",
                "sale_date": "—",
                "customer": self.get_crm_display_customer_name(parcel),
                "unit": "Actif global",
                "net_price": self.money_display(summary.get("cout_actif_total")),
                "total_paid": self.money_display(summary.get("versement_client_total")),
                "payment_progress": self.percent_display(
                    self.money_raw(summary.get("versement_client_total")),
                    self.money_raw(summary.get("cout_actif_total")),
                ),
                "status": "Synchronisé CRM",
            })

        return items

    def get_asset_main_client_label(self, asset, sales, reservations):
        if getattr(asset, "is_multi_unit", False) or len(sales) > 1:
            customer_names = []
            seen = set()

            for sale in sales:
                name = self.get_customer_name(sale.customer)
                if name not in seen and name != "—":
                    seen.add(name)
                    customer_names.append(name)

            for reservation in reservations:
                name = self.get_customer_name(reservation.customer)
                if name not in seen and name != "—":
                    seen.add(name)
                    customer_names.append(name)

            if not customer_names:
                return "—"
            if len(customer_names) == 1:
                return customer_names[0]
            return f"{len(customer_names)} clients"

        if sales:
            return self.get_customer_name(sales[0].customer)
        if reservations:
            return self.get_customer_name(reservations[0].customer)
        return "—"

    def map_sales_by_unit_id(self, sales):
        result = {}
        for sale in sales or []:
            if sale.unit_id and sale.unit_id not in result:
                result[sale.unit_id] = sale
        return result

    def map_reservations_by_unit_id(self, reservations):
        result = {}
        for reservation in reservations or []:
            if reservation.unit_id and reservation.unit_id not in result:
                result[reservation.unit_id] = reservation
        return result

    # =========================================================
    # FILTERS
    # =========================================================



    def apply_common_filters_assets(self, queryset, params):
        if params["program_id"]:
            queryset = queryset.filter(program_id=params["program_id"])

        if params["project_id"]:
            queryset = queryset.filter(program__project_id=params["project_id"])

        if params["status"]:
            queryset = queryset.filter(status=params["status"])

        if params.get("tag"):
            queryset = queryset.filter(
                parcel__tags__slug=params["tag"],
                parcel__tags__program_id=F("program_id"),
            )

        if params["bbox"]:
            queryset = queryset.filter(
                Q(parcel__geometry__intersects=params["bbox"]) |
                Q(parcel__centroid__within=params["bbox"])
            )

        if params["search"]:
            q = params["search"]
            queryset = queryset.filter(
                Q(label__icontains=q)
                | Q(code__icontains=q)
                | Q(program__name__icontains=q)
                | Q(program__project__nom__icontains=q)
                | Q(parcel__lot_number__icontains=q)
                | Q(parcel__parcel_code__icontains=q)
                | Q(property_type__label__icontains=q)
                | Q(asset_category__label__icontains=q)
                | Q(units__label__icontains=q)
                | Q(units__code__icontains=q)
                | Q(parcel__tags__name__icontains=q, parcel__tags__program_id=F("program_id"))
                | Q(parcel__tags__slug__icontains=q, parcel__tags__program_id=F("program_id"))
            ).distinct()

        return queryset

    def apply_common_filters_parcels(self, queryset, params):
        if params["program_id"]:
            queryset = queryset.filter(program_id=params["program_id"])

        if params["project_id"]:
            queryset = queryset.filter(program__project_id=params["project_id"])

        if params["status"]:
            queryset = queryset.filter(commercial_status=params["status"])

        if params.get("tag"):
            queryset = queryset.filter(
                tags__slug=params["tag"],
                tags__program_id=F("program_id"),
            )

        if params["bbox"]:
            queryset = queryset.filter(
                Q(geometry__intersects=params["bbox"]) |
                Q(centroid__within=params["bbox"])
            )

        if params["search"]:
            q = params["search"]
            queryset = queryset.filter(
                Q(lot_number__icontains=q)
                | Q(parcel_code__icontains=q)
                | Q(external_reference__icontains=q)
                | Q(program__name__icontains=q)
                | Q(program__project__nom__icontains=q)
                | Q(block__code__icontains=q)
                | Q(tags__name__icontains=q, tags__program_id=F("program_id"))
                | Q(tags__slug__icontains=q, tags__program_id=F("program_id"))
                | Q(metadata__crm_projection__display_customer_name__icontains=q)
                | Q(metadata__crm_lot_sync__asset_label__icontains=q)
            ).distinct()

        return queryset

    # =========================================================
    # TIMELINES
    # =========================================================

    def get_asset_timeline(self, asset, sales=None, reservations=None, zoom=17):
        if not self.should_include_timeline(zoom):
            return []

        sales = sales or []
        reservations = reservations or []
        items = []

        for reservation in reservations[:3]:
            if reservation.reservation_date:
                items.append({
                    "label": "Réservation",
                    "date": reservation.reservation_date.strftime("%d %b"),
                    "text": f"Réservation enregistrée ({reservation.unit.label if reservation.unit_id else 'actif'}).",
                    "iconBg": "bg-amber-100",
                })

        for sale in sales[:3]:
            if sale.sale_date:
                items.append({
                    "label": "Vente actée",
                    "date": sale.sale_date.strftime("%d %b"),
                    "text": f"Vente enregistrée ({sale.unit.label if sale.unit_id else 'actif'}).",
                    "iconBg": "bg-emerald-100",
                })

        try:
            for update in asset.updates.all()[:5]:
                items.append({
                    "label": update.get_stage_display() if hasattr(update, "get_stage_display") else getattr(update, "stage", "Mise à jour"),
                    "date": update.report_date.strftime("%d %b") if getattr(update, "report_date", None) else "—",
                    "text": getattr(update, "summary", None) or getattr(update, "details", None) or "Mise à jour chantier",
                    "iconBg": "bg-violet-100",
                })
        except Exception:
            pass

        return items[:8]

    def get_parcel_timeline(self, parcel, sale=None, reservation=None, zoom=17):
        if not self.should_include_timeline(zoom):
            return []

        items = [{
            "label": "Import parcellaire",
            "date": parcel.created_at.strftime("%d %b") if getattr(parcel, "created_at", None) else "—",
            "text": "Parcelle importée dans le système.",
            "iconBg": "bg-sky-100",
        }]

        if reservation and reservation.reservation_date:
            items.insert(0, {
                "label": "Réservation",
                "date": reservation.reservation_date.strftime("%d %b"),
                "text": "Réservation enregistrée sur la parcelle.",
                "iconBg": "bg-amber-100",
            })

        if sale and sale.sale_date:
            items.insert(0, {
                "label": "Vente actée",
                "date": sale.sale_date.strftime("%d %b"),
                "text": "Vente enregistrée dans le système.",
                "iconBg": "bg-emerald-100",
            })

        return items[:6]

    def get_crm_parcel_timeline(self, parcel, zoom=17):
        if not self.should_include_timeline(zoom):
            return []

        items = []

        try:
            for cp in parcel.construction_projects.all().order_by("-created_at")[:1]:
                for update in cp.updates.filter(is_active=True).order_by("-report_date", "-created_at")[:5]:
                    items.append({
                        "label": update.get_stage_display() if hasattr(update, "get_stage_display") else getattr(update, "stage", "Mise à jour"),
                        "date": update.report_date.strftime("%d %b") if getattr(update, "report_date", None) else "—",
                        "text": getattr(update, "summary", None) or getattr(update, "details", None) or "Mise à jour chantier",
                        "iconBg": "bg-violet-100",
                    })
        except Exception:
            pass

        crm = self.get_crm_sync_data(parcel)
        if crm and not items:
            items.append({
                "label": "Synchronisation CRM",
                "date": "—",
                "text": "Données CRM synchronisées sur la parcelle.",
                "iconBg": "bg-sky-100",
            })

        return items[:8]

    # =========================================================
    # SIDEBAR HELPERS
    # =========================================================

    def build_single_sidebar_data(
        self,
        *,
        asset,
        parcel,
        sale,
        reservation,
        financial_stats,
        construction_stats,
        can_view_patient,
        can_view_financial,
        can_view_construction,
    ):
        if can_view_patient:
            client_name = (
                self.get_customer_name(sale.customer)
                if sale and sale.customer_id
                else (
                    self.get_customer_name(reservation.customer)
                    if reservation and reservation.customer_id
                    else "—"
                )
            )
        else:
            client_name = self.get_masked_client_name()

        surface_value = "—"
        if asset and getattr(asset, "built_area_m2", None):
            surface_value = f"{asset.built_area_m2} m²"
        elif parcel and getattr(parcel, "official_area_m2", None):
            surface_value = f"{parcel.official_area_m2} m²"

        return {
            "client_name": client_name,
            "sale_number": sale.sale_number if sale else "—",
            "sale_date": sale.sale_date.strftime("%d/%m/%Y") if sale and sale.sale_date else "—",
            "reservation_number": reservation.reservation_number if reservation else "—",
            "reservation_date": reservation.reservation_date.strftime("%d/%m/%Y") if reservation and reservation.reservation_date else "—",
            "price": financial_stats["montant_vendu"] if can_view_financial else "Masqué",
            "base_amount": financial_stats["montant_base"] if can_view_financial else "Masqué",
            "amount_paid": financial_stats["montant_paye"] if can_view_financial else "Masqué",
            "payment_rate": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
            "payments_count": financial_stats["nombre_paiements"] if can_view_financial else 0,
            "construction_progress": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
            "mortgage_value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
            "surface": surface_value,
        }

    def build_building_sidebar_data(
        self,
        *,
        asset,
        parcel,
        units,
        sales,
        reservations,
        financial_stats,
        construction_stats,
        unit_summary,
        can_view_patient,
        can_view_financial,
        can_view_construction,
    ):
        if can_view_patient:
            customer_label = self.get_asset_main_client_label(asset, sales, reservations)
        else:
            customer_label = self.get_masked_client_name()

        if asset and getattr(asset, "gross_floor_area_m2", None):
            surface_value = f"{asset.gross_floor_area_m2} m²"
        elif asset and getattr(asset, "saleable_area_m2", None):
            surface_value = f"{asset.saleable_area_m2} m²"
        elif parcel and getattr(parcel, "official_area_m2", None):
            surface_value = f"{parcel.official_area_m2} m²"
        else:
            surface_value = "—"

        return {
            "label": asset.label if asset else "Immeuble",
            "global_client_label": customer_label,
            "total_units": unit_summary["total_units"],
            "available_units": unit_summary["available_units"],
            "reserved_units": unit_summary["reserved_units"],
            "sold_units": unit_summary["sold_units"],
            "blocked_units": unit_summary["blocked_units"],
            "sales_count": unit_summary["sales_count"],
            "reservations_count": unit_summary["reservations_count"],
            "surface": surface_value,
            "price": financial_stats["montant_base"] if can_view_financial else "Masqué",
            "sold_amount": financial_stats["montant_vendu"] if can_view_financial else "Masqué",
            "paid_amount": financial_stats["montant_paye"] if can_view_financial else "Masqué",
            "payment_rate": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
            "construction_progress": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
            "mortgage_value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
            "floors": getattr(asset, "floors", 0) if asset else 0,
        }

    def build_crm_single_sidebar_data(
        self,
        *,
        parcel,
        financial_stats,
        construction_stats,
        can_view_patient,
        can_view_financial,
        can_view_construction,
    ):
        summary = self.get_crm_summary(parcel)

        client_name = self.get_crm_display_customer_name(parcel) if can_view_patient else self.get_masked_client_name()

        return {
            "client_name": client_name,
            "sale_number": "CRM",
            "sale_date": "—",
            "reservation_number": "—",
            "reservation_date": "—",
            "price": financial_stats["montant_vendu"] if can_view_financial else "Masqué",
            "base_amount": financial_stats["montant_base"] if can_view_financial else "Masqué",
            "amount_paid": financial_stats["montant_paye"] if can_view_financial else "Masqué",
            "payment_rate": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
            "payments_count": financial_stats["nombre_paiements"] if can_view_financial else 0,
            "construction_progress": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
            "mortgage_value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
            "surface": f"{parcel.official_area_m2} m²" if getattr(parcel, "official_area_m2", None) else "—",
            "crm_source": "CRM",
            "crm_cost_total": self.money_display(summary.get("cout_actif_total")) if can_view_financial else "Masqué",
        }

    def build_crm_building_sidebar_data(
        self,
        *,
        parcel,
        financial_stats,
        construction_stats,
        unit_summary,
        can_view_patient,
        can_view_financial,
        can_view_construction,
    ):
        return {
            "label": self.get_crm_asset_label(parcel),
            "global_client_label": self.get_crm_display_customer_name(parcel) if can_view_patient else self.get_masked_client_name(),
            "total_units": unit_summary["total_units"],
            "available_units": unit_summary["available_units"],
            "reserved_units": unit_summary["reserved_units"],
            "sold_units": unit_summary["sold_units"],
            "blocked_units": unit_summary["blocked_units"],
            "sales_count": unit_summary["sales_count"],
            "reservations_count": unit_summary["reservations_count"],
            "surface": f"{parcel.official_area_m2} m²" if getattr(parcel, "official_area_m2", None) else "—",
            "price": financial_stats["montant_base"] if can_view_financial else "Masqué",
            "sold_amount": financial_stats["montant_vendu"] if can_view_financial else "Masqué",
            "paid_amount": financial_stats["montant_paye"] if can_view_financial else "Masqué",
            "payment_rate": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
            "construction_progress": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
            "mortgage_value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
            "floors": 0,
        }

    def build_building_units_payload(
        self,
        *,
        units,
        unit_sales,
        unit_reservations,
        can_view_patient,
        can_view_financial,
    ):
        sales_by_unit = self.map_sales_by_unit_id(unit_sales)
        reservations_by_unit = self.map_reservations_by_unit_id(unit_reservations)

        payload = []

        for unit in units[:100]:
            sale = sales_by_unit.get(unit.id)
            reservation = reservations_by_unit.get(unit.id)
            financial_stats = (
                self.get_unit_financial_stats(unit, sale=sale)
                if can_view_financial
                else self.get_masked_financial_stats()
            )
            unit_ui = self.get_unit_status_ui(unit.commercial_status)

            if can_view_patient:
                customer_name = (
                    self.get_customer_name(sale.customer)
                    if sale and sale.customer_id
                    else (
                        self.get_customer_name(reservation.customer)
                        if reservation and reservation.customer_id
                        else "—"
                    )
                )
            else:
                customer_name = self.get_masked_client_name()

            payload.append({
                "id": unit.id,
                "code": unit.code,
                "label": unit.label or unit.code,
                "slug": unit.slug,
                "type": unit.unit_type.label if unit.unit_type else "—",
                "building": unit.building or "—",
                "entrance": unit.entrance or "—",
                "staircase": unit.staircase or "—",
                "floor": unit.floor_number,
                "door_number": unit.door_number or "—",
                "bedrooms": unit.bedrooms or 0,
                "bathrooms": unit.bathrooms or 0,
                "status": unit_ui["status"],
                "statusBadge": unit_ui["statusBadge"],
                "commercial_status": unit.commercial_status,
                "surface": f"{unit.saleable_area_m2} m²" if unit.saleable_area_m2 else "—",
                "indoor_area": f"{unit.indoor_area_m2} m²" if unit.indoor_area_m2 else "—",
                "terrace_area": f"{unit.terrace_area_m2} m²" if unit.terrace_area_m2 else "—",
                "balcony_area": f"{unit.balcony_area_m2} m²" if unit.balcony_area_m2 else "—",
                "garden_area": f"{unit.garden_area_m2} m²" if unit.garden_area_m2 else "—",
                "parking_area": f"{unit.parking_area_m2} m²" if unit.parking_area_m2 else "—",
                "has_parking": bool(unit.has_parking),
                "has_garden": bool(unit.has_garden),
                "has_terrace": bool(unit.has_terrace),
                "has_balcony": bool(unit.has_balcony),
                "orientation": unit.get_orientation_display() if hasattr(unit, "get_orientation_display") else (unit.orientation or "—"),
                "price": financial_stats["montant_base"] if can_view_financial else "Masqué",
                "sold_amount": financial_stats["montant_vendu"] if can_view_financial else "Masqué",
                "paid_amount": financial_stats["montant_paye"] if can_view_financial else "Masqué",
                "payment_rate": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
                "payments_count": financial_stats["nombre_paiements"] if can_view_financial else 0,
                "customer": customer_name,
                "sale": {
                    "number": sale.sale_number if sale else "—",
                    "date": sale.sale_date.strftime("%d/%m/%Y") if sale and sale.sale_date else "—",
                    "status": sale.get_status_display() if sale and hasattr(sale, "get_status_display") else (sale.status if sale else "—"),
                },
                "reservation": {
                    "number": reservation.reservation_number if reservation else "—",
                    "date": reservation.reservation_date.strftime("%d/%m/%Y") if reservation and reservation.reservation_date else "—",
                    "status": reservation.get_status_display() if reservation and hasattr(reservation, "get_status_display") else (reservation.status if reservation else "—"),
                },
            })

        return payload

    def build_crm_building_units_payload(
        self,
        *,
        parcel,
        can_view_patient,
        can_view_financial,
    ):
        payload = []
        units = self.get_crm_units(parcel)

        for idx, unit in enumerate(units[:100], start=1):
            customer_name = self.safe_str(unit.get("client_nom_complet"), "—") if can_view_patient else self.get_masked_client_name()
            unit_amount = self.money_raw(unit.get("cout_actif"))
            unit_paid = self.money_raw(unit.get("versement_client"))
            payment_rate = self.safe_percent_value(unit_paid, unit_amount)

            payload.append({
                "id": idx,
                "code": self.safe_str(unit.get("lot"), f"U-{idx}"),
                "label": self.safe_str(unit.get("label"), f"Appartement {idx}"),
                "slug": "",
                "type": self.get_crm_asset_label(parcel),
                "building": self.get_crm_asset_label(parcel),
                "entrance": "—",
                "staircase": "—",
                "floor": None,
                "door_number": "—",
                "bedrooms": 0,
                "bathrooms": 0,
                "status": "Synchronisé CRM",
                "statusBadge": "bg-emerald-100 text-emerald-700",
                "commercial_status": "CRM",
                "surface": "—",
                "indoor_area": "—",
                "terrace_area": "—",
                "balcony_area": "—",
                "garden_area": "—",
                "parking_area": "—",
                "has_parking": False,
                "has_garden": False,
                "has_terrace": False,
                "has_balcony": False,
                "orientation": "—",
                "price": self.money_display(unit_amount) if can_view_financial else "Masqué",
                "sold_amount": self.money_display(unit_amount) if can_view_financial else "Masqué",
                "paid_amount": self.money_display(unit_paid) if can_view_financial else "Masqué",
                "payment_rate": f"{round(payment_rate)}%" if can_view_financial else "Masqué",
                "payments_count": 0,
                "customer": customer_name,
                "sale": {
                    "number": "CRM",
                    "date": "—",
                    "status": "Synchronisé CRM",
                },
                "reservation": {
                    "number": "—",
                    "date": "—",
                    "status": "—",
                },
            })

        return payload

    # =========================================================
    # BUILDERS
    # =========================================================

    def _build_from_assets(self, queryset, params):
        rights = getattr(self, "user_rights", {})
        can_view_financial = rights.get("can_view_financial_data", False)
        can_view_patient = rights.get("can_view_patient_data", False)
        can_view_construction = rights.get("can_view_construction_data", False)
        zoom = params["zoom"]

        queryset = queryset[:params["limit"]]

        asset_ids = list(queryset.values_list("id", flat=True))
        asset_units_map = self.get_asset_units_map(asset_ids)
        asset_sales_map = self.get_asset_sales_map(asset_ids)
        asset_reservations_map = self.get_asset_reservations_map(asset_ids)

        parcel_ids = [obj.parcel_id for obj in queryset if obj.parcel_id]
        sales_by_parcel = self.get_sales_by_parcel(parcel_ids)
        reservations_by_parcel = self.get_reservations_by_parcel(parcel_ids)

        assets_payload = []
        total_ca = Decimal("0")
        reserved_or_sold = 0

        for asset in queryset:
            parcel = getattr(asset, "parcel", None)
            units = asset_units_map.get(asset.id, [])
            unit_sales = asset_sales_map.get(asset.id, [])
            unit_reservations = asset_reservations_map.get(asset.id, [])

            direct_sale = sales_by_parcel.get(parcel.id) if parcel else None
            direct_reservation = reservations_by_parcel.get(parcel.id) if parcel else None

            sidebar_mode = self.get_sidebar_mode_for_asset(asset, units)
            is_multi = sidebar_mode == self.SIDEBAR_MODE_BUILDING

            effective_sales = unit_sales if is_multi else ([direct_sale] if direct_sale else [])
            effective_reservations = unit_reservations if is_multi else ([direct_reservation] if direct_reservation else [])

            ui = self.get_status_ui_from_asset_status(asset.status)

            construction_stats = (
                self.get_construction_stats(parcel=parcel, asset=asset)
                if can_view_construction
                else self.get_masked_construction_stats()
            )

            financial_stats = (
                self.get_asset_aggregated_financial_stats(asset=asset, sales=effective_sales, units=units)
                if can_view_financial
                else self.get_masked_financial_stats()
            )

            if can_view_financial and can_view_construction:
                priority_stats = self.get_hypotheque_payment_ratio(
                    construction_stats.get("valeur_hypothecaire_value", 0),
                    financial_stats.get("montant_paye_value", 0),
                )
                ui["color"] = priority_stats["priority_color"]
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

            if can_view_patient:
                client_name = self.get_asset_main_client_label(asset, effective_sales, effective_reservations)
                customers_summary = self.get_asset_customer_summary(effective_sales, effective_reservations)
            else:
                client_name = self.get_masked_client_name()
                customers_summary = {"count": 0, "items": []}

            unit_summary = self.get_asset_unit_summary(asset, units, effective_sales, effective_reservations)

            if asset.status in ["RESERVED", "SOLD", "UNDER_CONSTRUCTION", "COMPLETED"]:
                reserved_or_sold += 1

            if can_view_financial:
                total_ca += self.money_raw(financial_stats.get("montant_vendu_value", 0))

            details = [
                {
                    "label": "Projet",
                    "value": asset.program.project.nom if asset.program and getattr(asset.program, "project", None) else "—",
                },
                {"label": "Programme", "value": asset.program.name if asset.program else "—"},
                {"label": "Référence", "value": asset.code or "—"},
                {"label": "Nature", "value": self.get_asset_nature_label(asset)},
                {"label": "Type", "value": asset.property_type.label if asset.property_type else "—"},
                {"label": "Catégorie", "value": asset.asset_category.label if asset.asset_category else "—"},
                {"label": "Phase", "value": asset.phase.name if asset.phase else "—"},
                {
                    "label": "Parcelle",
                    "value": parcel.lot_number if parcel and parcel.lot_number else (parcel.parcel_code if parcel else "—"),
                },
            ]

            if is_multi:
                details.extend([
                    {"label": "Mode commercial", "value": "Vente par unités"},
                    {"label": "Unités totales", "value": str(unit_summary["total_units"])},
                    {"label": "Unités disponibles", "value": str(unit_summary["available_units"])},
                    {"label": "Unités réservées", "value": str(unit_summary["reserved_units"])},
                    {"label": "Unités vendues", "value": str(unit_summary["sold_units"])},
                ])
            else:
                details.append({"label": "Mode commercial", "value": "Vente globale de l'actif"})

            if can_view_patient:
                details.append({"label": "Client(s)", "value": client_name})

            if can_view_financial:
                details.append({
                    "label": "Valeur hypothécaire",
                    "value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
                })

            if can_view_financial and can_view_construction:
                details.append({"label": "Ratio hypo / paiements", "value": priority_stats["ratio_label"]})
                details.append({"label": "Niveau priorité", "value": priority_stats["priority_label"]})

            metrics = [
                {"label": "Étages", "value": str(asset.floors or 0)},
                {"label": "Chambres", "value": str(asset.bedrooms or 0)},
                {"label": "Unités", "value": str(unit_summary["total_units"]) if is_multi else "1"},
                {
                    "label": "Avancement",
                    "value": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
                },
            ]

            single_data = None
            building_data = None
            building_units = []

            if sidebar_mode == self.SIDEBAR_MODE_SINGLE:
                single_data = self.build_single_sidebar_data(
                    asset=asset,
                    parcel=parcel,
                    sale=direct_sale,
                    reservation=direct_reservation,
                    financial_stats=financial_stats,
                    construction_stats=construction_stats,
                    can_view_patient=can_view_patient,
                    can_view_financial=can_view_financial,
                    can_view_construction=can_view_construction,
                )
            else:
                building_data = self.build_building_sidebar_data(
                    asset=asset,
                    parcel=parcel,
                    units=units,
                    sales=unit_sales,
                    reservations=unit_reservations,
                    financial_stats=financial_stats,
                    construction_stats=construction_stats,
                    unit_summary=unit_summary,
                    can_view_patient=can_view_patient,
                    can_view_financial=can_view_financial,
                    can_view_construction=can_view_construction,
                )
                building_units = self.build_building_units_payload(
                    units=units,
                    unit_sales=unit_sales,
                    unit_reservations=unit_reservations,
                    can_view_patient=can_view_patient,
                    can_view_financial=can_view_financial,
                )

            assets_payload.append({
                "uid": f"asset-{asset.id}",
                "id": asset.id,
                "entity_type": "PROPERTY_ASSET",
                "sidebar_mode": sidebar_mode,
                "project": asset.program.project.nom if asset.program and getattr(asset.program, "project", None) else "—",
                "name": asset.label,
                "program": asset.program.name if asset.program else "—",
                "tags": self.get_parcel_tags_payload(parcel) if parcel else [],
                "type": asset.property_type.label if asset.property_type else "Actif immobilier",
                "asset_category": asset.asset_category.label if asset.asset_category else "—",
                "asset_nature": self.get_asset_nature_label(asset),
                "is_multi_unit": is_multi,
                "status": ui["status"],
                "statusKey": ui["statusKey"],
                "statusBadge": ui["statusBadge"],
                "color": ui["color"],
                "fillOpacity": ui["fillOpacity"],
                "price": (
                    financial_stats["montant_base"] if is_multi
                    else (self.money_display(asset.sale_price) if can_view_financial else "Masqué")
                ),
                "surface": (
                    f"{asset.built_area_m2} m²"
                    if getattr(asset, "built_area_m2", None)
                    else (f"{parcel.official_area_m2} m²" if parcel and getattr(parcel, "official_area_m2", None) else "—")
                ),
                "payment": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
                "client": client_name,
                "phase": asset.phase.name if asset.phase else "—",
                "center": self.get_center(parcel),
                "images": self.get_asset_images(asset, zoom=zoom),
                "details": details,
                "metrics": metrics,
                "timeline": self.get_asset_timeline(asset, sales=effective_sales, reservations=effective_reservations, zoom=zoom),
                "geometry": self.get_geometry_obj(parcel, zoom=zoom),
                "height": self.compute_asset_height(asset=asset, parcel=parcel),
                "base_height": self.compute_base_height(asset=asset, parcel=parcel),
                "building_type": self.get_3d_type(asset=asset, parcel=parcel),
                "financial_stats": financial_stats,
                "construction_stats": construction_stats,
                "priority_stats": priority_stats,
                "unit_summary": unit_summary,
                "customers": customers_summary if can_view_patient else {"count": 0, "items": []},
                "sales_summary": self.get_asset_sales_summary(effective_sales) if (can_view_financial and self.should_include_sales_summary(zoom)) else [],
                "units_preview": [
                    {
                        "id": unit.id,
                        "code": unit.code,
                        "label": unit.label,
                        "type": unit.unit_type.label if unit.unit_type else "—",
                        "floor": unit.floor_number,
                        "status": unit.get_commercial_status_display() if hasattr(unit, "get_commercial_status_display") else unit.commercial_status,
                        "statusBadge": self.get_unit_status_ui(unit.commercial_status)["statusBadge"],
                        "price": self.money_display(unit.sale_price) if can_view_financial else "Masqué",
                        "surface": f"{unit.saleable_area_m2} m²" if unit.saleable_area_m2 else "—",
                    }
                    for unit in (units[:20] if self.should_include_units_preview(zoom) else [])
                ],
                "single_data": single_data,
                "building_data": building_data,
                "building_units": building_units,
            })

        summaries = [
            {"label": "Actifs", "value": str(len(assets_payload))},
            {"label": "Réservés/Vendus", "value": str(reserved_or_sold)},
            {"label": "CA potentiel", "value": self.money_display(total_ca or 0) if can_view_financial else "Masqué"},
        ]

        return {
            "source": "property_assets",
            "assets": assets_payload,
            "summaries": summaries,
        }

    def _build_from_parcels(self, queryset, params):
        rights = getattr(self, "user_rights", {})
        can_view_financial = rights.get("can_view_financial_data", False)
        can_view_patient = rights.get("can_view_patient_data", False)
        can_view_construction = rights.get("can_view_construction_data", False)
        zoom = params["zoom"]

        queryset = queryset[:params["limit"]]

        parcel_ids = list(queryset.values_list("id", flat=True))
        sales_by_parcel = self.get_sales_by_parcel(parcel_ids)
        reservations_by_parcel = self.get_reservations_by_parcel(parcel_ids)

        assets_payload = []
        reserved_or_sold = 0
        total_ca = Decimal("0")

        for parcel in queryset:
            sale = sales_by_parcel.get(parcel.id)
            reservation = reservations_by_parcel.get(parcel.id)

            has_crm = self.has_crm_payload(parcel)
            sidebar_mode = self.get_sidebar_mode_for_parcel(parcel) if has_crm else self.SIDEBAR_MODE_SINGLE

            if has_crm:
                ui = self.get_crm_status_ui(parcel)
                financial_stats = self.get_crm_financial_stats(parcel) if can_view_financial else self.get_masked_financial_stats()
                construction_stats = self.get_construction_stats_with_crm_fallback(parcel=parcel, asset=None) if can_view_construction else self.get_masked_construction_stats()
                client_name = self.get_crm_display_customer_name(parcel) if can_view_patient else self.get_masked_client_name()
                unit_summary = self.get_crm_unit_summary(parcel)
                customers_summary = self.get_crm_customer_summary(parcel) if can_view_patient else {"count": 0, "items": []}
                crm_parent = self.get_crm_parent_reference(parcel)
                crm_asset_label = self.get_crm_asset_label(parcel)

                if ui["statusKey"] in ["Réservés", "Vendus", "En construction"]:
                    reserved_or_sold += 1

                if can_view_financial:
                    total_ca += self.money_raw(financial_stats.get("montant_vendu_value", 0))

                if can_view_financial and can_view_construction:
                    priority_stats = self.get_hypotheque_payment_ratio(
                        construction_stats.get("valeur_hypothecaire_value", 0),
                        financial_stats.get("montant_paye_value", 0),
                    )
                    ui["color"] = priority_stats["priority_color"]
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

                details = [
                    {
                        "label": "Projet",
                        "value": parcel.program.project.nom if parcel.program and getattr(parcel.program, "project", None) else "—",
                    },
                    {"label": "Programme", "value": parcel.program.name if parcel.program else "—"},
                    {"label": "Îlot", "value": crm_parent["ilot"] or "—"},
                    {"label": "Lot", "value": crm_parent["lot"] or "—"},
                    {"label": "Référence", "value": parcel.parcel_code or "—"},
                    {"label": "Type CRM", "value": crm_asset_label or "—"},
                    {"label": "Surface", "value": f"{parcel.official_area_m2} m²" if getattr(parcel, "official_area_m2", None) else "—"},
                ]

                if sidebar_mode == self.SIDEBAR_MODE_BUILDING:
                    details.extend([
                        {"label": "Mode commercial", "value": "Immeuble CRM multi-unités"},
                        {"label": "Unités totales", "value": str(unit_summary["total_units"])},
                        {"label": "Unités vendues", "value": str(unit_summary["sold_units"])},
                    ])
                else:
                    details.append({"label": "Mode commercial", "value": "Actif CRM mono-unité"})

                if can_view_patient:
                    details.append({"label": "Client(s)", "value": client_name})

                if can_view_financial:
                    details.append({
                        "label": "Valeur hypothécaire",
                        "value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
                    })

                if can_view_financial and can_view_construction:
                    details.append({"label": "Ratio hypo / paiements", "value": priority_stats["ratio_label"]})
                    details.append({"label": "Niveau priorité", "value": priority_stats["priority_label"]})

                metrics = [
                    {"label": "Îlot", "value": crm_parent["ilot"] or "—"},
                    {"label": "Unités", "value": str(unit_summary["total_units"]) if sidebar_mode == self.SIDEBAR_MODE_BUILDING else "1"},
                    {
                        "label": "Avancement",
                        "value": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
                    },
                ]

                if sidebar_mode == self.SIDEBAR_MODE_BUILDING:
                    single_data = None
                    building_data = self.build_crm_building_sidebar_data(
                        parcel=parcel,
                        financial_stats=financial_stats,
                        construction_stats=construction_stats,
                        unit_summary=unit_summary,
                        can_view_patient=can_view_patient,
                        can_view_financial=can_view_financial,
                        can_view_construction=can_view_construction,
                    )
                    building_units = self.build_crm_building_units_payload(
                        parcel=parcel,
                        can_view_patient=can_view_patient,
                        can_view_financial=can_view_financial,
                    )
                else:
                    single_data = self.build_crm_single_sidebar_data(
                        parcel=parcel,
                        financial_stats=financial_stats,
                        construction_stats=construction_stats,
                        can_view_patient=can_view_patient,
                        can_view_financial=can_view_financial,
                        can_view_construction=can_view_construction,
                    )
                    building_data = None
                    building_units = []

                assets_payload.append({
                    "uid": f"parcel-crm-{parcel.id}",
                    "id": parcel.id,
                    "entity_type": "PARCEL",
                    "sidebar_mode": sidebar_mode,
                    "project": parcel.program.project.nom if parcel.program and getattr(parcel.program, "project", None) else "—",
                    "name": (
                        crm_asset_label
                        if sidebar_mode == self.SIDEBAR_MODE_BUILDING
                        else f"Lot {crm_parent['lot'] or parcel.lot_number or parcel.parcel_code or parcel.id}"
                    ),
                    "program": parcel.program.name if parcel.program else "—",
                    "tags": self.get_parcel_tags_payload(parcel),
                    "type": crm_asset_label if sidebar_mode == self.SIDEBAR_MODE_BUILDING else "Parcelle",
                    "asset_category": "—",
                    "asset_nature": "Immeuble CRM" if sidebar_mode == self.SIDEBAR_MODE_BUILDING else "Parcelle CRM",
                    "is_multi_unit": sidebar_mode == self.SIDEBAR_MODE_BUILDING,
                    "status": ui["status"],
                    "statusKey": ui["statusKey"],
                    "statusBadge": ui["statusBadge"],
                    "color": ui["color"],
                    "fillOpacity": ui["fillOpacity"],
                    "price": financial_stats["montant_vendu"] if can_view_financial else "Masqué",
                    "surface": f"{parcel.official_area_m2} m²" if getattr(parcel, "official_area_m2", None) else "—",
                    "payment": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
                    "client": client_name,
                    "phase": parcel.phase.name if getattr(parcel, "phase", None) else "—",
                    "center": self.get_center(parcel),
                    "images": self.get_parcel_images(parcel, zoom=zoom),
                    "details": details,
                    "metrics": metrics,
                    "timeline": self.get_crm_parcel_timeline(parcel, zoom=zoom),
                    "geometry": self.get_geometry_obj(parcel, zoom=zoom),
                    "height": self.compute_asset_height(parcel=parcel),
                    "base_height": self.compute_base_height(parcel=parcel),
                    "building_type": self.get_3d_type(parcel=parcel),
                    "financial_stats": financial_stats,
                    "construction_stats": construction_stats,
                    "priority_stats": priority_stats,
                    "unit_summary": unit_summary,
                    "customers": customers_summary,
                    "sales_summary": self.get_crm_sales_summary(parcel) if (can_view_financial and self.should_include_sales_summary(zoom)) else [],
                    "units_preview": [
                        {
                            "id": idx,
                            "code": self.safe_str(unit.get("lot"), f"U-{idx}"),
                            "label": self.safe_str(unit.get("label"), f"Appartement {idx}"),
                            "type": crm_asset_label or "Unité",
                            "floor": None,
                            "status": "Synchronisé CRM",
                            "statusBadge": "bg-emerald-100 text-emerald-700",
                            "price": self.money_display(unit.get("cout_actif")) if can_view_financial else "Masqué",
                            "surface": "—",
                        }
                        for idx, unit in enumerate(
                            self.get_crm_units(parcel)[:20] if self.should_include_units_preview(zoom) else [],
                            start=1
                        )
                    ],
                    "single_data": single_data,
                    "building_data": building_data,
                    "building_units": building_units,
                })

                continue

            # ==========================
            # Fallback non-CRM classique
            # ==========================
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
                total_ca += self.money_raw(sale.net_price or sale.agreed_price)

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
                ui["color"] = priority_stats["priority_color"]
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

            if can_view_financial:
                details.append({
                    "label": "Valeur hypothécaire",
                    "value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
                })

            if can_view_financial and can_view_construction:
                details.append({"label": "Ratio hypo / paiements", "value": priority_stats["ratio_label"]})
                details.append({"label": "Niveau priorité", "value": priority_stats["priority_label"]})

            metrics = [
                {"label": "Accès route", "value": "Oui" if parcel.has_road_access else "Non"},
                {"label": "Angle", "value": "Oui" if parcel.is_corner else "Non"},
                {
                    "label": "Avancement",
                    "value": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
                },
            ]

            assets_payload.append({
                "uid": f"parcel-{parcel.id}",
                "id": parcel.id,
                "entity_type": "PARCEL",
                "sidebar_mode": self.SIDEBAR_MODE_SINGLE,
                "project": parcel.program.project.nom if parcel.program and getattr(parcel.program, "project", None) else "—",
                "name": f"Lot {parcel.lot_number or parcel.parcel_code or parcel.id}",
                "program": parcel.program.name if parcel.program else "—",
                "tags": self.get_parcel_tags_payload(parcel),
                "type": "Parcelle",
                "asset_category": "—",
                "asset_nature": "Parcelle",
                "is_multi_unit": False,
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
                "images": self.get_parcel_images(parcel, zoom=zoom),
                "details": details,
                "metrics": metrics,
                "timeline": self.get_parcel_timeline(parcel, sale=sale, reservation=reservation, zoom=zoom),
                "geometry": self.get_geometry_obj(parcel, zoom=zoom),
                "height": self.compute_asset_height(parcel=parcel),
                "base_height": self.compute_base_height(parcel=parcel),
                "building_type": self.get_3d_type(parcel=parcel),
                "financial_stats": financial_stats,
                "construction_stats": construction_stats,
                "priority_stats": priority_stats,
                "unit_summary": {
                    "total_units": 0,
                    "available_units": 0,
                    "reserved_units": 0,
                    "sold_units": 0,
                    "blocked_units": 0,
                    "sales_count": 1 if sale else 0,
                    "reservations_count": 1 if reservation else 0,
                },
                "customers": {
                    "count": 1 if (can_view_patient and client_name != "—") else 0,
                    "items": [],
                },
                "sales_summary": [],
                "units_preview": [],
                "single_data": {
                    "client_name": client_name,
                    "sale_number": sale.sale_number if sale else "—",
                    "sale_date": sale.sale_date.strftime("%d/%m/%Y") if sale and sale.sale_date else "—",
                    "reservation_number": reservation.reservation_number if reservation else "—",
                    "reservation_date": reservation.reservation_date.strftime("%d/%m/%Y") if reservation and reservation.reservation_date else "—",
                    "price": financial_stats["montant_vendu"] if can_view_financial else "Masqué",
                    "base_amount": financial_stats["montant_base"] if can_view_financial else "Masqué",
                    "amount_paid": financial_stats["montant_paye"] if can_view_financial else "Masqué",
                    "payment_rate": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
                    "payments_count": financial_stats["nombre_paiements"] if can_view_financial else 0,
                    "construction_progress": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
                    "mortgage_value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
                    "surface": f"{parcel.official_area_m2} m²" if parcel.official_area_m2 else "—",
                },
                "building_data": None,
                "building_units": [],
            })

        summaries = [
            {"label": "Actifs", "value": str(len(assets_payload))},
            {"label": "Réservés/Vendus", "value": str(reserved_or_sold)},
            {"label": "CA potentiel", "value": self.money_display(total_ca) if can_view_financial else "Masqué"},
        ]

        return {
            "source": "parcels",
            "assets": assets_payload,
            "summaries": summaries,
        }

    # =========================================================
    # GET
    # =========================================================
    def get_tag_filters(self, parcels_queryset=None, program_id=None, project_id=None):
        qs = ParcelTag.objects.filter(is_active=True).select_related("program", "program__project")

        if program_id:
            qs = qs.filter(program_id=program_id)

        elif project_id:
            qs = qs.filter(program__project_id=project_id)

        elif parcels_queryset is not None:
            program_ids = parcels_queryset.values_list("program_id", flat=True).distinct()
            qs = qs.filter(program_id__in=program_ids)

        return [self.serialize_tag(tag) for tag in qs.order_by("name")]
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
                "asset_category",
            )
            .prefetch_related(
                "photos",
                "updates",
                "parcel__documents",
                "parcel__tags",
                "units",
                "units__unit_type",
                "construction_projects",
                "construction_projects__updates",
                "construction_projects__photos",
            )
            .filter(is_active=True)
            .order_by("code")
        )
        asset_queryset = self.apply_common_filters_assets(asset_queryset, params)

        parcel_queryset = (
            Parcel.objects.select_related(
                "program",
                "program__project",
                "phase",
                "block",
            )
            .prefetch_related(
                "tags",
                "documents",
                "construction_projects__photos",
                "construction_projects__updates",
            )
            .filter(is_active=True)
            .exclude(geometry__isnull=True)
            .order_by("lot_number", "id")
        )
        parcel_queryset = self.apply_common_filters_parcels(parcel_queryset, params)

        asset_parcel_ids = list(
            asset_queryset.exclude(parcel_id__isnull=True).values_list("parcel_id", flat=True)
        )
        parcel_queryset = parcel_queryset.exclude(id__in=asset_parcel_ids)

        asset_data = self._build_from_assets(asset_queryset, params) if asset_queryset.exists() else {
            "source": "property_assets",
            "assets": [],
            "summaries": [],
        }

        parcel_data = self._build_from_parcels(parcel_queryset, params) if parcel_queryset.exists() else {
            "source": "parcels",
            "assets": [],
            "summaries": [],
        }

        asset_items = asset_data.get("assets", [])
        parcel_items = parcel_data.get("assets", [])

        rights = getattr(self, "user_rights", {})
        can_view_financial = rights.get("can_view_financial_data", False)

        combined_assets = asset_items + parcel_items

        reserved_or_sold = 0
        total_ca = Decimal("0")

        for item in combined_assets:
            if item.get("statusKey") in ["Réservés", "Vendus", "En construction"]:
                reserved_or_sold += 1

            if can_view_financial:
                try:
                    total_ca += Decimal(str(item.get("financial_stats", {}).get("montant_vendu_value", 0) or 0))
                except Exception:
                    pass

        summaries = [
            {"label": "Actifs", "value": str(len(combined_assets))},
            {"label": "Réservés/Vendus", "value": str(reserved_or_sold)},
            {"label": "CA potentiel", "value": self.money_display(total_ca) if can_view_financial else "Masqué"},
        ]
        all_relevant_parcel_ids = set(
            asset_queryset.exclude(parcel_id__isnull=True).values_list("parcel_id", flat=True)
        ) | set(parcel_queryset.values_list("id", flat=True))

        tag_filters = self.get_tag_filters(
            parcels_queryset=Parcel.objects.filter(id__in=all_relevant_parcel_ids),
            program_id=params.get("program_id"),
            project_id=params.get("project_id"),
        )
        return Response({
            "source": "mixed",
            "assets": combined_assets,
            "summaries": summaries,
            "filters": self.FILTERS,
            "tag_filters": tag_filters,
            "user_rights": rights,
            "counts": {
                "assets_count": len(asset_items),
                "parcels_count": len(parcel_items),
                "total_count": len(combined_assets),
            },

            "map_context": {
                "zoom": params["zoom"],
                "bbox_applied": bool(params["bbox"]),
                "limit": params["limit"],
                "geometry_included": self.should_include_geometry(params["zoom"]),
                "images_included": self.should_include_images(params["zoom"]),
            }
        })
# from rest_framework import status
# from parcelaire.sap.business_partner import SAPBusinessPartnerService
# from parcelaire.sap.exceptions import SAPError
#
# import calendar
# import json
# from datetime import date
# from decimal import Decimal
#
# from django.contrib.gis.geos import Polygon
# from django.contrib.gis.db.models.functions import Transform
# from django.db.models import Q, Sum
# from django.db.models.functions import Coalesce
# from rest_framework.permissions import IsAuthenticatedOrReadOnly
# from rest_framework.response import Response
# from rest_framework.views import APIView
#
# from parcelaire.models import (
#     Parcel,
#     PropertyAsset,
#     PropertyUnit,
#     Reservation,
#     SaleFile,
# )
#
#
# def user_can_view_financial_data(user):
#     return user.is_superuser or user.has_perm("parcelaire.view_financial_data")
#
#
# def user_can_view_patient_data(user):
#     return user.is_superuser or user.has_perm("parcelaire.view_patient_data")
#
#
# def user_can_view_construction_data(user):
#     return user.is_superuser or user.has_perm("parcelaire.view_construction_data")
#
#
# class RealEstateMapAPIView(APIView):
#     permission_classes = [IsAuthenticatedOrReadOnly]
#
#     FILTERS = ["Tous", "Disponibles", "Réservés", "Vendus", "En construction"]
#
#     DEFAULT_LIMIT = 1200
#     MAX_LIMIT = 2500
#
#     # =========================================================
#     # PERMISSIONS
#     # =========================================================
#
#     def get_user_rights(self, request):
#         user = request.user
#         return {
#             "can_view_financial_data": user.is_authenticated and (
#                 user.is_superuser or user.has_perm("parcelaire.view_financial_data")
#             ),
#             "can_view_patient_data": user.is_authenticated and (
#                 user.is_superuser or user.has_perm("parcelaire.view_patient_data")
#             ),
#             "can_view_construction_data": user.is_authenticated and (
#                 user.is_superuser or user.has_perm("parcelaire.view_construction_data")
#             ),
#         }
#
#     # =========================================================
#     # QUERY PARAMS / MAP PARAMS
#     # =========================================================
#
#     def parse_int(self, value, default=0):
#         try:
#             return int(value)
#         except Exception:
#             return default
#
#     def parse_bbox(self, value):
#         """
#         bbox attendu: minLng,minLat,maxLng,maxLat
#         """
#         if not value:
#             return None
#
#         try:
#             parts = [float(x.strip()) for x in value.split(",")]
#             if len(parts) != 4:
#                 return None
#
#             min_lng, min_lat, max_lng, max_lat = parts
#
#             if min_lng >= max_lng or min_lat >= max_lat:
#                 return None
#
#             return Polygon.from_bbox((min_lng, min_lat, max_lng, max_lat))
#         except Exception:
#             return None
#
#     def get_geometry_precision_from_zoom(self, zoom):
#         """
#         Plus le zoom est faible, moins on renvoie de géométrie détaillée.
#         """
#         if zoom <= 12:
#             return None
#         if zoom <= 14:
#             return 4
#         if zoom <= 16:
#             return 5
#         return 6
#
#     def should_include_geometry(self, zoom):
#         return zoom >= 14
#
#     def should_include_images(self, zoom):
#         return zoom >= 16
#
#     def should_include_timeline(self, zoom):
#         return zoom >= 16
#
#     def should_include_units_preview(self, zoom):
#         return zoom >= 16
#
#     def should_include_sales_summary(self, zoom):
#         return zoom >= 16
#
#     def normalize_query(self, request):
#         zoom = self.parse_int(request.GET.get("zoom"), default=17)
#         limit = self.parse_int(request.GET.get("limit"), default=self.DEFAULT_LIMIT)
#         if limit <= 0:
#             limit = self.DEFAULT_LIMIT
#         limit = min(limit, self.MAX_LIMIT)
#
#         return {
#             "program_id": request.GET.get("program"),
#             "project_id": request.GET.get("project"),
#             "status": request.GET.get("status"),
#             "search": (request.GET.get("search") or "").strip(),
#             "bbox": self.parse_bbox(request.GET.get("bbox")),
#             "zoom": zoom,
#             "limit": limit,
#         }
#
#     # =========================================================
#     # HELPERS DECIMAL / FORMAT
#     # =========================================================
#
#     def money_raw(self, value):
#         if value in [None, ""]:
#             return Decimal("0")
#         try:
#             return Decimal(value)
#         except Exception:
#             return Decimal("0")
#
#     def money_display(self, value):
#         if value in [None, ""]:
#             return "—"
#         try:
#             value = Decimal(value)
#         except Exception:
#             return str(value)
#         return f"{int(value):,} FCFA".replace(",", " ")
#
#     def percent_display(self, num, den):
#         if not den or den == 0:
#             return "0%"
#         try:
#             pct = (Decimal(num or 0) / Decimal(den)) * 100
#             return f"{round(pct)}%"
#         except Exception:
#             return "0%"
#
#     def safe_percent_value(self, num, den):
#         try:
#             num = Decimal(num or 0)
#             den = Decimal(den or 0)
#             if den <= 0:
#                 return 0
#             return round((num / den) * 100, 2)
#         except Exception:
#             return 0
#
#     def format_percent_value(self, value):
#         try:
#             return f"{round(float(value or 0))}%"
#         except Exception:
#             return "0%"
#
#     # =========================================================
#     # SAFE / MASKED BLOCKS
#     # =========================================================
#
#     def get_masked_financial_stats(self):
#         return {
#             "montant_base": "Masqué",
#             "montant_base_value": 0,
#             "montant_vendu": "Masqué",
#             "montant_vendu_value": 0,
#             "montant_paye": "Masqué",
#             "montant_paye_value": 0,
#             "nombre_paiements": 0,
#             "taux_paiement": "Masqué",
#             "taux_paiement_value": 0,
#         }
#
#     def get_masked_construction_stats(self):
#         return {
#             "taux_avancement": "Masqué",
#             "taux_avancement_value": 0,
#             "valeur_hypothecaire": "Masqué",
#             "valeur_hypothecaire_value": 0,
#             "budget_previsionnel": "Masqué",
#             "budget_previsionnel_value": 0,
#             "cout_reel": "Masqué",
#             "cout_reel_value": 0,
#             "comparatif_progression": {
#                 "il_y_a_2_mois": 0,
#                 "mois_dernier": 0,
#                 "mois_en_cours": 0,
#             },
#             "evolution_mensuelle": 0,
#             "evolution_mensuelle_label": "Masqué",
#         }
#
#     def get_masked_client_name(self):
#         return "Masqué"
#
#     # =========================================================
#     # STATUS UI
#     # =========================================================
#
#     def get_status_ui_from_asset_status(self, status):
#         mapping = {
#             "AVAILABLE": {
#                 "status": "Disponible",
#                 "statusKey": "Disponibles",
#                 "statusBadge": "bg-sky-100 text-sky-700",
#                 "color": "#38bdf8",
#                 "fillOpacity": 0.78,
#             },
#             "RESERVED": {
#                 "status": "Réservé",
#                 "statusKey": "Réservés",
#                 "statusBadge": "bg-amber-100 text-amber-700",
#                 "color": "#f59e0b",
#                 "fillOpacity": 0.80,
#             },
#             "SOLD": {
#                 "status": "Vendu",
#                 "statusKey": "Vendus",
#                 "statusBadge": "bg-emerald-100 text-emerald-700",
#                 "color": "#10b981",
#                 "fillOpacity": 0.78,
#             },
#             "UNDER_CONSTRUCTION": {
#                 "status": "En construction",
#                 "statusKey": "En construction",
#                 "statusBadge": "bg-violet-100 text-violet-700",
#                 "color": "#8b5cf6",
#                 "fillOpacity": 0.80,
#             },
#             "PLANNED": {
#                 "status": "Planifié",
#                 "statusKey": "Disponibles",
#                 "statusBadge": "bg-slate-100 text-slate-700",
#                 "color": "#94a3b8",
#                 "fillOpacity": 0.72,
#             },
#             "DESIGNED": {
#                 "status": "Conçu",
#                 "statusKey": "Disponibles",
#                 "statusBadge": "bg-indigo-100 text-indigo-700",
#                 "color": "#6366f1",
#                 "fillOpacity": 0.76,
#             },
#             "COMPLETED": {
#                 "status": "Achevé",
#                 "statusKey": "Vendus",
#                 "statusBadge": "bg-emerald-100 text-emerald-700",
#                 "color": "#10b981",
#                 "fillOpacity": 0.78,
#             },
#             "BLOCKED": {
#                 "status": "Bloqué",
#                 "statusKey": "Réservés",
#                 "statusBadge": "bg-rose-100 text-rose-700",
#                 "color": "#f43f5e",
#                 "fillOpacity": 0.80,
#             },
#         }
#         return mapping.get(
#             status,
#             {
#                 "status": status or "Inconnu",
#                 "statusKey": "Tous",
#                 "statusBadge": "bg-slate-100 text-slate-700",
#                 "color": "#94a3b8",
#                 "fillOpacity": 0.75,
#             },
#         )
#
#     def get_status_ui_from_parcel_status(self, status):
#         mapping = {
#             "AVAILABLE": {
#                 "status": "Disponible",
#                 "statusKey": "Disponibles",
#                 "statusBadge": "bg-sky-100 text-sky-700",
#                 "color": "#38bdf8",
#                 "fillOpacity": 0.78,
#             },
#             "OPTIONED": {
#                 "status": "Réservé",
#                 "statusKey": "Réservés",
#                 "statusBadge": "bg-amber-100 text-amber-700",
#                 "color": "#f59e0b",
#                 "fillOpacity": 0.80,
#             },
#             "RESERVED": {
#                 "status": "Réservé",
#                 "statusKey": "Réservés",
#                 "statusBadge": "bg-amber-100 text-amber-700",
#                 "color": "#f59e0b",
#                 "fillOpacity": 0.80,
#             },
#             "SOLD": {
#                 "status": "Vendu",
#                 "statusKey": "Vendus",
#                 "statusBadge": "bg-emerald-100 text-emerald-700",
#                 "color": "#10b981",
#                 "fillOpacity": 0.78,
#             },
#             "BLOCKED": {
#                 "status": "Bloqué",
#                 "statusKey": "Réservés",
#                 "statusBadge": "bg-rose-100 text-rose-700",
#                 "color": "#f43f5e",
#                 "fillOpacity": 0.80,
#             },
#             "LITIGATION": {
#                 "status": "Bloqué",
#                 "statusKey": "Réservés",
#                 "statusBadge": "bg-rose-100 text-rose-700",
#                 "color": "#f43f5e",
#                 "fillOpacity": 0.80,
#             },
#             "ARCHIVED": {
#                 "status": "Archivé",
#                 "statusKey": "Tous",
#                 "statusBadge": "bg-slate-100 text-slate-700",
#                 "color": "#94a3b8",
#                 "fillOpacity": 0.65,
#             },
#         }
#         return mapping.get(
#             status,
#             {
#                 "status": "Disponible",
#                 "statusKey": "Disponibles",
#                 "statusBadge": "bg-sky-100 text-sky-700",
#                 "color": "#38bdf8",
#                 "fillOpacity": 0.78,
#             },
#         )
#
#     # =========================================================
#     # PRIORITE HYPO / PAIEMENT
#     # =========================================================
#
#     def get_hypotheque_payment_ratio(self, valeur_hypothecaire, montant_paye):
#         try:
#             valeur_hypothecaire = Decimal(valeur_hypothecaire or 0)
#             montant_paye = Decimal(montant_paye or 0)
#
#             if valeur_hypothecaire <= 0:
#                 return {
#                     "ratio_value": 0,
#                     "ratio_label": "0%",
#                     "priority": "LOW",
#                     "priority_label": "Priorité faible",
#                     "priority_color": "#22c55e",
#                     "priority_badge": "bg-emerald-100 text-emerald-700",
#                     "priority_dot": "green",
#                 }
#
#             ratio = ((montant_paye - valeur_hypothecaire) / valeur_hypothecaire) * Decimal("100")
#             ratio = round(ratio, 2)
#
#             if ratio <= Decimal("-19"):
#                 return {
#                     "ratio_value": float(ratio),
#                     "ratio_label": f"{ratio}%",
#                     "priority": "LOW",
#                     "priority_label": "Priorité faible",
#                     "priority_color": "#22c55e",
#                     "priority_badge": "bg-emerald-100 text-emerald-700",
#                     "priority_dot": "green",
#                 }
#             elif Decimal("-19") < ratio < Decimal("0"):
#                 return {
#                     "ratio_value": float(ratio),
#                     "ratio_label": f"{ratio}%",
#                     "priority": "MEDIUM",
#                     "priority_label": "Priorité moyenne",
#                     "priority_color": "#f59e0b",
#                     "priority_badge": "bg-amber-100 text-amber-700",
#                     "priority_dot": "orange",
#                 }
#             else:
#                 return {
#                     "ratio_value": float(ratio),
#                     "ratio_label": f"{ratio}%",
#                     "priority": "HIGH",
#                     "priority_label": "Priorité élevée",
#                     "priority_color": "#ef4444",
#                     "priority_badge": "bg-rose-100 text-rose-700",
#                     "priority_dot": "red",
#                 }
#         except Exception:
#             return {
#                 "ratio_value": 0,
#                 "ratio_label": "0%",
#                 "priority": "LOW",
#                 "priority_label": "Priorité faible",
#                 "priority_color": "#22c55e",
#                 "priority_badge": "bg-emerald-100 text-emerald-700",
#                 "priority_dot": "green",
#             }
#
#     # =========================================================
#     # GEOMETRY / CENTER / MEDIA
#     # =========================================================
#
#     def get_geometry_obj(self, parcel, zoom=17):
#         if not parcel or not parcel.geometry:
#             return None
#
#         if not self.should_include_geometry(zoom):
#             return None
#
#         try:
#             geometry = parcel.geometry
#             precision = self.get_geometry_precision_from_zoom(zoom)
#
#             if precision is not None:
#                 geojson = geometry.geojson
#                 data = json.loads(geojson)
#                 return self.round_geojson_coordinates(data, precision)
#
#             return json.loads(geometry.geojson)
#         except Exception:
#             return None
#
#     def round_geojson_coordinates(self, geojson_obj, precision=5):
#         def round_coords(coords):
#             if isinstance(coords, (list, tuple)):
#                 if len(coords) == 2 and all(isinstance(x, (int, float)) for x in coords):
#                     return [round(coords[0], precision), round(coords[1], precision)]
#                 return [round_coords(c) for c in coords]
#             return coords
#
#         data = dict(geojson_obj)
#         if "coordinates" in data:
#             data["coordinates"] = round_coords(data["coordinates"])
#         return data
#
#     def get_center(self, parcel):
#         if not parcel or not parcel.centroid:
#             return None
#         try:
#             return [parcel.centroid.y, parcel.centroid.x]
#         except Exception:
#             return None
#
#     def get_asset_images(self, asset, zoom=17):
#         if not self.should_include_images(zoom):
#             return []
#
#         photos = []
#         try:
#             for photo in asset.photos.all()[:10]:
#                 image = getattr(photo, "image", None)
#                 if image:
#                     try:
#                         photos.append(image.url)
#                     except Exception:
#                         pass
#         except Exception:
#             pass
#
#         if not photos and asset.parcel:
#             try:
#                 for doc in asset.parcel.documents.filter(document_type="PHOTO")[:10]:
#                     file_obj = getattr(doc, "file", None)
#                     if file_obj:
#                         try:
#                             photos.append(file_obj.url)
#                         except Exception:
#                             pass
#             except Exception:
#                 pass
#
#         return photos[:10]
#
#     def get_parcel_images(self, parcel, zoom=17):
#         if not self.should_include_images(zoom):
#             return []
#
#         photos = []
#
#         try:
#             for doc in parcel.documents.filter(document_type="PHOTO")[:10]:
#                 file_obj = getattr(doc, "file", None)
#                 if file_obj:
#                     try:
#                         url = file_obj.url
#                         if url not in photos:
#                             photos.append(url)
#                     except Exception:
#                         pass
#         except Exception:
#             pass
#
#         try:
#             for cp in parcel.construction_projects.all():
#                 for photo in cp.photos.all()[:10]:
#                     image_obj = getattr(photo, "image", None)
#                     if image_obj:
#                         try:
#                             url = image_obj.url
#                             if url not in photos:
#                                 photos.append(url)
#                         except Exception:
#                             pass
#         except Exception:
#             pass
#
#         return photos[:10]
#
#     # =========================================================
#     # CUSTOMER HELPERS
#     # =========================================================
#
#     def get_customer_name(self, customer):
#         if not customer:
#             return "—"
#         if getattr(customer, "customer_type", None) == "COMPANY":
#             return customer.company_name or "Entreprise"
#         full_name = f"{customer.first_name or ''} {customer.last_name or ''}".strip()
#         return full_name or "Client"
#
#     def serialize_customer(self, customer):
#         if not customer:
#             return None
#         return {
#             "id": customer.id,
#             "name": self.get_customer_name(customer),
#             "type": getattr(customer, "customer_type", None),
#             "phone": getattr(customer, "phone", None) or "—",
#             "email": getattr(customer, "email", None) or "—",
#         }
#
#     # =========================================================
#     # 3D / TYPE HELPERS
#     # =========================================================
#
#     def is_building_asset(self, asset):
#         label = ""
#         if asset.asset_category and asset.asset_category.label:
#             label += f" {asset.asset_category.label.lower()}"
#         if asset.property_type and asset.property_type.label:
#             label += f" {asset.property_type.label.lower()}"
#         label = label.strip()
#
#         keywords = ["immeuble", "résidence", "residence", "appartement", "commerce", "commercial", "mixte", "r+"]
#         return any(k in label for k in keywords) or bool(asset.is_multi_unit)
#
#     def is_villa_asset(self, asset):
#         label = ""
#         if asset.asset_category and asset.asset_category.label:
#             label += f" {asset.asset_category.label.lower()}"
#         if asset.property_type and asset.property_type.label:
#             label += f" {asset.property_type.label.lower()}"
#         label = label.strip()
#
#         keywords = ["villa", "duplex", "triplex", "maison"]
#         return any(k in label for k in keywords) and not asset.is_multi_unit
#
#     def get_asset_nature_label(self, asset):
#         if self.is_building_asset(asset):
#             return "Immeuble / actif multi-unités"
#         if self.is_villa_asset(asset):
#             return "Villa / actif mono-unité"
#         return "Actif immobilier"
#
#     def compute_asset_height(self, asset=None, parcel=None):
#         if asset:
#             floors = asset.floors or 0
#
#             if floors > 0:
#                 return round(floors * 3.2, 2)
#
#             asset_label = ""
#             if asset.asset_category and asset.asset_category.label:
#                 asset_label += f" {asset.asset_category.label.lower()}"
#             if asset.property_type and asset.property_type.label:
#                 asset_label += f" {asset.property_type.label.lower()}"
#
#             if asset.status == "UNDER_CONSTRUCTION":
#                 progress = getattr(asset, "construction_progress", 40) or 40
#                 final_height = 10
#                 return round(final_height * (progress / 100), 2)
#
#             if "immeuble" in asset_label or "r+" in asset_label:
#                 return 18
#             if "appartement" in asset_label:
#                 return 12
#             if "duplex" in asset_label:
#                 return 8
#             if "triplex" in asset_label:
#                 return 10
#             if "villa" in asset_label:
#                 return 5
#             if "maison" in asset_label:
#                 return 4
#
#             return 2.5
#
#         if parcel:
#             area = parcel.official_area_m2 or 0
#             if area >= 800:
#                 return 2.2
#             if area >= 400:
#                 return 1.6
#             if area >= 200:
#                 return 1.2
#             return 0.8
#
#         return 1.0
#
#     def compute_base_height(self, asset=None, parcel=None):
#         return 0
#
#     def get_3d_type(self, asset=None, parcel=None):
#         if asset:
#             if asset.asset_category and asset.asset_category.label:
#                 return asset.asset_category.label
#             if asset.property_type and asset.property_type.label:
#                 return asset.property_type.label
#         return "Parcelle"
#
#     # =========================================================
#     # CONSTRUCTION HELPERS
#     # =========================================================
#
#     def month_range(self, year, month):
#         first_day = date(year, month, 1)
#         last_day = date(year, month, calendar.monthrange(year, month)[1])
#         return first_day, last_day
#
#     def get_parcel_or_asset_construction_project(self, parcel=None, asset=None):
#         if asset:
#             qs = asset.construction_projects.all().order_by("-created_at")
#             project = qs.first()
#             if project:
#                 return project
#
#         if parcel:
#             qs = parcel.construction_projects.all().order_by("-created_at")
#             return qs.first()
#
#         if asset and getattr(asset, "parcel", None):
#             qs = asset.parcel.construction_projects.all().order_by("-created_at")
#             return qs.first()
#
#         return None
#
#     def get_monthly_progress_value(self, construction_project, year, month):
#         if not construction_project:
#             return 0
#
#         start_date, end_date = self.month_range(year, month)
#
#         update = (
#             construction_project.updates
#             .filter(report_date__gte=start_date, report_date__lte=end_date, is_active=True)
#             .order_by("-report_date", "-created_at")
#             .first()
#         )
#         if update and update.progress_percent is not None:
#             try:
#                 return float(update.progress_percent)
#             except Exception:
#                 return 0
#         return 0
#
#     def get_construction_stats(self, parcel=None, asset=None):
#         project = self.get_parcel_or_asset_construction_project(parcel=parcel, asset=asset)
#
#         current_progress = 0
#         estimated_budget = Decimal("0")
#         actual_cost = Decimal("0")
#
#         if project:
#             try:
#                 current_progress = float(project.progress_percent or 0)
#             except Exception:
#                 current_progress = 0
#
#             estimated_budget = self.money_raw(getattr(project, "estimated_budget", 0))
#             actual_cost = self.money_raw(getattr(project, "actual_cost", 0))
#
#         today = date.today()
#         m0_y, m0_m = today.year, today.month
#         m1_y, m1_m = (m0_y - 1, 12) if m0_m == 1 else (m0_y, m0_m - 1)
#         m2_y, m2_m = (m1_y - 1, 12) if m1_m == 1 else (m1_y, m1_m - 1)
#
#         progress_m2 = self.get_monthly_progress_value(project, m2_y, m2_m)
#         progress_m1 = self.get_monthly_progress_value(project, m1_y, m1_m)
#         progress_m0 = self.get_monthly_progress_value(project, m0_y, m0_m)
#
#         monthly_delta = round(progress_m0 - progress_m1, 2)
#
#         valeur_hypothecaire = Decimal("0")
#
#         if asset and getattr(asset, "mortgage_value", None) not in [None, ""]:
#             valeur_hypothecaire = self.money_raw(asset.mortgage_value)
#         elif parcel and getattr(parcel, "valeur_hypothecaire", None) not in [None, ""]:
#             valeur_hypothecaire = self.money_raw(parcel.valeur_hypothecaire)
#         elif estimated_budget > 0 and current_progress > 0:
#             valeur_hypothecaire = (
#                 estimated_budget * Decimal(str(current_progress / 100))
#             ).quantize(Decimal("1"))
#
#         return {
#             "taux_avancement": f"{round(current_progress)}%",
#             "taux_avancement_value": current_progress,
#             "valeur_hypothecaire": self.money_display(valeur_hypothecaire),
#             "valeur_hypothecaire_value": float(valeur_hypothecaire),
#             "budget_previsionnel": self.money_display(estimated_budget),
#             "budget_previsionnel_value": float(estimated_budget),
#             "cout_reel": self.money_display(actual_cost),
#             "cout_reel_value": float(actual_cost),
#             "comparatif_progression": {
#                 "il_y_a_2_mois": progress_m2,
#                 "mois_dernier": progress_m1,
#                 "mois_en_cours": progress_m0,
#             },
#             "evolution_mensuelle": monthly_delta,
#             "evolution_mensuelle_label": (
#                 f"+{round(monthly_delta)}% ce mois" if monthly_delta > 0
#                 else f"{round(monthly_delta)}% ce mois"
#             ),
#         }
#
#     # =========================================================
#     # SALES / RESERVATIONS HELPERS
#     # =========================================================
#
#     def get_sales_by_parcel(self, parcel_ids):
#         if not parcel_ids:
#             return {}
#
#         sales = (
#             SaleFile.objects.select_related("customer", "parcel", "program", "unit")
#             .prefetch_related("payments", "buyers")
#             .filter(parcel_id__in=parcel_ids, is_active=True)
#             .annotate(total_paid=Coalesce(Sum("payments__amount"), Decimal("0")))
#             .order_by("-sale_date", "-created_at")
#         )
#
#         sales_by_parcel = {}
#         for sale in sales:
#             sales_by_parcel.setdefault(sale.parcel_id, sale)
#         return sales_by_parcel
#
#     def get_reservations_by_parcel(self, parcel_ids):
#         if not parcel_ids:
#             return {}
#
#         reservations = (
#             Reservation.objects.select_related("customer", "parcel", "program", "unit")
#             .filter(parcel_id__in=parcel_ids, is_active=True)
#             .order_by("-reservation_date", "-created_at")
#         )
#
#         reservations_by_parcel = {}
#         for reservation in reservations:
#             reservations_by_parcel.setdefault(reservation.parcel_id, reservation)
#         return reservations_by_parcel
#
#     def get_asset_sales_map(self, asset_ids):
#         if not asset_ids:
#             return {}
#
#         sales = (
#             SaleFile.objects.select_related("customer", "unit", "parcel", "program")
#             .prefetch_related("payments", "buyers")
#             .filter(unit__asset_id__in=asset_ids, is_active=True)
#             .annotate(total_paid=Coalesce(Sum("payments__amount"), Decimal("0")))
#             .order_by("-sale_date", "-created_at")
#         )
#
#         asset_sales = {}
#         for sale in sales:
#             asset_id = sale.unit.asset_id if sale.unit_id else None
#             if asset_id:
#                 asset_sales.setdefault(asset_id, []).append(sale)
#         return asset_sales
#
#     def get_asset_reservations_map(self, asset_ids):
#         if not asset_ids:
#             return {}
#
#         reservations = (
#             Reservation.objects.select_related("customer", "unit", "parcel", "program")
#             .filter(unit__asset_id__in=asset_ids, is_active=True)
#             .order_by("-reservation_date", "-created_at")
#         )
#
#         asset_reservations = {}
#         for reservation in reservations:
#             asset_id = reservation.unit.asset_id if reservation.unit_id else None
#             if asset_id:
#                 asset_reservations.setdefault(asset_id, []).append(reservation)
#         return asset_reservations
#
#     def get_asset_units_map(self, asset_ids):
#         if not asset_ids:
#             return {}
#
#         units = (
#             PropertyUnit.objects.select_related("unit_type", "asset", "program", "parcel")
#             .filter(asset_id__in=asset_ids, is_active=True)
#             .order_by("floor_number", "code")
#         )
#
#         asset_units = {}
#         for unit in units:
#             asset_units.setdefault(unit.asset_id, []).append(unit)
#         return asset_units
#
#     # =========================================================
#     # FINANCIAL HELPERS
#     # =========================================================
#
#     def get_sale_financial_stats(self, sale=None, asset=None):
#         base_amount = Decimal("0")
#         sold_amount = Decimal("0")
#         amount_paid = Decimal("0")
#         payments_count = 0
#
#         if asset and getattr(asset, "sale_price", None):
#             base_amount = self.money_raw(asset.sale_price)
#         elif asset and getattr(asset, "estimated_cost", None):
#             base_amount = self.money_raw(asset.estimated_cost)
#
#         if sale:
#             sold_amount = self.money_raw(sale.net_price or sale.agreed_price)
#             amount_paid = self.money_raw(getattr(sale, "total_paid", 0))
#             try:
#                 payments_count = sale.payments.count()
#             except Exception:
#                 payments_count = 0
#
#             if not base_amount:
#                 base_amount = sold_amount
#
#         taux_paiement = self.safe_percent_value(amount_paid, sold_amount or base_amount)
#
#         return {
#             "montant_base": self.money_display(base_amount),
#             "montant_base_value": float(base_amount),
#             "montant_vendu": self.money_display(sold_amount),
#             "montant_vendu_value": float(sold_amount),
#             "montant_paye": self.money_display(amount_paid),
#             "montant_paye_value": float(amount_paid),
#             "nombre_paiements": payments_count,
#             "taux_paiement": f"{round(taux_paiement)}%",
#             "taux_paiement_value": taux_paiement,
#         }
#
#     def get_asset_aggregated_financial_stats(self, asset, sales=None, units=None):
#         sales = sales or []
#         units = units or []
#
#         base_amount = Decimal("0")
#         sold_amount = Decimal("0")
#         amount_paid = Decimal("0")
#         payments_count = 0
#
#         if asset.is_multi_unit or units:
#             for unit in units:
#                 if getattr(unit, "sale_price", None):
#                     base_amount += self.money_raw(unit.sale_price)
#                 elif getattr(unit, "estimated_cost", None):
#                     base_amount += self.money_raw(unit.estimated_cost)
#
#             for sale in sales:
#                 sold_amount += self.money_raw(sale.net_price or sale.agreed_price)
#                 amount_paid += self.money_raw(getattr(sale, "total_paid", 0))
#                 try:
#                     payments_count += sale.payments.count()
#                 except Exception:
#                     pass
#
#             if base_amount <= 0 and asset.sale_price:
#                 base_amount = self.money_raw(asset.sale_price)
#         else:
#             primary_sale = sales[0] if sales else None
#             return self.get_sale_financial_stats(sale=primary_sale, asset=asset)
#
#         taux_paiement = self.safe_percent_value(amount_paid, sold_amount or base_amount)
#
#         return {
#             "montant_base": self.money_display(base_amount),
#             "montant_base_value": float(base_amount),
#             "montant_vendu": self.money_display(sold_amount),
#             "montant_vendu_value": float(sold_amount),
#             "montant_paye": self.money_display(amount_paid),
#             "montant_paye_value": float(amount_paid),
#             "nombre_paiements": payments_count,
#             "taux_paiement": f"{round(taux_paiement)}%",
#             "taux_paiement_value": taux_paiement,
#         }
#
#     def get_asset_unit_summary(self, asset, units, sales, reservations):
#         total_units = len(units)
#         available_units = 0
#         reserved_units = 0
#         sold_units = 0
#         blocked_units = 0
#
#         for unit in units:
#             status = unit.commercial_status
#             if status == "AVAILABLE":
#                 available_units += 1
#             elif status in ["OPTIONED", "RESERVED"]:
#                 reserved_units += 1
#             elif status in ["SOLD", "DELIVERED"]:
#                 sold_units += 1
#             elif status == "BLOCKED":
#                 blocked_units += 1
#
#         return {
#             "total_units": total_units,
#             "available_units": available_units,
#             "reserved_units": reserved_units,
#             "sold_units": sold_units,
#             "blocked_units": blocked_units,
#             "sales_count": len(sales),
#             "reservations_count": len(reservations),
#         }
#
#     def get_asset_customer_summary(self, sales, reservations):
#         customer_map = {}
#
#         for sale in sales:
#             if sale.customer_id:
#                 customer_map[sale.customer_id] = self.serialize_customer(sale.customer)
#
#             try:
#                 for buyer in sale.buyers.select_related("customer").all():
#                     if buyer.customer_id:
#                         customer_map[buyer.customer_id] = self.serialize_customer(buyer.customer)
#             except Exception:
#                 pass
#
#         for reservation in reservations:
#             if reservation.customer_id:
#                 customer_map[reservation.customer_id] = self.serialize_customer(reservation.customer)
#
#         customers = [c for c in customer_map.values() if c]
#         return {
#             "count": len(customers),
#             "items": customers[:20],
#         }
#
#     def get_asset_sales_summary(self, sales):
#         items = []
#         for sale in sales[:20]:
#             items.append({
#                 "sale_number": sale.sale_number,
#                 "sale_date": sale.sale_date.strftime("%d/%m/%Y") if sale.sale_date else "—",
#                 "customer": self.get_customer_name(sale.customer),
#                 "unit": sale.unit.label if sale.unit_id else "Actif global",
#                 "net_price": self.money_display(sale.net_price or sale.agreed_price),
#                 "total_paid": self.money_display(getattr(sale, "total_paid", 0)),
#                 "payment_progress": self.percent_display(
#                     getattr(sale, "total_paid", 0),
#                     sale.net_price or sale.agreed_price or 0
#                 ),
#                 "status": sale.get_status_display() if hasattr(sale, "get_status_display") else sale.status,
#             })
#         return items
#
#     def get_asset_main_client_label(self, asset, sales, reservations):
#         if asset.is_multi_unit or len(sales) > 1:
#             customer_names = []
#             seen = set()
#
#             for sale in sales:
#                 name = self.get_customer_name(sale.customer)
#                 if name not in seen and name != "—":
#                     seen.add(name)
#                     customer_names.append(name)
#
#             for reservation in reservations:
#                 name = self.get_customer_name(reservation.customer)
#                 if name not in seen and name != "—":
#                     seen.add(name)
#                     customer_names.append(name)
#
#             if not customer_names:
#                 return "—"
#             if len(customer_names) == 1:
#                 return customer_names[0]
#             return f"{len(customer_names)} clients"
#
#         if sales:
#             return self.get_customer_name(sales[0].customer)
#         if reservations:
#             return self.get_customer_name(reservations[0].customer)
#         return "—"
#
#     # =========================================================
#     # FILTERS
#     # =========================================================
#
#     def apply_common_filters_assets(self, queryset, params):
#         if params["program_id"]:
#             queryset = queryset.filter(program_id=params["program_id"])
#
#         if params["project_id"]:
#             queryset = queryset.filter(program__project_id=params["project_id"])
#
#         if params["status"]:
#             queryset = queryset.filter(status=params["status"])
#
#         if params["bbox"]:
#             queryset = queryset.filter(
#                 Q(parcel__geometry__intersects=params["bbox"]) |
#                 Q(parcel__centroid__within=params["bbox"])
#             )
#
#         if params["search"]:
#             q = params["search"]
#             queryset = queryset.filter(
#                 Q(label__icontains=q)
#                 | Q(code__icontains=q)
#                 | Q(program__name__icontains=q)
#                 | Q(program__project__nom__icontains=q)
#                 | Q(parcel__lot_number__icontains=q)
#                 | Q(parcel__parcel_code__icontains=q)
#                 | Q(property_type__label__icontains=q)
#                 | Q(asset_category__label__icontains=q)
#                 | Q(units__label__icontains=q)
#                 | Q(units__code__icontains=q)
#             ).distinct()
#
#         return queryset
#
#     def apply_common_filters_parcels(self, queryset, params):
#         if params["program_id"]:
#             queryset = queryset.filter(program_id=params["program_id"])
#
#         if params["project_id"]:
#             queryset = queryset.filter(program__project_id=params["project_id"])
#
#         if params["status"]:
#             queryset = queryset.filter(commercial_status=params["status"])
#
#         if params["bbox"]:
#             queryset = queryset.filter(
#                 Q(geometry__intersects=params["bbox"]) |
#                 Q(centroid__within=params["bbox"])
#             )
#
#         if params["search"]:
#             q = params["search"]
#             queryset = queryset.filter(
#                 Q(lot_number__icontains=q)
#                 | Q(parcel_code__icontains=q)
#                 | Q(external_reference__icontains=q)
#                 | Q(program__name__icontains=q)
#                 | Q(program__project__nom__icontains=q)
#                 | Q(block__code__icontains=q)
#             )
#
#         return queryset
#
#     # =========================================================
#     # TIMELINES
#     # =========================================================
#
#     def get_asset_timeline(self, asset, sales=None, reservations=None, zoom=17):
#         if not self.should_include_timeline(zoom):
#             return []
#
#         sales = sales or []
#         reservations = reservations or []
#         items = []
#
#         for reservation in reservations[:3]:
#             if reservation.reservation_date:
#                 items.append({
#                     "label": "Réservation",
#                     "date": reservation.reservation_date.strftime("%d %b"),
#                     "text": f"Réservation enregistrée ({reservation.unit.label if reservation.unit_id else 'actif'}).",
#                     "iconBg": "bg-amber-100",
#                 })
#
#         for sale in sales[:3]:
#             if sale.sale_date:
#                 items.append({
#                     "label": "Vente actée",
#                     "date": sale.sale_date.strftime("%d %b"),
#                     "text": f"Vente enregistrée ({sale.unit.label if sale.unit_id else 'actif'}).",
#                     "iconBg": "bg-emerald-100",
#                 })
#
#         try:
#             for update in asset.updates.all()[:5]:
#                 items.append({
#                     "label": update.get_stage_display() if hasattr(update, "get_stage_display") else getattr(update, "stage", "Mise à jour"),
#                     "date": update.report_date.strftime("%d %b") if getattr(update, "report_date", None) else "—",
#                     "text": getattr(update, "summary", None) or getattr(update, "details", None) or "Mise à jour chantier",
#                     "iconBg": "bg-violet-100",
#                 })
#         except Exception:
#             pass
#
#         return items[:8]
#
#     def get_parcel_timeline(self, parcel, sale=None, reservation=None, zoom=17):
#         if not self.should_include_timeline(zoom):
#             return []
#
#         items = [{
#             "label": "Import parcellaire",
#             "date": parcel.created_at.strftime("%d %b") if getattr(parcel, "created_at", None) else "—",
#             "text": "Parcelle importée dans le système.",
#             "iconBg": "bg-sky-100",
#         }]
#
#         if reservation and reservation.reservation_date:
#             items.insert(0, {
#                 "label": "Réservation",
#                 "date": reservation.reservation_date.strftime("%d %b"),
#                 "text": "Réservation enregistrée sur la parcelle.",
#                 "iconBg": "bg-amber-100",
#             })
#
#         if sale and sale.sale_date:
#             items.insert(0, {
#                 "label": "Vente actée",
#                 "date": sale.sale_date.strftime("%d %b"),
#                 "text": "Vente enregistrée dans le système.",
#                 "iconBg": "bg-emerald-100",
#             })
#
#         return items[:6]
#
#     # =========================================================
#     # BUILDERS
#     # =========================================================
#
#     def _build_from_assets(self, queryset, params):
#         rights = getattr(self, "user_rights", {})
#         can_view_financial = rights.get("can_view_financial_data", False)
#         can_view_patient = rights.get("can_view_patient_data", False)
#         can_view_construction = rights.get("can_view_construction_data", False)
#         zoom = params["zoom"]
#
#         queryset = queryset[:params["limit"]]
#
#         asset_ids = list(queryset.values_list("id", flat=True))
#         asset_units_map = self.get_asset_units_map(asset_ids)
#         asset_sales_map = self.get_asset_sales_map(asset_ids)
#         asset_reservations_map = self.get_asset_reservations_map(asset_ids)
#
#         parcel_ids = [obj.parcel_id for obj in queryset if obj.parcel_id]
#         sales_by_parcel = self.get_sales_by_parcel(parcel_ids)
#         reservations_by_parcel = self.get_reservations_by_parcel(parcel_ids)
#
#         assets_payload = []
#         total_ca = Decimal("0")
#         reserved_or_sold = 0
#
#         for asset in queryset:
#             parcel = asset.parcel
#             units = asset_units_map.get(asset.id, [])
#             unit_sales = asset_sales_map.get(asset.id, [])
#             unit_reservations = asset_reservations_map.get(asset.id, [])
#
#             direct_sale = sales_by_parcel.get(parcel.id) if parcel else None
#             direct_reservation = reservations_by_parcel.get(parcel.id) if parcel else None
#
#             is_multi = bool(asset.is_multi_unit or units)
#             effective_sales = unit_sales if is_multi else ([direct_sale] if direct_sale else [])
#             effective_reservations = unit_reservations if is_multi else ([direct_reservation] if direct_reservation else [])
#
#             ui = self.get_status_ui_from_asset_status(asset.status)
#
#             construction_stats = (
#                 self.get_construction_stats(parcel=parcel, asset=asset)
#                 if can_view_construction
#                 else self.get_masked_construction_stats()
#             )
#
#             financial_stats = (
#                 self.get_asset_aggregated_financial_stats(asset=asset, sales=effective_sales, units=units)
#                 if can_view_financial
#                 else self.get_masked_financial_stats()
#             )
#
#             if can_view_financial and can_view_construction:
#                 priority_stats = self.get_hypotheque_payment_ratio(
#                     construction_stats.get("valeur_hypothecaire_value", 0),
#                     financial_stats.get("montant_paye_value", 0),
#                 )
#                 ui["color"] = priority_stats["priority_color"]
#             else:
#                 priority_stats = {
#                     "ratio_value": 0,
#                     "ratio_label": "Masqué",
#                     "priority": "UNKNOWN",
#                     "priority_label": "Masqué",
#                     "priority_color": "#94a3b8",
#                     "priority_badge": "bg-slate-100 text-slate-700",
#                     "priority_dot": "gray",
#                 }
#
#             if can_view_patient:
#                 client_name = self.get_asset_main_client_label(asset, effective_sales, effective_reservations)
#                 customers_summary = self.get_asset_customer_summary(effective_sales, effective_reservations)
#             else:
#                 client_name = self.get_masked_client_name()
#                 customers_summary = {"count": 0, "items": []}
#
#             unit_summary = self.get_asset_unit_summary(asset, units, effective_sales, effective_reservations)
#
#             if asset.status in ["RESERVED", "SOLD", "UNDER_CONSTRUCTION", "COMPLETED"]:
#                 reserved_or_sold += 1
#
#             if can_view_financial:
#                 total_ca += self.money_raw(financial_stats.get("montant_vendu_value", 0))
#
#             details = [
#                 {
#                     "label": "Projet",
#                     "value": asset.program.project.nom if asset.program and getattr(asset.program, "project", None) else "—",
#                 },
#                 {"label": "Programme", "value": asset.program.name if asset.program else "—"},
#                 {"label": "Référence", "value": asset.code or "—"},
#                 {"label": "Nature", "value": self.get_asset_nature_label(asset)},
#                 {"label": "Type", "value": asset.property_type.label if asset.property_type else "—"},
#                 {"label": "Catégorie", "value": asset.asset_category.label if asset.asset_category else "—"},
#                 {"label": "Phase", "value": asset.phase.name if asset.phase else "—"},
#                 {
#                     "label": "Parcelle",
#                     "value": parcel.lot_number if parcel and parcel.lot_number else (parcel.parcel_code if parcel else "—"),
#                 },
#             ]
#
#             if is_multi:
#                 details.extend([
#                     {"label": "Mode commercial", "value": "Vente par unités"},
#                     {"label": "Unités totales", "value": str(unit_summary["total_units"])},
#                     {"label": "Unités disponibles", "value": str(unit_summary["available_units"])},
#                     {"label": "Unités réservées", "value": str(unit_summary["reserved_units"])},
#                     {"label": "Unités vendues", "value": str(unit_summary["sold_units"])},
#                 ])
#             else:
#                 details.append({"label": "Mode commercial", "value": "Vente globale de l'actif"})
#
#             if can_view_patient:
#                 details.append({"label": "Client(s)", "value": client_name})
#
#             if can_view_financial:
#                 details.append({"label": "Valeur hypothécaire", "value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué"})
#
#             if can_view_financial and can_view_construction:
#                 details.append({"label": "Ratio hypo / paiements", "value": priority_stats["ratio_label"]})
#                 details.append({"label": "Niveau priorité", "value": priority_stats["priority_label"]})
#
#             metrics = [
#                 {"label": "Étages", "value": str(asset.floors or 0)},
#                 {"label": "Chambres", "value": str(asset.bedrooms or 0)},
#                 {"label": "Unités", "value": str(unit_summary["total_units"]) if is_multi else "1"},
#                 {
#                     "label": "Avancement",
#                     "value": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
#                 },
#             ]
#
#             assets_payload.append({
#                 "id": asset.id,
#                 "project": asset.program.project.nom if asset.program and getattr(asset.program, "project", None) else "—",
#                 "name": asset.label,
#                 "program": asset.program.name if asset.program else "—",
#                 "type": asset.property_type.label if asset.property_type else "Actif immobilier",
#                 "asset_category": asset.asset_category.label if asset.asset_category else "—",
#                 "asset_nature": self.get_asset_nature_label(asset),
#                 "is_multi_unit": is_multi,
#                 "status": ui["status"],
#                 "statusKey": ui["statusKey"],
#                 "statusBadge": ui["statusBadge"],
#                 "color": ui["color"],
#                 "fillOpacity": ui["fillOpacity"],
#                 "price": (
#                     financial_stats["montant_base"] if is_multi
#                     else (self.money_display(asset.sale_price) if can_view_financial else "Masqué")
#                 ),
#                 "surface": (
#                     f"{asset.built_area_m2} m²"
#                     if asset.built_area_m2
#                     else (f"{parcel.official_area_m2} m²" if parcel and parcel.official_area_m2 else "—")
#                 ),
#                 "payment": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
#                 "client": client_name,
#                 "phase": asset.phase.name if asset.phase else "—",
#                 "center": self.get_center(parcel),
#                 "images": self.get_asset_images(asset, zoom=zoom),
#                 "details": details,
#                 "metrics": metrics,
#                 "timeline": self.get_asset_timeline(asset, sales=effective_sales, reservations=effective_reservations, zoom=zoom),
#                 "geometry": self.get_geometry_obj(parcel, zoom=zoom),
#                 "height": self.compute_asset_height(asset=asset, parcel=parcel),
#                 "base_height": self.compute_base_height(asset=asset, parcel=parcel),
#                 "building_type": self.get_3d_type(asset=asset, parcel=parcel),
#                 "financial_stats": financial_stats,
#                 "construction_stats": construction_stats,
#                 "priority_stats": priority_stats,
#                 "unit_summary": unit_summary,
#                 "customers": customers_summary if can_view_patient else {"count": 0, "items": []},
#                 "sales_summary": self.get_asset_sales_summary(effective_sales) if (can_view_financial and self.should_include_sales_summary(zoom)) else [],
#                 "units_preview": [
#                     {
#                         "id": unit.id,
#                         "code": unit.code,
#                         "label": unit.label,
#                         "type": unit.unit_type.label if unit.unit_type else "—",
#                         "floor": unit.floor_number,
#                         "status": unit.get_commercial_status_display() if hasattr(unit, "get_commercial_status_display") else unit.commercial_status,
#                         "price": self.money_display(unit.sale_price) if can_view_financial else "Masqué",
#                         "surface": f"{unit.saleable_area_m2} m²" if unit.saleable_area_m2 else "—",
#                     }
#                     for unit in (units[:20] if self.should_include_units_preview(zoom) else [])
#                 ],
#             })
#
#         summaries = [
#             {"label": "Actifs", "value": str(len(assets_payload))},
#             {"label": "Réservés/Vendus", "value": str(reserved_or_sold)},
#             {"label": "CA potentiel", "value": self.money_display(total_ca or 0) if can_view_financial else "Masqué"},
#         ]
#
#         return {
#             "source": "property_assets",
#             "assets": assets_payload,
#             "summaries": summaries,
#         }
#
#     def _build_from_parcels(self, queryset, params):
#         rights = getattr(self, "user_rights", {})
#         can_view_financial = rights.get("can_view_financial_data", False)
#         can_view_patient = rights.get("can_view_patient_data", False)
#         can_view_construction = rights.get("can_view_construction_data", False)
#         zoom = params["zoom"]
#
#         queryset = queryset[:params["limit"]]
#
#         parcel_ids = list(queryset.values_list("id", flat=True))
#         sales_by_parcel = self.get_sales_by_parcel(parcel_ids)
#         reservations_by_parcel = self.get_reservations_by_parcel(parcel_ids)
#
#         assets_payload = []
#         reserved_or_sold = 0
#         total_ca = Decimal("0")
#
#         for parcel in queryset:
#             sale = sales_by_parcel.get(parcel.id)
#             reservation = reservations_by_parcel.get(parcel.id)
#
#             ui = self.get_status_ui_from_parcel_status(parcel.commercial_status)
#
#             if can_view_patient:
#                 client_name = (
#                     self.get_customer_name(sale.customer)
#                     if sale and sale.customer
#                     else (
#                         self.get_customer_name(reservation.customer)
#                         if reservation and reservation.customer
#                         else "—"
#                     )
#                 )
#             else:
#                 client_name = self.get_masked_client_name()
#
#             if ui["statusKey"] in ["Réservés", "Vendus"]:
#                 reserved_or_sold += 1
#
#             if can_view_financial and sale and (sale.net_price or sale.agreed_price):
#                 total_ca += self.money_raw(sale.net_price or sale.agreed_price)
#
#             financial_stats = (
#                 self.get_sale_financial_stats(sale=sale, asset=None)
#                 if can_view_financial
#                 else self.get_masked_financial_stats()
#             )
#
#             construction_stats = (
#                 self.get_construction_stats(parcel=parcel, asset=None)
#                 if can_view_construction
#                 else self.get_masked_construction_stats()
#             )
#
#             if can_view_financial and can_view_construction:
#                 priority_stats = self.get_hypotheque_payment_ratio(
#                     construction_stats.get("valeur_hypothecaire_value", 0),
#                     financial_stats.get("montant_paye_value", 0),
#                 )
#                 ui["color"] = priority_stats["priority_color"]
#             else:
#                 priority_stats = {
#                     "ratio_value": 0,
#                     "ratio_label": "Masqué",
#                     "priority": "UNKNOWN",
#                     "priority_label": "Masqué",
#                     "priority_color": "#94a3b8",
#                     "priority_badge": "bg-slate-100 text-slate-700",
#                     "priority_dot": "gray",
#                 }
#
#             details = [
#                 {
#                     "label": "Projet",
#                     "value": parcel.program.project.nom if parcel.program and getattr(parcel.program, "project", None) else "—",
#                 },
#                 {"label": "Programme", "value": parcel.program.name if parcel.program else "—"},
#                 {"label": "Îlot", "value": parcel.block.code if parcel.block else "—"},
#                 {"label": "Lot", "value": parcel.lot_number or "—"},
#                 {"label": "Référence", "value": parcel.parcel_code or "—"},
#                 {"label": "Surface", "value": f"{parcel.official_area_m2} m²" if parcel.official_area_m2 else "—"},
#             ]
#
#             if can_view_patient:
#                 details.append({"label": "Client", "value": client_name})
#
#             if can_view_financial:
#                 details.append({
#                     "label": "Valeur hypothécaire",
#                     "value": construction_stats["valeur_hypothecaire"] if can_view_construction else "Masqué",
#                 })
#
#             if can_view_financial and can_view_construction:
#                 details.append({"label": "Ratio hypo / paiements", "value": priority_stats["ratio_label"]})
#                 details.append({"label": "Niveau priorité", "value": priority_stats["priority_label"]})
#
#             metrics = [
#                 {"label": "Accès route", "value": "Oui" if parcel.has_road_access else "Non"},
#                 {"label": "Angle", "value": "Oui" if parcel.is_corner else "Non"},
#                 {
#                     "label": "Avancement",
#                     "value": construction_stats["taux_avancement"] if can_view_construction else "Masqué",
#                 },
#             ]
#
#             assets_payload.append({
#                 "id": parcel.id,
#                 "project": parcel.program.project.nom if parcel.program and getattr(parcel.program, "project", None) else "—",
#                 "name": f"Lot {parcel.lot_number or parcel.parcel_code or parcel.id}",
#                 "program": parcel.program.name if parcel.program else "—",
#                 "type": "Parcelle",
#                 "status": ui["status"],
#                 "statusKey": ui["statusKey"],
#                 "statusBadge": ui["statusBadge"],
#                 "color": ui["color"],
#                 "fillOpacity": ui["fillOpacity"],
#                 "price": self.money_display(sale.net_price or sale.agreed_price) if (sale and can_view_financial) else ("Masqué" if not can_view_financial else "—"),
#                 "surface": f"{parcel.official_area_m2} m²" if parcel.official_area_m2 else "—",
#                 "payment": financial_stats["taux_paiement"] if can_view_financial else "Masqué",
#                 "client": client_name,
#                 "phase": parcel.phase.name if parcel.phase else "—",
#                 "center": self.get_center(parcel),
#                 "images": self.get_parcel_images(parcel, zoom=zoom),
#                 "details": details,
#                 "metrics": metrics,
#                 "timeline": self.get_parcel_timeline(parcel, sale=sale, reservation=reservation, zoom=zoom),
#                 "geometry": self.get_geometry_obj(parcel, zoom=zoom),
#                 "height": self.compute_asset_height(parcel=parcel),
#                 "base_height": self.compute_base_height(parcel=parcel),
#                 "building_type": self.get_3d_type(parcel=parcel),
#                 "financial_stats": financial_stats,
#                 "construction_stats": construction_stats,
#                 "priority_stats": priority_stats,
#             })
#
#         summaries = [
#             {"label": "Actifs", "value": str(len(assets_payload))},
#             {"label": "Réservés/Vendus", "value": str(reserved_or_sold)},
#             {"label": "CA potentiel", "value": self.money_display(total_ca) if can_view_financial else "Masqué"},
#         ]
#
#         return {
#             "source": "parcels",
#             "assets": assets_payload,
#             "summaries": summaries,
#         }
#
#     # =========================================================
#     # GET
#     # =========================================================
#
#     def get(self, request, *args, **kwargs):
#         self.user_rights = self.get_user_rights(request)
#         params = self.normalize_query(request)
#
#         asset_queryset = (
#             PropertyAsset.objects.select_related(
#                 "program",
#                 "program__project",
#                 "phase",
#                 "parcel",
#                 "property_type",
#                 "asset_category",
#             )
#             .prefetch_related(
#                 "photos",
#                 "updates",
#                 "parcel__documents",
#                 "units",
#                 "units__unit_type",
#                 "construction_projects",
#             )
#             .filter(is_active=True)
#             .order_by("code")
#         )
#         asset_queryset = self.apply_common_filters_assets(asset_queryset, params)
#
#         parcel_queryset = (
#             Parcel.objects.select_related(
#                 "program",
#                 "program__project",
#                 "phase",
#                 "block",
#             )
#             .prefetch_related(
#                 "documents",
#                 "construction_projects__photos",
#                 "construction_projects__updates",
#             )
#             .filter(is_active=True)
#             .exclude(geometry__isnull=True)
#             .order_by("lot_number", "id")
#         )
#         parcel_queryset = self.apply_common_filters_parcels(parcel_queryset, params)
#
#         asset_parcel_ids = list(
#             asset_queryset.exclude(parcel_id__isnull=True).values_list("parcel_id", flat=True)
#         )
#         parcel_queryset = parcel_queryset.exclude(id__in=asset_parcel_ids)
#
#         asset_data = self._build_from_assets(asset_queryset, params) if asset_queryset.exists() else {
#             "source": "property_assets",
#             "assets": [],
#             "summaries": [],
#         }
#
#         parcel_data = self._build_from_parcels(parcel_queryset, params) if parcel_queryset.exists() else {
#             "source": "parcels",
#             "assets": [],
#             "summaries": [],
#         }
#
#         asset_items = asset_data.get("assets", [])
#         parcel_items = parcel_data.get("assets", [])
#
#         rights = getattr(self, "user_rights", {})
#         can_view_financial = rights.get("can_view_financial_data", False)
#
#         combined_assets = asset_items + parcel_items
#
#         reserved_or_sold = 0
#         total_ca = Decimal("0")
#
#         for item in combined_assets:
#             if item.get("statusKey") in ["Réservés", "Vendus"]:
#                 reserved_or_sold += 1
#
#             if can_view_financial:
#                 try:
#                     total_ca += Decimal(str(item.get("financial_stats", {}).get("montant_vendu_value", 0) or 0))
#                 except Exception:
#                     pass
#
#         summaries = [
#             {"label": "Actifs", "value": str(len(combined_assets))},
#             {"label": "Réservés/Vendus", "value": str(reserved_or_sold)},
#             {"label": "CA potentiel", "value": self.money_display(total_ca) if can_view_financial else "Masqué"},
#         ]
#
#         return Response({
#             "source": "mixed",
#             "assets": combined_assets,
#             "summaries": summaries,
#             "filters": self.FILTERS,
#             "user_rights": rights,
#             "counts": {
#                 "assets_count": len(asset_items),
#                 "parcels_count": len(parcel_items),
#                 "total_count": len(combined_assets),
#             },
#             "map_context": {
#                 "zoom": params["zoom"],
#                 "bbox_applied": bool(params["bbox"]),
#                 "limit": params["limit"],
#                 "geometry_included": self.should_include_geometry(params["zoom"]),
#                 "images_included": self.should_include_images(params["zoom"]),
#             }
#         })
# class SAPHealthCheckView(APIView):
#     authentication_classes = []
#     permission_classes = []
#
#     def get(self, request):
#         try:
#             service = SAPBusinessPartnerService()
#             data = service.list_partners(top=1)
#             return Response(
#                 {"ok": True, "message": "Connexion SAP OK", "sample": data},
#                 status=status.HTTP_200_OK,
#             )
#         except SAPError as exc:
#             return Response(
#                 {"ok": False, "message": str(exc)},
#                 status=status.HTTP_502_BAD_GATEWAY,
#             )
