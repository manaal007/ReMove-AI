import asyncio, os, re, edge_tts

VOICE = "ur-PK-UzmaNeural"
OUT = "assets/audio"

phrases = {
    "raise_higher": "اپنا بازو تھوڑا اور اوپر اٹھائیں",
    "trunk_lean": "اپنا جسم سیدھا رکھیں، آگے نہ جھکیں",
    "good": "بہت اچھے، دوبارہ کوشش کریں",
}

def clean(t):
    return re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", t).strip()

async def make(name, text):
    text = clean(text)
    for attempt in range(3):
        try:
            await edge_tts.Communicate(text, VOICE).save(f"{OUT}/ur_{name}.mp3")
            print("done", name)
            return
        except Exception as e:
            print("retry", name, attempt + 1, repr(text), e)
            await asyncio.sleep(3)
    print("FAILED", name)

async def main():
    os.makedirs(OUT, exist_ok=True)
    for name, text in phrases.items():
        await make(name, text)
        await asyncio.sleep(1)

asyncio.run(main())