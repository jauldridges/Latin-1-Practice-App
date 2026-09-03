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


def session_stats(events, gap=SESSION_GAP, now=None):
    """Counts for this sitting. `studied` counts attempts, not distinct items:
    a student who retypes after a close has genuinely studied it twice."""
    run = current_session(events, gap=gap, now=now)
    out = {"studied": len(run), "right": 0, "close": 0, "wrong": 0}
    for e in run:
        r = e.get("result")
        if r in out:
            out[r] += 1
    return out


def readiness_from(events, now=None):
    """solid | shaky | not yet for one item's history.

    Kept identical to the drill's rule so the two never disagree: several
    rights, across more than one day, including at least one a week or more
    after the item was first seen. The delayed success is the whole point — it
    separates retention from a single evening of cramming.
    """
    now = now or time.time()
    if not events:
        return "not yet"
    rights = [e for e in events if e.get("result") == "right"]
    if not rights:
        return "not yet"
    first_seen = min(e["timestamp"] for e in events)
    days = {time.strftime("%Y-%m-%d", time.localtime(e["timestamp"])) for e in rights}
    delayed = any(e["timestamp"] - first_seen >= 7 * DAY for e in rights)
    if len(rights) >= 3 and len(days) >= 2 and delayed:
        return "solid"
    return "shaky"


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
