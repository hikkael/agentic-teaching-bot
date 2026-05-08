# AUA NLP — Agentic Telegram Teaching Assistant

A Telegram bot that accepts lecture slides (PDF), generates a full lesson plan using a local LLM, finds supporting web resources, and emails the result after user confirmation.

Built for the Natural Language Processing course at the American University of Armenia (AUA).

---

## Features

- Upload lecture slides as PDF via Telegram
- Automatic slide text extraction with page references
- Local LLM-powered lesson plan generation (no cloud API required)
- Web research for supporting educational resources
- Email delivery with preview-before-send confirmation
- Simple session state machine with `/status` visibility

---

## Architecture

```
Telegram Bot API
      │
      ▼
Session State (in-memory, per user)
      │
      ▼
Agent Orchestrator
      ├── Slide Parser      (tools/slides.py)
      ├── Web Search        (tools/web_search.py)
      ├── Email Sender      (tools/email.py)
      └── LLM Backend       (llm_backend.py)
            │
            ▼
      llama_cpp.server (local, OpenAI-compatible API)
            │
            ▼
      Qwen2.5-1.5B-Instruct (GGUF, Q4_K_M quantization)
```

---

## Requirements

- Python 3.10+
- Windows / Linux / macOS
- A Telegram bot token (from [@BotFather](https://t.me/botfather))
- Gmail account with App Password enabled
- ~1 GB disk space for the model

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/agentic-teaching-bot.git
cd agentic-teaching-bot
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Download the model

Download `qwen2.5-1.5b-instruct-q4_k_m.gguf` from:
```
https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/main
```
Save it to a local path, e.g. `E:\models\qwen2.5-1.5b-instruct-q4_k_m.gguf`

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
VLLM_BASE_URL=http://localhost:8000/v1
VLLM_MODEL_NAME=qwen2.5-1.5b-instruct-q4_k_m
EMAIL_SENDER=your@gmail.com
EMAIL_PASSWORD=your_app_password_no_spaces
```

> **Gmail App Password:** Go to `https://myaccount.google.com/apppasswords`, create a password named `aua-bot`, and paste it without spaces into `EMAIL_PASSWORD`.

---

## Running the Bot

### Step 1 — Start the local LLM server (Terminal 1)

```bash
python -m llama_cpp.server \
    --model /path/to/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    --port 8000 \
    --n_ctx 4096
```

Wait for:
```
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 2 — Start the bot (Terminal 2)

```bash
python bot.py
```

---

## Usage

| Command | Description |
|---|---|
| `/start` | Welcome message and example workflow |
| `/help` | List all commands and limitations |
| `/plan <duration> <audience> <language> <email>` | Generate lesson plan from uploaded slides |
| `/research` | Find supporting web resources |
| `/status` | Show current session state and errors |
| `/send` | Preview and email the lesson package |

### Example workflow

1. Open your bot in Telegram
2. Upload a PDF of your lecture slides
3. Run `/plan 90min undergrads English recipient@example.com`
4. Wait for the 5-step workflow to complete (~2-5 min on CPU)
5. Run `/research` to find supporting links
6. Run `/send`, review the preview, reply `YES` to confirm

---

## Model Details

| Property | Value |
|---|---|
| Model | Qwen2.5-1.5B-Instruct |
| Format | GGUF (Q4_K_M quantization) |
| Backend | llama-cpp-python (CPU) |
| Context length | 4096 tokens |
| Server | llama_cpp.server (OpenAI-compatible) |

> **Note:** vLLM was attempted but is not supported on Windows due to missing compiled CUDA extensions. llama-cpp-python was used as the Windows-compatible alternative.

---

## Project Structure

```
agentic-teaching-bot/
├── README.md
├── .env.example
├── .gitignore
├── bot.py                  # Telegram bot, commands, session state
├── llm_backend.py          # LLM client wrapper (generate, health_check)
├── agents/
│   ├── orchestrator.py     # Multi-step workflow pipeline
│   └── prompts.py          # System prompts for each LLM call
├── tools/
│   ├── slides.py           # PDF extraction, chunking, summarization
│   ├── web_search.py       # DuckDuckGo search + LLM justification
│   └── email.py            # Async Gmail SMTP sender
└── examples/
    ├── sample_slides.pdf
    └── sample_output.md
```

---

## Limitations

- PDF only — image-based or scanned slides produce no extracted text
- CPU inference is slow (~2-5 minutes per plan)
- Small model (1.5B) may produce generic or vague plans for complex topics
- DuckDuckGo may rate-limit — retry `/research` if no results appear
- Session state is in-memory and resets when the bot restarts

---

## Citation

- ClaudeAI

---

## Academic Integrity

This project was completed individually as part of the AUA NLP course. Open-source frameworks and AI-assisted code were used and cited. All submitted code, prompts, and report are my own work.