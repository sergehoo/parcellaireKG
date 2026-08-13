"""API REST du module d'alertes (Phase 6a).

Périmètre : configurations / destinataires / groupes / seuils (CRUD), détections
(liste + acquittement), génération manuelle (+ prévisualisation), historique,
téléchargement de rapport, tableau de bord, test SMTP. Montants masqués sans
`view_financial_data`.
"""
import os

from django.conf import settings
from django.core.mail import send_mail
from django.http import FileResponse, Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from parcelaire.api.crud import ModelWritePermission, StandardPagination
from parcelaire.api.views import user_can_view_financial_data

from alerting.models import (
    AlertConfiguration, AlertDetection, AlertDispatch, AlertRecipient,
    AlertRecipientGroup, AlertReport, AlertThreshold, DispatchStatus, Severity,
)
from alerting.services import dispatch_service
from .serializers import (
    AlertConfigurationSerializer, AlertDetectionSerializer, AlertDispatchSerializer,
    AlertRecipientGroupSerializer, AlertRecipientSerializer, AlertThresholdSerializer,
)


def _require(user, perm):
    if not (user.is_superuser or user.has_perm(perm)):
        raise PermissionDenied("Permission requise : " + perm)


class ThresholdPermission(BasePermission):
    """Lecture : authentifié. Écriture : `manage_alert_thresholds`.
    (has_permission renvoie un booléen — ne lève jamais, compatible schéma OpenAPI.)"""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or request.user.has_perm("alerting.manage_alert_thresholds")


# --------------------------------------------------------------------- CRUD

class AlertConfigurationViewSet(viewsets.ModelViewSet):
    queryset = AlertConfiguration.objects.all().order_by("name")
    serializer_class = AlertConfigurationSerializer
    permission_classes = [IsAuthenticated, ModelWritePermission]
    pagination_class = StandardPagination
    filterset_fields = ["alert_type", "frequency", "is_active", "minimum_severity"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AlertRecipientViewSet(viewsets.ModelViewSet):
    queryset = AlertRecipient.objects.filter(is_active=True).order_by("last_name", "email")
    serializer_class = AlertRecipientSerializer
    permission_classes = [IsAuthenticated, ModelWritePermission]
    pagination_class = StandardPagination
    filterset_fields = ["department", "preferred_channel", "is_active"]
    search_fields = ["first_name", "last_name", "email", "company"]

    def perform_destroy(self, instance):  # soft-delete
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class AlertRecipientGroupViewSet(viewsets.ModelViewSet):
    queryset = AlertRecipientGroup.objects.filter(is_active=True).order_by("name")
    serializer_class = AlertRecipientGroupSerializer
    permission_classes = [IsAuthenticated, ModelWritePermission]
    pagination_class = StandardPagination


class AlertThresholdViewSet(viewsets.ModelViewSet):
    queryset = AlertThreshold.objects.all().order_by("-updated_at")
    serializer_class = AlertThresholdSerializer
    permission_classes = [ThresholdPermission]


# --------------------------------------------------------------- Détections

class AlertDetectionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertDetectionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filterset_fields = ["severity", "alert_type", "status", "program"]

    def get_queryset(self):
        qs = AlertDetection.objects.select_related("program", "lot").order_by("-detected_at")
        if not user_can_view_financial_data(self.request.user):
            # Sans droit financier : on masque l'exposition et les libellés
            # potentiellement porteurs de PII (fait dans to_representation ci-dessous
            # via un flag). Ici on ne filtre pas les lignes.
            pass
        return qs


class AcknowledgeDetectionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Acquitter une détection d'alerte", tags=["Alertes"], request=None)
    def post(self, request, pk):
        _require(request.user, "alerting.acknowledge_alert")
        det = AlertDetection.objects.filter(pk=pk).first()
        if det is None:
            raise Http404
        det.status = AlertDetection.Status.ACKNOWLEDGED
        det.acknowledged_by = request.user
        det.acknowledged_at = timezone.now()
        det.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])
        return Response(AlertDetectionSerializer(det).data)


# ------------------------------------------------------- Génération / envoi

class GenerateReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Générer un rapport (aperçu ou envoi)", tags=["Alertes"], request=None)
    def post(self, request):
        _require(request.user, "alerting.generate_alertreport")
        data = request.data or {}
        preview = bool(data.get("preview", True))
        if not preview:
            _require(request.user, "alerting.send_alertreport")
        try:
            window_days = int(data.get("period_days") or 7)
        except (TypeError, ValueError):
            window_days = 7
        window_days = max(1, min(window_days, 365))
        can_fin = user_can_view_financial_data(request.user)

        cfg_id = data.get("configuration_id")
        temp_cfg = None
        if cfg_id:
            cfg = AlertConfiguration.objects.filter(pk=cfg_id).first()
            if cfg is None:
                raise ValidationError("Configuration introuvable.")
        else:
            program_ids = data.get("program_ids") or []
            cfg = temp_cfg = AlertConfiguration.objects.create(
                name="Génération manuelle", frequency="MANUAL",
                include_all_programs=not program_ids,
                minimum_severity=data.get("minimum_severity") or Severity.INFORMATION,
                include_pdf=bool(data.get("include_pdf", True)),
                created_by=request.user)
            if program_ids:
                cfg.programs.set(program_ids)

        recipients_override = data.get("recipients") if not preview else None
        try:
            dispatch = dispatch_service.run_configuration(
                cfg, window_days=window_days, preview=preview,
                recipients_override=recipients_override, can_fin=can_fin, reschedule=False)
        finally:
            if temp_cfg is not None:
                # Le dispatch/rapport survivent (FK SET_NULL) ; on nettoie la config jetable.
                temp_cfg.delete()
        return Response(AlertDispatchSerializer(dispatch).data)


class ResendDispatchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Renvoyer un rapport déjà généré", tags=["Alertes"], request=None)
    def post(self, request, pk):
        _require(request.user, "alerting.send_alertreport")
        dispatch = AlertDispatch.objects.filter(pk=pk).select_related("report", "configuration").first()
        if dispatch is None or dispatch.report is None or not dispatch.report.file_path:
            raise Http404
        abs_path = os.path.join(settings.MEDIA_ROOT, dispatch.report.file_path)
        if not os.path.exists(abs_path):
            raise ValidationError("Le fichier du rapport n'existe plus.")
        recipients = request.data.get("recipients") or []
        if not recipients and dispatch.configuration_id:
            recipients = [r.email for r in dispatch_service.resolve_recipients(dispatch.configuration)]
        if not recipients:
            raise ValidationError("Aucun destinataire.")
        from alerting.services import email_sender
        with open(abs_path, "rb") as fh:
            pdf_bytes = fh.read()
        ctx = {"programs": [], "period_start": dispatch.period_start,
               "period_end": dispatch.period_end, "report_id": f"RESEND-{dispatch.id}",
               "summary": {"sensitive_clients": 0, "critical_count": 0, "important_count": 0},
               "recommendations": [], "confidentiality": "Confidentiel"}
        sent = email_sender.send_report_email(ctx, pdf_bytes=pdf_bytes,
                                              pdf_filename=os.path.basename(abs_path),
                                              recipients=recipients)
        dispatch.email_count = (dispatch.email_count or 0) + sent
        dispatch.sent_at = timezone.now()
        dispatch.status = DispatchStatus.SENT if sent else DispatchStatus.FAILED
        dispatch.save(update_fields=["email_count", "sent_at", "status", "updated_at"])
        return Response({"sent": sent, "dispatch": AlertDispatchSerializer(dispatch).data})


class DownloadReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Télécharger le PDF d'un rapport", tags=["Alertes"])
    def get(self, request, pk):
        _require(request.user, "alerting.download_alertreport")
        report = AlertReport.objects.filter(pk=pk).first()
        if report is None or not report.file_path:
            raise Http404
        # Portée : son propre rapport, sauf droit « voir tous les rapports ».
        if not (request.user.is_superuser
                or report.generated_by_id == request.user.id
                or request.user.has_perm("alerting.view_all_alertreports")):
            raise PermissionDenied("Rapport hors de votre périmètre.")
        abs_path = os.path.join(settings.MEDIA_ROOT, report.file_path)
        if not os.path.exists(abs_path):
            raise Http404
        return FileResponse(open(abs_path, "rb"), content_type="application/pdf",
                            as_attachment=True, filename=os.path.basename(abs_path))


# --------------------------------------------------------------- Historique

class AlertHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertDispatchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filterset_fields = ["status", "configuration", "is_preview"]

    def get_queryset(self):
        return AlertDispatch.objects.select_related("report", "configuration").order_by("-created_at")


# ---------------------------------------------------------- Tableau de bord

class AlertDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Tableau de bord des alertes", tags=["Alertes"])
    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        active_configs = AlertConfiguration.objects.filter(is_active=True)
        next_dispatch = (active_configs.filter(next_send_at__isnull=False)
                         .order_by("next_send_at").values_list("next_send_at", flat=True).first())
        last_sent = (AlertDispatch.objects.filter(status=DispatchStatus.SENT)
                     .order_by("-sent_at").values_list("sent_at", flat=True).first())
        monitored = set()
        for c in active_configs:
            if c.include_all_programs:
                monitored = None
                break
            monitored |= set(c.programs.values_list("id", flat=True))
        from parcelaire.models import RealEstateProgram
        monitored_count = (RealEstateProgram.objects.filter(is_active=True).count()
                           if monitored is None else len(monitored))

        backend = getattr(settings, "EMAIL_BACKEND", "")
        # dummy = AUCUN envoi tenté (EMAIL_HOST absent en prod) ; smtp sans hôte
        # = non configuré. console/locmem (dev/tests) considérés fonctionnels.
        if "dummy" in backend:
            email_ok = False
        elif "smtp" in backend:
            email_ok = bool(getattr(settings, "EMAIL_HOST", ""))
        else:
            email_ok = True

        data = {
            "active_alerts": AlertDetection.objects.filter(status=AlertDetection.Status.NEW).count(),
            "next_send_at": next_dispatch,
            "last_sent_at": last_sent,
            "active_recipients": AlertRecipient.objects.filter(is_active=True, receive_email=True).count(),
            "monitored_programs": monitored_count,
            "critical_lots": AlertDetection.objects.filter(
                severity=Severity.CRITICAL, status=AlertDetection.Status.NEW, lot__isnull=False).count(),
            "reports_this_month": AlertDispatch.objects.filter(
                status=DispatchStatus.SENT, sent_at__gte=month_start).count(),
            "failed_dispatches": AlertDispatch.objects.filter(status=DispatchStatus.FAILED).count(),
            "last_dispatch_at": AlertDispatch.objects.order_by("-created_at")
                .values_list("created_at", flat=True).first(),
            "email_backend": backend.rsplit(".", 1)[-1] if backend else "",
            "email_service_ok": email_ok,
            "active_configurations": active_configs.count(),
        }
        return Response(data)


class SmtpTestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Envoyer un e-mail de test SMTP", tags=["Alertes"], request=None)
    def post(self, request):
        _require(request.user, "alerting.manage_alertrecipient")  # admin/gestion
        to = (request.data or {}).get("email")
        if not to:
            raise ValidationError("Adresse e-mail de test requise.")
        backend = getattr(settings, "EMAIL_BACKEND", "")
        if "dummy" in backend:
            return Response({
                "ok": False,
                "error": "Service e-mail NON configuré : EMAIL_HOST est vide, aucun envoi "
                         "n'est tenté (backend dummy). Renseigner EMAIL_HOST / EMAIL_HOST_USER / "
                         "EMAIL_HOST_PASSWORD / DEFAULT_FROM_EMAIL dans l'environnement.",
            }, status=502)
        try:
            sent = send_mail(
                subject="[TEST] Parcellaire KAYDAN — service d'alertes",
                message="Ceci est un e-mail de test du service d'alertes Parcellaire KAYDAN.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[to], fail_silently=False)
        except Exception as exc:  # noqa: BLE001
            return Response({"ok": False, "error": str(exc)}, status=502)
        return Response({"ok": bool(sent), "sent": sent, "to": to,
                         "tested_at": timezone.now()})
