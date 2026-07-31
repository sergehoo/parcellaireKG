"""Règles de détection (Phase 3) — fonctions PURES renvoyant des « findings ».

Chaque détecteur prend des données déjà calculées (lignes IDCP de
`parcelaire/api/analytics._sale_rows`, ou un programme) et renvoie une liste de
dicts normalisés. La persistance en `AlertDetection` est faite par
`alert_detector.run_detection`.
"""
from alerting.models import AlertType, Severity
from alerting.services import metrics


def _severity_max(a, b):
    from alerting.models import SEVERITY_ORDER
    return a if SEVERITY_ORDER[a] >= SEVERITY_ORDER[b] else b


# --- §4.2 Paiement supérieur à la construction (le détecteur phare) ---

def detect_payment_construction_gap(rows, th):
    findings = []
    for r in rows:
        if r.get("overpaid") or not r.get("construction_tracked"):
            continue  # artefacts traités ailleurs (data quality / non suivi)
        gap = r.get("idcp")
        if gap is None or gap < th.vigilance_min:
            continue
        findings.append({
            "alert_type": AlertType.PAYMENT_GT_CONSTRUCTION,
            "severity": th.classify(gap),
            "program_id": r.get("program_id"), "parcel_id": r.get("parcel_id"),
            "title": f"Écart paiement-construction +{gap} pts — lot {r.get('lot')}",
            "message": (f"{r.get('customer')} : paiement {r.get('payment_pct')}% vs "
                        f"construction {r.get('construction_pct')}% (écart +{gap} points)."),
            "current_value": r.get("payment_pct"), "previous_value": r.get("construction_pct"),
            "difference": gap, "threshold": th.vigilance_min,
            "financial_exposure": r.get("paid_value") or 0,
            "metadata": {"customer": r.get("customer"), "lot": r.get("lot")},
        })
    return findings


# --- §4.7 Lot vendu/réservé sans avancement ---

def detect_sold_no_progress(rows, th):
    findings = []
    for r in rows:
        if (r.get("paid_value") or 0) <= 0:
            continue
        tracked = r.get("construction_tracked")
        con = r.get("construction_pct") or 0
        if tracked and con > 0:
            continue
        sev = Severity.IMPORTANT if (r.get("payment_pct") or 0) >= 50 else Severity.VIGILANCE
        findings.append({
            "alert_type": AlertType.SOLD_NO_PROGRESS,
            "severity": sev,
            "program_id": r.get("program_id"), "parcel_id": r.get("parcel_id"),
            "title": f"Lot vendu sans avancement — lot {r.get('lot')}",
            "message": (f"{r.get('customer')} a payé {r.get('payment_pct')}% mais le chantier "
                        f"est {'à 0 %' if tracked else 'non renseigné'}."),
            "current_value": r.get("payment_pct"), "previous_value": con,
            "difference": r.get("payment_pct"), "threshold": 0,
            "financial_exposure": r.get("paid_value") or 0,
            "metadata": {"customer": r.get("customer"), "lot": r.get("lot"),
                         "construction_tracked": tracked},
        })
    return findings


# --- §4.8 Anomalie / incohérence de données (sur-paiement) ---

def detect_data_quality(rows, th):
    findings = []
    for r in rows:
        if not r.get("overpaid"):
            continue
        findings.append({
            "alert_type": AlertType.DATA_QUALITY,
            "severity": Severity.IMPORTANT,
            "program_id": r.get("program_id"), "parcel_id": r.get("parcel_id"),
            "title": f"Paiement supérieur au prix net — lot {r.get('lot')}",
            "message": (f"{r.get('customer')} : taux de paiement {r.get('payment_pct')}% (> 100 %). "
                        f"Probable paiement groupé mal ventilé ou erreur de saisie."),
            "current_value": r.get("payment_pct"), "previous_value": 100,
            "difference": round((r.get("payment_pct") or 0) - 100, 1), "threshold": 100,
            "financial_exposure": r.get("paid_value") or 0,
            "metadata": {"customer": r.get("customer"), "lot": r.get("lot")},
        })
    return findings


# --- §4.5 Commercialisation élevée, construction faible (niveau programme) ---

def detect_high_comm_low_construction(program, th):
    com = metrics.program_commercialization(program)["rate"]
    con = metrics.program_construction(program)
    if con is None:
        return []
    gap = round(com - con, 1)
    if com < 50 or con > 25 or gap < th.important_min:
        return []
    return [{
        "alert_type": AlertType.HIGH_COMM_LOW_CONSTRUCTION,
        "severity": _severity_max(th.classify(gap), Severity.IMPORTANT),
        "program_id": program.id,
        "title": f"Commercialisation {com}% vs construction {con}% — {program.name}",
        "message": (f"La commercialisation atteint {com}% alors que la construction reste à "
                    f"{con}% (écart {gap} points). Exposition commerciale élevée."),
        "current_value": com, "previous_value": con, "difference": gap,
        "threshold": th.important_min, "financial_exposure": 0,
        "metadata": {},
    }]


# --- §4.3 Construction sans évolution (via snapshots) ---

def detect_construction_stagnation(program, reference_date, window_days, th):
    m = metrics.program_period_metrics(program, reference_date, window_days)
    con = m["construction"]
    pay = m["payment"]
    if con["current"] is None or con["variation_points"] is None:
        return []  # pas de valeur / pas d'antérieur → indécidable
    if con["variation_points"] > 0:
        return []
    sev = Severity.VIGILANCE
    extra = ""
    if pay["variation_points"] and pay["variation_points"] > 0:
        sev = Severity.IMPORTANT
        extra = f" alors que les paiements ont progressé de +{pay['variation_points']} points"
    return [{
        "alert_type": AlertType.CONSTRUCTION_STAGNANT,
        "severity": sev,
        "program_id": program.id,
        "title": f"Chantier sans évolution — {program.name}",
        "message": (f"Aucune progression de construction sur la période "
                    f"(reste à {con['current']}%){extra}."),
        "current_value": con["current"], "previous_value": con["previous"],
        "difference": con["variation_points"], "threshold": 0, "financial_exposure": 0,
        "metadata": {"payment_variation": pay["variation_points"]},
    }]
