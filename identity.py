"""
Who a student is, in this system: a number.

The school committed to leadership that this app holds no student names — no
first name, no last name, no email, no display name. So identity here is an ID
number and nothing else, and there is deliberately no field a name could be
put in later.

That is a privacy decision, but it also fixes a real bug. Identity used to be
a typed name, which meant "Sam" and "Sam T." were two students with two
spaced-repetition schedules and half a history each, silently. Numbers do not
have that problem: two students cannot collide on one, and nobody has to spell
anything the same way twice.

The one hazard a number introduces is the typo. A mistyped name looks wrong;
a mistyped number looks fine, and writes a student's practice into somebody
else's record or into nobody's. Three things guard it:

  format     a number that is not shaped like an ID is refused outright.
  roster     a number that is well-formed but not on the class list is not
             silently accepted — the student is told and has to confirm.
  the list   the roster is loaded from a file the teacher supplies. The paper
             that maps numbers to actual students stays off the machine.
"""

import os
import re

# What a student ID looks like here. Libertas IDs were not specified in the
# change request, so this is a guess wide enough for most school ID schemes —
# override LATIN_ID_PATTERN if it is wrong. Leading zeros are significant, so
# they are never stripped.
DEFAULT_PATTERN = r"^[0-9]{4,10}$"

# Characters people put in a number that are not part of it: an ID written on
# a card as "40-217" or "40 217" is the same ID.
_STRIP = re.compile(r"[\s\-]+")


def pattern():
    return os.environ.get("LATIN_ID_PATTERN") or DEFAULT_PATTERN


def normalize(raw):
    """The stored form of a typed ID.

    Whitespace and separators come off; nothing else is touched. In
    particular leading zeros stay, because "04217" is a real ID and is not
    the same student as "4217".
    """
    return _STRIP.sub("", str(raw or "").strip())


def is_valid(raw):
    return bool(re.match(pattern(), normalize(raw)))


def describe_pattern():
    """A human sentence for the screen that rejects a bad number."""
    p = pattern()
    m = re.match(r"^\^\[0-9\]\{(\d+),(\d+)\}\$$", p)
    if m:
        lo, hi = m.group(1), m.group(2)
        if lo == hi:
            return "a %s-digit number" % lo
        return "a number, %s to %s digits" % (lo, hi)
    return "a valid student ID"
