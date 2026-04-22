"""
Shared command parser for Telegram and WhatsApp bots.
"""
from database import save_prompt, get_prompt, list_prompts, delete_prompt, get_history, log_execution
from llm_providers import run_prompt, AVAILABLE_PROVIDERS
from image_providers import generate_image, AVAILABLE_IMAGE_PROVIDERS


HELP_TEXT = """🤖 *MobiBot Commands*

/prompts — List your saved prompts
/save <name> <template> — Save a prompt (use {input} as placeholder)
/run <name> [input] — Execute a saved prompt
/run:<provider> <name> [input] — Run with specific provider
/delete <name> — Delete a prompt
/history — View recent executions
/providers — List available LLM providers
/imagine <prompt> — Generate an image from text
/imagine:<provider> <prompt> — Generate with specific provider (openai, google)
/provider <name> — Set your default provider
/help — Show this message

*Providers:* openai, anthropic, google, bedrock, vertex, azure

*Example:*
/save summarize Summarize this: {input}
/run summarize The quick brown fox jumps over the lazy dog
/run:anthropic summarize Same text but via Claude
"""


async def handle_command(user_id: str, text: str) -> str:
    """Parse and execute a command. Returns the response text."""
    text = text.strip()

    if not text or text == "/start":
        return f"Welcome to MobiBot! 🤖\n\n{HELP_TEXT}"

    if text == "/help":
        return HELP_TEXT

    if text == "/providers":
        return f"Available providers: {', '.join(AVAILABLE_PROVIDERS)}\nSet default with: /provider <name>"

    if text == "/prompts":
        prompts = list_prompts(user_id)
        if not prompts:
            return "No prompts saved yet. Use /save <name> <template> to create one."
        lines = [f"📋 *Your Prompts* ({len(prompts)}):\n"]
        for p in prompts:
            lines.append(f"• *{p.name}* (v{p.version}, {p.provider}) — {p.template[:60]}...")
        return "\n".join(lines)

    if text == "/history":
        logs = get_history(user_id)
        if not logs:
            return "No execution history yet."
        lines = ["📜 *Recent Executions*:\n"]
        for log in logs:
            lines.append(f"• *{log.prompt_name}* via {log.provider} ({log.tokens_used} tokens)\n  {log.output_text[:80]}...")
        return "\n".join(lines)

    if text.startswith("/save "):
        parts = text[6:].strip().split(" ", 1)
        if len(parts) < 2:
            return "Usage: /save <name> <template>\nExample: /save greet Hello {input}, welcome!"
        name, template = parts
        prompt = save_prompt(user_id, name, template)
        return f"✅ Saved prompt '*{name}*' (v{prompt.version})"

    if text.startswith("/delete "):
        name = text[8:].strip()
        if delete_prompt(user_id, name):
            return f"🗑️ Deleted prompt '*{name}*'"
        return f"Prompt '*{name}*' not found."

    if text.startswith("/run"):
        return await _handle_run(user_id, text)

    if text.startswith("/imagine"):
        return await _handle_imagine(user_id, text)

    if text.startswith("/provider "):
        # This is a per-message hint; actual default is in .env
        provider = text[10:].strip()
        if provider not in AVAILABLE_PROVIDERS:
            return f"Unknown provider. Available: {', '.join(AVAILABLE_PROVIDERS)}"
        return f"Provider hint noted. To permanently change, update DEFAULT_PROVIDER in your .env file.\nUse /run:{provider} <name> to run with this provider."

    # If no command prefix, treat as a direct prompt execution
    result = await run_prompt(text)
    log_execution(user_id, "_direct", result["provider"], text, result["text"], result["tokens"])
    return result["text"]


async def _handle_run(user_id: str, text: str) -> str:
    """Handle /run and /run:<provider> commands."""
    provider = "default"

    # Check for /run:<provider> syntax
    if text.startswith("/run:"):
        colon_part = text.split(" ", 1)[0]  # e.g. /run:anthropic
        provider = colon_part[5:]  # strip "/run:"
        if provider not in AVAILABLE_PROVIDERS:
            return f"Unknown provider '{provider}'. Available: {', '.join(AVAILABLE_PROVIDERS)}"
        rest = text[len(colon_part):].strip()
    else:
        rest = text[4:].strip()  # strip "/run"

    if not rest:
        return "Usage: /run <prompt_name> [input]\nExample: /run summarize Some text to summarize"

    parts = rest.split(" ", 1)
    name = parts[0]
    user_input = parts[1] if len(parts) > 1 else ""

    prompt = get_prompt(user_id, name)
    if not prompt:
        return f"Prompt '*{name}*' not found. Use /prompts to see your saved prompts."

    # Use prompt's saved provider unless overridden
    run_provider = provider if provider != "default" else (prompt.provider if prompt.provider != "default" else "default")

    result = await run_prompt(prompt.template, user_input, run_provider)
    log_execution(user_id, name, result["provider"], user_input, result["text"], result["tokens"])

    return f"🔮 *{name}* (via {result['provider']}, {result['tokens']} tokens):\n\n{result['text']}"


async def _handle_imagine(user_id: str, text: str) -> str:
    """Handle /imagine and /imagine:<provider> commands.
    Returns 'IMAGE:/path/to/file' on success so bots know to send a photo.
    """
    provider = "default"

    if text.startswith("/imagine:"):
        colon_part = text.split(" ", 1)[0]
        provider = colon_part[9:]  # strip "/imagine:"
        if provider not in AVAILABLE_IMAGE_PROVIDERS:
            return f"Unknown image provider '{provider}'. Available: {', '.join(AVAILABLE_IMAGE_PROVIDERS)}"
        prompt = text[len(colon_part):].strip()
    else:
        prompt = text[8:].strip()  # strip "/imagine"

    if not prompt:
        return "Usage: /imagine <description>\nExample: /imagine a cat wearing a space helmet"

    result = await generate_image(prompt, provider)

    if "error" in result:
        return f"❌ {result['error']}"

    # Special prefix so bots know to send as photo
    return f"IMAGE:{result['image_path']}"
