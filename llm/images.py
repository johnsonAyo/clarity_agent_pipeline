"""
llm/images.py
=============
Image generation via Ollama cloud.
Always best-effort — callers must handle None path gracefully.

Returns (path, reason) so callers can log the exact failure cause rather
than a generic "failed or skipped" message.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import ollama as ollama_sdk

import config

log = logging.getLogger(__name__)


def generate_image(prompt: str) -> tuple[Path | None, str]:
    """
    Attempts to generate an infographic image.

    Returns:
        (Path, "ok")                  — on success
        (None, "<reason>")            — on any failure
    """
    if not config.OLLAMA_API_KEY:
        return None, "OLLAMA_API_KEY not configured"

    if not config.OLLAMA_IMAGE_MODEL:
        return None, "OLLAMA_IMAGE_MODEL not set in .env"

    client = ollama_sdk.Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"},
    )

    log.info("Image generation start | model=%s | prompt_len=%d", config.OLLAMA_IMAGE_MODEL, len(prompt))

    try:
        response = client.generate(model=config.OLLAMA_IMAGE_MODEL, prompt=prompt)
    except Exception as exc:
        return None, f"API call failed: {exc}"

    image_bytes, extract_reason = _extract_image_bytes(response)

    if not image_bytes:
        return None, extract_reason

    try:
        config.IMAGE_OUTPUT_PATH.write_bytes(image_bytes)
        log.info("Image saved | path=%s | size_bytes=%d", config.IMAGE_OUTPUT_PATH, len(image_bytes))
        return config.IMAGE_OUTPUT_PATH, "ok"
    except OSError as exc:
        return None, f"file write failed: {exc}"


def _extract_image_bytes(response: object) -> tuple[bytes | None, str]:
    """
    Returns (bytes, reason). reason is "ok" on success, a specific explanation on failure.
    """
    # Format 1: response.images list (newer SDK)
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

    # Format 2: raw bytes in response.response (older SDK)
    if isinstance(resp_field, bytes) and resp_field:
        return resp_field, "ok"

    # Format 3: base64 string in response.response
    if isinstance(resp_field, str) and resp_field:
        try:
            return base64.b64decode(resp_field), "ok"
        except Exception:
            # Not base64 — the model returned plain text (VL model behaviour)
            preview = resp_field[:300].replace("\n", " ")
            return None, (
                f"model returned text instead of image bytes — "
                f"'{config.OLLAMA_IMAGE_MODEL}' is likely a vision-language model, "
                f"not a diffusion model. Model response preview: {preview}"
            )

    return None, "response contained no image data and no text (empty response)"
