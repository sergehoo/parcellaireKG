"""
Moteur de génération des alertes métier (persistées / auditables).

`generate_alerts()` recalcule l'ensemble des alertes actives à partir des
données réelles, puis :
- crée / met à jour (upsert par `dedup_key`) chaque alerte détectée ;
- passe automatiquement en RESOLVED les alertes précédemment ouvertes
  qui ne sont plus détectées (auto-résolution → traçabilité complète).

Idempotent : peut être lancé en boucle (cron / Celery beat) sans doublon.
"""
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from parcelaire.api.analytics import _construction_by_parcel, criticality
from parcelaire.models import Alert, Parcel, Payment, SaleFile


def _current_alerts():
    """Construit la liste des alertes qui DOIVENT exister maintenant."""
    con = _construction_by_parcel()
    out = []

    # Déséquilibre paiement / construction (par dossier de vente).
    sales = (
        SaleFile.objects.filter(is_active=True, parcel_id__isnull=False)
        .select_related("customer", "program", "parcel")
    )
    # Paiements confirmés par dossier.
    paid_by_sale = {
        row["sale_file_id"]: float(row["s"] or 0)
        for row in Payment.objects.filter(status="CONFIRMED")
        .values("sale_file_id").annotate(s=Sum("amount"))
    }

    for s in sales:
        net = float(s.net_price or 0)
        pay_pct = round(paid_by_sale.get(s.id, 0.0) / net * 100, 1) if net else 0.0
        con_pct = round(con.get(s.parcel_id, 0.0), 1)
        idcp = round(pay_pct - con_pct, 1)

        if idcp >= 20:
            level, reason = criticality(idcp)
            out.append({
                "dedup_key": f"idcp:sale:{s.id}",
                "rule": "idcp",
                "level": level,
                "title": f"Paiement en avance — {s.customer}",
                "detail": f"{reason} (payé {pay_pct} % / construit {con_pct} %).",
                "metric": f"IDCP +{idcp} %",
                "value": idcp,
                "program_id": s.program_id, "parcel_id": s.parcel_id,
                "sale_file_id": s.id, "customer_id": s.customer_id,
            })
        if con_pct < 20 and pay_pct > 40:
            out.append({
                "dedup_key": f"construction_retard:sale:{s.id}",
                "rule": "construction_retard",
                "level": "ELEVE",
                "title": f"Construction très en retard — lot {s.parcel.lot_number or s.parcel_id}",
                "detail": f"Avancement {con_pct} % alors que le paiement atteint {pay_pct} %.",
                "metric": f"Avancement {con_pct} %",
                "value": con_pct,
                "program_id": s.program_id, "parcel_id": s.parcel_id,
                "sale_file_id": s.id, "customer_id": s.customer_id,
            })

    # Lots vendus sans titre foncier.
    sold_parcel_ids = set(SaleFile.objects.filter(is_active=True, parcel_id__isnull=False)
                          .values_list("parcel_id", flat=True))
    for p in Parcel.objects.filter(id__in=sold_parcel_ids, is_active=True, has_title_document=False):
        out.append({
            "dedup_key": f"titre_manquant:parcel:{p.id}",
            "rule": "titre_manquant",
            "level": "MOYEN",
            "title": f"Titre foncier manquant — lot {p.lot_number or p.id}",
            "detail": "Parcelle vendue sans document de titre foncier.",
            "metric": "Titre absent",
            "program_id": p.program_id, "parcel_id": p.id,
        })

    # Dossiers de vente non signés mais avec paiements confirmés.
    for s in SaleFile.objects.filter(
            is_active=True, status__in=["OPEN", "PENDING_DOCS", "PENDING_PAYMENT"],
            payments__status="CONFIRMED").select_related("customer", "program").distinct():
        out.append({
            "dedup_key": f"contrat_non_signe:sale:{s.id}",
            "rule": "contrat_non_signe",
            "level": "MOYEN",
            "title": f"Dossier non signé avec paiements — {s.customer}",
            "detail": f"Paiements confirmés mais dossier au statut « {s.get_status_display()} ».",
            "metric": "Contrat non signé",
            "program_id": s.program_id, "sale_file_id": s.id, "customer_id": s.customer_id,
        })

    return out


@transaction.atomic
def generate_alerts():
    """Recalcule et persiste les alertes. Renvoie un résumé {created, updated, resolved}."""
    current = _current_alerts()
    current_keys = {a["dedup_key"] for a in current}
    created = updated = 0

    for a in current:
        obj, was_created = Alert.objects.update_or_create(
            dedup_key=a["dedup_key"],
            defaults={
                "rule": a["rule"], "level": a["level"], "title": a["title"],
                "detail": a.get("detail"), "metric": a.get("metric"), "value": a.get("value"),
                "program_id": a.get("program_id"), "parcel_id": a.get("parcel_id"),
                "sale_file_id": a.get("sale_file_id"), "customer_id": a.get("customer_id"),
            },
        )
        # Une alerte auparavant résolue qui réapparaît redevient NEW.
        if not was_created and obj.status == "RESOLVED":
            obj.status = "NEW"
            obj.resolved_at = None
            obj.save(update_fields=["status", "resolved_at"])
        created += 1 if was_created else 0
        updated += 0 if was_created else 1

    # Auto-résolution des alertes ouvertes non détectées ce tour-ci.
    stale = Alert.objects.exclude(dedup_key__in=current_keys).exclude(status="RESOLVED")
    resolved = stale.update(status="RESOLVED", resolved_at=timezone.now())

    return {"created": created, "updated": updated, "resolved": resolved, "active": len(current)}
