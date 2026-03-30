from rest_framework import serializers
from .models import (
    ConstructionSimulationProject,
    ConstructionSimulationScene,
    ConstructionSimulationAsset,
)


class ConstructionSimulationAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConstructionSimulationAsset
        fields = [
            "id", "asset_type", "file", "label", "sort_order", "metadata"
        ]


class ConstructionSimulationSceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConstructionSimulationScene
        fields = [
            "id",
            "order",
            "title",
            "phase_code",
            "duration_seconds",
            "shot_type",
            "environment",
            "weather",
            "camera_motion",
            "prompt_text",
            "negative_prompt",
            "reference_image",
            "generated_image",
            "generated_video",
            "status",
        ]


class ConstructionSimulationProjectSerializer(serializers.ModelSerializer):
    scenes = ConstructionSimulationSceneSerializer(many=True, read_only=True)
    assets = ConstructionSimulationAssetSerializer(many=True, read_only=True)

    class Meta:
        model = ConstructionSimulationProject
        fields = [
            "id",
            "program",
            "asset",
            "parcel",
            "title",
            "slug",
            "provider",
            "style",
            "camera_style",
            "target_duration_seconds",
            "aspect_ratio",
            "target_resolution",
            "include_audio",
            "include_voiceover",
            "include_branding",
            "include_watermark",
            "language",
            "status",
            "prompt_seed",
            "negative_prompt",
            "business_context",
            "technical_context",
            "final_video",
            "thumbnail",
            "total_scenes",
            "completed_scenes",
            "progress_percent",
            "error_message",
            "created_at",
            "updated_at",
            "started_at",
            "finished_at",
            "scenes",
            "assets",
        ]
        read_only_fields = [
            "status",
            "final_video",
            "thumbnail",
            "total_scenes",
            "completed_scenes",
            "progress_percent",
            "error_message",
            "created_at",
            "updated_at",
            "started_at",
            "finished_at",
        ]


class ConstructionSimulationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConstructionSimulationProject
        fields = [
            "program",
            "asset",
            "parcel",
            "title",
            "provider",
            "style",
            "camera_style",
            "target_duration_seconds",
            "aspect_ratio",
            "target_resolution",
            "include_audio",
            "include_voiceover",
            "include_branding",
            "include_watermark",
            "language",
            "prompt_seed",
            "negative_prompt",
        ]