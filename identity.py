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

import binascii
import hashlib
import hmac
import os
import re

# What a student ID looks like here: six digits, never starting with zero.
#
# These numbers are issued by make_ids.py rather than taken from the school's
# system, so the format is a choice rather than a constraint — and a tight one
# earns its keep. A typo that drops or doubles a digit is refused at the
# sign-in screen instead of becoming a mystery "unknown number", and no id can
# ever be written with a leading zero, which a spreadsheet would silently eat.
#
# Override LATIN_ID_PATTERN if you ever need to accept something else. Leading
# zeros are never stripped, so an id from another scheme keeps its shape.
DEFAULT_PATTERN = r"^[1-9][0-9]{5}$"

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
    if p == DEFAULT_PATTERN:
        return "a 6-digit number"
    m = re.match(r"^\^\[0-9\]\{(\d+),(\d+)\}\$$", p)
    if m:
        lo, hi = m.group(1), m.group(2)
        if lo == hi:
            return "a %s-digit number" % lo
        return "a number, %s to %s digits" % (lo, hi)
    m = re.match(r"^\^\[0-9\]\{(\d+)\}\$$", p)
    if m:
        return "a %s-digit number" % m.group(1)
    return "a valid student ID"


# --------------------------------------------------------------------------
# PINs
# --------------------------------------------------------------------------

PIN_LENGTH = 4
_PIN_RE = re.compile(r"^[0-9]{%d}$" % PIN_LENGTH)

# Deliberately not a password hash's worth of rounds. A four-digit PIN has only
# 10,000 possibilities, so no iteration count makes a stolen table safe against
# someone determined; what this buys is that the table is not a plain lookup,
# and that guessing costs real time. Meanwhile every sign-in pays this cost on
# a small server, so a million rounds would just make the app feel broken.
PIN_ROUNDS = 200000
PIN_ALGO = "pbkdf2_sha256$%d" % PIN_ROUNDS


def is_valid_pin(pin):
    return bool(_PIN_RE.match(str(pin or "").strip()))


def hash_pin(pin, salt=None):
    """Returns (algo, salt, hex digest). Per-student salt, so two students who
    pick the same PIN do not get the same hash."""
    salt = salt or binascii.hexlify(os.urandom(16)).decode()
    digest = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), salt.encode(), PIN_ROUNDS)
    return PIN_ALGO, salt, binascii.hexlify(digest).decode()


def verify_pin(pin, algo, salt, expected):
    """Constant-time compare, and the stored algo is honoured rather than
    assumed, so the rounds can be raised later without locking anyone out."""
    rounds = PIN_ROUNDS
    if algo and "$" in algo:
        try:
            rounds = int(algo.split("$", 1)[1])
        except ValueError:
            pass
    digest = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), str(salt).encode(), rounds)
    return hmac.compare_digest(binascii.hexlify(digest).decode(), str(expected))
