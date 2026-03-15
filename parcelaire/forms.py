from django import forms
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import GEOSGeometry

from .models import (
    Country,
    Place,
    ProjetImmobilier,
    RealEstateProgram,
    ProgramPhase,
    ParcelDataset,
    ProgramBlock,
    Parcel,
    PropertyType,
    PropertyAsset,
    Customer,
    Lead,
    Reservation,
    SaleFile,
    PaymentSchedule,
    PaymentInstallment,
    Payment,
    ProgramDocument,
    ParcelDocument,
    CustomerDocument,
    ConstructionProject,
    ConstructionUpdate,
    ConstructionPhoto,
    ConstructionMedia, LandUseType,
)


class BaseModelForm(forms.ModelForm):
    """
    Formulaire de base avec styles bootstrap / metronic simples.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault("class", "form-control")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-control")
                widget.attrs.setdefault("rows", 3)
            else:
                widget.attrs.setdefault("class", "form-control")

            widget.attrs.setdefault("autocomplete", "off")


class GeoJSONGeometryField(forms.CharField):
    """
    Permet de coller un GeoJSON dans un textarea puis le convertir en géométrie GEOS.
    """

    def __init__(self, *args, geom_type=None, srid=4326, **kwargs):
        self.geom_type = geom_type
        self.srid = srid
        kwargs.setdefault("required", False)
        kwargs.setdefault("widget", forms.Textarea(attrs={"rows": 5}))
        super().__init__(*args, **kwargs)

    def clean(self, value):
        value = super().clean(value)

        if not value:
            return None

        try:
            geom = GEOSGeometry(value, srid=self.srid)
        except Exception as exc:
            raise ValidationError(f"Géométrie invalide : {exc}")

        if self.geom_type and geom.geom_type.upper() != self.geom_type.upper():
            raise ValidationError(
                f"Type de géométrie invalide. Attendu : {self.geom_type}, reçu : {geom.geom_type}."
            )

        return geom


class CountryForm(BaseModelForm):
    class Meta:
        model = Country
        fields = ["nom", "code"]


class PlaceForm(BaseModelForm):
    geometry_input = GeoJSONGeometryField(
        label="Géométrie (GeoJSON MultiPolygon)",
        geom_type="MultiPolygon",
        required=False
    )

    centroid_input = GeoJSONGeometryField(
        label="Centroïde (GeoJSON Point)",
        geom_type="Point",
        required=False
    )

    class Meta:
        model = Place
        fields = [
            "nom",
            "code",
            "type",
            "country",
            "parent",
            "metadata",
        ]
        widgets = {
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["parent"].queryset = Place.objects.select_related("country").order_by("nom")
        self.fields["country"].queryset = Country.objects.order_by("nom")

        if self.instance.pk:
            self.fields["geometry_input"].initial = self.instance.geometry.geojson if self.instance.geometry else ""
            self.fields["centroid_input"].initial = self.instance.centroid.geojson if self.instance.centroid else ""

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.geometry = self.cleaned_data.get("geometry_input")
        obj.centroid = self.cleaned_data.get("centroid_input")
        if commit:
            obj.save()
        return obj


class ProjetImmobilierForm(BaseModelForm):
    boundary_input = GeoJSONGeometryField(
        label="Limite du projet (GeoJSON MultiPolygon)",
        geom_type="MultiPolygon",
        required=False
    )

    centroid_input = GeoJSONGeometryField(
        label="Centroïde du projet (GeoJSON Point)",
        geom_type="Point",
        required=False
    )

    class Meta:
        model = ProjetImmobilier
        fields = [
            "code",
            "nom",
            "description",
            "country",
            "place",
            "address",
            "metadata",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["country"].queryset = Country.objects.order_by("nom")
        self.fields["place"].queryset = Place.objects.select_related("country").order_by("nom")

        if self.instance.pk:
            self.fields["boundary_input"].initial = self.instance.boundary.geojson if self.instance.boundary else ""
            self.fields["centroid_input"].initial = self.instance.centroid.geojson if self.instance.centroid else ""

    def clean(self):
        cleaned_data = super().clean()
        country = cleaned_data.get("country")
        place = cleaned_data.get("place")

        if place and country and place.country_id != country.id:
            self.add_error("place", "Le lieu sélectionné doit appartenir au même pays que le projet.")

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.boundary = self.cleaned_data.get("boundary_input")
        obj.centroid = self.cleaned_data.get("centroid_input")
        if commit:
            obj.save()
        return obj


class RealEstateProgramForm(BaseModelForm):
    boundary_input = GeoJSONGeometryField(
        label="Limite du programme (GeoJSON MultiPolygon)",
        geom_type="MultiPolygon",
        required=False
    )

    centroid_input = GeoJSONGeometryField(
        label="Centroïde du programme (GeoJSON Point)",
        geom_type="Point",
        required=False
    )

    class Meta:
        model = RealEstateProgram
        fields = [
            "code",
            "name",
            "program_type",
            "status",
            "description",
            "marketing_title",
            "country",
            "place",
            "project",
            "address",
            "total_area_m2",
            "estimated_lot_count",
            "launch_date",
            "closing_date",
            "currency",
            "manager_name",
            "manager_phone",
            "manager_email",
            "metadata",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
            "launch_date": forms.DateInput(attrs={"type": "date"}),
            "closing_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["country"].queryset = Country.objects.order_by("nom")
        self.fields["place"].queryset = Place.objects.select_related("country").order_by("nom")
        self.fields["project"].queryset = ProjetImmobilier.objects.filter(is_active=True).order_by("nom")

        if self.instance.pk:
            self.fields["boundary_input"].initial = self.instance.boundary.geojson if self.instance.boundary else ""
            self.fields["centroid_input"].initial = self.instance.centroid.geojson if self.instance.centroid else ""

    def clean(self):
        cleaned_data = super().clean()

        country = cleaned_data.get("country")
        place = cleaned_data.get("place")
        project = cleaned_data.get("project")
        launch_date = cleaned_data.get("launch_date")
        closing_date = cleaned_data.get("closing_date")

        if place and country and place.country_id != country.id:
            self.add_error("place", "Le lieu doit appartenir au même pays que le programme.")

        if project and country and project.country_id != country.id:
            self.add_error("project", "Le projet doit appartenir au même pays que le programme.")

        if launch_date and closing_date and closing_date < launch_date:
            self.add_error("closing_date", "La date de clôture doit être postérieure ou égale à la date de lancement.")

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.boundary = self.cleaned_data.get("boundary_input")
        obj.centroid = self.cleaned_data.get("centroid_input")
        if commit:
            obj.save()
        return obj


class ProgramPhaseForm(BaseModelForm):
    class Meta:
        model = ProgramPhase
        fields = [
            "program",
            "code",
            "name",
            "order",
            "status",
            "start_date",
            "end_date",
            "description",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = RealEstateProgram.objects.filter(is_active=True).order_by("name")


class ParcelDatasetForm(BaseModelForm):
    class Meta:
        model = ParcelDataset
        fields = [
            "program",
            "phase",
            "name",
            "source_code",
            "source_file_name",
            "geojson_type",
            "crs_name",
            "xy_coordinate_resolution",
            "version",
            "is_current",
            "imported_by",
            "import_notes",
        ]
        widgets = {
            "import_notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        self.fields["phase"].queryset = ProgramPhase.objects.filter(is_active=True).order_by("program__name", "order")


class ProgramBlockForm(BaseModelForm):
    geometry_input = GeoJSONGeometryField(
        label="Géométrie îlot (GeoJSON MultiPolygon)",
        geom_type="MultiPolygon",
        required=False
    )

    class Meta:
        model = ProgramBlock
        fields = [
            "program",
            "phase",
            "code",
            "label",
            "description",
            "block_area_m2",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        self.fields["phase"].queryset = ProgramPhase.objects.filter(is_active=True).order_by("program__name", "order")

        if self.instance.pk:
            self.fields["geometry_input"].initial = self.instance.geometry.geojson if self.instance.geometry else ""

    def clean(self):
        cleaned_data = super().clean()
        program = cleaned_data.get("program")
        phase = cleaned_data.get("phase")

        if program and phase and phase.program_id != program.id:
            self.add_error("phase", "La phase doit appartenir au même programme.")
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.geometry = self.cleaned_data.get("geometry_input")
        if commit:
            obj.save()
        return obj


class ParcelForm(BaseModelForm):
    geometry_input = GeoJSONGeometryField(
        label="Géométrie parcelle (GeoJSON MultiPolygon)",
        geom_type="MultiPolygon",
        required=False
    )

    centroid_input = GeoJSONGeometryField(
        label="Centroïde parcelle (GeoJSON Point)",
        geom_type="Point",
        required=False
    )

    class Meta:
        model = Parcel
        fields = [
            "dataset",
            "program",
            "phase",
            "block",
            "source_fid",
            "lot_number",
            "parcel_code",
            "external_reference",
            "official_area_m2",
            "computed_area_m2",
            "frontage_m",
            "depth_m",
            "slope",
            "elevation",
            "land_use",
            "technical_status",
            "commercial_status",
            "is_corner",
            "is_serviced",
            "has_road_access",
            "has_title_document",
            "title_number",
            "zoning",
            "geometry_valid",
            "has_number",
            "duplicate_flag",
            "notes",
            "metadata",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["dataset"].queryset = ParcelDataset.objects.filter(is_active=True).order_by("-created_at")
        self.fields["program"].queryset = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        self.fields["phase"].queryset = ProgramPhase.objects.filter(is_active=True).order_by("program__name", "order")
        self.fields["block"].queryset = ProgramBlock.objects.filter(is_active=True).order_by("code")
        self.fields["land_use"].queryset = LandUseType.objects.order_by("label")

        if self.instance.pk:
            self.fields["geometry_input"].initial = self.instance.geometry.geojson if self.instance.geometry else ""
            self.fields["centroid_input"].initial = self.instance.centroid.geojson if self.instance.centroid else ""

    def clean(self):
        cleaned_data = super().clean()

        dataset = cleaned_data.get("dataset")
        program = cleaned_data.get("program")
        phase = cleaned_data.get("phase")
        block = cleaned_data.get("block")

        if dataset and program and dataset.program_id != program.id:
            self.add_error("dataset", "Le dataset doit appartenir au même programme.")

        if phase and program and phase.program_id != program.id:
            self.add_error("phase", "La phase doit appartenir au même programme.")

        if block and program and block.program_id != program.id:
            self.add_error("block", "L’îlot doit appartenir au même programme.")

        if phase and dataset and dataset.phase_id and dataset.phase_id != phase.id:
            self.add_error("phase", "La phase sélectionnée ne correspond pas à celle du dataset.")

        if block and phase and block.phase_id and block.phase_id != phase.id:
            self.add_error("block", "L’îlot sélectionné ne correspond pas à la phase.")

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.geometry = self.cleaned_data.get("geometry_input")
        obj.centroid = self.cleaned_data.get("centroid_input")
        if commit:
            obj.save()
        return obj


class PropertyTypeForm(BaseModelForm):
    class Meta:
        model = PropertyType
        fields = ["code", "label"]


class PropertyAssetForm(BaseModelForm):
    class Meta:
        model = PropertyAsset
        fields = [
            "program",
            "phase",
            "parcel",
            "property_type",
            "code",
            "label",
            "built_area_m2",
            "floors",
            "bedrooms",
            "bathrooms",
            "estimated_cost",
            "sale_price",
            "status",
            "description",
            "metadata",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        self.fields["phase"].queryset = ProgramPhase.objects.filter(is_active=True).order_by("program__name", "order")
        self.fields["parcel"].queryset = Parcel.objects.filter(is_active=True).order_by("block__code", "lot_number")
        self.fields["property_type"].queryset = PropertyType.objects.filter(is_active=True).order_by("label")

    def clean(self):
        cleaned_data = super().clean()
        program = cleaned_data.get("program")
        phase = cleaned_data.get("phase")
        parcel = cleaned_data.get("parcel")

        if phase and program and phase.program_id != program.id:
            self.add_error("phase", "La phase doit appartenir au même programme.")

        if parcel and program and parcel.program_id != program.id:
            self.add_error("parcel", "La parcelle doit appartenir au même programme.")

        return cleaned_data


class CustomerForm(BaseModelForm):
    class Meta:
        model = Customer
        fields = [
            "customer_type",
            "first_name",
            "last_name",
            "company_name",
            "phone",
            "email",
            "country",
            "place",
            "address",
            "id_type",
            "id_number",
            "notes",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].queryset = Country.objects.order_by("nom")
        self.fields["place"].queryset = Place.objects.order_by("nom")

    def clean(self):
        cleaned_data = super().clean()
        customer_type = cleaned_data.get("customer_type")
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")
        company_name = cleaned_data.get("company_name")
        country = cleaned_data.get("country")
        place = cleaned_data.get("place")

        if customer_type == "COMPANY" and not company_name:
            self.add_error("company_name", "Le nom de l’entreprise est obligatoire pour un client entreprise.")

        if customer_type == "INDIVIDUAL" and not (first_name or last_name):
            self.add_error("first_name", "Le prénom ou le nom est requis pour un client particulier.")

        if place and country and place.country_id != country.id:
            self.add_error("place", "Le lieu doit appartenir au pays sélectionné.")

        return cleaned_data


class LeadForm(BaseModelForm):
    class Meta:
        model = Lead
        fields = [
            "program",
            "customer",
            "interested_parcel",
            "source",
            "budget_min",
            "budget_max",
            "status",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("company_name", "last_name")
        self.fields["interested_parcel"].queryset = Parcel.objects.filter(is_active=True).order_by("block__code", "lot_number")

    def clean(self):
        cleaned_data = super().clean()
        program = cleaned_data.get("program")
        interested_parcel = cleaned_data.get("interested_parcel")
        budget_min = cleaned_data.get("budget_min")
        budget_max = cleaned_data.get("budget_max")

        if interested_parcel and program and interested_parcel.program_id != program.id:
            self.add_error("interested_parcel", "La parcelle d’intérêt doit appartenir au même programme.")

        if budget_min and budget_max and budget_max < budget_min:
            self.add_error("budget_max", "Le budget maximum doit être supérieur ou égal au budget minimum.")

        return cleaned_data


class ReservationForm(BaseModelForm):
    class Meta:
        model = Reservation
        fields = [
            "reservation_number",
            "program",
            "customer",
            "parcel",
            "lead",
            "reservation_date",
            "expiry_date",
            "reserved_price",
            "deposit_amount",
            "status",
            "notes",
        ]
        widgets = {
            "reservation_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("company_name", "last_name")
        self.fields["parcel"].queryset = Parcel.objects.filter(is_active=True).order_by("block__code", "lot_number")
        self.fields["lead"].queryset = Lead.objects.filter(is_active=True).order_by("-created_at")

    def clean(self):
        cleaned_data = super().clean()
        program = cleaned_data.get("program")
        parcel = cleaned_data.get("parcel")
        lead = cleaned_data.get("lead")
        reservation_date = cleaned_data.get("reservation_date")
        expiry_date = cleaned_data.get("expiry_date")
        deposit_amount = cleaned_data.get("deposit_amount")

        if parcel and program and parcel.program_id != program.id:
            self.add_error("parcel", "Le lot doit appartenir au même programme.")

        if lead and program and lead.program_id != program.id:
            self.add_error("lead", "Le lead doit appartenir au même programme.")

        if expiry_date and reservation_date and expiry_date < reservation_date:
            self.add_error("expiry_date", "La date d’expiration doit être postérieure à la date de réservation.")

        if deposit_amount is not None and deposit_amount < 0:
            self.add_error("deposit_amount", "Le montant de l’acompte ne peut pas être négatif.")

        return cleaned_data


class SaleFileForm(BaseModelForm):
    class Meta:
        model = SaleFile
        fields = [
            "sale_number",
            "program",
            "customer",
            "parcel",
            "reservation",
            "sale_date",
            "agreed_price",
            "discount_amount",
            "net_price",
            "status",
            "sales_agent",
            "notes",
        ]
        widgets = {
            "sale_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("company_name", "last_name")
        self.fields["parcel"].queryset = Parcel.objects.filter(is_active=True).order_by("block__code", "lot_number")
        self.fields["reservation"].queryset = Reservation.objects.filter(is_active=True).order_by("-reservation_date")

    def clean(self):
        cleaned_data = super().clean()
        program = cleaned_data.get("program")
        parcel = cleaned_data.get("parcel")
        reservation = cleaned_data.get("reservation")
        agreed_price = cleaned_data.get("agreed_price")
        discount_amount = cleaned_data.get("discount_amount")
        net_price = cleaned_data.get("net_price")

        if parcel and program and parcel.program_id != program.id:
            self.add_error("parcel", "La parcelle doit appartenir au même programme.")

        if reservation and program and reservation.program_id != program.id:
            self.add_error("reservation", "La réservation doit appartenir au même programme.")

        if discount_amount is not None and discount_amount < 0:
            self.add_error("discount_amount", "La remise ne peut pas être négative.")

        if agreed_price is not None and agreed_price < 0:
            self.add_error("agreed_price", "Le prix convenu ne peut pas être négatif.")

        if net_price is not None and net_price < 0:
            self.add_error("net_price", "Le prix net ne peut pas être négatif.")

        if agreed_price is not None and discount_amount is not None and net_price is not None:
            expected_net = agreed_price - discount_amount
            if net_price != expected_net:
                self.add_error("net_price", f"Le prix net attendu est {expected_net}.")

        return cleaned_data


class PaymentScheduleForm(BaseModelForm):
    class Meta:
        model = PaymentSchedule
        fields = [
            "sale_file",
            "name",
            "total_amount",
            "start_date",
            "end_date",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        total_amount = cleaned_data.get("total_amount")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La date de fin doit être postérieure ou égale à la date de début.")

        if total_amount is not None and total_amount < 0:
            self.add_error("total_amount", "Le montant total ne peut pas être négatif.")

        return cleaned_data


class PaymentInstallmentForm(BaseModelForm):
    class Meta:
        model = PaymentInstallment
        fields = [
            "schedule",
            "label",
            "due_date",
            "amount_due",
            "amount_paid",
            "balance",
            "order",
            "status",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        amount_due = cleaned_data.get("amount_due")
        amount_paid = cleaned_data.get("amount_paid")
        balance = cleaned_data.get("balance")

        for field_name, value in {
            "amount_due": amount_due,
            "amount_paid": amount_paid,
            "balance": balance,
        }.items():
            if value is not None and value < 0:
                self.add_error(field_name, "Cette valeur ne peut pas être négative.")

        return cleaned_data


class PaymentForm(BaseModelForm):
    class Meta:
        model = Payment
        fields = [
            "payment_number",
            "sale_file",
            "installment",
            "payment_date",
            "amount",
            "payment_method",
            "reference",
            "status",
            "received_by",
            "notes",
        ]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sale_file"].queryset = SaleFile.objects.filter(is_active=True).order_by("-created_at")
        self.fields["installment"].queryset = PaymentInstallment.objects.filter(is_active=True).order_by("schedule", "order")

    def clean(self):
        cleaned_data = super().clean()
        sale_file = cleaned_data.get("sale_file")
        installment = cleaned_data.get("installment")
        amount = cleaned_data.get("amount")

        if installment and sale_file and installment.schedule.sale_file_id != sale_file.id:
            self.add_error("installment", "L’échéance sélectionnée doit appartenir au même dossier de vente.")

        if amount is not None and amount <= 0:
            self.add_error("amount", "Le montant du paiement doit être supérieur à zéro.")

        return cleaned_data


class ProgramDocumentForm(BaseModelForm):
    class Meta:
        model = ProgramDocument
        fields = [
            "program",
            "title",
            "document_type",
            "description",
            "file",
            "issued_at",
            "expires_at",
            "uploaded_by",
            "is_confidential",
            "metadata",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "expires_at": forms.DateInput(attrs={"type": "date"}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }


class ParcelDocumentForm(BaseModelForm):
    class Meta:
        model = ParcelDocument
        fields = [
            "parcel",
            "title",
            "document_type",
            "description",
            "file",
            "issued_at",
            "expires_at",
            "uploaded_by",
            "is_confidential",
            "metadata",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "expires_at": forms.DateInput(attrs={"type": "date"}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }


class CustomerDocumentForm(BaseModelForm):
    class Meta:
        model = CustomerDocument
        fields = [
            "customer",
            "title",
            "document_type",
            "description",
            "file",
            "issued_at",
            "expires_at",
            "uploaded_by",
            "is_confidential",
            "metadata",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "expires_at": forms.DateInput(attrs={"type": "date"}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }


class ConstructionProjectForm(BaseModelForm):
    class Meta:
        model = ConstructionProject
        fields = [
            "parcel",
            "asset",
            "code",
            "title",
            "description",
            "status",
            "planned_start_date",
            "actual_start_date",
            "planned_end_date",
            "actual_end_date",
            "progress_percent",
            "estimated_budget",
            "actual_cost",
            "contractor_name",
            "site_manager",
            "metadata",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "planned_start_date": forms.DateInput(attrs={"type": "date"}),
            "actual_start_date": forms.DateInput(attrs={"type": "date"}),
            "planned_end_date": forms.DateInput(attrs={"type": "date"}),
            "actual_end_date": forms.DateInput(attrs={"type": "date"}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parcel"].queryset = Parcel.objects.filter(is_active=True).order_by("block__code", "lot_number")
        self.fields["asset"].queryset = PropertyAsset.objects.filter(is_active=True).order_by("code")


class ConstructionUpdateForm(BaseModelForm):
    class Meta:
        model = ConstructionUpdate
        fields = [
            "construction_project",
            "asset",
            "report_date",
            "stage",
            "progress_percent",
            "summary",
            "details",
            "issues",
            "next_actions",
            "weather_notes",
            "recorded_by",
        ]
        widgets = {
            "report_date": forms.DateInput(attrs={"type": "date"}),
            "details": forms.Textarea(attrs={"rows": 4}),
            "issues": forms.Textarea(attrs={"rows": 3}),
            "next_actions": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["construction_project"].queryset = ConstructionProject.objects.filter(is_active=True).order_by("-created_at")
        self.fields["asset"].queryset = PropertyAsset.objects.filter(is_active=True).order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        construction_project = cleaned_data.get("construction_project")
        asset = cleaned_data.get("asset")

        if asset and construction_project and construction_project.asset_id and construction_project.asset_id != asset.id:
            self.add_error("asset", "L’actif doit correspondre au chantier sélectionné.")

        return cleaned_data


class ConstructionPhotoForm(BaseModelForm):
    class Meta:
        model = ConstructionPhoto
        fields = [
            "construction_project",
            "update",
            "asset",
            "title",
            "image",
            "caption",
            "shot_date",
            "view_type",
            "is_cover",
            "sort_order",
            "uploaded_by",
            "metadata",
        ]
        widgets = {
            "caption": forms.Textarea(attrs={"rows": 3}),
            "shot_date": forms.DateInput(attrs={"type": "date"}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["construction_project"].queryset = ConstructionProject.objects.filter(is_active=True).order_by("-created_at")
        self.fields["update"].queryset = ConstructionUpdate.objects.filter(is_active=True).order_by("-report_date")
        self.fields["asset"].queryset = PropertyAsset.objects.filter(is_active=True).order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        construction_project = cleaned_data.get("construction_project")
        update = cleaned_data.get("update")
        asset = cleaned_data.get("asset")

        if update and construction_project and update.construction_project_id != construction_project.id:
            self.add_error("update", "Le rapport sélectionné doit appartenir au même chantier.")

        if asset and construction_project and construction_project.asset_id and construction_project.asset_id != asset.id:
            self.add_error("asset", "L’actif sélectionné ne correspond pas au chantier.")

        return cleaned_data


class ConstructionMediaForm(BaseModelForm):
    class Meta:
        model = ConstructionMedia
        fields = [
            "construction_project",
            "update",
            "media_type",
            "file",
            "title",
            "caption",
            "shot_date",
            "sort_order",
            "metadata",
        ]
        widgets = {
            "caption": forms.Textarea(attrs={"rows": 3}),
            "shot_date": forms.DateInput(attrs={"type": "date"}),
            "metadata": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["construction_project"].queryset = ConstructionProject.objects.filter(is_active=True).order_by("-created_at")
        self.fields["update"].queryset = ConstructionUpdate.objects.filter(is_active=True).order_by("-report_date")

    def clean(self):
        cleaned_data = super().clean()
        construction_project = cleaned_data.get("construction_project")
        update = cleaned_data.get("update")

        if update and construction_project and update.construction_project_id != construction_project.id:
            self.add_error("update", "La mise à jour doit appartenir au même chantier.")

        return cleaned_data