from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.contrib.gis.db import models as gis_models
from django.utils.text import slugify


# =========================================================
# BASES ABSTRAITES
# =========================================================

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        abstract = True


# =========================================================
# RÉFÉRENTIEL GÉOGRAPHIQUE
# =========================================================

class Country(TimeStampedModel):
    nom = models.CharField(max_length=255, unique=True, verbose_name="Nom")
    code = models.CharField(max_length=10, unique=True, blank=True, null=True, verbose_name="Code")

    class Meta:
        ordering = ["nom"]
        verbose_name = "Pays"
        verbose_name_plural = "Pays"

    def __str__(self):
        return self.nom


PLACE_TYPE_CHOICES = [
    ("REGION", "Région"),
    ("VILLE", "Ville"),
    ("DISTRICT", "District"),
    ("COMMUNE", "Commune"),
    ("QUARTIER", "Quartier"),
]


class Place(TimeStampedModel):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    code = models.CharField(max_length=50, blank=True, null=True, verbose_name="Code")
    type = models.CharField(max_length=20, choices=PLACE_TYPE_CHOICES, verbose_name="Type")

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="places",
        verbose_name="Pays"
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
        verbose_name="Parent"
    )
    geometry = gis_models.MultiPolygonField(srid=4326, blank=True, null=True, verbose_name="Géométrie")
    centroid = gis_models.PointField(srid=4326, blank=True, null=True, verbose_name="Centroïde")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    class Meta:
        ordering = ["nom"]
        unique_together = ("country", "type", "nom", "parent")
        verbose_name = "Lieu"
        verbose_name_plural = "Lieux"

    def __str__(self):
        return self.nom

    def clean(self):
        super().clean()

        if self.parent and self.parent_id == self.id:
            raise ValidationError({"parent": "Un lieu ne peut pas être son propre parent."})

        if self.parent and self.parent.country_id != self.country_id:
            raise ValidationError({"parent": "Le parent doit appartenir au même pays."})

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
                        f"Un lieu de type '{self.get_type_display()}' ne peut pas avoir pour parent "
                        f"un lieu de type '{self.parent.get_type_display()}'."
                    )
                })
        else:
            types_requiring_parent = {"DISTRICT", "VILLE", "COMMUNE", "QUARTIER"}
            if self.type in types_requiring_parent:
                raise ValidationError({
                    "parent": f"Un lieu de type '{self.get_type_display()}' doit avoir un parent."
                })

        ancestor = self.parent
        while ancestor:
            if ancestor.pk == self.pk and self.pk is not None:
                raise ValidationError({"parent": "Boucle hiérarchique détectée."})
            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# =========================================================
# PROJETS / PROGRAMMES
# =========================================================

class ProjetImmobilier(TimeStampedModel, SoftDeleteModel):
    code = models.CharField(max_length=100, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=255, verbose_name="Nom")
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True, verbose_name="Slug")

    description = models.TextField(blank=True, null=True, verbose_name="Description")

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="projects",
        verbose_name="Pays"
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
        verbose_name="Lieu"
    )

    address = models.TextField(blank=True, null=True, verbose_name="Adresse")
    boundary = gis_models.MultiPolygonField(srid=4326, blank=True, null=True, verbose_name="Périmètre")
    centroid = gis_models.PointField(srid=4326, blank=True, null=True, verbose_name="Centroïde")

    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    class Meta:
        ordering = ["nom"]
        verbose_name = "Projet immobilier"
        verbose_name_plural = "Projets immobiliers"

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

    code = models.CharField(max_length=100, unique=True, verbose_name="Code")
    name = models.CharField(max_length=255, verbose_name="Nom")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="Slug")

    program_type = models.CharField(max_length=30, choices=PROGRAM_TYPE_CHOICES, default="LOTISSEMENT", verbose_name="Type de programme")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT", verbose_name="Statut")

    description = models.TextField(blank=True, null=True, verbose_name="Description")
    marketing_title = models.CharField(max_length=255, blank=True, null=True, verbose_name="Titre marketing")

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="real_estate_programs",
        verbose_name="Pays"
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="real_estate_programs",
        verbose_name="Lieu"
    )
    project = models.ForeignKey(
        ProjetImmobilier,
        on_delete=models.CASCADE,
        related_name="programs",
        verbose_name="Projet immobilier"
    )

    address = models.TextField(blank=True, null=True, verbose_name="Adresse")
    total_area_m2 = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Superficie totale (m²)")
    estimated_lot_count = models.PositiveIntegerField(default=0, verbose_name="Nombre estimé de lots")

    launch_date = models.DateField(blank=True, null=True, verbose_name="Date de lancement")
    closing_date = models.DateField(blank=True, null=True, verbose_name="Date de clôture")

    currency = models.CharField(max_length=10, default="XOF", verbose_name="Devise")

    manager_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nom du responsable")
    manager_phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="Téléphone du responsable")
    manager_email = models.EmailField(blank=True, null=True, verbose_name="Email du responsable")

    boundary = gis_models.MultiPolygonField(srid=4326, blank=True, null=True, verbose_name="Périmètre")
    centroid = gis_models.PointField(srid=4326, blank=True, null=True, verbose_name="Centroïde")

    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    class Meta:
        ordering = ["name"]
        verbose_name = "Programme immobilier"
        verbose_name_plural = "Programmes immobiliers"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        if self.place and self.place.country_id != self.country_id:
            raise ValidationError({"place": "Le lieu doit appartenir au même pays que le programme."})

        if self.launch_date and self.closing_date and self.closing_date < self.launch_date:
            raise ValidationError({"closing_date": "La date de clôture doit être postérieure ou égale à la date de lancement."})

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
        related_name="phases",
        verbose_name="Programme"
    )
    code = models.CharField(max_length=100, verbose_name="Code")
    name = models.CharField(max_length=255, verbose_name="Nom")
    order = models.PositiveIntegerField(default=1, verbose_name="Ordre")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PLANNED", verbose_name="Statut")

    start_date = models.DateField(blank=True, null=True, verbose_name="Date de début")
    end_date = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    class Meta:
        unique_together = ("program", "code")
        ordering = ["program", "order", "name"]
        verbose_name = "Phase du programme"
        verbose_name_plural = "Phases du programme"

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La date de fin doit être postérieure ou égale à la date de début."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.program.name} - {self.name}"


# =========================================================
# RÉFÉRENTIEL FONCIER
# =========================================================

class LandUseType(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    label = models.CharField(max_length=150, verbose_name="Libellé")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    class Meta:
        ordering = ["label"]
        verbose_name = "Type d'usage du sol"
        verbose_name_plural = "Types d'usage du sol"

    def __str__(self):
        return self.label


class ParcelDataset(TimeStampedModel, SoftDeleteModel):
    program = models.ForeignKey(
        RealEstateProgram,
        on_delete=models.CASCADE,
        related_name="parcel_datasets",
        verbose_name="Programme"
    )
    phase = models.ForeignKey(
        ProgramPhase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parcel_datasets",
        verbose_name="Phase"
    )

    name = models.CharField(max_length=255, verbose_name="Nom")
    source_code = models.CharField(max_length=255, blank=True, null=True, verbose_name="Code source")
    source_file_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nom du fichier source")

    geojson_type = models.CharField(max_length=50, default="FeatureCollection", verbose_name="Type GeoJSON")
    crs_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nom du SCR")
    xy_coordinate_resolution = models.FloatField(blank=True, null=True, verbose_name="Résolution XY")

    version = models.CharField(max_length=50, default="1.0", verbose_name="Version")
    is_current = models.BooleanField(default=True, verbose_name="Version courante")

    imported_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Importé par")
    import_notes = models.TextField(blank=True, null=True, verbose_name="Notes d'import")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Jeu de données parcellaire"
        verbose_name_plural = "Jeux de données parcellaires"

    def clean(self):
        super().clean()
        if self.phase and self.phase.program_id != self.program_id:
            raise ValidationError({"phase": "La phase doit appartenir au même programme."})

    def __str__(self):
        return self.name


class ProgramBlock(TimeStampedModel, SoftDeleteModel):
    program = models.ForeignKey(
        RealEstateProgram,
        on_delete=models.CASCADE,
        related_name="blocks",
        verbose_name="Programme"
    )
    phase = models.ForeignKey(
        ProgramPhase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocks",
        verbose_name="Phase"
    )

    code = models.CharField(max_length=50, verbose_name="Code")
    label = models.CharField(max_length=255, blank=True, null=True, verbose_name="Libellé")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    block_area_m2 = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Superficie de l'îlot (m²)")
    geometry = gis_models.MultiPolygonField(srid=4326, blank=True, null=True, verbose_name="Géométrie")

    class Meta:
        unique_together = ("program", "code")
        ordering = ["code"]
        verbose_name = "Îlot"
        verbose_name_plural = "Îlots"

    def clean(self):
        super().clean()
        if self.phase and self.phase.program_id != self.program_id:
            raise ValidationError({"phase": "La phase doit appartenir au même programme."})

    def __str__(self):
        return f"Îlot {self.code}--{self.program.name}"


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

    dataset = models.ForeignKey(ParcelDataset, on_delete=models.CASCADE, related_name="parcels", verbose_name="Jeu de données")
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="parcels", verbose_name="Programme")
    phase = models.ForeignKey(ProgramPhase, on_delete=models.SET_NULL, null=True, blank=True, related_name="parcels", verbose_name="Phase")
    block = models.ForeignKey(ProgramBlock, on_delete=models.SET_NULL, null=True, blank=True, related_name="parcels", verbose_name="Îlot")

    source_fid = models.IntegerField(blank=True, null=True, db_index=True, verbose_name="FID source")

    lot_number = models.CharField(max_length=50, blank=True, null=True, db_index=True, verbose_name="Numéro de lot")
    parcel_code = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name="Code parcelle")
    external_reference = models.CharField(max_length=150, blank=True, null=True, db_index=True, verbose_name="Référence externe")

    official_area_m2 = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Superficie officielle (m²)")
    computed_area_m2 = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Superficie calculée (m²)")

    frontage_m = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Façade (m)")
    depth_m = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Profondeur (m)")

    slope = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, verbose_name="Pente")
    elevation = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Altitude")

    land_use = models.ForeignKey(LandUseType, on_delete=models.SET_NULL, null=True, blank=True, related_name="parcels", verbose_name="Usage du sol")

    technical_status = models.CharField(max_length=20, choices=TECHNICAL_STATUS_CHOICES, default="RAW", verbose_name="Statut technique")
    commercial_status = models.CharField(max_length=20, choices=COMMERCIAL_STATUS_CHOICES, default="AVAILABLE", verbose_name="Statut commercial")

    is_corner = models.BooleanField(default=False, verbose_name="Lot d'angle")
    is_serviced = models.BooleanField(default=False, verbose_name="Viabilisé")
    has_road_access = models.BooleanField(default=True, verbose_name="Accès route")
    has_title_document = models.BooleanField(default=False, verbose_name="Titre foncier disponible")

    title_number = models.CharField(max_length=150, blank=True, null=True, verbose_name="Numéro de titre")
    zoning = models.CharField(max_length=150, blank=True, null=True, verbose_name="Zonage")

    geometry = gis_models.MultiPolygonField(srid=4326, blank=True, null=True, verbose_name="Géométrie")
    centroid = gis_models.PointField(srid=4326, blank=True, null=True, verbose_name="Centroïde")

    geometry_valid = models.BooleanField(default=True, verbose_name="Géométrie valide")
    has_number = models.BooleanField(default=True, verbose_name="Numérotation présente")
    duplicate_flag = models.BooleanField(default=False, verbose_name="Doublon détecté")

    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")
    crm_last_synced_at = models.DateTimeField(blank=True, null=True, verbose_name="Dernière synchro CRM")
    valeur_hypothecaire = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Valeur hypothécaire")

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
        verbose_name = "Parcelle"
        verbose_name_plural = "Parcelles"

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

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Lot {self.lot_number or self.parcel_code or 'N/A'}---{self.program.name}"


class ParcelGeometryHistory(TimeStampedModel):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="geometry_history", verbose_name="Parcelle")
    geometry = gis_models.MultiPolygonField(srid=4326, blank=True, null=True, verbose_name="Géométrie")
    reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Motif")
    changed_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Modifié par")

    class Meta:
        verbose_name = "Historique géométrique de parcelle"
        verbose_name_plural = "Historiques géométriques de parcelles"

    def __str__(self):
        return f"Historique géométrie {self.parcel}"

# =========================================================
# CLIENTS / CRM
# =========================================================

class Customer(TimeStampedModel, SoftDeleteModel):
    CUSTOMER_TYPE_CHOICES = [
        ("INDIVIDUAL", "Particulier"),
        ("COMPANY", "Entreprise"),
        ("INSTITUTION", "Institution"),
    ]

    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default="INDIVIDUAL", verbose_name="Type de client")
    first_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Prénom")
    last_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nom")
    company_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Raison sociale")

    phone = models.CharField(max_length=50, blank=True, null=True, db_index=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, null=True, db_index=True, verbose_name="Email")

    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers", verbose_name="Pays")
    place = models.ForeignKey(Place, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers", verbose_name="Lieu")

    address = models.TextField(blank=True, null=True, verbose_name="Adresse")
    id_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Type de pièce")
    id_number = models.CharField(max_length=150, blank=True, null=True, verbose_name="Numéro de pièce")

    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        if self.customer_type == "COMPANY":
            return self.company_name or "Entreprise"
        full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return full_name or "Client"


class Lead(TimeStampedModel, SoftDeleteModel):
    LEAD_STATUS_CHOICES = [
        ("NEW", "Nouveau"),
        ("QUALIFIED", "Qualifié"),
        ("VISIT_PLANNED", "Visite planifiée"),
        ("NEGOTIATION", "Négociation"),
        ("CONVERTED", "Converti"),
        ("LOST", "Perdu"),
    ]

    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="leads", verbose_name="Programme")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="leads", verbose_name="Client")
    interested_parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads", verbose_name="Parcelle d'intérêt")

    source = models.CharField(max_length=100, blank=True, null=True, verbose_name="Source")
    budget_min = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Budget minimum")
    budget_max = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Budget maximum")
    status = models.CharField(max_length=20, choices=LEAD_STATUS_CHOICES, default="NEW", verbose_name="Statut")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

    def __str__(self):
        return f"Lead {self.customer}"

# =========================================================
# TYPOLOGIES D'ACTIFS / UNITÉS
# =========================================================

class PropertyType(TimeStampedModel, SoftDeleteModel):
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    label = models.CharField(max_length=150, verbose_name="Libellé")

    class Meta:
        ordering = ["label"]
        verbose_name = "Type de propriété"
        verbose_name_plural = "Types de propriété"

    def __str__(self):
        return self.label


class UnitType(TimeStampedModel, SoftDeleteModel):
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    label = models.CharField(max_length=150, verbose_name="Libellé")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    class Meta:
        ordering = ["label"]
        verbose_name = "Type d'unité"
        verbose_name_plural = "Types d'unités"

    def __str__(self):
        return self.label


class AssetCategory(TimeStampedModel, SoftDeleteModel):
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    label = models.CharField(max_length=150, verbose_name="Libellé")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    default_floors = models.PositiveIntegerField(default=0, verbose_name="Nombre d'étages par défaut")

    class Meta:
        ordering = ["label"]
        verbose_name = "Catégorie d'actif"
        verbose_name_plural = "Catégories d'actifs"

    def __str__(self):
        return self.label

# =========================================================
# ACTIFS / UNITÉS
# =========================================================

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

    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="assets", verbose_name="Programme")
    phase = models.ForeignKey(ProgramPhase, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets", verbose_name="Phase")
    parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets", verbose_name="Parcelle")
    property_type = models.ForeignKey(PropertyType, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets", verbose_name="Type de propriété")
    asset_category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets", verbose_name="Catégorie d'actif")

    code = models.CharField(max_length=100, verbose_name="Code")
    label = models.CharField(max_length=255, verbose_name="Libellé")

    built_area_m2 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Surface bâtie (m²)")
    floors = models.PositiveIntegerField(default=0, verbose_name="Nombre d'étages")
    bedrooms = models.PositiveIntegerField(default=0, verbose_name="Nombre de chambres")
    bathrooms = models.PositiveIntegerField(default=0, verbose_name="Nombre de salles de bain")

    estimated_cost = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Coût estimé")
    sale_price = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Prix de vente")

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="PLANNED", verbose_name="Statut")

    description = models.TextField(blank=True, null=True, verbose_name="Description")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    is_multi_unit = models.BooleanField(default=False, verbose_name="Actif multi-unités")
    total_units_count = models.PositiveIntegerField(default=0, verbose_name="Nombre total d'unités")
    gross_floor_area_m2 = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, verbose_name="Surface brute (m²)")
    saleable_area_m2 = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, verbose_name="Surface vendable (m²)")
    market_value = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Valeur marchande")
    mortgage_value = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Valeur hypothécaire")
    delivery_date = models.DateField(blank=True, null=True, verbose_name="Date de livraison")

    class Meta:
        unique_together = ("program", "code")
        ordering = ["code"]
        verbose_name = "Actif immobilier"
        verbose_name_plural = "Actifs immobiliers"

    def clean(self):
        super().clean()

        if self.phase and self.phase.program_id != self.program_id:
            raise ValidationError({"phase": "La phase doit appartenir au même programme."})

        if self.parcel and self.parcel.program_id != self.program_id:
            raise ValidationError({"parcel": "La parcelle doit appartenir au même programme."})

        numeric_fields = {
            "built_area_m2": self.built_area_m2,
            "estimated_cost": self.estimated_cost,
            "sale_price": self.sale_price,
            "gross_floor_area_m2": self.gross_floor_area_m2,
            "saleable_area_m2": self.saleable_area_m2,
            "market_value": self.market_value,
            "mortgage_value": self.mortgage_value,
        }
        for field, value in numeric_fields.items():
            if value is not None and value < 0:
                raise ValidationError({field: "La valeur ne peut pas être négative."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


class PropertyUnit(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("DRAFT", "Brouillon"),
        ("AVAILABLE", "Disponible"),
        ("OPTIONED", "En option"),
        ("RESERVED", "Réservé"),
        ("SOLD", "Vendu"),
        ("BLOCKED", "Bloqué"),
        ("DELIVERED", "Livré"),
        ("ARCHIVED", "Archivé"),
    ]

    ORIENTATION_CHOICES = [
        ("N", "Nord"),
        ("S", "Sud"),
        ("E", "Est"),
        ("W", "Ouest"),
        ("NE", "Nord-Est"),
        ("NW", "Nord-Ouest"),
        ("SE", "Sud-Est"),
        ("SW", "Sud-Ouest"),
    ]

    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="units", verbose_name="Programme")
    phase = models.ForeignKey(ProgramPhase, on_delete=models.SET_NULL, null=True, blank=True, related_name="units", verbose_name="Phase")
    parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL, null=True, blank=True, related_name="units", verbose_name="Parcelle")
    asset = models.ForeignKey(PropertyAsset, on_delete=models.CASCADE, related_name="units", verbose_name="Actif")
    unit_type = models.ForeignKey(UnitType, on_delete=models.SET_NULL, null=True, blank=True, related_name="units", verbose_name="Type d'unité")

    code = models.CharField(max_length=100, verbose_name="Code")
    label = models.CharField(max_length=255, verbose_name="Libellé")
    slug = models.SlugField(max_length=255, blank=True, null=True, verbose_name="Slug")

    building = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bâtiment")
    entrance = models.CharField(max_length=100, blank=True, null=True, verbose_name="Entrée")
    staircase = models.CharField(max_length=100, blank=True, null=True, verbose_name="Escalier")
    floor_number = models.IntegerField(blank=True, null=True, verbose_name="Niveau")
    door_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="Numéro de porte")

    bedrooms = models.PositiveIntegerField(default=0, verbose_name="Chambres")
    bathrooms = models.PositiveIntegerField(default=0, verbose_name="Salles de bain")
    kitchens = models.PositiveIntegerField(default=0, verbose_name="Cuisines")

    indoor_area_m2 = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, verbose_name="Surface intérieure (m²)")
    terrace_area_m2 = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, verbose_name="Surface terrasse (m²)")
    balcony_area_m2 = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, verbose_name="Surface balcon (m²)")
    garden_area_m2 = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, verbose_name="Surface jardin (m²)")
    parking_area_m2 = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, verbose_name="Surface parking (m²)")
    saleable_area_m2 = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True, verbose_name="Surface vendable (m²)")

    orientation = models.CharField(max_length=2, choices=ORIENTATION_CHOICES, blank=True, null=True, verbose_name="Orientation")
    has_parking = models.BooleanField(default=False, verbose_name="Dispose d'un parking")
    has_garden = models.BooleanField(default=False, verbose_name="Dispose d'un jardin")
    has_terrace = models.BooleanField(default=False, verbose_name="Dispose d'une terrasse")
    has_balcony = models.BooleanField(default=False, verbose_name="Dispose d'un balcon")

    technical_status = models.CharField(max_length=30, blank=True, null=True, verbose_name="Statut technique")
    commercial_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="AVAILABLE", verbose_name="Statut commercial")

    estimated_cost = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Coût estimé")
    sale_price = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Prix de vente")
    minimum_sale_price = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Prix minimum de vente")
    mortgage_value = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Valeur hypothécaire")

    is_saleable = models.BooleanField(default=True, verbose_name="Commercialisable")
    is_deliverable = models.BooleanField(default=True, verbose_name="Livrable")

    description = models.TextField(blank=True, null=True, verbose_name="Description")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    class Meta:
        ordering = ["asset", "floor_number", "code"]
        unique_together = [("asset", "code")]
        indexes = [
            models.Index(fields=["program", "commercial_status"]),
            models.Index(fields=["asset", "commercial_status"]),
            models.Index(fields=["code"]),
        ]
        verbose_name = "Unité immobilière"
        verbose_name_plural = "Unités immobilières"

    def clean(self):
        super().clean()

        if self.asset and self.program_id != self.asset.program_id:
            raise ValidationError({"program": "Le programme doit être identique à celui de l'actif."})

        if self.phase and self.phase.program_id != self.program_id:
            raise ValidationError({"phase": "La phase doit appartenir au même programme."})

        if self.parcel and self.parcel.program_id != self.program_id:
            raise ValidationError({"parcel": "La parcelle doit appartenir au même programme."})

        if self.asset and self.asset.parcel_id and self.parcel_id and self.asset.parcel_id != self.parcel_id:
            raise ValidationError({"parcel": "La parcelle doit être cohérente avec celle de l'actif."})

        if self.asset and self.asset.phase_id and self.phase_id and self.asset.phase_id != self.phase_id:
            raise ValidationError({"phase": "La phase doit être cohérente avec celle de l'actif."})

        numeric_fields = {
            "indoor_area_m2": self.indoor_area_m2,
            "terrace_area_m2": self.terrace_area_m2,
            "balcony_area_m2": self.balcony_area_m2,
            "garden_area_m2": self.garden_area_m2,
            "parking_area_m2": self.parking_area_m2,
            "saleable_area_m2": self.saleable_area_m2,
            "estimated_cost": self.estimated_cost,
            "sale_price": self.sale_price,
            "minimum_sale_price": self.minimum_sale_price,
            "mortgage_value": self.mortgage_value,
        }
        for field, value in numeric_fields.items():
            if value is not None and value < 0:
                raise ValidationError({field: "La valeur ne peut pas être négative."})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.label or self.code)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label or self.code


class PropertyUnitStatusHistory(TimeStampedModel):
    unit = models.ForeignKey(PropertyUnit, on_delete=models.CASCADE, related_name="status_history", verbose_name="Unité")
    old_status = models.CharField(max_length=20, blank=True, null=True, verbose_name="Ancien statut")
    new_status = models.CharField(max_length=20, verbose_name="Nouveau statut")
    changed_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Modifié par")
    reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Motif")
    comment = models.TextField(blank=True, null=True, verbose_name="Commentaire")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Historique de statut d'unité"
        verbose_name_plural = "Historiques de statut d'unités"

    def __str__(self):
        return f"{self.unit} : {self.old_status} -> {self.new_status}"


class PropertyAssetStatusHistory(TimeStampedModel):
    asset = models.ForeignKey(PropertyAsset, on_delete=models.CASCADE, related_name="status_history", verbose_name="Actif")
    old_status = models.CharField(max_length=30, blank=True, null=True, verbose_name="Ancien statut")
    new_status = models.CharField(max_length=30, verbose_name="Nouveau statut")
    changed_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Modifié par")
    reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Motif")
    comment = models.TextField(blank=True, null=True, verbose_name="Commentaire")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Historique de statut d'actif"
        verbose_name_plural = "Historiques de statut d'actifs"

    def __str__(self):
        return f"{self.asset} : {self.old_status} -> {self.new_status}"


# =========================================================
# RÉSERVATIONS / VENTES
# =========================================================

class Reservation(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("DRAFT", "Brouillon"),
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expirée"),
        ("CANCELLED", "Annulée"),
        ("CONVERTED", "Convertie"),
    ]

    reservation_number = models.CharField(max_length=100, unique=True, verbose_name="Numéro de réservation")
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="reservations", verbose_name="Programme")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="reservations", verbose_name="Client")
    parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations", verbose_name="Parcelle")
    unit = models.ForeignKey(PropertyUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations", verbose_name="Unité")
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations", verbose_name="Lead")

    reservation_date = models.DateField(verbose_name="Date de réservation")
    expiry_date = models.DateField(blank=True, null=True, verbose_name="Date d'expiration")
    reserved_price = models.DecimalField(max_digits=16, decimal_places=2, verbose_name="Prix réservé")
    deposit_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0, verbose_name="Montant de dépôt")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT", verbose_name="Statut")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"

    def clean(self):
        super().clean()

        if self.parcel and self.parcel.program_id != self.program_id:
            raise ValidationError({"parcel": "Le lot doit appartenir au même programme."})

        if self.unit and self.program_id != self.unit.program_id:
            raise ValidationError({"unit": "L’unité doit appartenir au même programme."})

        if self.unit and self.parcel and self.unit.parcel_id and self.unit.parcel_id != self.parcel_id:
            raise ValidationError({"unit": "L’unité ne correspond pas à la parcelle sélectionnée."})

        if self.expiry_date and self.expiry_date < self.reservation_date:
            raise ValidationError({"expiry_date": "La date d’expiration doit être postérieure à la date de réservation."})

        if self.deposit_amount < 0:
            raise ValidationError({"deposit_amount": "Le montant du dépôt ne peut pas être négatif."})

        if self.reserved_price < 0:
            raise ValidationError({"reserved_price": "Le prix réservé ne peut pas être négatif."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reservation_number


class SaleFile(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("OPEN", "Ouvert"),
        ("PENDING_DOCS", "Documents en attente"),
        ("PENDING_PAYMENT", "Paiement en attente"),
        ("SIGNED", "Signé"),
        ("COMPLETED", "Finalisé"),
        ("CANCELLED", "Annulé"),
    ]

    sale_number = models.CharField(max_length=100, unique=True, verbose_name="Numéro de vente")
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="sales", verbose_name="Programme")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="sales", verbose_name="Client principal")
    parcel = models.ForeignKey(Parcel, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales", verbose_name="Parcelle")
    unit = models.ForeignKey(PropertyUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales", verbose_name="Unité")
    reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales", verbose_name="Réservation")

    sale_date = models.DateField(blank=True, null=True, verbose_name="Date de vente")
    agreed_price = models.DecimalField(max_digits=16, decimal_places=2, verbose_name="Prix convenu")
    discount_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0, verbose_name="Remise")
    net_price = models.DecimalField(max_digits=16, decimal_places=2, verbose_name="Prix net")

    financing_mode = models.CharField(max_length=100, blank=True, null=True, verbose_name="Mode de financement")
    down_payment_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0, verbose_name="Apport initial")
    notary_fees = models.DecimalField(max_digits=16, decimal_places=2, default=0, verbose_name="Frais de notaire")
    admin_fees = models.DecimalField(max_digits=16, decimal_places=2, default=0, verbose_name="Frais administratifs")
    tax_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0, verbose_name="Taxes")

    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN", verbose_name="Statut")
    sales_agent = models.CharField(max_length=255, blank=True, null=True, verbose_name="Commercial")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Dossier de vente"
        verbose_name_plural = "Dossiers de vente"

    def clean(self):
        super().clean()

        if self.unit and self.program_id != self.unit.program_id:
            raise ValidationError({"unit": "L’unité doit appartenir au même programme."})

        if self.parcel and self.parcel.program_id != self.program_id:
            raise ValidationError({"parcel": "La parcelle doit appartenir au même programme."})

        if self.unit and self.parcel and self.unit.parcel_id and self.unit.parcel_id != self.parcel_id:
            raise ValidationError({"unit": "L’unité ne correspond pas à la parcelle sélectionnée."})

        numeric_fields = {
            "agreed_price": self.agreed_price,
            "discount_amount": self.discount_amount,
            "net_price": self.net_price,
            "down_payment_amount": self.down_payment_amount,
            "notary_fees": self.notary_fees,
            "admin_fees": self.admin_fees,
            "tax_amount": self.tax_amount,
        }
        for field, value in numeric_fields.items():
            if value is not None and value < 0:
                raise ValidationError({field: "La valeur ne peut pas être négative."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        customer_name = str(self.customer) if self.customer_id else "Client"
        return f"{customer_name} - {self.sale_number}"


class SaleBuyer(TimeStampedModel):
    ROLE_CHOICES = [
        ("PRIMARY", "Acquéreur principal"),
        ("CO_BUYER", "Coacquéreur"),
        ("GUARANTOR", "Garant"),
        ("REPRESENTATIVE", "Représentant"),
    ]

    sale_file = models.ForeignKey(SaleFile, on_delete=models.CASCADE, related_name="buyers", verbose_name="Dossier de vente")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="sale_roles", verbose_name="Client")

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="PRIMARY", verbose_name="Rôle")
    ownership_percent = models.DecimalField(max_digits=5, decimal_places=2, default=100, verbose_name="Pourcentage de propriété")
    is_primary = models.BooleanField(default=False, verbose_name="Acheteur principal")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    class Meta:
        unique_together = [("sale_file", "customer")]
        ordering = ["sale_file", "-is_primary", "id"]
        verbose_name = "Acquéreur de vente"
        verbose_name_plural = "Acquéreurs de vente"

    def clean(self):
        super().clean()

        if self.ownership_percent < 0 or self.ownership_percent > 100:
            raise ValidationError({"ownership_percent": "Le pourcentage doit être compris entre 0 et 100."})

        if self.is_primary:
            qs = SaleBuyer.objects.filter(sale_file=self.sale_file, is_primary=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"is_primary": "Il existe déjà un acquéreur principal pour ce dossier."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer} / {self.sale_file}"


class SaleFileStatusHistory(TimeStampedModel):
    sale_file = models.ForeignKey(SaleFile, on_delete=models.CASCADE, related_name="status_history", verbose_name="Dossier de vente")
    old_status = models.CharField(max_length=20, blank=True, null=True, verbose_name="Ancien statut")
    new_status = models.CharField(max_length=20, verbose_name="Nouveau statut")
    changed_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Modifié par")
    reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Motif")
    comment = models.TextField(blank=True, null=True, verbose_name="Commentaire")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Historique de statut de vente"
        verbose_name_plural = "Historiques de statut de vente"

    def __str__(self):
        return f"{self.sale_file} : {self.old_status} -> {self.new_status}"


# =========================================================
# PAIEMENTS
# =========================================================

class PaymentSchedule(TimeStampedModel, SoftDeleteModel):
    sale_file = models.OneToOneField(SaleFile, on_delete=models.CASCADE, related_name="payment_schedule", verbose_name="Dossier de vente")
    name = models.CharField(max_length=255, verbose_name="Nom")
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, verbose_name="Montant total")
    start_date = models.DateField(blank=True, null=True, verbose_name="Date de début")
    end_date = models.DateField(blank=True, null=True, verbose_name="Date de fin")

    class Meta:
        verbose_name = "Échéancier de paiement"
        verbose_name_plural = "Échéanciers de paiement"

    def clean(self):
        super().clean()
        if self.total_amount < 0:
            raise ValidationError({"total_amount": "Le montant total ne peut pas être négatif."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La date de fin doit être postérieure ou égale à la date de début."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

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

    schedule = models.ForeignKey(PaymentSchedule, on_delete=models.CASCADE, related_name="installments", verbose_name="Échéancier")
    label = models.CharField(max_length=255, verbose_name="Libellé")
    due_date = models.DateField(verbose_name="Date d'échéance")
    amount_due = models.DecimalField(max_digits=16, decimal_places=2, verbose_name="Montant dû")
    amount_paid = models.DecimalField(max_digits=16, decimal_places=2, default=0, verbose_name="Montant payé")
    balance = models.DecimalField(max_digits=16, decimal_places=2, default=0, verbose_name="Solde")
    order = models.PositiveIntegerField(default=1, verbose_name="Ordre")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING", verbose_name="Statut")

    class Meta:
        ordering = ["order", "due_date", "id"]
        verbose_name = "Échéance de paiement"
        verbose_name_plural = "Échéances de paiement"

    def clean(self):
        super().clean()

        if self.amount_due < 0:
            raise ValidationError({"amount_due": "Le montant dû ne peut pas être négatif."})

        if self.amount_paid < 0:
            raise ValidationError({"amount_paid": "Le montant payé ne peut pas être négatif."})

        if self.balance < 0:
            raise ValidationError({"balance": "Le solde ne peut pas être négatif."})

    def save(self, *args, **kwargs):
        if self.amount_due is not None and self.amount_paid is not None:
            computed_balance = self.amount_due - self.amount_paid
            self.balance = computed_balance if computed_balance >= 0 else 0
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


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

    payment_number = models.CharField(max_length=100, unique=True, verbose_name="Numéro de paiement")
    sale_file = models.ForeignKey(SaleFile, on_delete=models.CASCADE, related_name="payments", verbose_name="Dossier de vente")
    installment = models.ForeignKey(PaymentInstallment, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments", verbose_name="Échéance")

    payment_date = models.DateField(verbose_name="Date de paiement")
    amount = models.DecimalField(max_digits=16, decimal_places=2, verbose_name="Montant")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, verbose_name="Mode de paiement")
    reference = models.CharField(max_length=255, blank=True, null=True, verbose_name="Référence")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING", verbose_name="Statut")
    received_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Reçu par")
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

    def clean(self):
        super().clean()

        if self.amount < 0:
            raise ValidationError({"amount": "Le montant ne peut pas être négatif."})

        if self.installment and self.installment.schedule.sale_file_id != self.sale_file_id:
            raise ValidationError({"installment": "L’échéance doit appartenir au même dossier de vente."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.payment_number


class PaymentAllocation(TimeStampedModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations", verbose_name="Paiement")
    sale_file = models.ForeignKey(SaleFile, on_delete=models.CASCADE, related_name="payment_allocations", verbose_name="Dossier de vente")
    unit = models.ForeignKey(PropertyUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_allocations", verbose_name="Unité")

    label = models.CharField(max_length=255, blank=True, null=True, verbose_name="Libellé")
    allocated_amount = models.DecimalField(max_digits=16, decimal_places=2, verbose_name="Montant alloué")

    class Meta:
        ordering = ["payment", "id"]
        verbose_name = "Affectation de paiement"
        verbose_name_plural = "Affectations de paiement"

    def clean(self):
        super().clean()

        if self.allocated_amount <= 0:
            raise ValidationError({"allocated_amount": "Le montant alloué doit être strictement positif."})

        if self.payment and self.payment.sale_file_id != self.sale_file_id:
            raise ValidationError({"sale_file": "Le dossier de vente doit être identique à celui du paiement."})

        if self.unit and self.sale_file.unit_id and self.unit_id != self.sale_file.unit_id:
            raise ValidationError({"unit": "L’unité affectée ne correspond pas à celle du dossier de vente."})

        if self.unit and self.sale_file.program_id != self.unit.program_id:
            raise ValidationError({"unit": "L’unité doit appartenir au même programme que la vente."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.payment} - {self.allocated_amount}"


# =========================================================
# DOCUMENTS
# =========================================================

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

    title = models.CharField(max_length=255, verbose_name="Titre")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="OTHER", verbose_name="Type de document")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    file = models.FileField(upload_to="documents/%Y/%m/", verbose_name="Fichier")
    original_filename = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nom original du fichier")
    file_size = models.PositiveBigIntegerField(blank=True, null=True, verbose_name="Taille du fichier")
    mime_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Type MIME")

    issued_at = models.DateField(blank=True, null=True, verbose_name="Date d'émission")
    expires_at = models.DateField(blank=True, null=True, verbose_name="Date d'expiration")

    uploaded_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Téléversé par")
    is_confidential = models.BooleanField(default=False, verbose_name="Confidentiel")

    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.expires_at and self.issued_at and self.expires_at < self.issued_at:
            raise ValidationError({"expires_at": "La date d'expiration doit être postérieure ou égale à la date d'émission."})


class AssetDocument(DocumentBase):
    asset = models.ForeignKey(PropertyAsset, on_delete=models.CASCADE, related_name="documents", verbose_name="Actif")

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document d'actif"
        verbose_name_plural = "Documents d'actifs"

    def __str__(self):
        return f"{self.asset} - {self.title}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class UnitDocument(DocumentBase):
    unit = models.ForeignKey(PropertyUnit, on_delete=models.CASCADE, related_name="documents", verbose_name="Unité")

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document d'unité"
        verbose_name_plural = "Documents d'unités"

    def __str__(self):
        return f"{self.unit} - {self.title}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class SaleDocument(DocumentBase):
    sale_file = models.ForeignKey(SaleFile, on_delete=models.CASCADE, related_name="documents", verbose_name="Dossier de vente")

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document de vente"
        verbose_name_plural = "Documents de vente"

    def __str__(self):
        return f"{self.sale_file} - {self.title}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProgramDocument(DocumentBase):
    program = models.ForeignKey(RealEstateProgram, on_delete=models.CASCADE, related_name="documents", verbose_name="Programme")

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
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="documents", verbose_name="Parcelle")

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
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="documents", verbose_name="Client")

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document client"
        verbose_name_plural = "Documents clients"

    def __str__(self):
        return f"{self.customer} - {self.title}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# =========================================================
# CONSTRUCTION / CHANTIER
# =========================================================

class ConstructionProject(TimeStampedModel, SoftDeleteModel):
    STATUS_CHOICES = [
        ("PLANNED", "Planifié"),
        ("NOT_STARTED", "Non démarré"),
        ("IN_PROGRESS", "En cours"),
        ("ON_HOLD", "Suspendu"),
        ("COMPLETED", "Achevé"),
        ("CANCELLED", "Annulé"),
    ]

    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="construction_projects", verbose_name="Parcelle")
    asset = models.ForeignKey(PropertyAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name="construction_projects", verbose_name="Actif")

    code = models.CharField(max_length=100, unique=True, verbose_name="Code")
    title = models.CharField(max_length=255, verbose_name="Titre")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PLANNED", verbose_name="Statut")

    planned_start_date = models.DateField(blank=True, null=True, verbose_name="Début prévisionnel")
    actual_start_date = models.DateField(blank=True, null=True, verbose_name="Début réel")
    planned_end_date = models.DateField(blank=True, null=True, verbose_name="Fin prévisionnelle")
    actual_end_date = models.DateField(blank=True, null=True, verbose_name="Fin réelle")

    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Avancement (%)")
    estimated_budget = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Budget estimatif")
    actual_cost = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True, verbose_name="Coût réel")

    contractor_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Entreprise en charge")
    site_manager = models.CharField(max_length=255, blank=True, null=True, verbose_name="Chef de chantier")

    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Projet de construction"
        verbose_name_plural = "Projets de construction"

    def clean(self):
        super().clean()

        if self.asset and self.asset.parcel_id and self.asset.parcel_id != self.parcel_id:
            raise ValidationError({"asset": "L'actif sélectionné doit appartenir à la même parcelle."})

        if self.progress_percent is not None and (self.progress_percent < 0 or self.progress_percent > 100):
            raise ValidationError({"progress_percent": "Le pourcentage d'avancement doit être compris entre 0 et 100."})

        if self.planned_start_date and self.planned_end_date and self.planned_end_date < self.planned_start_date:
            raise ValidationError({"planned_end_date": "La date de fin prévisionnelle doit être postérieure à la date de début prévisionnelle."})

        if self.actual_start_date and self.actual_end_date and self.actual_end_date < self.actual_start_date:
            raise ValidationError({"actual_end_date": "La date de fin réelle doit être postérieure à la date de début réelle."})

        numeric_fields = {
            "estimated_budget": self.estimated_budget,
            "actual_cost": self.actual_cost,
        }
        for field, value in numeric_fields.items():
            if value is not None and value < 0:
                raise ValidationError({field: "La valeur ne peut pas être négative."})

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

    construction_project = models.ForeignKey(ConstructionProject, on_delete=models.CASCADE, related_name="updates", verbose_name="Projet de construction")

    report_date = models.DateField(verbose_name="Date du rapport")
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default="OTHER", verbose_name="Étape")

    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Avancement (%)")
    summary = models.CharField(max_length=255, verbose_name="Résumé")
    details = models.TextField(blank=True, null=True, verbose_name="Détails")

    issues = models.TextField(blank=True, null=True, verbose_name="Problèmes")
    next_actions = models.TextField(blank=True, null=True, verbose_name="Actions suivantes")

    weather_notes = models.CharField(max_length=255, blank=True, null=True, verbose_name="Météo")
    recorded_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Enregistré par")
    asset = models.ForeignKey(PropertyAsset, on_delete=models.CASCADE, related_name="updates", null=True, blank=True, verbose_name="Actif")

    class Meta:
        ordering = ["-report_date", "-created_at"]
        verbose_name = "Mise à jour de chantier"
        verbose_name_plural = "Mises à jour de chantier"

    def clean(self):
        super().clean()

        if self.progress_percent is not None and (self.progress_percent < 0 or self.progress_percent > 100):
            raise ValidationError({"progress_percent": "Le pourcentage d'avancement doit être compris entre 0 et 100."})

        if self.asset and self.construction_project.asset_id and self.asset_id != self.construction_project.asset_id:
            raise ValidationError({"asset": "L'actif doit correspondre à celui du projet de construction."})

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

    construction_project = models.ForeignKey(ConstructionProject, on_delete=models.CASCADE, related_name="photos", verbose_name="Projet de construction")
    update = models.ForeignKey(ConstructionUpdate, on_delete=models.SET_NULL, null=True, blank=True, related_name="photos", verbose_name="Mise à jour")

    title = models.CharField(max_length=255, blank=True, null=True, verbose_name="Titre")
    image = models.ImageField(upload_to="construction_progress/%Y/%m/", verbose_name="Image")
    caption = models.TextField(blank=True, null=True, verbose_name="Légende")

    shot_date = models.DateField(blank=True, null=True, verbose_name="Date de prise")
    view_type = models.CharField(max_length=20, choices=VIEW_CHOICES, default="OTHER", verbose_name="Type de vue")

    is_cover = models.BooleanField(default=False, verbose_name="Image de couverture")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    original_filename = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nom original")
    file_size = models.PositiveBigIntegerField(blank=True, null=True, verbose_name="Taille du fichier")
    mime_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Type MIME")

    uploaded_by = models.CharField(max_length=255, blank=True, null=True, verbose_name="Téléversé par")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")
    asset = models.ForeignKey(PropertyAsset, on_delete=models.CASCADE, related_name="photos", null=True, blank=True, verbose_name="Actif")

    class Meta:
        ordering = ["sort_order", "-shot_date", "-created_at"]
        verbose_name = "Photo de chantier"
        verbose_name_plural = "Photos de chantier"

    def clean(self):
        super().clean()

        if self.update and self.update.construction_project_id != self.construction_project_id:
            raise ValidationError({"update": "Le rapport sélectionné doit appartenir au même chantier."})

        if self.asset and self.construction_project.asset_id and self.asset_id != self.construction_project.asset_id:
            raise ValidationError({"asset": "L'actif doit être cohérent avec le projet de construction."})

    def save(self, *args, **kwargs):
        if self.image:
            self.original_filename = self.original_filename or self.image.name.split("/")[-1]
            self.file_size = getattr(self.image, "size", None)
            self.mime_type = self.mime_type or getattr(getattr(self.image, "file", None), "content_type", None)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or f"Photo {self.pk}"


class ConstructionMedia(TimeStampedModel, SoftDeleteModel):
    MEDIA_TYPE_CHOICES = [
        ("IMAGE", "Image"),
        ("VIDEO", "Vidéo"),
    ]

    construction_project = models.ForeignKey(ConstructionProject, on_delete=models.CASCADE, related_name="media", verbose_name="Projet de construction")
    update = models.ForeignKey(ConstructionUpdate, on_delete=models.SET_NULL, null=True, blank=True, related_name="media", verbose_name="Mise à jour")

    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default="IMAGE", verbose_name="Type de média")
    file = models.FileField(upload_to="construction_media/%Y/%m/", verbose_name="Fichier")
    title = models.CharField(max_length=255, blank=True, null=True, verbose_name="Titre")
    caption = models.TextField(blank=True, null=True, verbose_name="Légende")
    shot_date = models.DateField(blank=True, null=True, verbose_name="Date de prise")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Métadonnées")

    class Meta:
        ordering = ["sort_order", "-created_at"]
        verbose_name = "Média de chantier"
        verbose_name_plural = "Médias de chantier"

    def clean(self):
        super().clean()
        if self.update and self.update.construction_project_id != self.construction_project_id:
            raise ValidationError({"update": "La mise à jour doit appartenir au même projet de construction."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)



#-===-=-=-=-=-=-=-=-=SAP

class IntegrationLog(models.Model):
    DIRECTION_CHOICES = (
        ("OUTBOUND", "Outbound"),
        ("INBOUND", "Inbound"),
    )

    SYSTEM_CHOICES = (
        ("SAP", "SAP"),
    )

    STATUS_CHOICES = (
        ("SUCCESS", "Success"),
        ("ERROR", "Error"),
        ("PENDING", "Pending"),
    )

    system = models.CharField(max_length=50, choices=SYSTEM_CHOICES, default="SAP")
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default="OUTBOUND")
    operation = models.CharField(max_length=100)
    endpoint = models.CharField(max_length=500, blank=True, null=True)
    method = models.CharField(max_length=10, blank=True, null=True)
    request_payload = models.JSONField(blank=True, null=True)
    response_payload = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    http_status = models.IntegerField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    external_id = models.CharField(max_length=150, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.system} - {self.operation} - {self.status}"