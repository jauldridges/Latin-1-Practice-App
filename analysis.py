"""
Practice data for analysis: every answer, every sitting, every skill, one row
per student -- laid out so it can be set beside an exam's scores and the
gradebook, and split around the exam's date.

Student ID numbers only, like every other export. The text a student typed is
left out on purpose: it is not needed to measure practice, and a free-text box
is the one place a name could ride along.

Nothing here reads the database; server.py gathers the rows and zips the files.

Time on task is an ESTIMATE, from the gaps between answers (see README.txt in
the zip, which is DICTIONARY below): the app records when each answer was
given, not when a student looked away.
"""

import datetime
import statistics
import time

import fsrs
import rush

QUIZ_CONTEXTS = ("quiz", "exam")
SITTING_GAP = rush.SITTING_GAP          # 30 minutes without an answer ends a sitting
CARD_CAP_S = 300                        # one card never counts for more than 5 minutes
FIRST_CARD_S = 20                       # a sitting's first card, when its timing is missing
GRADE_NAMES = {0: "retype", 1: "again", 2: "hard", 3: "good", 4: "easy"}


# --------------------------------------------------------------------------
# One answer
# --------------------------------------------------------------------------

def activity(e):
    """vocab | grammar | reading | quiz (an in-app proctored quiz or exam)."""
    if "_act" not in e:
        e["_act"] = _activity(e)
    return e["_act"]


def _activity(e):
    if (e.get("context") or "practice") in QUIZ_CONTEXTS:
        return "quiz"
    iid = str(e.get("item_id") or "")
    if iid.startswith("vocab:"):
        return "vocab"
    if iid.startswith("read:"):
        return "reading"
    return "grammar"


def skill_of(e):
    """(kind, skill_id): a vocabulary word, a grammar topic (spec node) or a story."""
    if "_skill" not in e:
        e["_skill"] = _skill_of(e)
    return e["_skill"]


def _skill_of(e):
    iid = str(e.get("item_id") or "")
    if iid.startswith("vocab:"):
        parts = iid.split(":")
        return ("vocab", parts[1] if len(parts) > 2 else iid)
    if iid.startswith("read:"):
        return ("reading", iid.split(":")[1])
    return ("grammar", e.get("spec_node_id") or "")


def local_date(ts):
    return datetime.date.fromtimestamp(ts)


def exam_start(exam_date):
    """Midnight, school time, at the start of the exam day."""
    return time.mktime((exam_date.year, exam_date.month, exam_date.day, 0, 0, 0, 0, 0, -1))


def relation(ts, exam_date):
    """(days_before_exam, phase). 1 is the day before, 0 the exam day itself."""
    if exam_date is None:
        return ("", "")
    d = (exam_date - local_date(ts)).days
    return (d, "before" if d > 0 else ("exam day" if d == 0 else "after"))


def _pct(num, den):
    return "" if not den else int(round(100.0 * num / den))


def _accuracy(evs):
    """Share right, close counted as right (the app's own rule: teacher.accuracy)."""
    scored = [e for e in evs if e.get("result") in ("right", "close", "wrong")]
    return _pct(sum(1 for e in scored if e["result"] != "wrong"), len(scored))


def _cards(evs):
    """Cards studied. A near-miss the student retyped is one card, not two: since
    self-grading the near-miss is stored with rating 0 and is dropped; before
    it, a "close" followed straight away by the same card is the retype's first
    half. Unlike stats.collapse_retries, the same card met again later (the
    next day, or relearned after Again) stays a second card."""
    evs = sorted(evs, key=lambda e: e["timestamp"])
    out = []
    for i, e in enumerate(evs):
        if e.get("rating") == 0:
            continue
        nxt = evs[i + 1] if i + 1 < len(evs) else None
        if (e.get("rating") is None and e.get("result") == "close" and nxt is not None
                and nxt.get("item_id") == e.get("item_id")
                and nxt["timestamp"] - e["timestamp"] <= SITTING_GAP):
            continue
        out.append(e)
    return out


def _secs(ms, cap):
    return None if ms is None else min(max(int(ms), 0), cap * 1000) / 1000.0


def _median(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else ""


# --------------------------------------------------------------------------
# Sittings and time
# --------------------------------------------------------------------------

def sittings(practice):
    """Practice answers (oldest first) cut into sittings, each answer given its
    estimated seconds: the gap since the answer before it, capped at five
    minutes; a sitting's first answer gets its own timing (answering plus
    grading), or 20 seconds when that is missing."""
    out = []
    for e in practice:
        if out and e["timestamp"] - out[-1][-1]["timestamp"] <= SITTING_GAP:
            gap = e["timestamp"] - out[-1][-1]["timestamp"]
            e["_secs"] = min(gap, CARD_CAP_S)
            out[-1].append(e)
        else:
            own = (_secs(e.get("latency_ms"), 120) or 0) + (_secs(e.get("grade_ms"), 60) or 0)
            e["_secs"] = own or FIRST_CARD_S
            out.append([e])
    return out


def _minutes(evs):
    return round(sum(e.get("_secs", 0) for e in evs) / 60.0, 1)


# --------------------------------------------------------------------------
# The files
# --------------------------------------------------------------------------

def build(events, roster_rows, catalog, exam_date=None, exam_nodes=(), exam_words=(),
          exam_title="", homework=None, quiz_rows=(), item_formats=None, now=None):
    """{filename: [header, row, row, ...]} for every CSV in the download.

    events      every answer (store.all_events), any order
    roster_rows the class list (student_id, section, active)
    catalog     {(kind, skill_id): {"name", "unit", "week"}} -- every skill there is
    exam_date   a datetime.date, or None for no split
    exam_nodes / exam_words  what the exam covered (goals.scope), for on_exam
    homework    {student_id: goals.all_time summary}
    quiz_rows   in-app quiz attempts, each {quiz_id, title, context, student_id,
                started_at, submitted_at, results}
    """
    now = now or time.time()
    homework = homework or {}
    item_formats = item_formats or {}
    block = {r["student_id"]: r.get("section") or "" for r in roster_rows}
    on_exam_set = {("grammar", n) for n in exam_nodes} | {("vocab", w) for w in exam_words}
    cutoff = exam_start(exam_date) if exam_date else None

    def on_exam(key):
        if exam_date is None or not on_exam_set:
            return ""
        return "yes" if key in on_exam_set else "no"

    by_student = {}
    for e in sorted(events, key=lambda x: x["timestamp"]):
        by_student.setdefault(e["student_id"], []).append(dict(e))
    students = sorted(set(block) | set(by_student), key=lambda s: (block.get(s, "~"), s))

    answers = [["answer_id", "student_id", "block", "date", "time", "weekday", "sitting",
                "days_before_exam", "phase", "activity", "context", "item_id", "format",
                "direction", "skill_kind", "skill_id", "skill_name", "on_exam", "result",
                "self_grade", "answer_seconds", "grade_seconds", "est_seconds", "rushed"]]
    sit_rows = [["student_id", "block", "sitting", "date", "weekday", "start", "end",
                 "days_before_exam", "phase", "span_minutes", "est_minutes", "cards",
                 "vocab_cards", "grammar_cards", "reading_answers", "accuracy_pct",
                 "rushed_cards", "exam_material_cards", "grammar_topics", "vocab_words"]]
    skill_rows = [["student_id", "block", "skill_kind", "skill_id", "skill_name", "unit",
                   "week_taught", "on_exam", "cards", "cards_before_exam", "right", "close",
                   "wrong", "accuracy_pct", "accuracy_before_exam_pct", "days_practiced",
                   "first_practiced", "last_practiced", "est_minutes", "state_at_exam",
                   "state_now", "holds_days_now"]]
    student_rows = [_STUDENT_HEADER]

    for sid in students:
        evs = by_student.get(sid, [])
        practice = [e for e in evs if activity(e) != "quiz"]
        quiz = [e for e in evs if activity(e) == "quiz"]
        sits = sittings(practice)
        sitting_no = {}
        for i, s in enumerate(sits, 1):
            for e in s:
                sitting_no[id(e)] = i

        for e in evs:
            kind, skill = skill_of(e)
            days, phase = relation(e["timestamp"], exam_date)
            iid = str(e.get("item_id") or "")
            answers.append([
                e.get("id", ""), sid, block.get(sid, ""),
                time.strftime("%Y-%m-%d", time.localtime(e["timestamp"])),
                time.strftime("%H:%M:%S", time.localtime(e["timestamp"])),
                time.strftime("%a", time.localtime(e["timestamp"])),
                sitting_no.get(id(e), ""), days, phase, activity(e),
                e.get("context") or "practice", iid,
                "vocab" if kind == "vocab" else ("reading" if kind == "reading"
                                                 else item_formats.get(iid, "")),
                iid.split(":")[2] if kind == "vocab" and iid.count(":") >= 2 else "",
                kind, skill, catalog.get((kind, skill), {}).get("name", ""),
                on_exam((kind, skill)), e.get("result", ""),
                GRADE_NAMES.get(e.get("rating"), "") if e.get("rating") is not None else "",
                _secs(e.get("latency_ms"), 3600) if e.get("latency_ms") is not None else "",
                _secs(e.get("grade_ms"), 3600) if e.get("grade_ms") is not None else "",
                round(e["_secs"], 1) if "_secs" in e else "",
                (e.get("rush") or "").replace(",", " ")])

        for i, s in enumerate(sits, 1):
            cards = _cards(s)
            days, phase = relation(s[0]["timestamp"], exam_date)
            kinds = [activity(e) for e in cards]
            sit_rows.append([
                sid, block.get(sid, ""), i,
                time.strftime("%Y-%m-%d", time.localtime(s[0]["timestamp"])),
                time.strftime("%a", time.localtime(s[0]["timestamp"])),
                time.strftime("%H:%M", time.localtime(s[0]["timestamp"])),
                time.strftime("%H:%M", time.localtime(s[-1]["timestamp"])),
                days, phase, round((s[-1]["timestamp"] - s[0]["timestamp"]) / 60.0, 1),
                _minutes(s), len(cards), kinds.count("vocab"), kinds.count("grammar"),
                kinds.count("reading"), _accuracy(cards),
                sum(1 for e in cards if e.get("rush")),
                sum(1 for e in cards if skill_of(e) in on_exam_set) if on_exam_set else "",
                " ".join(sorted({skill_of(e)[1] for e in cards if activity(e) == "grammar"})),
                len({skill_of(e)[1] for e in cards if activity(e) == "vocab"})])

        # Per skill: practice answers, but the memory state reads every answer
        # (a quiz answer is a retrieval too), exactly as the app's own pages do.
        groups = {}
        for e in evs:
            groups.setdefault(skill_of(e), []).append(e)
        for key in sorted(groups, key=lambda k: (k[0], k[1])):
            allk = groups[key]
            prac = [e for e in allk if activity(e) != "quiz"]
            if not prac:
                continue
            cards = _cards(prac)
            before = [e for e in cards if cutoff is not None and e["timestamp"] < cutoff]
            info = catalog.get(key, {})
            card = fsrs.replay(allk)
            skill_rows.append([
                sid, block.get(sid, ""), key[0], key[1], info.get("name", ""),
                info.get("unit", ""), info.get("week", ""), on_exam(key), len(cards),
                len(before) if cutoff else "",
                sum(1 for e in cards if e.get("result") == "right"),
                sum(1 for e in cards if e.get("result") == "close"),
                sum(1 for e in cards if e.get("result") == "wrong"),
                _accuracy(cards), _accuracy(before) if cutoff else "",
                len({local_date(e["timestamp"]) for e in cards}),
                time.strftime("%Y-%m-%d", time.localtime(cards[0]["timestamp"])) if cards else "",
                time.strftime("%Y-%m-%d", time.localtime(cards[-1]["timestamp"])) if cards else "",
                _minutes(prac),
                fsrs.state(fsrs.replay([e for e in allk if e["timestamp"] < cutoff]))
                if cutoff else "",
                fsrs.state(card), round(card.stability, 1) if card else 0])

        student_rows.append(_student_row(
            sid, block.get(sid, ""), sid in block, practice, quiz, sits, evs,
            exam_date, cutoff, on_exam_set, exam_nodes, exam_words,
            homework.get(sid), groups, now))

    quiz_out = [["quiz_id", "quiz_title", "context", "student_id", "block", "started",
                 "submitted", "questions", "right", "close", "wrong", "written_self_check",
                 "unanswered", "score_pct", "days_before_exam"]]
    for a in quiz_rows:
        res = [r.get("result") for r in (a.get("results") or {}).values()]
        graded = [r for r in res if r in ("right", "close", "wrong", "unanswered")]
        quiz_out.append([
            a["quiz_id"], a.get("title", ""), a.get("context", ""), a["student_id"],
            block.get(a["student_id"], ""),
            time.strftime("%Y-%m-%d %H:%M", time.localtime(a["started_at"])),
            time.strftime("%Y-%m-%d %H:%M", time.localtime(a["submitted_at"]))
            if a.get("submitted_at") else "",
            len(res), res.count("right"), res.count("close"), res.count("wrong"),
            res.count("self"), res.count("unanswered"),
            _pct(res.count("right") + res.count("close"), len(graded)),
            relation(a["started_at"], exam_date)[0]])

    skill_list = [["skill_kind", "skill_id", "skill_name", "unit", "week_taught", "on_exam"]]
    for key in sorted(catalog, key=lambda k: (k[0], str(catalog[k].get("week", "")), k[1])):
        info = catalog[key]
        skill_list.append([key[0], key[1], info.get("name", ""), info.get("unit", ""),
                           info.get("week", ""), on_exam(key)])

    return {"students.csv": student_rows, "sittings.csv": sit_rows,
            "skills_by_student.csv": skill_rows, "answers.csv": answers,
            "in_app_quizzes.csv": quiz_out, "skill_list.csv": skill_list}


_STUDENT_HEADER = [
    "student_id", "block", "on_class_list",
    # all practice, all time
    "first_practice", "last_practice", "days_practiced", "sittings", "est_minutes",
    "median_sitting_minutes", "longest_sitting_minutes", "cards", "vocab_cards",
    "grammar_cards", "reading_answers", "accuracy_pct", "vocab_accuracy_pct",
    "grammar_accuracy_pct", "reading_accuracy_pct", "median_vocab_answer_seconds",
    "median_grammar_answer_seconds", "graded_again", "graded_hard", "graded_good",
    "graded_easy", "wrong_but_graded_good_pct", "rushed_cards", "rushed_pct",
    "flagged_sittings", "vocab_words_tried", "grammar_topics_tried",
    "words_solid_now", "words_shaky_now", "topics_solid_now", "topics_shaky_now",
    # around the exam
    "days_practiced_before_exam", "sittings_before_exam", "est_minutes_before_exam",
    "cards_before_exam", "accuracy_before_exam_pct", "weeks_practiced_before_exam",
    "cards_last_7_days_before_exam", "days_practiced_last_7_days_before_exam",
    "cards_day_before_exam", "cards_exam_day", "cards_after_exam",
    "exam_material_cards_before_exam", "exam_material_share_pct",
    "exam_material_accuracy_before_exam_pct",
    "exam_topics", "exam_topics_practiced", "exam_topics_solid_at_exam",
    "exam_topics_shaky_at_exam", "exam_words", "exam_words_practiced",
    "exam_words_solid_at_exam", "exam_words_shaky_at_exam",
    # homework weeks and in-app quizzes
    "homework_weeks_on_time", "homework_weeks_late", "homework_weeks_not_done",
    "in_app_quiz_answers", "in_app_quiz_accuracy_pct",
]


def _student_row(sid, blk, listed, practice, quiz, sits, evs, exam_date, cutoff,
                 on_exam_set, exam_nodes, exam_words, hw, groups, now):
    cards = _cards(practice)
    kinds = {k: [e for e in cards if activity(e) == k] for k in ("vocab", "grammar", "reading")}
    graded = [e for e in cards if e.get("rating") in (1, 2, 3, 4)]
    wrong_graded = [e for e in graded if e.get("result") == "wrong"]
    sit_mins = [_minutes(s) for s in sits]
    flagged = rush.flagged_sittings(practice)

    def states(kind, universe=None):
        out = {"solid": 0, "shaky": 0, "not yet": 0}
        groups = {}
        for e in evs:
            k = skill_of(e)
            if k[0] == kind and (universe is None or k[1] in universe):
                groups.setdefault(k[1], []).append(e)
        for g in groups.values():
            out[fsrs.state(fsrs.replay(g))] += 1
        return out, groups

    words_now, words_tried = states("vocab")
    topics_now, topics_tried = states("grammar")

    row = [sid, blk, "yes" if listed else "no",
           time.strftime("%Y-%m-%d", time.localtime(cards[0]["timestamp"])) if cards else "",
           time.strftime("%Y-%m-%d", time.localtime(cards[-1]["timestamp"])) if cards else "",
           len({local_date(e["timestamp"]) for e in cards}), len(sits),
           round(sum(sit_mins), 1), _median(sit_mins), max(sit_mins) if sit_mins else "",
           len(cards), len(kinds["vocab"]), len(kinds["grammar"]), len(kinds["reading"]),
           _accuracy(cards), _accuracy(kinds["vocab"]), _accuracy(kinds["grammar"]),
           _accuracy(kinds["reading"]),
           _median([_secs(e.get("latency_ms"), 120) for e in kinds["vocab"]]),
           _median([_secs(e.get("latency_ms"), 120) for e in kinds["grammar"]]),
           sum(1 for e in graded if e["rating"] == 1), sum(1 for e in graded if e["rating"] == 2),
           sum(1 for e in graded if e["rating"] == 3), sum(1 for e in graded if e["rating"] == 4),
           _pct(sum(1 for e in wrong_graded if e["rating"] >= 3), len(wrong_graded)),
           sum(1 for e in cards if e.get("rush")),
           _pct(sum(1 for e in cards if e.get("rush")), len(cards)), len(flagged),
           len(words_tried), len(topics_tried),
           words_now["solid"], words_now["shaky"], topics_now["solid"], topics_now["shaky"]]

    if cutoff is None:
        row += [""] * 19
    else:
        def days_before(e):
            return (exam_date - local_date(e["timestamp"])).days

        before = [e for e in cards if days_before(e) > 0]
        last7 = [e for e in before if days_before(e) <= 7]
        mat = [e for e in before if skill_of(e) in on_exam_set]
        sits_before = [s for s in sits if days_before(s[0]) > 0]

        def at_exam(kind, universe):
            got = {"solid": 0, "shaky": 0, "practiced": 0}
            for u in universe:
                g = [e for e in groups.get((kind, u), ()) if e["timestamp"] < cutoff]
                if any(activity(e) != "quiz" for e in g):
                    got["practiced"] += 1
                st = fsrs.state(fsrs.replay(g))
                if st in got:
                    got[st] += 1
            return got

        t, w = at_exam("grammar", exam_nodes), at_exam("vocab", exam_words)
        has_scope = bool(on_exam_set)
        row += [len({local_date(e["timestamp"]) for e in before}), len(sits_before),
                round(sum(_minutes([e for e in s if days_before(e) > 0]) for s in sits), 1),
                len(before), _accuracy(before),
                len({local_date(e["timestamp"]).isocalendar()[:2] for e in before}),
                len(last7), len({local_date(e["timestamp"]) for e in last7}),
                sum(1 for e in cards if days_before(e) == 1),
                sum(1 for e in cards if days_before(e) == 0),
                sum(1 for e in cards if days_before(e) < 0)]
        if has_scope:
            row += [len(mat), _pct(len(mat), len(before)), _accuracy(mat),
                    len(exam_nodes), t["practiced"], t["solid"], t["shaky"],
                    len(exam_words), w["practiced"], w["solid"], w["shaky"]]
        else:
            row += [""] * 11

    hw = hw or {}
    q = _cards(quiz)
    row += [hw.get("on_time", ""), hw.get("late", ""), hw.get("not_done", ""),
            len(q), _accuracy(q)]
    return row


DICTIONARY = """\
LATIN I PRACTICE APP -- DATA FOR ANALYSIS
=========================================
Downloaded {downloaded} (school time, Eastern).
Exam: {exam}
Block: {block}

Students are identified by student ID number only. To join with exam scores or
the gradebook, match on student_id. The text students typed is not included.

THE FILES
---------
students.csv           One row per student. The summary: start here.
sittings.csv           One row per sitting (answers with no gap over 30 minutes).
skills_by_student.csv  One row per student per skill they practiced.
answers.csv            One row per answer -- every detail the app records.
in_app_quizzes.csv     Quizzes taken inside the app (most quizzes are on paper and
                       are NOT here).
skill_list.csv         Every skill, practiced or not: name, unit, week taught, on
                       the exam or not.

WORDS USED
----------
skill        A vocabulary WORD (skill_kind "vocab", skill_id is the Latin), a
             grammar TOPIC (skill_kind "grammar", skill_id is a spec node such as
             MS-031), or a READING story (skill_kind "reading").
card         One question studied. A typo the student retyped on the spot is part
             of the same card, not a second one.
accuracy     Share of cards the APP judged right. "close" (right word, small
             spelling slip) counts as right. Accuracy measures the work, not the
             student's own grade.
self_grade   The student's own grade after seeing the answer: again / hard /
             good / easy (the spaced-repetition schedule runs on it). Blank =
             graded by the app (drag-and-drop, quizzes, older answers before
             self-grading began on 15 Oct 2026). "retype" = fixing a typo.
rushed       The app's flag for a card done too fast to be study (rules:
             looked_away = graded a wrong/blank answer within 1.5 s of seeing it;
             graded_up = graded Good/Easy on a non-answer; guessed = wrong and
             faster than reading allows). Only answers from 16 Oct 2026 on carry
             it.
state        solid / shaky / not yet: the app's memory estimate (FSRS). solid =
             predicted to hold three weeks or more; not yet = never got right.
             state_at_exam reads only answers before the exam day.
days_before_exam  1 = the day before the exam, 0 = exam day, negative = after.
phase        before / exam day / after. Exam-day answers may be before or after
             the exam itself (blocks meet at different times); "before" never
             includes exam day.
on_exam      yes = the topic or word is in what the exam covered (as set on the
             app's Goals & deadlines page), no = not; blank = no exam chosen.

TIME (an estimate -- read this)
----
The app records the moment each answer is given, not when a student looks
away. est_seconds for an answer = the gap since the student's previous answer,
capped at 5 minutes; a sitting's first answer gets its own measured time (or 20
seconds if that is missing). est_minutes = the sum. span_minutes = first answer
to last answer of a sitting, with no cap. A sitting with a 25-minute pause
counts 5 of them in est_minutes and all 25 in span_minutes.
answer_seconds = card shown to answer submitted. grade_seconds = answer shown
to self-grade pressed (from 16 Oct 2026).

STUDENTS.CSV COLUMNS
--------------------
days_practiced, sittings, est_minutes, cards ... all practice, all time.
median_*_answer_seconds    typical time to answer one card.
wrong_but_graded_good_pct  of cards the app judged wrong, the share the student
                           graded Good or Easy (an honesty / attention signal).
flagged_sittings           sittings of 10+ cards with a third or more rushed.
*_solid_now, *_shaky_now   memory state today.
weeks_practiced_before_exam  distinct calendar weeks with practice before the
                           exam: a spacing measure.
cards_last_7_days_before_exam, cards_day_before_exam: cramming measures.
exam_material_*            practice on topics/words the exam covered.
exam_topics_solid_at_exam  of the exam's topics, how many were solid going in.
homework_weeks_*           the weekly homework record (Saturday to Friday).
"""
