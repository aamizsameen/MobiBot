"""
Shared command parser for Telegram and WhatsApp bots.
"""
import re
import datetime
from database import (
    save_prompt, get_prompt, list_prompts, delete_prompt,
    get_history, log_execution,
    create_scheduled_task, list_scheduled_tasks, delete_scheduled_task,
)
from llm_providers import run_prompt, AVAILABLE_PROVIDERS
from image_providers import generate_image, AVAILABLE_IMAGE_PROVIDERS

# IST offset (UTC+5:30) — used as default timezone for scheduling
IST_OFFSET = datetime.timedelta(hours=5, minutes=30)


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

📅 *Scheduling:*
/schedule <time> <phone> <message> — Schedule a message
/schedules — List your pending schedules
/unschedule <id> — Cancel a scheduled message

/help — Show this message

*Providers:* openai, anthropic, google, bedrock, vertex, azure

*Schedule Examples:*
/schedule 15:00 +919876543210 Hey, let's catch up!
/schedule 2026-04-28 09:30 +919876543210 Good morning!
/schedule 5m +919876543210 Reminder in 5 minutes
/schedule 2h +919876543210 Reminder in 2 hours
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

    if text.startswith("/schedule "):
        return _handle_schedule(user_id, text)

    if text == "/schedules":
        return _handle_list_schedules(user_id)

    if text.startswith("/unschedule "):
        return _handle_unschedule(user_id, text)

    if text.startswith("/provider "):
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

    if text.startswith("/run:"):
        colon_part = text.split(" ", 1)[0]
        provider = colon_part[5:]
        if provider not in AVAILABLE_PROVIDERS:
            return f"Unknown provider '{provider}'. Available: {', '.join(AVAILABLE_PROVIDERS)}"
        rest = text[len(colon_part):].strip()
    else:
        rest = text[4:].strip()

    if not rest:
        return "Usage: /run <prompt_name> [input]\nExample: /run summarize Some text to summarize"

    parts = rest.split(" ", 1)
    name = parts[0]
    user_input = parts[1] if len(parts) > 1 else ""

    prompt = get_prompt(user_id, name)
    if not prompt:
        return f"Prompt '*{name}*' not found. Use /prompts to see your saved prompts."

    run_provider = provider if provider != "default" else (prompt.provider if prompt.provider != "default" else "default")

    result = await run_prompt(prompt.template, user_input, run_provider)
    log_execution(user_id, name, result["provider"], user_input, result["text"], result["tokens"])

    return f"🔮 *{name}* (via {result['provider']}, {result['tokens']} tokens):\n\n{result['text']}"


async def _handle_imagine(user_id: str, text: str) -> str:
    """Handle /imagine and /imagine:<provider> commands."""
    provider = "default"

    if text.startswith("/imagine:"):
        colon_part = text.split(" ", 1)[0]
        provider = colon_part[9:]
        if provider not in AVAILABLE_IMAGE_PROVIDERS:
            return f"Unknown image provider '{provider}'. Available: {', '.join(AVAILABLE_IMAGE_PROVIDERS)}"
        prompt = text[len(colon_part):].strip()
    else:
        prompt = text[8:].strip()

    if not prompt:
        return "Usage: /imagine <description>\nExample: /imagine a cat wearing a space helmet"

    result = await generate_image(prompt, provider)

    if "error" in result:
        return f"❌ {result['error']}"

    return f"IMAGE:{result['image_path']}"


# ──── Scheduling ─────────────────────────────────────────────────────────────

def _parse_schedule_time(time_str: str) -> datetime.datetime | None:
    """Parse various time formats and return a UTC datetime.

    Supported formats:
      - "15:00" or "3:00pm" → today at that time (IST)
      - "2026-04-28 15:00" → specific date and time (IST)
      - "5m" → 5 minutes from now
      - "2h" → 2 hours from now
      - "1d" → 1 day from now
    """
    time_str = time_str.strip()
    now_utc = datetime.datetime.utcnow()
    now_ist = now_utc + IST_OFFSET

    # Relative time: 5m, 2h, 1d
    relative = re.match(r"^(\d+)(m|h|d)$", time_str, re.IGNORECASE)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2).lower()
        delta = {"m": datetime.timedelta(minutes=amount),
                 "h": datetime.timedelta(hours=amount),
                 "d": datetime.timedelta(days=amount)}[unit]
        return now_utc + delta

    # Absolute date+time: 2026-04-28 15:00
    try:
        dt_ist = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        return dt_ist - IST_OFFSET  # convert IST to UTC
    except ValueError:
        pass

    # Time only: 15:00 or 3:00pm
    for fmt in ["%H:%M", "%I:%M%p", "%I:%M %p"]:
        try:
            parsed = datetime.datetime.strptime(time_str.upper(), fmt)
            dt_ist = now_ist.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
            # If that time already passed today, schedule for tomorrow
            if dt_ist <= now_ist:
                dt_ist += datetime.timedelta(days=1)
            return dt_ist - IST_OFFSET  # convert IST to UTC
        except ValueError:
            continue

    return None


def _handle_schedule(user_id: str, text: str) -> str:
    """Handle /schedule command.

    Formats:
      /schedule 15:00 +919876543210 Hey!
      /schedule 2026-04-28 15:00 +919876543210 Hey!
      /schedule 5m +919876543210 Hey!
    """
    rest = text[10:].strip()
    if not rest:
        return (
            "Usage: /schedule <time> <phone> <message>\n\n"
            "Time formats:\n"
            "  15:00 — Today at 3 PM (IST)\n"
            "  2026-04-28 09:30 — Specific date (IST)\n"
            "  5m — In 5 minutes\n"
            "  2h — In 2 hours\n\n"
            "Example:\n"
            "  /schedule 15:00 +919876543210 Hey, let's catch up!"
        )

    # Try to parse: first check if it starts with a date (YYYY-MM-DD HH:MM)
    date_time_match = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})\s+", rest)
    if date_time_match:
        time_str = date_time_match.group(1)
        remaining = rest[date_time_match.end():].strip()
    else:
        # Take the first token as time
        parts = rest.split(None, 1)
        if len(parts) < 2:
            return "❌ Not enough arguments. Usage: /schedule <time> <phone> <message>"
        time_str = parts[0]
        remaining = parts[1]

    # Parse time
    scheduled_utc = _parse_schedule_time(time_str)
    if not scheduled_utc:
        return f"❌ Could not parse time: '{time_str}'\n\nSupported: 15:00, 2026-04-28 09:30, 5m, 2h, 1d"

    # Parse phone and message
    parts = remaining.split(None, 1)
    if len(parts) < 2:
        return "❌ Need both a phone number and a message.\nUsage: /schedule <time> <phone> <message>"

    phone = parts[0]
    message = parts[1]

    # Validate phone number (basic check)
    clean_phone = phone.lstrip("+")
    if not clean_phone.isdigit() or len(clean_phone) < 7:
        return f"❌ Invalid phone number: '{phone}'\nUse format: +919876543210"

    # Create the task
    task = create_scheduled_task(user_id, clean_phone, message, scheduled_utc)

    # Show confirmation in IST
    scheduled_ist = scheduled_utc + IST_OFFSET
    time_display = scheduled_ist.strftime("%b %d, %Y at %I:%M %p IST")

    return (
        f"✅ Message scheduled! (ID: #{task.id})\n\n"
        f"📅 *When:* {time_display}\n"
        f"📱 *To:* +{clean_phone}\n"
        f"💬 *Message:* {message[:100]}{'...' if len(message) > 100 else ''}\n\n"
        f"Use /schedules to view all, /unschedule {task.id} to cancel."
    )


def _handle_list_schedules(user_id: str) -> str:
    """Handle /schedules command."""
    tasks = list_scheduled_tasks(user_id)
    if not tasks:
        return "📅 No pending scheduled messages.\nUse /schedule to create one."

    lines = [f"📅 *Pending Schedules* ({len(tasks)}):\n"]
    for t in tasks:
        ist = t.scheduled_at + IST_OFFSET
        time_str = ist.strftime("%b %d at %I:%M %p")
        lines.append(
            f"• *#{t.id}* → +{t.target_phone} at {time_str}\n"
            f"  💬 {t.message[:60]}{'...' if len(t.message) > 60 else ''}"
        )
    lines.append("\nCancel with: /unschedule <id>")
    return "\n".join(lines)


def _handle_unschedule(user_id: str, text: str) -> str:
    """Handle /unschedule <id> command."""
    id_str = text[12:].strip()
    if not id_str.isdigit():
        return "Usage: /unschedule <id>\nGet IDs from /schedules"

    task_id = int(id_str)
    if delete_scheduled_task(user_id, task_id):
        return f"🗑️ Cancelled scheduled message #{task_id}"
    return f"❌ Schedule #{task_id} not found or already executed."
