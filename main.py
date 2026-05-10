import logging

from telegram.ext import CommandHandler, Filters, MessageHandler, Updater

import config
import telemetry
from bot import errors, handlers

log = logging.getLogger(__name__)


def main() -> None:
    telemetry.setup()
    log.info(
        "Mind Cache starting | model=%s | chat_id=%s",
        config.CLAUDE_CLI_MODEL,
        config.TELEGRAM_CHAT_ID,
    )

    from telegram.ext import PicklePersistence
    persistence = PicklePersistence(filename='bot_state.pickle')

    updater    = Updater(config.TELEGRAM_INPUT_TOKEN, use_context=True, persistence=persistence)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("go",      handlers.cmd_go))
    dispatcher.add_handler(CommandHandler("save",    handlers.cmd_save))
    dispatcher.add_handler(CommandHandler("clear",   handlers.cmd_clear))
    dispatcher.add_handler(CommandHandler("ask",     handlers.cmd_ask, pass_args=True))
    dispatcher.add_handler(CommandHandler("chat",    handlers.cmd_chat))
    dispatcher.add_handler(CommandHandler("endchat", handlers.cmd_endchat))
    dispatcher.add_handler(
        MessageHandler(Filters.text & ~Filters.command, handlers.handle_message)
    )
    dispatcher.add_error_handler(errors.handle)

    updater.start_polling(drop_pending_updates=True, timeout=10)
    log.info("Mind Cache running.")
    updater.idle()


if __name__ == "__main__":
    main()
