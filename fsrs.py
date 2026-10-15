"""
FSRS: the spaced-repetition schedule for vocabulary and grammar.

Replaces the Leitner boxes (October 2026). Students said they saw "shaky" on
nearly everything and no sense of progress, and the old rules explain why:
"solid" needed a right answer a week after first meeting a word however well
it was known, "shaky" covered everything from one lucky answer to eight right
in a row, and a single miss threw a word back to the start.

FSRS keeps two numbers per card:

  stability   about how many days until the chance of remembering it drops to
              90%. Every successful review raises it; it is the progress
              students can see grow.
  difficulty  how hard this card is for this student, 1-10.

It is the published FSRS-5 algorithm with its standard weights, written out
here rather than installed, so the app still has no build step and nothing
new to install on Render or a laptop. The weights could later be fitted to the
class's own reviews.

GRADES. 1 Again, 2 Hard, 3 Good, 4 Easy -- what the student says after seeing
the answer. Students grade nearly everything themselves (the teacher's call:
spelling makes the app's own check unreliable, and judging your own recall is
worth practicing). The app grades a drag-and-drop question itself, and answers
from before self-grading are read from what the app checked:
right -> Good, wrong -> Again (a "close" was retyped, and the retype counts).

NOTHING IS STORED. A card's state is replayed from the event history, like
everything else in the app, so switching from Leitner lost nobody's progress:
September's answers replay into stabilities on the first day.
"""

import math
import time

DAY = 86400.0

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
GRADES = (AGAIN, HARD, GOOD, EASY)
GRADE_NAMES = {AGAIN: "Again", HARD: "Hard", GOOD: "Good", EASY: "Easy"}

# FSRS-5 default weights.
W = (0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575,
     0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621)
DECAY = -0.5
FACTOR = 19.0 / 81.0          # so that retrievability is exactly 90% at t = stability

RETENTION = 0.9               # schedule the next review when recall drops to this
RELEARN_SECONDS = 5 * 60      # an Again comes back in the same sitting
MAX_INTERVAL_DAYS = 365
SOLID_DAYS = 21               # stability that counts as "solid"
BAR_FULL_DAYS = 90            # where a strength bar is full

# Answers from before self-grading, and the ones the app grades itself. A
# "close" is left out: it was a typo the student retyped on the spot, and the
# retype is the answer that counts.
FROM_RESULT = {"right": GOOD, "wrong": AGAIN}


class Card(object):
    __slots__ = ("stability", "difficulty", "last", "due", "reps", "lapses",
                 "successes", "last_grade")

    def __init__(self):
        self.stability = 0.0
        self.difficulty = 0.0
        self.last = None
        self.due = 0.0
        self.reps = 0
        self.lapses = 0
        self.successes = 0
        self.last_grade = None


def _clamp_d(d):
    return min(10.0, max(1.0, d))


def retrievability(elapsed_days, stability):
    """Chance of recalling it now, 0-1."""
    if stability <= 0:
        return 0.0
    return (1.0 + FACTOR * max(0.0, elapsed_days) / stability) ** DECAY


def interval_days(stability, retention=RETENTION):
    """Days until recall drops to `retention`. With 90% that is the stability."""
    return stability / FACTOR * (retention ** (1.0 / DECAY) - 1.0)


def _init_d(g):
    return _clamp_d(W[4] - math.exp(W[5] * (g - 1)) + 1.0)


def _next_d(d, g):
    d2 = d + (-W[6] * (g - 3)) * (10.0 - d) / 9.0          # linear damping
    return _clamp_d(W[7] * _init_d(EASY) + (1.0 - W[7]) * d2)  # mean reversion


def _recall_s(d, s, r, g):
    hard = W[15] if g == HARD else 1.0
    easy = W[16] if g == EASY else 1.0
    return s * (1.0 + math.exp(W[8]) * (11.0 - d) * s ** (-W[9])
                * (math.exp(W[10] * (1.0 - r)) - 1.0) * hard * easy)


def _forget_s(d, s, r):
    return min(s, W[11] * d ** (-W[12]) * ((s + 1.0) ** W[13] - 1.0)
               * math.exp(W[14] * (1.0 - r)))


def _same_day_s(s, g):
    return s * math.exp(W[17] * (g - 3 + W[18]))


def _day(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _schedule(card, g, ts):
    if g == AGAIN:
        return ts + RELEARN_SECONDS
    days = min(MAX_INTERVAL_DAYS, max(1.0, round(interval_days(card.stability))))
    return ts + days * DAY


def review(card, g, ts):
    """The card after grade `g` at time `ts`. A new card is None."""
    out = Card()
    if card is None or card.last is None:
        out.stability = W[g - 1]
        out.difficulty = _init_d(g)
    else:
        out.difficulty = _next_d(card.difficulty, g)
        if _day(ts) == _day(card.last):
            out.stability = _same_day_s(card.stability, g)
        else:
            r = retrievability((ts - card.last) / DAY, card.stability)
            out.stability = (_forget_s(card.difficulty, card.stability, r) if g == AGAIN
                             else _recall_s(card.difficulty, card.stability, r, g))
        out.reps, out.lapses, out.successes = card.reps, card.lapses, card.successes
    out.stability = max(0.05, out.stability)
    out.reps += 1
    out.lapses += 1 if g == AGAIN and card is not None else 0
    out.successes += 1 if g >= HARD else 0
    out.last = ts
    out.last_grade = g
    out.due = _schedule(out, g, ts)
    return out


def grade_of(event):
    """The grade an event carries: the student's own if they gave one, else
    what the app checked. None when it is not a review at all (a typo retyped
    on the spot, an answer the student never graded)."""
    r = event.get("rating")
    if r is not None:
        return int(r) if int(r) in GRADES else None
    return FROM_RESULT.get(event.get("result"))


def replay(events):
    """A card's state from its history, oldest first; None if never reviewed."""
    card = None
    for e in sorted(events, key=lambda e: e["timestamp"]):
        g = grade_of(e)
        if g is not None:
            card = review(card, g, e["timestamp"])
    return card


def state(card):
    """solid | shaky | not yet -- the words students already know, now read
    from memory strength. Not yet: never got it. Solid: holds three weeks or
    more. Shaky: everything in between."""
    if card is None or card.successes == 0:
        return "not yet"
    if card.stability >= SOLID_DAYS:
        return "solid"
    return "shaky"


def strength(card, now=None):
    """What a progress bar shows: {"days", "bar", "due", "recall"}."""
    now = now or time.time()
    if card is None:
        return {"days": 0, "bar": 0.0, "due": True, "recall": 0.0}
    days = card.stability
    return {"days": days,
            "bar": min(1.0, math.log1p(days) / math.log1p(BAR_FULL_DAYS)),
            "due": card.due <= now,
            "recall": retrievability((now - card.last) / DAY, card.stability)}


def is_due(card, now=None):
    now = now or time.time()
    return card is not None and card.due <= now


def preview(card, now=None):
    """{grade: seconds until the next review} -- shown on each grade button."""
    now = now or time.time()
    return {g: review(card, g, now).due - now for g in GRADES}


def describe_wait(seconds):
    """"5 min", "1 day", "3 days", "2 mo" -- for a grade button."""
    if seconds < 3600:
        return "%d min" % max(1, round(seconds / 60.0))
    days = seconds / DAY
    if days < 1.5:
        return "1 day"
    if days < 30:
        return "%d days" % round(days)
    if days < 365:
        return "%d mo" % round(days / 30.0)
    return "1 yr"


def describe_days(days):
    """How long a memory holds, for a progress row: "2 days", "3 wks"."""
    if days < 1:
        return "under a day"
    if days < 14:
        return "%d day%s" % (round(days), "" if round(days) == 1 else "s")
    if days < 60:
        return "%d wks" % round(days / 7.0)
    return "%d mo" % round(days / 30.0)


def pick(cards, keys, now=None, avoid=None):
    """The next key to study, from {key: Card or None} over `keys` (in order):

      1. a card that is due, the one most likely forgotten first;
      2. otherwise a new card, in the order given (weeks, then the list);
      3. otherwise -- everything is done for today -- the card most likely
         forgotten, so practice can go on: an early review moves it less, as
         it should, and the 50 + 50 can always be reached.

    `avoid` is the card just answered, skipped while anything else is left."""
    now = now or time.time()
    keys = [k for k in keys if k != avoid] or list(keys)
    if not keys:
        return None

    def recall(k):
        c = cards.get(k)
        return retrievability((now - c.last) / DAY, c.stability)

    due = [k for k in keys if is_due(cards.get(k), now)]
    if due:
        return min(due, key=recall)
    new = [k for k in keys if cards.get(k) is None]
    if new:
        return new[0]
    return min(keys, key=recall)
