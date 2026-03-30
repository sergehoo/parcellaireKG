from django.shortcuts import render

# Create your views here.

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import ConstructionSimulationProject
from .serializers import (
    ConstructionSimulationProjectSerializer,
    ConstructionSimulationCreateSerializer,
)
from .permissions import CanManageConstructionSimulation
from .tasks import launch_simulation


class ConstructionSimulationViewSet(viewsets.ModelViewSet):
    queryset = ConstructionSimulationProject.objects.all().prefetch_related("scenes", "assets")
    permission_classes = [IsAuthenticated, CanManageConstructionSimulation]

    def get_serializer_class(self):
        if self.action == "create":
            return ConstructionSimulationCreateSerializer
        return ConstructionSimulationProjectSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, status="DRAFT")

    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        simulation = self.get_object()
        simulation.status = "QUEUED"
        simulation.save(update_fields=["status", "updated_at"])
        launch_simulation.delay(str(simulation.id))
        return Response({"detail": "Génération lancée."}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        simulation = self.get_object()
        simulation.status = "CANCELED"
        simulation.save(update_fields=["status", "updated_at"])
        return Response({"detail": "Simulation annulée."})

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        simulation = self.get_object()
        return Response({
            "status": simulation.status,
            "progress_percent": simulation.progress_percent,
            "completed_scenes": simulation.completed_scenes,
            "total_scenes": simulation.total_scenes,
            "error_message": simulation.error_message,
            "final_video": simulation.final_video.url if simulation.final_video else None,
        })
