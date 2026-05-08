# Design Report: Agentic Telegram Teaching Assistant
**Course:** Natural Language Processing — American University of Armenia (AUA)  
**Student:** Mikayel Hambaryan
**Date:** May 2026

---

## 1. Overview

This project implements a small but complete LLM-powered application: a Telegram bot that accepts lecture slides in PDF format, generates a structured lesson plan using a locally-running language model, finds supporting educational resources on the web, and delivers the final package by email after explicit user confirmation.

The focus of the design was on reliability, clarity, and practical tool integration rather than model size or complexity. A simple finite-state session model was chosen over frameworks like LangGraph or LlamaIndex, because the workflow is linear and deterministic — a state machine is easier to debug and reason about for this use case.

---

## 2. Architecture

The system consists of five main components that communicate through a central orchestrator:

```
Telegram Bot API
      │
      ▼
Session State (in-memory dict, keyed by user_id)
      │
      ▼
Agent Orchestrator (agents/orchestrator.py)
      ├── Slide Parser      (tools/slides.py)
      ├── Web Search        (tools/web_search.py)
      ├── Email Sender      (tools/email.py)
      └── LLM Backend       (llm_backend.py)
                │
                ▼
         llama_cpp.server
                │
                ▼
     Qwen2.5-1.5B-Instruct (GGUF Q4_K_M)
```

### Session State Machine

Each user has an independent session dictionary that tracks their current step in the workflow. The `step` field acts as a simple state machine:

```
idle → pdf_uploaded → planning → plan_ready → awaiting_confirmation → email_sent
```

This design makes the `/status` command trivially easy to implement and makes debugging straightforward — the current state is always visible and explicit.

### Agent Orchestrator

The orchestrator (`agents/orchestrator.py`) runs the full pipeline in sequence:

1. Extract and chunk slide text
2. Summarize slides and build a concept map (LLM call)
3. Generate a timed teaching plan (LLM call)
4. Revise the plan for quality and realism (LLM call)
5. Optionally run web research (separate `/research` command)
6. Build and send email after user confirmation

Each step sends a progress message to the Telegram user so they are never waiting in silence.

---

## 3. Local LLM Backend

### Model Choice

| Property | Value |
|---|---|
| Model | Qwen2.5-1.5B-Instruct |
| Format | GGUF (Q4_K_M quantization) |
| Backend | llama-cpp-python (CPU) |
| Context length | 4096 tokens |
| Quantization | 4-bit (Q4_K_M) — ~4x size reduction, minimal quality loss |

Qwen2.5-1.5B-Instruct was chosen because it is small enough to run on CPU within a reasonable time (~2-5 minutes per plan), follows instructions reliably for its size, and is available in GGUF format which llama-cpp-python supports natively on Windows.

### Why Not vLLM

vLLM was the original backend choice as it offers significantly faster inference via continuous batching and PagedAttention. However, vLLM relies on compiled CUDA extensions (`vllm._C`) that are only built for Linux. On Windows, the package installs but fails at runtime with `ModuleNotFoundError: No module named 'vllm._C'`. WSL2 would resolve this but I was not able to install it correctly . llama-cpp-python was used as the Windows-native alternative.

### Backend Wrapper

The LLM backend is wrapped behind a single `generate(messages, temperature, max_tokens)` function in `llm_backend.py`. This means the rest of the codebase is completely decoupled from the backend — switching from llama.cpp to vLLM or any other OpenAI-compatible server requires changing only the `VLLM_BASE_URL` environment variable.

### Context Window Management

The model's 4096-token context window (input + output combined) required careful prompt sizing. Slide text is capped at 300 characters per slide and only a sample of slides is sent per LLM call. Output tokens are capped at 300-600 depending on the task. This prevents context length errors while keeping responses focused.

---

## 4. Prompts

Three system prompts are defined in `agents/prompts.py`, each tuned for a specific task.

### Teaching Plan Prompt

```
You are an expert university lecturer and curriculum designer.
Your job is to create detailed, practical, and realistic lesson plans.

Rules:
- Always include slide references like [Slide N] when mentioning content
- Keep timing realistic — don't cram too much into short slots
- Write exercises that are concrete and doable in the given time
- Use clear headings and structure
- Write in the language specified by the user
```

**Design choices:** Low temperature (0.4) for structured output. The slide reference rule directly serves the assignment's grounding requirement. The timing realism rule was added after observing the model produce 5-minute slots for complex topics in early testing.

### Revision Prompt

```
You are a senior curriculum reviewer. Your job is to improve lesson plans.

Check for and fix:
- Unrealistic timing
- Vague objectives
- Missing exercise instructions
- Poor flow between sections
- Claims not grounded in the slide content
```

**Design choices:** A separate revision pass catches issues the generation step misses. Temperature is set to 0.3 (lower than generation) to make corrections conservative rather than creative. If the LLM call fails, the original plan is returned unchanged — the revision step degrades gracefully.

### Web Search Justification Prompt

For each search result, the LLM writes a one-sentence justification explaining why the resource is relevant to the lecture topic. This prevents the bot from returning raw search snippets and ensures every link has a clear pedagogical reason.

---

## 5. Tools

### Slide Parser (`tools/slides.py`)

PyMuPDF (`fitz`) extracts text from each PDF page. Pages are tagged with `[Slide N]` markers before being passed to the LLM, which allows the model to reference specific slides in its output. Text is chunked to fit within the context window, with a soft limit of 6000 characters per chunk. Image-based slides (where no text is extractable) are skipped with a log warning.

### Web Search (`tools/web_search.py`)

DuckDuckGo search is performed via the `ddgs` library (no API key required). The search query itself is generated by the LLM from the lesson plan, rather than being hardcoded — this produces more precise queries for diverse lecture topics. Each result is enriched with an LLM-generated justification before being returned to the user.

### Email Sender (`tools/email.py`)

Email is sent via Gmail SMTP using `aiosmtplib` (async). Credentials are loaded from environment variables — no secrets are hardcoded. The bot always shows a full email preview before sending and requires the user to reply `YES` to confirm. This explicit confirmation step is a core safety feature of the design.

---

## 6. Evaluation

### Test Case 1 — Normal Flow (Happy Path)

**Input:** `Lecture2_AutoDiff_annotated.pdf`, `/plan 30min undergrads English recipient@gmail.com`  
**Expected:** Full plan generated, research found, email delivered  
**Result:** ✅ Pass. Plan generated in ~3 minutes on CPU. 5 web resources returned. Email delivered to Gmail inbox.

### Test Case 2 — Invalid File Type

**Input:** User uploads a `.txt` file instead of PDF  
**Expected:** Clear error message, no crash  
**Result:** ✅ Pass. Bot responds: "❌ Only PDF files are supported right now."

### Test Case 3 — Missing Email Argument

**Input:** `/plan 30min undergrads English` (no email address)  
**Expected:** Warning message asking for email, no crash  
**Result:** ✅ Pass. Bot stores `email: None` and warns when `/send` is called: "⚠️ No recipient email. Re-run /plan with an email address as the 4th argument."

### Test Case 4 — Failed Web Search

**Input:** `/research` when DuckDuckGo rate-limits  
**Expected:** Graceful error message, no crash  
**Result:** ✅ Pass. Bot responds: "❌ Web search returned no results. Try again later."

### Latency

| Step | Approximate time (CPU) |
|---|---|
| Slide extraction | < 1 second |
| Summarization | 30-60 seconds |
| Concept map | 30-60 seconds |
| Teaching plan | 60-90 seconds |
| Revision | 60-90 seconds |
| Web search | 2-5 seconds |
| Email send | < 2 seconds |
| **Total** | **~3-5 minutes** |

---

## 7. Limitations

**Image-based PDFs:** PyMuPDF can only extract text from text-based PDFs. Scanned slides or slides exported as images produce no extractable content. OCR integration (e.g. via `pytesseract`) would address this.

**CPU inference speed:** Without GPU acceleration, each plan takes 3-5 minutes. On a GPU with vLLM on Linux, this would reduce to under 30 seconds.

**Small model quality:** At 1.5B parameters, Qwen2.5 produces functional but sometimes generic lesson plans. A 7B model would produce noticeably better structured output and more specific exercises.

**In-memory sessions:** Session state is stored in a Python dictionary and is lost when the bot restarts. A persistent store (SQLite or Redis) would fix this.

**Single-user testing:** The bot was tested with a single user. Concurrent users sharing the same process could experience session conflicts under high load.

---

## 8. References

- Qwen2.5 model: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
- llama-cpp-python: https://github.com/abetlen/llama-cpp-python
- python-telegram-bot: https://python-telegram-bot.org
- PyMuPDF: https://pymupdf.readthedocs.io
- ddgs (DuckDuckGo Search): https://github.com/deedy5/ddgs
- ArmLLM Agents materials: https://github.com/osoblanco/ArmLLM/tree/main/2025/Agents