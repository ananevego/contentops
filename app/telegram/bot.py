import os

from dotenv import load_dotenv
from telegram.request import HTTPXRequest
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

    relay_url = os.getenv(
        "TELEGRAM_RELAY_URL"
    )
    relay_secret = os.getenv(
        "RELAY_SECRET"
    )

    builder = (
        Application.builder()
        .token(token)
    )

    if relay_url and relay_secret:
        relay_headers = {
            "X-Relay-Secret": relay_secret,
        }

        request = HTTPXRequest(
            httpx_kwargs={
                "headers": relay_headers,
            }
        )

        get_updates_request = HTTPXRequest(
            httpx_kwargs={
                "headers": relay_headers,
            }
        )

        builder = (
            builder
            .base_url(
                f"{relay_url}/bot"
            )
            .base_file_url(
                f"{relay_url}/file/bot"
            )
            .request(request)
            .get_updates_request(
                get_updates_request
            )
        )

        print(
            "Telegram relay enabled"
        )
    else:
        print(
            "Telegram relay disabled"
        )

    application = builder.build()

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
