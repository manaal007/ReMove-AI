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

The six labels are the same for every exercise, but the words are not: an
exercise can map a label or prompt to its own phrase with `phrases:` in
config/exercises.yaml (E4 reduced_range -> straighten_more). Pass that map as
`phrases` to phrase_key / audio_path / get_feedback.
"""
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"
LANGS = ("ur", "en")

REP_LABELS = ("good", "reduced_range", "too_fast", "jerky",
              "trunk_compensation", "not_tracked")
PROMPTS = ("step_back", "come_closer", "too_dark", "too_bright", "start", "rest", "set_done",
           "adjust_position", "turn_sideways", "show_left_side", "show_right_side",
           "weight_ask_none", "weight_ask_light", "weight_ask_heavy",
           # weight guidance after the set (session/weight_advice.py)
           "weight_up_light", "weight_up_heavy", "weight_down_light", "weight_down_none",
           "weight_stay", "weight_stay_one_more", "weight_at_max", "talk_to_physio")

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
    # --- rep feedback, E3 elbow curl ---
    "bend_more": {
        "en": "Bend your elbow a little more.",
        "ur": "کہنی تھوڑی اور موڑیں",
    },
    "too_fast_elbow": {
        "en": "Slow down, bend and straighten your arm gently.",
        "ur": "آہستہ کریں، بازو آرام سے موڑیں اور سیدھا کریں",
    },
    "upper_arm_still": {
        "en": "Keep your upper arm still, close to your body.",
        "ur": "بازو کا اوپر والا حصہ جسم کے ساتھ ساکن رکھیں",
    },
    # --- rep feedback, E4 seated knee extension ---
    "straighten_more": {
        "en": "Straighten your knee a little more.",
        "ur": "گھٹنا تھوڑا اور سیدھا کریں",
    },
    "too_fast_knee": {
        "en": "Slow down, move your leg gently.",
        "ur": "آہستہ کریں، ٹانگ آرام سے ہلائیں",
    },
    "jerky_leg": {
        "en": "Move your leg smoothly, without jerks.",
        "ur": "ٹانگ کو آرام سے اور ہموار طریقے سے حرکت دیں",
    },
    "sit_straight": {
        "en": "Sit up straight, don't lean back.",
        "ur": "سیدھے بیٹھیں، پیچھے نہ جھکیں",
    },
    "not_tracked_leg": {
        "en": "I cannot see your leg clearly. Sit where the camera can see your whole leg.",
        "ur": "آپ کی ٹانگ صاف نظر نہیں آ رہی، ایسی جگہ بیٹھیں جہاں کیمرہ پوری ٹانگ دیکھ سکے",
    },
    # --- session prompts ---
    "step_back": {
        "en": "Step back a little so your whole body is visible.",
        "ur": "تھوڑا پیچھے ہٹیں تاکہ آپ کا پورا جسم نظر آئے",
    },
    "turn_sideways": {
        "en": "Turn sideways, so the side you are exercising faces the camera.",
        "ur": "پہلو کے بل مڑیں، تاکہ ورزش والی سائیڈ کیمرے کی طرف ہو",
    },
    "show_left_side": {
        "en": "Please turn so your left side faces the camera.",
        "ur": "براہ کرم مڑیں تاکہ آپ کا بایاں پہلو کیمرے کی طرف ہو",
    },
    "show_right_side": {
        "en": "Please turn so your right side faces the camera.",
        "ur": "براہ کرم مڑیں تاکہ آپ کا دایاں پہلو کیمرے کی طرف ہو",
    },
    "move_chair_back": {
        "en": "Move the chair or the camera back, so your whole body and leg are visible.",
        "ur": "کرسی یا کیمرہ تھوڑا پیچھے کریں، تاکہ پورا جسم اور ٹانگ نظر آئے",
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
    # --- weight check, before calibration (E3 / E4) ---
    "weight_ask_none": {
        "en": "We see: no weight. Is that right?",
        "ur": "ہمیں لگتا ہے: کوئی وزن نہیں۔ کیا یہ درست ہے؟",
    },
    "weight_ask_light": {
        "en": "We see: a light weight. Is that right?",
        "ur": "ہمیں لگتا ہے: ہلکا وزن۔ کیا یہ درست ہے؟",
    },
    "weight_ask_heavy": {
        "en": "We see: a heavy weight. Is that right?",
        "ur": "ہمیں لگتا ہے: بھاری وزن۔ کیا یہ درست ہے؟",
    },
    # --- weight guidance after the set, for the next session (TO CONFIRM WITH PHYSIO) ---
    "weight_up_light": {
        "en": "Well done! Next session, try a light weight.",
        "ur": "شاباش! اگلی بار ہلکا وزن استعمال کر کے دیکھیں",
    },
    "weight_up_heavy": {
        "en": "Well done! Next session, try a heavier weight.",
        "ur": "شاباش! اگلی بار تھوڑا بھاری وزن استعمال کر کے دیکھیں",
    },
    "weight_down_light": {
        "en": "Next session, use a lighter weight.",
        "ur": "اگلی بار ہلکا وزن استعمال کریں",
    },
    "weight_down_none": {
        "en": "Next session, do the exercise without a weight.",
        "ur": "اگلی بار یہ ورزش بغیر وزن کے کریں",
    },
    "weight_stay": {
        "en": "Keep the same weight next session.",
        "ur": "اگلی بار بھی یہی وزن رکھیں",
    },
    "weight_stay_one_more": {
        "en": "Stay at this weight. If next session goes as well, you can try the next weight.",
        "ur": "اسی وزن پر رہیں۔ اگر اگلی بار بھی اتنی ہی اچھی ورزش ہوئی تو آپ اگلا وزن آزما سکتے ہیں",
    },
    "weight_at_max": {
        "en": "Very good. Keep this weight: it is the most your physiotherapist allows.",
        "ur": "بہت اچھے۔ یہی وزن رکھیں، یہ آپ کے فزیوتھراپسٹ کی اجازت کے مطابق سب سے زیادہ ہے",
    },
    "talk_to_physio": {
        "en": "Please talk to your physiotherapist about your pain.",
        "ur": "براہ کرم اپنے درد کے بارے میں فزیوتھراپسٹ سے بات کریں",
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


def phrase_key(key, phrases=None):
    """Map a rep label or prompt to its phrase key. `phrases`: the exercise's own
    label -> phrase map (config/exercises.yaml), checked first."""
    if phrases and key in phrases:
        return phrases[key]
    return LABEL_TO_PHRASE.get(key, key)


def audio_path(key, lang="ur", phrases=None):
    return AUDIO_DIR / f"{lang}_{phrase_key(key, phrases)}.mp3"


def get_feedback(key, lang="ur", phrases=None):
    """Return (text, audio_path) for a rep label, phrase key or prompt."""
    if lang not in LANGS:
        raise ValueError(f"Unknown language {lang!r}, expected one of {LANGS}")
    pk = phrase_key(key, phrases)
    if pk not in PHRASES:
        raise KeyError(f"No phrase for {key!r}")
    return PHRASES[pk][lang], audio_path(key, lang, phrases)
