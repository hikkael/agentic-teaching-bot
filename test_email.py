# test_email.py
import asyncio
from tools.email import send_email

async def test():
    ok = await send_email(
        to="mi.hambaryan@gmail.com",
        subject="Test from AUA bot",
        body="If you see this, email works!",
    )
    print("Success:", ok)

asyncio.run(test())