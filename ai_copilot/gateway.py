"""AI Gateway — routage multi-fournisseurs derrière une interface unique.

`chat_completion()` accepte un SÉLECTEUR de moteur ('auto' | 'deepseek' |
'openai'/'chatgpt' | 'anthropic'/'claude'), le résout en fournisseur concret
(selon les clés réellement configurées) et renvoie TOUJOURS la forme OpenAI
(`{"choices":[{"message":{...}}]}`) — la boucle d'agent reste inchangée.

- DeepSeek & OpenAI : API compatible OpenAI (function calling natif).
- Anthropic : API Messages, traduite dans les deux sens (tools, tool_use).

Toutes les clés viennent de l'environnement ; aucun secret en dur, jamais
journalisé. Un fournisseur sans clé est simplement indisponible.
"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Alias de sélecteur → fournisseur canonique.
_ALIASES = {
    "auto": "auto",
    "deepseek": "deepseek",
    "openai": "openai", "chatgpt": "openai", "gpt": "openai",
    "anthropic": "anthropic", "claude": "anthropic",
}

# Libellés lisibles pour l'UI.
PROVIDER_LABELS = {
    "deepseek": "DeepSeek",
    "openai": "ChatGPT",
    "anthropic": "Claude",
}


class GatewayError(Exception):
    """Erreur d'appel au fournisseur LLM (config, réseau, HTTP)."""


def _key(provider):
    return {
        "deepseek": getattr(settings, "DEEPSEEK_API_KEY", ""),
        "openai": getattr(settings, "OPENAI_API_KEY", ""),
        "anthropic": getattr(settings, "ANTHROPIC_API_KEY", ""),
    }.get(provider, "")


def configured_providers():
    """Liste ordonnée (priorité) des fournisseurs dont la clé est présente."""
    priority = getattr(settings, "COPILOT_PROVIDER_PRIORITY",
                       ["deepseek", "openai", "anthropic"])
    return [p for p in priority if _key(p)]


def is_configured() -> bool:
    """Le Copilote est actif dès qu'AU MOINS un fournisseur est configuré."""
    return bool(configured_providers())


def available_engines():
    """Options de moteur pour le front : 'Auto' + chaque fournisseur configuré."""
    provs = configured_providers()
    engines = [{"value": p, "label": PROVIDER_LABELS.get(p, p)} for p in provs]
    if len(provs) > 1:
        engines.insert(0, {"value": "auto", "label": "Auto"})
    return engines


def _resolve(selector):
    """Sélecteur → fournisseur concret configuré, ou GatewayError."""
    canonical = _ALIASES.get((selector or "auto").lower(), "auto")
    provs = configured_providers()
    if not provs:
        raise GatewayError("Aucun fournisseur IA configuré.")
    if canonical == "auto":
        return provs[0]
    if canonical not in provs:
        raise GatewayError(
            f"Moteur « {PROVIDER_LABELS.get(canonical, canonical)} » non configuré.")
    return canonical


def chat_completion(messages, tools=None, *, model=None, timeout=60):
    """Route vers le fournisseur résolu et renvoie la forme OpenAI normalisée.

    `model` est un SÉLECTEUR de moteur (pas un nom de modèle brut).
    """
    provider = _resolve(model)
    if provider == "anthropic":
        return _anthropic_chat(messages, tools, timeout)
    return _openai_compatible_chat(provider, messages, tools, timeout)


# ---------------------------------------------------------------------
# Fournisseurs compatibles OpenAI (DeepSeek, OpenAI)
# ---------------------------------------------------------------------
def _openai_compatible_chat(provider, messages, tools, timeout):
    if provider == "openai":
        base = getattr(settings, "OPENAI_API_URL", "https://api.openai.com/v1")
        model_name = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
    else:  # deepseek
        base = f"{settings.DEEPSEEK_API_URL.rstrip('/')}"
        model_name = settings.DEEPSEEK_MODEL
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": settings.COPILOT_MAX_TOKENS,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    try:
        resp = requests.post(
            f"{base.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {_key(provider)}",
                     "Content-Type": "application/json"},
            json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise GatewayError(f"Fournisseur IA injoignable : {exc}") from exc
    if resp.status_code != 200:
        logger.warning("%s HTTP %s : %s", provider, resp.status_code, resp.text[:300])
        raise GatewayError(f"Fournisseur IA : HTTP {resp.status_code}.")
    return resp.json()


# ---------------------------------------------------------------------
# Anthropic (API Messages) — traduction bidirectionnelle vers la forme OpenAI
# ---------------------------------------------------------------------
def _to_anthropic(messages, tools):
    """Traduit messages+tools (format OpenAI) vers le format Anthropic."""
    system_parts, conv = [], []
    for m in messages:
        role = m.get("role")
        if role == "system":
            if m.get("content"):
                system_parts.append(m["content"])
        elif role == "tool":
            conv.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id") or "",
                "content": m.get("content") or "",
            }]})
        elif role == "assistant":
            blocks = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except (ValueError, TypeError):
                    args = {}
                blocks.append({"type": "tool_use", "id": tc.get("id") or fn.get("name"),
                               "name": fn.get("name"), "input": args})
            conv.append({"role": "assistant", "content": blocks or ""})
        else:  # user
            conv.append({"role": "user", "content": m.get("content") or ""})

    anthropic_tools = None
    if tools:
        anthropic_tools = [{
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object"}),
        } for t in tools if t.get("function")]
    return "\n\n".join(system_parts), conv, anthropic_tools


def _from_anthropic(data):
    """Traduit une réponse Anthropic vers la forme OpenAI attendue par l'agent."""
    text_parts, tool_calls = [], []
    for block in data.get("content") or []:
        if block.get("type") == "text":
            text_parts.append(block.get("text") or "")
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id"),
                "type": "function",
                "function": {"name": block.get("name"),
                             "arguments": json.dumps(block.get("input") or {},
                                                     ensure_ascii=False)},
            })
    message = {"content": "".join(text_parts)}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message}]}


def _anthropic_chat(messages, tools, timeout):
    system, conv, anthropic_tools = _to_anthropic(messages, tools)
    payload = {
        "model": getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        "max_tokens": settings.COPILOT_MAX_TOKENS,
        "messages": conv,
    }
    if system:
        payload["system"] = system
    if anthropic_tools:
        payload["tools"] = anthropic_tools
    base = getattr(settings, "ANTHROPIC_API_URL", "https://api.anthropic.com")
    try:
        resp = requests.post(
            f"{base.rstrip('/')}/v1/messages",
            headers={"x-api-key": _key("anthropic"),
                     "anthropic-version": getattr(settings, "ANTHROPIC_VERSION", "2023-06-01"),
                     "Content-Type": "application/json"},
            json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise GatewayError(f"Fournisseur IA injoignable : {exc}") from exc
    if resp.status_code != 200:
        logger.warning("anthropic HTTP %s : %s", resp.status_code, resp.text[:300])
        raise GatewayError(f"Fournisseur IA : HTTP {resp.status_code}.")
    return _from_anthropic(resp.json())
