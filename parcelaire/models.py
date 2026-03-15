from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Country(TimeStampedModel):
    nom = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


PLACE_TYPE_CHOICES = [
    ("REGION", "REGION"),
    ("VILLE", "VILLE"),
    ("DISTRICT", "DISTRICT"),
    ("COMMUNE", "COMMUNE"),
    ("QUARTIER", "QUARTIER"),
]


class Place(TimeStampedModel):
    nom = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True, null=True)
    type = models.CharField(max_length=20, choices=PLACE_TYPE_CHOICES)

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="places")
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.CASCADE)
    geometry = gis_models.MultiPolygonField(srid=4326, blank=True, null=True)
    centroid = gis_models.PointField(srid=4326, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["nom"]
        unique_together = ("country", "type", "nom", "parent")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nom

    def clean(self):
        super().clean()

        # Empêcher qu'un lieu soit son propre parent
        if self.parent and self.parent_id == self.id:
            raise ValidationError({
                "parent": "Un lieu ne peut pas être son propre parent."
            })

        # Le parent doit être dans le même pays
        if self.parent and self.parent.country_id != self.country_id:
            raise ValidationError({
                "parent": "Le parent doit appartenir au même pays."
            })

        # Hiérarchie autorisée
        allowed_parents = {
            "REGION": [],
            "DISTRICT": ["REGION"],
            "VILLE": ["DISTRICT", "REGION"],
            "COMMUNE": ["VILLE", "DISTRICT"],
            "QUARTIER": ["COMMUNE", "VILLE"],
        }

        if self.parent:
            allowed = allowed_parents.get(self.type, [])
            if self.parent.type not in allowed:
                raise ValidationError({
                    "parent": (
                        f"Un lieu de type '{self.type}' ne peut pas avoir pour parent "
                        f"un lieu de type '{self.parent.type}'. "
                        f"Parents autorisés : {', '.join(allowed) if allowed else 'aucun'}."
                    )
                })
        else:
            # Types qui doivent obligatoirement avoir un parent
            types_requiring_parent = {"DISTRICT", "VILLE", "COMMUNE", "QUARTIER"}
            if self.type in types_requiring_parent:
                raise ValidationError({
                    "parent": f"Un lieu de type '{self.type}' doit avoir un parent."
                })

        # Empêcher les boucles de hiérarchie
        ancestor = self.parent
        while ancestor:
            if ancestor.pk == self.pk and self.pk is not None:
                raise ValidationError({
                    "parent": "Boucle hiérarchique détectée."
                })
            ancestor = ancestor.parent


class ProjetImmobilier(TimeStampedModel, SoftDeleteModel):
    code = models.CharField(max_length=100, unique=True)
    nom = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="projects"
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects"
    )

    address = models.TextField(blank=True, null=True)
    boundary = gis_models.MultiPolygonField(srid=4326, blank=True, null=True)
    centroid = gis_models.PointField(srid=4326, blank=True, null=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
        self.full_clean()
        super().save(*args, **kwargs)


class RealEstateProgram(TimeStampedModel, SoftDeleteModel):
    PROGRAM_TYPE_CHOICES = [
        ("LOTISSEMENT", "Lotissement"),
        ("RESIDENTIEL", "Résidentiel"),
        ("MIXTE", "Mixte"),
        ("SOCIAL", "Habitat social"),
        ("COMMERCIAL", "Commercial"),
        ("INDUSTRIEL", "Industriel"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Brouillon"),
        ("PLANNED", "Planifié"),
        ("MARKETING", "Commercialisation"),
        ("ACTIVE", "Actif"),
        ("SUSPENDED", "Suspendu"),
        ("CLOSED", "Clôturé"),
    ]

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    program_type = models.CharField(max_length=30, choices=PROGRAM_TYPE_CHOICES, default="LOTISSEMENT")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    description = models.TextField(blank=True, null=True)
    marketing_title = models.CharField(max_length=255, blank=True, null=True)

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="real_estate_programs"
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="real_estate_programs"
    )
    project = models.ForeignKey(
        ProjetImmobilier,
        on_delete=models.CASCADE,
        related_name="programs"
    )

    address = models.TextField(blank=True, null=True)

    total_area_m2 = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)
    estimated_lot_count = models.PositiveIntegerField(default=0)

    launch_date = models.DateField(blank=True, null=True)
    closing_date = models.DateField(blank=True, null=True)

    currency = models.CharField(max_length=10, default="XOF")

    manager_name = models.CharField(max_length=255, blank=True, null=True)
    manager_phone = models.CharField(max_length=50, blank=True, null=True)
    manager_email = models.EmailField(blank=True, null=True)

    boundary = gis_models.MultiPolygonField(srid=4326, blank=True, null=True)
    centroid = gis_models.PointField(srid=4326, blank=True, null=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        if self.place and self.place.country_id != self.country_id:
            raise ValidationError({
                "place": "Le lieu doit appartenir au même pays que le programme."
            })

        if self.launch_date and self.closing_date and self.closing_date < self.launch_date:
            raise ValidationError({
                "closing_date": "La date de clôture doit être postérieure ou égale à la date de lancement."
            })

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        self.full_clean()
        super().save(*args, **kwargs)

    def get_ancestors(self):
        ancestors = []
        current = self.place
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    @property
    def quartier(self):
        for place in self.get_ancestors():
            if place.type == "QUARTIER":
                return place
        return None

    @property
    def commune(self):
        for place in self.get_ancestors():
            if place.type == "COMMUNE":
                return place
        return None

    @property
    def district(self):
        for place in self.get_ancestors():
            if place.type == "DISTRICT":
                return place
        return None

    @property
    def ville(self):
        for place in self.get_ancestors():
            if place.type == "VILLE":
                return place
        return None


class ProgramPhase(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("PLANNED", "Planifiée"),
        ("OPEN", "Ouverte"),
        ("CLOSED", "Clôturée"),
        ("SUSPENDED", "Suspendue"),
    ]

    program = models.ForeignKey(
        RealEstateProgram,
        on_delete=models.CASCADE,
        related_name="phases"
    )
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PLANNED")

    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("program", "code")
        ordering = ["program", "order", "name"]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                "end_date": "La date de fin doit être postérieure ou égale à la date de début."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.program.name} - {self.name}"


class LandUseType(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return self.label


class ParcelDataset(TimeStampedModel, SoftDeleteModel):
    program = models.ForeignKey(
        RealEstateProgram,
        on_delete=models.CASCADE,
        related_name="parcel_datasets"
    )
    phase = models.ForeignKey(
        ProgramPhase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcel_datasets"
    )

    name = models.CharField(max_length=255)
    source_code = models.CharField(max_length=255, blank=True, null=True)
    source_file_name = models.CharField(max_length=255, blank=True, null=True)

    geojson_type = models.CharField(max_length=50, default="FeatureCollection")
    crs_name = models.CharField(max_length=255, blank=True, null=True)
    xy_coordinate_resolution = models.FloatField(blank=True, null=True)

    version = models.CharField(max_length=50, default="1.0")
    is_current = models.BooleanField(default=True)

    imported_by = models.CharField(max_length=255, blank=True, null=True)
    import_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.phase and self.phase.program_id != self.program_id:
            raise ValidationError({
                "phase": "La phase doit appartenir au même programme."
            })

    def __str__(self):
        return self.name


class ProgramBlock(TimeStampedModel, SoftDeleteModel):
    program = models.ForeignKey(
        RealEstateProgram,
        on_delete=models.CASCADE,
        related_name="blocks"
    )
    phase = models.ForeignKey(
        ProgramPhase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocks"
    )

    code = models.CharField(max_length=50)
    label = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    block_area_m2 = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)
    geometry = gis_models.MultiPolygonField(srid=4326, blank=True, null=True)

    class Meta:
        unique_together = ("program", "code")
        ordering = ["code"]

    def clean(self):
        super().clean()
        if self.phase and self.phase.program_id != self.program_id:
            raise ValidationError({
                "phase": "La phase doit appartenir au même programme."
            })

    def __str__(self):
        return f"Îlot {self.code}"


class Parcel(TimeStampedModel, SoftDeleteModel):
    TECHNICAL_STATUS_CHOICES = [
        ("RAW", "Brut importé"),
        ("VALIDATED", "Validé"),
        ("REVIEW", "À vérifier"),
        ("REJECTED", "Rejeté"),
    ]

    COMMERCIAL_STATUS_CHOICES = [
        ("AVAILABLE", "Disponible"),
        ("OPTIONED", "En option"),
        ("RESERVED", "Réservé"),
        ("SOLD", "Vendu"),
        ("BLOCKED", "Bloqué"),
        ("LITIGATION", "Litige"),
        ("ARCHIVED", "Archivé"),
    ]

    dataset = models.ForeignKey(
        ParcelDataset,
        on_delete=models.CASCADE,
        related_name="parcels"
    )
    program = models.ForeignKey(
        RealEstateProgram,
        on_delete=models.CASCADE,
        related_name="parcels"
    )
    phase = models.ForeignKey(
        ProgramPhase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcels"
    )
    block = models.ForeignKey(
        ProgramBlock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcels"
    )

    source_fid = models.IntegerField(blank=True, null=True, db_index=True)

    lot_number = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    parcel_code = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    external_reference = models.CharField(max_length=150, blank=True, null=True, db_index=True)

    official_area_m2 = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)
    computed_area_m2 = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)

    frontage_m = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    depth_m = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    slope = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    elevation = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    land_use = models.ForeignKey(
        LandUseType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcels"
    )

    technical_status = models.CharField(max_length=20, choices=TECHNICAL_STATUS_CHOICES, default="RAW")
    commercial_status = models.CharField(max_length=20, choices=COMMERCIAL_STATUS_CHOICES, default="AVAILABLE")

    is_corner = models.BooleanField(default=False)
    is_serviced = models.BooleanField(default=False)
    has_road_access = models.BooleanField(default=True)
    has_title_document = models.BooleanField(default=False)

    title_number = models.CharField(max_length=150, blank=True, null=True)
    zoning = models.CharField(max_length=150, blank=True, null=True)

    geometry = gis_models.MultiPolygonField(srid=4326, blank=True, null=True)
    centroid = gis_models.PointField(srid=4326, blank=True, null=True)

    geometry_valid = models.BooleanField(default=True)
    has_number = models.BooleanField(default=True)
    duplicate_flag = models.BooleanField(default=False)

    notes = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    crm_last_synced_at = models.DateTimeField(blank=True, null=True)
    valeur_hypothecaire = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["block__code", "lot_number"]
        indexes = [
            models.Index(fields=["program", "lot_number"]),
            models.Index(fields=["program", "source_fid"]),
            models.Index(fields=["block", "lot_number"]),
            models.Index(fields=["commercial_status"]),
        ]
        permissions = [
            ("view_financial_data", "Peut voir les données financières"),
            ("view_patient_data", "Peut voir les données patient/client"),
            ("view_construction_data", "Peut voir les données de construction"),
            ("view_parcellaire", "Peut voir le parcellaire"),
        ]

    def clean(self):
        super().clean()

        if self.dataset and self.dataset.program_id != self.program_id:
            raise ValidationError({"dataset": "Le dataset doit appartenir au même programme."})

        if self.phase and self.phase.program_id != self.program_id:
            raise ValidationError({"phase": "La phase doit appartenir au même programme."})

        if self.block and self.block.program_id != self.program_id:
            raise ValidationError({"block": "L’îlot doit appartenir au même programme."})

        if self.phase and self.dataset and self.dataset.phase and self.dataset.phase_id != self.phase_id:
            raise ValidationError({"phase": "La phase est incohérente avec celle du dataset."})

        if self.block and self.phase and self.block.phase_id and self.block.phase_id != self.phase_id:
            raise ValidationError({"block": "L’îlot ne correspond pas à la phase sélectionnée."})

        numeric_fields = {
            "official_area_m2": self.official_area_m2,
            "computed_area_m2": self.computed_area_m2,
            "frontage_m": self.frontage_m,
            "depth_m": self.depth_m,
        }
        for field, value in numeric_fields.items():
            if value is not None and value < 0:
                raise ValidationError({field: "La valeur ne peut pas être négative."})

    def __str__(self):
        return f"Lot {self.lot_number or 'N/A'}"


class ParcelGeometryHistory(TimeStampedModel):
    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.CASCADE,
        related_name="geometry_history"
    )
    geometry = gis_models.MultiPolygonField(srid=4326, blank=True, null=True)
    reason = models.CharField(max_length=255, blank=True, null=True)
    changed_by = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Historique géométrie {self.parcel}"


class PropertyType(TimeStampedModel, SoftDeleteModel):
    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=150)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return self.label


class Customer(TimeStampedModel, SoftDeleteModel):
    CUSTOMER_TYPE_CHOICES = [
        ("INDIVIDUAL", "Particulier"),
        ("COMPANY", "Entreprise"),
        ("INSTITUTION", "Institution"),
    ]

    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default="INDIVIDUAL")
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)

    phone = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    email = models.EmailField(blank=True, null=True, db_index=True)

    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")
    place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")

    address = models.TextField(blank=True, null=True)
    id_type = models.CharField(max_length=100, blank=True, null=True)
    id_number = models.CharField(max_length=150, blank=True, null=True)

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.customer_type == "COMPANY":
            return self.company_name or "Entreprise"
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or "Client"


class Lead(TimeStampedModel, SoftDeleteModel):
    LEAD_STATUS_CHOICES = [
        ("NEW", "Nouveau"),
        ("QUALIFIED", "Qualifié"),
        ("VISIT_PLANNED", "Visite planifiée"),
        ("NEGOTIATION", "Négociation"),
        ("CONVERTED", "Converti"),
        ("LOST", "Perdu"),
    ]

    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="leads")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="leads")
    interested_parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="leads")

    source = models.CharField(max_length=100, blank=True, null=True)
    budget_min = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)
    budget_max = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=LEAD_STATUS_CHOICES, default="NEW")
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Lead {self.customer}"


class Reservation(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("DRAFT", "Brouillon"),
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expirée"),
        ("CANCELLED", "Annulée"),
        ("CONVERTED", "Convertie"),
    ]

    reservation_number = models.CharField(max_length=100, unique=True)
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="reservations")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="reservations")
    parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations")
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations")

    reservation_date = models.DateField()
    expiry_date = models.DateField(blank=True, null=True)
    reserved_price = models.DecimalField(max_digits=16, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    notes = models.TextField(blank=True, null=True)

    def clean(self):
        super().clean()
        if self.parcel and self.parcel.program_id != self.program_id:
            raise ValidationError({"parcel": "Le lot doit appartenir au même programme."})
        if self.expiry_date and self.expiry_date < self.reservation_date:
            raise ValidationError(
                {"expiry_date": "La date d’expiration doit être postérieure à la date de réservation."})


class SaleFile(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("OPEN", "Ouvert"),
        ("PENDING_DOCS", "Documents en attente"),
        ("PENDING_PAYMENT", "Paiement en attente"),
        ("SIGNED", "Signé"),
        ("COMPLETED", "Finalisé"),
        ("CANCELLED", "Annulé"),
    ]

    sale_number = models.CharField(max_length=100, unique=True)
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="sales")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="sales")
    parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales")
    reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales")

    sale_date = models.DateField(blank=True, null=True)
    agreed_price = models.DecimalField(max_digits=16, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    net_price = models.DecimalField(max_digits=16, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    sales_agent = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)


class PaymentSchedule(TimeStampedModel, SoftDeleteModel):
    sale_file = models.OneToOneField(SaleFile, on_delete=models.CASCADE, related_name="payment_schedule")
    name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=16, decimal_places=2)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name


class PaymentInstallment(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("PENDING", "En attente"),
        ("PARTIAL", "Partiellement payé"),
        ("PAID", "Payé"),
        ("OVERDUE", "En retard"),
        ("CANCELLED", "Annulé"),
    ]

    schedule = models.ForeignKey(PaymentSchedule, on_delete=models.CASCADE, related_name="installments")
    label = models.CharField(max_length=255)
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=16, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")


class Payment(TimeStampedModel, SoftDeleteModel):
    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Espèces"),
        ("BANK", "Virement bancaire"),
        ("CHEQUE", "Chèque"),
        ("MOBILE_MONEY", "Mobile Money"),
        ("CARD", "Carte"),
        ("OTHER", "Autre"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "En attente"),
        ("CONFIRMED", "Confirmé"),
        ("REJECTED", "Rejeté"),
        ("CANCELLED", "Annulé"),
    ]

    payment_number = models.CharField(max_length=100, unique=True)
    sale_file = models.ForeignKey(SaleFile, on_delete=models.CASCADE, related_name="payments")
    installment = models.ForeignKey(
        PaymentInstallment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments"
    )

    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference = models.CharField(max_length=255, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    received_by = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.payment_number


class PropertyAsset(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("PLANNED", "Planifié"),
        ("DESIGNED", "Conçu"),
        ("UNDER_CONSTRUCTION", "En construction"),
        ("COMPLETED", "Achevé"),
        ("AVAILABLE", "Disponible"),
        ("RESERVED", "Réservé"),
        ("SOLD", "Vendu"),
        ("BLOCKED", "Bloqué"),
    ]

    program = models.ForeignKey(
        RealEstateProgram,
        on_delete=models.CASCADE,
        related_name="assets"
    )
    phase = models.ForeignKey(
        ProgramPhase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets"
    )
    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets"
    )
    property_type = models.ForeignKey(
        PropertyType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets"
    )

    code = models.CharField(max_length=100)
    label = models.CharField(max_length=255)

    built_area_m2 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    floors = models.PositiveIntegerField(default=0)
    bedrooms = models.PositiveIntegerField(default=0)
    bathrooms = models.PositiveIntegerField(default=0)

    estimated_cost = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)
    sale_price = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="PLANNED")

    description = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("program", "code")
        ordering = ["code"]

    def clean(self):
        super().clean()

        if self.phase and self.phase.program_id != self.program_id:
            raise ValidationError({"phase": "La phase doit appartenir au même programme."})

        if self.parcel and self.parcel.program_id != self.program_id:
            raise ValidationError({"parcel": "La parcelle doit appartenir au même programme."})

    def __str__(self):
        return self.label


class DocumentBase(TimeStampedModel, SoftDeleteModel):
    DOCUMENT_TYPE_CHOICES = [
        ("BROCHURE", "Brochure"),
        ("MASTER_PLAN", "Plan de masse"),
        ("TITLE_DEED", "Titre foncier"),
        ("ADMINISTRATIVE", "Document administratif"),
        ("CONTRACT", "Contrat"),
        ("PAYMENT_PROOF", "Preuve de paiement"),
        ("IDENTITY", "Pièce d'identité"),
        ("PHOTO", "Photo"),
        ("PLAN", "Plan"),
        ("OTHER", "Autre"),
    ]

    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="OTHER")
    description = models.TextField(blank=True, null=True)

    file = models.FileField(upload_to="documents/%Y/%m/")
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.PositiveBigIntegerField(blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)

    issued_at = models.DateField(blank=True, null=True)
    expires_at = models.DateField(blank=True, null=True)

    uploaded_by = models.CharField(max_length=255, blank=True, null=True)
    is_confidential = models.BooleanField(default=False)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.expires_at and self.issued_at and self.expires_at < self.issued_at:
            raise ValidationError({
                "expires_at": "La date d'expiration doit être postérieure ou égale à la date d'émission."
            })


class ProgramDocument(DocumentBase):
    program = models.ForeignKey(
        RealEstateProgram,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document programme"
        verbose_name_plural = "Documents programmes"

    def __str__(self):
        return f"{self.program.name} - {self.title}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ParcelDocument(DocumentBase):
    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document parcelle"
        verbose_name_plural = "Documents parcelles"

    def __str__(self):
        return f"{self.parcel} - {self.title}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CustomerDocument(DocumentBase):
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.CASCADE,
        related_name="documents"
    )

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document client"
        verbose_name_plural = "Documents clients"

    def __str__(self):
        return f"{self.customer} - {self.title}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ConstructionProject(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("PLANNED", "Planifié"),
        ("NOT_STARTED", "Non démarré"),
        ("IN_PROGRESS", "En cours"),
        ("ON_HOLD", "Suspendu"),
        ("COMPLETED", "Achevé"),
        ("CANCELLED", "Annulé"),
    ]

    parcel = models.ForeignKey(
        Parcel,
        on_delete=models.CASCADE,
        related_name="construction_projects"
    )
    asset = models.ForeignKey(
        PropertyAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="construction_projects"
    )

    code = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PLANNED")

    planned_start_date = models.DateField(blank=True, null=True)
    actual_start_date = models.DateField(blank=True, null=True)
    planned_end_date = models.DateField(blank=True, null=True)
    actual_end_date = models.DateField(blank=True, null=True)

    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    estimated_budget = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)
    actual_cost = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)

    contractor_name = models.CharField(max_length=255, blank=True, null=True)
    site_manager = models.CharField(max_length=255, blank=True, null=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()

        if self.asset and self.asset.parcel_id and self.asset.parcel_id != self.parcel_id:
            raise ValidationError({
                "asset": "L'actif sélectionné doit appartenir à la même parcelle."
            })

        if self.progress_percent is not None and (self.progress_percent < 0 or self.progress_percent > 100):
            raise ValidationError({
                "progress_percent": "Le pourcentage d'avancement doit être compris entre 0 et 100."
            })

        if self.planned_start_date and self.planned_end_date and self.planned_end_date < self.planned_start_date:
            raise ValidationError({
                "planned_end_date": "La date de fin prévisionnelle doit être postérieure à la date de début prévisionnelle."
            })

        if self.actual_start_date and self.actual_end_date and self.actual_end_date < self.actual_start_date:
            raise ValidationError({
                "actual_end_date": "La date de fin réelle doit être postérieure à la date de début réelle."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class ConstructionUpdate(TimeStampedModel, SoftDeleteModel):
    STAGE_CHOICES = [
        ("SITE_INSTALLATION", "Installation chantier"),
        ("FOUNDATION", "Fondations"),
        ("BASEMENT", "Soubassement"),
        ("WALLS", "Élévation murs"),
        ("SLAB", "Dalle"),
        ("ROOF", "Toiture"),
        ("PLUMBING", "Plomberie"),
        ("ELECTRICITY", "Électricité"),
        ("PLASTERING", "Enduits"),
        ("PAINTING", "Peinture"),
        ("FINISHING", "Finitions"),
        ("DELIVERY", "Livraison"),
        ("OTHER", "Autre"),
    ]

    construction_project = models.ForeignKey(
        ConstructionProject,
        on_delete=models.CASCADE,
        related_name="updates"
    )

    report_date = models.DateField()
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default="OTHER")

    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    summary = models.CharField(max_length=255)
    details = models.TextField(blank=True, null=True)

    issues = models.TextField(blank=True, null=True)
    next_actions = models.TextField(blank=True, null=True)

    weather_notes = models.CharField(max_length=255, blank=True, null=True)
    recorded_by = models.CharField(max_length=255, blank=True, null=True)
    asset = models.ForeignKey(
        PropertyAsset,
        on_delete=models.CASCADE,
        related_name="updates",
        null=True,
        blank=True
    )
    class Meta:
        ordering = ["-report_date", "-created_at"]

    def clean(self):
        super().clean()
        if self.progress_percent is not None and (self.progress_percent < 0 or self.progress_percent > 100):
            raise ValidationError({
                "progress_percent": "Le pourcentage d'avancement doit être compris entre 0 et 100."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.construction_project} - {self.report_date}"

class ConstructionPhoto(TimeStampedModel, SoftDeleteModel):
    VIEW_CHOICES = [
        ("FRONT", "Façade"),
        ("BACK", "Arrière"),
        ("LEFT", "Côté gauche"),
        ("RIGHT", "Côté droit"),
        ("INTERIOR", "Intérieur"),
        ("AERIAL", "Vue aérienne"),
        ("DETAIL", "Détail"),
        ("OTHER", "Autre"),
    ]

    construction_project = models.ForeignKey(
        ConstructionProject,
        on_delete=models.CASCADE,
        related_name="photos"
    )
    update = models.ForeignKey(
        ConstructionUpdate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="photos"
    )

    title = models.CharField(max_length=255, blank=True, null=True)
    image = models.ImageField(upload_to="construction_progress/%Y/%m/")
    caption = models.TextField(blank=True, null=True)

    shot_date = models.DateField(blank=True, null=True)
    view_type = models.CharField(max_length=20, choices=VIEW_CHOICES, default="OTHER")

    is_cover = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    original_filename = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.PositiveBigIntegerField(blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)

    uploaded_by = models.CharField(max_length=255, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    asset = models.ForeignKey(
        PropertyAsset,
        on_delete=models.CASCADE,
        related_name="photos",
        null=True,
        blank=True
    )
    class Meta:
        ordering = ["sort_order", "-shot_date", "-created_at"]

    def clean(self):
        super().clean()

        if self.update and self.update.construction_project_id != self.construction_project_id:
            raise ValidationError({
                "update": "Le rapport sélectionné doit appartenir au même chantier."
            })

    def save(self, *args, **kwargs):
        if self.image:
            self.original_filename = self.original_filename or self.image.name.split("/")[-1]
            self.file_size = getattr(self.image, "size", None)
            self.mime_type = self.mime_type or getattr(self.image.file, "content_type", None)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or f"Photo {self.pk}"

class ConstructionMedia(TimeStampedModel, SoftDeleteModel):
    MEDIA_TYPE_CHOICES = [
        ("IMAGE", "Image"),
        ("VIDEO", "Vidéo"),
    ]

    construction_project = models.ForeignKey(
        ConstructionProject,
        on_delete=models.CASCADE,
        related_name="media"
    )
    update = models.ForeignKey(
        ConstructionUpdate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media"
    )

    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default="IMAGE")
    file = models.FileField(upload_to="construction_media/%Y/%m/")
    title = models.CharField(max_length=255, blank=True, null=True)
    caption = models.TextField(blank=True, null=True)
    shot_date = models.DateField(blank=True, null=True)

    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)