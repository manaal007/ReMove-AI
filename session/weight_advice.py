"""
Weight guidance after a set (E3, E4): move up / stay / move down one level next session.

Rules from config/thresholds.yaml weight_guidance (TO CONFIRM WITH PHYSIO):
  down  if ANY: pain after the set >= down.min_pain (also: talk to your physio),
        compensation in >= down.min_compensation_reps reps,
        set range < down.max_range_frac x reference range (dropped more than 20%)
  up    if ALL: good reps >= up.min_good_reps, compensation reps <= up.max_compensation_reps,
        pain <= up.max_pain, set range >= up.min_range_frac x no-weight baseline range,
        in up.consecutive_sessions sessions in a row (2-for-2 rule) at the same exercise and
        weight. Before that the advice is stay, with "if next session goes as well, you can
        try the next weight" when one more such session is needed.
  stay  otherwise
Moving down is immediate: one bad session is enough.

The run of qualifying sessions before this one (prior_streak) comes from the saved
advice of earlier sessions (storage.db.store.Store.qualifying_streak): each advice
records up_qualified = all move-up conditions met.
Limits: one level per session going up; never above the physio's max level (health
form; unknown = none, the safe default). If the patient is already above that max,
the advice is the max itself, even if that is two levels down: the max wins.
The weight never changes during a set (api.live refuses a new choice once the set
has started); this advice is for the next session, and the patient still confirms
the weight at the start of it.

Set range = median range (rom) of the set's scored reps. Reference = the patient's
latest no-weight baseline range (calibration with weight "none"). With no such
baseline the patient cannot move up (we cannot tell), and the range-drop rule is off.
"""
import numpy as np

REASONS = ("pain_high", "compensation", "range_drop", "above_max",            # down
           "all_criteria_met",                                                  # up
           "qualified_need_more",                                               # stay: 2-for-2
           "at_max", "few_good_reps", "some_compensation", "pain_some",         # stay: why not up
           "range_short", "no_reference")


def set_facts(log):
    """Good reps, compensation reps and median range of the scored reps of one session log."""
    scored = [r for r in log.get("reps", []) if r.get("phase") == "scoring"]
    roms = [r["features"]["rom"] for r in scored
            if (r.get("features") or {}).get("rom") is not None]
    return {
        "scored": len(scored),
        "good": sum(r["label"] == "good" for r in scored),
        "compensation": sum("trunk_compensation" in (r.get("faults") or []) for r in scored),
        "range": float(np.median(roms)) if roms else None,
    }


def advise(facts, pain, current, max_level, no_weight_rom, cfg, prior_streak=0):
    """Advice dict: action up | down | stay, current / next level, reasons, phrases to speak.
    prior_streak: sessions in a row right before this one, same exercise and weight, that met
    every move-up condition."""
    g = cfg["weight_guidance"]
    levels = list(g["levels"])
    if current not in levels:
        raise ValueError(f"current weight must be one of {levels}")
    max_level = max_level if max_level in levels else levels[0]
    if not isinstance(pain, int) or not 0 <= pain <= 10:
        raise ValueError("pain must be a whole number 0-10")
    cur, top = levels.index(current), levels.index(max_level)

    frac = None
    if facts.get("range") is not None and no_weight_rom:
        frac = facts["range"] / no_weight_rom
    up, down = g["up"], g["down"]

    down_reasons = []
    if pain >= down["min_pain"]:
        down_reasons.append("pain_high")
    if facts["compensation"] >= down["min_compensation_reps"]:
        down_reasons.append("compensation")
    if frac is not None and frac < down["max_range_frac"]:
        down_reasons.append("range_drop")

    not_up = []
    if facts["good"] < up["min_good_reps"]:
        not_up.append("few_good_reps")
    if facts["compensation"] > up["max_compensation_reps"]:
        not_up.append("some_compensation")
    if pain > up["max_pain"]:          # with today's values (3 / 4) pain 4+ already moves down,
        not_up.append("pain_some")     # but the physio may set max_pain lower than min_pain - 1
    if frac is None:
        not_up.append("no_reference")
    elif frac < up["min_range_frac"]:
        not_up.append("range_short")

    up_qualified = not down_reasons and not not_up
    streak = int(prior_streak) + 1 if up_qualified else 0
    needed = int(up["consecutive_sessions"])
    if down_reasons:                                                 # moving down is immediate
        nxt, reasons = max(cur - 1, 0), down_reasons
    elif up_qualified:
        if cur + 1 > top:
            nxt, reasons = cur, ["at_max"]
        elif streak >= needed:
            nxt, reasons = cur + 1, ["all_criteria_met"]            # one level at most
        else:
            nxt, reasons = cur, ["qualified_need_more"]
    else:
        nxt, reasons = cur, not_up
    if nxt > top:                                                    # never above the physio's max
        nxt, reasons = top, ["above_max"] + [r for r in reasons if r != "at_max"]

    action = "up" if nxt > cur else "down" if nxt < cur else "stay"
    talk = "pain_high" in reasons
    if action == "up":
        phrases = [f"weight_up_{levels[nxt]}"]
    elif action == "down":
        phrases = [f"weight_down_{levels[nxt]}"]
    elif "at_max" in reasons:
        phrases = ["weight_at_max"]
    elif "qualified_need_more" in reasons and needed - streak == 1:
        phrases = ["weight_stay_one_more"]
    else:
        phrases = ["weight_stay"]
    if talk:
        phrases.append("talk_to_physio")
    return {
        "action": action, "current": current, "next": levels[nxt], "max_level": max_level,
        "reasons": reasons, "talk_to_physio": talk, "phrases": phrases, "pain": pain,
        "good_reps": facts["good"], "scored_reps": facts["scored"],
        "compensation_reps": facts["compensation"],
        "range": None if facts.get("range") is None else round(facts["range"], 1),
        "no_weight_range": None if not no_weight_rom else round(float(no_weight_rom), 1),
        "range_frac": None if frac is None else round(frac, 3),
        "up_qualified": up_qualified,          # saved: the next session's prior_streak counts these
        "qualifying_streak": streak, "sessions_needed": needed,
    }
