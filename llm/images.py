"""
llm/images.py
=============
Infographic image generation — two-tier pipeline:

  1. Ollama cloud image model (primary, requires a diffusion model)
  2. Claude CLI → SVG → PNG via cairosvg (fallback, always available if CLI is present)

Always best-effort. Returns (path, reason) so callers can log the exact outcome.
"""

from __future__ import annotations

import base64
import logging
import re
import subprocess
from pathlib import Path

import ollama as ollama_sdk

import config

from prompts import svg as svg_prompts

log = logging.getLogger(__name__)

SVG_OUTPUT_PATH = config.IMAGE_OUTPUT_PATH.with_suffix(".svg")


# ── Public interface ──────────────────────────────────────────────────────────

def generate_image(prompt: str) -> tuple[Path | None, str]:
    """
    Tries Ollama image model first, then falls back to Claude CLI → SVG → PNG.

    Returns:
        (Path, "ok")       — image saved successfully
        (None, "<reason>") — both providers failed; reason explains why
    """
    # ── Tier 1: Ollama ────────────────────────────────────────────────────────
    if config.OLLAMA_API_KEY and config.OLLAMA_IMAGE_MODEL:
        log.info("Image gen tier 1 | provider=Ollama | model=%s", config.OLLAMA_IMAGE_MODEL)
        path, reason = _generate_via_ollama(prompt)
        if path:
            return path, reason
        log.warning("Ollama image failed | reason=%s | trying Claude SVG fallback", reason)
    else:
        log.info("Ollama image skipped | OLLAMA_IMAGE_MODEL not configured | trying Claude SVG fallback")

    # ── Tier 2: Claude CLI → SVG → PNG ────────────────────────────────────────
    log.info("Image gen tier 2 | provider=Claude CLI SVG")
    return _generate_via_claude_svg(prompt)


# ── Tier 1: Ollama ────────────────────────────────────────────────────────────

def _generate_via_ollama(prompt: str) -> tuple[Path | None, str]:
    client = ollama_sdk.Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"},
    )
    try:
        response = client.generate(model=config.OLLAMA_IMAGE_MODEL, prompt=prompt)
    except Exception as exc:
        return None, f"Ollama API call failed: {exc}"

    image_bytes, reason = _extract_image_bytes(response)
    if not image_bytes:
        return None, reason

    try:
        config.IMAGE_OUTPUT_PATH.write_bytes(image_bytes)
        log.info("Ollama image saved | path=%s | bytes=%d", config.IMAGE_OUTPUT_PATH, len(image_bytes))
        return config.IMAGE_OUTPUT_PATH, "ok"
    except OSError as exc:
        return None, f"file write failed: {exc}"


def _extract_image_bytes(response: object) -> tuple[bytes | None, str]:
    images = getattr(response, "images", None)
    if images:
        raw = images[0]
        if isinstance(raw, bytes):
            return raw, "ok"
        if isinstance(raw, str):
            try:
                return base64.b64decode(raw), "ok"
            except Exception as exc:
                return None, f"base64 decode of response.images[0] failed: {exc}"

    resp_field = getattr(response, "response", None)

    if isinstance(resp_field, bytes) and resp_field:
        return resp_field, "ok"

    if isinstance(resp_field, str) and resp_field:
        try:
            return base64.b64decode(resp_field), "ok"
        except Exception:
            preview = resp_field[:200].replace("\n", " ")
            return None, (
                f"model returned text instead of image bytes — "
                f"'{config.OLLAMA_IMAGE_MODEL}' is likely a VL model, not a diffusion model. "
                f"Preview: {preview}"
            )

    return None, "response contained no image data (empty)"


# ── Tier 2: Claude CLI → SVG → PNG ───────────────────────────────────────────

def _generate_via_claude_svg(prompt: str) -> tuple[Path | None, str]:
    import shutil
    if not shutil.which(config.CLAUDE_CLI_PATH) and not Path(config.CLAUDE_CLI_PATH).is_file():
        return None, "Claude CLI not found — cannot generate SVG fallback"

    log.info("Requesting SVG from Claude CLI | prompt_len=%d", len(prompt))

    try:
        result = subprocess.run(
            [
                config.CLAUDE_CLI_PATH,
                "-p", f"Generate an SVG infographic for this brief:\n\n{prompt}",
                "--model",               config.CLAUDE_CLI_MODEL,
                "--append-system-prompt", svg_prompts.SYSTEM_PROMPT,
                "--output-format",       "text",
                "--no-session-persistence",
                "--permission-mode",     "bypassPermissions",
            ],
            capture_output=True,
            text=True,
            timeout=config.CLAUDE_CLI_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None, "Claude CLI timed out during SVG generation"
    except Exception as exc:
        return None, f"Claude CLI subprocess error: {exc}"

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()[:200]
        return None, f"Claude CLI exited {result.returncode}: {err}"

    svg_content = _extract_svg(result.stdout)
    if not svg_content:
        log.warning("Claude SVG response did not contain valid SVG | preview=%s", result.stdout[:200])
        return None, "Claude did not return valid SVG markup"

    log.info("SVG extracted | len=%d", len(svg_content))
    return _svg_to_png(svg_content)


def _extract_svg(text: str) -> str | None:
    match = re.search(r"<svg[\s\S]*?</svg>", text, re.IGNORECASE)
    if match:
        return match.group(0)
    if text.strip().lower().startswith("<svg"):
        return text.strip()
    return None


def _svg_to_png(svg_content: str) -> tuple[Path | None, str]:
    try:
        # On macOS arm64, Homebrew installs cairo to /opt/homebrew/lib.
        # cairocffi only searches /usr/local/lib by default, so we add the arm64 path
        # before importing. No-op on Linux or if already set.
        import os
        if "DYLD_LIBRARY_PATH" not in os.environ:
            os.environ["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"
        import cairosvg
    except ImportError:
        return None, "cairosvg not installed — run: pip install cairosvg"
    except OSError as exc:
        return None, f"cairo native library not found: {exc}"

    try:
        cairosvg.svg2png(
            bytestring=svg_content.encode("utf-8"),
            write_to=str(config.IMAGE_OUTPUT_PATH),
            output_width=1080,
            output_height=1350,
        )
        log.info("SVG → PNG conversion complete | path=%s", config.IMAGE_OUTPUT_PATH)
        return config.IMAGE_OUTPUT_PATH, "ok"
    except Exception as exc:
        return None, f"SVG → PNG conversion failed: {exc}"
