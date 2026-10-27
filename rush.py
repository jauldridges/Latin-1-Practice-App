"""
Rushing: cards flipped through without studying.

A card is RUSHED when any of these is true (the teacher's rules, October 2026):

  1. looked_away -- the app's check said wrong (or the answer was blank), and
     the student tapped a grade within 1.5 seconds of the right answer
     appearing. Too fast to have read it.
  2. graded_up -- Good or Easy on something that wasn't a real try: a blank
     answer, a typed answer sharing less than half its letters with the right
     one ("zzz" for water; "watre" is a real try), or a wrong multiple-choice
     pick.
  3. guessed -- a wrong answer given faster than the question can be read:
     1.5 s for a vocabulary card, 2.5 s for a grammar question, 1 s per box
     on a drag-and-drop question.

A RIGHT answer is never rushed, however fast: quick and right means known.
A blank answer graded Again after reading the answer is not rushed either --
that is honest flashcard study.

The verdict is worked out when the answer is recorded and stored with it
(events.rush: the reason codes, comma-separated, or NULL), so every screen
reads the same verdict and a later change to these thresholds never rewrites
what a student was told at the time.

A SITTING (answers with no gap over 30 minutes, stats.current_session's rule)
is flagged for the teacher when it has at least 10 cards and a third or more
were rushed. One lazy card never flags anyone.
"""

from difflib import SequenceMatcher

from answercheck import clean

LOOKED_AWAY_MS = 1500
GUESS_MS = {"vocab": 1500, "grammar": 2500}
GUESS_MS_PER_BOX = 1000
MIN_ATTEMPT = 0.5                # share of letters a typed answer must have in common
SITTING_GAP = 30 * 60
FLAG_MIN_CARDS = 10
FLAG_SHARE = 1.0 / 3.0
NUDGE_RUN = 3                    # rushed cards in a row before the Magister says something

REASONS = {
    "looked_away": "graded before reading the answer",
    "graded_up": "graded Good or Easy on a non-answer",
    "guessed": "wrong answer faster than the question can be read",
}


def similarity(response, accepted):
    """Best share of letters in common with any accepted answer, 0-1."""
    r = clean(response or "")
    if not r:
        return 0.0
    return max((SequenceMatcher(None, r, clean(a)).ratio() for a in accepted or [] if a),
               default=0.0)


def verdict(kind, result, rating, response="", accepted=(), latency_ms=None,
            grade_ms=None, typed=True, boxes=1):
    """The reasons a card was rushed, or [] if it wasn't.

    kind     "vocab" or "grammar"
    result   the app's own check: right | close | wrong (a self-check: None)
    rating   the student's grade 1-4, or None when the app graded it
    typed    whether the answer was typed (vs picked from options)
    """
    if result == "right":
        return []
    out = []
    blank = not clean(response or "")
    if result == "wrong" or blank:
        if grade_ms is not None and grade_ms < LOOKED_AWAY_MS:
            out.append("looked_away")
    if rating is not None and rating >= 3 and result is not None:
        if blank or (typed and similarity(response, accepted) < MIN_ATTEMPT) \
                or (not typed and result == "wrong"):
            out.append("graded_up")
    if result == "wrong" and latency_ms is not None:
        limit = GUESS_MS_PER_BOX * max(1, boxes) if boxes > 1 else GUESS_MS.get(kind, 2500)
        if latency_ms < limit:
            out.append("guessed")
    return out


def encode(reasons):
    return ",".join(reasons) or None


def is_rushed(event):
    return bool(event.get("rush"))


def sittings(events, gap=SITTING_GAP):
    """Graded answers split into sittings, oldest first. Retyped typos
    (rating 0) and quiz answers aren't cards studied, so they're left out."""
    graded = sorted((e for e in events
                     if e.get("rating") not in (0,) and e.get("context") not in ("quiz", "exam", "reading", "badge")),
                    key=lambda e: e["timestamp"])
    out, cur = [], []
    for e in graded:
        if cur and e["timestamp"] - cur[-1]["timestamp"] > gap:
            out.append(cur)
            cur = []
        cur.append(e)
    if cur:
        out.append(cur)
    return out


def flagged_sittings(events):
    """The sittings worth the teacher's look: {"start", "end", "cards",
    "rushed", "reasons": {code: n}, "events"}."""
    out = []
    for s in sittings(events):
        rushed = [e for e in s if is_rushed(e)]
        if len(s) >= FLAG_MIN_CARDS and len(rushed) >= FLAG_SHARE * len(s):
            reasons = {}
            for e in rushed:
                for code in str(e["rush"]).split(","):
                    reasons[code] = reasons.get(code, 0) + 1
            out.append({"start": s[0]["timestamp"], "end": s[-1]["timestamp"],
                        "cards": len(s), "rushed": len(rushed), "reasons": reasons,
                        "events": s})
    return out


def rushing_now(events, now=None, run=NUDGE_RUN):
    """True when the last `run` cards in the current sitting were all rushed:
    the moment for the Magister's slow-down message."""
    s = sittings(events)
    if not s:
        return False
    last = s[-1]
    if now is not None and now - last[-1]["timestamp"] > SITTING_GAP:
        return False
    tail = last[-run:]
    return len(tail) == run and all(is_rushed(e) for e in tail)
