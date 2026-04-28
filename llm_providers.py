"""
Multi-provider LLM router.
Supports: openai, anthropic, google, bedrock, vertex, azure
"""
import json
from config import Config

AVAILABLE_PROVIDERS = ["openai", "anthropic", "google", "bedrock", "vertex", "azure"]


async def run_prompt(template: str, user_input: str = "", provider: str = "default") -> dict:
    """Execute a prompt template against the chosen LLM provider.
    Returns {"text": str, "tokens": int, "provider": str}
    """
    if provider == "default":
        provider = Config.DEFAULT_PROVIDER

    # Render template — supports {input} placeholder
    rendered = template.replace("{input}", user_input).replace("{{input}}", user_input)

    dispatch = {
        "openai": _run_openai,
        "anthropic": _run_anthropic,
        "google": _run_google,
        "bedrock": _run_bedrock,
        "vertex": _run_vertex,
        "azure": _run_azure,
    }

    fn = dispatch.get(provider)
    if not fn:
        return {"text": f"Unknown provider: {provider}. Available: {', '.join(AVAILABLE_PROVIDERS)}", "tokens": 0, "provider": provider}

    try:
        result = await fn(rendered)
        result["provider"] = provider
        return result
    except Exception as e:
        return {"text": f"Error ({provider}): {str(e)}", "tokens": 0, "provider": provider}


async def _run_openai(prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
    resp = await client.chat.completions.create(
        model=Config.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "text": resp.choices[0].message.content,
        "tokens": resp.usage.total_tokens if resp.usage else 0,
    }


async def _run_anthropic(prompt: str) -> dict:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)
    resp = await client.messages.create(
        model=Config.ANTHROPIC_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    tokens = (resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0
    return {"text": resp.content[0].text, "tokens": tokens}


async def _run_google(prompt: str) -> dict:
    import asyncio

    def _sync_call():
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        response = client.models.generate_content(
            model=Config.GOOGLE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
            ),
        )
        text = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    text += part.text
        tokens = getattr(response, "usage_metadata", None)
        token_count = 0
        if tokens:
            token_count = getattr(tokens, "total_token_count", 0) or 0
        return {"text": text or "No response generated.", "tokens": token_count}

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_call)


async def _run_bedrock(prompt: str) -> dict:
    import boto3
    client = boto3.client("bedrock-runtime", region_name=Config.AWS_REGION)
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    })
    resp = client.invoke_model(modelId=Config.BEDROCK_MODEL, body=body)
    result = json.loads(resp["body"].read())
    text = result.get("content", [{}])[0].get("text", "")
    tokens = result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)
    return {"text": text, "tokens": tokens}


async def _run_vertex(prompt: str) -> dict:
    from google.cloud import aiplatform
    from vertexai.generative_models import GenerativeModel
    import vertexai
    vertexai.init(project=Config.VERTEX_PROJECT_ID, location=Config.VERTEX_LOCATION)
    model = GenerativeModel(Config.VERTEX_MODEL)
    resp = await model.generate_content_async(prompt)
    return {"text": resp.text, "tokens": 0}


async def _run_azure(prompt: str) -> dict:
    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        api_key=Config.AZURE_OPENAI_API_KEY,
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_version=Config.AZURE_OPENAI_API_VERSION,
    )
    resp = await client.chat.completions.create(
        model=Config.AZURE_OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "text": resp.choices[0].message.content,
        "tokens": resp.usage.total_tokens if resp.usage else 0,
    }
