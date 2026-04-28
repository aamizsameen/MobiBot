"""
Image generation providers.
Supports: google (Gemini native + Imagen), openai (DALL-E)

Google offers two image generation approaches:
  - Gemini Image models (gemini-2.5-flash-image, etc.) — via generate_content with response_modalities=["IMAGE"]
  - Imagen models (imagen-4.0-generate-001, etc.) — via dedicated generate_images API
"""
from __future__ import annotations
import os
import tempfile
import httpx
from config import Config

AVAILABLE_IMAGE_PROVIDERS = ["google", "openai"]

# Gemini models that can actually generate images (must have "image" in name)
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"

# Imagen model for high-quality image generation
IMAGEN_MODEL = "imagen-4.0-generate-001"


async def generate_image(prompt: str, provider: str = "default") -> dict:
    """Generate an image from a text prompt.
    Returns {"image_path": str, "provider": str} or {"error": str, "provider": str}
    """
    if provider == "default":
        if Config.GOOGLE_API_KEY and Config.GOOGLE_API_KEY != "your-google-key":
            provider = "google"
        elif Config.OPENAI_API_KEY and Config.OPENAI_API_KEY != "your-openai-key":
            provider = "openai"
        else:
            return {"error": "No image provider configured. Set GOOGLE_API_KEY or OPENAI_API_KEY.", "provider": "none"}

    dispatch = {
        "openai": _generate_openai,
        "google": _generate_google,
    }

    fn = dispatch.get(provider)
    if not fn:
        return {"error": f"Unknown image provider: {provider}. Available: {', '.join(AVAILABLE_IMAGE_PROVIDERS)}", "provider": provider}

    try:
        result = await fn(prompt)
        result["provider"] = provider
        return result
    except Exception as e:
        return {"error": f"Error ({provider}): {str(e)}", "provider": provider}


async def _generate_openai(prompt: str) -> dict:
    """Generate image using OpenAI DALL-E 3."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
    resp = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    image_url = resp.data[0].url

    async with httpx.AsyncClient() as http:
        img_resp = await http.get(image_url)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(img_resp.content)
        tmp.close()
        return {"image_path": tmp.name}


async def _generate_google(prompt: str) -> dict:
    """Generate image using Google AI.

    Strategy:
      1. Try Gemini Image model (gemini-2.5-flash-image) — fast, good quality
      2. Fallback to Imagen 4 API if Gemini image model fails
    """
    import asyncio

    def _sync_generate():
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=Config.GOOGLE_API_KEY)

        # --- Attempt 1: Gemini Image model ---
        try:
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        img_data = part.inline_data.data
                        mime = getattr(part.inline_data, "mime_type", "image/png") or "image/png"
                        ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
                        ext = ext_map.get(mime, ".png")

                        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                        tmp.write(img_data if isinstance(img_data, bytes) else img_data.encode())
                        tmp.close()
                        return {"image_path": tmp.name}
        except Exception:
            pass  # Fall through to Imagen

        # --- Attempt 2: Imagen 4 ---
        try:
            response = client.models.generate_images(
                model=IMAGEN_MODEL,
                prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1),
            )

            if response.generated_images:
                img = response.generated_images[0]
                img_bytes = img.image.image_bytes
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp.write(img_bytes)
                tmp.close()
                return {"image_path": tmp.name}
        except Exception as e:
            return {"error": f"Image generation failed: {str(e)}"}

        return {"error": "No image was generated. Try a different prompt."}

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_generate)

