"""
Voice processing for MobiBot.
- STT: Transcribes incoming WhatsApp voice messages using Gemini
- TTS: Converts text responses to voice notes using Gemini TTS
- Audio conversion via ffmpeg (PCM → OGG Opus for WhatsApp)
"""
from __future__ import annotations
import asyncio
import logging
import os
import tempfile
import wave
from config import Config

logger = logging.getLogger(__name__)

# Gemini model for TTS (text-to-speech)
TTS_MODEL = "gemini-2.5-flash-preview-tts"
# Gemini model for STT (speech-to-text / audio understanding)
STT_MODEL = "gemini-2.5-flash"
# TTS voice — Options: Kore, Charon, Fenrir, Aoede, Puck, Leda, Orus, Zephyr
TTS_VOICE = "Kore"


def _sync_transcribe(audio_bytes: bytes, mime_type: str) -> str:
    """Synchronous transcription — runs in a thread to avoid blocking the event loop."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=Config.GOOGLE_API_KEY)

    response = client.models.generate_content(
        model=STT_MODEL,
        contents=[
            "Listen to this audio message and transcribe what the person is saying. "
            "Return ONLY the spoken words, nothing else.",
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        ],
    )

    text = ""
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.text:
                text += part.text

    return text.strip() or "[Could not transcribe audio]"


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """Transcribe audio bytes to text using Gemini's multimodal understanding.

    Runs the API call in a thread executor to avoid blocking the async event loop.
    """
    logger.info(f"STT: Transcribing {len(audio_bytes)} bytes ({mime_type})...")
    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, _sync_transcribe, audio_bytes, mime_type)
    logger.info(f"STT result: {text[:100]}...")
    return text


def _sync_tts(text: str) -> bytes | None:
    """Synchronous TTS — runs in a thread to avoid blocking the event loop."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=Config.GOOGLE_API_KEY)

    # Limit text length for TTS
    if len(text) > 3000:
        text = text[:3000] + "... I'll stop here. The full response was too long for a voice note."

    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=TTS_VOICE,
                    )
                )
            ),
        ),
    )

    if not response.candidates:
        logger.warning("TTS: No candidates in response")
        return None

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            pcm_data = part.inline_data.data
            mime = part.inline_data.mime_type or ""
            # Parse sample rate from mime (e.g., "audio/L16;codec=pcm;rate=24000")
            sample_rate = 24000
            if "rate=" in mime:
                try:
                    sample_rate = int(mime.split("rate=")[1].split(";")[0])
                except (ValueError, IndexError):
                    pass
            return _sync_pcm_to_ogg(pcm_data, sample_rate)

    logger.warning("TTS: No audio data in response")
    return None


def _sync_pcm_to_ogg(pcm_data: bytes, sample_rate: int = 24000) -> bytes | None:
    """Convert raw PCM audio to OGG Opus format using ffmpeg (synchronous).

    Uses proper metadata so neonize's ffmpeg probe can read duration/tags.
    """
    import subprocess

    wav_path = tempfile.mktemp(suffix=".wav")
    ogg_path = tempfile.mktemp(suffix=".ogg")

    try:
        # Create a proper WAV file from raw PCM data
        with wave.open(wav_path, "wb") as wav_file:
            wav_file.setnchannels(1)        # mono
            wav_file.setsampwidth(2)         # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)

        # Convert WAV → OGG Opus with proper metadata
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path,
             "-c:a", "libopus", "-b:a", "64k", "-ar", "48000",
             "-application", "voip",
             "-metadata", "title=MobiBot Voice",
             "-metadata", "artist=MobiBot",
             ogg_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=30,
        )

        if result.returncode != 0:
            logger.error(f"ffmpeg failed: {result.stderr.decode()[:200]}")
            return None

        with open(ogg_path, "rb") as f:
            return f.read()

    except Exception as e:
        logger.error(f"Audio conversion error: {e}", exc_info=True)
        return None
    finally:
        for path in [wav_path, ogg_path]:
            try:
                os.unlink(path)
            except OSError:
                pass


async def text_to_speech(text: str) -> bytes | None:
    """Convert text to speech using Gemini TTS.

    Runs API call + ffmpeg conversion in a thread executor.

    Returns:
        OGG Opus audio bytes ready for WhatsApp, or None on failure
    """
    logger.info(f"TTS: Converting {len(text)} chars to speech...")
    try:
        loop = asyncio.get_running_loop()
        ogg_bytes = await loop.run_in_executor(None, _sync_tts, text)
        if ogg_bytes:
            logger.info(f"TTS: Generated {len(ogg_bytes)} bytes of OGG audio")
        else:
            logger.warning("TTS: No audio generated")
        return ogg_bytes
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        return None
