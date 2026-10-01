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

import hashlib
import time
from collections import namedtuple

from answercheck import check as check_answer

# The fixed menu choices. Never written per item; appended to every item's own
# what_went_wrong list. The last is the contest path.
#
# "I don't know" used to head this list, as the exemplar file's rules specify.
# It came out after the app met a real class: it was most of the answers, which
# is not a diagnosis, and being first it crowded out the reasons that are.
# A deliberate deviation from the exemplar rule; the README records it.
#
# Removing it does NOT leave a student cornered. Every choice here is a claim
# about why you were wrong, so the feedback screen carries a quiet way past the
# menu that records nothing. Without it, a student with no idea has two ways
# out and both are worse than silence: invent a reason, which puts a sentence
# in the teacher's "what they say went wrong" table that nobody meant, or tap
# "I think my answer should be right", which pulls a sound question out of
# circulation and into the flagged queue.
FIXED_MENU = [
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

# --------------------------------------------------------------------------
# Which order a student sees the options in
# --------------------------------------------------------------------------

DISPLAY_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def display_options(options, viewer_seed):
    """The options in a per-student order, relabelled a/b/c/... down the page.

    Every choice item in the bank was written with its correct answer as option
    `a`, and for a long time the templates rendered `options` in the order the
    YAML listed them. The answer was therefore always the first thing on the
    screen, in practice and in a quiz alike: tapping the top option scored full
    marks on every multiple-choice question in the course without reading any
    Latin. Nothing in the tests caught it, because no individual question was
    wrong.

    Rewriting 214 answer keys would have fixed the bank and left the next batch
    of questions free to reintroduce it, so the order moves at render time
    instead and the bank keeps its convention: the author writes the answer
    first, the student never sees it there.

    Returns a list of (display_letter, submit_key, text). The submit key is the
    item's own key, so what the browser posts back is unchanged -- grading,
    saved quiz answers, the event record and the review tool all keep working
    on the letters the YAML uses. Only the order and the printed label move.

    The order is derived from a hash of the seed rather than from `random`, so
    it is identical on every machine and every Python version: a quiz review
    screen must show a student the same lettering they answered under, possibly
    days later and after a redeploy.
    """
    opts = options or {}
    if not isinstance(opts, dict):
        return []
    seed = "" if viewer_seed is None else str(viewer_seed)

    def rank(key):
        digest = hashlib.sha256(("%s|%s" % (seed, key)).encode("utf-8"))
        return (digest.hexdigest(), key)

    ordered = sorted(opts, key=rank)
    return [(DISPLAY_LETTERS[i] if i < len(DISPLAY_LETTERS) else str(i + 1), k, opts[k])
            for i, k in enumerate(ordered)]


def option_seed(student_id, item_id):
    """One shuffle per student per question.

    Per student, so no two students can compare positions. Per question, so a
    student cannot learn "the answer is second for me" and apply it to the next
    one. Stable for that pair for ever, so a refresh does not reshuffle and the
    quiz review matches the paper they sat.
    """
    return "%s|%s" % (student_id or "", item_id or "")


# --------------------------------------------------------------------------
# What a hint may show before the student has answered
# --------------------------------------------------------------------------

def _plain(text):
    """Lower-case, macrons off, letters and spaces only -- for comparing."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join("".join(c if c.isalpha() else " " for c in s.lower()).split())


def _answers_of(item):
    """The strings that ARE the answer, where a hint must not print them."""
    out = []
    fmt = item.get("format")
    if fmt == "choice":
        v = (item.get("options") or {}).get(item.get("answer"))
        if v:
            out.append(v)
    elif fmt == "boxes":
        for b in item.get("boxes") or []:
            out.extend(a for a in (b.get("answer") or []) if a)
    elif fmt == LABEL_WORDS:
        for t in label_targets(item):
            out.extend(t["accepted"])
    return [a for a in (_plain(x) for x in out) if len(a) >= 3]


def question_text(item):
    """Everything the student reads before answering: the stem, and for a
    label-words question the sentence itself, which lives outside the stem."""
    words = " ".join(str(w.get("latin", "")) for w in (item.get("sentence") or [])
                     if isinstance(w, dict))
    return (str(item.get("stem") or "") + " " + words).strip()


def hint_examples(examples, item):
    """Worked examples that are safe to show BEFORE the student answers.

    Teaching text is written per node and serves two moments: the hint, taken
    before answering, and the explanation, read after. Its worked examples are
    often built from the same handful of sentences the questions use -- which
    is fine after the answer and fatal before it. The MS-014 hint said "Nauta
    puellam spectat -- nauta is nominative" on the question "In Nauta puellam
    spectat, which word is the subject?"

    So the hint drops any example that repeats three or more consecutive words
    of the question, or that contains the answer itself. The explanation after
    the answer still shows every example, and the approved wording is never
    changed -- this is a filter on one moment, not an edit to the text.
    """
    stem = _plain(question_text(item)).split()
    windows = {" ".join(stem[i:i + 3]) for i in range(len(stem) - 2)}
    answers = _answers_of(item)
    kept = []
    for ex in examples or []:
        e = " %s " % _plain(ex)
        if any(" %s " % w in e for w in windows):
            continue
        if any(" %s " % a in e for a in answers):
            continue
        kept.append(ex)
    return kept


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
# Label the words: tap a label from the bank, tap the box over a word
# --------------------------------------------------------------------------
#
# format: label-words
#   sentence:  the words in order. A word with `answer` gets a box above it;
#              a word without one (et, a preposition) is shown plain.
#              answer is the accepted label, or a list of accepted labels.
#   bank:      every label offered, in the order shown. Labels are reusable --
#              "nominative · subject" can go on two words -- so the last box can
#              never be filled by elimination, and the bank always holds at
#              least one label the sentence doesn't use.
#   translation_model_answer (optional): the English. The student writes it
#              after labelling and compares; it is not graded.
#
# The same shape serves two kinds of question: case-and-job labels
# ("accusative · direct object", "verb"), and the English for each word as it
# works in this sentence ("the girls", "of the farmer").

LABEL_WORDS = "label-words"


def _as_list(v):
    if v is None:
        return []
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]


def label_targets(item):
    """The boxed words, in order: [{"word", "accepted"}]."""
    out = []
    for w in item.get("sentence") or []:
        acc = _as_list(w.get("answer"))
        if acc:
            out.append({"word": str(w.get("latin", "")), "accepted": acc})
    return out


def label_problems(item):
    """What is wrong with a label-words question, in plain words. Empty is fine."""
    out = []
    sentence = item.get("sentence")
    if not isinstance(sentence, list) or not sentence:
        return ["it has no sentence"]
    if any(not isinstance(w, dict) or not str(w.get("latin") or "").strip() for w in sentence):
        out.append("every sentence entry needs a latin word")
    targets = label_targets(item)
    if len(targets) < 2:
        out.append("it needs at least two words with boxes")
    bank = _as_list(item.get("bank"))
    if len(set(bank)) != len(bank):
        out.append("the bank lists a label twice")
    if not 3 <= len(bank) <= 12:
        out.append("the bank should offer 3 to 12 labels (it has %d)" % len(bank))
    used = set()
    for t in targets:
        missing = [a for a in t["accepted"] if a not in bank]
        if missing:
            out.append("the answer for %s is not in the bank: %s" % (t["word"], ", ".join(missing)))
        used.update(t["accepted"])
    if bank and not (set(bank) - used):
        out.append("every label in the bank is an answer -- add at least one that isn't, "
                   "so nothing can be done by elimination")
    return out


def grade_labels(item, picks):
    """Overall right only if every box is right. There is no close: the
    student picks a label, so there is nothing to misspell."""
    results = []
    picks = list(picks) + [""] * len(label_targets(item))
    for i, t in enumerate(label_targets(item)):
        p = str(picks[i] or "").strip()
        results.append({"word": t["word"], "picked": p, "accepted": t["accepted"],
                        "result": "right" if p in t["accepted"] else "wrong"})
    overall = "right" if results and all(r["result"] == "right" for r in results) else "wrong"
    return overall, results


def label_summary(results):
    """The event's `response`: what went in each box."""
    return " | ".join("%s=%s" % (r["word"], r["picked"] or "(blank)") for r in results)[:200]


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
