"""
config.py
=========
Single source of truth for all runtime configuration.
Reads from .env / environment variables. Fails fast on missing required values.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_INPUT_TOKEN  = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_OUTPUT_TOKEN = _require("TELEGRAM_OUTPUT_BOT_TOKEN")
TELEGRAM_CHAT_ID      = _require("TELEGRAM_CHAT_ID")

# ── Claude CLI (primary analyst) ──────────────────────────────────────────────
_cli_path_env    = _optional("CLAUDE_CLI_PATH", "claude")
CLAUDE_CLI_PATH  = shutil.which(_cli_path_env) or _cli_path_env
CLAUDE_CLI_MODEL = _optional("CLAUDE_CLI_MODEL", "claude-opus-4-7")
CLAUDE_CLI_TIMEOUT = int(_optional("CLAUDE_CLI_TIMEOUT", "300"))

# ── Ollama cloud (fallback + image generation) ────────────────────────────────
OLLAMA_API_KEY     = _optional("OLLAMA_API_KEY")
OLLAMA_CLOUD_MODEL = _optional("OLLAMA_CLOUD_MODEL", "qwen3.5:397b")
OLLAMA_IMAGE_MODEL = _optional("OLLAMA_IMAGE_MODEL", "qwen3-vl:235b")  # Note: VL = vision-language (reads images, does not generate them)
OLLAMA_MAX_TOOL_RESULT_CHARS = 8_000

# ── Skills ─────────────────────────────────────────────────────────────────────
CLARITY_SKILL_PATH = BASE_DIR / "skills" / "clarity-bot" / "SKILL.md"

# ── Output paths ──────────────────────────────────────────────────────────────
IMAGE_OUTPUT_PATH = Path("/tmp/clarity_infographic.png")
LOG_PATH          = BASE_DIR / "bot.log"
