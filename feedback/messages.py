"""
Feedback phrases (Urdu + English) and the audio file for each.

Single source of truth: the app reads text from here, and
scripts/make_audio.py generates the mp3 files from the same phrases.

Two kinds of keys:
  - rep labels   : the six labels from the labeling guide, one per scored rep
  - prompts      : session messages that are not about a single rep

Some rep labels share an audio clip with a differently named phrase
(reduced_range -> raise_higher, trunk_compensation -> trunk_lean), so the
phrase key and the label are kept separate.
"""
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"
LANGS = ("ur", "en")

REP_LABELS = ("good", "reduced_range", "too_fast", "jerky",
              "trunk_compensation", "not_tracked")
PROMPTS = ("step_back", "come_closer", "too_dark", "too_bright", "start", "rest", "set_done",
           "adjust_position")

# rep label -> phrase key (labels not listed use their own name)
LABEL_TO_PHRASE = {
    "reduced_range": "raise_higher",
    "trunk_compensation": "trunk_lean",
}

PHRASES = {
    # --- rep feedback ---
    "good": {
        "en": "Very good, do the next rep.",
        "ur": "بہت اچھے، اگلا ریپ کریں",
    },
    "raise_higher": {
        "en": "Raise your arm a little higher.",
        "ur": "اپنا بازو تھوڑا اور اوپر اٹھائیں",
    },
    "too_fast": {
        "en": "Slow down, raise your arm gently.",
        "ur": "آہستہ کریں، بازو آرام سے اٹھائیں",
    },
    "jerky": {
        "en": "Move your arm smoothly, without jerks.",
        "ur": "بازو کو آرام سے اور ہموار طریقے سے حرکت دیں",
    },
    "trunk_lean": {
        "en": "Keep your body straight, don't lean to the side.",
        "ur": "سیدھے کھڑے رہیں، ایک طرف نہ جھکیں",
    },
    "not_tracked": {
        "en": "I cannot see you clearly. Please stand in front of the camera.",
        "ur": "آپ صاف نظر نہیں آ رہے، کیمرے کے سامنے کھڑے ہوں",
    },
    # --- session prompts ---
    "step_back": {
        "en": "Step back a little so your whole body is visible.",
        "ur": "تھوڑا پیچھے ہٹیں تاکہ آپ کا پورا جسم نظر آئے",
    },
    "come_closer": {
        "en": "Come a little closer to the camera.",
        "ur": "کیمرے کے تھوڑا قریب آئیں",
    },
    "too_bright": {
        "en": "There is too much light behind you. Turn the camera away from the window.",
        "ur": "پیچھے روشنی بہت زیادہ ہے، کیمرے کا رخ کھڑکی سے ہٹا دیں",
    },
    "too_dark": {
        "en": "The room is too dark. Please turn on more light.",
        "ur": "کمرے میں روشنی کم ہے، براہ کرم روشنی بڑھائیں",
    },
    "start": {
        "en": "Get ready. You can start now.",
        "ur": "تیار ہو جائیں، اب شروع کریں",
    },
    "rest": {
        "en": "Take a short rest.",
        "ur": "تھوڑا آرام کر لیں",
    },
    "adjust_position": {
        "en": "Please adjust your position and try again.",
        "ur": "براہ کرم اپنی جگہ ٹھیک کریں اور دوبارہ کوشش کریں",
    },
    "set_done": {
        "en": "Well done, this set is complete.",
        "ur": "شاباش، یہ سیٹ مکمل ہو گیا",
    },
}


def phrase_key(key):
    """Map a rep label or prompt to its phrase key."""
    return LABEL_TO_PHRASE.get(key, key)


def audio_path(key, lang="ur"):
    return AUDIO_DIR / f"{lang}_{phrase_key(key)}.mp3"


def get_feedback(key, lang="ur"):
    """Return (text, audio_path) for a rep label, phrase key or prompt."""
    if lang not in LANGS:
        raise ValueError(f"Unknown language {lang!r}, expected one of {LANGS}")
    pk = phrase_key(key)
    if pk not in PHRASES:
        raise KeyError(f"No phrase for {key!r}")
    return PHRASES[pk][lang], audio_path(key, lang)
