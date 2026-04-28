"""
WhatsApp bot integration via neonize (whatsmeow Python wrapper).
Authenticates via QR code in terminal — no Twilio account needed.
Session is persisted in SQLite so you only scan once.
"""
from __future__ import annotations
import asyncio
import logging
import os
from config import Config

logger = logging.getLogger(__name__)

# Global async client reference
whatsapp_client = None
_client_task: asyncio.Task | None = None


async def setup_whatsapp():
    """Initialize the neonize WhatsApp client with QR code auth."""
    global whatsapp_client, _client_task

    if not Config.WHATSAPP_ENABLED:
        logger.info("WhatsApp is disabled (WHATSAPP_ENABLED=false), skipping setup")
        return

    try:
        from neonize.aioze.client import NewAClient
        from neonize.aioze.events import ConnectedEv, MessageEv, QREv
    except ImportError:
        logger.error(
            "neonize is not installed. Run: pip install neonize\n"
            "Also install libmagic: brew install libmagic (macOS)\n"
            "Then restart the bot."
        )
        return

    # The 'name' is used as the session identifier — neonize stores
    # session data in a SQLite DB named after this value.
    whatsapp_client = NewAClient("mobibot")

    @whatsapp_client.event(ConnectedEv)
    async def on_connected(client: NewAClient, event: ConnectedEv):
        logger.info("✅ WhatsApp connected successfully!")

    @whatsapp_client.event(QREv)
    async def on_qr(client: NewAClient, qr_data: bytes):
        """Display QR code in terminal when authentication is needed."""
        try:
            import segno
            print("\n" + "=" * 60)
            print("  📱 Scan this QR code with WhatsApp")
            print("  WhatsApp → Settings → Linked Devices → Link a Device")
            print("=" * 60 + "\n")
            segno.make_qr(qr_data).terminal(compact=True)
            print("\n" + "=" * 60 + "\n")
        except Exception as e:
            logger.error(f"Failed to display QR code: {e}")

    @whatsapp_client.event(MessageEv)
    async def on_message(client: NewAClient, event: MessageEv):
        await _handle_whatsapp_message(client, event)

    # Start the client in a background task
    _client_task = asyncio.create_task(_run_client())
    logger.info(
        "WhatsApp client starting... "
        "If this is your first run, scan the QR code in the terminal with "
        "WhatsApp → Settings → Linked Devices → Link a Device"
    )


async def _run_client():
    """Run the neonize client (blocking coroutine)."""
    try:
        await whatsapp_client.connect()
        await whatsapp_client.idle()
    except asyncio.CancelledError:
        logger.info("WhatsApp client task cancelled")
    except Exception as e:
        logger.error(f"WhatsApp client error: {e}", exc_info=True)


async def _handle_whatsapp_message(client, event):
    """Process an incoming WhatsApp message through the command system.

    Supports:
      - Text messages → text reply
      - Voice notes → transcribe → LLM → TTS → voice reply
      - Image commands → image reply
    """
    from commands import handle_command

    try:
        msg = event.Message
        sender = event.Info.MessageSource.Sender
        chat = event.Info.MessageSource.Chat
        is_from_me = event.Info.MessageSource.IsFromMe
        is_self_chat = sender.User == chat.User
        is_group = chat.Server == "g.us"

        # Skip group messages to avoid spam/errors
        if is_group:
            return

        # Skip our own outgoing messages (except self-chat for testing)
        if is_from_me and not is_self_chat:
            return

        user_id = f"wa:{sender.User}"
        is_voice = False

        # ── Detect message type ──────────────────────────────────────────
        # Voice message (push-to-talk audio note)
        if msg.audioMessage and msg.audioMessage.PTT:
            is_voice = True
            logger.info(f"🎤 Voice note from {sender.User}, transcribing...")

            try:
                from voice import transcribe_audio

                # Download the audio from WhatsApp servers
                audio_bytes = await client.download_any(msg)
                if not audio_bytes:
                    await client.send_message(chat, "❌ Could not download voice message.")
                    return

                mime = msg.audioMessage.mimetype or "audio/ogg"
                text = await transcribe_audio(audio_bytes, mime)
                logger.info(f"🎤 Transcribed: {text[:80]}...")

            except Exception as e:
                logger.error(f"Voice transcription error: {e}", exc_info=True)
                await client.send_message(chat, f"❌ Could not transcribe voice message: {e}")
                return

        # Text message
        elif msg.conversation:
            text = msg.conversation
        elif msg.extendedTextMessage and msg.extendedTextMessage.text:
            text = msg.extendedTextMessage.text
        else:
            return  # Unsupported message type

        if not text:
            return

        logger.info(f"WhatsApp {'🎤 voice' if is_voice else '💬 text'} from {sender.User}: {text[:50]}...")

        # ── Process through command handler ──────────────────────────────
        response = await handle_command(user_id, text)

        if not response:
            return

        # ── Send response ────────────────────────────────────────────────
        # Image response (from /imagine)
        if response.startswith("IMAGE:"):
            image_path = response[6:]
            await _send_image(client, chat, image_path)
            return

        # Voice response (reply to voice with voice)
        if is_voice:
            await _send_voice_reply(client, chat, response)
        else:
            # Text response — split long messages
            for i in range(0, len(response), 4000):
                chunk = response[i:i + 4000]
                await client.send_message(chat, chunk)

    except Exception as e:
        logger.error(f"Error handling WhatsApp message: {e}", exc_info=True)


async def _send_voice_reply(client, chat_jid, text: str):
    """Convert text to speech and send as a WhatsApp voice note."""
    from voice import text_to_speech

    try:
        logger.info(f"🔊 Generating voice reply ({len(text)} chars)...")
        audio_bytes = await text_to_speech(text)

        if audio_bytes:
            try:
                # Build a proper audio message with ptt=True (voice note)
                audio_msg = await client.build_audio_message(
                    file=audio_bytes,
                    ptt=True,
                )
                await client.send_message(chat_jid, audio_msg)
                logger.info("🔊 Voice reply sent!")
            except Exception as e:
                logger.error(f"send_audio failed: {e}, trying text fallback")
                await client.send_message(chat_jid, f"🔊 {text}")
        else:
            # Fallback to text if TTS fails
            logger.warning("TTS failed, falling back to text reply")
            await client.send_message(chat_jid, text)
    except Exception as e:
        logger.error(f"Voice reply error: {e}", exc_info=True)
        # Fallback to text
        await client.send_message(chat_jid, f"🔊 [Voice reply failed]\n\n{text}")


async def _send_image(client, chat_jid, image_path: str):
    """Send an image file via WhatsApp using neonize."""
    try:
        if not os.path.exists(image_path):
            await client.send_message(chat_jid, f"❌ Image file not found: {image_path}")
            return

        with open(image_path, "rb") as f:
            image_data = f.read()

        image_msg = await client.build_image_message(
            file=image_data,
            caption="🖼️ Generated image",
        )
        await client.send_message(chat_jid, image_msg)

        try:
            os.unlink(image_path)
        except OSError:
            pass

        logger.info(f"Image sent to WhatsApp: {image_path}")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp image: {e}")
        await client.send_message(chat_jid, f"❌ Failed to send image: {e}")


async def shutdown_whatsapp():
    """Gracefully disconnect the WhatsApp client."""
    global whatsapp_client, _client_task
    if _client_task and not _client_task.done():
        _client_task.cancel()
        try:
            await _client_task
        except asyncio.CancelledError:
            pass
    if whatsapp_client:
        try:
            await whatsapp_client.disconnect()
            logger.info("WhatsApp client disconnected")
        except Exception as e:
            logger.warning(f"Error disconnecting WhatsApp: {e}")
