"""Métriques & comparaison de périodes (Phase 2).

Calcule les indicateurs courants par programme/îlot (construction, paiement,
commercialisation) et les compare à un instantané antérieur pour produire les
variations en POINTS et en RELATIF. Réutilise la logique commerciale de
`parcelaire/api/analytics.py` (statut réel via ventes, écart paiement-construction).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from alerting.models import (
    CommercializationSnapshot, ConstructionProgressSnapshot, PaymentSnapshot,
)


# ---------------------------------------------------------------------------
# Valeurs COURANTES (live) par programme
# ---------------------------------------------------------------------------

def program_construction(program):
    """Avancement construction moyen (%) sur les parcelles SUIVIES du programme.
    None si aucune parcelle n'a de chantier renseigné (≠ 0 % réel)."""
    from parcelaire.models import ConstructionProject
    by_parcel = {}
    for pid, prog in (ConstructionProject.objects
                      .filter(parcel__program=program, parcel__is_active=True)
                      .values_list("parcel_id", "progress_percent")):
        by_parcel[pid] = max(by_parcel.get(pid, 0.0), float(prog or 0))
    if not by_parcel:
        return None
    return round(sum(by_parcel.values()) / len(by_parcel), 1)


def program_payment(program):
    """{net, paid, rate} des ventes du programme."""
    from parcelaire.models import Payment, SaleFile
    net = float(SaleFile.objects.filter(is_active=True, program=program)
                .aggregate(s=Coalesce(Sum("net_price"), Decimal("0")))["s"])
    paid = float(Payment.objects.filter(is_active=True, status="CONFIRMED",
                                        sale_file__program=program)
                 .aggregate(s=Coalesce(Sum("amount"), Decimal("0")))["s"])
    return {"net": net, "paid": paid, "rate": round(paid / net * 100, 1) if net else 0.0}


def program_commercialization(program):
    """Comptages + taux, statut RÉEL déduit des ventes/réservations."""
    from parcelaire.models import Reservation, SaleFile
    parcels = program.parcels.filter(is_active=True)
    total = parcels.count()
    sold = set(SaleFile.objects.filter(is_active=True, program=program, parcel__isnull=False)
               .values_list("parcel_id", flat=True))
    reserved = set(Reservation.objects.filter(is_active=True, program=program, parcel__isnull=False)
                   .values_list("parcel_id", flat=True)) - sold
    blocked = (parcels.filter(commercial_status__in=["BLOCKED", "LITIGATION"])
               .exclude(id__in=sold | reserved).count())
    available = max(total - len(sold) - len(reserved) - blocked, 0)
    return {
        "total": total, "sold": len(sold), "reserved": len(reserved),
        "blocked": blocked, "available": available,
        "rate": round(len(sold) / total * 100, 1) if total else 0.0,
    }


# ---------------------------------------------------------------------------
# Comparaison de périodes
# ---------------------------------------------------------------------------

def compare(current, previous):
    """{current, previous, variation_points, variation_relative}.
    - variation_points : différence absolue (en points de %).
    - variation_relative : variation en % de l'ancienne valeur.
    Distingue clairement le taux, la variation en points et la variation relative."""
    if current is None:
        return {"current": None, "previous": previous,
                "variation_points": None, "variation_relative": None}
    cur = round(float(current), 1)
    if previous is None:
        return {"current": cur, "previous": None,
                "variation_points": None, "variation_relative": None}
    prev = round(float(previous), 1)
    pts = round(cur - prev, 1)
    rel = round((cur - prev) / prev * 100, 1) if prev else None
    return {"current": cur, "previous": prev, "variation_points": pts, "variation_relative": rel}


def _snapshot_value(model, program, on_or_before, field, block=None):
    """Valeur `field` de l'instantané le plus récent ≤ `on_or_before`."""
    qs = model.objects.filter(program=program, recorded_at__lte=on_or_before)
    if hasattr(model, "block"):
        qs = qs.filter(block=block) if block is not None else qs.filter(block__isnull=True)
    if hasattr(model, "lot"):
        qs = qs.filter(lot__isnull=True)
    snap = qs.order_by("-recorded_at", "-id").first()
    return float(getattr(snap, field)) if snap else None


# ---------------------------------------------------------------------------
# Métriques par programme (avec évolution sur une fenêtre)
# ---------------------------------------------------------------------------

def program_period_metrics(program, reference_date=None, window_days=7):
    """Indicateurs §6.1 + évolutions sur `window_days` (via snapshots)."""
    reference_date = reference_date or date.today()
    prev_date = reference_date - timedelta(days=window_days)

    con = program_construction(program)
    pay = program_payment(program)
    com = program_commercialization(program)

    prev_con = _snapshot_value(ConstructionProgressSnapshot, program, prev_date, "progress_percent")
    prev_pay = _snapshot_value(PaymentSnapshot, program, prev_date, "payment_rate")
    prev_com = _snapshot_value(CommercializationSnapshot, program, prev_date, "commercialization_rate")

    gap = round((pay["rate"] - con), 1) if con is not None else None
    return {
        "program_id": program.id,
        "program": program.name,
        "project": program.project.nom if program.project_id else None,
        "manager": getattr(program, "manager_name", None),
        "total_lots": com["total"],
        "available": com["available"],
        "reserved": com["reserved"],
        "sold": com["sold"],
        "blocked": com["blocked"],
        "commercialization": compare(com["rate"], prev_com),
        "payment": compare(pay["rate"], prev_pay),
        "construction": compare(con, prev_con),
        "gap_points": gap,
        "net_total": pay["net"],
        "paid_total": pay["paid"],
        "remaining": round(pay["net"] - pay["paid"], 2),
        "construction_tracked": con is not None,
    }


# ---------------------------------------------------------------------------
# Métriques par îlot / bloc (§6.2)
# ---------------------------------------------------------------------------

def _block_construction(program, block):
    from parcelaire.models import ConstructionProject
    q = Q(parcel__program=program, parcel__is_active=True)
    q &= Q(parcel__block=block) if block is not None else Q(parcel__block__isnull=True)
    by_parcel = {}
    for pid, prog in ConstructionProject.objects.filter(q).values_list("parcel_id", "progress_percent"):
        by_parcel[pid] = max(by_parcel.get(pid, 0.0), float(prog or 0))
    if not by_parcel:
        return None
    return round(sum(by_parcel.values()) / len(by_parcel), 1)


def block_period_metrics(program, reference_date=None, window_days=7):
    """Une ligne par îlot, triée par variation de construction (classement)."""
    reference_date = reference_date or date.today()
    prev_date = reference_date - timedelta(days=window_days)
    out = []
    for block in program.blocks.filter(is_active=True):
        cur = _block_construction(program, block)
        prev = _snapshot_value(ConstructionProgressSnapshot, program, prev_date,
                               "progress_percent", block=block)
        lots = block.parcels.filter(is_active=True).count()
        out.append({
            "block_id": block.id,
            "block": block.label or block.code,
            "lots": lots,
            "construction": compare(cur, prev),
        })
    # Classement : meilleure progression d'abord (None en dernier).
    out.sort(key=lambda r: (r["construction"]["variation_points"] is None,
                            -(r["construction"]["variation_points"] or 0)))
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out
