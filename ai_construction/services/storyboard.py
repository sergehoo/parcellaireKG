DEFAULT_PHASES = [
    ("SITE", "Terrain initial", 4),
    ("EARTHWORK", "Terrassement et préparation", 4),
    ("FOUNDATION", "Fondations et dalle", 4),
    ("STRUCTURE", "Élévation de la structure", 5),
    ("FACADE", "Façades et clos couvert", 4),
    ("FINISHING", "Finitions et aménagements", 4),
    ("DELIVERY", "Bâtiment final livré", 5),
]


class StoryboardGenerator:
    @staticmethod
    def generate(simulation, context: dict) -> list[dict]:
        project_name = context.get("project_name", simulation.title)
        building_type = context.get("building_type", "bâtiment résidentiel premium")
        location = context.get("location", "Abidjan")
        total = simulation.target_duration_seconds or 30

        phases = DEFAULT_PHASES.copy()
        total_weight = sum(item[2] for item in phases)

        scenes = []
        order = 1
        for code, label, weight in phases:
            duration = max(3, round((weight / total_weight) * total))
            scenes.append({
                "order": order,
                "title": label,
                "phase_code": code,
                "duration_seconds": duration,
                "shot_type": "drone cinematic reveal" if order in [1, 7] else "mid aerial tracking shot",
                "environment": f"{project_name}, {location}, {building_type}",
                "weather": "clear daylight",
                "camera_motion": "slow cinematic movement",
                "prompt_text": (
                    f"Montrer la phase '{label}' du projet {project_name} avec un rendu photoréaliste, "
                    f"cohérent, premium et réaliste, dans le même environnement urbain."
                ),
            })
            order += 1

        return scenes