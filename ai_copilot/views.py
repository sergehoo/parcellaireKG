"""API du Copilote IA : POST /api/copilot/chat/."""
import json

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .agent import run_turn
from .gateway import GatewayError, is_configured
from .models import CopilotConversation


@extend_schema_view(post=extend_schema(
    summary="Copilote IA — envoyer un message",
    description="Envoie un message au Copilote. L'IA peut appeler des outils métier "
                "(recherche, carte, dashboard, rapport) dans la limite des permissions "
                "de l'utilisateur. Renvoie la réponse + d'éventuelles actions UI.",
    tags=["Copilot"],
    request=None,
    responses={200: OpenApiResponse(description="Réponse + actions."),
               503: OpenApiResponse(description="Copilote non configuré.")},
))
class CopilotChatAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "copilot"

    def post(self, request):
        if not is_configured():
            return Response(
                {"detail": "Copilote IA non configuré (DEEPSEEK_API_KEY manquante)."},
                status=503)

        message = (request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "Message vide."}, status=400)
        if len(message) > 4000:
            return Response({"detail": "Message trop long (max 4000 caractères)."}, status=400)

        client_context = request.data.get("context") or {}
        if not isinstance(client_context, dict):
            client_context = {}
        # Whitelist des clés + borne de taille (anti-amplification de tokens/coût).
        client_context = {k: client_context[k] for k in
                          ("route", "program_id", "parcel_id", "bbox", "layers")
                          if k in client_context}
        if len(json.dumps(client_context, default=str)) > 4000:
            client_context = {"route": str(client_context.get("route", ""))[:200]}

        model = request.data.get("model") or None  # Phase 2 : routage multi-modèles

        conv = None
        conv_id = request.data.get("conversation_id")
        if conv_id:
            conv = CopilotConversation.objects.filter(pk=conv_id, user=request.user).first()
        if conv is None:
            conv = CopilotConversation.objects.create(
                user=request.user, title=message[:60])

        try:
            out = run_turn(request.user, message, client_context, conv, model=model)
        except GatewayError as exc:
            return Response({"detail": str(exc)}, status=502)
        return Response(out)
