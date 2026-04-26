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
from dataclasses import dataclass, field
from pathlib import Path

import telemetry
from llm.images import generate_image
from llm.router import call_llm
from prompts.output import system_prompt, user_prompt

log = logging.getLogger(__name__)

_INFOGRAPHIC_HEADER = "Deliverable 3 — Infographic Prompt"

_D1_RE = re.compile(r"Deliverable\s+1\s*[—–-][^\n]*\n?", re.IGNORECASE)
_D2_RE = re.compile(r"Deliverable\s+2\s*[—–-][^\n]*\n?", re.IGNORECASE)
_D3_RE = re.compile(re.escape(_INFOGRAPHIC_HEADER), re.IGNORECASE)


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
    Splits raw LLM output into (short_reply, thread_tweets, infographic_prompt).

    Uses the Deliverable headers as anchors. Falls back gracefully if the model
    omits headers — content is still delivered, just unsplit.
    """
    # Strip infographic section first
    d3 = _D3_RE.search(raw)
    infographic = raw[d3.end():].strip() if d3 else ""
    body = raw[:d3.start()].strip() if d3 else raw.strip()

    if not infographic:
        log.warning("Infographic header not found — prompt will be empty")

    # Find Deliverable 1 and 2 markers within body
    d1 = _D1_RE.search(body)
    d2 = _D2_RE.search(body)

    if d1 and d2 and d1.start() < d2.start():
        short_reply = body[d1.end():d2.start()].strip()
        thread_raw = body[d2.end():].strip()
    elif d2:
        short_reply = body[:d2.start()].strip()
        thread_raw = body[d2.end():].strip()
    else:
        log.warning("Post structure headers not found — delivering full body as short reply")
        return body, [], infographic

    tweets = [t.strip() for t in re.split(r"\n{2,}", thread_raw) if t.strip()]

    log.info(
        "Output parsed | short_reply_len=%d | tweets=%d | infographic_len=%d",
        len(short_reply), len(tweets), len(infographic),
    )

    if len(short_reply) < 10:
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
