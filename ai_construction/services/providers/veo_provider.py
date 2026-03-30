import os
from .base import BaseVideoProvider


class VeoVideoProvider(BaseVideoProvider):
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.model = os.getenv("VEO_MODEL_NAME", "veo-3.0-generate-001")

    def generate_video_from_text(self, *, prompt: str, duration: int, ratio: str, resolution: str):
        # à brancher via SDK Vertex AI ou Gemini API selon ton choix d’infra
        raise NotImplementedError("Implémenter avec Vertex AI SDK ou Gemini API.")

    def generate_video_from_image(self, *, prompt: str, image_path: str, duration: int, ratio: str, resolution: str):
        raise NotImplementedError("Implémenter avec image-guided generation Veo.")

    def get_job_status(self, job_id: str):
        raise NotImplementedError

    def download_result(self, job_id: str, output_path: str):
        raise NotImplementedError