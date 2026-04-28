#!/usr/bin/env python3
"""
MobiBot — Interactive TUI Setup Wizard
Run this to configure your .env file with a beautiful terminal UI.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# ─── Bootstrap: ensure rich + questionary are available ───────────────────────
def _ensure_deps():
    """Install rich and questionary if not present."""
    missing = []
    try:
        import rich  # noqa: F401
    except ImportError:
        missing.append("rich>=13.0.0")
    try:
        import questionary  # noqa: F401
    except ImportError:
        missing.append("questionary>=2.0.0")

    if missing:
        print(f"⏳ Installing setup dependencies: {', '.join(missing)}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *missing, "-q"],
            stdout=subprocess.DEVNULL,
        )
        print("✅ Dependencies installed!\n")


_ensure_deps()

# ─── Now we can safely import ────────────────────────────────────────────────
import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.live import Live
from rich.align import Align
import time

console = Console()

# Custom questionary style to match the branding
CUSTOM_STYLE = Style([
    ("qmark", "fg:#E91E63 bold"),       # Pink question mark
    ("question", "fg:#FFFFFF bold"),     # White question text
    ("answer", "fg:#00E676 bold"),       # Green answer
    ("pointer", "fg:#E91E63 bold"),      # Pink pointer
    ("highlighted", "fg:#E91E63 bold"),  # Pink highlighted
    ("selected", "fg:#00E676"),          # Green selected
    ("separator", "fg:#546E7A"),         # Gray separator
    ("instruction", "fg:#78909C"),       # Muted instruction
    ("text", "fg:#ECEFF1"),             # Light text
])

# ─── Constants ────────────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).parent / ".env"
ENV_EXAMPLE_PATH = Path(__file__).parent / ".env.example"
REQUIREMENTS_PATH = Path(__file__).parent / "requirements.txt"

BANNER = r"""
[bold #E91E63]
    ╔╦╗╔═╗╔╗ ╦╔╗ ╔═╗╔╦╗
    ║║║║ ║╠╩╗║╠╩╗║ ║ ║
    ╩ ╩╚═╝╚═╝╩╚═╝╚═╝ ╩
[/bold #E91E63][bold #78909C]
    ⚡ AI Prompt Engine for
    WhatsApp & Telegram
[/bold #78909C]"""

PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "emoji": "🟢",
        "fields": {
            "OPENAI_API_KEY": {"prompt": "OpenAI API Key", "secret": True, "default": ""},
            "OPENAI_MODEL": {"prompt": "OpenAI Model", "secret": False, "default": "gpt-4o"},
        },
    },
    "anthropic": {
        "name": "Anthropic",
        "emoji": "🟠",
        "fields": {
            "ANTHROPIC_API_KEY": {"prompt": "Anthropic API Key", "secret": True, "default": ""},
            "ANTHROPIC_MODEL": {"prompt": "Anthropic Model", "secret": False, "default": "claude-sonnet-4-20250514"},
        },
    },
    "google": {
        "name": "Google Gemini",
        "emoji": "🔵",
        "fields": {
            "GOOGLE_API_KEY": {"prompt": "Google AI API Key", "secret": True, "default": ""},
            "GOOGLE_MODEL": {"prompt": "Google Model", "secret": False, "default": "gemini-2.0-flash"},
        },
    },
    "bedrock": {
        "name": "AWS Bedrock",
        "emoji": "🟡",
        "fields": {
            "AWS_ACCESS_KEY_ID": {"prompt": "AWS Access Key ID", "secret": True, "default": ""},
            "AWS_SECRET_ACCESS_KEY": {"prompt": "AWS Secret Access Key", "secret": True, "default": ""},
            "AWS_REGION": {"prompt": "AWS Region", "secret": False, "default": "us-east-1"},
            "BEDROCK_MODEL": {"prompt": "Bedrock Model ID", "secret": False, "default": "anthropic.claude-sonnet-4-20250514-v1:0"},
        },
    },
    "vertex": {
        "name": "Google Vertex AI",
        "emoji": "🔷",
        "fields": {
            "VERTEX_PROJECT_ID": {"prompt": "GCP Project ID", "secret": False, "default": ""},
            "VERTEX_LOCATION": {"prompt": "Vertex Location", "secret": False, "default": "us-central1"},
            "VERTEX_MODEL": {"prompt": "Vertex Model", "secret": False, "default": "gemini-2.0-flash"},
            "GOOGLE_APPLICATION_CREDENTIALS": {"prompt": "Path to Service Account JSON", "secret": False, "default": ""},
        },
    },
    "azure": {
        "name": "Azure OpenAI",
        "emoji": "🟣",
        "fields": {
            "AZURE_OPENAI_API_KEY": {"prompt": "Azure OpenAI API Key", "secret": True, "default": ""},
            "AZURE_OPENAI_ENDPOINT": {"prompt": "Azure OpenAI Endpoint URL", "secret": False, "default": ""},
            "AZURE_OPENAI_MODEL": {"prompt": "Azure OpenAI Model", "secret": False, "default": "gpt-4o"},
            "AZURE_OPENAI_API_VERSION": {"prompt": "Azure API Version", "secret": False, "default": "2024-02-01"},
        },
    },
}

PLACEHOLDER_VALUES = {
    "your-telegram-bot-token",
    "your-openai-key",
    "your-anthropic-key",
    "your-google-key",
    "your-aws-access-key",
    "your-aws-secret-key",
    "your-gcp-project-id",
    "your-azure-key",
    "your-twilio-sid",
    "your-twilio-auth-token",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_existing_env() -> dict:
    """Load existing .env values as defaults."""
    values = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                # Remove inline comments
                if "  #" in val:
                    val = val.split("  #")[0].strip()
                if val not in PLACEHOLDER_VALUES:
                    values[key] = val
    return values


def mask_secret(value: str) -> str:
    """Mask a secret value for display."""
    if not value or value in PLACEHOLDER_VALUES:
        return "[dim]not set[/dim]"
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "•" * (len(value) - 8) + value[-4:]


def section_header(title: str, emoji: str = ""):
    """Print a styled section header."""
    console.print()
    console.rule(f"[bold #E91E63]{emoji}  {title}[/bold #E91E63]", style="#E91E63")
    console.print()


# ─── Step Functions ───────────────────────────────────────────────────────────
def step_welcome():
    """Display the welcome banner."""
    console.clear()
    console.print(Panel(
        Align.center(BANNER),
        border_style="#E91E63",
        box=box.DOUBLE_EDGE,
        padding=(1, 4),
        subtitle="[#78909C]v1.0.0 • Setup Wizard[/#78909C]",
    ))
    console.print()
    console.print(
        "[bold]Welcome to MobiBot Setup![/bold] "
        "This wizard will configure your environment step by step.",
        style="#ECEFF1",
    )
    console.print()

    if ENV_PATH.exists():
        console.print(
            "[yellow]⚠  An existing .env file was found. "
            "Your current values will be used as defaults.[/yellow]"
        )
        console.print()

    if not questionary.confirm(
        "Ready to begin?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask():
        console.print("[dim]Setup cancelled. Goodbye![/dim]")
        sys.exit(0)


def step_install_deps():
    """Install project dependencies from requirements.txt."""
    section_header("Dependencies", "📦")

    if not REQUIREMENTS_PATH.exists():
        console.print("[yellow]requirements.txt not found, skipping...[/yellow]")
        return

    install = questionary.confirm(
        "Install project dependencies (pip install -r requirements.txt)?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask()

    if install:
        console.print("[dim]Installing dependencies...[/dim]")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                console.print("[green]✅ All dependencies installed successfully![/green]")
            else:
                console.print(f"[red]❌ pip install failed:[/red]\n{result.stderr[:500]}")
                if not questionary.confirm("Continue anyway?", default=True, style=CUSTOM_STYLE).ask():
                    sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
    else:
        console.print("[dim]Skipping dependency installation.[/dim]")


def step_server_config(existing: dict) -> dict:
    """Configure server settings."""
    section_header("Server Configuration", "🖥️")

    host = questionary.text(
        "Host address:",
        default=existing.get("HOST", "0.0.0.0"),
        style=CUSTOM_STYLE,
    ).ask()

    port = questionary.text(
        "Port:",
        default=existing.get("PORT", "8000"),
        style=CUSTOM_STYLE,
        validate=lambda val: val.isdigit() or "Port must be a number",
    ).ask()

    default_url = existing.get("BASE_URL", "http://localhost:8000")
    base_url = questionary.text(
        "Base URL (public URL or ngrok URL for webhooks):",
        default=default_url,
        style=CUSTOM_STYLE,
    ).ask()

    return {"HOST": host, "PORT": port, "BASE_URL": base_url}


def step_database_config(existing: dict) -> dict:
    """Configure database settings."""
    section_header("Database", "🗄️")

    db_url = questionary.text(
        "Database URL:",
        default=existing.get("DATABASE_URL", "sqlite:///./mobibot.db"),
        style=CUSTOM_STYLE,
    ).ask()

    return {"DATABASE_URL": db_url}


def step_messaging_channels(existing: dict) -> dict:
    """Configure messaging channels (Telegram, WhatsApp)."""
    section_header("Messaging Channels", "💬")

    console.print(
        "[#78909C]Select which messaging platforms to enable. "
        "You can enable both![/#78909C]"
    )
    console.print()

    channels = questionary.checkbox(
        "Enable channels:",
        choices=[
            questionary.Choice("📱 Telegram", value="telegram"),
            questionary.Choice("💬 WhatsApp (QR Code Auth — no Twilio needed!)", value="whatsapp"),
        ],
        style=CUSTOM_STYLE,
        validate=lambda x: len(x) > 0 or "Select at least one channel",
    ).ask()

    config = {}

    if "telegram" in channels:
        console.print()
        console.print(
            "[#78909C]Get your Telegram bot token from @BotFather on Telegram.[/#78909C]"
        )
        token = questionary.text(
            "Telegram Bot Token:",
            default=existing.get("TELEGRAM_BOT_TOKEN", ""),
            style=CUSTOM_STYLE,
        ).ask()
        config["TELEGRAM_BOT_TOKEN"] = token
    else:
        config["TELEGRAM_BOT_TOKEN"] = ""

    if "whatsapp" in channels:
        config["WHATSAPP_ENABLED"] = "true"
        config["WHATSAPP_SESSION_DB"] = existing.get("WHATSAPP_SESSION_DB", "./whatsapp_session.db")
        console.print()
        console.print(Panel(
            "[bold #00E676]WhatsApp Setup — No configuration needed here![/bold #00E676]\n\n"
            "When you start MobiBot for the first time, a [bold]QR code[/bold] will appear "
            "in your terminal.\n\n"
            "[bold]To connect:[/bold]\n"
            "  1. Open WhatsApp on your phone\n"
            "  2. Go to [bold]Settings → Linked Devices → Link a Device[/bold]\n"
            "  3. Scan the QR code shown in the terminal\n\n"
            "[dim]Your session is saved locally — you won't need to scan again "
            "unless you log out.[/dim]",
            border_style="#00E676",
            title="[bold #00E676]📱 WhatsApp[/bold #00E676]",
            padding=(1, 2),
        ))
    else:
        config["WHATSAPP_ENABLED"] = "false"
        config["WHATSAPP_SESSION_DB"] = "./whatsapp_session.db"

    return config


def step_llm_providers(existing: dict) -> dict:
    """Configure LLM providers."""
    section_header("LLM Providers", "🤖")

    console.print(
        "[#78909C]Select the AI providers you want to use. "
        "You only need to configure the ones you select.[/#78909C]"
    )
    console.print()

    choices = [
        questionary.Choice(
            f"{p['emoji']}  {p['name']}",
            value=key,
        )
        for key, p in PROVIDERS.items()
    ]

    selected = questionary.checkbox(
        "Select LLM providers to configure:",
        choices=choices,
        style=CUSTOM_STYLE,
        validate=lambda x: len(x) > 0 or "Select at least one provider",
    ).ask()

    if not selected:
        console.print("[red]No providers selected. At least one is required.[/red]")
        sys.exit(1)

    config = {}

    # Set default provider
    if len(selected) == 1:
        config["DEFAULT_PROVIDER"] = selected[0]
    else:
        default_choices = [
            questionary.Choice(
                f"{PROVIDERS[s]['emoji']}  {PROVIDERS[s]['name']}",
                value=s,
            )
            for s in selected
        ]
        default_provider = questionary.select(
            "Which provider should be the default?",
            choices=default_choices,
            style=CUSTOM_STYLE,
        ).ask()
        config["DEFAULT_PROVIDER"] = default_provider

    # Configure each selected provider
    for provider_key in selected:
        provider = PROVIDERS[provider_key]
        console.print()
        console.print(f"[bold]{provider['emoji']}  Configuring {provider['name']}[/bold]")
        console.print()

        for field_key, field_info in provider["fields"].items():
            default = existing.get(field_key, field_info["default"])
            if default in PLACEHOLDER_VALUES:
                default = ""

            if field_info.get("secret") and default:
                console.print(
                    f"  [dim]Current value: {mask_secret(default)}[/dim]"
                )

            value = questionary.text(
                f"  {field_info['prompt']}:",
                default=default,
                style=CUSTOM_STYLE,
            ).ask()

            config[field_key] = value

    # Set defaults for unselected providers (so .env is complete)
    for provider_key, provider in PROVIDERS.items():
        if provider_key not in selected:
            for field_key, field_info in provider["fields"].items():
                if field_key not in config:
                    config[field_key] = existing.get(field_key, field_info["default"]) or field_info["default"]

    return config


def step_summary_and_confirm(all_config: dict) -> bool:
    """Show a summary table and ask for confirmation."""
    section_header("Configuration Summary", "📋")

    # Secrets to mask
    secret_keys = set()
    for provider in PROVIDERS.values():
        for field_key, field_info in provider["fields"].items():
            if field_info.get("secret"):
                secret_keys.add(field_key)
    secret_keys.add("TELEGRAM_BOT_TOKEN")

    # Build grouped tables
    groups = [
        ("🖥️  Server", ["HOST", "PORT", "BASE_URL"]),
        ("🗄️  Database", ["DATABASE_URL"]),
        ("📱  Telegram", ["TELEGRAM_BOT_TOKEN"]),
        ("💬  WhatsApp", ["WHATSAPP_ENABLED", "WHATSAPP_SESSION_DB"]),
        ("🤖  Default Provider", ["DEFAULT_PROVIDER"]),
    ]

    # Add provider groups for selected providers
    default_provider = all_config.get("DEFAULT_PROVIDER", "openai")
    for key, provider in PROVIDERS.items():
        field_keys = list(provider["fields"].keys())
        # Only show providers that have non-empty values
        has_values = any(
            all_config.get(fk, "") and all_config.get(fk, "") not in PLACEHOLDER_VALUES
            for fk in field_keys
            if provider["fields"][fk].get("secret")
        )
        if has_values or key == default_provider:
            groups.append((f"{provider['emoji']}  {provider['name']}", field_keys))

    table = Table(
        box=box.ROUNDED,
        border_style="#E91E63",
        show_header=True,
        header_style="bold #E91E63",
        padding=(0, 2),
    )
    table.add_column("Setting", style="bold #ECEFF1", min_width=25)
    table.add_column("Value", style="#00E676", min_width=40)

    for group_name, keys in groups:
        table.add_row(f"[bold #78909C]{group_name}[/bold #78909C]", "", style="dim")
        for key in keys:
            value = all_config.get(key, "")
            display = mask_secret(value) if key in secret_keys else (value or "[dim]not set[/dim]")
            table.add_row(f"  {key}", display)
        table.add_row("", "")  # spacer

    console.print(table)
    console.print()

    return questionary.confirm(
        "Write this configuration to .env?",
        default=True,
        style=CUSTOM_STYLE,
    ).ask()


def step_write_env(all_config: dict):
    """Write the .env file (with backup)."""
    section_header("Writing Configuration", "💾")

    # Backup existing .env
    if ENV_PATH.exists():
        backup_name = f".env.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = ENV_PATH.parent / backup_name
        shutil.copy2(ENV_PATH, backup_path)
        console.print(f"[dim]Backed up existing .env → {backup_name}[/dim]")

    # Generate .env content
    lines = []
    lines.append("# ═══════════════════════════════════════════════════════════════")
    lines.append("# MobiBot Configuration")
    lines.append(f"# Generated by setup wizard on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("# ═══════════════════════════════════════════════════════════════")
    lines.append("")

    def add_section(title, keys, comment=None):
        lines.append(f"# === {title} ===")
        if comment:
            lines.append(f"# {comment}")
        for key in keys:
            val = all_config.get(key, "")
            lines.append(f"{key}={val}")
        lines.append("")

    add_section("Server", ["HOST", "PORT", "BASE_URL"])
    add_section("Database", ["DATABASE_URL"])
    add_section("Telegram", ["TELEGRAM_BOT_TOKEN"])
    add_section("WhatsApp (Direct — QR code auth via neonize)", ["WHATSAPP_ENABLED", "WHATSAPP_SESSION_DB"],
                "No API keys needed! Scan QR code on first run.")

    add_section("LLM Defaults", ["DEFAULT_PROVIDER"])

    for key, provider in PROVIDERS.items():
        field_keys = list(provider["fields"].keys())
        add_section(provider["name"], field_keys)

    ENV_PATH.write_text("\n".join(lines) + "\n")
    console.print("[green]✅ .env file written successfully![/green]")


def step_next_steps():
    """Show next steps after setup."""
    console.print()
    console.print(Panel(
        "[bold #00E676]🎉  Setup Complete![/bold #00E676]\n\n"
        "[bold]Next steps:[/bold]\n\n"
        "  [bold #E91E63]1.[/bold #E91E63] Start MobiBot:\n"
        "     [bold]python app.py[/bold]\n\n"
        "  [bold #E91E63]2.[/bold #E91E63] If WhatsApp is enabled:\n"
        "     Scan the QR code that appears in the terminal\n"
        "     with WhatsApp → Settings → Linked Devices\n\n"
        "  [bold #E91E63]3.[/bold #E91E63] If Telegram is enabled:\n"
        "     Make sure your BASE_URL is publicly accessible\n"
        "     (use ngrok for local development)\n\n"
        "  [bold #E91E63]4.[/bold #E91E63] Send a message to test:\n"
        "     Try [bold]/help[/bold] to see all commands\n\n"
        "[dim]To reconfigure, just run [bold]python setup.py[/bold] again.[/dim]",
        border_style="#E91E63",
        box=box.DOUBLE_EDGE,
        padding=(1, 3),
    ))
    console.print()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    """Run the full setup wizard."""
    try:
        existing = load_existing_env()

        step_welcome()
        step_install_deps()

        config = {}
        config.update(step_server_config(existing))
        config.update(step_database_config(existing))
        config.update(step_messaging_channels(existing))
        config.update(step_llm_providers(existing))

        if step_summary_and_confirm(config):
            step_write_env(config)
            step_next_steps()
        else:
            console.print("[dim]Setup cancelled. No changes were made.[/dim]")

    except KeyboardInterrupt:
        console.print("\n[dim]Setup cancelled. Goodbye![/dim]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
