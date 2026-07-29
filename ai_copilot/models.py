"""Modèles du Copilote IA : conversations, messages et journal d'audit des
appels d'outils (gouvernance / traçabilité — chaque action IA est tracée)."""
from django.conf import settings
from django.db import models


class CopilotConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="copilot_conversations")
    title = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation #{self.pk} ({self.user_id})"


class CopilotMessage(models.Model):
    ROLE_CHOICES = [("user", "Utilisateur"), ("assistant", "Assistant"), ("tool", "Outil")]

    conversation = models.ForeignKey(
        CopilotConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField(blank=True, default="")
    # Actions UI renvoyées (map.focus, download…) + méta.
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class CopilotToolCall(models.Model):
    """Journal d'audit immuable de chaque appel d'outil par l'IA."""
    STATUS_CHOICES = [
        ("ok", "OK"), ("denied", "Refusé (permission)"),
        ("needs_confirmation", "Confirmation requise"),
        ("unknown", "Outil inconnu"), ("error", "Erreur"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="copilot_tool_calls")
    conversation = models.ForeignKey(
        CopilotConversation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tool_calls")
    tool_name = models.CharField(max_length=100)
    # Arguments déjà expurgés du sensible avant journalisation.
    arguments = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    detail = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tool_name", "status"])]
