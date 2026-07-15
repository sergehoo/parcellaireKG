"""
API REST orthophotos — consommée par le frontend React (frontend/).

Les endpoints d'upload multipart S3 (init / complete / abort) et le
polling de statut existent déjà en JSON dans parcelaire/views.py ;
ici on expose uniquement ce qui manquait au SPA : liste filtrée,
détail + logs, actions (retry / set-current / delete-tiles) et les
données de référence pour les filtres et le formulaire.

Authentification : session Django (mêmes cookies que le reste du site).
Le endpoint `csrf_prime` pose le cookie csrftoken pour que le SPA
puisse envoyer l'en-tête X-CSRFToken sur les POST.
"""
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings as dj_settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from parcelaire.models import (
    ProgramOrthophoto,
    ProjetImmobilier,
    RealEstateProgram,
)


@ensure_csrf_cookie
def csrf_prime(request):
    """GET /api/orthophotos/csrf/ — pose le cookie csrftoken."""
    return JsonResponse({"ok": True})


# =====================================================================
# Sérialisation (dicts simples, même style que RealEstateMapAPIView)
# =====================================================================

def _bounds_latlng(ortho):
    """Emprise au format Leaflet [[south, west], [north, east]]."""
    if not ortho.bounds:
        return None
    xmin, ymin, xmax, ymax = ortho.bounds.extent  # lon/lat
    return [[ymin, xmin], [ymax, xmax]]


def serialize_orthophoto(ortho, *, with_logs=False):
    data = {
        "id": ortho.pk,
        "name": ortho.name or "",
        "slug": ortho.slug or "",
        "program": {
            "id": ortho.program_id,
            "name": ortho.program.name,
            "project": {
                "id": ortho.program.project_id,
                "name": getattr(ortho.program.project, "nom", "") or "",
            } if ortho.program.project_id else None,
        },
        "period_label": ortho.period_label or "",
        "reference_year": ortho.reference_year,
        "reference_month": ortho.reference_month,
        "capture_date": ortho.capture_date.isoformat() if ortho.capture_date else None,
        "version": ortho.version or "",
        "status": ortho.status,
        "status_display": ortho.get_status_display(),
        "progress_percent": ortho.progress_percent or 0,
        "current_step": ortho.current_step or "",
        "error_message": ortho.error_message or "",
        "is_current": bool(ortho.is_current),
        "is_active": bool(ortho.is_active),
        "min_zoom": ortho.min_zoom,
        "max_zoom": ortho.max_zoom,
        "max_native_zoom": ortho.max_native_zoom,
        "tiles_url": ortho.tiles_url or "",
        "bounds": _bounds_latlng(ortho),
        "created_by": ortho.created_by.get_username() if ortho.created_by_id else None,
        "created_at": ortho.created_at.isoformat() if ortho.created_at else None,
        "updated_at": ortho.updated_at.isoformat() if ortho.updated_at else None,
        "processed_at": ortho.processed_at.isoformat() if ortho.processed_at else None,
    }
    if with_logs:
        data["logs"] = [
            {
                "id": log.pk,
                "level": log.level,
                "message": log.message,
                "command": log.command or "",
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in ortho.processing_logs.all()[:200]
        ]
    return data


# =====================================================================
# Endpoints
# =====================================================================

class OrthophotoListAPIView(APIView):
    """GET /api/orthophotos/ — liste paginée + filtres (mêmes filtres
    que OrthophotoListView côté templates)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            ProgramOrthophoto.objects
            .select_related("program", "program__project", "created_by")
            .order_by("-reference_year", "-reference_month", "-created_at")
        )
        params = request.query_params
        if params.get("project"):
            qs = qs.filter(program__project_id=params["project"])
        if params.get("program"):
            qs = qs.filter(program_id=params["program"])
        if params.get("year"):
            qs = qs.filter(reference_year=params["year"])
        if params.get("month"):
            qs = qs.filter(reference_month=params["month"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(period_label__icontains=q)
                | Q(program__name__icontains=q)
                | Q(program__project__nom__icontains=q)
            )

        try:
            page_size = min(max(int(params.get("page_size", 24)), 1), 100)
        except ValueError:
            page_size = 24
        paginator = Paginator(qs, page_size)
        try:
            page_number = int(params.get("page", 1))
        except ValueError:
            page_number = 1
        page = paginator.get_page(page_number)

        return Response({
            "count": paginator.count,
            "page": page.number,
            "pages": paginator.num_pages,
            "page_size": page_size,
            "results": [serialize_orthophoto(o) for o in page.object_list],
        })


class OrthophotoDetailAPIView(APIView):
    """GET /api/orthophotos/<pk>/ — détail + 200 derniers logs."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        ortho = get_object_or_404(
            ProgramOrthophoto.objects
            .select_related("program", "program__project", "created_by")
            .prefetch_related("processing_logs"),
            pk=pk,
        )
        return Response(serialize_orthophoto(ortho, with_logs=True))


class OrthophotoRetryAPIView(APIView):
    """POST /api/orthophotos/<pk>/retry/ — relance le pipeline GDAL."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ortho = get_object_or_404(ProgramOrthophoto, pk=pk)
        ortho.status = "PENDING"
        ortho.progress_percent = 0
        ortho.current_step = "Relance demandée"
        ortho.error_message = None
        ortho.processed_at = None
        ortho.save(update_fields=[
            "status", "progress_percent", "current_step",
            "error_message", "processed_at", "updated_at",
        ])
        try:
            from parcelaire.tasks import process_orthophoto
            process_orthophoto.delay(ortho.pk)
        except Exception as exc:  # noqa: BLE001
            return Response(
                {"detail": f"Orthophoto réinitialisée mais Celery injoignable : {exc}",
                 "orthophoto": serialize_orthophoto(ortho)},
                status=202,
            )
        return Response({"detail": "Traitement relancé.",
                         "orthophoto": serialize_orthophoto(ortho)})


class OrthophotoSetCurrentAPIView(APIView):
    """POST /api/orthophotos/<pk>/set-current/ — définit la courante."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ortho = get_object_or_404(ProgramOrthophoto, pk=pk)
        ProgramOrthophoto.objects.filter(
            program=ortho.program,
        ).exclude(pk=ortho.pk).update(is_current=False)
        ortho.is_current = True
        ortho.save(update_fields=["is_current", "updated_at"])
        return Response({"detail": "Définie comme orthophoto courante.",
                         "orthophoto": serialize_orthophoto(ortho)})


class OrthophotoDeleteTilesAPIView(APIView):
    """POST /api/orthophotos/<pk>/delete-tiles/ — purge les tuiles
    et repasse le statut à PENDING (même logique que la vue template)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ortho = get_object_or_404(ProgramOrthophoto, pk=pk)
        tiles_root = Path(dj_settings.MEDIA_ROOT) / (ortho.tiles_folder or "")
        if ortho.tiles_folder and tiles_root.exists():
            try:
                shutil.rmtree(tiles_root)
            except OSError as exc:
                return Response(
                    {"detail": f"Échec de suppression des tuiles : {exc}"},
                    status=500,
                )
        ortho.tiles_url = None
        ortho.tiles_folder = None
        ortho.status = "PENDING"
        ortho.progress_percent = 0
        ortho.current_step = "Tuiles supprimées"
        ortho.save(update_fields=[
            "tiles_url", "tiles_folder", "status",
            "progress_percent", "current_step", "updated_at",
        ])
        return Response({"detail": "Tuiles supprimées avec succès.",
                         "orthophoto": serialize_orthophoto(ortho)})


class OrthophotoReferenceDataAPIView(APIView):
    """GET /api/orthophotos/reference-data/ — listes pour filtres et
    formulaire (projets, programmes, statuts, années, mois)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = [
            {"id": p.pk, "name": p.nom}
            for p in ProjetImmobilier.objects.filter(is_active=True).order_by("nom")
        ]
        programs = [
            {"id": p.pk, "name": p.name, "project_id": p.project_id}
            for p in RealEstateProgram.objects.filter(is_active=True)
            .order_by("name")
        ]
        current_year = datetime.now().year
        return Response({
            "projects": projects,
            "programs": programs,
            "statuses": [
                {"value": value, "label": label}
                for value, label in ProgramOrthophoto.STATUS_CHOICES
            ],
            "years": list(range(current_year - 3, current_year + 2)),
            "months": list(range(1, 13)),
            "user": {
                "username": request.user.get_username(),
                "can_add": request.user.has_perm("parcelaire.add_programorthophoto"),
                "can_change": request.user.has_perm("parcelaire.change_programorthophoto"),
                "can_delete": request.user.has_perm("parcelaire.delete_programorthophoto"),
            },
        })
