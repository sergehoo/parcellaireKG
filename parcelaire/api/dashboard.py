"""
Statistiques du tableau de bord (KPIs) consommées par le SPA React.
Les montants financiers sont masqués si l'utilisateur n'a pas le droit
`parcelaire.view_financial_data` (cohérent avec la carte).
"""
from decimal import Decimal

from django.db.models import Count, Sum
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from parcelaire.models import (
    Customer,
    Parcel,
    Payment,
    ProjetImmobilier,
    RealEstateProgram,
    Reservation,
    SaleFile,
)


def _fmt_money(value):
    try:
        v = int(Decimal(value or 0))
    except Exception:
        v = 0
    return f"{v:,}".replace(",", " ") + " FCFA"


@extend_schema_view(get=extend_schema(
    summary="Statistiques du tableau de bord",
    description="KPIs synthétiques (compteurs, statuts, montants). Les montants "
                "sont masqués sans `view_financial_data`.",
    tags=["Analytics"],
    responses={200: OpenApiResponse(description="KPIs du tableau de bord.")},
))
class DashboardStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        can_fin = request.user.is_superuser or request.user.has_perm("parcelaire.view_financial_data")

        parcels = Parcel.objects.filter(is_active=True)
        by_status = dict(
            parcels.values_list("commercial_status")
            .annotate(n=Count("id"))
            .values_list("commercial_status", "n")
        )

        sales = SaleFile.objects.filter(is_active=True)
        ca_total = sales.aggregate(s=Sum("net_price"))["s"] or Decimal("0")
        paid_total = Payment.objects.filter(status="CONFIRMED").aggregate(s=Sum("amount"))["s"] or Decimal("0")

        recent_sales = [
            {
                "id": s.id,
                "sale_number": s.sale_number,
                "customer": str(s.customer) if s.customer_id else "—",
                "program": s.program.name if s.program_id else "—",
                "status": s.get_status_display(),
                "net_price": _fmt_money(s.net_price) if can_fin else "Masqué",
                "sale_date": s.sale_date.isoformat() if s.sale_date else None,
            }
            for s in sales.select_related("customer", "program").order_by("-sale_date", "-created_at")[:6]
        ]

        return Response({
            "can_view_financial": can_fin,
            "counts": {
                "projects": ProjetImmobilier.objects.filter(is_active=True).count(),
                "programs": RealEstateProgram.objects.filter(is_active=True).count(),
                "parcels": parcels.count(),
                "customers": Customer.objects.filter(is_active=True).count(),
                "sales": sales.count(),
                "reservations": Reservation.objects.filter(is_active=True).count(),
            },
            "parcels_by_status": [
                {"status": k or "—", "count": v} for k, v in sorted(by_status.items(), key=lambda x: -x[1])
            ],
            "finance": {
                "ca_total": _fmt_money(ca_total) if can_fin else "Masqué",
                "ca_total_value": float(ca_total) if can_fin else None,
                "paid_total": _fmt_money(paid_total) if can_fin else "Masqué",
            },
            "recent_sales": recent_sales,
        })
