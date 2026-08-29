"""
Vocabulary drill logic: card selection, the Leitner box schedule, and the
solid / shaky / not-yet readiness state.

Design choices held to the spec:
  - A simple box system, nothing more elaborate. Right moves a word up a box and
    pushes its next appearance out; wrong drops it to box 1; close never counts
    as wrong and does not change the box.
  - State is DERIVED from the append-only event history, never stored. Replaying
    a word's events gives its box, its due time, and its readiness state.
  - "solid" requires retrieval that survived a gap: several rights, across more
    than one sitting, including at least one right a week or more after the word
    was first seen. That delayed-success condition is the whole point.

A "sitting" is approximated by a distinct calendar day (UTC). See the writeup:
this is an approximation of "a separate study session".
"""

import time
from collections import namedtuple

from answercheck import clean

DAY = 86400.0

# Leitner intervals (seconds) indexed by box level 1..5: the wait before the
# word is due again once it has reached that box.
_INTERVALS = {1: 0.0, 2: 1 * DAY, 3: 3 * DAY, 4: 7 * DAY, 5: 21 * DAY}

WEEK_ORDER = ["week_of_aug_24", "week_of_aug_31", "week_of_sep_8",
              "week_of_sep_14", "week_of_sep_21", "week_of_sep_28"]

WEEK_LABELS = {
    "week_of_aug_24": "Week of Aug 24",
    "week_of_aug_31": "Week of Aug 31",
    "week_of_sep_8": "Week of Sep 7",
    "week_of_sep_14": "Week of Sep 14",
    "week_of_sep_21": "Week of Sep 21",
    "week_of_sep_28": "Week of Sep 28",
}

# Monday of each core-list week, for resolving "the current week".
_WEEK_MONDAY = {
    "week_of_aug_24": "2026-08-24", "week_of_aug_31": "2026-08-31",
    "week_of_sep_8": "2026-09-07", "week_of_sep_14": "2026-09-14",
    "week_of_sep_21": "2026-09-21", "week_of_sep_28": "2026-09-28",
}

Card = namedtuple("Card", ["latin", "ask", "prompt", "instruction", "week"])


def _key(latin):
    return clean(latin)


def item_id_for(word, ask):
    """Stable id used in the event record. Encodes the direction so the data can
    distinguish Latin->English from English->Latin, while state is grouped by
    word."""
    return f"vocab:{_key(word['latin'])}:{ask}"


def node_for(word):
    """Vocabulary is not spec-noded (the spec keeps VO out of the node list), so
    the event's spec_node_id is None for drill attempts."""
    return None


def find_word(words, latin):
    k = _key(latin)
    for w in words:
        if _key(w["latin"]) == k:
            return w
    return None


def accepted_for(word, ask):
    """Accepted answers for a card. la_en asks for English (the gloss list);
    en_la asks for the Latin headword (macrons never required)."""
    if ask == "la_en":
        return list(word["en"])
    return [word["latin"]]


def current_week(now=None):
    now = now or time.time()
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    chosen = WEEK_ORDER[0]
    for wk in WEEK_ORDER:
        if _WEEK_MONDAY[wk] <= today:
            chosen = wk
    return chosen


def _scope_words(words, week):
    if week in (None, "all", "cumulative"):
        return list(words)
    if week == "current":
        wk = current_week()
        upto = WEEK_ORDER.index(wk)
        allowed = set(WEEK_ORDER[: upto + 1])
        # "the current week's list" plus everything before it (cumulative floor)
        return [w for w in words if w["week"] in allowed]
    return [w for w in words if w["week"] == week]


def _events_for_key(events, key):
    prefix = f"vocab:{key}:"
    return sorted((e for e in events if str(e.get("item_id", "")).startswith(prefix)),
                  key=lambda e: e["timestamp"])


def box_and_due(word_events):
    """Replay a word's events to a (box_level, due_timestamp). New word -> box 1,
    due now."""
    box = 1
    last_ts = None
    for e in word_events:
        last_ts = e["timestamp"]
        r = e["result"]
        if r == "right":
            box = min(box + 1, 5)
        elif r == "wrong":
            box = 1
        # close: no change
    if last_ts is None:
        return 1, 0.0
    return box, last_ts + _INTERVALS[box]


def readiness(word_events, now=None):
    """solid | shaky | not yet, from a word's history."""
    now = now or time.time()
    if not word_events:
        return "not yet"
    rights = [e for e in word_events if e["result"] == "right"]
    if not rights:
        return "not yet"
    first_seen = min(e["timestamp"] for e in word_events)
    days = {time.strftime("%Y-%m-%d", time.localtime(e["timestamp"])) for e in rights}
    delayed = any(e["timestamp"] - first_seen >= 7 * DAY for e in rights)
    if len(rights) >= 3 and len(days) >= 2 and delayed:
        return "solid"
    return "shaky"


def next_card(words, events, week="current", direction="both", now=None):
    """Choose the next word to show and in which direction. Prefers words that
    are due (new words are due immediately), lowest box first, then the most
    overdue."""
    now = now or time.time()
    pool = _scope_words(words, week)
    if not pool:
        return None

    scored = []
    for w in pool:
        wev = _events_for_key(events, _key(w["latin"]))
        box, due = box_and_due(wev)
        due_flag = due <= now
        scored.append((w, wev, box, due, due_flag))

    due_words = [s for s in scored if s[4]]
    picklist = due_words or scored
    # lowest box first, then most overdue (smallest due timestamp)
    picklist.sort(key=lambda s: (s[2], s[3]))
    w, wev, box, due, _ = picklist[0]

    ask = _choose_direction(wev, direction)
    return card_for(w, ask)


def card_for(word, ask):
    """Build the display card for a word in a given direction."""
    if ask == "la_en":
        prompt, instruction = word["latin"], "Type the English."
    else:
        prompt, instruction = word["en"][0], "Type the Latin (macrons not needed)."
    return Card(latin=word["latin"], ask=ask, prompt=prompt,
                instruction=instruction, week=word["week"])


def _choose_direction(word_events, direction):
    if direction in ("la_en", "en_la"):
        return direction
    # 'both': show whichever direction the student has practised less for this
    # word, breaking ties toward Latin->English.
    la_en = sum(1 for e in word_events if str(e.get("item_id", "")).endswith(":la_en"))
    en_la = sum(1 for e in word_events if str(e.get("item_id", "")).endswith(":en_la"))
    return "en_la" if en_la < la_en else "la_en"


# --------------------------------------------------------------------------
# Progress display
# --------------------------------------------------------------------------

ProgressRow = namedtuple("ProgressRow",
                         ["latin", "en", "week", "state", "box", "attempts", "rights", "last_seen"])


def progress_table(words, events, now=None):
    now = now or time.time()
    rows = []
    for w in words:
        wev = _events_for_key(events, _key(w["latin"]))
        state = readiness(wev, now)
        box, _due = box_and_due(wev)
        rights = sum(1 for e in wev if e["result"] == "right")
        last_seen = max((e["timestamp"] for e in wev), default=None)
        rows.append(ProgressRow(
            latin=w["latin"], en=", ".join(w["en"][:3]), week=w["week"],
            state=state, box=box, attempts=len(wev), rights=rights,
            last_seen=(time.strftime("%b %d", time.localtime(last_seen)) if last_seen else "—"),
        ))
    order = {wk: i for i, wk in enumerate(WEEK_ORDER)}
    rows.sort(key=lambda r: (order.get(r.week, 99), r.latin))
    return rows


def progress_summary(rows):
    def tally(rs):
        out = {"solid": 0, "shaky": 0, "not yet": 0}
        for r in rs:
            out[r.state] += 1
        return out
    cur = current_week()
    upto = set(WEEK_ORDER[: WEEK_ORDER.index(cur) + 1])
    return {
        "cumulative": tally(rows),
        "current_week": tally([r for r in rows if r.week == cur]),
        "current_week_label": WEEK_LABELS.get(cur, cur),
        "total": len(rows),
    }
