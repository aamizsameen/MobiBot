"""
MobiBot — Command your AI prompts from WhatsApp & Telegram.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from config import Config
from bot_telegram import setup_telegram, process_telegram_update
from bot_whatsapp import setup_whatsapp, shutdown_whatsapp
from scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting MobiBot...")
    await setup_whatsapp()   # neonize: QR code auth, runs as background task
    await setup_telegram()   # webhook-based
    await start_scheduler()  # background task scheduler
    logger.info("MobiBot is ready!")
    yield
    logger.info("Shutting down MobiBot...")
    await stop_scheduler()
    await shutdown_whatsapp()


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=Config.HOST, port=Config.PORT, reload=False)
