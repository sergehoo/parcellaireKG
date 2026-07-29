from django.urls import path

from .views import CopilotChatAPIView

urlpatterns = [
    path("chat/", CopilotChatAPIView.as_view(), name="copilot-chat"),
]
