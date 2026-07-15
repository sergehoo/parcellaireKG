from django.urls import path

from parcelaire.api import orthophotos as ortho_api
from parcelaire.api.views import RealEstateMapAPIView
from parcelaire.views import RealEstateMap3DView

urlpatterns = [
    path("map/assets/", RealEstateMapAPIView.as_view(), name="api-map-assets"),
    path("map/3d/", RealEstateMap3DView.as_view(), name="real-estate-map-3d"),
    # path("sap/health/", SAPHealthCheckView.as_view(), name="sap_health"),

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
