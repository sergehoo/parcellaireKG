from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcknowledgeDetectionAPIView, AlertConfigurationViewSet, AlertDashboardAPIView,
    AlertDetectionViewSet, AlertHistoryViewSet, AlertRecipientGroupViewSet,
    AlertRecipientViewSet, AlertThresholdViewSet, DownloadReportAPIView,
    GenerateReportAPIView, ResendDispatchAPIView, SmtpTestAPIView,
)

router = DefaultRouter()
router.register("configurations", AlertConfigurationViewSet, basename="alert-configuration")
router.register("recipients", AlertRecipientViewSet, basename="alert-recipient")
router.register("groups", AlertRecipientGroupViewSet, basename="alert-group")
router.register("thresholds", AlertThresholdViewSet, basename="alert-threshold")
router.register("detections", AlertDetectionViewSet, basename="alert-detection")
router.register("history", AlertHistoryViewSet, basename="alert-history")

urlpatterns = [
    path("dashboard/", AlertDashboardAPIView.as_view(), name="alert-dashboard"),
    path("detections/<int:pk>/acknowledge/", AcknowledgeDetectionAPIView.as_view(),
         name="alert-detection-acknowledge"),
    path("reports/generate/", GenerateReportAPIView.as_view(), name="alert-report-generate"),
    path("reports/<int:pk>/download/", DownloadReportAPIView.as_view(), name="alert-report-download"),
    path("dispatches/<int:pk>/send/", ResendDispatchAPIView.as_view(), name="alert-dispatch-send"),
    path("smtp/test/", SmtpTestAPIView.as_view(), name="alert-smtp-test"),
    path("", include(router.urls)),
]
