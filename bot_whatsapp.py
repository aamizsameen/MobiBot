"""
WhatsApp bot integration via Twilio API.
"""
from __future__ import annotations
import logging
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from config import Config
from commands import handle_command

logger = logging.getLogger(__name__)

twilio_client: Client | None = None
validator: RequestValidator | None = None


def setup_whatsapp():
    """Initialize Twilio client for WhatsApp."""
    global twilio_client, validator
    placeholders = {"your-twilio-sid", "your-twilio-auth-token"}
    sid = Config.TWILIO_ACCOUNT_SID
    token = Config.TWILIO_AUTH_TOKEN
    if not sid or not token or sid in placeholders or token in placeholders:
        logger.warning("Twilio credentials not configured, skipping WhatsApp setup")
        return
    twilio_client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
    validator = RequestValidator(Config.TWILIO_AUTH_TOKEN)
    logger.info("WhatsApp (Twilio) client initialized")


def validate_twilio_request(url: str, params: dict, signature: str) -> bool:
    """Validate that the request actually came from Twilio."""
    if not validator:
        return False
    return validator.validate(url, params, signature)


async def process_whatsapp_message(form_data: dict) -> str:
    """Process incoming WhatsApp message and send response."""
    from_number = form_data.get("From", "")
    body = form_data.get("Body", "").strip()
    user_id = f"wa:{from_number}"

    if not body:
        return ""

    response = await handle_command(user_id, body)

    # Send response back via Twilio
    if twilio_client:
        if response.startswith("IMAGE:"):
            image_path = response[6:]
            try:
                # For WhatsApp images, we need a publicly accessible URL.
                # Upload to your server or use a temp hosting service.
                # For now, send a message that image was generated locally.
                twilio_client.messages.create(
                    body="🖼️ Image generated! (WhatsApp image delivery requires a public URL for the image. Check server logs for the file path.)",
                    from_=Config.TWILIO_WHATSAPP_NUMBER,
                    to=from_number,
                )
                logger.info(f"Image generated at: {image_path}")
            except Exception as e:
                twilio_client.messages.create(
                    body=f"Failed to send image: {e}",
                    from_=Config.TWILIO_WHATSAPP_NUMBER,
                    to=from_number,
                )
        else:
            # WhatsApp has a 1600 char limit per message
            for i in range(0, len(response), 1500):
                twilio_client.messages.create(
                    body=response[i:i+1500],
                    from_=Config.TWILIO_WHATSAPP_NUMBER,
                    to=from_number,
                )

    return response
