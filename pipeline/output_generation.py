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

def _extract_tag(raw: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", raw, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


@dataclass
class OutputResult:
    model_label: str
    short_reply: str
    thread_tweets: list[str]
    infographic_prompt: str = ""
    image_path: Path | None = None
    image_generated: bool = False


def _parse_output(raw: str) -> tuple[str, list[str], str]:
    """
    Extracts (short_reply, thread_tweets, infographic_prompt) from XML-tagged LLM output.
    Falls back to full body as short_reply if tags are missing.
    """
    short_reply = _extract_tag(raw, "short_reply")
    thread_raw = _extract_tag(raw, "thread")
    infographic = _extract_tag(raw, "infographic_prompt")

    if not short_reply:
        log.warning("short_reply tag not found — delivering full body as short reply")
        short_reply = raw.strip()

    if not thread_raw:
        log.warning("thread tag not found — no tweets extracted")

    if not infographic:
        log.warning("infographic_prompt tag not found — prompt will be empty")

    tweets = [t.strip() for t in re.split(r"\n{2,}", thread_raw) if t.strip()] if thread_raw else []

    log.info(
        "Output parsed | short_reply_len=%d | tweets=%d | infographic_len=%d",
        len(short_reply), len(tweets), len(infographic),
    )

    if short_reply and len(short_reply) < 10:
        log.warning("Short reply suspiciously short (%d chars) | preview: %s", len(short_reply), raw[:300])

    return short_reply, tweets, infographic


def run(content: str, analysis: str) -> OutputResult:
    """
    Generates short reply + thread tweets + infographic prompt from approved analysis.

    Image generation is best-effort and never blocks text delivery.
    """
    log.info("Output generation start | content_len=%d | analysis_len=%d", len(content), len(analysis))

    with telemetry.timed(log, "Output generation LLM call"):
        model_label, raw_output = call_llm(
            system=system_prompt(),
            user=user_prompt(content, analysis),
            temperature=0.7,
            think=False,
        )

    short_reply, thread_tweets, infographic_prompt = _parse_output(raw_output)
    log.info(
        "Output generation LLM done | model=%s | short_reply_len=%d | tweets=%d",
        model_label, len(short_reply), len(thread_tweets),
    )

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
        short_reply=short_reply,
        thread_tweets=thread_tweets,
        infographic_prompt=infographic_prompt,
        image_path=image_path,
        image_generated=image_path is not None,
    )
