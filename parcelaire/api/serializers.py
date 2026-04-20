def serialize_orthophoto(self, ortho):
    if not ortho:
        return None

    bounds = None
    try:
        if ortho.bounds:
            bounds = json.loads(ortho.bounds.geojson)
    except Exception:
        bounds = None

    return {
        "id": ortho.id,
        "name": ortho.name,
        "slug": ortho.slug,
        "program_id": ortho.program_id,
        "program_name": ortho.program.name if ortho.program_id else None,
        "tiles_folder": ortho.tiles_folder,
        "tiles_url": ortho.tiles_url,
        "min_zoom": ortho.min_zoom,
        "max_zoom": ortho.max_zoom,
        "max_native_zoom": ortho.max_native_zoom,
        "capture_date": ortho.capture_date.isoformat() if ortho.capture_date else None,
        "reference_year": ortho.reference_year,
        "reference_month": ortho.reference_month,
        "period_label": ortho.period_label,
        "version": ortho.version,
        "is_current": ortho.is_current,
        "is_active": ortho.is_active,
        "bounds": bounds,
    }