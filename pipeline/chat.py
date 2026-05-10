"""
pipeline/chat.py
================
Brain-augmented chat pipeline.

Runs an Ollama Cloud agentic loop with brain tools + web tools attached:
  - gbrain_query   - hybrid search across all imported stores
  - gbrain_search  - exact-keyword search (best for names / IDs)
  - gbrain_get     - fetch full page contents by slug
  - web_search     - Ollama Cloud built-in web search
  - web_fetch      - Ollama Cloud built-in web fetch

Two entry points:
  - ask(question)            -> one-shot, no conversation memory
  - chat(history, message)   -> multi-turn, caller persists history

Provider: Ollama Cloud (requires OLLAMA_API_KEY). Chat model defaults to
hermes3:latest; override with CHAT_MODEL env var.
"""

from __future__ import annotations

import logging
import os

import ollama as ollama_sdk
from ollama import web_fetch, web_search

import config
from brain import gbrain_cli
from prompts.chat import system_prompt as _chat_system_prompt

log = logging.getLogger(__name__)

_MAX_STEPS = 10
_MAX_HISTORY_TURNS = 12

_CHAT_MODEL = os.getenv("CHAT_MODEL", "hermes3:latest")


# Tool registry. Functions Ollama can introspect for tool schema.

def gbrain_query(question: str, limit: int = 5) -> str:
    """Hybrid semantic + keyword search across the user's brain (notes, skills, projects, interview prep, clarity outputs, company pages). Use for natural-language questions like 'what did I write about X' or 'find notes related to Y'."""
    return gbrain_cli.query(question, limit=limit)


def gbrain_search(keyword: str, limit: int = 5) -> str:
    """Exact-keyword search across the brain. Use for proper nouns, IDs, or specific terms where semantic search adds noise."""
    return gbrain_cli.search(keyword, limit=limit)


def gbrain_get(slug: str) -> str:
    """Fetch the full contents of a brain page by its slug (e.g. 'companies/aveni' or 'projects/clarity-bot'). Use after gbrain_query/gbrain_search returns a slug worth reading in full."""
    return gbrain_cli.get_page(slug)


_CUSTOM_TOOLS = {
    "gbrain_query": gbrain_query,
    "gbrain_search": gbrain_search,
    "gbrain_get": gbrain_get,
}


def _make_client() -> ollama_sdk.Client:
    return ollama_sdk.Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"},
    )


def _run_loop(messages: list[dict]) -> str:
    """Drives the Ollama agentic loop until the model returns a final reply."""
    client = _make_client()
    options = {"num_predict": 2048, "temperature": 0.4, "num_ctx": 32768}
    tools = [web_search, web_fetch] + list(_CUSTOM_TOOLS.values())

    for step in range(1, _MAX_STEPS + 1):
        log.info("Chat loop | step=%d/%d | model=%s | msgs=%d",
                 step, _MAX_STEPS, _CHAT_MODEL, len(messages))

        response = client.chat(
            model=_CHAT_MODEL,
            messages=messages,
            tools=tools,
            options=options,
        )
        messages.append(response.message)

        if not response.message.tool_calls:
            content = response.message.content or ""
            log.info("Chat loop done | step=%d | output_len=%d", step, len(content))
            return content

        log.info("Tool calls | step=%d | count=%d", step, len(response.message.tool_calls))
        for call in response.message.tool_calls:
            name = call.function.name
            args = call.function.arguments or {}

            try:
                if name in _CUSTOM_TOOLS:
                    result = _CUSTOM_TOOLS[name](**args)
                else:
                    # Ollama Cloud built-in (web_search / web_fetch)
                    result = getattr(client, name)(**args)
                result_text = str(result)[:config.OLLAMA_MAX_TOOL_RESULT_CHARS]
                log.info("Tool ok | name=%s | len=%d", name, len(result_text))
            except Exception as exc:
                result_text = f"Tool '{name}' failed: {exc}"
                log.error("Tool err | name=%s | %s", name, exc)

            messages.append({"role": "tool", "content": result_text, "tool_name": name})

    raise RuntimeError(f"Chat loop exceeded {_MAX_STEPS} steps without final reply")


# Public API

def ask(question: str) -> str:
    """One-shot: no conversation memory. Returns the assistant reply."""
    messages = [
        {"role": "system", "content": _chat_system_prompt()},
        {"role": "user", "content": question},
    ]
    return _run_loop(messages)


def chat(history: list[dict], user_message: str) -> tuple[str, list[dict]]:
    """
    Multi-turn: caller passes prior history (list of {role, content}).
    Returns (assistant_reply, updated_history). History is trimmed to the
    last _MAX_HISTORY_TURNS exchanges.
    """
    trimmed = history[-(_MAX_HISTORY_TURNS * 2):] if history else []
    messages = (
        [{"role": "system", "content": _chat_system_prompt()}]
        + trimmed
        + [{"role": "user", "content": user_message}]
    )
    reply = _run_loop(messages)

    new_history = trimmed + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return reply, new_history[-(_MAX_HISTORY_TURNS * 2):]
