"""
brain/gbrain_cli.py
===================
Subprocess wrapper around the gbrain CLI.

Mirrors the llm/claude_cli.py pattern. Each function shells out to gbrain,
returns the trimmed stdout, and lets the caller (the chat agent loop)
decide what to do with it.

The gbrain binary is expected on PATH (linked via `bun link` after
`bun install` in the gbrain repo). Override with GBRAIN_CLI_PATH if needed.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

log = logging.getLogger(__name__)

_GBRAIN_PATH = shutil.which(os.getenv("GBRAIN_CLI_PATH", "gbrain")) or "gbrain"
_TIMEOUT = int(os.getenv("GBRAIN_CLI_TIMEOUT", "60"))
_MAX_OUTPUT_CHARS = 8_000


def _run(args: list[str], stdin: str | None = None) -> str:
    log.info("gbrain call | args=%s", " ".join(args))
    result = subprocess.run(
        [_GBRAIN_PATH, *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        input=stdin,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        log.error("gbrain failed | exit=%d | detail=%s", result.returncode, err[:300])
        raise RuntimeError(f"gbrain exited {result.returncode}: {err[:200]}")
    out = (result.stdout or "").strip()
    if len(out) > _MAX_OUTPUT_CHARS:
        out = out[:_MAX_OUTPUT_CHARS] + "\n…[truncated]"
    return out


def query(question: str, limit: int = 5) -> str:
    """Hybrid search (vector + keyword + RRF). Best for natural-language questions."""
    return _run(["query", question, "--limit", str(limit)])


def search(keyword: str, limit: int = 5) -> str:
    """Keyword-only search (tsvector). Best for exact terms / names."""
    return _run(["search", keyword, "--limit", str(limit)])


def get_page(slug: str) -> str:
    """Fetch a full brain page by slug (e.g. 'Projects/clarity-bot')."""
    return _run(["get", slug])


def list_recent(limit: int = 10) -> str:
    """List recently-updated pages."""
    return _run(["list", "-n", str(limit)])


def put(slug: str, body: str) -> str:
    """Write or update a page. Body is sent on stdin to avoid shell escaping."""
    return _run(["put", slug], stdin=body)


def embed(slug: str) -> str:
    """Generate/refresh embeddings for a single page so it's retrievable by hybrid search."""
    return _run(["embed", slug])


def save_page(slug: str, frontmatter: dict, body: str, *, do_embed: bool = True) -> str:
    """
    Higher-level helper: write a markdown page with YAML frontmatter, then embed it.

    Embedding failures are logged but don't propagate — the page is still on disk
    and will be picked up by the next gbrain sync/embed pass.
    """
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, str) and ("\n" in v or ":" in v):
            v = v.replace('"', '\\"')
            fm_lines.append(f'{k}: "{v}"')
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    document = "\n".join(fm_lines) + "\n\n" + body.strip() + "\n"

    put_result = put(slug, document)

    if do_embed:
        try:
            embed(slug)
        except Exception as exc:
            log.warning("embed failed for %s — page saved, retrieval may lag | %s", slug, exc)

    return put_result
