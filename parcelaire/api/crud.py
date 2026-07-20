"""
API CRUD pour le SPA React (données maîtres + consultation transactionnelle).

- CRUD complet : ProjetImmobilier, RealEstateProgram, Customer (données
  maîtres, faible risque).
- Lecture seule (liste + détail) : Parcel, Reservation, SaleFile, Payment
  (transactionnel/financier — les écritures restent sur Django ou la carte).

Pagination, recherche, filtres et tri via DRF. Écriture protégée par les
permissions Django add/change/delete_<model> ; lecture pour tout compte
authentifié. Suppression = soft-delete (is_active=False) sur les modèles
qui héritent de SoftDeleteModel.
"""
from decimal import Decimal

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from parcelaire.api.views import (
    user_can_view_financial_data,
    user_can_view_patient_data,
)
from parcelaire.models import (
    Country,
    Customer,
    Lead,
    Parcel,
    Payment,
    Place,
    ProjetImmobilier,
    RealEstateProgram,
    Reservation,
    SaleFile,
)

MASKED = "Masqué"


def fmt_money(value):
    try:
        v = int(Decimal(value or 0))
    except Exception:
        return "—"
    return f"{v:,}".replace(",", " ") + " FCFA"


def _ctx_user(serializer):
    """Utilisateur courant depuis le contexte DRF (None hors requête)."""
    request = serializer.context.get("request")
    return getattr(request, "user", None) if request else None


def money_field(serializer, value):
    """Montant formaté si l'utilisateur a view_financial_data, sinon « Masqué ».
    Réplique le masquage centralisé (analytics/dashboard) côté CRUD."""
    user = _ctx_user(serializer)
    return fmt_money(value) if (user and user_can_view_financial_data(user)) else MASKED


# =====================================================================
# Permissions & pagination
# =====================================================================

class ModelWritePermission(BasePermission):
    """Lecture : authentifié. Écriture : permission Django correspondante
    (add/change/delete_<model>) déduite du modèle du queryset."""

    message = "Vous n'avez pas la permission d'effectuer cette action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        model = view.queryset.model
        app = model._meta.app_label
        codename = {"POST": "add", "PUT": "change", "PATCH": "change", "DELETE": "delete"}.get(request.method)
        return request.user.has_perm(f"{app}.{codename}_{model._meta.model_name}")


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class _SoftDeleteMixin:
    """DELETE = soft-delete (is_active=False) au lieu d'une suppression dure."""

    def perform_destroy(self, instance):
        if hasattr(instance, "is_active"):
            instance.is_active = False
            instance.save(update_fields=["is_active", "updated_at"])
        else:
            instance.delete()


class BaseCrudViewSet(_SoftDeleteMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, ModelWritePermission]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]


class BaseReadViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]


# =====================================================================
# Données maîtres — CRUD
# =====================================================================

class ProjectSerializer(serializers.ModelSerializer):
    country_label = serializers.CharField(source="country.nom", read_only=True, default="")
    programs_count = serializers.SerializerMethodField()

    class Meta:
        model = ProjetImmobilier
        fields = [
            "id", "code", "nom", "description", "country", "place", "address",
            "country_label", "programs_count", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_programs_count(self, obj):
        return obj.programs.filter(is_active=True).count() if hasattr(obj, "programs") else 0


class ProjectViewSet(BaseCrudViewSet):
    queryset = ProjetImmobilier.objects.filter(is_active=True).select_related("country", "place")
    serializer_class = ProjectSerializer
    search_fields = ["code", "nom", "description", "address"]
    filterset_fields = ["country"]
    ordering_fields = ["nom", "code", "created_at"]
    ordering = ["nom"]


class ProgramSerializer(serializers.ModelSerializer):
    project_label = serializers.CharField(source="project.nom", read_only=True, default="")
    country_label = serializers.CharField(source="country.nom", read_only=True, default="")
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    program_type_display = serializers.CharField(source="get_program_type_display", read_only=True)
    parcels_count = serializers.SerializerMethodField()

    class Meta:
        model = RealEstateProgram
        fields = [
            "id", "code", "name", "program_type", "status", "description",
            "marketing_title", "project", "country", "place", "address",
            "total_area_m2", "estimated_lot_count", "launch_date", "closing_date",
            "currency", "manager_name", "manager_phone", "manager_email",
            "project_label", "country_label", "status_display",
            "program_type_display", "parcels_count", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {"slug": {"required": False}}

    def get_parcels_count(self, obj):
        return obj.parcels.filter(is_active=True).count() if hasattr(obj, "parcels") else 0


class ProgramViewSet(BaseCrudViewSet):
    queryset = RealEstateProgram.objects.filter(is_active=True).select_related("project", "country", "place")
    serializer_class = ProgramSerializer
    search_fields = ["code", "name", "marketing_title", "description"]
    filterset_fields = ["project", "status", "program_type", "country"]
    ordering_fields = ["name", "code", "launch_date", "created_at"]
    ordering = ["name"]


class CustomerSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    customer_type_display = serializers.CharField(source="get_customer_type_display", read_only=True)

    # PII de contact / pièce d'identité — masquée en LECTURE sans view_patient_data.
    PII_FIELDS = ("phone", "email", "id_type", "id_number", "address", "notes")

    class Meta:
        model = Customer
        fields = [
            "id", "customer_type", "first_name", "last_name", "company_name",
            "phone", "email", "country", "place", "address", "id_type",
            "id_number", "notes", "display_name", "customer_type_display",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_display_name(self, obj):
        return str(obj)

    def to_representation(self, obj):
        data = super().to_representation(obj)
        user = _ctx_user(self)
        if not (user and user_can_view_patient_data(user)):
            for f in self.PII_FIELDS:
                if data.get(f) not in (None, ""):
                    data[f] = MASKED
        return data


class CustomerViewSet(BaseCrudViewSet):
    queryset = Customer.objects.filter(is_active=True).select_related("country", "place")
    serializer_class = CustomerSerializer
    # id_number retiré de la recherche : pas d'énumération par n° de pièce.
    search_fields = ["first_name", "last_name", "company_name", "phone", "email"]
    filterset_fields = ["customer_type", "country"]
    ordering_fields = ["last_name", "company_name", "created_at"]
    ordering = ["-created_at"]


# =====================================================================
# Transactionnel — lecture seule
# =====================================================================

class ParcelSerializer(serializers.ModelSerializer):
    program_label = serializers.CharField(source="program.name", read_only=True, default="")
    commercial_status_display = serializers.CharField(source="get_commercial_status_display", read_only=True)
    area = serializers.SerializerMethodField()

    class Meta:
        model = Parcel
        fields = [
            "id", "lot_number", "parcel_code", "program", "program_label",
            "commercial_status", "commercial_status_display", "technical_status",
            "official_area_m2", "area", "is_serviced", "has_road_access",
            "is_corner", "title_number", "created_at",
        ]

    def get_area(self, obj):
        return f"{obj.official_area_m2} m²" if obj.official_area_m2 else "—"


class ParcelViewSet(BaseReadViewSet):
    queryset = Parcel.objects.filter(is_active=True).select_related("program")
    serializer_class = ParcelSerializer
    search_fields = ["lot_number", "parcel_code", "title_number", "program__name"]
    filterset_fields = ["program", "commercial_status", "technical_status"]
    ordering_fields = ["lot_number", "created_at"]
    ordering = ["lot_number", "id"]


class ReservationSerializer(serializers.ModelSerializer):
    customer_label = serializers.SerializerMethodField()
    program_label = serializers.CharField(source="program.name", read_only=True, default="")
    parcel_label = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reserved_price_display = serializers.SerializerMethodField()
    deposit_display = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id", "reservation_number", "program", "program_label",
            "customer", "customer_label", "parcel", "parcel_label",
            "reservation_date", "expiry_date", "status", "status_display",
            "reserved_price_display", "deposit_display", "notes", "created_at",
        ]

    def get_customer_label(self, obj):
        return str(obj.customer) if obj.customer_id else "—"

    def get_parcel_label(self, obj):
        return (obj.parcel.lot_number or obj.parcel.parcel_code or f"#{obj.parcel_id}") if obj.parcel_id else "—"

    def get_reserved_price_display(self, obj):
        return money_field(self, obj.reserved_price)

    def get_deposit_display(self, obj):
        return money_field(self, obj.deposit_amount)


class ReservationViewSet(BaseReadViewSet):
    queryset = Reservation.objects.filter(is_active=True).select_related("program", "customer", "parcel")
    serializer_class = ReservationSerializer
    search_fields = ["reservation_number", "customer__last_name", "customer__company_name", "program__name"]
    filterset_fields = ["program", "status"]
    ordering_fields = ["reservation_date", "created_at"]
    ordering = ["-reservation_date", "-created_at"]


class SaleSerializer(serializers.ModelSerializer):
    customer_label = serializers.SerializerMethodField()
    program_label = serializers.CharField(source="program.name", read_only=True, default="")
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    net_price_display = serializers.SerializerMethodField()
    agreed_price_display = serializers.SerializerMethodField()

    class Meta:
        model = SaleFile
        fields = [
            "id", "sale_number", "program", "program_label", "customer",
            "customer_label", "sale_date", "status", "status_display",
            "agreed_price_display", "net_price_display", "financing_mode",
            "sales_agent", "notes", "created_at",
        ]

    def get_customer_label(self, obj):
        return str(obj.customer) if obj.customer_id else "—"

    def get_net_price_display(self, obj):
        return money_field(self, obj.net_price)

    def get_agreed_price_display(self, obj):
        return money_field(self, obj.agreed_price)


class SaleViewSet(BaseReadViewSet):
    queryset = SaleFile.objects.filter(is_active=True).select_related("program", "customer")
    serializer_class = SaleSerializer
    search_fields = ["sale_number", "customer__last_name", "customer__company_name", "program__name", "sales_agent"]
    filterset_fields = ["program", "status"]
    ordering_fields = ["sale_date", "created_at"]
    ordering = ["-sale_date", "-created_at"]


class PaymentSerializer(serializers.ModelSerializer):
    sale_label = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    amount_display = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "payment_number", "sale_file", "sale_label", "payment_date",
            "amount_display", "payment_method", "reference", "status",
            "status_display", "received_by", "notes", "created_at",
        ]

    def get_sale_label(self, obj):
        return obj.sale_file.sale_number if obj.sale_file_id else "—"

    def get_amount_display(self, obj):
        return money_field(self, obj.amount)


class PaymentViewSet(BaseReadViewSet):
    queryset = Payment.objects.filter(is_active=True).select_related("sale_file")
    serializer_class = PaymentSerializer
    search_fields = ["payment_number", "reference", "sale_file__sale_number"]
    filterset_fields = ["status", "payment_method", "sale_file"]
    ordering_fields = ["payment_date", "created_at"]
    ordering = ["-payment_date", "-created_at"]


class LeadSerializer(serializers.ModelSerializer):
    program_label = serializers.CharField(source="program.name", read_only=True, default="")
    customer_label = serializers.SerializerMethodField()
    parcel_label = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    budget_min_display = serializers.SerializerMethodField()
    budget_max_display = serializers.SerializerMethodField()
    notes_display = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "program", "program_label", "customer", "customer_label",
            "interested_parcel", "parcel_label", "source", "status", "status_display",
            "budget_min_display", "budget_max_display", "notes_display", "created_at",
        ]

    def get_customer_label(self, obj):
        return str(obj.customer) if obj.customer_id else "—"

    def get_parcel_label(self, obj):
        p = obj.interested_parcel
        return (p.lot_number or p.parcel_code or f"#{p.id}") if p else "—"

    def get_budget_min_display(self, obj):
        return money_field(self, obj.budget_min)

    def get_budget_max_display(self, obj):
        return money_field(self, obj.budget_max)

    def get_notes_display(self, obj):
        # Notes = potentiellement du PII (contexte prospect) → masqué sans droit.
        if not obj.notes:
            return ""
        user = _ctx_user(self)
        return obj.notes if (user and user_can_view_patient_data(user)) else MASKED


class LeadViewSet(BaseReadViewSet):
    queryset = Lead.objects.filter(is_active=True).select_related(
        "program", "customer", "interested_parcel")
    serializer_class = LeadSerializer
    search_fields = ["customer__last_name", "customer__company_name", "program__name", "source"]
    filterset_fields = ["program", "status"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


# =====================================================================
# Options pour les formulaires / filtres du SPA
# =====================================================================

def _choices(model, field):
    return [{"value": v, "label": lbl} for v, lbl in model._meta.get_field(field).choices]


class CrudOptionsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user

        def perms(model):
            app, name = model._meta.app_label, model._meta.model_name
            return {
                "add": u.has_perm(f"{app}.add_{name}"),
                "change": u.has_perm(f"{app}.change_{name}"),
                "delete": u.has_perm(f"{app}.delete_{name}"),
            }

        return Response({
            "countries": [{"value": c.id, "label": c.nom} for c in Country.objects.order_by("nom")],
            "places": [{"value": p.id, "label": p.nom} for p in Place.objects.order_by("nom")[:500]],
            "projects": [{"value": p.id, "label": p.nom}
                         for p in ProjetImmobilier.objects.filter(is_active=True).order_by("nom")],
            "programs": [{"value": p.id, "label": p.name, "project": p.project_id}
                         for p in RealEstateProgram.objects.filter(is_active=True).order_by("name")],
            "program_types": _choices(RealEstateProgram, "program_type"),
            "program_statuses": _choices(RealEstateProgram, "status"),
            "customer_types": _choices(Customer, "customer_type"),
            "parcel_commercial_statuses": _choices(Parcel, "commercial_status"),
            "sale_statuses": _choices(SaleFile, "status"),
            "reservation_statuses": _choices(Reservation, "status"),
            "payment_statuses": _choices(Payment, "status"),
            "lead_statuses": _choices(Lead, "status"),
            "permissions": {
                "project": perms(ProjetImmobilier),
                "program": perms(RealEstateProgram),
                "customer": perms(Customer),
            },
        })
