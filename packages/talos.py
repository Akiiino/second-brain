import argparse
import asyncio
import logging
from dataclasses import dataclass

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ContextTypes,
    ExtBot,
    TypeHandler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@dataclass
class WebhookUpdate:
    """Simple dataclass to wrap a custom update type"""

    payload: str
    user_id: int


class CustomContext(CallbackContext[ExtBot, dict, dict, dict]):
    """
    Custom CallbackContext class that makes `user_data` available
    for updates of type `WebhookUpdate`.
    """

    @classmethod
    def from_update(
        cls,
        update: object,
        application: "Application",
    ) -> "CustomContext":
        if isinstance(update, WebhookUpdate):
            return cls(application=application, user_id=update.user_id)
        return super().from_update(update, application)


async def start(update: Update, context: CustomContext) -> None:
    """Display a message with instructions on how to use this bot."""
    url = context.bot_data["url"]
    text = (
        f"Your Beeminder webhook URL: "
        f"<code>{url}/beeminder/{update.message.from_user.id}</code>.\n\n"
        f"To check if the bot is still running, call "
        f"<code>{url}/healthcheck</code>."
    )
    await update.message.reply_html(text=text)


async def webhook_update(
    update: WebhookUpdate, context: CustomContext
) -> None:
    """Handle custom updates."""
    title = update.payload["title"]
    limsum = update.payload["limsum"]
    text = f"The goal <b>{title}</b> is about to derail! {limsum}"
    await context.bot.send_message(
        chat_id=update.user_id, text=text, parse_mode=ParseMode.HTML
    )


async def main(
    url: str,
    port: int,
    token: str,
) -> None:
    """Set up PTB application and a web application for handling the
    incoming requests."""
    context_types = ContextTypes(context=CustomContext)

    application = (
        Application.builder()
        .token(token)
        .updater(None)
        .context_types(context_types)
        .build()
    )
    application.bot_data["url"] = url

    # register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        TypeHandler(type=WebhookUpdate, callback=webhook_update)
    )

    # Pass webhook settings to telegram
    await application.bot.set_webhook(
        url=f"{url}/telegram", allowed_updates=Update.ALL_TYPES
    )

    # Set up webserver
    async def telegram(request: Request) -> Response:
        """Handle incoming Telegram updates by putting them into
        the `update_queue`"""
        await application.update_queue.put(
            Update.de_json(data=await request.json(), bot=application.bot)
        )
        return Response()

    async def custom_updates(request: Request) -> PlainTextResponse:
        """
        Handle incoming webhook updates by also putting them into the
        `update_queue` if the required parameters were passed correctly.
        """
        payload = (await request.json())["goal"]
        user_id = request.path_params["user_id"]

        await application.update_queue.put(
            WebhookUpdate(payload=payload, user_id=user_id)
        )
        return PlainTextResponse(
            "Thank you for the submission! It's being forwarded."
        )

    async def health(_: Request) -> PlainTextResponse:
        """For the health endpoint, reply with a simple plain text message."""
        return PlainTextResponse(content="The bot is still running fine :)")

    starlette_app = Starlette(
        routes=[
            Route("/telegram", telegram, methods=["POST"]),
            Route("/healthcheck", health, methods=["GET"]),
            Route("/beeminder/{user_id:int}", custom_updates, methods=["POST"]),
        ]
    )
    webserver = uvicorn.Server(
        config=uvicorn.Config(
            app=starlette_app,
            port=port,
            use_colors=False,
            host="127.0.0.1",
        )
    )

    # Run application and webserver together
    async with application:
        await application.start()
        await webserver.serve()
        await application.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Talos",
        description="A multipurpose assistant Telegram bot",
    )

    parser.add_argument("-u", "--url", required=True)
    parser.add_argument("-p", "--port", type=int, required=True)
    parser.add_argument("-t", "--token", required=True)

    args = parser.parse_args()
    with open(args.token, "r") as token_file:
        token = token_file.read().strip()
    asyncio.run(main(args.url, args.port, token))
