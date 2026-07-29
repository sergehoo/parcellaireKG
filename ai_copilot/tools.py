"""Tool Registry (MCP interne).

Chaque outil = fonction + schéma JSON + permission Django requise + drapeau
`side_effecting`. Les outils RÉUTILISENT le code existant (querysets DRF,
endpoints rapport…) et appliquent le masquage financier/PII. Les données
renvoyées à l'IA sont déjà masquées selon les droits de l'utilisateur.
"""
import math
from dataclasses import dataclass
from typing import Callable, Optional

from parcelaire.api.views import (
    user_can_view_financial_data,
    user_can_view_patient_data,
)

MASKED = "Masqué"


@dataclass
class ToolResult:
    # `content` : renvoyé à l'IA (déjà masqué). `action` : commande UI optionnelle
    # (map.focus, download, navigate) exécutée côté front.
    content: object
    action: Optional[dict] = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    handler: Callable
    permission: Optional[str] = None   # None = tout compte authentifié
    side_effecting: bool = False
    # Résumé lisible (user, args)->str affiché sur la carte de confirmation
    # (consentement éclairé : on nomme la cible plutôt qu'un id brut).
    confirm_summary: Optional[Callable] = None

    def schema(self) -> dict:
        """Définition au format function-calling OpenAI/DeepSeek."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec):
    _REGISTRY[spec.name] = spec
    return spec


def get(name: str) -> Optional[ToolSpec]:
    return _REGISTRY.get(name)


def schemas_for(user) -> list[dict]:
    """Schémas des outils que CET utilisateur a le droit d'appeler."""
    out = []
    for spec in _REGISTRY.values():
        if spec.permission and not (user.is_superuser or user.has_perm(spec.permission)):
            continue
        out.append(spec.schema())
    return out


# =====================================================================
# Outils MVP (Phase 0) — lecture + actions UI, tous masqués
# =====================================================================

def _tool_search_entities(user, args, context):
    from parcelaire.models import Customer, Parcel, RealEstateProgram

    q = (args.get("query") or "").strip()
    kind = (args.get("kind") or "all").lower()
    results = []

    if kind in ("all", "program", "programme", "programmes"):
        qs = RealEstateProgram.objects.filter(is_active=True)
        if q:
            qs = qs.filter(name__icontains=q)
        for p in qs.order_by("name")[:8]:
            results.append({"kind": "program", "id": p.id, "label": p.name,
                            "code": getattr(p, "code", "")})

    if kind in ("all", "parcel", "parcelle", "parcelles", "lot", "lots"):
        qs = Parcel.objects.filter(is_active=True)
        if q:
            qs = qs.filter(lot_number__icontains=q) | qs.filter(parcel_code__icontains=q)
        for p in qs.order_by("id")[:8]:
            results.append({
                "kind": "parcel", "id": p.id,
                "label": p.lot_number or p.parcel_code or f"#{p.id}",
                "status": getattr(p, "commercial_status", None),
            })

    if kind in ("all", "customer", "client", "clients"):
        # Aucun client renvoyé sans droit PII — y compris requête vide
        # (sinon l'IA énumérait les IDs/compte des clients actifs).
        if user_can_view_patient_data(user):
            qs = Customer.objects.filter(is_active=True)
            if q:
                qs = qs.filter(last_name__icontains=q) | qs.filter(company_name__icontains=q)
            for c in qs.order_by("id")[:8]:
                results.append({"kind": "customer", "id": c.id, "label": str(c)})

    return ToolResult(content={"count": len(results), "results": results})


def _tool_dashboard_summary(user, args, context):
    from decimal import Decimal

    from django.db.models import Sum

    from parcelaire.models import (
        Customer, Parcel, Payment, RealEstateProgram, Reservation, SaleFile,
    )

    can_fin = user_can_view_financial_data(user)
    counts = {
        "programs": RealEstateProgram.objects.filter(is_active=True).count(),
        "parcels": Parcel.objects.filter(is_active=True).count(),
        "customers": Customer.objects.filter(is_active=True).count(),
        "sales": SaleFile.objects.filter(is_active=True).count(),
        "reservations": Reservation.objects.filter(is_active=True).count(),
    }
    ca = SaleFile.objects.filter(is_active=True).aggregate(s=Sum("net_price"))["s"] or Decimal("0")
    paid = (Payment.objects.filter(is_active=True, status="CONFIRMED")
            .aggregate(s=Sum("amount"))["s"] or Decimal("0"))
    finance = {
        "ca_total": float(ca) if can_fin else MASKED,
        "paid_total": float(paid) if can_fin else MASKED,
    }
    return ToolResult(content={"counts": counts, "finance": finance,
                               "can_view_financial": can_fin})


def _resolve_program(program_id=None, program_name=None):
    from parcelaire.models import RealEstateProgram
    if program_id:
        p = RealEstateProgram.objects.filter(is_active=True, pk=program_id).first()
        if p:
            return p
    if program_name:
        return (RealEstateProgram.objects.filter(is_active=True, name__icontains=program_name)
                .order_by("name").first())
    return None


def _program_center(program):
    """Centre [lat, lng] du programme (centroïde, sinon centre du périmètre)."""
    pt = program.centroid or (program.boundary.centroid if program.boundary else None)
    return [pt.y, pt.x] if pt is not None else None


def _haversine_km(a, b):
    """Distance à vol d'oiseau (km) entre deux points [lat, lng]."""
    r = 6371.0
    lat1, lng1, lat2, lng2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return round(2 * r * math.asin(math.sqrt(h)), 2)


def _tool_focus_map_on_program(user, args, context):
    program = _resolve_program(args.get("program_id"), (args.get("program_name") or "").strip())
    if program is None:
        return ToolResult(content={"error": "Programme introuvable."})
    center = _program_center(program)
    if center is None:
        return ToolResult(
            content={"program": program.name,
                     "note": "Programme sans géométrie : carte non centrable."},
            action={"type": "navigate", "to": "/carte"})
    return ToolResult(
        content={"program": program.name, "center": center,
                 "note": "Carte centrée sur le programme."},
        action={"type": "map.focus", "program_id": program.id,
                "name": program.name, "center": center, "zoom": 15})


def _tool_distance_between_programs(user, args, context):
    """Distance à vol d'oiseau entre deux programmes + tracé de la ligne."""
    a = _resolve_program(args.get("program_a_id"), (args.get("program_a") or "").strip())
    b = _resolve_program(args.get("program_b_id"), (args.get("program_b") or "").strip())
    if a is None or b is None:
        return ToolResult(content={"error": "Un des deux programmes est introuvable."})
    ca, cb = _program_center(a), _program_center(b)
    if ca is None or cb is None:
        return ToolResult(content={"error": "Un des programmes n'a pas de géométrie."})
    dist = _haversine_km(ca, cb)
    label = f"{a.name} ↔ {b.name} : {dist} km (à vol d'oiseau)"
    return ToolResult(
        content={"from": a.name, "to": b.name, "distance_km": dist,
                 "note": "Distance à vol d'oiseau (la distance routière nécessite un service de routage)."},
        action={"type": "map.line", "points": [ca, cb], "label": label})


def _tool_buffer_around_program(user, args, context):
    """Dessine un cercle (rayon en km) autour d'un programme."""
    program = _resolve_program(args.get("program_id"), (args.get("program_name") or "").strip())
    if program is None:
        return ToolResult(content={"error": "Programme introuvable."})
    center = _program_center(program)
    if center is None:
        return ToolResult(content={"error": "Programme sans géométrie : rayon non traçable."})
    try:
        radius_km = float(args.get("radius_km") or 2)
    except (TypeError, ValueError):
        radius_km = 2.0
    radius_km = max(0.05, min(radius_km, 100))  # borne raisonnable
    return ToolResult(
        content={"program": program.name, "radius_km": radius_km, "center": center},
        action={"type": "map.circle", "center": center,
                "radius_m": radius_km * 1000, "name": f"{program.name} — rayon {radius_km} km"})


_BASEMAP_ALIASES = {
    "satellite": "satellite", "sat": "satellite", "imagery": "satellite",
    "aerien": "satellite", "aérien": "satellite", "aerienne": "satellite",
    "relief": "relief", "topo": "relief", "topographique": "relief", "terrain": "relief",
    "osm": "standard", "standard": "standard", "plan": "standard", "rue": "standard",
    "carte": "standard", "openstreetmap": "standard",
    "sombre": "sombre", "dark": "sombre", "nuit": "sombre", "noir": "sombre",
    "clair": "clair", "light": "clair", "blanc": "clair",
}


def _tool_set_map_basemap(user, args, context):
    """Change le fond de carte (satellite / relief / standard OSM / sombre / clair)."""
    req = (args.get("style") or "").strip().lower()
    key = _BASEMAP_ALIASES.get(req)
    if key is None:
        return ToolResult(content={
            "error": f"Fond inconnu : « {req} ». Choix : satellite, relief, standard, sombre, clair."})
    return ToolResult(content={"basemap": key, "note": f"Fond de carte : {key}."},
                      action={"type": "map.basemap", "basemap": key})


def _tool_show_program_orthophoto(user, args, context):
    """Affiche l'orthophoto (si publiée) d'un programme sur la carte."""
    from parcelaire.models import ProgramOrthophoto

    program = _resolve_program(args.get("program_id"), (args.get("program_name") or "").strip())
    if program is None:
        return ToolResult(content={"error": "Programme introuvable."})
    if not ProgramOrthophoto.objects.filter(program=program, status="DONE").exists():
        return ToolResult(content={"program": program.name,
                                   "note": "Aucune orthophoto publiée pour ce programme."})
    return ToolResult(
        content={"program": program.name, "note": "Affichage de l'orthophoto sur la carte."},
        action={"type": "map.ortho", "program_id": program.id, "on": True,
                "center": _program_center(program)})


def _geocode(place):
    """Géocode un lieu via Nominatim/OSM. Renvoie ([lat, lng], label) ou
    (None, message d'erreur)."""
    import requests
    from django.conf import settings
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1,
                    "countrycodes": settings.COPILOT_GEOCODE_COUNTRY},
            headers={"User-Agent": "parcelaireKG-copilot/1.0"},
            timeout=8)
        data = resp.json() if resp.status_code == 200 else []
    except Exception as exc:  # noqa: BLE001 - réseau / parsing
        return None, f"Géocodage indisponible : {exc}"
    if not data:
        return None, f"Lieu introuvable : {place}"
    top = data[0]
    try:
        return [float(top["lat"]), float(top["lon"])], top.get("display_name", place)
    except (KeyError, TypeError, ValueError):
        return None, "Réponse de géocodage invalide."


def _tool_geocode_place(user, args, context):
    """Recherche géographique (ville, commune, quartier, POI) → centre la carte."""
    place = (args.get("place") or "").strip()
    if not place:
        return ToolResult(content={"error": "Lieu non précisé."})
    center, label = _geocode(place)
    if center is None:
        return ToolResult(content={"error": label})
    return ToolResult(
        content={"place": label, "center": center},
        action={"type": "map.focus", "name": label, "center": center, "zoom": 13})


def _tool_programs_near_place(user, args, context):
    """Urbanisme : programmes à moins de N km d'un lieu (école, hôpital, voie…).
    Géocode le lieu puis mesure la distance aux centroïdes des programmes."""
    from parcelaire.models import RealEstateProgram
    place = (args.get("place") or "").strip()
    if not place:
        return ToolResult(content={"error": "Lieu non précisé."})
    try:
        radius = float(args.get("radius_km") or 2)
    except (TypeError, ValueError):
        radius = 2.0
    radius = max(0.1, min(radius, 200))
    center, label = _geocode(place)
    if center is None:
        return ToolResult(content={"error": label})
    near = []
    for p in RealEstateProgram.objects.filter(is_active=True):
        c = _program_center(p)
        if c is None:
            continue
        d = _haversine_km(c, center)
        if d <= radius:
            near.append({"program": p.name, "distance_km": d})
    near.sort(key=lambda x: x["distance_km"])
    return ToolResult(
        content={"place": label, "radius_km": radius, "count": len(near), "programs": near},
        action={"type": "map.circle", "center": center, "radius_m": radius * 1000,
                "name": f"{label} — rayon {radius} km"})


def _tool_get_analytics_digest(user, args, context):
    """Synthèse décisionnelle (KPIs, santé programmes, alertes, clients à risque)
    pour que l'IA produise l'« analyse automatique » du tableau de bord.
    Montants masqués sans droit financier (build_dashboard applique le masquage)."""
    from parcelaire.api.analytics import AnalyticsDashboardAPIView, _can_view_financial
    data = AnalyticsDashboardAPIView().build_dashboard(_can_view_financial(user))
    return ToolResult(content=data)


# Rapports = actions de téléchargement vers des endpoints protégés EXISTANTS
# (session authentifiée). PDF = pilotage ; xlsx/csv = clients à risque ; csv = alertes.
_REPORTS = {
    "dashboard": {"url": "/api/analytics/dashboard/report/", "filename": "rapport-pilotage.pdf", "format": "PDF"},
    "dg": {"url": "/api/analytics/dashboard/report/", "filename": "rapport-dg.pdf", "format": "PDF"},
    "pilotage": {"url": "/api/analytics/dashboard/report/", "filename": "rapport-pilotage.pdf", "format": "PDF"},
    "risques": {"url": "/api/analytics/at-risk/export/?fmt=xlsx", "filename": "clients-a-risque.xlsx", "format": "Excel"},
    "clients_a_risque": {"url": "/api/analytics/at-risk/export/?fmt=xlsx", "filename": "clients-a-risque.xlsx", "format": "Excel"},
    "commercial": {"url": "/api/analytics/at-risk/export/?fmt=xlsx", "filename": "rapport-commercial.xlsx", "format": "Excel"},
    "alertes": {"url": "/api/alerts/export/", "filename": "alertes.csv", "format": "CSV"},
}


def _tool_generate_report(user, args, context):
    kind = (args.get("kind") or "dashboard").strip().lower().replace(" ", "_")
    rep = _REPORTS.get(kind)
    if rep is None:
        return ToolResult(content={
            "error": f"Rapport inconnu : « {kind} ».",
            "available": sorted(set(_REPORTS))})
    url, filename = rep["url"], rep["filename"]
    # Variante CSV possible pour le rapport clients à risque.
    if kind in ("risques", "clients_a_risque", "commercial") \
            and (args.get("format") or "").strip().lower() == "csv":
        url, filename = "/api/analytics/at-risk/export/", filename.replace(".xlsx", ".csv")
    return ToolResult(
        content={"report": kind, "note": f"Rapport {rep['format']} prêt au téléchargement."},
        action={"type": "download", "url": url, "filename": filename})


# =====================================================================
# Cluster B — requêtes métier (outils EXPLICITES, masqués ; pas de SQL libre)
# =====================================================================
_PARCEL_STATUS_ALIASES = {
    "disponible": "AVAILABLE", "disponibles": "AVAILABLE", "libre": "AVAILABLE",
    "libres": "AVAILABLE", "available": "AVAILABLE",
    "reserve": "RESERVED", "réservé": "RESERVED", "reserves": "RESERVED",
    "réservés": "RESERVED", "réservées": "RESERVED", "reserved": "RESERVED",
    "vendu": "SOLD", "vendus": "SOLD", "vendues": "SOLD", "sold": "SOLD",
    "litige": "LITIGATION", "litiges": "LITIGATION", "litigation": "LITIGATION",
    "conflit": "LITIGATION",
}


def _tool_count_parcels_by_status(user, args, context):
    from parcelaire.models import Parcel
    raw = (args.get("status") or "").strip().lower()
    status = _PARCEL_STATUS_ALIASES.get(raw)
    if status is None:
        return ToolResult(content={
            "error": f"Statut inconnu : « {raw} ». Choix : disponible, réservé, vendu, litige."})
    qs = Parcel.objects.filter(is_active=True, commercial_status=status)
    sample = [{"id": p.id, "label": p.lot_number or p.parcel_code or f"#{p.id}"}
              for p in qs.order_by("id")[:15]]
    return ToolResult(content={"status": status, "count": qs.count(), "sample": sample})


def _tool_list_parcels_without_geometry(user, args, context):
    from parcelaire.models import Parcel
    qs = Parcel.objects.filter(is_active=True, geometry__isnull=True)
    sample = [{"id": p.id, "label": p.lot_number or p.parcel_code or f"#{p.id}"}
              for p in qs.order_by("id")[:15]]
    return ToolResult(content={"count": qs.count(), "sample": sample})


def _tool_list_programs_without_orthophoto(user, args, context):
    from parcelaire.models import ProgramOrthophoto, RealEstateProgram
    with_ortho = set(ProgramOrthophoto.objects.filter(status="DONE")
                     .values_list("program_id", flat=True))
    qs = RealEstateProgram.objects.filter(is_active=True).exclude(pk__in=with_ortho)
    names = list(qs.order_by("name").values_list("name", flat=True)[:30])
    return ToolResult(content={"count": qs.count(), "programs": names})


def _tool_sales_this_month(user, args, context):
    from decimal import Decimal

    from django.db.models import Sum
    from django.utils import timezone

    from parcelaire.models import SaleFile
    now = timezone.now()
    qs = SaleFile.objects.filter(is_active=True,
                                 sale_date__year=now.year, sale_date__month=now.month)
    total = qs.aggregate(s=Sum("net_price"))["s"] or Decimal("0")
    return ToolResult(content={
        "month": f"{now.year}-{now.month:02d}", "count": qs.count(),
        "total_net": float(total) if user_can_view_financial_data(user) else MASKED})


def _tool_customers_by_payment_ratio(user, args, context):
    from django.db.models import Sum

    from parcelaire.models import Customer, Payment, SaleFile
    try:
        min_pct = float(args.get("min_percent") or 70)
    except (TypeError, ValueError):
        min_pct = 70.0
    sales = (SaleFile.objects.filter(is_active=True)
             .values("customer").annotate(total=Sum("net_price")))
    paid = (Payment.objects.filter(is_active=True, status="CONFIRMED")
            .values("sale_file__customer").annotate(paid=Sum("amount")))
    paid_map = {r["sale_file__customer"]: (r["paid"] or 0) for r in paid}
    rows = []
    for r in sales:
        cid, total = r["customer"], float(r["total"] or 0)
        if cid is None or total <= 0:
            continue
        ratio = round(float(paid_map.get(cid, 0)) / total * 100, 1)
        if ratio >= min_pct:
            rows.append((cid, ratio))
    rows.sort(key=lambda x: -x[1])
    rows = rows[:20]
    can_pii = user_can_view_patient_data(user)
    cust = {c.id: c for c in Customer.objects.filter(id__in=[cid for cid, _ in rows])}
    results = [{"customer": (str(cust[cid]) if can_pii and cid in cust else f"Client #{cid}"),
                "paid_percent": ratio} for cid, ratio in rows]
    return ToolResult(content={"min_percent": min_pct, "count": len(results), "results": results})


# =====================================================================
# Cluster B (2/2) — Agent SQL/PostGIS LECTURE SEULE, whitelisté, gated
# =====================================================================
import re  # noqa: E402

_SQL_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|merge|"
    r"call|do|vacuum|analyze|reindex|cluster|comment|lock|into|"
    r"pg_read_file|pg_ls_dir|lo_import|lo_export|dblink|pg_sleep|set_config|"
    r"current_setting|pg_catalog|information_schema)\b", re.I)


def _sql_allowed_tables(user):
    """Tables interrogeables. Les tables sensibles (client/vente/paiement) ne
    sont ouvertes qu'aux utilisateurs ayant à la fois les droits financier ET PII."""
    from parcelaire.models import (
        Parcel, ParcelDataset, ProgramBlock, ProgramOrthophoto, ProgramPhase,
        ProjetImmobilier, RealEstateProgram,
    )
    base = [RealEstateProgram, ProjetImmobilier, Parcel, ProgramPhase,
            ParcelDataset, ProgramBlock, ProgramOrthophoto]
    tables = {m._meta.db_table for m in base}
    if user_can_view_financial_data(user) and user_can_view_patient_data(user):
        from parcelaire.models import Customer, Payment, Reservation, SaleFile
        tables |= {m._meta.db_table for m in [Customer, SaleFile, Payment, Reservation]}
    return tables


def _validate_sql(sql, allowed):
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        return "Une seule requête est autorisée (pas de « ; »)."
    low = s.lower()
    if not (low.startswith("select") or low.startswith("with")):
        return "Seules les requêtes SELECT (lecture) sont autorisées."
    if "--" in s or "/*" in s:
        return "Les commentaires SQL sont interdits."
    if _SQL_FORBIDDEN.search(s):
        return "Requête refusée : mot-clé non autorisé (lecture seule uniquement)."
    refs = set(re.findall(r'(?:from|join)\s+"?([a-zA-Z_][a-zA-Z0-9_]*)"?', low))
    forbidden = sorted(t for t in refs if t not in allowed)
    if forbidden:
        return f"Table(s) non autorisée(s) : {', '.join(forbidden)}."
    return None


def _tool_sql_query(user, args, context):
    from django.db import connection, transaction

    sql = (args.get("sql") or "").strip()
    if not sql:
        return ToolResult(content={"error": "Requête vide."})
    allowed = _sql_allowed_tables(user)
    err = _validate_sql(sql, allowed)
    if err:
        return ToolResult(content={"error": err, "allowed_tables": sorted(allowed)})

    limit = 100
    s = sql.rstrip(";").strip()
    if not re.search(r"\blimit\s+\d+\s*$", s, re.I):
        s = f"{s} LIMIT {limit}"

    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                try:
                    cur.execute("SET TRANSACTION READ ONLY")
                except Exception:  # noqa: BLE001 - sous-transaction (tests) : la validation garde
                    pass
                cur.execute(s)
                cols = [c[0] for c in cur.description] if cur.description else []
                rows = cur.fetchmany(limit)
            transaction.set_rollback(True)  # ne jamais persister, quoi qu'il arrive
    except Exception as exc:  # noqa: BLE001
        return ToolResult(content={"error": f"Erreur SQL : {str(exc)[:300]}"})

    data = [dict(zip(cols, [str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                            for v in r])) for r in rows]
    return ToolResult(content={"columns": cols, "row_count": len(data), "rows": data})


def _find_orthophoto(args):
    """Résout l'orthophoto ciblée par un appel d'action (par id, sinon dernière
    en échec / la plus récente du programme). Partagé par le handler et le résumé
    de confirmation pour garantir qu'ils désignent la MÊME cible."""
    from parcelaire.models import ProgramOrthophoto
    oid = args.get("orthophoto_id")
    if oid:
        return ProgramOrthophoto.objects.filter(pk=oid).first()
    program = _resolve_program(args.get("program_id"),
                               (args.get("program_name") or "").strip())
    if program is not None:
        return (program.orthophotos.filter(status="FAILED").order_by("-updated_at").first()
                or program.orthophotos.order_by("-updated_at").first())
    return None


def _retry_orthophoto_summary(user, args):
    ortho = _find_orthophoto(args)
    if ortho is None:
        return "Relancer le traitement d'une orthophoto (cible introuvable)."
    prog = getattr(ortho.program, "name", "?")
    return (f"Relancer le traitement (pipeline GDAL) de l'orthophoto "
            f"« {ortho.name or ortho.pk} » — programme {prog}.")


def _tool_retry_orthophoto(user, args, context):
    """ACTION à effet de bord : relance le pipeline GDAL d'une orthophoto.
    Réinitialise le statut à PENDING puis déclenche la tâche Celery — reprend
    exactement la logique de OrthophotoRetryAPIView (mêmes champs, même task)."""
    ortho = _find_orthophoto(args)
    if ortho is None:
        return ToolResult(content={"error": "Orthophoto introuvable."})

    ortho.status = "PENDING"
    ortho.progress_percent = 0
    ortho.current_step = "Relance demandée (Copilote)"
    ortho.error_message = None
    ortho.processed_at = None
    ortho.save(update_fields=["status", "progress_percent", "current_step",
                              "error_message", "processed_at", "updated_at"])
    celery_ok = True
    try:
        from parcelaire.tasks import process_orthophoto
        process_orthophoto.delay(ortho.pk)
    except Exception:  # noqa: BLE001 - broker injoignable : orthophoto déjà réinitialisée
        celery_ok = False
    label = ortho.name or f"#{ortho.pk}"
    msg = (f"Traitement de l'orthophoto « {label} » relancé."
           if celery_ok else
           f"Orthophoto « {label} » réinitialisée, mais la file de traitement est injoignable.")
    return ToolResult(
        content={"orthophoto_id": ortho.pk, "status": ortho.status,
                 "celery_queued": celery_ok, "message": msg},
        action={"type": "navigate", "to": f"/orthophotos/{ortho.pk}"})


def register_builtins():
    register(ToolSpec(
        name="search_entities",
        description="Recherche des programmes, parcelles/lots ou clients par nom/code. "
                    "Renvoie des résultats masqués selon les droits de l'utilisateur.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Terme recherché."},
                "kind": {"type": "string",
                         "enum": ["all", "program", "parcel", "customer"],
                         "description": "Type d'entité (défaut all)."},
            },
            "required": ["query"],
        },
        handler=_tool_search_entities,
    ))
    register(ToolSpec(
        name="get_dashboard_summary",
        description="Renvoie les KPI synthétiques (compteurs, montants). "
                    "Les montants sont masqués sans le droit financier.",
        parameters={"type": "object", "properties": {}},
        handler=_tool_dashboard_summary,
    ))
    register(ToolSpec(
        name="focus_map_on_program",
        description="Centre et zoome la carte sur un programme immobilier "
                    "(par id ou par nom).",
        parameters={
            "type": "object",
            "properties": {
                "program_id": {"type": "integer", "description": "Identifiant du programme."},
                "program_name": {"type": "string", "description": "Nom du programme."},
            },
        },
        handler=_tool_focus_map_on_program,
    ))
    register(ToolSpec(
        name="distance_between_programs",
        description="Calcule la distance à vol d'oiseau entre deux programmes et trace "
                    "la ligne sur la carte. Ex. « distance entre Callisto et Héliopolis ».",
        parameters={
            "type": "object",
            "properties": {
                "program_a": {"type": "string", "description": "Nom du 1er programme."},
                "program_b": {"type": "string", "description": "Nom du 2e programme."},
                "program_a_id": {"type": "integer"},
                "program_b_id": {"type": "integer"},
            },
        },
        handler=_tool_distance_between_programs,
    ))
    register(ToolSpec(
        name="buffer_around_program",
        description="Dessine un cercle (buffer) d'un rayon donné en km autour d'un "
                    "programme. Ex. « cercle de 2 km autour de Callisto ».",
        parameters={
            "type": "object",
            "properties": {
                "program_name": {"type": "string"},
                "program_id": {"type": "integer"},
                "radius_km": {"type": "number", "description": "Rayon en km (défaut 2)."},
            },
        },
        handler=_tool_buffer_around_program,
    ))
    register(ToolSpec(
        name="sql_query",
        description="Exécute une requête SQL SELECT en LECTURE SEULE sur les tables "
                    "autorisées (programmes, projets, parcelles, phases, îlots, datasets, "
                    "orthophotos ; + client/vente/paiement seulement avec les droits). "
                    "Réservé aux comptes habilités. Renvoie colonnes + lignes (max 100).",
        parameters={
            "type": "object",
            "properties": {"sql": {"type": "string",
                           "description": "Requête SELECT PostgreSQL/PostGIS unique."}},
            "required": ["sql"],
        },
        permission="ai_copilot.use_sql_agent",
        handler=_tool_sql_query,
    ))
    register(ToolSpec(
        name="count_parcels_by_status",
        description="Compte les parcelles/lots par statut commercial (disponible, "
                    "réservé, vendu, litige) + échantillon.",
        parameters={
            "type": "object",
            "properties": {"status": {"type": "string",
                           "description": "disponible | réservé | vendu | litige"}},
            "required": ["status"],
        },
        handler=_tool_count_parcels_by_status,
    ))
    register(ToolSpec(
        name="list_parcels_without_geometry",
        description="Liste les parcelles sans géométrie (à géoréférencer).",
        parameters={"type": "object", "properties": {}},
        handler=_tool_list_parcels_without_geometry,
    ))
    register(ToolSpec(
        name="list_programs_without_orthophoto",
        description="Liste les programmes sans orthophoto publiée.",
        parameters={"type": "object", "properties": {}},
        handler=_tool_list_programs_without_orthophoto,
    ))
    register(ToolSpec(
        name="sales_this_month",
        description="Ventes du mois en cours (nombre + montant total ; montant "
                    "masqué sans droit financier).",
        parameters={"type": "object", "properties": {}},
        handler=_tool_sales_this_month,
    ))
    register(ToolSpec(
        name="customers_by_payment_ratio",
        description="Clients ayant payé au moins X % de leurs ventes. Ex. « clients "
                    "ayant payé plus de 70 % ». Réservé au droit financier.",
        parameters={
            "type": "object",
            "properties": {"min_percent": {"type": "number",
                           "description": "Seuil de paiement en % (défaut 70)."}},
        },
        permission="parcelaire.view_financial_data",
        handler=_tool_customers_by_payment_ratio,
    ))
    register(ToolSpec(
        name="set_map_basemap",
        description="Change le fond de carte : satellite, relief, standard (OSM), "
                    "sombre ou clair. Ex. « affiche le satellite ».",
        parameters={
            "type": "object",
            "properties": {"style": {"type": "string",
                           "description": "satellite | relief | standard | sombre | clair"}},
            "required": ["style"],
        },
        handler=_tool_set_map_basemap,
    ))
    register(ToolSpec(
        name="show_program_orthophoto",
        description="Affiche l'orthophoto d'un programme sur la carte (si publiée).",
        parameters={
            "type": "object",
            "properties": {
                "program_name": {"type": "string"},
                "program_id": {"type": "integer"},
            },
        },
        handler=_tool_show_program_orthophoto,
    ))
    register(ToolSpec(
        name="geocode_place",
        description="Localise un lieu (ville, commune, quartier, route, POI : aéroport, "
                    "hôpital, école…) et centre la carte dessus. Ex. « Va à Cocody ».",
        parameters={
            "type": "object",
            "properties": {
                "place": {"type": "string", "description": "Lieu à localiser."},
            },
            "required": ["place"],
        },
        handler=_tool_geocode_place,
    ))
    register(ToolSpec(
        name="programs_near_place",
        description="Urbanisme : liste les programmes situés à moins de N km d'un lieu "
                    "(école, hôpital, aéroport, voie principale…). Géocode le lieu puis "
                    "mesure la distance à vol d'oiseau et trace le rayon sur la carte. "
                    "Ex. « Quels programmes à moins de 3 km du CHU de Cocody ? ».",
        parameters={
            "type": "object",
            "properties": {
                "place": {"type": "string", "description": "Lieu de référence à localiser."},
                "radius_km": {"type": "number", "description": "Rayon en km (défaut 2)."},
            },
            "required": ["place"],
        },
        handler=_tool_programs_near_place,
    ))
    register(ToolSpec(
        name="get_analytics_digest",
        description="Synthèse décisionnelle du tableau de bord (KPIs, santé des "
                    "programmes, alertes métier, top clients à risque) pour produire "
                    "une analyse automatique. Montants masqués sans droit financier.",
        parameters={"type": "object", "properties": {}},
        handler=_tool_get_analytics_digest,
    ))
    register(ToolSpec(
        name="generate_report",
        description="Prépare un rapport au téléchargement : « dashboard »/« DG » (PDF), "
                    "« risques »/« commercial » (Excel .xlsx ; format=csv possible), "
                    "« alertes » (CSV).",
        parameters={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "description": "dashboard | dg | risques | commercial | alertes"},
                "format": {"type": "string", "description": "xlsx (défaut risques) ou csv"},
            },
        },
        handler=_tool_generate_report,
    ))
    register(ToolSpec(
        name="retry_orthophoto_processing",
        description="ACTION : relance le traitement (pipeline GDAL) d'une orthophoto, "
                    "par id ou par programme (reprend la dernière en échec). Effet de "
                    "bord → confirmation requise. Ex. « Relance l'orthophoto de Callisto ».",
        parameters={
            "type": "object",
            "properties": {
                "orthophoto_id": {"type": "integer", "description": "Id de l'orthophoto."},
                "program_id": {"type": "integer"},
                "program_name": {"type": "string",
                                 "description": "Nom du programme (à défaut d'id)."},
            },
        },
        handler=_tool_retry_orthophoto,
        permission="parcelaire.change_programorthophoto",
        side_effecting=True,
        confirm_summary=_retry_orthophoto_summary,
    ))


register_builtins()
