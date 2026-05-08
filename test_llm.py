# test_llm.py
import asyncio
from llm_backend import generate_with_system, health_check

async def test():
    print("Health:", await health_check())
    reply = await generate_with_system(
        system_prompt="You are a helpful teaching assistant.",
        user_prompt="List 3 key concepts in transformer attention.",
        temperature=0.3,
    )
    print(reply)

asyncio.run(test())