"""
What the teacher sees. Aggregation only — every figure here is derived from
the same append-only event history the students' own screens are derived from,
so the dashboard and the student can never disagree about what happened.

Two ideas do the work:

  the roster is the denominator
        "Did they do their homework?" is a question about the students who did
        NOTHING, and a student who did nothing leaves no events. Counting rows
        in `events` can only ever show you the kids who showed up. So every
        class-level figure starts from the roster and joins history onto it.

  a window, not a total
        "Have they practiced?" is meaningless without a since-when. Homework is
        checked over an explicit date window (since last class, this week), and
        the window is always shown alongside the number.

Nothing in this module writes. Nothing in it grades.
"""

import time

import schooltime  # noqa: F401  -- every day below is the school's day
import stats

DAY = 86400.0

# The homework: this many cards of each kind a week, the teacher's number,
# changed on Goals & deadlines. "Did it" on the dashboard means exactly this,
# counted exactly the way the student's own home screen counts it.
DEFAULT_TARGETS = {"vocab": 50, "grammar": 50}
STARTED_ATTEMPTS = 1

# Proctored contexts are assessments, not homework, and never count toward it.
# Counting them would let a Friday quiz fill Monday's quota. Reader questions
# aren't vocabulary or grammar cards either, so they don't fill the 50 + 50.
NOT_HOMEWORK = {"quiz", "exam", "reading"}

# Above this share right, a topic is not the thing to reteach on Monday. It is
# a display threshold only — nothing is scored against it.
SECURE = 0.8


# --------------------------------------------------------------------------
# Small shared helpers
# --------------------------------------------------------------------------

def day_key(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def kind_of(event):
    """'vocab' for drill attempts, 'grammar' for question attempts.

    The drill writes item ids of the form vocab:<word>:<direction>; the
    grammar app writes real item ids from the bank. That prefix is the only
    thing separating the two streams, so it is named once, here.
    """
    return "vocab" if str(event.get("item_id") or "").startswith("vocab:") else "grammar"


def homework_events(events):
    """Every answer that counts as homework: anything but a proctored quiz."""
    return [e for e in events if (e.get("context") or "practice") not in NOT_HOMEWORK]


def homework_counts(events):
    """{"vocab": n, "grammar": n} cards studied, for ONE student's events.

    A close sends the student straight back to retype, and "aqu" then "aqua"
    is one card studied, not two -- the same rule the stats bar uses, so the
    home screen, the stats bar and this dashboard cannot disagree.
    """
    counts = {"vocab": 0, "grammar": 0}
    for e in stats.collapse_retries(homework_events(events)):
        counts[kind_of(e)] += 1
    return counts


def window_bounds(days=7, now=None, start_of_day=True):
    """(since, until) for the last `days` days. Windows start at midnight local
    so 'this week' means whole school days, not a rolling 168 hours."""
    now = now or time.time()
    if not start_of_day:
        return (now - days * DAY, now)
    lt = time.localtime(now)
    midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    return (midnight - (days - 1) * DAY, now)


def in_window(events, since=None, until=None):
    out = []
    for e in events:
        ts = e["timestamp"]
        if since is not None and ts < since:
            continue
        if until is not None and ts > until:
            continue
        out.append(e)
    return out


def by_student(events):
    out = {}
    for e in events:
        out.setdefault(e["student_id"], []).append(e)
    for evs in out.values():
        evs.sort(key=lambda e: e["timestamp"])
    return out


def accuracy(events):
    """Share right, counting close as right. Close means the Latin was there
    and the spelling slipped; treating it as a miss would make a careful
    student look weak."""
    scored = [e for e in events if e.get("result") in ("right", "close", "wrong")]
    if not scored:
        return None
    good = sum(1 for e in scored if e["result"] in ("right", "close"))
    return good / float(len(scored))


# --------------------------------------------------------------------------
# Did they practice? — one row per student
# --------------------------------------------------------------------------

def activity(events, since=None, until=None):
    """One student's activity in a window."""
    win = in_window(events, since, until)
    days = sorted({day_key(e["timestamp"]) for e in win})
    return {
        "attempts": len(win),
        "days": len(days),
        "day_list": days,
        "vocab": sum(1 for e in win if kind_of(e) == "vocab"),
        "grammar": sum(1 for e in win if kind_of(e) == "grammar"),
        "hw": homework_counts(win),
        "accuracy": accuracy(win),
        "last_at": max((e["timestamp"] for e in win), default=None),
        "ever_last_at": max((e["timestamp"] for e in events), default=None),
        "ever_attempts": len(events),
    }


def homework_state(act, targets=None, started=STARTED_ATTEMPTS):
    """done | started | none -- deliberately three words, like solid/shaky/not
    yet. "done" is the weekly goal met inside the window: the teacher's
    vocabulary AND grammar numbers, counted the way the student's home screen
    counts them."""
    targets = targets or DEFAULT_TARGETS
    if all(act["hw"][k] >= targets[k] for k in targets):
        return "done"
    if act["attempts"] >= started:
        return "started"
    return "none"


def class_activity(roster_rows, events, since=None, until=None, targets=None):
    """The homework table: every rostered student, practiced or not.

    IDs with events that are NOT on the roster are returned separately rather
    than dropped. A mistyped ID number looks perfectly well-formed, so that
    list is the only place a typo becomes visible.
    """
    grouped = by_student(events)
    rows = []
    for r in roster_rows:
        sid = r["student_id"]
        act = activity(grouped.get(sid, []), since, until)
        rows.append({
            "student_id": sid,
            # No display name: there is none to display. The ID is the label.
            "section": r.get("section"),
            "state": homework_state(act, targets),
            **act,
        })
    rows.sort(key=lambda x: (x["attempts"], x["days"]))
    known = {r["student_id"] for r in roster_rows}
    unrostered = sorted(set(grouped) - known)
    return {"rows": rows, "unrostered": unrostered,
            "n_done": sum(1 for x in rows if x["state"] == "done"),
            "n_started": sum(1 for x in rows if x["state"] == "started"),
            "n_none": sum(1 for x in rows if x["state"] == "none"),
            "n_students": len(rows)}


# --------------------------------------------------------------------------
# What does the class know? — one row per thing being learned
# --------------------------------------------------------------------------

def _bucket(events, key_fn):
    out = {}
    for e in events:
        k = key_fn(e)
        if k is None:
            continue
        out.setdefault(k, []).append(e)
    return out


def node_key(e):
    if kind_of(e) != "grammar":
        return None
    return e.get("spec_node_id") or None


def word_key(e):
    if kind_of(e) != "vocab":
        return None
    parts = str(e["item_id"]).split(":")
    return parts[1] if len(parts) > 2 else None


def difficulty(events, key_fn, min_attempts=5, universe=None):
    """Weakest-first table over whatever key_fn picks out.

    `min_attempts` exists because one student getting one question wrong is
    not a class weakness, and a 0% row built on a single attempt would sit at
    the top of the list forever. Rows below the threshold are still returned,
    flagged `thin`, so a topic nobody has touched is visible rather than
    absent.
    """
    buckets = _bucket(events, key_fn)
    rows = []
    for k, evs in buckets.items():
        if universe is not None and k not in universe:
            continue
        acc = accuracy(evs)
        rows.append({
            "key": k,
            "attempts": len(evs),
            "students": len({e["student_id"] for e in evs}),
            "right": sum(1 for e in evs if e.get("result") == "right"),
            "close": sum(1 for e in evs if e.get("result") == "close"),
            "wrong": sum(1 for e in evs if e.get("result") == "wrong"),
            "accuracy": acc,
            "thin": len(evs) < min_attempts,
        })
    if universe is not None:
        for k in sorted(set(universe) - set(buckets)):
            rows.append({"key": k, "attempts": 0, "students": 0, "right": 0,
                         "close": 0, "wrong": 0, "accuracy": None, "thin": True})
    # Weakest first; untouched rows last, since "no data" is not "hard".
    rows.sort(key=lambda r: (r["accuracy"] is None, r["accuracy"] if r["accuracy"] is not None else 0,
                             -r["attempts"]))
    return rows


def miss_reason_counts(miss_rows, min_count=1):
    """What students said went wrong, most common first.

    Grouped by the node that EXPLAINS the mistake, not the node the question
    was about: "I matched the ending instead of the gender" is a fact about
    agreement, whichever question exposed it. That is the difference between
    a list of hard questions and a list of things to reteach.
    """
    out = {}
    for r in miss_rows:
        k = (r.get("reason_node") or "", r.get("reason_text") or r.get("reason_key") or "")
        d = out.setdefault(k, {"reason_node": k[0], "reason_text": k[1],
                               "count": 0, "students": set(), "contested": 0})
        d["count"] += 1
        d["students"].add(r.get("student_id"))
        if r.get("contested"):
            d["contested"] += 1
    rows = []
    for d in out.values():
        if d["count"] < min_count:
            continue
        d = dict(d)
        d["students"] = len(d["students"])
        rows.append(d)
    rows.sort(key=lambda r: (-r["count"], r["reason_text"]))
    return rows


def contested_items(miss_rows):
    """Every 'I think my answer should be right'. These are the ones worth the
    teacher's eyes — a contested question is either a student misconception or
    a bad question, and both need a person to tell them apart."""
    rows = [r for r in miss_rows if r.get("contested")]
    rows.sort(key=lambda r: -r["timestamp"])
    return rows
