from django.contrib import admin

from .models import (
    AlertConfiguration, AlertDetection, AlertDispatch, AlertDispatchRecipient,
    AlertRecipient, AlertRecipientGroup, AlertReport, AlertRule, AlertThreshold,
    CommercializationSnapshot, ConstructionProgressSnapshot, PaymentSnapshot,
)


@admin.register(AlertRecipient)
class AlertRecipientAdmin(admin.ModelAdmin):
    list_display = ("__str__", "email", "department", "preferred_channel", "is_active")
    list_filter = ("is_active", "preferred_channel", "department")
    search_fields = ("first_name", "last_name", "email", "company")


@admin.register(AlertRecipientGroup)
class AlertRecipientGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    filter_horizontal = ("recipients",)
    search_fields = ("name",)


@admin.register(AlertThreshold)
class AlertThresholdAdmin(admin.ModelAdmin):
    list_display = ("label", "vigilance_min", "important_min", "critical_min", "is_active")
    list_filter = ("is_active",)


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "alert_type", "is_enabled", "severity_floor")
    list_filter = ("alert_type", "is_enabled")


@admin.register(AlertConfiguration)
class AlertConfigurationAdmin(admin.ModelAdmin):
    list_display = ("name", "alert_type", "frequency", "minimum_severity",
                    "is_active", "next_send_at", "last_sent_at")
    list_filter = ("alert_type", "frequency", "is_active", "minimum_severity")
    search_fields = ("name",)
    filter_horizontal = ("recipient_groups", "recipients", "projects", "programs", "lots")
    readonly_fields = ("next_send_at", "last_sent_at")


@admin.register(AlertDetection)
class AlertDetectionAdmin(admin.ModelAdmin):
    list_display = ("title", "alert_type", "severity", "program", "status", "detected_at")
    list_filter = ("severity", "alert_type", "status")
    search_fields = ("title", "message")
    date_hierarchy = "detected_at"


@admin.register(AlertReport)
class AlertReportAdmin(admin.ModelAdmin):
    list_display = ("title", "period_start", "period_end", "confidentiality", "created_at")
    list_filter = ("confidentiality",)


@admin.register(AlertDispatch)
class AlertDispatchAdmin(admin.ModelAdmin):
    list_display = ("subject", "status", "email_count", "period_start", "period_end", "created_at")
    list_filter = ("status", "is_preview")
    date_hierarchy = "created_at"


admin.site.register(AlertDispatchRecipient)
admin.site.register(ConstructionProgressSnapshot)
admin.site.register(PaymentSnapshot)
admin.site.register(CommercializationSnapshot)
