from django.urls import include, path
from rest_framework.routers import DefaultRouter

from parcelaire.api import crud as crud_api
from parcelaire.api import orthophotos as ortho_api
from parcelaire.api.analytics import (
    AlertActionAPIView,
    AlertExportAPIView,
    AlertListAPIView,
    AlertMapAPIView,
    AlertRegenerateAPIView,
    AlertSummaryAPIView,
    AnalyticsDashboardAPIView,
    AtRiskClientsAPIView,
    AtRiskExportAPIView,
)
from parcelaire.api.dashboard import DashboardStatsAPIView
from parcelaire.api.views import RealEstateMapAPIView
from parcelaire.views import RealEstateMap3DView

router = DefaultRouter()
router.register("projects", crud_api.ProjectViewSet, basename="api-project")
router.register("programs", crud_api.ProgramViewSet, basename="api-program")
router.register("customers", crud_api.CustomerViewSet, basename="api-customer")
router.register("parcels", crud_api.ParcelViewSet, basename="api-parcel")
router.register("reservations", crud_api.ReservationViewSet, basename="api-reservation")
router.register("sales", crud_api.SaleViewSet, basename="api-sale")
router.register("payments", crud_api.PaymentViewSet, basename="api-payment")

urlpatterns = [
    path("map/assets/", RealEstateMapAPIView.as_view(), name="api-map-assets"),
    path("map/3d/", RealEstateMap3DView.as_view(), name="real-estate-map-3d"),
    # path("sap/health/", SAPHealthCheckView.as_view(), name="sap_health"),

    # -------- Tableau de bord + CRUD (frontend React) --------
    path("dashboard/", DashboardStatsAPIView.as_view(), name="api-dashboard"),
    # -------- Moteur d'analyse décisionnel --------
    path("analytics/dashboard/", AnalyticsDashboardAPIView.as_view(), name="api-analytics-dashboard"),
    path("analytics/at-risk/", AtRiskClientsAPIView.as_view(), name="api-analytics-at-risk"),
    path("analytics/at-risk/export/", AtRiskExportAPIView.as_view(), name="api-analytics-at-risk-export"),
    # -------- Centre de notifications (alertes persistées) --------
    path("alerts/", AlertListAPIView.as_view(), name="api-alerts"),
    path("alerts/summary/", AlertSummaryAPIView.as_view(), name="api-alert-summary"),
    path("alerts/map/", AlertMapAPIView.as_view(), name="api-alert-map"),
    path("alerts/regenerate/", AlertRegenerateAPIView.as_view(), name="api-alert-regenerate"),
    path("alerts/export/", AlertExportAPIView.as_view(), name="api-alert-export"),
    path("alerts/<int:pk>/<str:action>/", AlertActionAPIView.as_view(), name="api-alert-action"),
    path("crud/options/", crud_api.CrudOptionsAPIView.as_view(), name="api-crud-options"),
    path("crud/", include(router.urls)),

    # -------- ORTHOPHOTOS (frontend React) --------
    # NB : l'upload multipart S3 (init/complete/abort) et le polling de
    # statut restent sur /orthophotos/... (JSON, déjà en place).
    path("orthophotos/csrf/", ortho_api.csrf_prime, name="api-orthophoto-csrf"),
    path("orthophotos/reference-data/", ortho_api.OrthophotoReferenceDataAPIView.as_view(),
         name="api-orthophoto-refdata"),
    path("orthophotos/", ortho_api.OrthophotoListAPIView.as_view(),
         name="api-orthophoto-list"),
    path("orthophotos/<int:pk>/", ortho_api.OrthophotoDetailAPIView.as_view(),
         name="api-orthophoto-detail"),
    path("orthophotos/<int:pk>/retry/", ortho_api.OrthophotoRetryAPIView.as_view(),
         name="api-orthophoto-retry"),
    path("orthophotos/<int:pk>/set-current/", ortho_api.OrthophotoSetCurrentAPIView.as_view(),
         name="api-orthophoto-set-current"),
    path("orthophotos/<int:pk>/delete-tiles/", ortho_api.OrthophotoDeleteTilesAPIView.as_view(),
         name="api-orthophoto-delete-tiles"),
]
