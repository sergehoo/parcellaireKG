"""Tool Registry (MCP interne).

Chaque outil = fonction + schéma JSON + permission Django requise + drapeau
`side_effecting`. Les outils RÉUTILISENT le code existant (querysets DRF,
endpoints rapport…) et appliquent le masquage financier/PII. Les données
renvoyées à l'IA sont déjà masquées selon les droits de l'utilisateur.
"""
from dataclasses import dataclass, field
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


def _tool_focus_map_on_program(user, args, context):
    from parcelaire.models import RealEstateProgram

    program = None
    pid = args.get("program_id")
    name = (args.get("program_name") or "").strip()
    if pid:
        program = RealEstateProgram.objects.filter(is_active=True, pk=pid).first()
    if program is None and name:
        program = RealEstateProgram.objects.filter(
            is_active=True, name__icontains=name).order_by("name").first()
    if program is None:
        return ToolResult(content={"error": "Programme introuvable."})

    center = None
    pt = program.centroid or (program.boundary.centroid if program.boundary else None)
    if pt is not None:
        center = [pt.y, pt.x]  # [lat, lng]

    action = {"type": "map.focus", "program_id": program.id,
              "name": program.name, "center": center, "zoom": 15}
    if center is None:
        return ToolResult(
            content={"program": program.name,
                     "note": "Programme sans géométrie : carte non centrable."},
            action={"type": "navigate", "to": "/carte"})
    return ToolResult(
        content={"program": program.name, "center": center,
                 "note": "Carte centrée sur le programme."},
        action=action)


def _tool_geocode_place(user, args, context):
    """Recherche géographique (Nominatim/OSM) : ville, commune, quartier, POI…
    Renvoie le centre → action map.focus (réutilise le pilotage carte existant)."""
    import requests
    from django.conf import settings

    place = (args.get("place") or "").strip()
    if not place:
        return ToolResult(content={"error": "Lieu non précisé."})
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place, "format": "json", "limit": 1,
                    "countrycodes": settings.COPILOT_GEOCODE_COUNTRY},
            headers={"User-Agent": "parcelaireKG-copilot/1.0"},
            timeout=8)
        data = resp.json() if resp.status_code == 200 else []
    except Exception as exc:  # noqa: BLE001 - réseau / parsing
        return ToolResult(content={"error": f"Géocodage indisponible : {exc}"})
    if not data:
        return ToolResult(content={"error": f"Lieu introuvable : {place}"})

    top = data[0]
    try:
        center = [float(top["lat"]), float(top["lon"])]
    except (KeyError, TypeError, ValueError):
        return ToolResult(content={"error": "Réponse de géocodage invalide."})
    label = top.get("display_name", place)
    return ToolResult(
        content={"place": label, "center": center},
        action={"type": "map.focus", "name": label, "center": center, "zoom": 13})


def _tool_generate_dashboard_report(user, args, context):
    # Réutilise l'endpoint rapport protégé existant ; le navigateur le télécharge
    # avec la session authentifiée (aucun PDF généré dans la requête de chat).
    return ToolResult(
        content={"status": "ready", "note": "Rapport de pilotage prêt au téléchargement."},
        action={"type": "download", "url": "/api/analytics/dashboard/report/",
                "filename": "rapport-pilotage-kaydan.pdf"})


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
        name="generate_dashboard_report",
        description="Prépare le rapport de pilotage (PDF) au téléchargement.",
        parameters={"type": "object", "properties": {}},
        handler=_tool_generate_dashboard_report,
    ))


register_builtins()
