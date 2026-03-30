from .provider_factory import VideoProviderFactory
from .prompt_builder import ConstructionPromptBuilder
from .storyboard import StoryboardGenerator

class ConstructionVideoAgent:
    def __init__(self, simulation, context):
        self.simulation = simulation
        self.context = context
        self.provider = VideoProviderFactory.make(simulation.provider)

    def prepare(self):
        master_prompt = ConstructionPromptBuilder.build_master_prompt(self.simulation, self.context)
        scenes = StoryboardGenerator.generate(self.simulation, self.context)
        return master_prompt, scenes

    def choose_generation_mode(self, scene, reference_image=None):
        if reference_image:
            return "image_to_video"
        return "text_to_video"