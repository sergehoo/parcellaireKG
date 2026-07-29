"""Action Executor — exécute un appel d'outil AVEC contrôle de permission,
gestion des actions à effet de bord (confirmation humaine) et journalisation.

L'IA agit strictement avec les permissions de l'utilisateur courant : aucune
élévation. Toute action à effet de bord exige une confirmation explicite côté
UI (jamais déclenchée par une injection de prompt dans les données).
"""
import logging

from . import tools as registry
from .models import CopilotToolCall

logger = logging.getLogger(__name__)


def _redact(args):
    """N'inscrit au journal que des valeurs tronquées (jamais de contenu long/sensible)."""
    if not isinstance(args, dict):
        return {}
    return {k: str(v)[:120] for k, v in args.items()}


def _journal(user, conversation, name, args, status, detail=""):
    CopilotToolCall.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        conversation=conversation,
        tool_name=name[:100],
        arguments=_redact(args),
        status=status,
        detail=(detail or "")[:500],
    )


def run_tool(user, name, args, context, conversation=None, allow_side_effects=False):
    spec = registry.get(name)
    if spec is None:
        _journal(user, conversation, name, args, "unknown")
        return registry.ToolResult(content={"error": f"Outil inconnu : {name}"})

    if spec.permission and not (user.is_superuser or user.has_perm(spec.permission)):
        _journal(user, conversation, name, args, "denied", spec.permission)
        return registry.ToolResult(
            content={"error": "Vous n'avez pas la permission d'utiliser cet outil."})

    if spec.side_effecting and not allow_side_effects:
        _journal(user, conversation, name, args, "needs_confirmation")
        return registry.ToolResult(
            content={"status": "confirmation_required",
                     "message": "Action à effet de bord : confirmation utilisateur requise."},
            action={"type": "confirm", "tool": name, "arguments": args})

    try:
        result = spec.handler(user, args or {}, context)
        _journal(user, conversation, name, args, "ok")
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("Copilot : outil %s a échoué", name)
        _journal(user, conversation, name, args, "error", str(exc))
        return registry.ToolResult(content={"error": f"Erreur lors de l'exécution : {exc}"})
