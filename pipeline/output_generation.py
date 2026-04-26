"""
pipeline/output_generation.py
==============================
Output generation stage: turns a completed analysis into Twitter posts + infographic.

The infographic prompt is ALWAYS returned as text, regardless of whether
image generation succeeds. Image generation is best-effort.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import telemetry
from llm.images import generate_image
from llm.router import call_llm
from prompts.output import system_prompt, user_prompt

log = logging.getLogger(__name__)

# Headers the LLM may use to delineate the infographic prompt section
_INFOGRAPHIC_HEADERS = [
    "**Infographic Prompt**",
    "**infographic prompt**",
    "## 3. Infographic Prompt",
    "3. Infographic Prompt:",
    "Infographic Prompt:",
    "Deliverable 3 — Infographic Prompt",
    "INFOGRAPHIC PROMPT",
]


@dataclass
class OutputResult:
    model_label: str
    posts_text: str
    infographic_prompt: str = ""
    image_path: Path | None = None
    image_generated: bool = False


def _split_posts_and_infographic(raw: str) -> tuple[str, str]:
    """
    Splits the LLM output into (posts_text, infographic_prompt).
    infographic_prompt is empty string if the header is not found.
    """
    for header in _INFOGRAPHIC_HEADERS:
        pattern = re.compile(re.escape(header), re.IGNORECASE)
        if pattern.search(raw):
            parts = pattern.split(raw, maxsplit=1)
            posts = parts[0].strip()
            # Take everything up to the first double blank line as the prompt
            infographic = parts[1].strip()
            log.info("Infographic prompt extracted | header='%s' | prompt_len=%d", header, len(infographic))
            return posts, infographic

    log.warning("No infographic prompt header found in LLM output — prompt will be empty")
    return raw.strip(), ""


def run(content: str, analysis: str) -> OutputResult:
    """
    Generates short reply + long thread + infographic prompt from approved analysis.

    Image generation is attempted and never blocks delivery of text outputs.
    The infographic_prompt field is always populated (if the LLM produced one),
    regardless of whether the image was successfully generated.

    Args:
        content:  Original post text.
        analysis: Completed analysis from the analysis pipeline.

    Returns:
        OutputResult with all generated content.
    """
    log.info("Output generation start | content_len=%d | analysis_len=%d", len(content), len(analysis))

    with telemetry.timed(log, "Output generation LLM call"):
        model_label, raw_output = call_llm(
            system=system_prompt(),
            user=user_prompt(content, analysis),
            temperature=0.7,
        )

    posts_text, infographic_prompt = _split_posts_and_infographic(raw_output)
    log.info("Output generation LLM done | model=%s | posts_len=%d", model_label, len(posts_text))

    # Image generation — best-effort, never raises
    image_path: Path | None = None
    if infographic_prompt:
        with telemetry.timed(log, "Image generation"):
            image_path, image_reason = generate_image(infographic_prompt)
        if image_path:
            log.info("Image generation succeeded | path=%s", image_path)
        else:
            log.warning("Image generation failed | reason=%s", image_reason)

    return OutputResult(
        model_label=model_label,
        posts_text=posts_text,
        infographic_prompt=infographic_prompt,
        image_path=image_path,
        image_generated=image_path is not None,
    )
