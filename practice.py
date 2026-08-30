"""
Grammar practice — selection and grading.

The student-facing counterpart to the review tool: it serves questions the
teacher has APPROVED, checks them with the shared answer-checker, and on a miss
shows the what-went-wrong menu so the mistake is classified rather than just
counted.

Three rules from the exemplar file shape everything here:

  - "An item is bounded by what has been taught on the date it is used."
    Selection is filtered by each node's teaching date in the spec, so a
    question never arrives before its lesson.

  - "A CLOSE result never triggers the what-went-wrong menu." Close means the
    spelling needs another look, not that the student was wrong.

  - The menu's three fixed choices are appended here, never written per item,
    and the last one ("I think my answer should be right") flags the question
    for re-review. That is the live-fire path.

Grading is per box, not per item: a student who gets four of six verb endings
sees four right and two wrong, which is the whole reason v2 of the exemplar
file exists.
"""

import time
from collections import namedtuple

from answercheck import check as check_answer

# The three fixed menu choices. Never written per item; appended to every
# item's own what_went_wrong list. The third is the contest path.
FIXED_MENU = [
    {"key": "dont_know", "text": "I don't know", "node": None},
    {"key": "didnt_know_word", "text": "I didn't know the word", "node": None},
    {"key": "should_be_right", "text": "I think my answer should be right", "node": None},
]

CONTEST_KEY = "should_be_right"

BoxResult = namedtuple("BoxResult", ["label", "response", "result", "accepted", "rule"])


# --------------------------------------------------------------------------
# What has been taught by now
# --------------------------------------------------------------------------

def taught_nodes(spec, on_date=None):
    """Node ids whose teaching day has arrived. Module-paced nodes (day: null)
    fall back to their week. A node with neither is treated as available."""
    if on_date is None:
        on_date = time.strftime("%Y-%m-%d")
    out = set()
    for nid, n in spec.items():
        when = n.get("day") or n.get("week")
        if when is None or str(when) <= on_date:
            out.add(nid)
    return out


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

def _seen_stats(events, item_id):
    evs = [e for e in events if e.get("item_id") == item_id]
    if not evs:
        return 0, 0.0, None
    last = max(e["timestamp"] for e in evs)
    misses = sum(1 for e in evs if e["result"] == "wrong")
    return len(evs), last, misses


def select_question(items, events, allowed_nodes=None, node_id=None, now=None):
    """Pick the next question.

    Unseen questions first; then the ones missed before; then least recently
    seen. Deterministic, so a refresh does not reshuffle the queue.
    """
    now = now or time.time()
    pool = list(items)
    if node_id:
        pool = [i for i in pool if i.get("node") == node_id]
    elif allowed_nodes is not None:
        pool = [i for i in pool if i.get("node") in allowed_nodes]
    if not pool:
        return None

    scored = []
    for it in pool:
        seen, last, misses = _seen_stats(events, it.get("id"))
        # unseen (0) sorts before seen; then more misses first; then oldest.
        scored.append((seen, -(misses or 0), last, it.get("id"), it))
    scored.sort(key=lambda s: (s[0], s[1], s[2], s[3]))
    return scored[0][4]


def practiceable(items, allowed_nodes):
    """Questions whose node has been taught. Used for the empty-state message."""
    return [i for i in items if i.get("node") in allowed_nodes]


# --------------------------------------------------------------------------
# Grading
# --------------------------------------------------------------------------

def grade_choice(item, picked):
    """Multiple choice: right or wrong. There is no 'close' when picking."""
    return "right" if picked == item.get("answer") else "wrong"


def _box_accepted(box):
    return [a for a in (box.get("answer") or []) if a is not None]


def grade_boxes(item, responses):
    """Grade a boxes item. Returns (overall, [BoxResult...]).

    Honours order_matters: when order does not matter, any box may hold any
    correct answer, so responses are matched to boxes rather than compared
    position by position.

    A box carrying `answer_rule` instead of a list cannot be checked
    mechanically; it is returned with result 'self' and left out of the overall
    result. (Only one item in the bank uses this — the trans- derivative box.)
    """
    boxes = item.get("boxes") or []
    mm = bool(item.get("macron_matters"))
    responses = list(responses) + [""] * (len(boxes) - len(responses))

    if item.get("order_matters") is False:
        results = _match_unordered(boxes, responses, mm)
    else:
        results = []
        for box, resp in zip(boxes, responses):
            accepted = _box_accepted(box)
            if not accepted and box.get("answer_rule"):
                results.append(BoxResult(box.get("label", ""), resp, "self", [], box["answer_rule"]))
            else:
                results.append(BoxResult(box.get("label", ""), resp,
                                         check_answer(resp, accepted, macron_matters=mm),
                                         accepted, None))

    scored = [r.result for r in results if r.result != "self"]
    if not scored:
        overall = "self"
    elif all(r == "right" for r in scored):
        overall = "right"
    elif any(r == "wrong" for r in scored):
        overall = "wrong"
    else:
        overall = "close"
    return overall, results


def _match_unordered(boxes, responses, macron_matters):
    """Match responses to boxes when order is irrelevant.

    Two passes: claim exact matches first so a response that is right for one
    box is never spent on a box it is merely close to, then hand out the
    remainder.
    """
    n = len(boxes)
    accepted = [_box_accepted(b) for b in boxes]
    rules = [b.get("answer_rule") for b in boxes]
    taken_box = [False] * n
    assign = [None] * len(responses)

    # Pass 1: exact matches.
    for ri, resp in enumerate(responses):
        for bi in range(n):
            if taken_box[bi] or not accepted[bi]:
                continue
            if check_answer(resp, accepted[bi], macron_matters=macron_matters) == "right":
                assign[ri] = bi
                taken_box[bi] = True
                break

    # Pass 2: close matches against what is left.
    for ri, resp in enumerate(responses):
        if assign[ri] is not None:
            continue
        for bi in range(n):
            if taken_box[bi] or not accepted[bi]:
                continue
            if check_answer(resp, accepted[bi], macron_matters=macron_matters) == "close":
                assign[ri] = bi
                taken_box[bi] = True
                break

    # Pass 3: whatever remains, in order, so every response reports somewhere.
    leftovers = [bi for bi in range(n) if not taken_box[bi]]
    for ri in range(len(responses)):
        if assign[ri] is None and leftovers:
            assign[ri] = leftovers.pop(0)

    results = []
    for ri, resp in enumerate(responses):
        bi = assign[ri]
        if bi is None:
            results.append(BoxResult("", resp, "wrong", [], None))
            continue
        label = boxes[bi].get("label", "")
        if not accepted[bi] and rules[bi]:
            results.append(BoxResult(label, resp, "self", [], rules[bi]))
        else:
            results.append(BoxResult(label, resp,
                                     check_answer(resp, accepted[bi], macron_matters=macron_matters),
                                     accepted[bi], None))
    return results


def grade_tags(item, case_responses, job_responses):
    """Tag-then-translate: the case and job labels are checked, the English is
    self-checked afterwards."""
    tags = item.get("tag_boxes") or []
    results = []
    for i, tb in enumerate(tags):
        c = case_responses[i] if i < len(case_responses) else ""
        j = job_responses[i] if i < len(job_responses) else ""
        results.append({
            "word": tb.get("word"),
            "case_response": c,
            "case_result": check_answer(c, tb.get("case") or []),
            "case_accepted": tb.get("case") or [],
            "job_response": j,
            "job_result": check_answer(j, tb.get("job") or []),
            "job_accepted": tb.get("job") or [],
        })
    flat = [r["case_result"] for r in results] + [r["job_result"] for r in results]
    if all(x == "right" for x in flat):
        overall = "right"
    elif any(x == "wrong" for x in flat):
        overall = "wrong"
    else:
        overall = "close"
    return overall, results


# --------------------------------------------------------------------------
# The what-went-wrong menu
# --------------------------------------------------------------------------

def menu_for(item):
    """The item's own reasons, each tagged to the node that explains it, plus
    the three fixed choices. Never shown for a CLOSE result."""
    own = []
    for i, w in enumerate(item.get("what_went_wrong") or []):
        own.append({"key": f"w{i}", "text": w.get("text", ""), "node": w.get("node")})
    return own + [dict(m) for m in FIXED_MENU]


def response_summary(item, box_results=None, picked=None, typed=None):
    """What to store in the event's `response` field: what the student actually
    entered, in one short string."""
    if picked is not None:
        opts = item.get("options") or {}
        return f"{picked}: {opts.get(picked, '')}"[:200]
    if box_results:
        return " | ".join((r.response or "") for r in box_results)[:200]
    return (typed or "")[:200]
