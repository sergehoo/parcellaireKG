from rest_framework.routers import DefaultRouter
from .views import ConstructionSimulationViewSet

router = DefaultRouter()
router.register("construction-simulations", ConstructionSimulationViewSet, basename="construction-simulation")

urlpatterns = router.urls