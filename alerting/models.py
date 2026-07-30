"""Module d'alertes automatisées — modèles (Phase 1 : fondation).

Couvre : destinataires + groupes, seuils de sévérité paramétrables,
configurations d'alerte avec planification (`compute_next_send_at`), détections,
rapports + dispatch (historique d'envoi), et snapshots d'historisation
(construction / paiement / commercialisation) indispensables au calcul des
variations entre périodes.

La logique métier (détection, métriques, PDF, e-mail, Celery) arrive dans les
phases suivantes ; ici on pose les données + la planification, testées.
"""
import calendar
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from parcelaire.models import SoftDeleteModel, TimeStampedModel


# =====================================================================
# Énumérations partagées
# =====================================================================

class Channel(models.TextChoices):
    EMAIL = "EMAIL", "E-mail"
    SMS = "SMS", "SMS"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    IN_APP = "IN_APP", "Notification interne"


class Severity(models.TextChoices):
    INFORMATION = "INFORMATION", "Information"
    VIGILANCE = "VIGILANCE", "Vigilance"
    IMPORTANT = "IMPORTANT", "Important"
    CRITICAL = "CRITICAL", "Critique"


# Ordre croissant de gravité (pour le filtre `minimum_severity`).
SEVERITY_ORDER = {
    Severity.INFORMATION: 0, Severity.VIGILANCE: 1,
    Severity.IMPORTANT: 2, Severity.CRITICAL: 3,
}


class AlertType(models.TextChoices):
    PERIODIC_GLOBAL = "PERIODIC_GLOBAL", "Rapport périodique global"
    PAYMENT_GT_CONSTRUCTION = "PAYMENT_GT_CONSTRUCTION", "Paiement supérieur à la construction"
    CONSTRUCTION_STAGNANT = "CONSTRUCTION_STAGNANT", "Construction sans évolution"
    PERFORMANCE_DROP = "PERFORMANCE_DROP", "Baisse ou stagnation de performance"
    HIGH_COMM_LOW_CONSTRUCTION = "HIGH_COMM_LOW_CONSTRUCTION", "Commercialisation élevée, construction faible"
    STRATEGIC_COMBO = "STRATEGIC_COMBO", "Paiements/commercialisation élevés, travaux faibles"
    SOLD_NO_PROGRESS = "SOLD_NO_PROGRESS", "Lot vendu sans avancement"
    DATA_QUALITY = "DATA_QUALITY", "Anomalie ou incohérence de données"


class Frequency(models.TextChoices):
    WEEKLY = "WEEKLY", "Hebdomadaire"
    BIWEEKLY = "BIWEEKLY", "Quinzaine"
    MONTHLY = "MONTHLY", "Mensuelle"
    CUSTOM = "CUSTOM", "Personnalisée"
    MANUAL = "MANUAL", "Manuelle"


class DispatchStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    GENERATING = "GENERATING", "Génération"
    READY = "READY", "Prêt"
    SENDING = "SENDING", "Envoi en cours"
    SENT = "SENT", "Envoyé"
    PARTIAL = "PARTIAL", "Partiel"
    FAILED = "FAILED", "Échec"
    CANCELLED = "CANCELLED", "Annulé"


class Retention(models.IntegerChoices):
    D30 = 30, "30 jours"
    D90 = 90, "90 jours"
    D180 = 180, "180 jours"
    Y1 = 365, "1 an"
    UNLIMITED = 0, "Illimitée"


def _month_day(year, month, dom):
    """Date valide (year, month, dom) en bornant dom au dernier jour du mois
    (dom=31 → dernier jour ; utile pour « dernier jour du mois »)."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(int(dom or 1), 1), last))


# =====================================================================
# Destinataires
# =====================================================================

class AlertRecipient(TimeStampedModel, SoftDeleteModel):
    first_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Prénom")
    last_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nom")
    email = models.EmailField(db_index=True, verbose_name="E-mail")
    phone_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Téléphone")
    job_title = models.CharField(max_length=150, blank=True, null=True, verbose_name="Fonction")
    department = models.CharField(max_length=150, blank=True, null=True, verbose_name="Direction")
    company = models.CharField(max_length=150, blank=True, null=True, verbose_name="Société")
    preferred_channel = models.CharField(max_length=20, choices=Channel.choices,
                                         default=Channel.EMAIL, verbose_name="Canal préféré")
    receive_email = models.BooleanField(default=True, verbose_name="Recevoir par e-mail")
    receive_sms = models.BooleanField(default=False, verbose_name="Recevoir par SMS")
    receive_pdf = models.BooleanField(default=True, verbose_name="Recevoir le PDF")
    # Lien optionnel vers un compte (pour le périmètre projet/programme autorisé).
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="alert_recipients")

    class Meta:
        verbose_name = "Destinataire d'alerte"
        verbose_name_plural = "Destinataires d'alerte"
        ordering = ["last_name", "first_name", "email"]
        permissions = [("manage_alertrecipient", "Peut gérer les destinataires d'alerte")]

    def __str__(self):
        name = " ".join(filter(None, [self.first_name, self.last_name])).strip()
        return name or self.email


class AlertRecipientGroup(TimeStampedModel, SoftDeleteModel):
    name = models.CharField(max_length=150, verbose_name="Nom du groupe")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    recipients = models.ManyToManyField(AlertRecipient, blank=True, related_name="groups",
                                        verbose_name="Destinataires")

    class Meta:
        verbose_name = "Groupe de destinataires"
        verbose_name_plural = "Groupes de destinataires"
        ordering = ["name"]

    def __str__(self):
        return self.name


# =====================================================================
# Seuils de sévérité (paramétrables)
# =====================================================================

class AlertThreshold(TimeStampedModel):
    """Seuils de l'écart paiement-construction (en POINTS) → sévérité.
    Paramétrable ; un seul jeu `is_active` sert de référence courante."""
    label = models.CharField(max_length=120, default="Seuils par défaut")
    vigilance_min = models.FloatField(default=10, verbose_name="Vigilance ≥ (points)")
    important_min = models.FloatField(default=25, verbose_name="Important ≥ (points)")
    critical_min = models.FloatField(default=40, verbose_name="Critique ≥ (points)")
    # Critères additionnels de criticité (pondérations, seuils monétaires…).
    stagnation_days = models.PositiveIntegerField(default=30, verbose_name="Stagnation critique (jours)")
    high_exposure_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0,
                                               verbose_name="Exposition financière élevée (FCFA)")
    is_active = models.BooleanField(default=True, verbose_name="Jeu de seuils actif")

    class Meta:
        verbose_name = "Seuils de sévérité"
        verbose_name_plural = "Seuils de sévérité"
        permissions = [("manage_alert_thresholds", "Peut gérer les seuils de sévérité")]

    def __str__(self):
        return f"{self.label} (V{self.vigilance_min}/I{self.important_min}/C{self.critical_min})"

    def classify(self, gap_points):
        """Sévérité d'après l'écart paiement-construction (en points)."""
        if gap_points is None:
            return Severity.INFORMATION
        if gap_points >= self.critical_min:
            return Severity.CRITICAL
        if gap_points >= self.important_min:
            return Severity.IMPORTANT
        if gap_points >= self.vigilance_min:
            return Severity.VIGILANCE
        return Severity.INFORMATION

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).order_by("-updated_at").first()


class AlertRule(TimeStampedModel):
    """Active/désactive un type d'alerte et porte ses paramètres (JSON)."""
    name = models.CharField(max_length=150)
    alert_type = models.CharField(max_length=40, choices=AlertType.choices, db_index=True)
    is_enabled = models.BooleanField(default=True)
    severity_floor = models.CharField(max_length=20, choices=Severity.choices,
                                      default=Severity.INFORMATION)
    params = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Règle d'alerte"
        verbose_name_plural = "Règles d'alerte"
        ordering = ["alert_type"]

    def __str__(self):
        return f"{self.get_alert_type_display()} ({'on' if self.is_enabled else 'off'})"


# =====================================================================
# Configuration d'une alerte (+ planification)
# =====================================================================

class AlertConfiguration(TimeStampedModel):
    name = models.CharField(max_length=200, verbose_name="Nom")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    alert_type = models.CharField(max_length=40, choices=AlertType.choices,
                                  default=AlertType.PERIODIC_GLOBAL, verbose_name="Type d'alerte")

    # --- Planification ---
    frequency = models.CharField(max_length=20, choices=Frequency.choices,
                                 default=Frequency.WEEKLY, verbose_name="Fréquence")
    custom_interval_days = models.PositiveIntegerField(default=7, verbose_name="Intervalle (jours)")
    day_of_week = models.PositiveSmallIntegerField(default=0, verbose_name="Jour de la semaine (0=lundi)")
    day_of_month = models.PositiveSmallIntegerField(default=1, verbose_name="Jour du mois (31=dernier)")
    send_time = models.TimeField(default=time(8, 0), verbose_name="Heure d'envoi")
    timezone = models.CharField(max_length=64, default="Africa/Abidjan", verbose_name="Fuseau horaire")
    start_date = models.DateField(blank=True, null=True, verbose_name="Date de début")
    end_date = models.DateField(blank=True, null=True, verbose_name="Date de fin")
    cron_expression = models.CharField(max_length=120, blank=True, null=True,
                                       verbose_name="Expression cron (admin)")
    skip_weekends = models.BooleanField(default=False, verbose_name="Reporter si week-end")
    excluded_dates = models.JSONField(default=list, blank=True,
                                      verbose_name="Dates exclues (ISO)")

    # --- Destinataires ---
    recipient_groups = models.ManyToManyField(AlertRecipientGroup, blank=True,
                                              related_name="configurations")
    recipients = models.ManyToManyField(AlertRecipient, blank=True,
                                        related_name="configurations")

    # --- Périmètre d'analyse ---
    projects = models.ManyToManyField("parcelaire.ProjetImmobilier", blank=True,
                                      related_name="alert_configurations")
    programs = models.ManyToManyField("parcelaire.RealEstateProgram", blank=True,
                                      related_name="alert_configurations")
    lots = models.ManyToManyField("parcelaire.Parcel", blank=True,
                                  related_name="alert_configurations")
    include_all_projects = models.BooleanField(default=False)
    include_all_programs = models.BooleanField(default=True)
    include_all_lots = models.BooleanField(default=True)

    # --- Contenu ---
    include_pdf = models.BooleanField(default=True)
    include_excel = models.BooleanField(default=False)
    email_subject_template = models.CharField(max_length=255, blank=True, null=True)
    email_intro_template = models.TextField(blank=True, null=True)
    minimum_severity = models.CharField(max_length=20, choices=Severity.choices,
                                        default=Severity.INFORMATION,
                                        verbose_name="Sévérité minimale")

    # --- État ---
    is_active = models.BooleanField(default=True, verbose_name="Active")
    last_sent_at = models.DateTimeField(blank=True, null=True)
    next_send_at = models.DateTimeField(blank=True, null=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="alert_configurations")

    class Meta:
        verbose_name = "Configuration d'alerte"
        verbose_name_plural = "Configurations d'alerte"
        ordering = ["name"]
        permissions = [
            ("view_alert_dashboard", "Peut voir le tableau de bord des alertes"),
            ("generate_alertreport", "Peut générer un rapport d'alerte"),
            ("send_alertreport", "Peut envoyer un rapport d'alerte"),
            ("view_all_alertreports", "Peut voir tous les rapports d'alerte"),
            ("download_alertreport", "Peut télécharger un rapport d'alerte"),
        ]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Planification
    # ------------------------------------------------------------------
    def _aware(self, d):
        """Combine une date + l'heure d'envoi en datetime aware (fuseau courant)."""
        naive = datetime.combine(d, self.send_time or time(8, 0))
        if timezone.is_naive(naive):
            return timezone.make_aware(naive, timezone.get_current_timezone())
        return naive

    def _adjust(self, d):
        """Reporte au jour ouvré suivant si week-end / date exclue."""
        excluded = set(self.excluded_dates or [])
        for _ in range(400):
            if self.skip_weekends and d.weekday() >= 5:
                d = d + timedelta(days=1)
                continue
            if d.isoformat() in excluded:
                d = d + timedelta(days=1)
                continue
            return d
        return d

    def compute_next_send_at(self, after=None):
        """Prochaine échéance d'envoi strictement postérieure à `after`
        (défaut : maintenant). Renvoie None si MANUEL ou au-delà de end_date."""
        after = after or timezone.now()
        if self.frequency == Frequency.MANUAL:
            return None
        if self.end_date and after.date() > self.end_date:
            return None

        if self.frequency == Frequency.WEEKLY:
            dow = self.day_of_week or 0
            days_ahead = (dow - after.weekday()) % 7
            d = after.date() + timedelta(days=days_ahead)
            if self._aware(d) <= after:
                d = d + timedelta(days=7)
            d = self._adjust(d)

        elif self.frequency == Frequency.BIWEEKLY:
            d = self.start_date or after.date()
            guard = 0
            while self._aware(d) <= after and guard < 4000:
                d = d + timedelta(days=14)
                guard += 1
            d = self._adjust(d)

        elif self.frequency == Frequency.MONTHLY:
            dom = self.day_of_month or 1
            d = _month_day(after.year, after.month, dom)
            if self._aware(d) <= after:
                y = after.year + (1 if after.month == 12 else 0)
                m = 1 if after.month == 12 else after.month + 1
                d = _month_day(y, m, dom)
            d = self._adjust(d)

        else:  # CUSTOM
            step = self.custom_interval_days or 7
            if self.last_sent_at:
                d = (self.last_sent_at + timedelta(days=step)).date()
            elif self.start_date:
                d = self.start_date
            else:
                d = after.date()
            guard = 0
            while self._aware(d) <= after and guard < 10000:
                d = d + timedelta(days=step)
                guard += 1
            d = self._adjust(d)

        result = self._aware(d)
        if self.end_date and result.date() > self.end_date:
            return None
        return result

    def refresh_next_send_at(self, save=True):
        self.next_send_at = self.compute_next_send_at()
        if save:
            self.save(update_fields=["next_send_at", "updated_at"])
        return self.next_send_at


# =====================================================================
# Détections d'alerte
# =====================================================================

class AlertDetection(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "NEW", "Nouvelle"
        ACKNOWLEDGED = "ACKNOWLEDGED", "Acquittée"
        RESOLVED = "RESOLVED", "Résolue"
        DISMISSED = "DISMISSED", "Ignorée"

    configuration = models.ForeignKey(AlertConfiguration, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name="detections")
    alert_type = models.CharField(max_length=40, choices=AlertType.choices, db_index=True)
    severity = models.CharField(max_length=20, choices=Severity.choices,
                                default=Severity.INFORMATION, db_index=True)

    project = models.ForeignKey("parcelaire.ProjetImmobilier", on_delete=models.CASCADE,
                                null=True, blank=True, related_name="alert_detections")
    program = models.ForeignKey("parcelaire.RealEstateProgram", on_delete=models.CASCADE,
                                null=True, blank=True, related_name="alert_detections")
    block = models.ForeignKey("parcelaire.ProgramBlock", on_delete=models.CASCADE,
                              null=True, blank=True, related_name="alert_detections")
    lot = models.ForeignKey("parcelaire.Parcel", on_delete=models.CASCADE,
                            null=True, blank=True, related_name="alert_detections")
    customer = models.ForeignKey("parcelaire.Customer", on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="alert_detections")

    title = models.CharField(max_length=255)
    message = models.TextField(blank=True, null=True)
    current_value = models.FloatField(blank=True, null=True)
    previous_value = models.FloatField(blank=True, null=True)
    difference = models.FloatField(blank=True, null=True)
    threshold = models.FloatField(blank=True, null=True)
    financial_exposure = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    period_start = models.DateField(blank=True, null=True)
    period_end = models.DateField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.NEW, db_index=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name="acknowledged_detections")
    acknowledged_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Détection d'alerte"
        verbose_name_plural = "Détections d'alerte"
        ordering = ["-detected_at"]
        permissions = [("acknowledge_alert", "Peut acquitter une alerte")]

    def __str__(self):
        return f"[{self.severity}] {self.title}"


# =====================================================================
# Rapports + dispatch (historique d'envoi)
# =====================================================================

class AlertReport(TimeStampedModel):
    class Confidentiality(models.TextChoices):
        INTERNAL = "INTERNAL", "Interne"
        CONFIDENTIAL = "CONFIDENTIAL", "Confidentiel"
        RESTRICTED = "RESTRICTED", "Diffusion restreinte"

    title = models.CharField(max_length=255)
    period_start = models.DateField(blank=True, null=True)
    period_end = models.DateField(blank=True, null=True)
    programs = models.ManyToManyField("parcelaire.RealEstateProgram", blank=True,
                                      related_name="alert_reports")
    file_path = models.CharField(max_length=512, blank=True, null=True)
    checksum = models.CharField(max_length=128, blank=True, null=True)
    confidentiality = models.CharField(max_length=20, choices=Confidentiality.choices,
                                       default=Confidentiality.INTERNAL)
    retention_days = models.IntegerField(choices=Retention.choices, default=Retention.D90)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="alert_reports")
    expires_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Rapport d'alerte"
        verbose_name_plural = "Rapports d'alerte"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class AlertDispatch(TimeStampedModel):
    configuration = models.ForeignKey(AlertConfiguration, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name="dispatches")
    report = models.ForeignKey(AlertReport, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name="dispatches")
    subject = models.CharField(max_length=255, blank=True, null=True)
    period_start = models.DateField(blank=True, null=True)
    period_end = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=DispatchStatus.choices,
                              default=DispatchStatus.PENDING, db_index=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    celery_task_id = models.CharField(max_length=100, blank=True, null=True)
    email_count = models.PositiveIntegerField(default=0)
    attachment_path = models.CharField(max_length=512, blank=True, null=True)
    checksum = models.CharField(max_length=128, blank=True, null=True)
    is_preview = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Envoi d'alerte"
        verbose_name_plural = "Envois d'alerte"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject or 'Envoi'} [{self.status}]"


class AlertDispatchRecipient(TimeStampedModel):
    class DeliveryStatus(models.TextChoices):
        PENDING = "PENDING", "En attente"
        SENT = "SENT", "Envoyé"
        FAILED = "FAILED", "Échec"

    dispatch = models.ForeignKey(AlertDispatch, on_delete=models.CASCADE, related_name="deliveries")
    recipient = models.ForeignKey(AlertRecipient, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="deliveries")
    email = models.EmailField(blank=True, null=True)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    status = models.CharField(max_length=20, choices=DeliveryStatus.choices,
                              default=DeliveryStatus.PENDING)
    error = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Livraison d'alerte"
        verbose_name_plural = "Livraisons d'alerte"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email or self.recipient} [{self.status}]"


# =====================================================================
# Snapshots d'historisation (indispensables aux variations entre périodes)
# =====================================================================

class ConstructionProgressSnapshot(TimeStampedModel):
    program = models.ForeignKey("parcelaire.RealEstateProgram", on_delete=models.CASCADE,
                                related_name="construction_snapshots")
    block = models.ForeignKey("parcelaire.ProgramBlock", on_delete=models.CASCADE,
                              null=True, blank=True, related_name="construction_snapshots")
    lot = models.ForeignKey("parcelaire.Parcel", on_delete=models.CASCADE,
                            null=True, blank=True, related_name="construction_snapshots")
    progress_percent = models.FloatField(default=0)
    source = models.CharField(max_length=60, default="system")
    recorded_at = models.DateField(default=date.today, db_index=True)

    class Meta:
        verbose_name = "Instantané de construction"
        verbose_name_plural = "Instantanés de construction"
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["program", "recorded_at"])]

    def __str__(self):
        return f"{self.program_id} @ {self.recorded_at} = {self.progress_percent}%"


class PaymentSnapshot(TimeStampedModel):
    program = models.ForeignKey("parcelaire.RealEstateProgram", on_delete=models.CASCADE,
                                related_name="payment_snapshots")
    lot = models.ForeignKey("parcelaire.Parcel", on_delete=models.CASCADE,
                            null=True, blank=True, related_name="payment_snapshots")
    customer = models.ForeignKey("parcelaire.Customer", on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="payment_snapshots")
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    payment_rate = models.FloatField(default=0)
    recorded_at = models.DateField(default=date.today, db_index=True)

    class Meta:
        verbose_name = "Instantané de paiement"
        verbose_name_plural = "Instantanés de paiement"
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["program", "recorded_at"])]

    def __str__(self):
        return f"{self.program_id} @ {self.recorded_at} = {self.payment_rate}%"


class CommercializationSnapshot(TimeStampedModel):
    program = models.ForeignKey("parcelaire.RealEstateProgram", on_delete=models.CASCADE,
                                related_name="commercialization_snapshots")
    available_count = models.PositiveIntegerField(default=0)
    reserved_count = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    blocked_count = models.PositiveIntegerField(default=0)
    commercialization_rate = models.FloatField(default=0)
    recorded_at = models.DateField(default=date.today, db_index=True)

    class Meta:
        verbose_name = "Instantané de commercialisation"
        verbose_name_plural = "Instantanés de commercialisation"
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["program", "recorded_at"])]

    def __str__(self):
        return f"{self.program_id} @ {self.recorded_at} = {self.commercialization_rate}%"
