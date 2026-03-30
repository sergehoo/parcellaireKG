import os
import tempfile
from celery import shared_task
from django.utils import timezone
from django.core.files import File

from .models import (
    ConstructionSimulationProject,
    ConstructionSimulationScene,
    ConstructionSimulationLog,
    ConstructionSimulationVersion,
)
from .services.storyboard import StoryboardGenerator
from .services.prompt_builder import ConstructionPromptBuilder
from .services.provider_factory import VideoProviderFactory
from .services.ffmpeg_service import FFmpegService


def log(simulation, message, level="INFO", scene=None, extra=None):
    ConstructionSimulationLog.objects.create(
        simulation=simulation,
        scene=scene,
        level=level,
        message=message,
        extra=extra or {},
    )


@shared_task
def launch_simulation(simulation_id):
    simulation = ConstructionSimulationProject.objects.get(id=simulation_id)
    simulation.status = "STORYBOARDING"
    simulation.started_at = timezone.now()
    simulation.save(update_fields=["status", "started_at", "updated_at"])

    context = {
        "project_name": simulation.title,
        "location": "Abidjan, Côte d’Ivoire",
        "building_type": "immeuble résidentiel premium",
        "floors": "R+8",
        "materials": "béton, verre, aluminium, finitions premium",
    }

    simulation.prompt_seed = ConstructionPromptBuilder.build_master_prompt(simulation, context)
    simulation.negative_prompt = ConstructionPromptBuilder.build_negative_prompt()
    simulation.save(update_fields=["prompt_seed", "negative_prompt", "updated_at"])

    scenes_data = StoryboardGenerator.generate(simulation, context)

    simulation.scenes.all().delete()
    scenes = []
    for item in scenes_data:
        scenes.append(
            ConstructionSimulationScene(
                simulation=simulation,
                order=item["order"],
                title=item["title"],
                phase_code=item["phase_code"],
                duration_seconds=item["duration_seconds"],
                shot_type=item["shot_type"],
                environment=item["environment"],
                weather=item["weather"],
                camera_motion=item["camera_motion"],
                prompt_text=ConstructionPromptBuilder.build_scene_prompt(item),
                negative_prompt=simulation.negative_prompt,
                status="READY",
            )
        )
    ConstructionSimulationScene.objects.bulk_create(scenes)

    simulation.total_scenes = len(scenes)
    simulation.status = "GENERATING_VIDEOS"
    simulation.save(update_fields=["total_scenes", "status", "updated_at"])

    log(simulation, "Storyboard généré avec succès.")

    for scene in simulation.scenes.all():
        generate_scene_video.delay(str(scene.id))

    return True


@shared_task
def generate_scene_video(scene_id):
    scene = ConstructionSimulationScene.objects.select_related("simulation").get(id=scene_id)
    simulation = scene.simulation
    provider = VideoProviderFactory.make(simulation.provider)

    scene.status = "PROCESSING"
    scene.save(update_fields=["status", "updated_at"])

    try:
        result = provider.generate_video_from_text(
            prompt=scene.prompt_text,
            duration=scene.duration_seconds,
            ratio=simulation.aspect_ratio,
            resolution=simulation.target_resolution,
        )

        job_id = result.get("id") or result.get("taskId") or result.get("job_id")
        scene.provider_job_id = job_id or ""
        scene.provider_payload = result
        scene.status = "SUBMITTED"
        scene.save(update_fields=["provider_job_id", "provider_payload", "status", "updated_at"])

        poll_scene_generation.delay(str(scene.id))

    except Exception as exc:
        scene.status = "FAILED"
        scene.save(update_fields=["status", "updated_at"])
        simulation.status = "FAILED"
        simulation.error_message = str(exc)
        simulation.save(update_fields=["status", "error_message", "updated_at"])
        log(simulation, f"Erreur génération scène {scene.order}: {exc}", level="ERROR", scene=scene)
        raise


@shared_task(bind=True, max_retries=60, default_retry_delay=20)
def poll_scene_generation(self, scene_id):
    scene = ConstructionSimulationScene.objects.select_related("simulation").get(id=scene_id)
    simulation = scene.simulation
    provider = VideoProviderFactory.make(simulation.provider)

    try:
        job = provider.get_job_status(scene.provider_job_id)
        status = str(job.get("status", "")).upper()

        if status in ["SUCCEEDED", "COMPLETED", "DONE"]:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                output_path = tmp.name

            provider.download_result(scene.provider_job_id, output_path)

            with open(output_path, "rb") as f:
                scene.generated_video.save(
                    f"scene_{scene.order}.mp4",
                    File(f),
                    save=False,
                )

            scene.status = "COMPLETED"
            scene.save(update_fields=["generated_video", "status", "updated_at"])

            completed = scene.simulation.scenes.filter(status="COMPLETED").count()
            total = scene.simulation.scenes.count()
            simulation.completed_scenes = completed
            simulation.progress_percent = round((completed / total) * 100) if total else 0
            simulation.save(update_fields=["completed_scenes", "progress_percent", "updated_at"])

            log(simulation, f"Scène {scene.order} terminée.", scene=scene)

            if completed == total:
                assemble_simulation_video.delay(str(simulation.id))
            return

        if status in ["FAILED", "ERROR", "CANCELED"]:
            scene.status = "FAILED"
            scene.save(update_fields=["status", "updated_at"])
            simulation.status = "FAILED"
            simulation.error_message = f"Echec provider sur scène {scene.order}"
            simulation.save(update_fields=["status", "error_message", "updated_at"])
            log(simulation, f"Echec scène {scene.order}", level="ERROR", scene=scene, extra=job)
            return

        raise self.retry()

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def assemble_simulation_video(simulation_id):
    simulation = ConstructionSimulationProject.objects.get(id=simulation_id)
    simulation.status = "ASSEMBLING"
    simulation.save(update_fields=["status", "updated_at"])

    video_paths = [
        scene.generated_video.path
        for scene in simulation.scenes.filter(status="COMPLETED").order_by("order")
        if scene.generated_video
    ]

    if not video_paths:
        simulation.status = "FAILED"
        simulation.error_message = "Aucune vidéo de scène disponible."
        simulation.save(update_fields=["status", "error_message", "updated_at"])
        return

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        output_path = tmp.name

    FFmpegService.concat_videos(video_paths, output_path)

    with open(output_path, "rb") as f:
        simulation.final_video.save(f"{simulation.id}.mp4", File(f), save=False)

    simulation.status = "COMPLETED"
    simulation.progress_percent = 100
    simulation.finished_at = timezone.now()
    simulation.save(update_fields=["final_video", "status", "progress_percent", "finished_at", "updated_at"])

    version_number = (simulation.versions.count() or 0) + 1
    ConstructionSimulationVersion.objects.create(
        simulation=simulation,
        version_number=version_number,
        config_snapshot={
            "provider": simulation.provider,
            "style": simulation.style,
            "camera_style": simulation.camera_style,
            "target_duration_seconds": simulation.target_duration_seconds,
            "aspect_ratio": simulation.aspect_ratio,
        },
        prompt_snapshot={
            "prompt_seed": simulation.prompt_seed,
            "negative_prompt": simulation.negative_prompt,
        },
        final_video=simulation.final_video,
    )

    log(simulation, "Vidéo finale assemblée avec succès.")