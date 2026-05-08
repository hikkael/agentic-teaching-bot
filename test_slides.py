# test_slides.py
import asyncio
from tools.slides import extract_slides, summarize_slides

async def test():
    slides = extract_slides("uploads/1723648800_Lecture2_AutoDiff_annotated.pdf")
    print(f"Slides extracted: {len(slides)}")
    if slides:
        print("First slide preview:")
        print(slides[0]["text"][:300])
    else:
        print("NO SLIDES EXTRACTED - PDF might be image-based")
        return

    print("\nCalling LLM...")
    summary = await summarize_slides(slides)
    print("Summary:", summary)

asyncio.run(test())