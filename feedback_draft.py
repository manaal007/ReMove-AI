from pathlib import Path

AUDIO = Path("assets/audio")

FEEDBACK = {
    "raise_higher": {
        "en": "Raise your arm a little higher.",
        "ur": "اپنا بازو تھوڑا اور اوپر اٹھائیں",
    },
    "trunk_lean": {
        "en": "Keep your body straight, do not lean forward.",
        "ur": "اپنا جسم سیدھا رکھیں، آگے نہ جھکیں",
    },
    "good": {
        "en": "Very good, try again.",
        "ur": "بہت اچھے، دوبارہ کوشش کریں",
    },
}

def get_feedback(issue, lang="ur"):
    text = FEEDBACK[issue][lang]
    return text, AUDIO / f"{lang}_{issue}.mp3"lang = st.radio("Language", ["ur", "en"], format_func=lambda x: "اردو" if x == "ur" else "English")
