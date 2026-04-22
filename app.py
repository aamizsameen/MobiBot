"""
MobiBot — Command your AI prompts from WhatsApp & Telegram.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from config import Config
from bot_telegram import setup_telegram, process_telegram_update
from bot_whatsapp import setup_whatsapp, process_whatsapp_message, validate_twilio_request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting MobiBot...")
    setup_whatsapp()
    await setup_telegram()
    logger.info("MobiBot is ready!")
    yield
    logger.info("Shutting down MobiBot...")


app = FastAPI(title="MobiBot", version="1.0.0", lifespan=lifespan)


@app.get("/")
async def root():
    return {"app": "MobiBot", "status": "running", "version": "1.0.0"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Receive Telegram bot updates."""
    payload = await request.json()
    await process_telegram_update(payload)
    return Response(status_code=200)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receive WhatsApp messages via Twilio webhook."""
    form_data = dict(await request.form())

    # Validate Twilio signature (optional but recommended)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if signature and not validate_twilio_request(url, form_data, signature):
        return Response(status_code=403, content="Invalid signature")

    await process_whatsapp_message(form_data)

    # Return empty TwiML response
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=Config.HOST, port=Config.PORT, reload=True)
