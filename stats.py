"""
Progress figures shown to a student while they work.

Everything here is DERIVED from the append-only event history — nothing is
stored. That is the same rule the drill's box schedule follows, and it is what
lets the definition of "solid" change later without corrupting past data.

Two horizons:
  session   this sitting. A sitting ends when the student stops for longer than
            SESSION_GAP; the next attempt starts a new one. Derived, so it
            survives a closed tab or a switch from laptop to phone.
  all time  everything they have ever done, summarised as solid / shaky /
            not yet — the same three words the rest of the app uses.
"""

import time

import fsrs

SESSION_GAP = 30 * 60          # 30 minutes of inactivity ends a sitting
DAY = 86400.0


def current_session(events, gap=SESSION_GAP, now=None):
    """The trailing run of attempts with no gap longer than `gap`."""
    if not events:
        return []
    evs = sorted(events, key=lambda e: e["timestamp"])
    run = [evs[-1]]
    for a, b in zip(reversed(evs[:-1]), reversed(evs[1:])):
        if b["timestamp"] - a["timestamp"] > gap:
            break
        run.append(a)
    return list(reversed(run))


def collapse_retries(events):
    """A near-miss and the retype that fixes it count as one study.

    A close sends the student straight back to the same card to retype it, so
    "aqu" then "aqua" is one word studied, not two -- and the result that counts
    is the one they finished on. Counting both made a corrected close look like
    a miss, which is the opposite of what close is for.

    Only that pair collapses: a CLOSE followed by the same card within the
    sitting. Any other repeat is a real second study and stays one -- the last
    card one night and the first the next morning, or a card relearned after
    Again. (Until Oct 2026 every consecutive repeat collapsed, which quietly
    left those cards out of the homework count.)
    """
    out = []
    for e in sorted(events, key=lambda x: x["timestamp"]):
        prev = out[-1] if out else None
        if (prev is not None and prev.get("result") == "close"
                and prev.get("item_id") == e.get("item_id")
                and e["timestamp"] - prev["timestamp"] <= SESSION_GAP):
            out[-1] = e          # the retype replaces the attempt it corrects
        else:
            out.append(e)
    return out


def session_stats(events, gap=SESSION_GAP, now=None):
    """Counts for this sitting, one entry per card studied.

    `credited` is what the percentage is built from, and it counts a close as
    right. That is the same rule the teacher dashboard uses: close means the
    Latin was there and the spelling slipped, and the app has already told the
    student it does not count against them. It also keeps the bar from reading
    0% during the moment they are retyping.
    """
    run = collapse_retries(current_session(events, gap=gap, now=now))
    out = {"studied": len(run), "right": 0, "close": 0, "wrong": 0}
    for e in run:
        r = e.get("result")
        if r in out:
            out[r] += 1
    out["credited"] = out["right"] + out["close"]
    out["pct"] = int(round(100.0 * out["credited"] / out["studied"])) if out["studied"] else None
    # Cards remembered this sitting (graded Hard, Good or Easy): each one's
    # memory just got longer. This is the number that moves every session.
    out["stronger"] = sum(1 for e in run if (fsrs.grade_of(e) or 0) >= fsrs.HARD)
    return out


def readiness_from(events, now=None):
    """solid | shaky | not yet for one item's (or one topic's) history.

    The same rule as the drill's, so the two never disagree: the history is
    replayed as one FSRS card (fsrs.py) and read from its stability -- solid
    holds three weeks or more, not yet was never got right.
    """
    return fsrs.state(fsrs.replay(events))


def strength_from(events, now=None):
    """The strength bar for one item's or topic's history (fsrs.strength)."""
    return fsrs.strength(fsrs.replay(events), now)


def group_events(events, key_fn):
    out = {}
    for e in events:
        k = key_fn(e)
        if k is None:
            continue
        out.setdefault(k, []).append(e)
    return out


def alltime_by_node(events, universe=None, now=None):
    """solid/shaky/not-yet counted over spec nodes (grammar practice)."""
    by = group_events(events, lambda e: e.get("spec_node_id"))
    return _tally(by, universe, now)


def alltime_by_word(events, universe=None, now=None):
    """solid/shaky/not-yet counted over vocabulary words (the drill).

    Drill events are keyed `vocab:<word>:<direction>`; both directions of a
    word count toward the same word.
    """
    def key(e):
        iid = str(e.get("item_id") or "")
        if not iid.startswith("vocab:"):
            return None
        parts = iid.split(":")
        return parts[1] if len(parts) > 2 else None
    by = group_events(events, key)
    return _tally(by, universe, now)


def _tally(by_key, universe, now):
    out = {"solid": 0, "shaky": 0, "not yet": 0}
    for k, evs in by_key.items():
        if universe is not None and k not in universe:
            continue
        out[readiness_from(evs, now)] += 1
    if universe is not None:
        # Anything never attempted is "not yet" — the denominator is the whole
        # list, so the figure does not flatter a student who has only tried ten.
        out["not yet"] += len(set(universe) - set(by_key))
    out["total"] = sum(out[k] for k in ("solid", "shaky", "not yet"))
    return out


def grammar_progress(spec, universe, events, now=None):
    """Per-topic readiness for the student's progress page, grouped by week.

    `universe` is the set of nodes a student can meet right now -- approved
    questions on lessons already taught -- which is the same denominator the
    bar on every question uses, so the two can never disagree. A topic never
    attempted is "not yet": the page does not flatter a student who has only
    tried five.

    Returns weeks in teaching order, each {"week", "rows", "counts", "total"},
    with rows {"node", "label", "state", "strength", "attempts"}.
    """
    by = group_events(events, lambda e: e.get("spec_node_id"))
    weeks = {}
    for nid in universe:
        node = spec.get(nid) or {}
        wk = str(node.get("week") or node.get("day") or "")
        evs = by.get(nid, [])
        card = fsrs.replay(evs)
        weeks.setdefault(wk, []).append({
            "node": nid, "label": node.get("label", nid),
            "state": fsrs.state(card), "strength": fsrs.strength(card, now),
            "attempts": len(evs), "day": str(node.get("day") or wk)})
    out = []
    for wk in sorted(weeks):
        rows = sorted(weeks[wk], key=lambda r: (r["day"], r["node"]))
        counts = {"solid": 0, "shaky": 0, "not yet": 0}
        for r in rows:
            counts[r["state"]] += 1
        out.append({"week": wk, "rows": rows, "counts": counts, "total": len(rows)})
    return out
