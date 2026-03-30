import os
import requests
from .base import BaseVideoProvider


class RunwayVideoProvider(BaseVideoProvider):
    def __init__(self):
        self.api_key = os.getenv("RUNWAY_API_KEY")
        self.base_url = "https://api.dev.runwayml.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_video_from_text(self, *, prompt: str, duration: int, ratio: str, resolution: str):
        payload = {
            "model": "gen4_turbo",
            "promptText": prompt,
            "duration": duration,
            "ratio": ratio,
        }
        response = requests.post(
            f"{self.base_url}/tasks",
            json=payload,
            headers=self.headers,
            timeout=90,
        )
        response.raise_for_status()
        return response.json()

    def generate_video_from_image(self, *, prompt: str, image_path: str, duration: int, ratio: str, resolution: str):
        # selon ton workflow, tu peux d'abord uploader l'image chez Runway si requis
        raise NotImplementedError("Implémenter selon le flux d’upload image Runway choisi.")

    def get_job_status(self, job_id: str):
        response = requests.get(
            f"{self.base_url}/tasks/{job_id}",
            headers=self.headers,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def download_result(self, job_id: str, output_path: str):
        job = self.get_job_status(job_id)
        output_url = job.get("output", [None])[0]
        if not output_url:
            raise ValueError("Aucune URL de sortie disponible.")

        with requests.get(output_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        return output_path