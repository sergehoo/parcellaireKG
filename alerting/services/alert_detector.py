"""Orchestrateur de détection (Phase 3).

Exécute les règles sur le périmètre d'une configuration (ou tout le portefeuille),
persiste les `AlertDetection` de façon idempotente par période, et produit des
recommandations d'action automatiques.
"""
from datetime import date, timedelta
from decimal import Decimal

from alerting.models import (
    SEVERITY_ORDER, AlertDetection, AlertThreshold, AlertType, Severity,
)
from alerting.services import alert_rules


def active_threshold():
    return AlertThreshold.active() or AlertThreshold()


def scope_programs(configuration):
    """Programmes du périmètre de la configuration (ou tous si global/None)."""
    from parcelaire.models import RealEstateProgram
    qs = RealEstateProgram.objects.filter(is_active=True)
    if configuration and not configuration.include_all_programs:
        pids = set(configuration.programs.values_list("id", flat=True))
        proj_ids = set(configuration.projects.values_list("id", flat=True))
        if proj_ids:
            pids |= set(RealEstateProgram.objects.filter(project_id__in=proj_ids)
                        .values_list("id", flat=True))
        qs = qs.filter(id__in=pids) if pids else qs.none()
    return list(qs)


def _to_detection(f, configuration, period_start, period_end):
    return AlertDetection(
        configuration=configuration,
        alert_type=f["alert_type"],
        severity=f["severity"],
        program_id=f.get("program_id"),
        lot_id=f.get("parcel_id"),
        block_id=f.get("block_id"),
        title=f["title"][:255],
        message=f.get("message"),
        current_value=f.get("current_value"),
        previous_value=f.get("previous_value"),
        difference=f.get("difference"),
        threshold=f.get("threshold"),
        financial_exposure=Decimal(str(f.get("financial_exposure") or 0)),
        period_start=period_start,
        period_end=period_end,
        metadata=f.get("metadata") or {},
    )


def run_detection(configuration=None, reference_date=None, window_days=7, persist=True):
    """Détecte les alertes sur le périmètre. Renvoie la liste des AlertDetection
    (persistées si `persist`). Idempotent : purge les détections NEW de la même
    période/config avant réinsertion."""
    reference_date = reference_date or date.today()
    period_start = reference_date - timedelta(days=window_days)
    th = active_threshold()

    from parcelaire.api.analytics import _sale_rows
    rows = _sale_rows(can_fin=True)
    programs = scope_programs(configuration)
    pids = {p.id for p in programs}
    rows = [r for r in rows if r.get("program_id") in pids]

    findings = []
    findings += alert_rules.detect_payment_construction_gap(rows, th)
    findings += alert_rules.detect_sold_no_progress(rows, th)
    findings += alert_rules.detect_data_quality(rows, th)
    for program in programs:
        findings += alert_rules.detect_high_comm_low_construction(program, th)
        findings += alert_rules.detect_construction_stagnation(program, reference_date, window_days, th)

    # Filtre de sévérité minimale de la configuration.
    if configuration:
        floor = SEVERITY_ORDER[configuration.minimum_severity]
        findings = [f for f in findings if SEVERITY_ORDER[f["severity"]] >= floor]

    detections = [_to_detection(f, configuration, period_start, reference_date) for f in findings]

    if persist:
        purge = AlertDetection.objects.filter(period_end=reference_date,
                                              status=AlertDetection.Status.NEW)
        purge = (purge.filter(configuration=configuration) if configuration
                 else purge.filter(configuration__isnull=True))
        purge.delete()
        AlertDetection.objects.bulk_create(detections)
    return detections


# ---------------------------------------------------------------------------
# Recommandations automatiques (§ recommandations du rapport)
# ---------------------------------------------------------------------------

_RECO_BY_TYPE = {
    AlertType.PAYMENT_GT_CONSTRUCTION: "Accélérer les travaux et informer la direction technique.",
    AlertType.SOLD_NO_PROGRESS: "Vérifier l'état des lots vendus sans avancement et planifier le chantier.",
    AlertType.HIGH_COMM_LOW_CONSTRUCTION: "Accélérer le chantier pour limiter l'exposition commerciale.",
    AlertType.CONSTRUCTION_STAGNANT: "Contacter le responsable de programme : chantier sans évolution.",
    AlertType.DATA_QUALITY: "Corriger les données : ventiler les paiements groupés / vérifier les saisies.",
    AlertType.PERFORMANCE_DROP: "Analyser le ralentissement et réaligner le planning.",
}


def generate_recommendations(detections):
    """Liste d'actions dédupliquées, priorisées par sévérité présente."""
    present = {}
    lots_to_prioritize = []
    for d in detections:
        atype = getattr(d, "alert_type", None) or (d.get("alert_type") if isinstance(d, dict) else None)
        sev = getattr(d, "severity", None) or (d.get("severity") if isinstance(d, dict) else None)
        if atype in _RECO_BY_TYPE:
            rank = SEVERITY_ORDER.get(sev, 0)
            present[atype] = max(present.get(atype, 0), rank)
        meta = getattr(d, "metadata", None) or (d.get("metadata") if isinstance(d, dict) else {}) or {}
        if atype == AlertType.PAYMENT_GT_CONSTRUCTION and meta.get("lot"):
            lots_to_prioritize.append(meta["lot"])

    recos = [_RECO_BY_TYPE[t] for t, _ in sorted(present.items(), key=lambda kv: -kv[1])]
    if lots_to_prioritize:
        top = ", ".join(str(x) for x in lots_to_prioritize[:5])
        recos.insert(0, f"Prioriser les travaux sur les lots {top}.")
    return recos
