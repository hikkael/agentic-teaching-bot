import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Session state ──────────────────────────────────────────────────────────────
# Keyed by user_id (int). Stores everything we need across turns.
sessions: dict[int, dict] = {}

def get_session(user_id: int) -> dict:
    """Return existing session or create a fresh one."""
    if user_id not in sessions:
        sessions[user_id] = {
            "pdf_path": None,       # path to uploaded PDF on disk
            "duration": None,       # e.g. "90 minutes"
            "audience": None,       # e.g. "3rd year CS undergrads"
            "language": "English",  # output language
            "email": None,          # recipient email
            "plan": None,           # generated teaching plan text
            "research": None,       # list of web resources
            "email_body": None,     # drafted email body
            "step": "idle",         # tracks where in the workflow we are
            "errors": [],           # list of error strings
        }
    return sessions[user_id]

# ── /start ─────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello {user.first_name}! I'm your AUA NLP Teaching Assistant.\n\n"
        "I can turn your lecture slides into a full lesson plan, find supporting "
        "resources online, and email the result to anyone you choose.\n\n"
        "📌 *Quick example workflow:*\n"
        "1. Upload a PDF of your slides\n"
        "2. Run /plan and answer a few questions\n"
        "3. Run /research to find supporting links\n"
        "4. Run /send to email the package after previewing it\n\n"
        "Type /help to see all commands.",
        parse_mode="Markdown",
    )

# ── /help ──────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *Available commands:*\n\n"
        "/start — Welcome message and example\n"
        "/help — This message\n"
        "/plan — Generate a lesson plan from uploaded slides\n"
        "/research — Find supporting web resources\n"
        "/status — Show current session state\n"
        "/send — Email the approved package\n\n"
        "⚠️ *Limitations:*\n"
        "• PDF slides only (PPTX not yet supported)\n"
        "• One active session per user\n"
        "• Web search limited to 5 results\n"
        "• Email requires prior /plan run",
        parse_mode="Markdown",
    )

# ── PDF upload handler ─────────────────────────────────────────────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called whenever a user sends a file."""
    session = get_session(update.effective_user.id)
    doc = update.message.document

    # Validate file type
    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text(
            "❌ Only PDF files are supported right now. Please upload a .pdf file."
        )
        return

    await update.message.reply_text("⏳ Downloading your slides...")

    # Download file from Telegram's servers to local disk
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{update.effective_user.id}_{doc.file_name}"
    tg_file = await context.bot.get_file(doc.file_id)
    await tg_file.download_to_drive(file_path)

    session["pdf_path"] = file_path
    session["step"] = "pdf_uploaded"

    await update.message.reply_text(
        f"✅ Got it! *{doc.file_name}* is ready.\n\n"
        "Now run /plan to generate your lesson package.",
        parse_mode="Markdown",
    )

# ── /plan ──────────────────────────────────────────────────────────────────────
async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_user.id)

    if not session["pdf_path"]:
        await update.message.reply_text(
            "📎 Please upload a PDF of your slides first, then run /plan."
        )
        return

    # Collect parameters from command args, e.g. /plan 90 "CS undergrads" English
    args = context.args  # list of words after the command
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: `/plan <duration> <audience> <language> <email>`\n\n"
            "Example:\n`/plan 90min undergrads English alice@example.com`",
            parse_mode="Markdown",
        )
        return

    session["duration"] = args[0]
    session["audience"] = args[1]
    session["language"] = args[2]
    session["email"] = args[3] if len(args) >= 4 else None
    session["step"] = "planning"

    await update.message.reply_text(
        f"🧠 Running the full lesson-planning workflow...\n\n"
        f"• Duration: {session['duration']}\n"
        f"• Audience: {session['audience']}\n"
        f"• Language: {session['language']}\n"
        f"• Email: {session['email'] or 'not set'}\n\n"
        "This may take a minute ⏳"
    )

    # Import here to avoid circular imports
    from agents.orchestrator import run_plan_workflow
    result = await run_plan_workflow(session, update, context)

    if result:
        session["plan"] = result
        session["step"] = "plan_ready"
        await update.message.reply_text(
            "✅ Plan generated! Here's the preview:\n\n"
            f"{result[:3000]}"  # Telegram has a 4096-char limit per message
            "\n\n📌 Run /research to find supporting links, or /send to email this.",
        )
    else:
        session["step"] = "error"
        await update.message.reply_text(
            "❌ Something went wrong generating the plan. Run /status to see errors."
        )

# ── /research ──────────────────────────────────────────────────────────────────
async def research(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_user.id)

    if not session["plan"]:
        await update.message.reply_text(
            "⚠️ Run /plan first so I know what topic to research."
        )
        return

    await update.message.reply_text("🔍 Searching the web for supporting resources...")

    from agents.orchestrator import run_research_workflow
    links = await run_research_workflow(session)

    if links:
        session["research"] = links
        formatted = "\n\n".join(
            f"🔗 *{r['title']}*\n{r['url']}\n_{r['justification']}_"
            for r in links
        )
        await update.message.reply_text(
            f"📚 Found {len(links)} resources:\n\n{formatted}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Web search returned no results. Try again later.")

# ── /status ────────────────────────────────────────────────────────────────────
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_user.id)
    errors = "\n".join(session["errors"]) if session["errors"] else "None"
    await update.message.reply_text(
        f"📊 *Session Status*\n\n"
        f"• Step: `{session['step']}`\n"
        f"• PDF: `{session['pdf_path'] or 'none'}`\n"
        f"• Duration: `{session['duration'] or 'not set'}`\n"
        f"• Audience: `{session['audience'] or 'not set'}`\n"
        f"• Language: `{session['language']}`\n"
        f"• Email: `{session['email'] or 'not set'}`\n"
        f"• Plan ready: `{'yes' if session['plan'] else 'no'}`\n"
        f"• Research ready: `{'yes' if session['research'] else 'no'}`\n"
        f"• Errors: {errors}",
        parse_mode="Markdown",
    )

# ── /send ──────────────────────────────────────────────────────────────────────
async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_user.id)

    if not session["plan"]:
        await update.message.reply_text("⚠️ No plan to send yet. Run /plan first.")
        return
    if not session["email"]:
        await update.message.reply_text(
            "⚠️ No recipient email. Re-run /plan with an email address as the 4th argument."
        )
        return

    # Build and show email preview BEFORE sending
    from agents.orchestrator import build_email_body
    email_body = build_email_body(session)
    session["email_body"] = email_body

    preview = (
        f"📧 Email Preview — sending to: {session['email']}\n\n"
        f"{email_body[:3000]}\n\n"
        "Reply YES to confirm and send, or anything else to cancel."
    )
    await update.message.reply_text(preview)
    session["step"] = "awaiting_confirmation"
    logger.info(f"Step set to awaiting_confirmation for user {update.effective_user.id}")

# ── Text message handler (used for email confirmation) ─────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = get_session(update.effective_user.id)

    if session["step"] == "awaiting_confirmation":
        if update.message.text.strip().upper() == "YES":
            await update.message.reply_text("📨 Sending email...")
            from tools.email import send_email
            ok = await send_email(
                to=session["email"],
                subject="Your Lesson Plan from AUA Teaching Assistant",
                body=session["email_body"],
            )
            if ok:
                session["step"] = "email_sent"
                await update.message.reply_text("✅ Email sent successfully!")
            else:
                session["step"] = "error"
                await update.message.reply_text("❌ Failed to send email. Check /status.")
        else:
            session["step"] = "plan_ready"
            await update.message.reply_text("🚫 Send cancelled. The plan is still saved.")
    else:
        await update.message.reply_text(
            "I only understand commands. Type /help to see what's available."
        )

# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = ApplicationBuilder().token(token).build()

    # Register handlers — order matters for MessageHandler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("plan", plan))
    app.add_handler(CommandHandler("research", research))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("send", send))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot is running...")
    app.run_polling()  # blocking loop

if __name__ == "__main__":
    main()