import os

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.telegram.handlers import (
    button_handler,
    start,
    text_handler,
)
from app.database import create_tables


load_dotenv()


def run_bot() -> None:
    # Создаёт только отсутствующие таблицы; данные в уже существующих не меняет.
    create_tables()

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN"
    )

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set"
        )

    application = (
        Application.builder()
        .token(token)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_handler,
        )
    )

    print(
        "Telegram bot started"
    )

    application.run_polling()


if __name__ == "__main__":
    run_bot()
