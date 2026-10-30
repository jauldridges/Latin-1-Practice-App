"""
The weekly homework, the spacing reminder, and what a quiz or test covers.

Everything here is derived from the event history, like the rest of the app:
no count is stored, so changing a target in November reads September correctly.

THE HOMEWORK WEEK runs Saturday to Friday, because the quiz is on Friday and
the cards should be done for it. The goal is two numbers, vocabulary cards and
grammar cards (50 and 50 unless the teacher changes them); a week is DONE when
both are met. What counts is decided once, in teacher.homework_cards: any
practice except a proctored quiz or exam, one card per card studied (a retype
after a near-miss is the same card), and each card at most once a day.

ON TIME OR LATE. A week met by Friday night is on time -- green, full credit.
A week can still be finished afterwards, and is then late -- yellow, partial
credit. The rule for which week a card goes to:

  1. a card counts for its own week while that week is short of the goal;
  2. once its own week is met, the card finishes the OLDEST unfinished earlier
     week, of the same kind.

The current week comes first on purpose. The other way round, a student who
missed one week and then did exactly the homework every week after would have
every later week pulled late to cover the one before, forever. This way doing
each week's homework keeps each week on time, and a missed week is made up by
doing extra, which is what "make it up" means.

Weeks before the teacher's start date don't exist for homework, and weeks the
teacher marks as no-homework (a vacation) are neither owed nor shown as missed;
cards done in them go to an unfinished earlier week, if there is one.

THE SPACING REMINDER is always present and quiet, because spacing is the whole
design of the app, and becomes a flag once a student has gone more than two
days without practicing. It never says anything about a grade.

AN ASSESSMENT covers teaching weeks. The words introduced in those weeks and
the grammar topics taught in them are what it tests, minus any topic the
teacher unticks. Only topics with approved questions on lessons already taught
can be practiced or counted, so a quiz page never offers practice on something
that has not been taught.

READINESS on an assessment page keeps solid / shaky / not yet exactly as they
are everywhere else, and adds one more number: what the student got right on
their most recent try. "Solid" means a memory that would hold three weeks
(fsrs.py), which takes reviews on several different days, so a student who
starts studying four days before a quiz rarely reaches it -- the right rule
for memory, and a hopeless-looking page for a kid who is doing the right thing. "Right last
time" is the number a few days of real study can move.
"""

import time

import dates

import badges
import drill
import stats
import teacher

DAY = 86400
IDLE_DAYS = 2                    # more than this without practice raises the flag
NOT_HOMEWORK = teacher.NOT_HOMEWORK
DEFAULT_TARGETS = teacher.DEFAULT_TARGETS
KINDS = ("vocab", "grammar")

HOMEWORK_STARTS_ON = 5           # Saturday, in time.localtime's Monday=0 numbering
DAY_LETTERS = ["S", "S", "M", "T", "W", "T", "F"]   # a homework week, Saturday first

# The first homework week when the teacher hasn't picked one: the week this
# feature went live. Weeks before it were never announced as Saturday-to-Friday,
# so they are not counted against anybody.
DEFAULT_HOMEWORK_FROM = "2026-09-26"


# --------------------------------------------------------------------------
# The homework week
# --------------------------------------------------------------------------

def _midnight(y, m, d):
    # mktime normalizes day 0 or day 35, and gets daylight saving right,
    # which adding 7 * 86400 does not.
    return time.mktime((y, m, d, 0, 0, 0, 0, 0, -1))


def week_start(now=None):
    """Midnight on the Saturday that opens this homework week."""
    lt = time.localtime(now or time.time())
    back = (lt.tm_wday - HOMEWORK_STARTS_ON) % 7
    return _midnight(lt.tm_year, lt.tm_mon, lt.tm_mday - back)


def week_end(start):
    """Midnight at the end of the Friday: the deadline."""
    lt = time.localtime(start)
    return _midnight(lt.tm_year, lt.tm_mon, lt.tm_mday + 7)


def week_key(ts):
    """A homework week's name: its Saturday, as YYYY-MM-DD."""
    return time.strftime("%Y-%m-%d", time.localtime(week_start(ts)))


def key_start(key):
    """The Saturday midnight of the homework week `key` (any date in it) falls in."""
    return week_start(time.mktime(time.strptime(str(key), "%Y-%m-%d")) + 12 * 3600)


def week_label(key):
    """"Saturday September 26 – Friday October 2" (dates.py)."""
    start = key_start(key)
    return dates.span(start, week_end(start) - 12 * 3600)


def _local_date(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _homework(events):
    return teacher.homework_events(events)


def _targets(targets):
    return dict(DEFAULT_TARGETS, **(targets or {}))


def weekly_progress(events, targets=None, now=None, badge_rule=None):
    """This homework week's cards against the goal, and which days had any.

    Returns {"vocab", "grammar", "targets", "days", "today", "met", "done",
    "due", "badges"} where `days` is seven booleans, Saturday first -- the
    picture of spacing -- and `due` is what a student reads: "due Friday",
    "due today". In a badge week, `badges` is badge_week's answer and grammar
    cards are not part of the goal.
    """
    now = now or time.time()
    start = week_start(now)
    targets = week_targets(targets, week_key(start), badge_rule)
    week_badges = None
    if badge_rule and week_key(start) >= badge_rule["from"]:
        week_badges = badge_week(events, badge_rule, start, week_end(start))
    mine = [e for e in _homework(events) if start <= e["timestamp"] <= now]
    counts = teacher.homework_counts(mine)
    days = [False] * 7
    for e in mine:
        days[(time.localtime(e["timestamp"]).tm_wday - HOMEWORK_STARTS_ON) % 7] = True
    today = (time.localtime(now).tm_wday - HOMEWORK_STARTS_ON) % 7
    met = {k: counts[k] >= targets[k] for k in KINDS}
    done = all(met.values()) and (week_badges is None or not week_badges["missing"])
    return {
        "vocab": counts["vocab"], "grammar": counts["grammar"],
        "targets": targets,
        "days": days,
        "today": today,
        "met": met,
        "done": done,
        "due": "due today" if today == 6 else "due Friday",
        "badges": week_badges,
    }


def homework_weeks(first, off=(), now=None, until=None):
    """Homework week keys from `first`'s week to this one (or to `until`'s),
    oldest first, leaving out the weeks the teacher marked as no homework."""
    now = now or time.time()
    last = key_start(until) if until else week_start(now)
    off = set(off or ())
    out = []
    start = key_start(first)
    while start <= last:
        k = time.strftime("%Y-%m-%d", time.localtime(start))
        if k not in off:
            out.append(k)
        start = week_end(start)
    return out


def week_targets(targets, key, badge_rule=None):
    """The card targets for one homework week. From the week grammar badges
    begin, grammar is badges rather than cards: its card target is 0."""
    t = _targets(targets)
    if badge_rule and str(key) >= badge_rule["from"]:
        t = dict(t, grammar=0)
    return t


def badge_week(events, rule, start, end):
    """The badges a homework week asks for and how each went.

    {"required": [ids], "on_time": [ids], "late": {id: ts}, "missing": [ids],
     "done_at": ts or None} -- done_at is when the last required badge was
    done, None while any is missing."""
    events = [e for e in events if badges.is_marker(e)]
    req = rule["required"](end)
    out = {"required": req, "on_time": [], "late": {}, "missing": [], "done_at": None}
    times = []
    for bid in req:
        how, ts = badges.done_for_week(events, bid, start, end)
        if how == "on time":
            out["on_time"].append(bid)
            times.append(ts)
        elif how == "late":
            out["late"][bid] = ts
            times.append(ts)
        else:
            out["missing"].append(bid)
    if not out["missing"]:
        out["done_at"] = max(times) if times else start
    return out


def homework_history(events, targets=None, weeks=(), now=None, badge_rule=None):
    """Every homework week in `weeks`, oldest first, with how it went.

    Each row: key, label, start, end, counts {vocab, grammar} (what went toward
    the goal, so never above it), late {vocab, grammar} (the part that arrived
    after Friday), done_at, and status -- "on time", "late", "not done", or
    "this week" while it is still open. The allocation rule is in the module
    docstring.

    `badge_rule` ({"from": week key, "required": f(deadline) -> badge ids})
    switches the grammar half to badges from that week on: those weeks also
    carry "badges" (badge_week) and are done when the vocabulary is met AND
    every badge is up to date. A badge passed after Friday makes the week late.
    """
    now = now or time.time()
    rows = []
    for k in weeks:
        start = key_start(k)
        rows.append({"key": k, "label": week_label(k), "start": start,
                     "end": week_end(start),
                     "targets": week_targets(targets, k, badge_rule),
                     "counts": {x: 0 for x in KINDS}, "late": {x: 0 for x in KINDS},
                     "done_at": None, "badges": None})
    by_key = {r["key"]: r for r in rows}
    for r in rows:
        if badge_rule and r["key"] >= badge_rule["from"]:
            r["badges"] = badge_week(events, badge_rule, r["start"], r["end"])

    def complete(r):
        cards = all(r["counts"][x] >= r["targets"][x] for x in KINDS)
        return cards and (r["badges"] is None or r["badges"]["done_at"] is not None)

    def give(r, kind, ts, late):
        r["counts"][kind] += 1
        if late:
            r["late"][kind] += 1

    if rows:
        first = rows[0]["start"]
        for e in teacher.homework_cards(events):
            ts = e["timestamp"]
            if ts < first or ts > now:
                continue
            kind = teacher.kind_of(e)
            own_key = week_key(ts)
            own = by_key.get(own_key)
            if own is not None and own["counts"][kind] < own["targets"][kind]:
                give(own, kind, ts, late=False)
                r = own
            else:
                r = None
                for cand in rows:
                    if cand["key"] >= own_key:
                        break
                    if cand["counts"][kind] < cand["targets"][kind]:
                        give(cand, kind, ts, late=True)
                        r = cand
                        break
            # The moment the cards are met. A badge week is done when the
            # badges are too, whichever came last.
            if r is not None and r.get("cards_at") is None and all(
                    r["counts"][x] >= r["targets"][x] for x in KINDS):
                r["cards_at"] = ts

    for r in rows:
        if r.get("cards_at") is None and all(r["targets"][x] <= 0 for x in KINDS):
            r["cards_at"] = r["start"]
        r["total"] = sum(r["counts"].values())
        r["goal"] = sum(r["targets"][x] for x in KINDS)
        if complete(r):
            r["done_at"] = max(r.get("cards_at") or r["start"],
                               (r["badges"] or {}).get("done_at") or r["start"])
            late = any(r["late"].values()) or bool((r["badges"] or {}).get("late"))
            r["status"] = "late" if late else "on time"
        elif now < r["end"]:
            r["status"] = "this week"
        else:
            r["status"] = "not done"
    return rows


def all_time(events, history=()):
    """What a student has done since the start: cards, days, and weeks."""
    counts = teacher.homework_counts(events)
    statuses = [r["status"] for r in history]
    return {"vocab": counts["vocab"], "grammar": counts["grammar"],
            "cards": counts["vocab"] + counts["grammar"],
            "days": len({_local_date(e["timestamp"]) for e in _homework(events)}),
            "on_time": statuses.count("on time"), "late": statuses.count("late"),
            "not_done": statuses.count("not done")}


def days_since_practice(events, now=None):
    """Whole calendar days since the last practice, or None if there has been
    none. Practicing yesterday is 1; today is 0."""
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
    already taught. A topic outside it cannot be practiced, so it is left off
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
    return dates.day(date_str)
