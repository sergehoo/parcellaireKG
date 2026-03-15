from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin, OSMGeoAdmin

from django.utils.html import format_html

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
    PaymentSchedule,
    PaymentInstallment,
    Payment,
    PropertyAsset,
    ProgramDocument,
    ParcelDocument,
    CustomerDocument, ConstructionUpdate, ConstructionProject, ConstructionPhoto,
)

admin.site.site_header = "Administration Parcellaire & Immobilier"
admin.site.site_title = "Admin Immobilier"
admin.site.index_title = "Gestion des projets, programmes, parcelles et actifs"


# =========================
# INLINES
# =========================

class PlaceInline(admin.TabularInline):
    model = Place
    extra = 0
    fields = ("nom", "type", "parent", "code")
    show_change_link = True


class ProgramPhaseInline(admin.TabularInline):
    model = ProgramPhase
    extra = 0
    fields = ("code", "name", "order", "status", "start_date", "end_date")
    show_change_link = True


class ProgramBlockInline(admin.TabularInline):
    model = ProgramBlock
    extra = 0
    fields = ("code", "label", "phase", "block_area_m2")
    show_change_link = True


class ParcelDatasetInline(admin.TabularInline):
    model = ParcelDataset
    extra = 0
    fields = ("name", "phase", "version", "is_current", "source_file_name")
    show_change_link = True


class ProgramDocumentInline(admin.TabularInline):
    model = ProgramDocument
    extra = 0
    fields = ("title", "document_type", "file", "is_confidential")
    show_change_link = True


class ParcelDocumentInline(admin.TabularInline):
    model = ParcelDocument
    extra = 0
    fields = ("title", "document_type", "file", "is_confidential")
    show_change_link = True


class ParcelGeometryHistoryInline(admin.TabularInline):
    model = ParcelGeometryHistory
    extra = 0
    fields = ("reason", "changed_by", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


class PaymentInstallmentInline(admin.TabularInline):
    model = PaymentInstallment
    extra = 0
    fields = ("order", "label", "due_date", "amount_due", "amount_paid", "balance", "status")
    show_change_link = True


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("payment_number", "payment_date", "amount", "payment_method", "status")
    show_change_link = True


class CustomerDocumentInline(admin.TabularInline):
    model = CustomerDocument
    extra = 0
    fields = ("title", "document_type", "file", "is_confidential")
    show_change_link = True


# =========================
# COUNTRY / PLACE
# =========================

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("nom", "code", "created_at")
    search_fields = ("nom", "code")
    ordering = ("nom",)
    inlines = [PlaceInline]


@admin.register(Place)
class PlaceAdmin(OSMGeoAdmin):
    list_display = ("nom", "type", "country", "parent", "created_at")
    list_filter = ("type", "country")
    search_fields = ("nom", "code", "country__nom", "parent__nom")
    autocomplete_fields = ("country", "parent")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("country", "parent")


# =========================
# REFERENTIELS
# =========================

@admin.register(LandUseType)
class LandUseTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "created_at")
    search_fields = ("code", "label")
    ordering = ("label",)


@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "label")
    ordering = ("label",)


# =========================
# PROJET / PROGRAMME
# =========================

@admin.register(ProjetImmobilier)
class ProjetImmobilierAdmin(OSMGeoAdmin):
    list_display = ("nom", "code", "country", "place", "is_active", "created_at")
    list_filter = ("is_active", "country")
    search_fields = ("nom", "code", "country__nom", "place__nom")
    autocomplete_fields = ("country", "place")
    readonly_fields = ("slug", "created_at", "updated_at")
    list_select_related = ("country", "place")


@admin.register(RealEstateProgram)
class RealEstateProgramAdmin(OSMGeoAdmin):
    list_display = (
        "name",
        "code",
        "project",
        "program_type",
        "status",
        "country",
        "place",
        "estimated_lot_count",
        "is_active",
    )
    list_filter = ("program_type", "status", "is_active", "country")
    search_fields = (
        "name",
        "code",
        "slug",
        "marketing_title",
        "project__nom",
        "country__nom",
        "place__nom",
    )
    autocomplete_fields = ("country", "place", "project")
    readonly_fields = ("slug", "created_at", "updated_at")
    list_select_related = ("country", "place", "project")
    inlines = [ProgramPhaseInline, ProgramBlockInline, ParcelDatasetInline, ProgramDocumentInline]


@admin.register(ProgramPhase)
class ProgramPhaseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "program", "order", "status", "start_date", "end_date", "is_active")
    list_filter = ("status", "is_active", "program")
    search_fields = ("name", "code", "program__name")
    autocomplete_fields = ("program",)
    list_select_related = ("program",)


@admin.register(ParcelDataset)
class ParcelDatasetAdmin(admin.ModelAdmin):
    list_display = ("name", "program", "phase", "version", "is_current", "source_file_name", "created_at")
    list_filter = ("is_current", "program", "phase")
    search_fields = ("name", "source_code", "source_file_name", "program__name")
    autocomplete_fields = ("program", "phase")
    list_select_related = ("program", "phase")


@admin.register(ProgramBlock)
class ProgramBlockAdmin(OSMGeoAdmin):
    list_display = ("code", "label", "program", "phase", "block_area_m2", "is_active")
    list_filter = ("is_active", "program", "phase")
    search_fields = ("code", "label", "program__name", "phase__name")
    autocomplete_fields = ("program", "phase")
    list_select_related = ("program", "phase")


# =========================
# PARCELLAIRE
# =========================

@admin.register(Parcel)
class ParcelAdmin(OSMGeoAdmin):
    list_display = (
        "display_lot",
        "program",
        "phase",
        "block",
        "official_area_m2",
        "commercial_status",
        "technical_status",
        "land_use",
        "duplicate_flag",
        "is_active",
    )
    list_filter = (
        "commercial_status",
        "technical_status",
        "is_corner",
        "is_serviced",
        "has_road_access",
        "has_title_document",
        "duplicate_flag",
        "geometry_valid",
        "program",
        "phase",
        "block",
        "land_use",
        "is_active",
    )
    search_fields = (
        "lot_number",
        "parcel_code",
        "external_reference",
        "source_fid",
        "title_number",
        "program__name",
        "block__code",
    )
    autocomplete_fields = ("dataset", "program", "phase", "block", "land_use")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("dataset", "program", "phase", "block", "land_use")
    inlines = [ParcelDocumentInline, ParcelGeometryHistoryInline]

    @admin.display(description="Lot / Parcelle")
    def display_lot(self, obj):
        return obj.lot_number or obj.parcel_code or f"FID {obj.source_fid or '-'}"


@admin.register(ParcelGeometryHistory)
class ParcelGeometryHistoryAdmin(OSMGeoAdmin):
    list_display = ("parcel", "reason", "changed_by", "created_at")
    search_fields = ("parcel__lot_number", "parcel__parcel_code", "reason", "changed_by")
    autocomplete_fields = ("parcel",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("parcel",)


# =========================
# CLIENTS / CRM
# =========================

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "customer_type", "phone", "email", "country", "place", "is_active")
    list_filter = ("customer_type", "country", "is_active")
    search_fields = (
        "first_name",
        "last_name",
        "company_name",
        "phone",
        "email",
        "id_number",
    )
    autocomplete_fields = ("country", "place")
    list_select_related = ("country", "place")
    inlines = [CustomerDocumentInline]

    @admin.display(description="Client")
    def display_name(self, obj):
        if obj.customer_type == "COMPANY":
            return obj.company_name or "Entreprise"
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip() or "Client"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("customer", "program", "interested_parcel", "source", "status", "created_at")
    list_filter = ("status", "program", "source", "is_active")
    search_fields = (
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "program__name",
        "interested_parcel__lot_number",
    )
    autocomplete_fields = ("program", "customer", "interested_parcel")
    list_select_related = ("program", "customer", "interested_parcel")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "reservation_number",
        "program",
        "customer",
        "parcel",
        "reservation_date",
        "expiry_date",
        "reserved_price",
        "deposit_amount",
        "status",
    )
    list_filter = ("status", "program", "reservation_date", "is_active")
    search_fields = (
        "reservation_number",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "parcel__lot_number",
        "program__name",
    )
    autocomplete_fields = ("program", "customer", "parcel", "lead")
    list_select_related = ("program", "customer", "parcel", "lead")


# =========================
# VENTE / PAIEMENT
# =========================

@admin.register(SaleFile)
class SaleFileAdmin(admin.ModelAdmin):
    list_display = (
        "sale_number",
        "program",
        "customer",
        "parcel",
        "sale_date",
        "agreed_price",
        "discount_amount",
        "net_price",
        "status",
    )
    list_filter = ("status", "program", "sale_date", "is_active")
    search_fields = (
        "sale_number",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "parcel__lot_number",
        "program__name",
    )
    autocomplete_fields = ("program", "customer", "parcel", "reservation")
    list_select_related = ("program", "customer", "parcel", "reservation")
    inlines = [PaymentInline]


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "sale_file", "total_amount", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "sale_file__sale_number")
    autocomplete_fields = ("sale_file",)
    list_select_related = ("sale_file",)
    inlines = [PaymentInstallmentInline]


@admin.register(PaymentInstallment)
class PaymentInstallmentAdmin(admin.ModelAdmin):
    list_display = ("label", "schedule", "order", "due_date", "amount_due", "amount_paid", "balance", "status")
    list_filter = ("status", "due_date", "is_active")
    search_fields = ("label", "schedule__name", "schedule__sale_file__sale_number")
    autocomplete_fields = ("schedule",)
    list_select_related = ("schedule",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_number",
        "sale_file",
        "installment",
        "payment_date",
        "amount",
        "payment_method",
        "status",
    )
    list_filter = ("status", "payment_method", "payment_date", "is_active")
    search_fields = ("payment_number", "reference", "sale_file__sale_number")
    autocomplete_fields = ("sale_file", "installment")
    list_select_related = ("sale_file", "installment")


# =========================
# ACTIFS IMMOBILIERS
# =========================

@admin.register(PropertyAsset)
class PropertyAssetAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "code",
        "program",
        "phase",
        "parcel",
        "property_type",
        "built_area_m2",
        "sale_price",
        "status",
        "is_active",
    )
    list_filter = ("status", "property_type", "program", "phase", "is_active")
    search_fields = ("label", "code", "program__name", "parcel__lot_number")
    autocomplete_fields = ("program", "phase", "parcel", "property_type")
    list_select_related = ("program", "phase", "parcel", "property_type")


# =========================
# DOCUMENTS
# =========================

@admin.register(ProgramDocument)
class ProgramDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "program", "document_type", "is_confidential", "created_at", "file_link")
    list_filter = ("document_type", "is_confidential", "created_at", "is_active")
    search_fields = ("title", "program__name", "original_filename")
    autocomplete_fields = ("program",)
    list_select_related = ("program",)
    readonly_fields = ("created_at", "updated_at", "file_link", "original_filename", "file_size", "mime_type")

    @admin.display(description="Fichier")
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Ouvrir</a>', obj.file.url)
        return "-"


@admin.register(ParcelDocument)
class ParcelDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "parcel", "document_type", "is_confidential", "created_at", "file_link")
    list_filter = ("document_type", "is_confidential", "created_at", "is_active")
    search_fields = ("title", "parcel__lot_number", "parcel__parcel_code", "original_filename")
    autocomplete_fields = ("parcel",)
    list_select_related = ("parcel",)
    readonly_fields = ("created_at", "updated_at", "file_link", "original_filename", "file_size", "mime_type")

    @admin.display(description="Fichier")
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Ouvrir</a>', obj.file.url)
        return "-"


@admin.register(CustomerDocument)
class CustomerDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "customer", "document_type", "is_confidential", "created_at", "file_link")
    list_filter = ("document_type", "is_confidential", "created_at", "is_active")
    search_fields = (
        "title",
        "customer__first_name",
        "customer__last_name",
        "customer__company_name",
        "original_filename",
    )
    autocomplete_fields = ("customer",)
    list_select_related = ("customer",)
    readonly_fields = ("created_at", "updated_at", "file_link", "original_filename", "file_size", "mime_type")

    @admin.display(description="Fichier")
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Ouvrir</a>', obj.file.url)
        return "-"


class ConstructionPhotoInline(admin.TabularInline):
    model = ConstructionPhoto
    extra = 0
    fields = ("preview", "title", "image", "shot_date", "view_type", "is_cover", "sort_order")
    readonly_fields = ("preview",)
    show_change_link = True

    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="height:80px; border-radius:6px;" />',
                obj.image.url
            )
        return "-"

    preview.short_description = "Aperçu"


class ConstructionUpdateInline(admin.TabularInline):
    model = ConstructionUpdate
    extra = 0
    fields = ("report_date", "stage", "progress_percent", "summary", "recorded_by")
    show_change_link = True


@admin.register(ConstructionProject)
class ConstructionProjectAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "parcel",
        "asset",
        "status",
        "progress_percent",
        "planned_start_date",
        "planned_end_date",
        "actual_end_date",
        "is_active",
    )
    list_filter = ("status", "is_active", "planned_start_date")
    search_fields = ("title", "code", "parcel__lot_number", "asset__label", "contractor_name")
    autocomplete_fields = ("parcel", "asset")
    inlines = [ConstructionUpdateInline, ConstructionPhotoInline]


@admin.register(ConstructionUpdate)
class ConstructionUpdateAdmin(admin.ModelAdmin):
    list_display = (
        "construction_project",
        "report_date",
        "stage",
        "progress_percent",
        "recorded_by",
    )
    list_filter = ("stage", "report_date", "is_active")
    search_fields = ("construction_project__title", "summary", "recorded_by")
    autocomplete_fields = ("construction_project",)


@admin.register(ConstructionPhoto)
class ConstructionPhotoAdmin(admin.ModelAdmin):
    list_display = (
        "thumbnail",
        "construction_project",
        "update",
        "title",
        "shot_date",
        "view_type",
        "is_cover",
    )
    list_filter = ("view_type", "is_cover", "shot_date", "is_active")
    search_fields = ("title", "construction_project__title", "caption")
    autocomplete_fields = ("construction_project", "update")
    readonly_fields = ("thumbnail",)

    def thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:70px; border-radius:6px;" />',
                obj.image.url
            )
        return "-"

    thumbnail.short_description = "Image"
