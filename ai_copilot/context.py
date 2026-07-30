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

    customer_id = client_context.get("customer_id")
    if customer_id:
        from parcelaire.api.views import user_can_view_patient_data
        from parcelaire.models import Customer
        cu = Customer.objects.filter(is_active=True, pk=customer_id).first()
        if cu:
            # Le nom du client n'est révélé qu'avec le droit PII ; sinon on
            # signale seulement qu'une fiche client est ouverte (id).
            if user_can_view_patient_data(user):
                parts.append(f"client sélectionné='{cu}' (id={cu.id})")
            else:
                parts.append(f"fiche client ouverte (id={cu.id}, nom masqué)")

    # bbox/layers viennent du client : on NORMALISE avant d'interpoler dans le
    # prompt système (jamais de texte libre client dans le prompt de plus haute
    # priorité — évite un self-jailbreak du ton de l'assistant).
    bbox = client_context.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            parts.append(f"emprise carte visible={[round(float(x), 5) for x in bbox]}")
        except (TypeError, ValueError):
            pass
    layers = client_context.get("layers")
    if isinstance(layers, (list, tuple)):
        safe = [str(x)[:30] for x in list(layers)[:12] if isinstance(x, (str, int))]
        if safe:
            parts.append(f"couches actives={safe}")

    return " ; ".join(parts)
