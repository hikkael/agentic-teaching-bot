import logging
from ddgs import DDGS
from llm_backend import generate_with_system

logger = logging.getLogger(__name__)


async def search_resources(query: str, max_results: int = 5) -> list[dict]:
    """
    Search DuckDuckGo for educational resources on the given query.
    For each result, ask the LLM to write a short justification.

    Returns a list of dicts:
        [{"title": ..., "url": ..., "justification": ...}, ...]
    """
    raw_results = []

    try:
        # DDGS is synchronous — runs fine here since it's fast
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                raw_results.append({
                    "title": r.get("title", "No title"),
                    "url":   r.get("href", ""),
                    "body":  r.get("body", ""),
                })
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []

    if not raw_results:
        logger.warning("Search returned no results.")
        return []

    # Ask LLM to write a justification for each result
    enriched = []
    for r in raw_results:
        if not r["url"]:
            continue

        justification = await _justify_resource(query, r["title"], r["body"])
        enriched.append({
            "title":         r["title"],
            "url":           r["url"],
            "justification": justification or "Relevant to the lecture topic.",
        })

    logger.info(f"Returning {len(enriched)} enriched search results.")
    return enriched


async def _justify_resource(query: str, title: str, snippet: str) -> str | None:
    """
    Ask the LLM why this resource is useful for the given topic.
    Keeps justifications grounded and avoids hallucinated URLs.
    """
    user = (
        f"Lecture topic: {query}\n"
        f"Resource title: {title}\n"
        f"Resource snippet: {snippet[:300]}\n\n"
        f"In one sentence, explain why this resource would be useful "
        f"for a student learning about this topic."
    )
    return await generate_with_system(
        "You write concise, honest justifications for educational resources.",
        user,
        temperature=0.3,
        max_tokens=80,
    )