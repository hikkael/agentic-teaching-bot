import logging
from telegram import Update
from telegram.ext import ContextTypes

from llm_backend import generate_with_system
from tools.slides import extract_slides, summarize_slides, extract_concepts
from tools.web_search import search_resources
from agents.prompts import TEACHING_PLAN_SYSTEM, REVISION_SYSTEM, EMAIL_SYSTEM

logger = logging.getLogger(__name__)


# ── Helper: send a status update to the user mid-workflow ─────────────────────
async def _notify(update: Update, text: str) -> None:
    """Send a progress message to the Telegram user."""
    try:
        await update.message.reply_text(text)
    except Exception as e:
        logger.warning(f"Could not send progress update: {e}")


# ── Step 1-2: Slide ingestion + summarization ──────────────────────────────────
async def _ingest_slides(session: dict, update: Update) -> tuple[list, str, str] | None:
    """
    Extract slides, summarize them, and build a concept map.
    Returns (slides, summary, concepts) or None on failure.
    """
    await _notify(update, "📄 Step 1/5 — Extracting slide content...")
    slides = extract_slides(session["pdf_path"])

    if not slides:
        session["errors"].append("Could not extract text from PDF.")
        return None

    await _notify(update, "🧠 Step 2/5 — Summarizing and mapping concepts...")
    summary = await summarize_slides(slides)
    concepts = await extract_concepts(slides)

    if not summary or not concepts:
        session["errors"].append("LLM failed to summarize slides.")
        return None

    return slides, summary, concepts


# ── Step 3: Teaching plan generation ──────────────────────────────────────────
async def _generate_plan(
    session: dict,
    summary: str,
    concepts: str,
    update: Update,
) -> str | None:
    """Generate a full timed teaching plan from the slide summary."""
    await _notify(update, "📝 Step 3/5 — Generating teaching plan...")

    user_prompt = (
        f"Lecture summary:\n{summary}\n\n"
        f"Key concepts:\n{concepts}\n\n"
        f"Duration: {session['duration']}\n"
        f"Target audience: {session['audience']}\n"
        f"Output language: {session['language']}\n\n"
        "Create a detailed, timed lesson plan with:\n"
        "- Clear learning objectives (3-5 bullet points)\n"
        "- Timed sections that add up to the total duration\n"
        "- At least one hands-on exercise with instructions\n"
        "- A recap/summary section\n"
        "- Slide references where relevant (e.g. [Slide 3])\n"
    )

    plan = await generate_with_system(
        TEACHING_PLAN_SYSTEM,
        user_prompt,
        temperature=0.4,
        max_tokens=600,
    )
    return plan


# ── Step 4: Web research ───────────────────────────────────────────────────────
async def run_research_workflow(session: dict) -> list[dict] | None:
    """
    Search the web for resources relevant to the lecture topic.
    Called separately by /research command.
    Returns a list of {title, url, justification} dicts.
    """
    if not session.get("plan"):
        return None

    # Extract topic keywords from the plan using the LLM
    topic_prompt = (
        f"From this lesson plan, extract a 2-4 word search query "
        f"for finding educational resources. "
        f"Reply with ONLY the query words, no punctuation, no explanation.\n\n"
        f"Example good outputs: 'automatic differentiation tutorial', "
        f"'backpropagation neural networks', 'gradient descent explained'\n\n"
        f"{session['plan'][:500]}\n\n"
        f"Query:"
    )
    query = await generate_with_system(
        "You extract concise search queries from educational content.",
        topic_prompt,
        temperature=0.1,
        max_tokens=32,
    )

    if not query:
        return None

    query = query.strip().strip('"')
    logger.info(f"Web search query: {query}")

    results = await search_resources(query)
    return results


# ── Step 5: Revision ───────────────────────────────────────────────────────────
async def _revise_plan(plan: str, update: Update) -> str:
    """
    Ask the LLM to review and improve the plan for clarity and realism.
    If revision fails, return the original plan unchanged.
    """
    await _notify(update, "🔍 Step 4/5 — Revising plan for quality...")

    revised = await generate_with_system(
        REVISION_SYSTEM,
        f"Please review and improve this lesson plan:\n\n{plan[:800]}",
        temperature=0.3,
        max_tokens=600,
    )
    return revised if revised else plan  # fall back to original if LLM fails


# ── Email body builder ─────────────────────────────────────────────────────────
def build_email_body(session: dict) -> str:
    """
    Assemble the final email body from all session components.
    Called synchronously — no LLM needed here.
    """
    research_section = ""
    if session.get("research"):
        links = "\n".join(
            f"- {r['title']}: {r['url']}\n  {r['justification']}"
            for r in session["research"]
        )
        research_section = f"\n\n## Supporting Resources\n{links}"

    return (
        f"Dear colleague,\n\n"
        f"Please find below the AI-generated lesson plan prepared by the "
        f"AUA NLP Teaching Assistant.\n\n"
        f"---\n\n"
        f"{session['plan']}"
        f"{research_section}\n\n"
        f"---\n\n"
        f"This package was generated from uploaded lecture slides.\n"
        f"Duration: {session['duration']} | Audience: {session['audience']} | "
        f"Language: {session['language']}\n\n"
        f"Best regards,\nAUA NLP Teaching Assistant"
    )


# ── Main workflow entry point ──────────────────────────────────────────────────
async def run_plan_workflow(
    session: dict,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str | None:
    """
    Full pipeline: ingest → plan → revise.
    Returns the final plan text, or None on failure.
    """
    # Step 1-2: Ingest slides
    result = await _ingest_slides(session, update)
    if not result:
        return None
    slides, summary, concepts = result

    # Store summary in session for reference
    session["summary"] = summary
    session["concepts"] = concepts

    # Step 3: Generate plan
    plan = await _generate_plan(session, summary, concepts, update)
    if not plan:
        session["errors"].append("LLM failed to generate teaching plan.")
        return None

    # Step 4 (of 5): Revise plan
    plan = await _revise_plan(plan, update)

    await _notify(update, "✅ Step 5/5 — Done!")
    return plan