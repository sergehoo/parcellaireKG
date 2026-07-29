"""AI Gateway — adaptateur DeepSeek (API compatible OpenAI, function-calling).

Point d'entrée unique `chat_completion()`. D'autres fournisseurs (Claude,
OpenAI) + routage « Auto » viendront en Phase 2 derrière la même interface.
La clé vient de l'environnement ; aucun secret en dur.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    """Erreur d'appel au fournisseur LLM (config, réseau, HTTP)."""


def is_configured() -> bool:
    return bool(getattr(settings, "DEEPSEEK_API_KEY", ""))


def chat_completion(messages, tools=None, *, model=None, timeout=60):
    """Appelle DeepSeek /chat/completions et renvoie le JSON brut.

    `messages` : format OpenAI. `tools` : schémas de fonctions (function calling).
    """
    key = getattr(settings, "DEEPSEEK_API_KEY", "")
    if not key:
        raise GatewayError("DEEPSEEK_API_KEY n'est pas configurée.")

    payload = {
        "model": model or settings.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": settings.COPILOT_MAX_TOKENS,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        resp = requests.post(
            f"{settings.DEEPSEEK_API_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json=payload, timeout=timeout,
        )
    except requests.RequestException as exc:
        raise GatewayError(f"Fournisseur IA injoignable : {exc}") from exc

    if resp.status_code != 200:
        # Ne jamais logguer la clé ; tronquer le corps.
        logger.warning("DeepSeek HTTP %s : %s", resp.status_code, resp.text[:300])
        raise GatewayError(f"Fournisseur IA : HTTP {resp.status_code}.")
    return resp.json()
