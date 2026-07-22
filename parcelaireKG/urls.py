"""
URL configuration for parcelaireKG project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from parcelaire.views import HomeView, MapView, ParcellaireDashboardView, ProjetImmobilierListView, \
    ProjetImmobilierCreateView, ProjetImmobilierDeleteView, ProjetImmobilierUpdateView, ProjetImmobilierDetailView, \
    RealEstateProgramListView, RealEstateProgramCreateView, RealEstateProgramUpdateView, RealEstateProgramDetailView, \
    RealEstateProgramDeleteView, ProgramPhaseListView, ProgramPhaseCreateView, ProgramPhaseUpdateView, \
    ProgramPhaseDeleteView, ParcelDatasetListView, ParcelDatasetDeleteView, ParcelDatasetUpdateView, \
    ParcelDatasetDetailView, ParcelDatasetCreateView, ProgramBlockListView, ProgramBlockCreateView, \
    ProgramBlockUpdateView, ProgramBlockDetailView, ProgramBlockDeleteView, ParcelListView, ParcelCreateView, \
    ParcelDeleteView, ParcelUpdateView, ParcelDetailView, CustomerListView, CustomerCreateView, CustomerUpdateView, \
    ReservationListView, ReservationCreateView, ReservationUpdateView, SaleFileListView, SaleFileCreateView, \
    SaleFileUpdateView, SaleFileDetailView, PaymentListView, PaymentCreateView, PaymentUpdateView, \
    ConstructionProjectListView, ConstructionProjectCreateView, ConstructionProjectDetailView, \
    ConstructionProjectUpdateView, ConstructionUpdateCreateView, ConstructionUpdateUpdateView, \
    ConstructionPhotoCreateView, ConstructionPhotoUpdateView, ConstructionMediaCreateView, ProgramByProjectAjaxView, \
    PhaseByProgramAjaxView, BlockByProgramAjaxView, ParcelByBlockAjaxView, ProgramStatsAjaxView, LeadListView, \
    LeadUpdateView, LeadCreateView, PropertyAssetDeleteView, PropertyAssetListView, PropertyAssetCreateView, \
    PropertyAssetDetailView, PropertyAssetUpdateView, MapCommercialView, \
    OrthophotoListView, OrthophotoCreateView, OrthophotoDetailView, OrthophotoStatusAPIView, \
    OrthophotoRetryView, OrthophotoSetCurrentView, OrthophotoDeleteTilesView, OrthophotoDownloadLogsView, \
    OrthophotoUploadInitView, OrthophotoUploadCompleteView, OrthophotoUploadAbortView

from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView, TemplateView

# SPA React (build Vite servi par WhiteNoise depuis static/orthophotos-app/).
# HashRouter → une seule route Django suffit ; le routage interne se fait
# après le `#`. La carte est la vue d'accueil du SPA.
_react_app = login_required(TemplateView.as_view(
    template_name="parcelaire/orthophoto/react_app.html",
))


def _spa(hash_url):
    """Redirige une ancienne route HTML vers son équivalent du SPA React.

    Le SPA React est désormais le frontend principal. Les routes de navigation
    historiques (templates Django) pointent vers le SPA — ce qui, au passage,
    retire les pages HTML héritées comme surface (elles n'exposent plus de
    données financières/PII, cf. audit H3/H5) sans risque de verrouillage.
    `%(pk)s` est substitué par l'identifiant de l'URL.
    """
    return RedirectView.as_view(url=hash_url, permanent=False)

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path("api/", include("parcelaire.api.urls")),
                  path("ai/", include("ai_construction.urls")),

                  # Coquille SPA (carte, orthophotos, …).
                  path("app/", _react_app, name="react_app"),
                  # Rétrocompat de l'itération précédente.
                  path("app/orthophotos/",
                       RedirectView.as_view(url="/app/#/orthophotos", permanent=False),
                       name="orthophoto_react_app"),

                  path('home', HomeView.as_view(), name='home'),

                  # Cartographie : /map et /map_commercial redirigent vers le
                  # SPA React (parité 2D atteinte). Les templates Leaflet
                  # historiques restent accessibles en repli sous /map/legacy/
                  # tant que la parité n'est pas définitivement validée.
                  path('map/', RedirectView.as_view(url="/app/#/carte", permanent=False), name='map'),
                  path('map_commercial', RedirectView.as_view(url="/app/#/carte", permanent=False), name='map_commercial'),
                  path('map/legacy/', MapView.as_view(), name='map_legacy'),
                  path('map_commercial/legacy/', MapCommercialView.as_view(), name='map_commercial_legacy'),

                  path('accounts/', include('allauth.urls')),

                  # Frontend principal = SPA React : la racine ouvre le SPA.
                  # L'ancien tableau de bord HTML reste en repli sous /legacy/.
                  path("", _spa("/app/"), name="parcelaire_dashboard"),
                  path("legacy/dashboard/", ParcellaireDashboardView.as_view(), name="parcelaire_dashboard_legacy"),

                  # -------- Entités migrées vers le SPA (redirections) --------
                  path("projects/", _spa("/app/#/r/projects"), name="project_list"),
                  path("projects/add/", _spa("/app/#/r/projects/new"), name="project_add"),
                  path("projects/<int:pk>/", _spa("/app/#/r/projects/%(pk)s"), name="project_detail"),
                  path("projects/<int:pk>/edit/", _spa("/app/#/r/projects/%(pk)s/edit"), name="project_edit"),
                  path("projects/<int:pk>/delete/", _spa("/app/#/r/projects/%(pk)s"), name="project_delete"),

                  path("programs/", _spa("/app/#/r/programs"), name="program_list"),
                  path("programs/add/", _spa("/app/#/r/programs/new"), name="program_add"),
                  path("programs/<int:pk>/", _spa("/app/#/r/programs/%(pk)s"), name="program_detail"),
                  path("programs/<int:pk>/edit/", _spa("/app/#/r/programs/%(pk)s/edit"), name="program_edit"),
                  path("programs/<int:pk>/delete/", _spa("/app/#/r/programs/%(pk)s"), name="program_delete"),

                  # Entités techniques migrées au SPA : liste/détail → SPA
                  # (lecture, masquage financier), écritures conservées sur Django.
                  path("phases/", _spa("/app/#/r/phases"), name="phase_list"),
                  path("phases/add/", ProgramPhaseCreateView.as_view(), name="phase_add"),
                  path("phases/<int:pk>/edit/", ProgramPhaseUpdateView.as_view(), name="phase_edit"),
                  path("phases/<int:pk>/delete/", ProgramPhaseDeleteView.as_view(), name="phase_delete"),

                  path("datasets/", _spa("/app/#/r/datasets"), name="dataset_list"),
                  path("datasets/<int:pk>/", _spa("/app/#/r/datasets/%(pk)s"), name="dataset_detail"),
                  path("datasets/add/", ParcelDatasetCreateView.as_view(), name="dataset_add"),
                  path("datasets/<int:pk>/edit/", ParcelDatasetUpdateView.as_view(), name="dataset_edit"),
                  path("datasets/<int:pk>/delete/", ParcelDatasetDeleteView.as_view(), name="dataset_delete"),

                  path("blocks/", _spa("/app/#/r/blocks"), name="block_list"),
                  path("blocks/<int:pk>/", _spa("/app/#/r/blocks/%(pk)s"), name="block_detail"),
                  path("blocks/add/", ProgramBlockCreateView.as_view(), name="block_add"),
                  path("blocks/edit/<int:pk>", ProgramBlockUpdateView.as_view(), name="block_edit"),
                  path("blocks/<int:pk>/delete/", ProgramBlockDeleteView.as_view(), name="block_delete"),

                  # Lecture → SPA ; écritures conservées sur Django (le SPA est
                  # en lecture seule pour les entités transactionnelles).
                  path("parcels/", _spa("/app/#/r/parcels"), name="parcel_list"),
                  path("parcels/<int:pk>/", _spa("/app/#/r/parcels/%(pk)s"), name="parcel_detail"),
                  path("parcels/add/", ParcelCreateView.as_view(), name="parcel_add"),
                  path("parcels/<int:pk>/edit/", ParcelUpdateView.as_view(), name="parcel_edit"),
                  path("parcels/<int:pk>/delete/", ParcelDeleteView.as_view(), name="parcel_delete"),

                  path("assets/", _spa("/app/#/r/assets"), name="asset_list"),
                  path("assets/<int:pk>/", _spa("/app/#/r/assets/%(pk)s"), name="asset_detail"),
                  path("assets/add/", PropertyAssetCreateView.as_view(), name="asset_add"),
                  path("assets/<int:pk>/edit/", PropertyAssetUpdateView.as_view(), name="asset_edit"),
                  path("assets/<int:pk>/delete/", PropertyAssetDeleteView.as_view(), name="asset_delete"),

                  path("customers/", _spa("/app/#/r/customers"), name="customer_list"),
                  path("customers/add/", _spa("/app/#/r/customers/new"), name="customer_add"),
                  path("customers/<int:pk>/edit/", _spa("/app/#/r/customers/%(pk)s/edit"), name="customer_edit"),

                  # Liste (fuite PII/budget) → SPA en lecture masquée ; écritures
                  # conservées sur Django.
                  path("leads/", _spa("/app/#/r/leads"), name="lead_list"),
                  path("leads/add/", LeadCreateView.as_view(), name="lead_add"),
                  path("leads/<int:pk>/edit/", LeadUpdateView.as_view(), name="lead_edit"),

                  path("reservations/", _spa("/app/#/r/reservations"), name="reservation_list"),
                  path("reservations/add/", ReservationCreateView.as_view(), name="reservation_add"),
                  path("reservations/<int:pk>/edit/", ReservationUpdateView.as_view(), name="reservation_edit"),

                  path("sales/", _spa("/app/#/r/sales"), name="sale_list"),
                  path("sales/<int:pk>/", _spa("/app/#/r/sales/%(pk)s"), name="sale_detail"),
                  path("sales/add/", SaleFileCreateView.as_view(), name="sale_add"),
                  path("sales/<int:pk>/edit/", SaleFileUpdateView.as_view(), name="sale_edit"),

                  path("payments/", _spa("/app/#/r/payments"), name="payment_list"),
                  path("payments/add/", PaymentCreateView.as_view(), name="payment_add"),
                  path("payments/<int:pk>/edit/", PaymentUpdateView.as_view(), name="payment_edit"),

                  path("construction-projects/", _spa("/app/#/r/construction"),
                       name="construction_project_list"),
                  path("construction-projects/<int:pk>/", _spa("/app/#/r/construction/%(pk)s"),
                       name="construction_project_detail"),
                  path("construction-projects/add/", ConstructionProjectCreateView.as_view(),
                       name="construction_project_add"),
                  path("construction-projects/<int:pk>/edit/", ConstructionProjectUpdateView.as_view(),
                       name="construction_project_edit"),

                  path("construction-updates/add/", ConstructionUpdateCreateView.as_view(),
                       name="construction_update_add"),
                  path("construction-updates/<int:pk>/edit/", ConstructionUpdateUpdateView.as_view(),
                       name="construction_update_edit"),

                  path("construction-photos/add/", ConstructionPhotoCreateView.as_view(),
                       name="construction_photo_add"),
                  path("construction-photos/<int:pk>/edit/", ConstructionPhotoUpdateView.as_view(),
                       name="construction_photo_edit"),

                  path("construction-media/add/", ConstructionMediaCreateView.as_view(), name="construction_media_add"),

                  path("ajax/programs-by-project/", ProgramByProjectAjaxView.as_view(),
                       name="ajax_programs_by_project"),
                  path("ajax/phases-by-program/", PhaseByProgramAjaxView.as_view(), name="ajax_phases_by_program"),
                  path("ajax/blocks-by-program/", BlockByProgramAjaxView.as_view(), name="ajax_blocks_by_program"),
                  path("ajax/parcels-by-block/", ParcelByBlockAjaxView.as_view(), name="ajax_parcels_by_block"),
                  path("ajax/program-stats/", ProgramStatsAjaxView.as_view(), name="ajax_program_stats"),

                  # -------- ORTHOPHOTOS --------
                  # Navigation migrée vers le SPA ; les actions (status/retry/
                  # set-current/delete-tiles/logs) et l'upload restent en place.
                  path("orthophotos/", _spa("/app/#/orthophotos"), name="orthophoto_list"),
                  path("orthophotos/add/", _spa("/app/#/orthophotos/upload"), name="orthophoto_add"),
                  path("orthophotos/<int:pk>/", _spa("/app/#/orthophotos/%(pk)s"), name="orthophoto_detail"),
                  path("orthophotos/<int:pk>/status/", OrthophotoStatusAPIView.as_view(), name="orthophoto_status"),
                  path("orthophotos/<int:pk>/retry/", OrthophotoRetryView.as_view(), name="orthophoto_retry"),
                  path("orthophotos/<int:pk>/set-current/", OrthophotoSetCurrentView.as_view(), name="orthophoto_set_current"),
                  path("orthophotos/<int:pk>/delete-tiles/", OrthophotoDeleteTilesView.as_view(), name="orthophoto_delete_tiles"),
                  path("orthophotos/<int:pk>/logs.txt", OrthophotoDownloadLogsView.as_view(), name="orthophoto_logs"),

                  # -------- UPLOAD MULTIPART S3 (MinIO) --------
                  # Le navigateur PUT directement vers MinIO via des
                  # presigned URLs ; Django ne reçoit que init/complete.
                  path("orthophotos/upload/init/", OrthophotoUploadInitView.as_view(), name="orthophoto_upload_init"),
                  path("orthophotos/upload/complete/", OrthophotoUploadCompleteView.as_view(), name="orthophoto_upload_complete"),
                  path("orthophotos/upload/abort/", OrthophotoUploadAbortView.as_view(), name="orthophoto_upload_abort"),
              ]

# -------------------------------------------------------------------
# Serving des fichiers statiques et media.
#
# * STATIC : en prod, c'est WhiteNoise (middleware) qui sert depuis
#   STATIC_ROOT — pas besoin d'ajouter de route Django. En DEBUG=True
#   on ajoute la route Django (runserver).
# * MEDIA  : WhiteNoise ne sert PAS /media/ par défaut. Or les tuiles
#   d'orthophoto sont sous /media/tiles_ortho/... et le navigateur
#   Leaflet doit pouvoir les charger en prod aussi. On ajoute donc une
#   route via `django.views.static.serve`, MAIS protégée par
#   `login_required` : /media/ contenait des tuiles cadastrales, des
#   médias de construction et des documents accessibles à tout anonyme.
#   L'utilisateur qui consulte la carte est authentifié, son cookie de
#   session accompagne donc les requêtes de tuiles (pas de régression).
#   (Idéalement remplacé par un CDN + URLs signées à terme.)
# -------------------------------------------------------------------
from django.urls import re_path as _re_path
from django.views.static import serve as _serve

urlpatterns += [
    _re_path(
        r"^media/(?P<path>.*)$",
        login_required(_serve),
        {"document_root": settings.MEDIA_ROOT},
        name="media-serve",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

