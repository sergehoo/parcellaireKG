"""API du Copilote IA : POST /api/copilot/chat/."""
import json

from django.db.models import Count
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .agent import run_confirmed, run_turn
from .executor import read_confirm_token
from .gateway import GatewayError, available_engines, is_configured
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

    def _client_context(self, request):
        client_context = request.data.get("context") or {}
        if not isinstance(client_context, dict):
            client_context = {}
        # Whitelist des clés + borne de taille (anti-amplification de tokens/coût).
        client_context = {k: client_context[k] for k in
                          ("route", "program_id", "parcel_id", "customer_id", "bbox", "layers")
                          if k in client_context}
        if len(json.dumps(client_context, default=str)) > 4000:
            client_context = {"route": str(client_context.get("route", ""))[:200]}
        return client_context

    def _resolve_conversation(self, request, default_title):
        conv = None
        conv_id = request.data.get("conversation_id")
        if conv_id:
            conv = CopilotConversation.objects.filter(pk=conv_id, user=request.user).first()
        if conv is None:
            conv = CopilotConversation.objects.create(
                user=request.user, title=default_title[:60])
        return conv

    def post(self, request):
        client_context = self._client_context(request)

        # --- Confirmation d'une action à effet de bord (chemin hors-LLM) ---
        # Exige un jeton signé émis par un vrai tour LLM : impossible de forger
        # une confirmation, et l'outil + les arguments exécutés proviennent du
        # jeton (non falsifiables côté client).
        confirm = request.data.get("confirm_action")
        if isinstance(confirm, dict) and confirm.get("token"):
            data = read_confirm_token(request.user, confirm.get("token"))
            if data is None:
                return Response({"detail": "Confirmation invalide ou expirée."}, status=400)
            tool = str(data.get("t") or "")[:100]
            args = data.get("a") if isinstance(data.get("a"), dict) else {}
            conv = self._resolve_conversation(request, f"Action : {tool}")
            return Response(run_confirmed(request.user, tool, args, client_context, conv))

        # --- Message conversationnel (nécessite le LLM) ---
        if not is_configured():
            return Response(
                {"detail": "Copilote IA non configuré (DEEPSEEK_API_KEY manquante)."},
                status=503)

        message = (request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "Message vide."}, status=400)
        if len(message) > 4000:
            return Response({"detail": "Message trop long (max 4000 caractères)."}, status=400)

        model = request.data.get("model") or None  # Phase 2 : routage multi-modèles
        conv = self._resolve_conversation(request, message)

        try:
            out = run_turn(request.user, message, client_context, conv, model=model)
        except GatewayError as exc:
            return Response({"detail": str(exc)}, status=502)
        return Response(out)


@extend_schema_view(get=extend_schema(
    summary="Copilote IA — moteurs disponibles",
    description="Liste les moteurs LLM réellement configurés (clé présente) : "
                "'Auto' + chaque fournisseur. Vide si le Copilote est désactivé.",
    tags=["Copilot"],
    responses={200: OpenApiResponse(description="Moteurs disponibles.")},
))
class CopilotEnginesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"engines": available_engines(), "configured": is_configured()})


@extend_schema_view(get=extend_schema(
    summary="Copilote IA — historique des conversations",
    description="Liste les conversations du Copilote de l'utilisateur courant "
                "(les siennes uniquement), les plus récentes d'abord.",
    tags=["Copilot"],
    responses={200: OpenApiResponse(description="Liste des conversations.")},
))
class CopilotConversationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (CopilotConversation.objects
              .filter(user=request.user)
              .annotate(n=Count("messages"))
              .order_by("-updated_at")[:50])
        data = [{"id": c.id, "title": c.title or f"Conversation #{c.id}",
                 "updated_at": c.updated_at, "message_count": c.n} for c in qs]
        return Response({"conversations": data})


@extend_schema_view(get=extend_schema(
    summary="Copilote IA — messages d'une conversation",
    description="Renvoie les messages (utilisateur/assistant) d'une conversation "
                "appartenant à l'utilisateur courant. 404 si elle ne lui appartient pas.",
    tags=["Copilot"],
    responses={200: OpenApiResponse(description="Messages de la conversation."),
               404: OpenApiResponse(description="Introuvable.")},
))
class CopilotConversationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        conv = CopilotConversation.objects.filter(pk=pk, user=request.user).first()
        if conv is None:
            return Response({"detail": "Conversation introuvable."}, status=404)
        msgs = (conv.messages.filter(role__in=["user", "assistant"])
                .order_by("created_at", "id"))
        data = [{"role": m.role, "content": m.content,
                 "actions": (m.metadata or {}).get("actions", [])} for m in msgs]
        return Response({"id": conv.id, "title": conv.title, "messages": data})
