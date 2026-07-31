"""Construction du contexte de rapport (Phase 4).

Assemble : résumé exécutif du portefeuille, indicateurs par programme (avec
variations), clients/lots prioritaires (écart paiement-construction), répartition
des sévérités, recommandations et graphiques SVG. Réutilise les métriques
(Phase 2) et le moteur de détection (Phase 3).
"""
from collections import Counter
from datetime import date, timedelta

from parcelaire.api.analytics import fmt_money

from alerting.models import AlertType, Severity
from alerting.services import alert_detector, chart_generator, metrics


def build_report_context(configuration=None, reference_date=None, window_days=7,
                         generated_at=None, can_fin=True):
    reference_date = reference_date or date.today()
    period_start = reference_date - timedelta(days=window_days)

    programs = alert_detector.scope_programs(configuration)
    prog_metrics = [metrics.program_period_metrics(p, reference_date, window_days) for p in programs]
    detections = alert_detector.run_detection(configuration, reference_date, window_days, persist=False)

    def money(v):
        return fmt_money(v) if can_fin else "Masqué"

    # Résumé exécutif du portefeuille.
    total_lots = sum(m["total_lots"] for m in prog_metrics)
    paid_total = sum(m["paid_total"] for m in prog_metrics)
    net_total = sum(m["net_total"] for m in prog_metrics)
    sold_total = sum(m["sold"] for m in prog_metrics)
    con_vals = [m["construction"]["current"] for m in prog_metrics if m["construction"]["current"] is not None]
    pay_vals = [m["payment"]["current"] for m in prog_metrics if m["payment"]["current"] is not None]

    sev_counts = Counter(d.severity for d in detections)
    gap_detections = sorted(
        [d for d in detections if d.alert_type == AlertType.PAYMENT_GT_CONSTRUCTION],
        key=lambda d: -(d.difference or 0))

    priority_clients = [{
        "customer": (d.metadata or {}).get("customer", "—"),
        "program": next((m["program"] for m in prog_metrics if m["program_id"] == d.program_id), "—"),
        "lot": (d.metadata or {}).get("lot", "—"),
        "payment": d.current_value, "construction": d.previous_value,
        "gap": d.difference, "paid": money(d.financial_exposure),
        "severity": d.severity, "severity_label": Severity(d.severity).label,
    } for d in gap_detections[:15]]

    summary = {
        "programs_count": len(prog_metrics),
        "total_lots": total_lots,
        "paid_total": money(paid_total),
        "commercialization_avg": round(sold_total / total_lots * 100, 1) if total_lots else 0.0,
        "construction_avg": round(sum(con_vals) / len(con_vals), 1) if con_vals else 0.0,
        "payment_avg": round(sum(pay_vals) / len(pay_vals), 1) if pay_vals else 0.0,
        "critical_count": sev_counts.get(Severity.CRITICAL, 0),
        "important_count": sev_counts.get(Severity.IMPORTANT, 0),
        "sensitive_clients": len(gap_detections),
        "detections_count": len(detections),
    }

    charts = {
        "payment_vs_construction": chart_generator.payment_vs_construction_svg([
            {"label": m["program"], "payment": m["payment"]["current"] or 0,
             "construction": m["construction"]["current"] or 0} for m in prog_metrics]),
        "severity": chart_generator.severity_distribution_svg(dict(sev_counts)),
    }

    # Enrichit chaque programme avec ses montants formatés.
    for m in prog_metrics:
        m["paid_display"] = money(m["paid_total"])
        m["remaining_display"] = money(m["remaining"])

    return {
        "report_id": f"KAY-{reference_date.strftime('%Y%m%d')}-{(configuration.id if configuration else 0):04d}",
        "generated_at": generated_at,
        "period_start": period_start,
        "period_end": reference_date,
        "window_days": window_days,
        "confidentiality": "Confidentiel",
        "author": "Système d'alertes Parcellaire KAYDAN",
        "configuration": configuration,
        "summary": summary,
        "programs": prog_metrics,
        "priority_clients": priority_clients,
        "severity_counts": dict(sev_counts),
        "recommendations": alert_detector.generate_recommendations(detections),
        "charts": charts,
        "can_view_financial": can_fin,
    }
