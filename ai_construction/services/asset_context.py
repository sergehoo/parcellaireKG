class AssetContextBuilder:
    @staticmethod
    def build_from_asset(asset):
        parcel = getattr(asset, "parcel", None)

        return {
            "project_name": asset.label,
            "building_type": (
                asset.property_type.label if getattr(asset, "property_type", None) else "bâtiment immobilier"
            ),
            "floors": getattr(asset, "floors", None) or "R+1",
            "location": "Abidjan, Côte d’Ivoire",
            "materials": "béton, verre, aluminium, enduit premium",
            "surface": getattr(asset, "built_area_m2", None),
            "parcel_surface": getattr(parcel, "official_area_m2", None) if parcel else None,
            "construction_progress": getattr(asset, "construction_progress", None),
        }