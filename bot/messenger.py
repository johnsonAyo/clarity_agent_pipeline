"""
bot/messenger.py
================
Telegram delivery layer — isolated from all business logic.

Two bots:
  Input bot  — used by handlers to reply directly to the user's commands.
  Output bot — passive sender, delivers analysis results and generated posts.

All sends are HTML-mode with a plaintext fallback. Long messages are chunked
safely without breaking mid-tag.
"""

from __future__ import annotations

import html
import logging
import re
from pathlib import Path

from telegram import Bot

import config

log = logging.getLogger(__name__)

_TELEGRAM_CHAR_LIMIT = 4_000  # conservative under the 4096 hard limit

# Instantiated once at module load — the token is validated on first API call
_output_bot = Bot(token=config.TELEGRAM_OUTPUT_TOKEN)

# Escaped HTML tags to restore after html.escape()
_RESTORE_TAGS = {
    "&lt;b&gt;":    "<b>",     "&lt;/b&gt;":    "</b>",
    "&lt;i&gt;":    "<i>",     "&lt;/i&gt;":    "</i>",
    "&lt;code&gt;": "<code>",  "&lt;/code&gt;": "</code>",
    "&lt;pre&gt;":  "<pre>",   "&lt;/pre&gt;":  "</pre>",
}


def _to_html(text: str) -> str:
    """Converts raw LLM output to Telegram-safe HTML."""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = html.escape(text)
    for escaped, tag in _RESTORE_TAGS.items():
        text = text.replace(escaped, tag)
    # Markdown → HTML (only non-overlapping patterns)
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)_(.*?)_(?!\w)", r"<i>\1</i>", text)
    return text


def _chunk(text: str) -> list[str]:
    """Splits text into chunks that fit within Telegram's character limit."""
    if len(text) <= _TELEGRAM_CHAR_LIMIT:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        segment = line + "\n"
        if len(current) + len(segment) > _TELEGRAM_CHAR_LIMIT:
            if current:
                chunks.append(current)
            current = segment
        else:
            current += segment
    if current:
        chunks.append(current)
    return chunks


def _send_text(bot: Bot | None, chat_id: str | None, text: str, reply_fn=None) -> None:
    html_text = _to_html(text)
    for chunk in _chunk(html_text):
        try:
            if reply_fn:
                reply_fn(chunk, parse_mode="HTML")
            else:
                bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")
        except Exception as exc:
            log.error("HTML send failed | len=%d | error=%s | retrying plaintext", len(chunk), exc)
            raw_chunk = chunk  # already chunked; just drop formatting
            try:
                if reply_fn:
                    reply_fn(raw_chunk)
                else:
                    bot.send_message(chat_id=chat_id, text=raw_chunk)
            except Exception as exc2:
                log.critical("Plaintext send also failed | error=%s", exc2)


# Public API

def reply(message, text: str) -> None:
    """Reply to a user message via the input bot."""
    _send_text(None, None, text, reply_fn=message.reply_text)


def send_to_output(text: str) -> None:
    """Deliver a text message to the output bot channel."""
    log.info("Output bot send | len=%d", len(text))
    _send_text(_output_bot, config.TELEGRAM_CHAT_ID, text)


def send_photo_to_output(image_path: Path, caption: str = "Mind Cache Infographic") -> bool:
    """
    Delivers an image to the output bot channel.
    Returns True on success, False on failure (caller should log accordingly).
    """
    try:
        with open(image_path, "rb") as photo:
            _output_bot.send_photo(
                chat_id=config.TELEGRAM_CHAT_ID,
                photo=photo,
                caption=caption,
            )
        log.info("Photo sent | path=%s", image_path)
        return True
    except Exception as exc:
        log.error("Photo send failed | path=%s | error=%s", image_path, exc)
        return False


def send_divider(text: str) -> None:
    """Sends a plain-text status/divider message to the output bot."""
    try:
        _output_bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
    except Exception as exc:
        log.error("Divider message send failed | error=%s", exc)
