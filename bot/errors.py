"""
bot/errors.py
=============
Global Telegram error handler.
Registered with dispatcher.add_error_handler() — catches all unhandled
exceptions from handlers and network errors, logs them, and notifies the user
where possible without crashing the bot.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.error import Conflict, NetworkError, TimedOut
from telegram.ext import CallbackContext

log = logging.getLogger(__name__)


def handle(update: object, context: CallbackContext) -> None:
    error = context.error

    # Network-level errors — expected intermittently, not actionable
    if isinstance(error, (TimedOut, NetworkError)):
        log.warning("Telegram network error (transient) | error=%s", error)
        return

    # Conflict = two bot instances polling simultaneously
    if isinstance(error, Conflict):
        log.error(
            "Conflict: duplicate bot instance detected. "
            "Kill all other processes running telegram_bot.py or main.py before restarting."
        )
        return

    # All other errors — log with full traceback for diagnostics
    log.error("Unhandled handler error | error=%s", error, exc_info=error)

    # Notify the user if there's a message context to reply to
    if isinstance(update, Update) and update.effective_message:
        try:
            update.effective_message.reply_text(
                " Something went wrong. The error has been logged.\n"
                "Send /clear to reset and try again."
            )
        except Exception as notify_exc:
            log.error("Could not deliver error notification to user | error=%s", notify_exc)
