"""
bot/handlers.py
===============
All Telegram command and message handlers.

State machine per user session:
  STATE_COLLECTING        — accumulating post content chunks
  STATE_AWAITING_APPROVAL — analysis delivered, waiting to accept or reject the content

The handler layer is intentionally thin — it manages state and delegates all
heavy work to the pipeline layer. No LLM calls, no prompt building here.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import CallbackContext

import bot.messenger as messenger
from pipeline import analysis as analysis_pipeline
from pipeline import output_generation as output_pipeline

log = logging.getLogger(__name__)

_STATE_COLLECTING        = 0
_STATE_AWAITING_APPROVAL = 1
_MIN_CONTENT_LEN         = 20


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_go(update: Update, context: CallbackContext) -> None:
    """
    /go — Trigger analysis on all accumulated content chunks.
    Blocked if a previous analysis is still pending approval.
    """
    if context.user_data.get("state") == _STATE_AWAITING_APPROVAL:
        update.message.reply_text(
            "Still waiting on your ✅ or ❌ for the previous analysis. "
            "Send /clear if you want to start over."
        )
        return

    chunks  = context.user_data.get("chunks", [])
    content = "\n\n".join(chunks).strip()

    if len(content) < _MIN_CONTENT_LEN:
        update.message.reply_text(
            "Nothing to analyze yet. Paste the post content first, then send /go."
        )
        return

    update.message.reply_text(
        f"Got it — {len(content):,} chars across {len(chunks)} message(s).\n"
        "Running analysis… this takes 60–90 seconds."
    )

    log.info("Analysis requested | user=%s | content_len=%d", update.effective_user.id, len(content))

    try:
        model_label, analysis = analysis_pipeline.run(content)
    except Exception as exc:
        log.error("Analysis pipeline failed | error=%s", exc, exc_info=True)
        update.message.reply_text(f"⚠️ Analysis failed: {exc}\nSend /clear to reset.")
        return

    context.user_data.update(
        content=content,
        analysis=analysis,
        model=model_label,
        state=_STATE_AWAITING_APPROVAL,
        chunks=[],
    )

    messenger.send_to_output(f"<b>Analysis — {model_label}</b>\n\n{analysis}")
    messenger.send_divider(
        "─────\n"
        "Analysis above. Reply:\n"
        "✅  → Generate short reply + long thread + infographic\n"
        "❌  → Discard"
    )


def cmd_clear(update: Update, context: CallbackContext) -> None:
    """
    /clear — Wipe all accumulated content and reset to collecting state.
    """
    context.user_data.clear()
    update.message.reply_text("Cleared. Ready for the next post.")
    log.info("Session cleared | user=%s", update.effective_user.id)


# ── Message routing ───────────────────────────────────────────────────────────

def handle_message(update: Update, context: CallbackContext) -> None:
    text  = (update.message.text or "").strip()
    state = context.user_data.get("state", _STATE_COLLECTING)

    if state == _STATE_AWAITING_APPROVAL:
        _handle_approval(update, context, text)
    else:
        _handle_collecting(update, context, text)


def _handle_collecting(update: Update, context: CallbackContext, text: str) -> None:
    chunks = context.user_data.setdefault("chunks", [])
    chunks.append(text)
    total = sum(len(c) for c in chunks)
    update.message.reply_text(
        f"Chunk {len(chunks)} saved ({len(text):,} chars · {total:,} total).\n"
        "Keep pasting or send /go to analyze."
    )
    log.debug("Chunk saved | chunk=%d | len=%d | total=%d", len(chunks), len(text), total)


def _handle_approval(update: Update, context: CallbackContext, text: str) -> None:
    if text == "✅":
        _generate_and_deliver(update, context)
    elif text == "❌":
        context.user_data.clear()
        update.message.reply_text("❌ Discarded. Ready for the next post.")
        log.info("Analysis discarded | user=%s", update.effective_user.id)
    else:
        update.message.reply_text("Reply ✅ to approve or ❌ to discard.")


def _generate_and_deliver(update: Update, context: CallbackContext) -> None:
    content  = context.user_data.get("content", "")
    analysis = context.user_data.get("analysis", "")

    if not content or not analysis:
        update.message.reply_text("⚠️ Session context is missing. Send /clear and start over.")
        context.user_data.clear()
        return

    update.message.reply_text("✅ Approved. Drafting posts…")
    log.info("Output generation requested | user=%s", update.effective_user.id)

    try:
        result = output_pipeline.run(content, analysis)
    except Exception as exc:
        log.error("Output pipeline failed | error=%s", exc, exc_info=True)
        update.message.reply_text(f"⚠️ Output generation failed: {exc}")
        return

    log.info(
        "Output generation complete | model=%s | image=%s | tweets=%d | infographic_prompt_len=%d",
        result.model_label,
        result.image_generated,
        len(result.thread_tweets),
        len(result.infographic_prompt),
    )

    # 1. Short reply
    if result.short_reply:
        messenger.send_to_output(f"<b>Short reply — {result.model_label}</b>\n\n{result.short_reply}")
    else:
        log.warning("No short reply extracted from LLM output")

    # 2. Thread — each tweet as its own message
    if result.thread_tweets:
        messenger.send_to_output("<b>Thread</b>")
        for tweet in result.thread_tweets:
            messenger.send_to_output(tweet)
    else:
        log.warning("No thread tweets extracted from LLM output")

    # 3. Infographic prompt — always sent as text, regardless of image gen outcome
    if result.infographic_prompt:
        messenger.send_to_output(
            "<b>Infographic Prompt:</b>\n\n"
            f"<code>{result.infographic_prompt}</code>"
        )
    else:
        log.warning("No infographic prompt extracted from LLM output")

    # 4. Image — delivered if generated; prompt text above already covers the no-image case
    if result.image_path:
        sent = messenger.send_photo_to_output(result.image_path)
        if not sent:
            log.warning("Image file exists but Telegram photo send failed | path=%s", result.image_path)

    update.message.reply_text("🚀 Outputs delivered to Clarity Output bot.")
    context.user_data.clear()
