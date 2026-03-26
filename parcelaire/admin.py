from django.contrib import admin
from django.db.models import Sum
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    Country,
    Place,
    ProjetImmobilier,
    RealEstateProgram,
    ProgramPhase,
    LandUseType,
    ParcelDataset,
    ProgramBlock,
    Parcel,
    ParcelGeometryHistory,
    PropertyType,
    Customer,
    Lead,
    Reservation,
    SaleFile,
    SaleBuyer,
    SaleFileStatusHistory,
    PaymentSchedule,
    PaymentInstallment,
    Payment,
    PaymentAllocation,
    PropertyAsset,
    UnitType,
    AssetCategory,
    PropertyUnit,
    PropertyUnitStatusHistory,
    PropertyAssetStatusHistory,
    AssetDocument,
    UnitDocument,
    SaleDocument,
    ProgramDocument,
    ParcelDocument,
    CustomerDocument,
    ConstructionProject,
    ConstructionUpdate,
    ConstructionPhoto,
    ConstructionMedia, IntegrationLog,
)


# =========================================================
# IMPORT / EXPORT RESOURCES
# =========================================================

class CountryResource(resources.ModelResource):
    class Meta:
        model = Country


class PlaceResource(resources.ModelResource):
    class Meta:
        model = Place


class ProjetImmobilierResource(resources.ModelResource):
    class Meta:
        model = ProjetImmobilier


class RealEstateProgramResource(resources.ModelResource):
    class Meta:
        model = RealEstateProgram


class ProgramPhaseResource(resources.ModelResource):
    class Meta:
        model = ProgramPhase


class LandUseTypeResource(resources.ModelResource):
    class Meta:
        model = LandUseType


class ParcelDatasetResource(resources.ModelResource):
    class Meta:
        model = ParcelDataset


class ProgramBlockResource(resources.ModelResource):
    class Meta:
        model = ProgramBlock


class ParcelResource(resources.ModelResource):
    class Meta:
        model = Parcel


class PropertyTypeResource(resources.ModelResource):
    class Meta:
        model = PropertyType


class AssetCategoryResource(resources.ModelResource):
    class Meta:
        model = AssetCategory


class UnitTypeResource(resources.ModelResource):
    class Meta:
        model = UnitType


class CustomerResource(resources.ModelResource):
    class Meta:
        model = Customer


class LeadResource(resources.ModelResource):
    class Meta:
        model = Lead


class ReservationResource(resources.ModelResource):
    class Meta:
        model = Reservation


class SaleFileResource(resources.ModelResource):
    class Meta:
        model = SaleFile


class PaymentScheduleResource(resources.ModelResource):
    class Meta:
        model = PaymentSchedule


class PaymentInstallmentResource(resources.ModelResource):
    class Meta:
        model = PaymentInstallment


class PaymentResource(resources.ModelResource):
    class Meta:
        model = Payment


class PropertyAssetResource(resources.ModelResource):
    class Meta:
        model = PropertyAsset


class PropertyUnitResource(resources.ModelResource):
    class Meta:
        model = PropertyUnit


class ConstructionProjectResource(resources.ModelResource):
    class Meta:
        model = ConstructionProject


class ConstructionUpdateResource(resources.ModelResource):
    class Meta:
        model = ConstructionUpdate


# =========================================================
# MIXINS
# =========================================================

class BaseAdminMixin:
    """
    Mixin commun pour harmoniser l’admin.
    Les champs FK déclarés dans autocomplete_fields utiliseront
    l’autocomplete Django admin (Select2 natif).
    """
    save_on_top = True
    list_per_page = 50
    show_full_result_count = True


# =========================================================
# INLINES
# =========================================================

class PlaceInline(admin.TabularInline):
    model = Place
    extra = 0
    fields = ("nom", "type", "code", "parent", "geometry", "centroid")
    autocomplete_fields = ("parent",)
    show_change_link = True


class ProgramPhaseInline(admin.TabularInline):
    model = ProgramPhase
    extra = 0
    fields = ("code", "name", "order", "status", "start_date", "end_date", "is_active")
    show_change_link = True


class ProgramBlockInline(admin.TabularInline):
    model = ProgramBlock
    extra = 0
    fields = ("code", "label", "phase", "block_area_m2", "is_active")
    autocomplete_fields = ("phase",)
    show_change_link = True


class ParcelInline(admin.TabularInline):
    model = Parcel
    extra = 0
    fields = (
        "lot_number",
        "parcel_code",
        "external_reference",
        "phase",
        "block",
        "commercial_status",
        "official_area_m2",
        "is_active",
    )
    autocomplete_fields = ("phase", "block", "dataset", "land_use")
    show_change_link = True


class ParcelGeometryHistoryInline(admin.TabularInline):
    model = ParcelGeometryHistory
    extra = 0
    fields = ("reason", "changed_by", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


class ProgramDocumentInline(admin.TabularInline):
    model = ProgramDocument
    extra = 0
    fields = ("title", "document_type", "file", "issued_at", "expires_at", "is_confidential", "is_active")
    show_change_link = True


class ParcelDocumentInline(admin.TabularInline):
    model = ParcelDocument
    extra = 0
    fields = ("title", "document_type", "file", "issued_at", "expires_at", "is_confidential", "is_active")
    show_change_link = True


class CustomerDocumentInline(admin.TabularInline):
    model = CustomerDocument
    extra = 0
    fields = ("title", "document_type", "file", "issued_at", "expires_at", "is_confidential", "is_active")
    show_change_link = True


class AssetDocumentInline(admin.TabularInline):
    model = AssetDocument
    extra = 0
    fields = ("title", "document_type", "file", "issued_at", "expires_at", "is_confidential", "is_active")
    show_change_link = True


class UnitDocumentInline(admin.TabularInline):
    model = UnitDocument
    extra = 0
    fields = ("title", "document_type", "file", "issued_at", "expires_at", "is_confidential", "is_active")
    show_change_link = True


class SaleDocumentInline(admin.TabularInline):
    model = SaleDocument
    extra = 0
    fields = ("title", "document_type", "file", "issued_at", "expires_at", "is_confidential", "is_active")
    show_change_link = True


class PropertyAssetInline(admin.TabularInline):
    model = PropertyAsset
    extra = 0
    fields = (
        "code",
        "label",
        "property_type",
        "asset_category",
        "parcel",
        "status",
        "is_multi_unit",
        "sale_price",
        "is_active",
    )
    autocomplete_fields = ("property_type", "asset_category", "parcel", "phase")
    show_change_link = True


class PropertyUnitInline(admin.TabularInline):
    model = PropertyUnit
    extra = 0
    fields = (
        "code",
        "label",
        "unit_type",
        "floor_number",
        "commercial_status",
        "sale_price",
        "is_saleable",
        "is_active",
    )
    autocomplete_fields = ("unit_type", "phase", "parcel")
    show_change_link = True


class ReservationInline(admin.TabularInline):
    model = Reservation
    extra = 0
    fields = (
        "reservation_number",
        "customer",
        "parcel",
        "unit",
        "reservation_date",
        "reserved_price",
        "deposit_amount",
        "status",
        "is_active",
    )
    autocomplete_fields = ("customer", "parcel", "unit", "lead")
    show_change_link = True


class SaleFileInline(admin.TabularInline):
    model = SaleFile
    extra = 0
    fields = (
        "sale_number",
        "customer",
        "parcel",
        "unit",
        "sale_date",
        "net_price",
        "status",
        "is_active",
    )
    autocomplete_fields = ("customer", "parcel", "unit", "reservation")
    show_change_link = True


class SaleBuyerInline(admin.TabularInline):
    model = SaleBuyer
    extra = 0
    fields = ("customer", "role", "ownership_percent", "is_primary", "notes")
    autocomplete_fields = ("customer",)
    show_change_link = True


class SaleFileStatusHistoryInline(admin.TabularInline):
    model = SaleFileStatusHistory
    extra = 0
    fields = ("old_status", "new_status", "changed_by", "reason", "comment", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


class PaymentInstallmentInline(admin.TabularInline):
    model = PaymentInstallment
    extra = 0
    fields = (
        "label",
        "due_date",
        "amount_due",
        "amount_paid",
        "balance",
        "order",
        "status",
        "is_active",
    )
    show_change_link = True


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = (
        "payment_number",
        "installment",
        "payment_date",
        "amount",
        "payment_method",
        "status",
        "reference",
        "is_active",
    )
    autocomplete_fields = ("installment",)
    show_change_link = True


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    fields = ("sale_file", "unit", "label", "allocated_amount")
    autocomplete_fields = ("sale_file", "unit")
    show_change_link = True


class ConstructionUpdateInline(admin.TabularInline):
    model = ConstructionUpdate
    extra = 0
    fields = (
        "report_date",
        "stage",
        "progress_percent",
        "summary",
        "recorded_by",
        "asset",
        "is_active",
    )
    autocomplete_fields = ("asset",)
    show_change_link = True


class ConstructionPhotoInline(admin.TabularInline):
    model = ConstructionPhoto
    extra = 0
    fields = (
        "title",
        "image",
        "update",
        "shot_date",
        "view_type",
        "is_cover",
        "sort_order",
        "asset",
        "is_active",
    )
    autocomplete_fields = ("update", "asset")
    show_change_link = True


class ConstructionMediaInline(admin.TabularInline):
    model = ConstructionMedia
    extra = 0
    fields = (
        "media_type",
        "file",
        "title",
        "update",
        "shot_date",
        "sort_order",
        "is_active",
    )
    autocomplete_fields = ("update",)
    show_change_link = True


class PropertyUnitStatusHistoryInline(admin.TabularInline):
    model = PropertyUnitStatusHistory
    extra = 0
    fields = ("old_status", "new_status", "changed_by", "reason", "comment", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


class PropertyAssetStatusHistoryInline(admin.TabularInline):
    model = PropertyAssetStatusHistory
    extra = 0
    fields = ("old_status", "new_status", "changed_by", "reason", "comment", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


# =========================================================
# RÉFÉRENTIEL GÉOGRAPHIQUE
# =========================================================

@admin.register(Country)
class CountryAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = CountryResource
    list_display = ("nom", "code", "created_at")
    search_fields = ("nom", "code")
    ordering = ("nom",)
    inlines = [PlaceInline]


@admin.register(Place)
class PlaceAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = PlaceResource
    list_display = ("nom", "type", "country", "parent", "code", "created_at")
    list_filter = ("type", "country")
    search_fields = ("nom", "code", "country__nom", "parent__nom")
    autocomplete_fields = ("country", "parent")
    ordering = ("nom",)


# =========================================================
# PROJETS / PROGRAMMES
# =========================================================

@admin.register(ProjetImmobilier)
class ProjetImmobilierAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = ProjetImmobilierResource
    list_display = ("code", "nom", "country", "place", "is_active", "created_at")
    list_filter = ("country", "is_active")
    search_fields = ("code", "nom", "slug", "description", "address", "country__nom", "place__nom")
    autocomplete_fields = ("country", "place")
    ordering = ("nom",)


@admin.register(RealEstateProgram)
class RealEstateProgramAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = RealEstateProgramResource
    list_display = (
        "code",
        "name",
        "project",
        "program_type",
        "status",
        "country",
        "place",
        "estimated_lot_count",
        "is_active",
    )
    list_filter = ("program_type", "status", "country", "is_active")
    search_fields = (
        "code",
        "name",
        "slug",
        "marketing_title",
        "description",
        "project__nom",
        "country__nom",
        "place__nom",
        "manager_name",
        "manager_phone",
        "manager_email",
    )
    autocomplete_fields = ("project", "country", "place")
    inlines = [ProgramPhaseInline, ProgramBlockInline, ProgramDocumentInline]
    ordering = ("name",)


@admin.register(ProgramPhase)
class ProgramPhaseAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = ProgramPhaseResource
    list_display = ("code", "name", "program", "order", "status", "start_date", "end_date", "is_active")
    list_filter = ("status", "program", "is_active")
    search_fields = ("code", "name", "program__name", "program__code")
    autocomplete_fields = ("program",)
    ordering = ("program", "order", "name")


# =========================================================
# RÉFÉRENTIEL FONCIER
# =========================================================

@admin.register(LandUseType)
class LandUseTypeAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = LandUseTypeResource
    list_display = ("code", "label", "created_at")
    search_fields = ("code", "label", "description")
    ordering = ("label",)


@admin.register(ParcelDataset)
class ParcelDatasetAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = ParcelDatasetResource
    list_display = (
        "name",
        "program",
        "phase",
        "version",
        "is_current",
        "source_code",
        "imported_by",
        "is_active",
        "created_at",
    )
    list_filter = ("is_current", "program", "phase", "is_active")
    search_fields = ("name", "source_code", "source_file_name", "program__name", "phase__name", "imported_by")
    autocomplete_fields = ("program", "phase")
    ordering = ("-created_at",)


@admin.register(ProgramBlock)
class ProgramBlockAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = ProgramBlockResource
    list_display = ("code", "label", "program", "phase", "block_area_m2", "is_active")
    list_filter = ("program", "phase", "is_active")
    search_fields = ("code", "label", "description", "program__name", "phase__name")
    autocomplete_fields = ("program", "phase")
    inlines = [ParcelInline]
    ordering = ("program", "code")


@admin.register(Parcel)
class ParcelAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = ParcelResource
    list_display = (
        "display_name",
        "program",
        "phase",
        "block",
        "commercial_status",
        "technical_status",
        "official_area_m2",
        "has_road_access",
        "is_corner",
        "is_active",
    )
    list_filter = (
        "commercial_status",
        "technical_status",
        "program",
        "phase",
        "block",
        "is_corner",
        "is_serviced",
        "has_road_access",
        "has_title_document",
        "geometry_valid",
        "duplicate_flag",
        "is_active",
    )
    search_fields = (
        "lot_number",
        "parcel_code",
        "external_reference",
        "title_number",
        "zoning",
        "program__name",
        "program__code",
        "phase__name",
        "block__code",
    )
    autocomplete_fields = ("dataset", "program", "phase", "block", "land_use")
    inlines = [
        ParcelGeometryHistoryInline,
        ParcelDocumentInline,
        PropertyAssetInline,
        ReservationInline,
        SaleFileInline,
    ]
    ordering = ("program", "block__code", "lot_number")
    date_hierarchy = "created_at"

    fieldsets = (
        ("Identification", {
            "fields": (
                "dataset",
                "program",
                "phase",
                "block",
                "source_fid",
                "lot_number",
                "parcel_code",
                "external_reference",
            )
        }),
        ("Surfaces et dimensions", {
            "fields": (
                "official_area_m2",
                "computed_area_m2",
                "frontage_m",
                "depth_m",
                "slope",
                "elevation",
            )
        }),
        ("Usage / statuts", {
            "fields": (
                "land_use",
                "technical_status",
                "commercial_status",
                "is_corner",
                "is_serviced",
                "has_road_access",
                "has_title_document",
                "title_number",
                "zoning",
                "valeur_hypothecaire",
                "crm_last_synced_at",
            )
        }),
        ("Géospatial", {
            "fields": ("geometry", "centroid", "geometry_valid")
        }),
        ("Contrôle", {
            "fields": ("has_number", "duplicate_flag", "is_active")
        }),
        ("Compléments", {
            "fields": ("notes", "metadata")
        }),
    )

    @admin.display(description="Parcelle")
    def display_name(self, obj):
        return obj.lot_number or obj.parcel_code or f"Parcelle #{obj.pk}"


@admin.register(ParcelGeometryHistory)
class ParcelGeometryHistoryAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("parcel", "reason", "changed_by", "created_at")
    search_fields = ("parcel__lot_number", "parcel__parcel_code", "reason", "changed_by")
    autocomplete_fields = ("parcel",)
    ordering = ("-created_at",)


# =========================================================
# CLIENTS / CRM
# =========================================================

@admin.register(Customer)
class CustomerAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = CustomerResource
    list_display = (
        "display_name",
        "customer_type",
        "phone",
        "email",
        "country",
        "place",
        "is_active",
        "created_at",
    )
    list_filter = ("customer_type", "country", "is_active")
    search_fields = (
        "first_name",
        "last_name",
        "company_name",
        "phone",
        "email",
        "id_number",
        "address",
    )
    autocomplete_fields = ("country", "place")
    inlines = [CustomerDocumentInline, ReservationInline, SaleFileInline]
    ordering = ("last_name", "first_name", "company_name")

    @admin.display(description="Client")
    def display_name(self, obj):
        return str(obj)


@admin.register(Lead)
class LeadAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = LeadResource
    list_display = ("id", "program", "customer", "interested_parcel", "status", "budget_min", "budget_max", "created_at")
    list_filter = ("status", "program", "is_active")
    search_fields = (
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "program__name",
        "source",
        "notes",
        "interested_parcel__lot_number",
        "interested_parcel__parcel_code",
    )
    autocomplete_fields = ("program", "customer", "interested_parcel")
    ordering = ("-created_at",)


# =========================================================
# TYPOLOGIES D'ACTIFS / UNITÉS
# =========================================================

@admin.register(PropertyType)
class PropertyTypeAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = PropertyTypeResource
    list_display = ("code", "label", "is_active", "created_at")
    search_fields = ("code", "label")
    list_filter = ("is_active",)
    ordering = ("label",)


@admin.register(UnitType)
class UnitTypeAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = UnitTypeResource
    list_display = ("code", "label", "is_active", "created_at")
    search_fields = ("code", "label", "description")
    list_filter = ("is_active",)
    ordering = ("label",)


@admin.register(AssetCategory)
class AssetCategoryAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = AssetCategoryResource
    list_display = ("code", "label", "default_floors", "is_active", "created_at")
    search_fields = ("code", "label", "description")
    list_filter = ("is_active",)
    ordering = ("label",)


# =========================================================
# ACTIFS / UNITÉS
# =========================================================

@admin.register(PropertyAsset)
class PropertyAssetAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = PropertyAssetResource
    list_display = (
        "code",
        "label",
        "program",
        "phase",
        "parcel",
        "property_type",
        "asset_category",
        "status",
        "is_multi_unit",
        "total_units_count",
        "sale_price",
        "is_active",
    )
    list_filter = (
        "status",
        "is_multi_unit",
        "program",
        "phase",
        "property_type",
        "asset_category",
        "is_active",
    )
    search_fields = (
        "code",
        "label",
        "description",
        "program__name",
        "phase__name",
        "parcel__lot_number",
        "parcel__parcel_code",
        "property_type__label",
        "asset_category__label",
    )
    autocomplete_fields = ("program", "phase", "parcel", "property_type", "asset_category")
    inlines = [
        PropertyUnitInline,
        AssetDocumentInline,
        ConstructionPhotoInline,
        PropertyAssetStatusHistoryInline,
    ]
    ordering = ("program", "code")


@admin.register(PropertyUnit)
class PropertyUnitAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = PropertyUnitResource
    list_display = (
        "code",
        "label",
        "program",
        "asset",
        "unit_type",
        "floor_number",
        "commercial_status",
        "sale_price",
        "is_saleable",
        "is_active",
    )
    list_filter = (
        "commercial_status",
        "program",
        "phase",
        "unit_type",
        "has_parking",
        "has_garden",
        "has_terrace",
        "has_balcony",
        "is_saleable",
        "is_deliverable",
        "is_active",
    )
    search_fields = (
        "code",
        "label",
        "slug",
        "building",
        "entrance",
        "staircase",
        "door_number",
        "asset__label",
        "asset__code",
        "parcel__lot_number",
        "parcel__parcel_code",
    )
    autocomplete_fields = ("program", "phase", "parcel", "asset", "unit_type")
    inlines = [
        UnitDocumentInline,
        ReservationInline,
        SaleFileInline,
        PropertyUnitStatusHistoryInline,
    ]
    ordering = ("asset", "floor_number", "code")


@admin.register(PropertyUnitStatusHistory)
class PropertyUnitStatusHistoryAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("unit", "old_status", "new_status", "changed_by", "reason", "created_at")
    list_filter = ("new_status",)
    search_fields = ("unit__code", "unit__label", "changed_by", "reason", "comment")
    autocomplete_fields = ("unit",)
    ordering = ("-created_at",)


@admin.register(PropertyAssetStatusHistory)
class PropertyAssetStatusHistoryAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("asset", "old_status", "new_status", "changed_by", "reason", "created_at")
    list_filter = ("new_status",)
    search_fields = ("asset__code", "asset__label", "changed_by", "reason", "comment")
    autocomplete_fields = ("asset",)
    ordering = ("-created_at",)


# =========================================================
# RÉSERVATIONS / VENTES
# =========================================================

@admin.register(Reservation)
class ReservationAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = ReservationResource
    list_display = (
        "reservation_number",
        "program",
        "customer",
        "parcel",
        "unit",
        "reservation_date",
        "expiry_date",
        "reserved_price",
        "deposit_amount",
        "status",
        "is_active",
    )
    list_filter = ("status", "program", "reservation_date", "expiry_date", "is_active")
    search_fields = (
        "reservation_number",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "parcel__lot_number",
        "parcel__parcel_code",
        "unit__code",
        "unit__label",
        "notes",
    )
    autocomplete_fields = ("program", "customer", "parcel", "unit", "lead")
    ordering = ("-reservation_date", "-created_at")
    date_hierarchy = "reservation_date"


@admin.register(SaleFile)
class SaleFileAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = SaleFileResource
    list_display = (
        "sale_number",
        "program",
        "customer",
        "parcel",
        "unit",
        "sale_date",
        "agreed_price",
        "discount_amount",
        "net_price",
        "status",
        "is_active",
        "total_paid_display",
    )
    list_filter = ("status", "program", "sale_date", "is_active")
    search_fields = (
        "sale_number",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "parcel__lot_number",
        "parcel__parcel_code",
        "unit__code",
        "unit__label",
        "sales_agent",
        "notes",
    )
    autocomplete_fields = ("program", "customer", "parcel", "unit", "reservation")
    inlines = [
        SaleBuyerInline,
        SaleDocumentInline,
        PaymentInline,
        PaymentAllocationInline,
        SaleFileStatusHistoryInline,
    ]
    ordering = ("-sale_date", "-created_at")
    date_hierarchy = "sale_date"

    @admin.display(description="Total payé")
    def total_paid_display(self, obj):
        total = obj.payments.filter(status="CONFIRMED").aggregate(total=Sum("amount"))["total"] or 0
        return total


@admin.register(SaleBuyer)
class SaleBuyerAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("sale_file", "customer", "role", "ownership_percent", "is_primary", "created_at")
    list_filter = ("role", "is_primary")
    search_fields = (
        "sale_file__sale_number",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
    )
    autocomplete_fields = ("sale_file", "customer")
    ordering = ("sale_file", "-is_primary", "id")


@admin.register(SaleFileStatusHistory)
class SaleFileStatusHistoryAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("sale_file", "old_status", "new_status", "changed_by", "reason", "created_at")
    list_filter = ("new_status",)
    search_fields = ("sale_file__sale_number", "changed_by", "reason", "comment")
    autocomplete_fields = ("sale_file",)
    ordering = ("-created_at",)


# =========================================================
# PAIEMENTS
# =========================================================

@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = PaymentScheduleResource
    list_display = ("name", "sale_file", "total_amount", "start_date", "end_date", "is_active")
    list_filter = ("is_active", "start_date", "end_date")
    search_fields = ("name", "sale_file__sale_number", "sale_file__customer__first_name", "sale_file__customer__last_name")
    autocomplete_fields = ("sale_file",)
    inlines = [PaymentInstallmentInline]
    ordering = ("-created_at",)


@admin.register(PaymentInstallment)
class PaymentInstallmentAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = PaymentInstallmentResource
    list_display = (
        "label",
        "schedule",
        "due_date",
        "amount_due",
        "amount_paid",
        "balance",
        "order",
        "status",
        "is_active",
    )
    list_filter = ("status", "schedule", "is_active")
    search_fields = ("label", "schedule__name", "schedule__sale_file__sale_number")
    autocomplete_fields = ("schedule",)
    ordering = ("schedule", "order", "due_date")


@admin.register(Payment)
class PaymentAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = PaymentResource
    list_display = (
        "payment_number",
        "sale_file",
        "installment",
        "payment_date",
        "amount",
        "payment_method",
        "status",
        "reference",
        "is_active",
    )
    list_filter = ("payment_method", "status", "payment_date", "is_active")
    search_fields = (
        "payment_number",
        "sale_file__sale_number",
        "reference",
        "received_by",
        "notes",
        "sale_file__customer__first_name",
        "sale_file__customer__last_name",
        "sale_file__customer__company_name",
    )
    autocomplete_fields = ("sale_file", "installment")
    inlines = [PaymentAllocationInline]
    ordering = ("-payment_date", "-created_at")
    date_hierarchy = "payment_date"


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("payment", "sale_file", "unit", "label", "allocated_amount", "created_at")
    search_fields = (
        "payment__payment_number",
        "sale_file__sale_number",
        "unit__code",
        "unit__label",
        "label",
    )
    autocomplete_fields = ("payment", "sale_file", "unit")
    ordering = ("payment", "id")


# =========================================================
# DOCUMENTS
# =========================================================

@admin.register(ProgramDocument)
class ProgramDocumentAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("title", "program", "document_type", "issued_at", "expires_at", "is_confidential", "is_active")
    list_filter = ("document_type", "is_confidential", "is_active")
    search_fields = ("title", "description", "program__name", "original_filename")
    autocomplete_fields = ("program",)
    ordering = ("-created_at",)


@admin.register(ParcelDocument)
class ParcelDocumentAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("title", "parcel", "document_type", "issued_at", "expires_at", "is_confidential", "is_active")
    list_filter = ("document_type", "is_confidential", "is_active")
    search_fields = ("title", "description", "parcel__lot_number", "parcel__parcel_code", "original_filename")
    autocomplete_fields = ("parcel",)
    ordering = ("-created_at",)


@admin.register(CustomerDocument)
class CustomerDocumentAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("title", "customer", "document_type", "issued_at", "expires_at", "is_confidential", "is_active")
    list_filter = ("document_type", "is_confidential", "is_active")
    search_fields = (
        "title",
        "description",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "original_filename",
    )
    autocomplete_fields = ("customer",)
    ordering = ("-created_at",)


@admin.register(AssetDocument)
class AssetDocumentAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("title", "asset", "document_type", "issued_at", "expires_at", "is_confidential", "is_active")
    list_filter = ("document_type", "is_confidential", "is_active")
    search_fields = ("title", "description", "asset__code", "asset__label", "original_filename")
    autocomplete_fields = ("asset",)
    ordering = ("-created_at",)


@admin.register(UnitDocument)
class UnitDocumentAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("title", "unit", "document_type", "issued_at", "expires_at", "is_confidential", "is_active")
    list_filter = ("document_type", "is_confidential", "is_active")
    search_fields = ("title", "description", "unit__code", "unit__label", "original_filename")
    autocomplete_fields = ("unit",)
    ordering = ("-created_at",)


@admin.register(SaleDocument)
class SaleDocumentAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("title", "sale_file", "document_type", "issued_at", "expires_at", "is_confidential", "is_active")
    list_filter = ("document_type", "is_confidential", "is_active")
    search_fields = ("title", "description", "sale_file__sale_number", "original_filename")
    autocomplete_fields = ("sale_file",)
    ordering = ("-created_at",)


# =========================================================
# CONSTRUCTION / CHANTIER
# =========================================================

@admin.register(ConstructionProject)
class ConstructionProjectAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = ConstructionProjectResource
    list_display = (
        "code",
        "title",
        "parcel",
        "asset",
        "status",
        "progress_percent",
        "estimated_budget",
        "actual_cost",
        "planned_start_date",
        "actual_start_date",
        "is_active",
    )
    list_filter = ("status", "is_active", "planned_start_date", "actual_start_date")
    search_fields = (
        "code",
        "title",
        "description",
        "contractor_name",
        "site_manager",
        "parcel__lot_number",
        "parcel__parcel_code",
        "asset__code",
        "asset__label",
    )
    autocomplete_fields = ("parcel", "asset")
    inlines = [ConstructionUpdateInline, ConstructionPhotoInline, ConstructionMediaInline]
    ordering = ("-created_at",)


@admin.register(ConstructionUpdate)
class ConstructionUpdateAdmin(BaseAdminMixin, ImportExportModelAdmin):
    resource_class = ConstructionUpdateResource
    list_display = (
        "construction_project",
        "report_date",
        "stage",
        "progress_percent",
        "summary",
        "recorded_by",
        "asset",
        "is_active",
    )
    list_filter = ("stage", "report_date", "is_active")
    search_fields = (
        "summary",
        "details",
        "issues",
        "next_actions",
        "recorded_by",
        "construction_project__code",
        "construction_project__title",
        "asset__code",
        "asset__label",
    )
    autocomplete_fields = ("construction_project", "asset")
    ordering = ("-report_date", "-created_at")
    date_hierarchy = "report_date"


@admin.register(ConstructionPhoto)
class ConstructionPhotoAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "construction_project",
        "update",
        "shot_date",
        "view_type",
        "is_cover",
        "sort_order",
        "asset",
        "is_active",
    )
    list_filter = ("view_type", "is_cover", "is_active")
    search_fields = (
        "title",
        "caption",
        "construction_project__code",
        "construction_project__title",
        "asset__code",
        "asset__label",
    )
    autocomplete_fields = ("construction_project", "update", "asset")
    ordering = ("sort_order", "-shot_date", "-created_at")


@admin.register(ConstructionMedia)
class ConstructionMediaAdmin(BaseAdminMixin, admin.ModelAdmin):
    list_display = ("title", "construction_project", "update", "media_type", "shot_date", "sort_order", "is_active")
    list_filter = ("media_type", "is_active")
    search_fields = ("title", "caption", "construction_project__code", "construction_project__title")
    autocomplete_fields = ("construction_project", "update")
    ordering = ("sort_order", "-created_at")



# SAP -=-=-=-=-=-=-=-=-=-=
@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "system",
        "direction",
        "operation",
        "status",
        "http_status",
        "external_id",
    )
    list_filter = ("system", "direction", "status", "operation")
    search_fields = ("operation", "endpoint", "external_id", "error_message")
    readonly_fields = (
        "created_at",
        "system",
        "direction",
        "operation",
        "endpoint",
        "method",
        "request_payload",
        "response_payload",
        "status",
        "http_status",
        "error_message",
        "external_id",
    )