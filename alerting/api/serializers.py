from rest_framework import serializers

from alerting.models import (
    AlertConfiguration, AlertDetection, AlertDispatch, AlertRecipient,
    AlertRecipientGroup, AlertReport, AlertThreshold, Severity,
)


class AlertRecipientSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = AlertRecipient
        fields = [
            "id", "first_name", "last_name", "email", "phone_number", "job_title",
            "department", "company", "preferred_channel", "receive_email",
            "receive_sms", "receive_pdf", "is_active", "display_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_display_name(self, obj):
        return str(obj)


class AlertRecipientGroupSerializer(serializers.ModelSerializer):
    recipients_count = serializers.SerializerMethodField()

    class Meta:
        model = AlertRecipientGroup
        fields = ["id", "name", "description", "recipients", "recipients_count",
                  "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def get_recipients_count(self, obj):
        return obj.recipients.count()


class AlertThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertThreshold
        fields = ["id", "label", "vigilance_min", "important_min", "critical_min",
                  "stagnation_days", "high_exposure_amount", "is_active",
                  "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class AlertConfigurationSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source="get_alert_type_display", read_only=True)
    frequency_display = serializers.CharField(source="get_frequency_display", read_only=True)

    class Meta:
        model = AlertConfiguration
        fields = [
            "id", "name", "description", "alert_type", "alert_type_display",
            "frequency", "frequency_display", "custom_interval_days", "day_of_week",
            "day_of_month", "send_time", "timezone", "start_date", "end_date",
            "cron_expression", "skip_weekends", "excluded_dates",
            "recipient_groups", "recipients", "projects", "programs", "lots",
            "include_all_projects", "include_all_programs", "include_all_lots",
            "include_pdf", "include_excel", "email_subject_template",
            "email_intro_template", "minimum_severity", "is_active",
            "last_sent_at", "next_send_at", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["last_sent_at", "next_send_at", "created_by",
                            "created_at", "updated_at"]

    def create(self, validated_data):
        cfg = super().create(validated_data)
        cfg.refresh_next_send_at()  # calcule la 1re échéance dès la création
        return cfg

    def update(self, instance, validated_data):
        cfg = super().update(instance, validated_data)
        cfg.refresh_next_send_at()  # la planification a pu changer
        return cfg


class AlertDetectionSerializer(serializers.ModelSerializer):
    severity_label = serializers.SerializerMethodField()
    alert_type_display = serializers.CharField(source="get_alert_type_display", read_only=True)
    program_name = serializers.CharField(source="program.name", read_only=True, default=None)
    lot_label = serializers.SerializerMethodField()

    class Meta:
        model = AlertDetection
        fields = [
            "id", "alert_type", "alert_type_display", "severity", "severity_label",
            "program", "program_name", "block", "lot", "lot_label", "customer",
            "title", "message", "current_value", "previous_value", "difference",
            "threshold", "financial_exposure", "detected_at", "period_start",
            "period_end", "status", "acknowledged_by", "acknowledged_at", "metadata",
        ]
        read_only_fields = fields

    def get_severity_label(self, obj):
        return Severity(obj.severity).label

    def get_lot_label(self, obj):
        if not obj.lot_id:
            return None
        return obj.lot.lot_number or obj.lot.parcel_code or f"#{obj.lot_id}"

    def to_representation(self, obj):
        from parcelaire.api.views import (
            user_can_view_financial_data, user_can_view_patient_data,
        )
        data = super().to_representation(obj)
        req = self.context.get("request")
        user = getattr(req, "user", None)
        if not (user and user_can_view_financial_data(user)):
            data["financial_exposure"] = None  # montant masqué
        if not (user and user_can_view_patient_data(user)):
            # message/metadata portent des noms de clients → masqués sans droit PII
            # (le titre ne contient que le n° de lot).
            data["message"] = None
            data["metadata"] = {}
            data["customer"] = None
        return data


class AlertReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertReport
        fields = ["id", "title", "period_start", "period_end", "confidentiality",
                  "checksum", "retention_days", "created_at"]
        read_only_fields = fields


class AlertDispatchSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    report = AlertReportSerializer(read_only=True)
    configuration_name = serializers.CharField(source="configuration.name", read_only=True, default=None)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = AlertDispatch
        fields = [
            "id", "configuration", "configuration_name", "report", "subject",
            "period_start", "period_end", "status", "status_display", "email_count",
            "is_preview", "error_message", "started_at", "completed_at", "sent_at",
            "duration_seconds", "created_at",
        ]
        read_only_fields = fields

    def get_duration_seconds(self, obj):
        if obj.started_at and obj.completed_at:
            return round((obj.completed_at - obj.started_at).total_seconds(), 1)
        return None
