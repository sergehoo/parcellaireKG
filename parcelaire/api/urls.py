from django.urls import path

from parcelaire.api.views import RealEstateMapAPIView
from parcelaire.views import RealEstateMap3DView

urlpatterns = [
    path("map/assets/", RealEstateMapAPIView.as_view(), name="api-map-assets"),
    path("map/3d/", RealEstateMap3DView.as_view(), name="real-estate-map-3d"),

]