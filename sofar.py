"""Your Latin so far: a student's progress against everything taught to date.

Standards-based grading has no homework to hand in, so the home screen stops
counting cards toward a weekly quota and asks a different question: of the
words and grammar the class has met so far, how much has this student
practiced, and how much of it would they still remember in three weeks
(solid, fsrs.SOLID_DAYS)?

Everything here is counted the way the rest of the app counts it -- the same
solid / shaky / not yet (fsrs.state), the same taught topics (the Progress
page's denominator), the same badge status -- so the home screen, the
Progress page and the badge map never disagree.
"""

import time

import badges as badges_mod
import drill
import fsrs
import stats

STATES = ("solid", "shaky", "not yet")


def taught_words(words, today):
    """The drill words whose week has started by `today` (YYYY-MM-DD)."""
    return [w for w in words
            if drill._WEEK_MONDAY.get(w.get("week"), "9999") <= today]


def _tally(states):
    out = {s: 0 for s in STATES}
    for s in states:
        out[s] = out.get(s, 0) + 1
    out["total"] = sum(out[s] for s in STATES)
    return out


def summary(words, events, spec, universe, badge_list=None, approved=None,
            badges_on=False, now=None):
    """{"words", "grammar", "badges", "week"} for the home screen.

    words:   {solid, shaky, not yet, total, practiced}, over taught words.
    grammar: the same, over `universe` (taught topics with approved
             questions -- the Progress page's denominator).
    badges:  {"open", "earned", "fading": [ids]} when badges are on, else None.
    week:    this week's new material: {"label", "words", "words_started",
             "topics", "topics_started"}.
    """
    now = now or time.time()
    today = time.strftime("%Y-%m-%d", time.localtime(now))

    taught = taught_words(words, today)
    rows = drill.progress_table(taught, events, now=now)
    w = _tally(r.state for r in rows)
    w["practiced"] = sum(1 for r in rows if r.attempts)

    by_node = stats.group_events(events, lambda e: e.get("spec_node_id"))
    gstate = {nid: fsrs.state(fsrs.replay(by_node.get(nid, []))) for nid in universe}
    g = _tally(gstate.values())
    g["practiced"] = sum(1 for nid in universe if by_node.get(nid))

    b = None
    if badges_on and badge_list is not None:
        open_ = badges_mod.available(badge_list, spec, approved or [], today)
        st = {x["id"]: badges_mod.status(events, x["id"], now=now) for x in open_}
        b = {"open": len(open_), "earned": sum(1 for s in st.values() if s["earned"]),
             "fading": [bid for bid, s in st.items() if s["due"]]}

    this_week = drill.current_week(now)
    monday = drill._WEEK_MONDAY.get(this_week, "")
    new_words = [r for r in rows if r.week == this_week]
    new_topics = [nid for nid in universe if str((spec.get(nid) or {}).get("week") or "") == monday]
    week = {"label": drill.WEEK_LABELS.get(this_week, ""),
            "words": len(new_words), "words_started": sum(1 for r in new_words if r.attempts),
            "topics": len(new_topics),
            "topics_started": sum(1 for nid in new_topics if by_node.get(nid))}
    return {"words": w, "grammar": g, "badges": b, "week": week}
