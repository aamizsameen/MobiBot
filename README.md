# 🤖 MobiBot

**Command your AI prompts from any mobile device via WhatsApp and Telegram.**

MobiBot is a self-hosted chatbot that lets you save, manage, and execute AI prompt templates from your phone. It supports 6 LLM providers and 2 image generation providers, all accessible through simple chat commands.

---

## ✨ Features

- 📝 **Prompt Management** — Save, version, list, and delete reusable prompt templates
- 🔄 **6 LLM Providers** — OpenAI, Anthropic, Google Gemini, AWS Bedrock, Vertex AI, Azure OpenAI
- 🎨 **Image Generation** — Generate images via OpenAI DALL-E 3 or Google Gemini
- 📱 **Dual Platform** — Works on both WhatsApp (via Twilio) and Telegram
- 📊 **Execution History** — Track all prompt runs with token usage
- 🎯 **Per-prompt Provider Selection** — Choose which AI model to use per prompt or per execution
- 💬 **Direct Chat** — Send any text without a command to get an instant AI response

---

## 📋 Prerequisites

Before you begin, make sure you have:

- **Python 3.9+** installed
- **ngrok** installed ([download here](https://ngrok.com/download)) — needed to expose your local server to the internet
- At least one **LLM API key** (OpenAI, Anthropic, Google, etc.)
- A **Telegram Bot Token** and/or **Twilio account** for WhatsApp

---

## 🚀 Getting Started

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/mobibot.git
cd mobibot
```

### Step 2: Create a Virtual Environment & Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate          # Windows

pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in the required values (see the [Configuration](#-configuration) section below).

### Step 4: Start ngrok

Open a **separate terminal** and run:

```bash
ngrok http 8000
```

Copy the `https://` URL that ngrok gives you (e.g. `https://abc123.ngrok-free.dev`). You'll need this in the next step.

### Step 5: Update `.env` with your ngrok URL

```env
BASE_URL=https://abc123.ngrok-free.dev
```

> ⚠️ **Important:** The `BASE_URL` must be your public ngrok URL, not `localhost`. This is required for Telegram and WhatsApp webhooks to reach your server.

### Step 6: Run the App

```bash
source venv/bin/activate
python3 app.py
```

You should see output like:

```
INFO: Starting MobiBot...
INFO: Telegram bot webhook set
INFO: MobiBot is ready!
INFO: Uvicorn running on http://0.0.0.0:8000
```

✅ **MobiBot is now live!** Open Telegram or WhatsApp and start chatting with your bot.

---

## ⚙️ Configuration

All configuration is managed through the `.env` file. Here's what each section does:

### Server Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `BASE_URL` | Your public URL (ngrok URL for dev) | `http://localhost:8000` |
| `DATABASE_URL` | SQLite database path | `sqlite:///./mobibot.db` |

### Telegram Setup

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from [@BotFather](https://t.me/BotFather) |

**How to get your Telegram Bot Token:**

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to name your bot
3. BotFather will give you a token like `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`
4. Paste this token into your `.env` file as `TELEGRAM_BOT_TOKEN`

### WhatsApp Setup (Twilio)

| Variable | Description |
|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Your Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Your Twilio Auth Token |
| `TWILIO_WHATSAPP_NUMBER` | Your Twilio WhatsApp number (e.g. `whatsapp:+14155238886`) |

**How to set up WhatsApp via Twilio:**

1. Sign up at [twilio.com](https://www.twilio.com/) and get your Account SID and Auth Token from the Console dashboard
2. Go to **Console → Messaging → Try it out → Send a WhatsApp message**
3. Follow the sandbox setup instructions — you'll need to send a join code from your phone (e.g. `join example-sandbox`)
4. Copy your Account SID, Auth Token, and the WhatsApp sandbox number into `.env`
5. In the Twilio Console, set the **webhook URL** for incoming messages to:
   ```
   https://your-ngrok-url.ngrok-free.dev/webhook/whatsapp
   ```
   Use HTTP **POST** method.

### LLM Provider API Keys

You only need to configure the providers you want to use. Set `DEFAULT_PROVIDER` to your preferred one.

| Variable | Description | Default Model |
|----------|-------------|---------------|
| `DEFAULT_PROVIDER` | Default LLM provider | `openai` |
| `OPENAI_API_KEY` | [OpenAI API key](https://platform.openai.com/api-keys) | Model: `gpt-4o` |
| `ANTHROPIC_API_KEY` | [Anthropic API key](https://console.anthropic.com/) | Model: `claude-sonnet-4-20250514` |
| `GOOGLE_API_KEY` | [Google AI Studio key](https://aistudio.google.com/apikey) | Model: `gemini-2.0-flash` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |
| `VERTEX_PROJECT_ID` | GCP project ID for Vertex AI | Model: `gemini-2.0-flash` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | Model: `gpt-4o` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | — |

> 💡 **Tip:** The easiest way to get started is to just configure `OPENAI_API_KEY` or `GOOGLE_API_KEY` — you can add more providers later.

---

## 💬 Bot Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/prompts` | List your saved prompts |
| `/save <name> <template>` | Save a prompt template (use `{input}` as placeholder) |
| `/run <name> [input]` | Execute a saved prompt with optional input |
| `/run:<provider> <name> [input]` | Run with a specific LLM provider |
| `/delete <name>` | Delete a saved prompt |
| `/history` | View your recent executions with token usage |
| `/providers` | List all available LLM providers |
| `/imagine <prompt>` | Generate an image from a text description |
| `/imagine:<provider> <prompt>` | Generate image with a specific provider (`openai` or `google`) |

---

## 📖 Usage Examples

### Save and run a prompt

```
/save summarize Summarize the following text concisely: {input}
```
```
/run summarize The quick brown fox jumps over the lazy dog. It ran across the field and jumped over the fence. Then it sat down and took a nap.
```

### Run with a specific provider

```
/run:anthropic summarize Same text but using Claude
/run:google summarize Same text but using Gemini
```

### Generate an image

```
/imagine a cat wearing a space helmet floating in orbit
/imagine:openai a cyberpunk cityscape at sunset
```

### Direct chat (no command needed)

Just type any message without a `/` prefix and MobiBot will send it directly to your default LLM:

```
What is the capital of France?
```

---

## 🏗️ Project Structure

```
mobibot/
├── app.py               # FastAPI entry point, webhook endpoints, server lifecycle
├── config.py            # Environment variable configuration loader
├── bot_telegram.py      # Telegram bot integration (webhook mode)
├── bot_whatsapp.py      # WhatsApp bot integration via Twilio
├── commands.py          # Shared command parser (handles all /commands)
├── llm_providers.py     # Multi-provider LLM router (6 providers)
├── image_providers.py   # Image generation (DALL-E 3, Google Gemini)
├── database.py          # SQLAlchemy ORM models + CRUD operations
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── .env                 # Your local config (not committed to git)
```

---

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check — returns app status |
| `POST` | `/webhook/telegram` | Receives Telegram bot updates |
| `POST` | `/webhook/whatsapp` | Receives WhatsApp messages via Twilio |

---

## 🛠️ Development

### Running in Development Mode

The app runs with `--reload` enabled by default, so any code changes will auto-restart the server.

```bash
source venv/bin/activate
python3 app.py
```

### Inspecting Requests

ngrok provides a web inspection UI at [http://127.0.0.1:4040](http://127.0.0.1:4040) where you can see all incoming webhook requests and replay them for debugging.

### Database

MobiBot uses SQLite by default. The database file (`mobibot.db`) is created automatically on first run. You can inspect it with any SQLite client:

```bash
sqlite3 mobibot.db
.tables          # shows: prompts, execution_logs
.schema prompts  # view prompt table schema
SELECT * FROM prompts;
```

---

## ⚠️ Important Notes

- **ngrok URL changes** every time you restart ngrok (on the free plan). After restarting ngrok, update `BASE_URL` in your `.env` and restart the app so the Telegram webhook gets re-registered.
- **WhatsApp sandbox** requires you to re-send the join code every 72 hours (Twilio sandbox limitation). For production, upgrade to a Twilio WhatsApp Business number.
- Telegram messages are limited to **4096 characters** — long responses are automatically split.
- WhatsApp messages are limited to **1600 characters** — long responses are automatically split.
- The `.env` file contains sensitive API keys — **never commit it to git**. The `.env.example` file is safe to commit.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
