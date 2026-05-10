"""
pipeline/retrieval.py
=====================
Pulls prior brain context for a post about to be analyzed.

Cheap and best-effort: a single gbrain hybrid query, formatted into a
prior_context block. If the brain has nothing relevant (cold start, off-topic),
returns an empty string and analysis runs as before.
"""

from __future__ import annotations

import logging

from brain import gbrain_cli

log = logging.getLogger(__name__)

_QUERY_CHAR_BUDGET = 500
_DEFAULT_LIMIT = 3


def fetch_prior_context(content: str, limit: int = _DEFAULT_LIMIT) -> str:
    """
    Returns a string ready to drop into a prompt, or "" if nothing useful surfaced.

    Strategy: send the first ~500 chars of the post to gbrain query. The hybrid
    search handles intent classification and ranking; we don't second-guess it.
    """
    if not content.strip():
        return ""

    snippet = content.strip()[:_QUERY_CHAR_BUDGET]

    try:
        raw = gbrain_cli.query(snippet, limit=limit)
    except Exception as exc:
        log.warning("retrieval failed — analysis will run without prior context | %s", exc)
        return ""

    if not raw or _looks_empty(raw):
        log.info("retrieval | no prior context")
        return ""

    log.info("retrieval | prior_context_len=%d", len(raw))
    return raw


def _looks_empty(raw: str) -> bool:
    """gbrain returns short status strings when nothing matches; filter those out."""
    lowered = raw.lower().strip()
    if len(lowered) < 40:
        return True
    return any(
        marker in lowered
        for marker in ("no results", "no matches", "nothing found", "0 results")
    )
