from abc import ABC, abstractmethod


class BaseVideoProvider(ABC):
    @abstractmethod
    def generate_video_from_text(self, *, prompt: str, duration: int, ratio: str, resolution: str):
        raise NotImplementedError

    @abstractmethod
    def generate_video_from_image(self, *, prompt: str, image_path: str, duration: int, ratio: str, resolution: str):
        raise NotImplementedError

    @abstractmethod
    def get_job_status(self, job_id: str):
        raise NotImplementedError

    @abstractmethod
    def download_result(self, job_id: str, output_path: str):
        raise NotImplementedError