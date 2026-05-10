"""
llm/images.py
=============
Infographic image generation - two-tier pipeline:

  1. Hugging Face - FLUX.1-schnell via InferenceClient (free tier, excellent quality)
  2. OpenAI - gpt-image-1 or dall-e-3 (paid fallback)

Always best-effort. Returns (path, reason) so callers can log the exact outcome.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import config

log = logging.getLogger(__name__)


# Public interface

def generate_image(prompt: str) -> tuple[Path | None, str]:
    # Tier 1: Hugging Face (free)
    if config.HF_API_TOKEN:
        log.info("Image gen tier 1 | provider=HuggingFace | model=%s", config.HF_IMAGE_MODEL)
        path, reason = _generate_via_huggingface(prompt)
        if path:
            return path, reason
        log.warning("HuggingFace image failed | reason=%s | trying OpenAI", reason)
    else:
        log.info("HuggingFace skipped | HF_API_TOKEN not set | trying OpenAI")

    # Tier 2: OpenAI (paid)
    if config.OPENAI_API_KEY:
        log.info("Image gen tier 2 | provider=OpenAI | model=%s", config.OPENAI_IMAGE_MODEL)
        path, reason = _generate_via_openai(prompt)
        if path:
            return path, reason
        log.warning("OpenAI image failed | reason=%s", reason)
    else:
        log.info("OpenAI skipped | OPENAI_API_KEY not set")

    return None, "All image providers failed"


# Tier 1: Hugging Face

def _generate_via_huggingface(prompt: str) -> tuple[Path | None, str]:
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        return None, "huggingface_hub not installed - run: pip install huggingface_hub"

    client = InferenceClient(token=config.HF_API_TOKEN)

    try:
        image = client.text_to_image(prompt, model=config.HF_IMAGE_MODEL)
    except Exception as exc:
        return None, f"HuggingFace inference failed: {exc}"

    try:
        image.save(str(config.IMAGE_OUTPUT_PATH))
        log.info("HuggingFace image saved | path=%s", config.IMAGE_OUTPUT_PATH)
        return config.IMAGE_OUTPUT_PATH, "ok"
    except Exception as exc:
        return None, f"File write failed: {exc}"


# Tier 2: OpenAI

def _generate_via_openai(prompt: str) -> tuple[Path | None, str]:
    try:
        from openai import OpenAI
    except ImportError:
        return None, "openai package not installed - run: pip install openai"

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    is_dalle = "dall-e" in config.OPENAI_IMAGE_MODEL
    size = "1024x1792" if is_dalle else "1024x1536"
    quality = "standard" if is_dalle else "medium"

    try:
        response = client.images.generate(
            model=config.OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
    except Exception as exc:
        return None, f"OpenAI API call failed: {exc}"

    try:
        image_b64 = response.data[0].b64_json
        if not image_b64:
            return None, "OpenAI returned no image data"
        image_bytes = base64.b64decode(image_b64)
    except Exception as exc:
        return None, f"OpenAI response decode failed: {exc}"

    try:
        config.IMAGE_OUTPUT_PATH.write_bytes(image_bytes)
        log.info("OpenAI image saved | path=%s | bytes=%d", config.IMAGE_OUTPUT_PATH, len(image_bytes))
        return config.IMAGE_OUTPUT_PATH, "ok"
    except OSError as exc:
        return None, f"File write failed: {exc}"
