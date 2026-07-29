from django.urls import path

from .views import (
    CopilotChatAPIView,
    CopilotConversationDetailAPIView,
    CopilotConversationsAPIView,
)

urlpatterns = [
    path("chat/", CopilotChatAPIView.as_view(), name="copilot-chat"),
    path("conversations/", CopilotConversationsAPIView.as_view(),
         name="copilot-conversations"),
    path("conversations/<int:pk>/", CopilotConversationDetailAPIView.as_view(),
         name="copilot-conversation-detail"),
]
