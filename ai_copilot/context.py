"""Context Engine — reconstruit côté serveur le contexte de la page courante.

Le front envoie un contexte compact (route, id programme/parcelle sélectionné,
emprise carte…). On NE fait JAMAIS confiance à ces données comme autorité : on
ré-résout les ids en base (avec masquage) pour décrire la page à l'IA.
"""


def build_context_summary(user, client_context) -> str:
    client_context = client_context or {}
    parts = [f"route={client_context.get('route') or '?'}"]

    pid = client_context.get("program_id")
    if pid:
        from parcelaire.models import RealEstateProgram
        p = RealEstateProgram.objects.filter(is_active=True, pk=pid).first()
        if p:
            parts.append(f"programme sélectionné='{p.name}' (id={p.id})")

    parcel_id = client_context.get("parcel_id")
    if parcel_id:
        from parcelaire.models import Parcel
        pc = Parcel.objects.filter(is_active=True, pk=parcel_id).first()
        if pc:
            label = pc.lot_number or pc.parcel_code or f"#{pc.id}"
            parts.append(f"parcelle sélectionnée='{label}' (id={pc.id})")

    bbox = client_context.get("bbox")
    if bbox:
        parts.append(f"emprise carte visible={bbox}")
    layers = client_context.get("layers")
    if layers:
        parts.append(f"couches actives={layers}")

    return " ; ".join(parts)
