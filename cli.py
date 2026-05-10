#!/usr/bin/env python3
"""
cli.py — headless entrypoint for Hermes skill invocation.

Usage:
    python cli.py --text "<post content>"
    python cli.py --text "<post content>" --full   # also generate thread + infographic

Returns JSON to stdout so Hermes can parse and relay it to the user.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import telemetry

telemetry.setup()
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clarity pipeline — headless mode")
    parser.add_argument("--text", required=True, help="Post content to analyse")
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Also generate tweet thread + infographic prompt after analysis",
    )
    args = parser.parse_args()

    content = args.text.strip()
    if len(content) < 20:
        print(json.dumps({"error": "Content too short (min 20 chars)"}))
        sys.exit(1)

    from pipeline import analysis as analysis_pipeline

    try:
        model_label, analysis = analysis_pipeline.run(content)
    except Exception as exc:
        log.error("Analysis failed: %s", exc, exc_info=True)
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)

    result: dict = {"model": model_label, "analysis": analysis}

    if args.full:
        from pipeline import output_generation as output_pipeline
        try:
            out = output_pipeline.run(content, analysis)
            result["short_reply"] = out.short_reply or ""
            result["thread"] = out.thread_tweets or []
            result["infographic_prompt"] = out.infographic_prompt or ""
        except Exception as exc:
            log.error("Output generation failed: %s", exc, exc_info=True)
            result["output_error"] = str(exc)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
