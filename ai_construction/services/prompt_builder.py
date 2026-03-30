class ConstructionPromptBuilder:
    @staticmethod
    def build_master_prompt(simulation, context: dict) -> str:
        location = context.get("location", "Abidjan, Côte d’Ivoire")
        building_type = context.get("building_type", "bâtiment résidentiel premium")
        style = simulation.style.lower()
        camera_style = simulation.camera_style.lower()
        floors = context.get("floors", "plusieurs niveaux")
        materials = context.get("materials", "béton, verre, peinture haut de gamme")
        project_name = context.get("project_name", simulation.title)

        return f"""
Créer une simulation vidéo {style} et photoréaliste de l'évolution d'un chantier immobilier.
Projet: {project_name}
Lieu: {location}
Type de bâtiment: {building_type}
Niveaux: {floors}
Matériaux dominants: {materials}
Style de caméra: {camera_style}
Conserver une cohérence stricte du bâtiment, de la parcelle, des volumes et du style architectural.
Montrer une progression réaliste des travaux depuis le terrain jusqu'au bâtiment finalisé.
Rendu premium, crédible, commercialisable, lumière naturelle, détails réalistes du chantier.
""".strip()

    @staticmethod
    def build_scene_prompt(scene_data: dict) -> str:
        return f"""
{scene_data['title']}.
Phase: {scene_data['phase_code']}.
Angle caméra: {scene_data['shot_type']}.
Environnement: {scene_data['environment']}.
Météo: {scene_data['weather']}.
Mouvement caméra: {scene_data['camera_motion']}.
Instruction visuelle: {scene_data['prompt_text']}.
Conserver strictement l'identité visuelle du même projet immobilier.
""".strip()

    @staticmethod
    def build_negative_prompt() -> str:
        return (
            "cartoon, low quality, deformed building, inconsistent facade, duplicated objects, "
            "broken geometry, unrealistic workers, blurry crane, wrong perspective, extra floors"
        )