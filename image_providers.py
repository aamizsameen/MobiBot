"""
Image generation providers.
Supports: openai (DALL-E), google (Imagen)
"""
from __future__ import annotations
import base64
import os
import tempfile
import httpx
from config import Config

AVAILABLE_IMAGE_PROVIDERS = ["openai", "google"]


async def generate_image(prompt: str, provider: str = "default") -> dict:
    """Generate an image from a text prompt.
    Returns {"image_path": str, "provider": str} or {"error": str, "provider": str}
    """
    if provider == "default":
        # Pick first available image provider
        if Config.OPENAI_API_KEY and Config.OPENAI_API_KEY != "your-openai-key":
            provider = "openai"
        elif Config.GOOGLE_API_KEY and Config.GOOGLE_API_KEY != "your-google-key":
            provider = "google"
        else:
            return {"error": "No image provider configured. Set OPENAI_API_KEY or GOOGLE_API_KEY.", "provider": "none"}

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

    # Download the image to a temp file
    async with httpx.AsyncClient() as http:
        img_resp = await http.get(image_url)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(img_resp.content)
        tmp.close()
        return {"image_path": tmp.name}


async def _generate_google(prompt: str) -> dict:
    """Generate image using Google Gemini's image generation."""
    import google.generativeai as genai
    genai.configure(api_key=Config.GOOGLE_API_KEY)

    # Use Gemini 2.0 Flash with image generation
    model = genai.GenerativeModel(Config.GOOGLE_MODEL)
    response = await model.generate_content_async(
        f"Generate an image of: {prompt}",
        generation_config=genai.GenerationConfig(response_modalities=["image", "text"]),
    )

    # Extract image from response parts
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data is not None:
            img_data = part.inline_data.data
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(base64.b64decode(img_data) if isinstance(img_data, str) else img_data)
            tmp.close()
            return {"image_path": tmp.name}

    return {"error": "No image was generated. The model may not support image output with this prompt."}
