from ai_construction.models import SimulationProviderChoices
from .providers.runway_provider import RunwayVideoProvider
from .providers.veo_provider import VeoVideoProvider


class VideoProviderFactory:
    @staticmethod
    def make(provider_code: str):
        if provider_code == SimulationProviderChoices.RUNWAY:
            return RunwayVideoProvider()
        if provider_code == SimulationProviderChoices.VEO:
            return VeoVideoProvider()
        raise ValueError(f"Provider non supporté: {provider_code}")