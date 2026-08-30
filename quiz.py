"""
Proctored quizzes: a frozen, hand-picked set of questions answered straight
through, submitted once, then reviewed.

What makes this different from practice, and why:

  - NO FEEDBACK DURING. Nothing is graded until the student submits. In practice
    mode instant feedback is the point; in a quiz it would hand out the answers.
  - CLOSE IS ACCEPTED SILENTLY. A one-letter typo cannot re-prompt ("check your
    spelling") without being a free hint, so it is accepted at the time and
    surfaces on the review screen as `close`. It is logged as close, never
    silently promoted to right and never punished as wrong.
  - THE PAPER IS FROZEN. The item ids are stored on the quiz, so every student
    sits the same questions in the same order, and re-importing the bank later
    cannot change a quiz someone has already taken.
  - WORK IS SAVED AS THEY GO, graded only at submit, so a dead phone or a closed
    tab loses nothing and a student can resume where they left off.

Grading reuses the practice graders, so there is exactly one implementation of
what counts as right.
"""

import time
import uuid

import practice

# Formats whose answer the app cannot grade mechanically. The student types
# during the quiz, sees the model answer only on the review screen afterwards,
# and reports there how they did.
SELF_REPORTED = {"self-check"}


def new_quiz_id():
    return uuid.uuid4().hex[:8]


def answer_is_blank(fmt, value):
    if value is None:
        return True
    if fmt == "boxes":
        return not any(str(v).strip() for v in (value or []))
    if fmt == "tag-then-translate":
        cases = (value or {}).get("case") or []
        jobs = (value or {}).get("job") or []
        return not any(str(v).strip() for v in list(cases) + list(jobs))
    return not str(value).strip()


def grade_attempt(items_by_id, item_ids, answers):
    """Grade a whole submitted attempt.

    Returns {item_id: result_dict}. Each result carries `result`
    (right|close|wrong|self|unanswered) plus whatever detail the review screen
    needs to show the student what happened.
    """
    out = {}
    for iid in item_ids:
        item = items_by_id.get(iid)
        if item is None:
            out[iid] = {"result": "unanswered", "detail": "question no longer available"}
            continue
        fmt = item.get("format")
        value = answers.get(iid)

        if answer_is_blank(fmt, value):
            out[iid] = {"result": "unanswered"}
            continue

        if fmt == "choice":
            res = practice.grade_choice(item, value)
            out[iid] = {"result": res, "picked": value}

        elif fmt == "boxes":
            res, box_results = practice.grade_boxes(item, list(value))
            out[iid] = {"result": res,
                        "boxes": [dict(label=b.label, response=b.response,
                                       box_result=b.result, accepted=b.accepted,
                                       rule=b.rule) for b in box_results]}

        elif fmt == "tag-then-translate":
            cases = (value or {}).get("case") or []
            jobs = (value or {}).get("job") or []
            res, tag_results = practice.grade_tags(item, list(cases), list(jobs))
            out[iid] = {"result": res, "tags": tag_results,
                        "typed": (value or {}).get("typed", "")}

        else:                                   # self-check
            out[iid] = {"result": "self", "typed": str(value)}

    return out


def summarise(results):
    """Counts for the student's summary line. `close` is reported on its own —
    accepted, but visibly a spelling matter rather than a clean right."""
    s = {"right": 0, "close": 0, "wrong": 0, "unanswered": 0, "self": 0}
    for r in results.values():
        key = r.get("result", "unanswered")
        if key in s:
            s[key] += 1
    s["total"] = len(results)
    # What the student "got": right plus close. Deliberately not called a score,
    # and deliberately not a percentage -- nothing here produces a grade.
    s["accepted"] = s["right"] + s["close"]
    return s


def answered_count(items_by_id, item_ids, answers):
    n = 0
    for iid in item_ids:
        item = items_by_id.get(iid)
        fmt = item.get("format") if item else None
        if not answer_is_blank(fmt, answers.get(iid)):
            n += 1
    return n


def unanswered_positions(items_by_id, item_ids, answers):
    """1-based positions still blank, for the check-before-submit screen."""
    out = []
    for i, iid in enumerate(item_ids, start=1):
        item = items_by_id.get(iid)
        fmt = item.get("format") if item else None
        if answer_is_blank(fmt, answers.get(iid)):
            out.append(i)
    return out


def events_for_attempt(results, items_by_id, context, version="v1"):
    """The rows to append to the event record at submit — one per question, so
    proctored work sits in the same history as practice and is told apart by
    `context`. Unanswered questions are recorded as wrong: leaving it blank is
    an outcome, not an absence of data."""
    rows = []
    for iid, r in results.items():
        item = items_by_id.get(iid) or {}
        res = r.get("result")
        if res == "self":
            continue                     # recorded when the student self-reports
        rows.append({
            "item_id": iid,
            "spec_node_id": item.get("node"),
            "response": _response_summary(r)[:200],
            "result": "wrong" if res == "unanswered" else res,
            "context": context,
            "version": version,
        })
    return rows


def _response_summary(r):
    if "picked" in r:
        return str(r["picked"])
    if "boxes" in r:
        return " | ".join(str(b.get("response") or "") for b in r["boxes"])
    if "tags" in r:
        return " | ".join(f"{t.get('case_response','')}/{t.get('job_response','')}"
                          for t in r["tags"])
    if "typed" in r:
        return str(r["typed"])
    return ""
