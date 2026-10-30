"""
Grammar badges: the Grammar tab is a map of badges, each a short check on a
group of spec topics (badges.yaml), and keeping them up to date is the grammar
half of the weekly homework (from the week the teacher picks).

EARNING. A badge check is EARN_N questions drawn across the badge's topics
(approved questions, on lessons already taught). EARN_PASS of them right earns
the badge. Once earned, a badge FADES: a shorter REFRESH_N-question check keeps
it. Right means the app's check said right or close; on a question only the
student can judge, their grade of Hard or better.

THE FORGETTING TIMER is the same memory model as everything else (fsrs.py),
run on the badge itself: every finished check is one review of the badge's
card -- passed is Good, not passed is Again. The card's due date is when the
badge needs a refresh; its stability says solid (holds three weeks or more) or
shaky. A first pass holds about three days, and each refresh on time stretches
it (about 10 days, then a month, then more), so a student who keeps up does a
handful of quick refreshes a week, fewer as the year goes on.

THE RECORD. A finished check is one event, item "badge:<id>", context "badge",
result right (passed) or wrong, rating Good or Again, the score in `response`.
The questions inside it are ordinary practice events. Nothing else is stored:
like every other figure in the app, a badge's state is replayed from history.

HOMEWORK. A badge is up to date for a homework week when it was passed during
the week, or it did not need a refresh at the Friday deadline. One passed after
the deadline makes the week late. Which badges a week asks for: every badge
whose first topic was taught by that Friday and that has questions to ask.
"""

import math
import os
import time

import yaml

import fsrs

NLE_PREFIX = "NLE-"          # a past National Latin Exam question (nle.PREFIX)

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "badges.yaml")

PREFIX = "badge:"
CONTEXT = "badge"
EARN_N, EARN_PASS = 6, 5 / 6.0
REFRESH_N, REFRESH_PASS = 3, 2 / 3.0


def load(path=PATH):
    """(rows, badges): rows [{id, label}], badges [{id, row, title, about, nodes}]."""
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    rows = [{"id": r["id"], "label": r["label"]} for r in doc.get("rows") or []]
    out = []
    for b in doc.get("badges") or []:
        out.append({"id": str(b["id"]), "row": b.get("row"), "title": b.get("title", b["id"]),
                    "about": b.get("about", ""), "nodes": list(b.get("nodes") or [])})
    return rows, out


def item_id(badge_id):
    return PREFIX + badge_id


def is_marker(event):
    return str(event.get("item_id") or "").startswith(PREFIX)


# --------------------------------------------------------------------------
# What a badge covers, and when it appears
# --------------------------------------------------------------------------

def _when(node):
    return str(node.get("day") or node.get("week") or "")


def first_taught(badge, spec):
    """The date (YYYY-MM-DD) the badge's first topic is taught."""
    dates = [_when(spec[n]) for n in badge["nodes"] if n in spec]
    return min(dates) if dates else ""


def pool(badge, approved, taught):
    """The approved questions a check on this badge may ask, in id order. A
    question that leans on another topic too (`needs`, as past-NLE questions
    do) waits until that one has been taught as well."""
    taught = set(taught)
    nodes = set(badge["nodes"]) & taught
    return sorted((it for it in approved if it.get("node") in nodes
                   and all(n in taught for n in it.get("needs") or [])),
                  key=lambda it: str(it.get("id")))


def available(badges, spec, approved, on_date):
    """The badges on the map on `on_date`: first topic taught, and at least one
    approved question on a taught topic."""
    import practice
    taught = practice.taught_nodes(spec, on_date)
    return [b for b in badges
            if first_taught(b, spec) and first_taught(b, spec) <= on_date
            and pool(b, approved, taught)]


def foundations(badges, spec):
    """{badge id: [badge ids it builds on]}, from the spec's prereqs."""
    owner = {n: b["id"] for b in badges for n in b["nodes"]}
    out = {}
    for b in badges:
        pre = []
        for n in b["nodes"]:
            for p in (spec.get(n) or {}).get("prereqs") or []:
                o = owner.get(p)
                if o and o != b["id"] and o not in pre:
                    pre.append(o)
        out[b["id"]] = pre
    return out


def direct_foundations(badges, spec):
    """foundations() with the shortcuts taken out: B builds directly on A unless
    A is already underneath another of B's foundations. Genitive builds on
    Second declension, which builds on First declension -- so no line from
    First declension straight to Genitive. These are the map's lines."""
    found = foundations(badges, spec)
    below = {}

    def under(bid, seen=()):
        if bid not in below:
            out = set()
            for p in found.get(bid, []):
                if p not in seen:
                    out |= {p} | under(p, seen + (bid,))
            below[bid] = out
        return below[bid]

    return {bid: [p for p in pre if not any(p in under(q) for q in pre if q != p)]
            for bid, pre in found.items()}


def levels(badges, spec):
    """{badge id: level}: 0 for a badge that builds on nothing, otherwise one
    below the deepest badge it builds on -- the rows of the tree."""
    found = foundations(badges, spec)
    out = {}

    def level(bid, seen=()):
        if bid not in out:
            pre = [p for p in found.get(bid, []) if p not in seen]
            out[bid] = 1 + max((level(p, seen + (bid,)) for p in pre), default=-1)
        return out[bid]

    for b in badges:
        level(b["id"])
    return out


# --------------------------------------------------------------------------
# A student's badge
# --------------------------------------------------------------------------

def markers(events, badge_id, until=None):
    key = item_id(badge_id)
    return sorted((e for e in events if e.get("item_id") == key
                   and (until is None or e["timestamp"] < until)),
                  key=lambda e: e["timestamp"])


def status(events, badge_id, now=None):
    """{"earned", "due", "state", "days_left", "next"} for one badge.

    state: not yet | shaky | solid (fsrs.state on the badge's card).
    due:   earned, and it needs a refresh now.
    days_left: whole days until it needs one (0 when due; None if not earned).
    next:  "earn" or "refresh" -- which check the button starts.
    """
    now = now or time.time()
    ms = markers(events, badge_id, until=now + 1)
    earned = any(e.get("result") == "right" for e in ms)
    card = fsrs.replay(ms) if ms else None
    due = bool(earned and card is not None and card.due <= now)
    days = None
    if earned and card is not None:
        days = max(0, int(math.floor((card.due - now) / fsrs.DAY)))
    return {"earned": earned, "due": due,
            "state": fsrs.state(card) if earned else "not yet",
            "days_left": days, "next": "refresh" if earned else "earn",
            "up_to_date": earned and not due}


def done_for_week(events, badge_id, start, end):
    """(how, when) for one badge in one homework week.

    ("on time", ts) -- passed during the week, or did not need a refresh at the
                       deadline (ts is then the week's start);
    ("late", ts)    -- not up to date at the deadline, passed afterwards;
    (None, None)    -- neither.
    """
    ms = markers(events, badge_id)
    passes = [e["timestamp"] for e in ms if e.get("result") == "right"]
    during = [t for t in passes if start <= t < end]
    if during:
        return "on time", during[0]
    before = [e for e in ms if e["timestamp"] < end]
    if any(e.get("result") == "right" for e in before):
        card = fsrs.replay(before)
        if card is not None and card.due > end:
            return "on time", start
    after = [t for t in passes if t >= end]
    if after:
        return "late", after[0]
    return None, None


# --------------------------------------------------------------------------
# A check
# --------------------------------------------------------------------------

def check_size(mode, pool_size):
    return min(EARN_N if mode == "earn" else REFRESH_N, pool_size)


def needed(mode, n):
    """Right answers needed to pass a check of n questions."""
    share = EARN_PASS if mode == "earn" else REFRESH_PASS
    return int(math.ceil(n * share - 1e-9))


def pick(items, events, n):
    """n questions spread across the badge's topics: one per topic in turn,
    and within a topic the one this student met least recently (never first),
    so a retake asks different questions where the badge has them.

    Every check includes at least one past-NLE question when the badge has
    one (the teacher's rule, October 2026), so students meet the exam's kind
    of question from their first check: the least recently met one takes the
    place of the last question picked on its own topic (or the last question
    picked, if its topic got none)."""
    last = {}
    for e in events:
        last[e.get("item_id")] = max(last.get(e.get("item_id"), 0), e["timestamp"])
    by_node = {}
    for it in items:
        by_node.setdefault(it.get("node"), []).append(it)
    queues = []
    for node in sorted(by_node):
        queues.append(sorted(by_node[node], key=lambda it: (last.get(it.get("id"), 0),
                                                             str(it.get("id")))))
    # Topics least practiced lately go first, so a short refresh still moves around.
    queues.sort(key=lambda q: last.get(q[0].get("id"), 0))
    out = []
    while len(out) < n and any(queues):
        for q in queues:
            if q and len(out) < n:
                out.append(q.pop(0))
    exam = [it for it in items if str(it.get("id") or "").startswith(NLE_PREFIX)]
    if out and exam and not any(str(it.get("id") or "").startswith(NLE_PREFIX) for it in out):
        best = min(exam, key=lambda it: (last.get(it.get("id"), 0), str(it.get("id"))))
        same = [i for i, it in enumerate(out) if it.get("node") == best.get("node")]
        out[same[-1] if same else len(out) - 1] = best
    return out


def answered(run_items, events, started):
    """[(item id, correct)] for the questions of a check answered so far, in
    order: each question's first graded answer since the check started. A
    near-miss waiting for its retype (rating 0) is not an answer yet."""
    out = []
    for iid in run_items:
        mine = [e for e in events if e.get("item_id") == iid and e["timestamp"] >= started
                and e.get("rating") != 0]
        if not mine:
            break
        e = min(mine, key=lambda x: x["timestamp"])
        out.append((iid, is_right(e)))
    return out


def is_right(event):
    if event.get("result") in ("right", "close"):
        return True
    if event.get("result") == "wrong":
        return False
    return (event.get("rating") or 0) >= fsrs.HARD
