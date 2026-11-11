"""Feedback phrases and audio mapping (feedback/messages.py, scripts/make_audio.py)."""
import importlib.util
import re
from pathlib import Path

import pytest

from feedback import messages as M

ARABIC_SCRIPT = re.compile(r"[؀-ۿ]")
ALL_KEYS = M.REP_LABELS + M.PROMPTS


def test_six_rep_labels_from_labeling_guide():
    assert set(M.REP_LABELS) == {"good", "reduced_range", "too_fast", "jerky",
                                 "trunk_compensation", "not_tracked"}


@pytest.mark.parametrize("key", ALL_KEYS)
@pytest.mark.parametrize("lang", M.LANGS)
def test_every_label_and_prompt_has_text(key, lang):
    text, path = M.get_feedback(key, lang)
    assert text.strip()
    assert path.name == f"{lang}_{M.phrase_key(key)}.mp3"


@pytest.mark.parametrize("key", list(M.PHRASES))
def test_urdu_is_urdu_and_english_is_not(key):
    assert ARABIC_SCRIPT.search(M.PHRASES[key]["ur"])
    assert not ARABIC_SCRIPT.search(M.PHRASES[key]["en"])


def test_label_audio_mapping():
    assert M.audio_path("reduced_range", "ur").name == "ur_raise_higher.mp3"
    assert M.audio_path("trunk_compensation", "en").name == "en_trunk_lean.mp3"
    assert M.audio_path("too_fast", "ur").name == "ur_too_fast.mp3"


def test_no_orphan_phrases():
    used = {M.phrase_key(k) for k in ALL_KEYS}
    assert used == set(M.PHRASES)


def test_default_language_is_urdu():
    assert M.get_feedback("good")[0] == M.PHRASES["good"]["ur"]


def test_unknown_language_and_key_raise():
    with pytest.raises(ValueError):
        M.get_feedback("good", "fr")
    with pytest.raises(KeyError):
        M.get_feedback("nonsense")


def test_audio_dir_does_not_depend_on_cwd():
    assert M.AUDIO_DIR.is_absolute()
    assert M.AUDIO_DIR.parts[-2:] == ("assets", "audio")


@pytest.mark.parametrize("key", ["good", "raise_higher", "trunk_lean"])
@pytest.mark.parametrize("lang", M.LANGS)
def test_existing_audio_files_present(key, lang):
    assert (M.AUDIO_DIR / f"{lang}_{key}.mp3").exists()


def test_make_audio_has_a_voice_per_language():
    pytest.importorskip("edge_tts")
    path = Path(__file__).resolve().parent.parent / "scripts" / "make_audio.py"
    spec = importlib.util.spec_from_file_location("make_audio", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)            # safe: generation only runs under __main__
    assert set(mod.VOICES) == set(M.LANGS)
    assert mod.clean("‏سلام‎") == "سلام"
