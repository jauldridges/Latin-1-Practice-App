"""
Vocabulary drill logic: card selection, the schedule, and the solid / shaky /
not-yet state.

The schedule is FSRS (fsrs.py), one card per word, both directions together:
"puella" asked Latin to English and English to Latin is one memory. It
replaced a five-box Leitner system in October 2026.

State is DERIVED from the append-only event history, never stored. Replaying
a word's events gives its stability, its due time and its state.
"""

import time
from collections import namedtuple

import fsrs
from answercheck import clean

DAY = 86400.0

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
    if "," in week:
        # Several weeks at once: what an assessment page sends to drill just
        # the words that quiz covers.
        chosen = {w for w in week.split(",") if w}
        return [w for w in words if w["week"] in chosen]
    return [w for w in words if w["week"] == week]


def _events_for_key(events, key):
    prefix = f"vocab:{key}:"
    return sorted((e for e in events if str(e.get("item_id", "")).startswith(prefix)),
                  key=lambda e: e["timestamp"])


def card_state(word_events):
    """The word's FSRS card, replayed from its events; None if never studied."""
    return fsrs.replay(word_events)


def readiness(word_events, now=None):
    """solid | shaky | not yet, from a word's history (fsrs.state)."""
    return fsrs.state(card_state(word_events))


def _word_of(event):
    parts = str(event.get("item_id") or "").split(":")
    return parts[1] if len(parts) > 2 and parts[0] == "vocab" else None


def scheduled(words, events, week="current"):
    """({word key: Card or None}, [keys in order]) for the words in scope."""
    pool = _scope_words(words, week)
    by_key = {}
    for e in events:
        k = _word_of(e)
        if k is not None:
            by_key.setdefault(k, []).append(e)
    keys = [_key(w["latin"]) for w in pool]
    return {k: card_state(by_key.get(k, [])) for k in keys}, keys


def due_count(words, events, week="current", now=None):
    """Reviews due now, not counting words never studied."""
    cards, keys = scheduled(words, events, week)
    return sum(1 for k in keys if fsrs.is_due(cards[k], now))


def next_card(words, events, week="current", direction="both", now=None):
    """The next word and direction (fsrs.pick): due words, most likely
    forgotten first; then new words in teaching order; then, with nothing
    left for today, extra practice on the weakest. Never the word just
    answered while another is available."""
    now = now or time.time()
    pool = _scope_words(words, week)
    if not pool:
        return None
    cards, keys = scheduled(words, events, week)
    vocab = [e for e in events if _word_of(e)]
    last = _word_of(max(vocab, key=lambda e: e["timestamp"])) if vocab else None
    k = fsrs.pick(cards, keys, now=now, avoid=last)
    w = next(w for w in pool if _key(w["latin"]) == k)
    ask = _choose_direction(_events_for_key(events, k), direction)
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
    # 'both': show whichever direction the student has practiced less for this
    # word, breaking ties toward Latin->English.
    la_en = sum(1 for e in word_events if str(e.get("item_id", "")).endswith(":la_en"))
    en_la = sum(1 for e in word_events if str(e.get("item_id", "")).endswith(":en_la"))
    return "en_la" if en_la < la_en else "la_en"


# --------------------------------------------------------------------------
# Progress display
# --------------------------------------------------------------------------

ProgressRow = namedtuple("ProgressRow",
                         ["latin", "en", "week", "state", "strength", "attempts", "rights",
                          "last_seen"])


def progress_table(words, events, now=None):
    now = now or time.time()
    rows = []
    for w in words:
        wev = _events_for_key(events, _key(w["latin"]))
        card = card_state(wev)
        rights = sum(1 for e in wev if e["result"] == "right")
        last_seen = max((e["timestamp"] for e in wev), default=None)
        rows.append(ProgressRow(
            latin=w["latin"], en=", ".join(w["en"][:3]), week=w["week"],
            state=fsrs.state(card), strength=fsrs.strength(card, now),
            attempts=len(wev), rights=rights,
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
        "by_week": by_week(rows),
    }


def by_week(rows):
    """The progress table split into the weeks the words were introduced.

    A flat list of eighty words tells a student they have work to do; the same
    list grouped by week tells them WHERE, and "you are shaky on the week of
    Sep 14" is something a fourteen-year-old can act on tonight.

    Weeks come back in teaching order, not alphabetical, and a word whose week
    is not in WEEK_ORDER still gets a group rather than disappearing.
    """
    groups = {}
    for r in rows:
        groups.setdefault(r.week, []).append(r)

    def tally(rs):
        out = {"solid": 0, "shaky": 0, "not yet": 0}
        for r in rs:
            out[r.state] += 1
        return out

    order = {w: i for i, w in enumerate(WEEK_ORDER)}
    out = []
    for week in sorted(groups, key=lambda w: (order.get(w, 99), str(w))):
        rs = groups[week]
        out.append({"week": week,
                    "label": WEEK_LABELS.get(week, str(week)),
                    "rows": rs,
                    "counts": tally(rs),
                    "total": len(rs)})
    return out
