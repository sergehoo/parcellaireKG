from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView, DeleteView, UpdateView, CreateView, ListView, DetailView

from parcelaire.forms import ProgramPhaseForm, ParcelDatasetForm, ProgramBlockForm, ParcelForm, CustomerForm, \
    ReservationForm, SaleFileForm, PaymentForm, ConstructionProjectForm, ConstructionUpdateForm, ConstructionPhotoForm, \
    ConstructionMediaForm, RealEstateProgramForm, ProjetImmobilierForm, LeadForm, PropertyAssetForm
from parcelaire.models import ProgramBlock, ProjetImmobilier, RealEstateProgram, Parcel, PropertyAsset, Customer, Lead, \
    Reservation, SaleFile, ProgramPhase, ParcelDataset, Payment, ConstructionProject, ConstructionUpdate, \
    ConstructionPhoto, ConstructionMedia


# Create your views here.

class HomeView(TemplateView):
    template_name = "index.html"


class MapView(TemplateView):
    template_name = "map.html"


class RealEstateMap3DView(TemplateView):
    template_name = "map_3d.html"


class SearchFilterMixin:
    search_param = "q"

    def get_search_query(self):
        return self.request.GET.get(self.search_param, "").strip()

    def apply_filters(self, queryset):
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.apply_filters(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.get_search_query()
        return context


class AjaxableListMixin:
    paginate_by = 20

    def render_to_json_response(self, context):
        data = {
            "results": [
                {
                    "id": obj.pk,
                    "text": str(obj),
                }
                for obj in context["object_list"]
            ]
        }
        return JsonResponse(data)

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return self.render_to_json_response(context)
        return super().render_to_response(context, **response_kwargs)


class ParcellaireDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "parcelaire/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["projects_count"] = ProjetImmobilier.objects.filter(is_active=True).count()
        context["programs_count"] = RealEstateProgram.objects.filter(is_active=True).count()
        context["blocks_count"] = ProgramBlock.objects.filter(is_active=True).count()
        context["parcels_count"] = Parcel.objects.filter(is_active=True).count()
        context["assets_count"] = PropertyAsset.objects.filter(is_active=True).count()
        context["customers_count"] = Customer.objects.filter(is_active=True).count()
        context["leads_count"] = Lead.objects.filter(is_active=True).count()
        context["reservations_count"] = Reservation.objects.filter(is_active=True).count()
        context["sales_count"] = SaleFile.objects.filter(is_active=True).count()

        context["available_parcels_count"] = Parcel.objects.filter(
            is_active=True,
            commercial_status="AVAILABLE"
        ).count()
        context["reserved_parcels_count"] = Parcel.objects.filter(
            is_active=True,
            commercial_status__in=["OPTIONED", "RESERVED"]
        ).count()
        context["sold_parcels_count"] = Parcel.objects.filter(
            is_active=True,
            commercial_status="SOLD"
        ).count()

        context["programs_by_project"] = (
            ProjetImmobilier.objects.filter(is_active=True)
            .annotate(programs_total=Count("programs"))
            .order_by("nom")
        )

        context["sales_total"] = (
                                     SaleFile.objects.filter(is_active=True)
                                     .aggregate(total=Sum("net_price"))
                                     .get("total")
                                 ) or 0

        return context


class ProjetImmobilierListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = ProjetImmobilier
    template_name = "parcelaire/project/list.html"
    context_object_name = "projects"
    paginate_by = 20

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("country", "place")
        q = self.get_search_query()

        if q:
            queryset = queryset.filter(
                Q(nom__icontains=q) |
                Q(code__icontains=q) |
                Q(description__icontains=q)
            )
        return queryset.order_by("nom")


class ProjetImmobilierDetailView(LoginRequiredMixin, DetailView):
    model = ProjetImmobilier
    template_name = "parcelaire/project/detail.html"
    context_object_name = "project"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        context["programs"] = project.programs.filter(is_active=True).order_by("name")
        context["programs_count"] = context["programs"].count()
        return context


class ProjetImmobilierCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ProjetImmobilier
    form_class = ProjetImmobilierForm
    template_name = "parcelaire/project/form.html"
    success_message = "Projet créé avec succès."

    def get_success_url(self):
        return reverse("project_detail", kwargs={"pk": self.object.pk})


class ProjetImmobilierUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ProjetImmobilier
    form_class = ProjetImmobilierForm
    template_name = "parcelaire/project/form.html"
    success_message = "Projet mis à jour avec succès."

    def get_success_url(self):
        return reverse("project_detail", kwargs={"pk": self.object.pk})


class ProjetImmobilierDeleteView(LoginRequiredMixin, DeleteView):
    model = ProjetImmobilier
    template_name = "parcelaire/project/delete.html"
    success_url = reverse_lazy("project_list")


class RealEstateProgramListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = RealEstateProgram
    template_name = "parcelaire/program/list.html"
    context_object_name = "programs"
    paginate_by = 20

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("project", "country", "place")
        q = self.get_search_query()
        project_id = self.request.GET.get("project")
        status = self.request.GET.get("status")

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        if status:
            queryset = queryset.filter(status=status)

        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(code__icontains=q) |
                Q(marketing_title__icontains=q) |
                Q(project__nom__icontains=q)
            )

        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projects"] = ProjetImmobilier.objects.filter(is_active=True).order_by("nom")
        context["selected_project"] = self.request.GET.get("project", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["status_choices"] = RealEstateProgram.STATUS_CHOICES
        return context


class RealEstateProgramDetailView(LoginRequiredMixin, DetailView):
    model = RealEstateProgram
    template_name = "parcelaire/program/detail.html"
    context_object_name = "program"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        program = self.object

        context["phases"] = program.phases.filter(is_active=True).order_by("order", "name")
        context["datasets"] = program.parcel_datasets.filter(is_active=True).order_by("-created_at")
        context["blocks"] = program.blocks.filter(is_active=True).order_by("code")
        context["parcels_count"] = program.parcels.filter(is_active=True).count()
        context["assets_count"] = program.assets.filter(is_active=True).count()
        context["available_parcels_count"] = program.parcels.filter(
            is_active=True, commercial_status="AVAILABLE"
        ).count()

        return context


class RealEstateProgramCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = RealEstateProgram
    form_class = RealEstateProgramForm
    template_name = "parcelaire/program/form.html"
    success_message = "Programme créé avec succès."

    def get_initial(self):
        initial = super().get_initial()
        project_id = self.request.GET.get("project")
        if project_id:
            initial["project"] = project_id
        return initial

    def get_success_url(self):
        return reverse("program_detail", kwargs={"pk": self.object.pk})


class RealEstateProgramUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = RealEstateProgram
    form_class = RealEstateProgramForm
    template_name = "parcelaire/program/form.html"
    success_message = "Programme mis à jour avec succès."

    def get_success_url(self):
        return reverse("program_detail", kwargs={"pk": self.object.pk})


class RealEstateProgramDeleteView(LoginRequiredMixin, DeleteView):
    model = RealEstateProgram
    template_name = "parcelaire/program/delete.html"

    def get_success_url(self):
        return reverse("project_detail", kwargs={"pk": self.object.project_id})


class ProgramPhaseListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = ProgramPhase
    template_name = "parcelaire/phase/list.html"
    context_object_name = "phases"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("program", "program__project")
        program_id = self.request.GET.get("program")
        q = self.get_search_query()

        if program_id:
            queryset = queryset.filter(program_id=program_id)

        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(code__icontains=q) |
                Q(program__name__icontains=q)
            )

        return queryset.order_by("program__name", "order", "name")


class ProgramPhaseCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ProgramPhase
    form_class = ProgramPhaseForm
    template_name = "parcelaire/phase/form.html"
    success_message = "Phase créée avec succès."

    def get_initial(self):
        initial = super().get_initial()
        program_id = self.request.GET.get("program")
        if program_id:
            initial["program"] = program_id
        return initial

    def get_success_url(self):
        return reverse("program_detail", kwargs={"pk": self.object.program_id})


class ProgramPhaseUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ProgramPhase
    form_class = ProgramPhaseForm
    template_name = "parcelaire/phase/form.html"
    success_message = "Phase mise à jour avec succès."

    def get_success_url(self):
        return reverse("program_detail", kwargs={"pk": self.object.program_id})


class ProgramPhaseDeleteView(LoginRequiredMixin, DeleteView):
    model = ProgramPhase
    template_name = "parcelaire/phase/delete.html"

    def get_success_url(self):
        return reverse("program_detail", kwargs={"pk": self.object.program_id})


class ParcelDatasetListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = ParcelDataset
    template_name = "parcelaire/dataset/list.html"
    context_object_name = "datasets"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["programs"] = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        context["selected_program"] = self.request.GET.get("program", "")
        return context
    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("program", "phase")
        program_id = self.request.GET.get("program")
        q = self.get_search_query()

        if program_id:
            queryset = queryset.filter(program_id=program_id)

        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(source_code__icontains=q) |
                Q(source_file_name__icontains=q)
            )

        return queryset.order_by("-created_at")


class ParcelDatasetDetailView(LoginRequiredMixin, DetailView):
    model = ParcelDataset
    template_name = "parcelaire/dataset/detail.html"
    context_object_name = "dataset"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dataset = self.object
        context["parcels_count"] = dataset.parcels.count()
        context["parcels"] = dataset.parcels.select_related("block", "phase").order_by("block__code", "lot_number")[
                             :100]
        return context


class ParcelDatasetCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ParcelDataset
    form_class = ParcelDatasetForm
    template_name = "parcelaire/dataset/form.html"
    success_message = "Dataset créé avec succès."

    def get_initial(self):
        initial = super().get_initial()
        program_id = self.request.GET.get("program")
        if program_id:
            initial["program"] = program_id
        return initial

    def get_success_url(self):
        return reverse("dataset_detail", kwargs={"pk": self.object.pk})


class ParcelDatasetUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ParcelDataset
    form_class = ParcelDatasetForm
    template_name = "parcelaire/dataset/form.html"
    success_message = "Dataset mis à jour avec succès."

    def get_success_url(self):
        return reverse("dataset_detail", kwargs={"pk": self.object.pk})


class ParcelDatasetDeleteView(LoginRequiredMixin, DeleteView):
    model = ParcelDataset
    template_name = "parcelaire/dataset/delete.html"

    def get_success_url(self):
        return reverse("program_detail", kwargs={"pk": self.object.program_id})


class ProgramBlockListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = ProgramBlock
    template_name = "parcelaire/block/list.html"
    context_object_name = "blocks"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("program", "phase")
        program_id = self.request.GET.get("program")
        phase_id = self.request.GET.get("phase")
        q = self.get_search_query()

        if program_id:
            queryset = queryset.filter(program_id=program_id)

        if phase_id:
            queryset = queryset.filter(phase_id=phase_id)

        if q:
            queryset = queryset.filter(
                Q(code__icontains=q) |
                Q(label__icontains=q) |
                Q(program__name__icontains=q)
            )

        return queryset.order_by("code")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["programs"] = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        context["phases"] = ProgramPhase.objects.filter(is_active=True).select_related("program").order_by("program__name", "order", "name")
        context["selected_program"] = self.request.GET.get("program", "")
        context["selected_phase"] = self.request.GET.get("phase", "")
        return context

class ProgramBlockDetailView(LoginRequiredMixin, DetailView):
    model = ProgramBlock
    template_name = "parcelaire/block/detail.html"
    context_object_name = "block"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        block = self.object
        context["parcels"] = block.parcels.filter(is_active=True).order_by("lot_number")
        context["parcels_count"] = context["parcels"].count()
        return context


class ProgramBlockCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ProgramBlock
    form_class = ProgramBlockForm
    template_name = "parcelaire/block/form.html"
    success_message = "Îlot créé avec succès."

    def get_initial(self):
        initial = super().get_initial()
        program_id = self.request.GET.get("program")
        phase_id = self.request.GET.get("phase")
        if program_id:
            initial["program"] = program_id
        if phase_id:
            initial["phase"] = phase_id
        return initial

    def get_success_url(self):
        return reverse("block_detail", kwargs={"pk": self.object.pk})


class ProgramBlockUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ProgramBlock
    form_class = ProgramBlockForm
    template_name = "parcelaire/block/form.html"
    success_message = "Îlot mis à jour avec succès."

    def get_success_url(self):
        return reverse("block_detail", kwargs={"pk": self.object.pk})


class ProgramBlockDeleteView(LoginRequiredMixin, DeleteView):
    model = ProgramBlock
    template_name = "parcelaire/block/delete.html"

    def get_success_url(self):
        return reverse("program_detail", kwargs={"pk": self.object.program_id})


class ParcelListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = Parcel
    template_name = "parcelaire/parcel/list.html"
    context_object_name = "parcels"
    paginate_by = 50

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related(
            "program", "phase", "block", "dataset", "land_use"
        )

        project_id = self.request.GET.get("project")
        program_id = self.request.GET.get("program")
        phase_id = self.request.GET.get("phase")
        block_id = self.request.GET.get("block")
        status = self.request.GET.get("status")
        q = self.get_search_query()

        if project_id:
            queryset = queryset.filter(program__project_id=project_id)
        if program_id:
            queryset = queryset.filter(program_id=program_id)
        if phase_id:
            queryset = queryset.filter(phase_id=phase_id)
        if block_id:
            queryset = queryset.filter(block_id=block_id)
        if status:
            queryset = queryset.filter(commercial_status=status)

        if q:
            queryset = queryset.filter(
                Q(lot_number__icontains=q) |
                Q(parcel_code__icontains=q) |
                Q(external_reference__icontains=q) |
                Q(block__code__icontains=q) |
                Q(program__name__icontains=q)
            )

        return queryset.order_by("block__code", "lot_number", "id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projects"] = ProjetImmobilier.objects.filter(is_active=True).order_by("nom")
        context["programs"] = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        context["phases"] = ProgramPhase.objects.filter(is_active=True).order_by("program__name", "order")
        context["blocks"] = ProgramBlock.objects.filter(is_active=True).order_by("code")
        context["commercial_status_choices"] = Parcel.COMMERCIAL_STATUS_CHOICES
        return context


class ParcelDetailView(LoginRequiredMixin, DetailView):
    model = Parcel
    template_name = "parcelaire/parcel/detail.html"
    context_object_name = "parcel"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parcel = self.object

        context["assets"] = parcel.assets.filter(is_active=True).order_by("code")
        context["documents"] = parcel.documents.filter(is_active=True).order_by("-created_at")
        context["construction_projects"] = parcel.construction_projects.filter(is_active=True).order_by("-created_at")
        context["reservations"] = parcel.reservations.filter(is_active=True).order_by("-created_at")
        context["sales"] = parcel.sales.filter(is_active=True).order_by("-created_at")
        context["geometry_history"] = parcel.geometry_history.order_by("-created_at")

        return context


class ParcelCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Parcel
    form_class = ParcelForm
    template_name = "parcelaire/parcel/form.html"
    success_message = "Parcelle créée avec succès."

    def get_initial(self):
        initial = super().get_initial()
        program_id = self.request.GET.get("program")
        block_id = self.request.GET.get("block")
        dataset_id = self.request.GET.get("dataset")

        if program_id:
            initial["program"] = program_id
        if block_id:
            initial["block"] = block_id
        if dataset_id:
            initial["dataset"] = dataset_id
        return initial

    def get_success_url(self):
        return reverse("parcel_detail", kwargs={"pk": self.object.pk})


class ParcelUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Parcel
    form_class = ParcelForm
    template_name = "parcelaire/parcel/form.html"
    success_message = "Parcelle mise à jour avec succès."

    def get_success_url(self):
        return reverse("parcel_detail", kwargs={"pk": self.object.pk})


class ParcelDeleteView(LoginRequiredMixin, DeleteView):
    model = Parcel
    template_name = "parcelaire/parcel/delete.html"

    def get_success_url(self):
        return reverse("parcel_list")


class CustomerListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = Customer
    template_name = "parcelaire/customer/list.html"
    context_object_name = "customers"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("country", "place")
        q = self.get_search_query()

        if q:
            queryset = queryset.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(company_name__icontains=q) |
                Q(phone__icontains=q) |
                Q(email__icontains=q)
            )
        return queryset.order_by("company_name", "last_name", "first_name")


class CustomerCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "parcelaire/customer/form.html"
    success_message = "Client créé avec succès."
    success_url = reverse_lazy("customer_list")


class CustomerUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "parcelaire/customer/form.html"
    success_message = "Client mis à jour avec succès."
    success_url = reverse_lazy("customer_list")


class ReservationListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = Reservation
    template_name = "parcelaire/reservation/list.html"
    context_object_name = "reservations"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("program", "customer", "parcel", "lead")
        status = self.request.GET.get("status")
        q = self.get_search_query()

        if status:
            queryset = queryset.filter(status=status)

        if q:
            queryset = queryset.filter(
                Q(reservation_number__icontains=q) |
                Q(customer__first_name__icontains=q) |
                Q(customer__last_name__icontains=q) |
                Q(customer__company_name__icontains=q) |
                Q(parcel__lot_number__icontains=q)
            )
        return queryset.order_by("-reservation_date", "-created_at")


class ReservationCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "parcelaire/reservation/form.html"
    success_message = "Réservation créée avec succès."
    success_url = reverse_lazy("reservation_list")


class ReservationUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "parcelaire/reservation/form.html"
    success_message = "Réservation mise à jour avec succès."
    success_url = reverse_lazy("reservation_list")

# =========================================================
# PROPERTY ASSET
# =========================================================

class PropertyAssetListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = PropertyAsset
    template_name = "parcelaire/asset/list.html"
    context_object_name = "assets"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related(
            "program",
            "program__project",
            "phase",
            "parcel",
            "property_type",
        )

        project_id = self.request.GET.get("project")
        program_id = self.request.GET.get("program")
        phase_id = self.request.GET.get("phase")
        status = self.request.GET.get("status")
        q = self.get_search_query()

        if project_id:
            queryset = queryset.filter(program__project_id=project_id)

        if program_id:
            queryset = queryset.filter(program_id=program_id)

        if phase_id:
            queryset = queryset.filter(phase_id=phase_id)

        if status:
            queryset = queryset.filter(status=status)

        if q:
            queryset = queryset.filter(
                Q(label__icontains=q)
                | Q(code__icontains=q)
                | Q(program__name__icontains=q)
                | Q(program__project__nom__icontains=q)
                | Q(parcel__lot_number__icontains=q)
                | Q(parcel__parcel_code__icontains=q)
                | Q(property_type__label__icontains=q)
            )

        return queryset.order_by("program__name", "code", "label")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["projects"] = ProjetImmobilier.objects.filter(is_active=True).order_by("nom")
        context["programs"] = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        context["phases"] = ProgramPhase.objects.filter(is_active=True).order_by("program__name", "order", "name")
        context["status_choices"] = getattr(PropertyAsset, "STATUS_CHOICES", [])
        context["selected_project"] = self.request.GET.get("project", "")
        context["selected_program"] = self.request.GET.get("program", "")
        context["selected_phase"] = self.request.GET.get("phase", "")
        context["selected_status"] = self.request.GET.get("status", "")
        return context


class PropertyAssetDetailView(LoginRequiredMixin, DetailView):
    model = PropertyAsset
    template_name = "parcelaire/asset/detail.html"
    context_object_name = "asset"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        asset = self.object
        parcel = getattr(asset, "parcel", None)

        context["documents"] = getattr(asset, "documents", None).all().order_by("-created_at") if hasattr(asset, "documents") else []
        context["photos"] = getattr(asset, "photos", None).all().order_by("-created_at") if hasattr(asset, "photos") else []
        context["updates"] = getattr(asset, "updates", None).all().order_by("-created_at") if hasattr(asset, "updates") else []
        context["parcel"] = parcel
        context["program"] = asset.program
        context["project"] = asset.program.project if asset.program and getattr(asset.program, "project", None) else None
        return context


class PropertyAssetCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = PropertyAsset
    form_class = PropertyAssetForm
    template_name = "parcelaire/asset/form.html"
    success_message = "Actif immobilier créé avec succès."

    def get_initial(self):
        initial = super().get_initial()
        program_id = self.request.GET.get("program")
        phase_id = self.request.GET.get("phase")
        parcel_id = self.request.GET.get("parcel")

        if program_id:
            initial["program"] = program_id
        if phase_id:
            initial["phase"] = phase_id
        if parcel_id:
            initial["parcel"] = parcel_id

        return initial

    def get_success_url(self):
        return reverse("asset_detail", kwargs={"pk": self.object.pk})


class PropertyAssetUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = PropertyAsset
    form_class = PropertyAssetForm
    template_name = "parcelaire/asset/form.html"
    success_message = "Actif immobilier mis à jour avec succès."

    def get_success_url(self):
        return reverse("asset_detail", kwargs={"pk": self.object.pk})


class PropertyAssetDeleteView(LoginRequiredMixin, DeleteView):
    model = PropertyAsset
    template_name = "parcelaire/asset/delete.html"

    def get_success_url(self):
        return reverse("asset_list")


# =========================================================
# LEAD
# =========================================================

class LeadListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = Lead
    template_name = "parcelaire/lead/list.html"
    context_object_name = "leads"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related(
            "program",
            "parcel",
            "customer",
        )

        status = self.request.GET.get("status")
        program_id = self.request.GET.get("program")
        q = self.get_search_query()

        if status:
            queryset = queryset.filter(status=status)

        if program_id:
            queryset = queryset.filter(program_id=program_id)

        if q:
            queryset = queryset.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(company_name__icontains=q)
                | Q(reference__icontains=q)
                | Q(program__name__icontains=q)
                | Q(parcel__lot_number__icontains=q)
                | Q(parcel__parcel_code__icontains=q)
            )

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["programs"] = RealEstateProgram.objects.filter(is_active=True).order_by("name")
        context["status_choices"] = getattr(Lead, "STATUS_CHOICES", [])
        context["selected_program"] = self.request.GET.get("program", "")
        context["selected_status"] = self.request.GET.get("status", "")
        return context


class LeadCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Lead
    form_class = LeadForm
    template_name = "parcelaire/lead/form.html"
    success_message = "Lead créé avec succès."

    def get_initial(self):
        initial = super().get_initial()
        program_id = self.request.GET.get("program")
        parcel_id = self.request.GET.get("parcel")
        customer_id = self.request.GET.get("customer")

        if program_id:
            initial["program"] = program_id
        if parcel_id:
            initial["parcel"] = parcel_id
        if customer_id:
            initial["customer"] = customer_id

        return initial

    def get_success_url(self):
        return reverse("lead_list")


class LeadUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Lead
    form_class = LeadForm
    template_name = "parcelaire/lead/form.html"
    success_message = "Lead mis à jour avec succès."

    def get_success_url(self):
        return reverse("lead_list")
class SaleFileListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = SaleFile
    template_name = "parcelaire/sale/list.html"
    context_object_name = "sales"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("program", "customer", "parcel", "reservation")
        status = self.request.GET.get("status")
        q = self.get_search_query()

        if status:
            queryset = queryset.filter(status=status)

        if q:
            queryset = queryset.filter(
                Q(sale_number__icontains=q) |
                Q(customer__first_name__icontains=q) |
                Q(customer__last_name__icontains=q) |
                Q(customer__company_name__icontains=q) |
                Q(parcel__lot_number__icontains=q)
            )
        return queryset.order_by("-sale_date", "-created_at")


class SaleFileDetailView(LoginRequiredMixin, DetailView):
    model = SaleFile
    template_name = "parcelaire/sale/detail.html"
    context_object_name = "sale"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payments"] = self.object.payments.filter(is_active=True).order_by("-payment_date", "-created_at")
        return context


class SaleFileCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = SaleFile
    form_class = SaleFileForm
    template_name = "parcelaire/sale/form.html"
    success_message = "Vente créée avec succès."

    def get_success_url(self):
        return reverse("sale_detail", kwargs={"pk": self.object.pk})


class SaleFileUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = SaleFile
    form_class = SaleFileForm
    template_name = "parcelaire/sale/form.html"
    success_message = "Vente mise à jour avec succès."

    def get_success_url(self):
        return reverse("sale_detail", kwargs={"pk": self.object.pk})


class PaymentListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = Payment
    template_name = "parcelaire/payment/list.html"
    context_object_name = "payments"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("sale_file", "installment")
        status = self.request.GET.get("status")
        q = self.get_search_query()

        if status:
            queryset = queryset.filter(status=status)

        if q:
            queryset = queryset.filter(
                Q(payment_number__icontains=q) |
                Q(reference__icontains=q) |
                Q(sale_file__sale_number__icontains=q)
            )
        return queryset.order_by("-payment_date", "-created_at")


class PaymentCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "parcelaire/payment/form.html"
    success_message = "Paiement enregistré avec succès."
    success_url = reverse_lazy("payment_list")


class PaymentUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Payment
    form_class = PaymentForm
    template_name = "parcelaire/payment/form.html"
    success_message = "Paiement mis à jour avec succès."
    success_url = reverse_lazy("payment_list")


class ConstructionProjectListView(LoginRequiredMixin, SearchFilterMixin, ListView):
    model = ConstructionProject
    template_name = "parcelaire/construction_project/list.html"
    context_object_name = "construction_projects"
    paginate_by = 30

    def apply_filters(self, queryset):
        queryset = queryset.filter(is_active=True).select_related("parcel", "asset")
        status = self.request.GET.get("status")
        q = self.get_search_query()

        if status:
            queryset = queryset.filter(status=status)

        if q:
            queryset = queryset.filter(
                Q(code__icontains=q) |
                Q(title__icontains=q) |
                Q(parcel__lot_number__icontains=q) |
                Q(asset__label__icontains=q)
            )
        return queryset.order_by("-created_at")


class ConstructionProjectDetailView(LoginRequiredMixin, DetailView):
    model = ConstructionProject
    template_name = "parcelaire/construction_project/detail.html"
    context_object_name = "construction_project"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cp = self.object
        context["updates"] = cp.updates.filter(is_active=True).order_by("-report_date")
        context["photos"] = cp.photos.filter(is_active=True).order_by("sort_order", "-shot_date")
        context["media_list"] = cp.media.filter(is_active=True).order_by("sort_order", "-created_at")
        return context


class ConstructionProjectCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ConstructionProject
    form_class = ConstructionProjectForm
    template_name = "parcelaire/construction_project/form.html"
    success_message = "Chantier créé avec succès."

    def get_initial(self):
        initial = super().get_initial()
        parcel_id = self.request.GET.get("parcel")
        asset_id = self.request.GET.get("asset")
        if parcel_id:
            initial["parcel"] = parcel_id
        if asset_id:
            initial["asset"] = asset_id
        return initial

    def get_success_url(self):
        return reverse("construction_project_detail", kwargs={"pk": self.object.pk})


class ConstructionProjectUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ConstructionProject
    form_class = ConstructionProjectForm
    template_name = "parcelaire/construction_project/form.html"
    success_message = "Chantier mis à jour avec succès."

    def get_success_url(self):
        return reverse("construction_project_detail", kwargs={"pk": self.object.pk})


class ConstructionUpdateCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ConstructionUpdate
    form_class = ConstructionUpdateForm
    template_name = "parcelaire/construction_update/form.html"
    success_message = "Mise à jour de chantier ajoutée avec succès."

    def get_initial(self):
        initial = super().get_initial()
        project_id = self.kwargs.get("project_id") or self.request.GET.get("project")
        if project_id:
            initial["construction_project"] = project_id
        return initial

    def get_success_url(self):
        return reverse("construction_project_detail", kwargs={"pk": self.object.construction_project_id})


class ConstructionUpdateUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ConstructionUpdate
    form_class = ConstructionUpdateForm
    template_name = "parcelaire/construction_update/form.html"
    success_message = "Mise à jour de chantier modifiée avec succès."

    def get_success_url(self):
        return reverse("construction_project_detail", kwargs={"pk": self.object.construction_project_id})


class ConstructionPhotoCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ConstructionPhoto
    form_class = ConstructionPhotoForm
    template_name = "parcelaire/construction_photo/form.html"
    success_message = "Photo ajoutée avec succès."

    def get_initial(self):
        initial = super().get_initial()
        project_id = self.kwargs.get("project_id") or self.request.GET.get("project")
        if project_id:
            initial["construction_project"] = project_id
        return initial

    def get_success_url(self):
        return reverse("construction_project_detail", kwargs={"pk": self.object.construction_project_id})


class ConstructionPhotoUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ConstructionPhoto
    form_class = ConstructionPhotoForm
    template_name = "parcelaire/construction_photo/form.html"
    success_message = "Photo modifiée avec succès."

    def get_success_url(self):
        return reverse("construction_project_detail", kwargs={"pk": self.object.construction_project_id})


class ConstructionMediaCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = ConstructionMedia
    form_class = ConstructionMediaForm
    template_name = "parcelaire/construction_media/form.html"
    success_message = "Média ajouté avec succès."

    def get_initial(self):
        initial = super().get_initial()
        project_id = self.kwargs.get("project_id") or self.request.GET.get("project")
        if project_id:
            initial["construction_project"] = project_id
        return initial

    def get_success_url(self):
        return reverse("construction_project_detail", kwargs={"pk": self.object.construction_project_id})


class ProgramByProjectAjaxView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        project_id = request.GET.get("project_id")
        data = []

        if project_id:
            programs = RealEstateProgram.objects.filter(
                is_active=True,
                project_id=project_id
            ).order_by("name")
            data = [{"id": p.id, "name": p.name} for p in programs]

        return JsonResponse({"results": data})


class PhaseByProgramAjaxView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        program_id = request.GET.get("program_id")
        data = []

        if program_id:
            phases = ProgramPhase.objects.filter(
                is_active=True,
                program_id=program_id
            ).order_by("order", "name")
            data = [{"id": p.id, "name": p.name} for p in phases]

        return JsonResponse({"results": data})


class BlockByProgramAjaxView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        program_id = request.GET.get("program_id")
        phase_id = request.GET.get("phase_id")
        queryset = ProgramBlock.objects.filter(is_active=True)

        if program_id:
            queryset = queryset.filter(program_id=program_id)
        if phase_id:
            queryset = queryset.filter(phase_id=phase_id)

        queryset = queryset.order_by("code")
        data = [{"id": b.id, "name": b.code} for b in queryset]
        return JsonResponse({"results": data})


class ParcelByBlockAjaxView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        block_id = request.GET.get("block_id")
        program_id = request.GET.get("program_id")

        queryset = Parcel.objects.filter(is_active=True)

        if block_id:
            queryset = queryset.filter(block_id=block_id)
        if program_id:
            queryset = queryset.filter(program_id=program_id)

        queryset = queryset.order_by("lot_number", "id")
        data = [
            {
                "id": p.id,
                "name": f"Lot {p.lot_number or p.parcel_code or p.id}",
                "status": p.commercial_status,
            }
            for p in queryset
        ]
        return JsonResponse({"results": data})


class ProgramStatsAjaxView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        program_id = request.GET.get("program_id")
        if not program_id:
            return JsonResponse({"error": "program_id requis"}, status=400)

        program = get_object_or_404(RealEstateProgram, pk=program_id, is_active=True)

        data = {
            "program": program.name,
            "parcels_count": program.parcels.filter(is_active=True).count(),
            "assets_count": program.assets.filter(is_active=True).count(),
            "available_parcels": program.parcels.filter(is_active=True, commercial_status="AVAILABLE").count(),
            "reserved_parcels": program.parcels.filter(is_active=True,
                                                       commercial_status__in=["OPTIONED", "RESERVED"]).count(),
            "sold_parcels": program.parcels.filter(is_active=True, commercial_status="SOLD").count(),
            "blocks_count": program.blocks.filter(is_active=True).count(),
            "datasets_count": program.parcel_datasets.filter(is_active=True).count(),
        }
        return JsonResponse(data)
