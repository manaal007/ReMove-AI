"""
Generate feedback audio (Urdu + English) with edge-tts.

Phrases come from feedback/messages.py so text and audio never drift apart.
Output: assets/audio/{lang}_{phrase}.mp3

Both languages use a female neural voice with a Pakistani / South Asian accent
so the app sounds like the same speaker in either language.

Run from inside remove-pk (needs internet):
    python scripts/make_audio.py                 # only makes files that are missing
    python scripts/make_audio.py --force         # remake every file
    python scripts/make_audio.py --lang en       # one language only
"""
import argparse
import asyncio
import os
import re
import sys

import edge_tts

sys.path.insert(0, os.getcwd())
from feedback.messages import AUDIO_DIR, LANGS, PHRASES  # noqa: E402

VOICES = {
    "ur": "ur-PK-UzmaNeural",
    "en": "en-IN-NeerjaNeural",
}


def clean(t):
    """Strip invisible direction marks that make edge-tts fail on Urdu text."""
    return re.sub(r"[‎‏‪-‮⁦-⁩﻿]", "", t).strip()


async def make(lang, name, text):
    out = AUDIO_DIR / f"{lang}_{name}.mp3"
    text = clean(text)
    for attempt in range(3):
        try:
            await edge_tts.Communicate(text, VOICES[lang]).save(str(out))
            print("done", out.name)
            return True
        except Exception as e:
            print("retry", out.name, attempt + 1, repr(text), e)
            await asyncio.sleep(3)
    print("FAILED", out.name)
    return False


async def main(langs, force):
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for lang in langs:
        for name, texts in PHRASES.items():
            if not force and (AUDIO_DIR / f"{lang}_{name}.mp3").exists():
                print("skip", f"{lang}_{name}.mp3", "(exists, use --force to remake)")
                continue
            if not await make(lang, name, texts[lang]):
                failed.append(f"{lang}_{name}")
            await asyncio.sleep(1)
    if failed:
        print("\nFailed:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=LANGS, help="only this language")
    ap.add_argument("--force", action="store_true", help="remake files that already exist")
    args = ap.parse_args()
    asyncio.run(main([args.lang] if args.lang else list(LANGS), args.force))
