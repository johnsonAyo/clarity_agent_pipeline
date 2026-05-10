"""
pipeline/analysis.py
====================
Analysis stage: takes raw post content, runs the Clarity Agent analysis,
returns (model_label, analysis_text).
"""

from __future__ import annotations

import logging

import config
import telemetry
from llm.router import call_llm
from pipeline.retrieval import fetch_prior_context
from prompts.analysis import system_prompt, user_prompt

log = logging.getLogger(__name__)

# Load skill file once at import time — fail with warning, not crash
_skill_instructions: str = ""
if config.CLARITY_SKILL_PATH.exists():
    _skill_instructions = config.CLARITY_SKILL_PATH.read_text(encoding="utf-8")
    log.info("Clarity skill loaded | path=%s | len=%d", config.CLARITY_SKILL_PATH, len(_skill_instructions))
else:
    log.warning("Clarity skill file not found | path=%s | proceeding without it", config.CLARITY_SKILL_PATH)


def _build_system() -> str:
    parts = [_skill_instructions, system_prompt()]
    return "\n\n".join(p for p in parts if p).strip()


def run(content: str) -> tuple[str, str]:
    """
    Runs the full analysis pipeline on a post.

    Args:
        content: Raw text of the post to analyze.

    Returns:
        (model_label, analysis_text)

    Raises:
        RuntimeError if all LLM providers fail.
    """
    log.info("Analysis pipeline start | content_len=%d", len(content))

    with telemetry.timed(log, "Brain retrieval"):
        prior_context = fetch_prior_context(content)

    with telemetry.timed(log, "Analysis pipeline"):
        model_label, analysis = call_llm(
            system=_build_system(),
            user=user_prompt(content, prior_context=prior_context),
            temperature=0.1,  # Deep analytical dive
        )

    log.info("Analysis pipeline done | model=%s | analysis_len=%d", model_label, len(analysis))
    return model_label, analysis
