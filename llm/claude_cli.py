"""
llm/claude_cli.py
=================
Runs the Claude CLI as a subprocess.
Primary analyst — consumes Pro subscription quota at zero marginal API cost.
"""

from __future__ import annotations

import logging
import subprocess

import config

log = logging.getLogger(__name__)

_QUOTA_SIGNALS = frozenset(
    ("usage limit", "rate limit", "quota", "429", "too many requests", "5-hour", "reset")
)


def is_quota_error(message: str) -> bool:
    msg = message.lower()
    return any(signal in msg for signal in _QUOTA_SIGNALS)


def run(system: str, user: str, temperature: float = 0.3) -> str:
    """
    Calls Claude CLI and returns the text response.
    Raises RuntimeError on non-zero exit so the router can decide whether to fallback.
    Note: Claude CLI does not expose a --temperature flag; the parameter is accepted
    for interface consistency with the Ollama provider but has no effect here.
    """
    log.info(
        "Claude CLI call start | model=%s | user_len=%d",
        config.CLAUDE_CLI_MODEL, len(user),
    )

    result = subprocess.run(
        [
            config.CLAUDE_CLI_PATH,
            "-p", user,
            "--model",               config.CLAUDE_CLI_MODEL,
            "--append-system-prompt", system,
            "--output-format",       "text",
            "--no-session-persistence",
            "--permission-mode",     "bypassPermissions",
            "--allowedTools",        "WebSearch",
        ],
        capture_output=True,
        text=True,
        timeout=config.CLAUDE_CLI_TIMEOUT,
    )

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        log.error("Claude CLI failed | exit=%d | detail=%s", result.returncode, err[:300])
        raise RuntimeError(f"claude CLI exited {result.returncode}: {err}")

    output = result.stdout.strip()
    log.info("Claude CLI call complete | output_len=%d", len(output))
    return output
