"""
llm/router.py
=============
Tiered LLM routing.

Primary:  Ollama cloud (qwen3.5:397b with web search)
Fallback: Claude CLI (Opus via Pro subscription)

Returns (model_label, response_text) so callers know which model ran.
"""

from __future__ import annotations

import logging
import os
import re
import shutil

import config
from llm import claude_cli, ollama as ollama_provider

log = logging.getLogger(__name__)

_ARTIFACT_RE = re.compile(
    r"<｜tool.*?｜>|<\|.*?\|>|<think>.*?</think>",
    re.DOTALL,
)


def _strip_artifacts(text: str) -> str:
    return _ARTIFACT_RE.sub("", text).strip()


def _cli_is_available() -> bool:
    return bool(
        os.path.isfile(config.CLAUDE_CLI_PATH)
        or shutil.which(config.CLAUDE_CLI_PATH)
    )


def call_llm(system: str, user: str, temperature: float = 0.3, think: bool = True) -> tuple[str, str]:
    """
    Routes to the best available model.

    Returns:
        (model_label, response_text)

    Raises:
        RuntimeError if all providers fail.
    """
    # Primary: Ollama
    if config.OLLAMA_API_KEY:
        try:
            text = ollama_provider.run(system, user, temperature=temperature, think=think)
            text = _strip_artifacts(text)
            return (f"Ollama {config.OLLAMA_CLOUD_MODEL}", text)
        except Exception as exc:
            log.warning("Ollama failed — switching to Claude CLI | error=%s", str(exc)[:200])
    else:
        log.warning("OLLAMA_API_KEY not set — skipping Ollama, trying Claude CLI")

    # Fallback: Claude CLI
    if not _cli_is_available():
        raise RuntimeError(
            "Ollama unavailable and Claude CLI not found. "
            "Set OLLAMA_API_KEY or ensure the claude CLI is installed."
        )

    try:
        text = claude_cli.run(system, user, temperature=temperature)
        return (f"Claude {config.CLAUDE_CLI_MODEL} (fallback)", text)
    except Exception as exc:
        log.error("Claude CLI fallback also failed | error=%s", exc, exc_info=True)
        raise RuntimeError(f"All LLM providers failed. Last error: {exc}") from exc
