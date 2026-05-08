import os
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Client setup ───────────────────────────────────────────────────────────────
# AsyncOpenAI speaks the OpenAI API protocol, but we point it at our local vLLM
# server instead of api.openai.com. No real OpenAI key is needed.
_client = AsyncOpenAI(
    base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
    api_key="not-needed",  # vLLM doesn't check this, but the client requires a value
)

MODEL = os.getenv("VLLM_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.2")

# ── Core generation function ───────────────────────────────────────────────────
async def generate(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str | None:
    """
    Send a list of messages to the local vLLM server and return the reply text.

    Args:
        messages: OpenAI-format message list, e.g.
                  [{"role": "system", "content": "..."}, 
                   {"role": "user",   "content": "..."}]
        temperature: 0.0 = deterministic, 1.0 = creative. Use ~0.3 for plans.
        max_tokens:  Hard cap on response length.

    Returns:
        The assistant's reply as a plain string, or None if the call fails.
    """
    try:
        response = await _client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


# ── Convenience wrappers ───────────────────────────────────────────────────────
async def generate_with_system(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str | None:
    """Shorthand for the common system + user message pattern."""
    return await generate(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def health_check() -> bool:
    """
    Ping the vLLM server. Returns True if it's reachable and responding.
    Call this at bot startup so the user gets a clear error early.
    """
    try:
        models = await _client.models.list()
        available = [m.id for m in models.data]
        logger.info(f"vLLM is up. Available models: {available}")
        if MODEL not in available:
            logger.warning(
                f"Configured model '{MODEL}' not found in vLLM. "
                f"Available: {available}"
            )
        return True
    except Exception as e:
        logger.error(f"vLLM health check failed: {e}")
        return False