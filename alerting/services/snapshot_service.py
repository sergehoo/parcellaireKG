"""Capture d'instantanés périodiques (Phase 2).

Historise, par programme (et par îlot pour la construction), les taux courants
de construction / paiement / commercialisation. Sans cet historique, les
variations « +2 / +4 points » entre périodes ne sont pas calculables.

Idempotent par (programme[, îlot], date) : relancer la capture d'un même jour
met à jour l'instantané au lieu de le dupliquer.
"""
from datetime import date
from decimal import Decimal

from alerting.models import (
    CommercializationSnapshot, ConstructionProgressSnapshot, PaymentSnapshot,
)
from alerting.services import metrics


def capture_program(program, recorded_at=None):
    """Capture les instantanés d'UN programme pour la date donnée (aujourd'hui
    par défaut). Renvoie le nombre d'instantanés écrits."""
    recorded_at = recorded_at or date.today()
    written = 0

    con = metrics.program_construction(program)
    pay = metrics.program_payment(program)
    com = metrics.program_commercialization(program)

    # Construction niveau programme (uniquement si suivie).
    if con is not None:
        ConstructionProgressSnapshot.objects.update_or_create(
            program=program, block__isnull=True, lot__isnull=True, recorded_at=recorded_at,
            defaults={"progress_percent": con, "source": "daily"})
        written += 1

    # Construction par îlot.
    for block in program.blocks.filter(is_active=True):
        bcon = metrics._block_construction(program, block)
        if bcon is not None:
            ConstructionProgressSnapshot.objects.update_or_create(
                program=program, block=block, lot__isnull=True, recorded_at=recorded_at,
                defaults={"progress_percent": bcon, "source": "daily"})
            written += 1

    PaymentSnapshot.objects.update_or_create(
        program=program, lot__isnull=True, customer__isnull=True, recorded_at=recorded_at,
        defaults={"total_amount": Decimal(str(pay["net"])),
                  "paid_amount": Decimal(str(pay["paid"])),
                  "payment_rate": pay["rate"]})
    written += 1

    CommercializationSnapshot.objects.update_or_create(
        program=program, recorded_at=recorded_at,
        defaults={"available_count": com["available"], "reserved_count": com["reserved"],
                  "sold_count": com["sold"], "blocked_count": com["blocked"],
                  "commercialization_rate": com["rate"]})
    written += 1
    return written


def capture_all(recorded_at=None):
    """Capture tous les programmes actifs. Renvoie {programs, snapshots}."""
    from parcelaire.models import RealEstateProgram
    recorded_at = recorded_at or date.today()
    programs = 0
    snapshots = 0
    for program in RealEstateProgram.objects.filter(is_active=True):
        snapshots += capture_program(program, recorded_at)
        programs += 1
    return {"programs": programs, "snapshots": snapshots, "recorded_at": recorded_at.isoformat()}
