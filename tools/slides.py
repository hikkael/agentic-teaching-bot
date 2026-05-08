import logging
import fitz  # PyMuPDF
from llm_backend import generate_with_system

logger = logging.getLogger(__name__)

# ── PDF Extraction ─────────────────────────────────────────────────────────────
def extract_slides(pdf_path: str) -> list[dict]:
    """
    Extract text from each page of a PDF.

    Returns a list of dicts like:
        [{"page": 1, "text": "Introduction to NLP..."}, ...]

    Pages with no text (e.g. pure image slides) are skipped.
    """
    slides = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                slides.append({"page": i, "text": text})
            else:
                logger.info(f"Page {i} has no extractable text — skipping.")
        doc.close()
    except Exception as e:
        logger.error(f"Failed to open PDF: {e}")
        return []

    logger.info(f"Extracted text from {len(slides)} pages out of {i} total.")
    return slides


# ── Chunking ───────────────────────────────────────────────────────────────────
def chunk_slides(slides: list[dict], max_chars: int = 6000) -> list[str]:
    """
    Group slide texts into chunks that fit within the LLM context window.

    Each chunk is a plain string with [Slide N] markers so the LLM
    knows where content came from.

    Args:
        slides:    Output from extract_slides()
        max_chars: Soft limit per chunk. 6000 chars ≈ ~1500 tokens,
                   safe for a 4096-token context window after the prompt.
    """
    chunks = []
    current_chunk = ""

    for slide in slides:
        entry = f"[Slide {slide['page']}]\n{slide['text']}\n\n"
        if len(current_chunk) + len(entry) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = entry
        else:
            current_chunk += entry

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    logger.info(f"Slides chunked into {len(chunks)} chunk(s).")
    return chunks


# ── Summarization ──────────────────────────────────────────────────────────────
async def summarize_slides(slides: list[dict]) -> str | None:
    """
    Ask the LLM to summarize the lecture content and identify the main topic.
    Uses only the first 3 slides to stay within the 2048 token context limit.
    """
    if not slides:
        return None

    # Only use first 3 slides and cap at 800 chars to stay well within context
    sample = slides[:3]
    slide_text = "\n\n".join(
        f"[Slide {s['page']}]\n{s['text'][:300]}" for s in sample
    )

    system = "You are a concise teaching assistant. Keep all responses brief."
    user = (
        f"Lecture slides sample:\n\n{slide_text}\n\n"
        "In 3-4 sentences total:\n"
        "1. Main topic\n"
        "2. Key concepts (comma separated)\n"
        "3. Prerequisites\n"
    )

    result = await generate_with_system(system, user, temperature=0.3, max_tokens=300)
    return result


# ── Concept Map ────────────────────────────────────────────────────────────────
async def extract_concepts(slides: list[dict]) -> str | None:
    """
    Extract the main concepts from a small sample of slides.
    Kept short to fit within the 2048 token context window.
    """
    if not slides:
        return None

    # Sample every 4th slide to get coverage without exceeding context
    sampled = slides[::4][:4]
    slide_text = "\n\n".join(
        f"[Slide {s['page']}]\n{s['text'][:250]}" for s in sampled
    )

    system = "You are a concise curriculum designer."
    user = (
        f"Slides:\n\n{slide_text}\n\n"
        "List 4-6 main concepts as a numbered list. "
        "One line each: concept name and one-sentence definition only."
    )

    result = await generate_with_system(system, user, temperature=0.3, max_tokens=300)
    return result