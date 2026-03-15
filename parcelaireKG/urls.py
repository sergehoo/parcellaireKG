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
    PhaseByProgramAjaxView, BlockByProgramAjaxView, ParcelByBlockAjaxView, ProgramStatsAjaxView

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path("api/", include("parcelaire.api.urls")),
                  path('home', HomeView.as_view(), name='home'),
                  path('map', MapView.as_view(), name='map'),
                  path('accounts/', include('allauth.urls')),

                  path("", ParcellaireDashboardView.as_view(), name="parcelaire_dashboard"),

                  path("projects/", ProjetImmobilierListView.as_view(), name="project_list"),
                  path("projects/add/", ProjetImmobilierCreateView.as_view(), name="project_add"),
                  path("projects/<int:pk>/", ProjetImmobilierDetailView.as_view(), name="project_detail"),
                  path("projects/<int:pk>/edit/", ProjetImmobilierUpdateView.as_view(), name="project_edit"),
                  path("projects/<int:pk>/delete/", ProjetImmobilierDeleteView.as_view(), name="project_delete"),

                  path("programs/", RealEstateProgramListView.as_view(), name="program_list"),
                  path("programs/add/", RealEstateProgramCreateView.as_view(), name="program_add"),
                  path("programs/<int:pk>/", RealEstateProgramDetailView.as_view(), name="program_detail"),
                  path("programs/<int:pk>/edit/", RealEstateProgramUpdateView.as_view(), name="program_edit"),
                  path("programs/<int:pk>/delete/", RealEstateProgramDeleteView.as_view(), name="program_delete"),

                  path("phases/", ProgramPhaseListView.as_view(), name="phase_list"),
                  path("phases/add/", ProgramPhaseCreateView.as_view(), name="phase_add"),
                  path("phases/<int:pk>/edit/", ProgramPhaseUpdateView.as_view(), name="phase_edit"),
                  path("phases/<int:pk>/delete/", ProgramPhaseDeleteView.as_view(), name="phase_delete"),

                  path("datasets/", ParcelDatasetListView.as_view(), name="dataset_list"),
                  path("datasets/add/", ParcelDatasetCreateView.as_view(), name="dataset_add"),
                  path("datasets/<int:pk>/", ParcelDatasetDetailView.as_view(), name="dataset_detail"),
                  path("datasets/<int:pk>/edit/", ParcelDatasetUpdateView.as_view(), name="dataset_edit"),
                  path("datasets/<int:pk>/delete/", ParcelDatasetDeleteView.as_view(), name="dataset_delete"),

                  path("blocks/", ProgramBlockListView.as_view(), name="block_list"),
                  path("blocks/add/", ProgramBlockCreateView.as_view(), name="block_add"),
                  path("blocks/<int:pk>/", ProgramBlockDetailView.as_view(), name="block_detail"),
                  path("blocks/<int:pk>/edit/", ProgramBlockUpdateView.as_view(), name="block_edit"),
                  path("blocks/<int:pk>/delete/", ProgramBlockDeleteView.as_view(), name="block_delete"),

                  path("parcels/", ParcelListView.as_view(), name="parcel_list"),
                  path("parcels/add/", ParcelCreateView.as_view(), name="parcel_add"),
                  path("parcels/<int:pk>/", ParcelDetailView.as_view(), name="parcel_detail"),
                  path("parcels/<int:pk>/edit/", ParcelUpdateView.as_view(), name="parcel_edit"),
                  path("parcels/<int:pk>/delete/", ParcelDeleteView.as_view(), name="parcel_delete"),

                  # path("assets/", PropertyAssetListView.as_view(), name="asset_list"),
                  # path("assets/add/", PropertyAssetCreateView.as_view(), name="asset_add"),
                  # path("assets/<int:pk>/", PropertyAssetDetailView.as_view(), name="asset_detail"),
                  # path("assets/<int:pk>/edit/", PropertyAssetUpdateView.as_view(), name="asset_edit"),
                  # path("assets/<int:pk>/delete/", PropertyAssetDeleteView.as_view(), name="asset_delete"),

                  path("customers/", CustomerListView.as_view(), name="customer_list"),
                  path("customers/add/", CustomerCreateView.as_view(), name="customer_add"),
                  path("customers/<int:pk>/edit/", CustomerUpdateView.as_view(), name="customer_edit"),

                  # path("leads/", LeadListView.as_view(), name="lead_list"),
                  # path("leads/add/", LeadCreateView.as_view(), name="lead_add"),
                  # path("leads/<int:pk>/edit/", LeadUpdateView.as_view(), name="lead_edit"),

                  path("reservations/", ReservationListView.as_view(), name="reservation_list"),
                  path("reservations/add/", ReservationCreateView.as_view(), name="reservation_add"),
                  path("reservations/<int:pk>/edit/", ReservationUpdateView.as_view(), name="reservation_edit"),

                  path("sales/", SaleFileListView.as_view(), name="sale_list"),
                  path("sales/add/", SaleFileCreateView.as_view(), name="sale_add"),
                  path("sales/<int:pk>/", SaleFileDetailView.as_view(), name="sale_detail"),
                  path("sales/<int:pk>/edit/", SaleFileUpdateView.as_view(), name="sale_edit"),

                  path("payments/", PaymentListView.as_view(), name="payment_list"),
                  path("payments/add/", PaymentCreateView.as_view(), name="payment_add"),
                  path("payments/<int:pk>/edit/", PaymentUpdateView.as_view(), name="payment_edit"),

                  path("construction-projects/", ConstructionProjectListView.as_view(),
                       name="construction_project_list"),
                  path("construction-projects/add/", ConstructionProjectCreateView.as_view(),
                       name="construction_project_add"),
                  path("construction-projects/<int:pk>/", ConstructionProjectDetailView.as_view(),
                       name="construction_project_detail"),
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
              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

