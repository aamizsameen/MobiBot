"""
Telegram bot integration using python-telegram-bot with webhook mode.
"""
from __future__ import annotations
import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import Config
from commands import handle_command

logger = logging.getLogger(__name__)

telegram_app: Application | None = None


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming Telegram messages."""
    if not update.message or not update.message.text:
        return
    user_id = f"tg:{update.message.from_user.id}"
    text = update.message.text
    response = await handle_command(user_id, text)

    # If response is an image, send as photo
    if response.startswith("IMAGE:"):
        image_path = response[6:]
        try:
            with open(image_path, "rb") as photo:
                await update.message.reply_photo(photo=photo)
            os.unlink(image_path)  # cleanup temp file
        except Exception as e:
            await update.message.reply_text(f"Failed to send image: {e}")
        return

    # Telegram has a 4096 char limit per message
    for i in range(0, len(response), 4000):
        await update.message.reply_text(response[i:i+4000], parse_mode="Markdown")


async def setup_telegram() -> Application | None:
    """Initialize the Telegram bot application."""
    global telegram_app
    token = Config.TELEGRAM_BOT_TOKEN
    if not token or token == "your-telegram-bot-token":
        logger.warning("TELEGRAM_BOT_TOKEN not configured, skipping Telegram bot setup")
        return None

    telegram_app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # All messages go through the same handler
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    telegram_app.add_handler(MessageHandler(filters.COMMAND, _handle_message))

    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(f"{Config.BASE_URL}/webhook/telegram")
    logger.info("Telegram bot webhook set")
    return telegram_app


async def process_telegram_update(payload: dict):
    """Process an incoming Telegram webhook update."""
    if telegram_app:
        update = Update.de_json(payload, telegram_app.bot)
        await telegram_app.process_update(update)
