"""
pipeline/output_generation.py
==============================
Output generation stage: turns a completed analysis into Twitter posts + infographic.

The infographic prompt is ALWAYS returned as text, regardless of whether
image generation succeeds. Image generation is best-effort.
"""

class OutputParseError(ValueError):
    def __init__(self, missing_tags: list[str], raw_preview: str) -> None:
        self.missing_tags = missing_tags
        self.raw_preview = raw_preview
        super().__init__(f"LLM output missing required tags: {missing_tags} | preview: {raw_preview[:200]}")



import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import telemetry
from brain import gbrain_cli
from llm.router import call_llm
from prompts.output import system_prompt, user_prompt

log = logging.getLogger(__name__)


def _writeback_slug(content: str) -> str:
    """Stable slug from content hash, prefixed with the UTC date for chronological listing."""
    digest = hashlib.sha1(content.strip().encode("utf-8")).hexdigest()[:8]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"mindcache/analyses/{today}-{digest}"


def _writeback_body(
    content: str,
    analysis: str,
    short_reply: str,
    thread_tweets: list[str],
    infographic_prompt: str,
) -> str:
    thread_block = "\n\n".join(thread_tweets) if thread_tweets else "(none)"
    return (
        "## Original Post\n\n"
        f"{content.strip()}\n\n"
        "## Analysis\n\n"
        f"{analysis.strip()}\n\n"
        "## Short Reply\n\n"
        f"{short_reply.strip() or '(none)'}\n\n"
        "## Thread\n\n"
        f"{thread_block}\n\n"
        "## Infographic Prompt\n\n"
        f"{infographic_prompt.strip() or '(none)'}\n"
    )


def _persist_to_brain(
    content: str,
    analysis: str,
    short_reply: str,
    thread_tweets: list[str],
    infographic_prompt: str,
    model_label: str,
) -> None:
    """
    Best-effort write-back so future analyses retrieve this one as prior context.
    Never raises — the post has already been delivered to the user; this is a
    background indexing step.
    """
    try:
        slug = _writeback_slug(content)
        frontmatter = {
            "type": "mindcache-analysis",
            "model": model_label,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "content_preview": content.strip().replace("\n", " ")[:140],
        }
        body = _writeback_body(content, analysis, short_reply, thread_tweets, infographic_prompt)
        gbrain_cli.save_page(slug, frontmatter, body)
        log.info("Write-back ok | slug=%s", slug)
    except Exception as exc:
        log.warning("Write-back failed | %s", exc)

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
        raise OutputParseError(["short_reply"], raw[:200])


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

    # Image generation removed - use Hermes Agent for visual tasks
    image_path = None

    _persist_to_brain(
        content=content,
        analysis=analysis,
        short_reply=short_reply,
        thread_tweets=thread_tweets,
        infographic_prompt=infographic_prompt,
        model_label=model_label,
    )

    return OutputResult(
        model_label=model_label,
        short_reply=short_reply,
        thread_tweets=thread_tweets,
        infographic_prompt=infographic_prompt,
        image_path=image_path,
        image_generated=image_path is not None,
    )
