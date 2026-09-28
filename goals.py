"""
The weekly practice goal, the spacing reminder, and what a quiz or test covers.

Everything here is derived from the event history, like the rest of the app:
no count is stored, so changing a target in November reads September correctly.

THE WEEKLY GOAL is two numbers, vocabulary answers and grammar answers, set by
the teacher. A week runs Monday to Sunday, because "this week" means that to a
student; the dashboard's rolling seven days is a different question, asked by a
different person. What counts:

  - practice of any kind except a proctored quiz or exam. A quiz is an
    assessment, not homework, and counting it would let a Friday quiz fill
    Monday's quota;
  - one answer per card studied. A close sends the student straight back to
    retype, and "aqu" then "aqua" is one word studied, not two -- the same rule
    the stats bar already uses, so the two numbers cannot drift apart.

THE SPACING REMINDER is always present and quiet, because spacing is the whole
design of the app, and becomes a flag once a student has gone more than two
days without practising. It never says anything about a grade.

AN ASSESSMENT covers teaching weeks. The words introduced in those weeks and
the grammar topics taught in them are what it tests, minus any topic the
teacher unticks. Only topics with approved questions on lessons already taught
can be practised or counted, so a quiz page never offers practice on something
that has not been taught.

READINESS on an assessment page keeps solid / shaky / not yet exactly as they
are everywhere else, and adds one more number: what the student got right on
their most recent try. "Solid" needs a success at least a week after first
meeting something, so a student who starts studying four days before a quiz
cannot reach it however hard they work -- the right rule for memory, and a
hopeless-looking page for a kid who is doing the right thing. "Right last
time" is the number a few days of real study can move.
"""

import time

import drill
import stats
import teacher

DAY = 86400
IDLE_DAYS = 2                    # more than this without practice raises the flag
NOT_HOMEWORK = {"quiz", "exam"}  # proctored contexts never count toward the goal
DEFAULT_TARGETS = {"vocab": 50, "grammar": 50}


# --------------------------------------------------------------------------
# The week
# --------------------------------------------------------------------------

def week_start(now=None):
    """Midnight local on the Monday of this week."""
    now = now or time.time()
    lt = time.localtime(now)
    midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    return midnight - lt.tm_wday * DAY


def _local_date(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _homework(events):
    return [e for e in events if (e.get("context") or "practice") not in NOT_HOMEWORK]


def weekly_progress(events, targets=None, now=None):
    """This week's answers against the goal, and which days had any.

    Returns {"vocab", "grammar", "targets", "days", "met"} where `days` is a
    list of seven booleans, Monday first -- the picture of spacing.
    """
    now = now or time.time()
    targets = dict(DEFAULT_TARGETS, **(targets or {}))
    start = week_start(now)
    mine = [e for e in _homework(events) if start <= e["timestamp"] <= now]
    studied = stats.collapse_retries(mine)
    counts = {"vocab": 0, "grammar": 0}
    for e in studied:
        counts[teacher.kind_of(e)] += 1
    days = [False] * 7
    for e in mine:
        days[time.localtime(e["timestamp"]).tm_wday] = True
    today = time.localtime(now).tm_wday
    return {
        "vocab": counts["vocab"], "grammar": counts["grammar"],
        "targets": targets,
        "days": days,
        "today": today,
        "met": {k: counts[k] >= targets[k] for k in counts},
    }


def days_since_practice(events, now=None):
    """Whole calendar days since the last practice, or None if there has been
    none. Practising yesterday is 1; today is 0."""
    mine = _homework(events)
    if not mine:
        return None
    now = now or time.time()
    last = max(e["timestamp"] for e in mine)
    a = time.strptime(_local_date(last), "%Y-%m-%d")
    b = time.strptime(_local_date(now), "%Y-%m-%d")
    return int(round((time.mktime(b) - time.mktime(a)) / DAY))


def spacing_flag(events, now=None):
    """None, or "never" / "idle" -- when the reminder should raise its voice."""
    gap = days_since_practice(events, now)
    if gap is None:
        return "never"
    if gap > IDLE_DAYS:
        return "idle"
    return None


# --------------------------------------------------------------------------
# What an assessment covers
# --------------------------------------------------------------------------

def word_week_date(word):
    """A drill word's week as a Monday date, the same shape spec nodes use."""
    return drill._WEEK_MONDAY.get(word.get("week"), "")


def all_weeks(spec, words):
    """Every teaching week anything is filed under, as Monday dates, in order."""
    weeks = {str(n.get("week")) for n in spec.values() if n.get("week")}
    weeks |= {word_week_date(w) for w in words if word_week_date(w)}
    return sorted(w for w in weeks if w)


def scope(assessment, spec, words, practiceable):
    """(nodes, words) an assessment covers.

    `practiceable` is the set of nodes with approved questions on lessons
    already taught. A topic outside it cannot be practised, so it is left off
    the student's page rather than shown as something they cannot act on.
    """
    weeks = set(assessment.get("weeks") or [])
    excluded = set(assessment.get("excluded_nodes") or [])
    nodes = sorted(
        (nid for nid, n in spec.items()
         if str(n.get("week")) in weeks and nid in practiceable and nid not in excluded),
        key=lambda nid: (str(spec[nid].get("day") or ""), nid))
    ws = [w for w in words if word_week_date(w) in weeks]
    return nodes, ws


def _right_last_time(evs):
    if not evs:
        return False
    return max(evs, key=lambda e: e["timestamp"]).get("result") == "right"


def readiness(nodes, words, events, spec, now=None):
    """Per-topic and per-word state for an assessment page, plus totals.

    Each row carries `state` (solid / shaky / not yet, unchanged from anywhere
    else in the app) and `right_last` (the most recent try was right).
    """
    now = now or time.time()
    by_node = stats.group_events(events, lambda e: e.get("spec_node_id"))
    topic_rows = []
    for nid in nodes:
        evs = by_node.get(nid, [])
        topic_rows.append({"node": nid, "label": spec[nid].get("label", nid),
                           "state": stats.readiness_from(evs, now),
                           "right_last": _right_last_time(evs), "tried": bool(evs)})
    word_rows = []
    for w in words:
        evs = drill._events_for_key(events, drill._key(w["latin"]))
        word_rows.append({"latin": w["latin"], "en": ", ".join(w.get("en") or [])[:40],
                          "week": w.get("week"), "state": drill.readiness(evs, now),
                          "right_last": _right_last_time(evs), "tried": bool(evs)})

    def totals(rows):
        t = {"solid": 0, "shaky": 0, "not yet": 0, "right_last": 0, "total": len(rows)}
        for r in rows:
            t[r["state"]] += 1
            t["right_last"] += 1 if r["right_last"] else 0
        return t

    return {"topics": topic_rows, "words": word_rows,
            "topic_totals": totals(topic_rows), "word_totals": totals(word_rows)}


def days_until(date_str, now=None):
    """Whole days from today to a YYYY-MM-DD date; 0 is today, negative is past."""
    now = now or time.time()
    try:
        target = time.mktime(time.strptime(str(date_str), "%Y-%m-%d"))
    except (ValueError, TypeError):
        return None
    today = time.mktime(time.strptime(_local_date(now), "%Y-%m-%d"))
    return int(round((target - today) / DAY))


def when_label(date_str, now=None):
    """"today", "tomorrow", "in 4 days", "Fri 9 Oct" -- what a student reads."""
    d = days_until(date_str, now)
    if d is None:
        return str(date_str)
    if d == 0:
        return "today"
    if d == 1:
        return "tomorrow"
    if 1 < d <= 13:
        return "in %d days" % d
    if d < 0:
        return "finished"
    t = time.strptime(str(date_str), "%Y-%m-%d")
    return "%s %d %s" % (time.strftime("%a", t), t.tm_mday, time.strftime("%b", t))
