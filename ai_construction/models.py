from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid


class SimulationProviderChoices(models.TextChoices):
    RUNWAY = "RUNWAY", "Runway"
    VEO = "VEO", "Google Veo"


class SimulationStatusChoices(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    QUEUED = "QUEUED", "En file"
    STORYBOARDING = "STORYBOARDING", "Storyboard"
    GENERATING_IMAGES = "GENERATING_IMAGES", "Génération images"
    GENERATING_VIDEOS = "GENERATING_VIDEOS", "Génération vidéos"
    ASSEMBLING = "ASSEMBLING", "Assemblage"
    COMPLETED = "COMPLETED", "Terminée"
    FAILED = "FAILED", "Échec"
    CANCELED = "CANCELED", "Annulée"


class SimulationStyleChoices(models.TextChoices):
    REALISTIC = "REALISTIC", "Réaliste"
    CINEMATIC = "CINEMATIC", "Cinématique"
    PREMIUM = "PREMIUM", "Premium"
    DOCUMENTARY = "DOCUMENTARY", "Documentaire"


class CameraStyleChoices(models.TextChoices):
    DRONE = "DRONE", "Drone"
    STREET = "STREET", "Vue rue"
    MIXED = "MIXED", "Mixte"
    ORBIT = "ORBIT", "Orbit"
    FIXED = "FIXED", "Fixe"


class ConstructionSimulationProject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # rattachement métier
    program = models.ForeignKey(
        "parcelaire.RealEstateProgram",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="construction_simulations",
    )
    asset = models.ForeignKey(
        "parcelaire.PropertyAsset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="construction_simulations",
    )
    parcel = models.ForeignKey(
        "parcelaire.Parcel",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="construction_simulations",
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)

    provider = models.CharField(
        max_length=20,
        choices=SimulationProviderChoices.choices,
        default=SimulationProviderChoices.RUNWAY,
    )
    style = models.CharField(
        max_length=20,
        choices=SimulationStyleChoices.choices,
        default=SimulationStyleChoices.REALISTIC,
    )
    camera_style = models.CharField(
        max_length=20,
        choices=CameraStyleChoices.choices,
        default=CameraStyleChoices.MIXED,
    )

    target_duration_seconds = models.PositiveIntegerField(default=30)
    aspect_ratio = models.CharField(max_length=20, default="16:9")
    target_resolution = models.CharField(max_length=20, default="1280x720")

    include_audio = models.BooleanField(default=False)
    include_voiceover = models.BooleanField(default=False)
    include_branding = models.BooleanField(default=True)
    include_watermark = models.BooleanField(default=True)

    language = models.CharField(max_length=10, default="fr")
    status = models.CharField(
        max_length=30,
        choices=SimulationStatusChoices.choices,
        default=SimulationStatusChoices.DRAFT,
        db_index=True,
    )

    prompt_seed = models.TextField(blank=True)
    negative_prompt = models.TextField(blank=True)
    business_context = models.JSONField(default=dict, blank=True)
    technical_context = models.JSONField(default=dict, blank=True)

    final_video = models.FileField(upload_to="ai_simulations/final/", blank=True, null=True)
    thumbnail = models.ImageField(upload_to="ai_simulations/thumbs/", blank=True, null=True)

    total_scenes = models.PositiveIntegerField(default=0)
    completed_scenes = models.PositiveIntegerField(default=0)
    progress_percent = models.PositiveIntegerField(default=0)

    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="construction_simulations_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ConstructionSimulationScene(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    simulation = models.ForeignKey(
        ConstructionSimulationProject,
        on_delete=models.CASCADE,
        related_name="scenes",
    )

    order = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    phase_code = models.CharField(max_length=50, blank=True)

    duration_seconds = models.PositiveIntegerField(default=5)
    shot_type = models.CharField(max_length=100, blank=True)
    environment = models.CharField(max_length=255, blank=True)
    weather = models.CharField(max_length=100, blank=True, default="clear daylight")
    camera_motion = models.CharField(max_length=100, blank=True, default="slow cinematic movement")

    prompt_text = models.TextField()
    negative_prompt = models.TextField(blank=True)

    reference_image = models.ImageField(upload_to="ai_simulations/scenes/reference/", blank=True, null=True)
    generated_image = models.ImageField(upload_to="ai_simulations/scenes/generated_images/", blank=True, null=True)
    generated_video = models.FileField(upload_to="ai_simulations/scenes/generated_videos/", blank=True, null=True)

    provider_job_id = models.CharField(max_length=255, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, default="PENDING", db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("simulation", "order")]

    def __str__(self):
        return f"{self.simulation.title} - Scene {self.order}"


class ConstructionSimulationAsset(models.Model):
    ASSET_TYPE_CHOICES = [
        ("PHOTO", "Photo"),
        ("PLAN", "Plan"),
        ("RENDER", "Render"),
        ("DRONE", "Drone"),
        ("STYLE", "Style"),
        ("LOGO", "Logo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    simulation = models.ForeignKey(
        ConstructionSimulationProject,
        on_delete=models.CASCADE,
        related_name="assets",
    )
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES)
    file = models.FileField(upload_to="ai_simulations/assets/")
    label = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]


class ConstructionSimulationVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    simulation = models.ForeignKey(
        ConstructionSimulationProject,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField(default=1)
    config_snapshot = models.JSONField(default=dict, blank=True)
    prompt_snapshot = models.JSONField(default=dict, blank=True)
    final_video = models.FileField(upload_to="ai_simulations/versions/", blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        unique_together = [("simulation", "version_number")]


class ConstructionSimulationLog(models.Model):
    LEVEL_CHOICES = [
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
    ]

    simulation = models.ForeignKey(
        ConstructionSimulationProject,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    scene = models.ForeignKey(
        ConstructionSimulationScene,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="INFO")
    message = models.TextField()
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]