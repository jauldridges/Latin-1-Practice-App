"""
Generate student ID numbers.

These numbers are the whole of a student's identity in this app, so they are
worth choosing rather than just picking. Four decisions:

SIX DIGITS, NEVER STARTING WITH ZERO
    Fixed length means a typo that drops or doubles a digit is caught by the
    format check before it reaches the roster. No leading zero because this
    list will end up in a spreadsheet at some point, and spreadsheets eat
    leading zeros silently — 042173 becoming 42173 would quietly unperson a
    student.

RANDOM, NOT SEQUENTIAL
    Sequential ids let a student reach a classmate's account by adding one.
    The PIN is the only thing behind the id, so the id should not be a
    guessing game.

SPARSE
    100-ish numbers scattered through 900,000 means a mistyped digit almost
    never lands on another real student. It lands on nothing, and the student
    gets the "we don't have that number" screen — which is recoverable, unlike
    silently practising into somebody else's record.

AND NO TWO WITHIN ONE TYPO OF EACH OTHER
    "Almost never" is free to turn into "never" at this size, so the generator
    enforces it: no issued id can be reached from another by changing a single
    digit or swapping two neighbouring ones. Those are the two mistakes people
    actually make. Sparsity makes this cheap — rejecting a candidate costs one
    set lookup.

    This is the one property here that is worth a test, and has one.

Usage:
    python3 make_ids.py 120 > ids.txt
    python3 make_ids.py 120 --seed 7      # reproducible, for testing only
"""

import random
import sys

LENGTH = 6
LOW = 10 ** (LENGTH - 1)          # 100000 — never a leading zero
HIGH = 10 ** LENGTH - 1           # 999999


def typo_neighbours(sid):
    """Every id one realistic slip away: one wrong digit, or two swapped.

    Deliberately not a general edit distance. Inserting or deleting a digit
    changes the length, and a wrong-length id is already refused by the format
    check, so those need no room here.
    """
    out = set()
    for i, ch in enumerate(sid):
        for d in "0123456789":
            if d == ch:
                continue
            if i == 0 and d == "0":     # would not be a legal id anyway
                continue
            out.add(sid[:i] + d + sid[i + 1:])
    for i in range(len(sid) - 1):
        if sid[i] != sid[i + 1]:
            out.add(sid[:i] + sid[i + 1] + sid[i] + sid[i + 2:])
    return out


def generate(n, seed=None, rng=None):
    """n ids, none reachable from another by a single-digit typo."""
    if n > 4000:
        # Long before the space is full, the rejection rate makes this crawl.
        raise ValueError("this generator is sized for a school, not a district")
    rng = rng or random.Random(seed)
    issued, blocked = [], set()
    attempts = 0
    while len(issued) < n:
        attempts += 1
        if attempts > 100 * n + 1000:
            raise RuntimeError("could not place %d ids — the space is too crowded" % n)
        sid = str(rng.randint(LOW, HIGH))
        if sid in blocked:
            continue
        issued.append(sid)
        blocked.add(sid)
        blocked |= typo_neighbours(sid)
    return issued


def main(argv):
    n = 120
    seed = None
    args = list(argv)
    if "--seed" in args:
        i = args.index("--seed")
        seed = int(args[i + 1])
        del args[i:i + 2]
    if args:
        n = int(args[0])
    for sid in generate(n, seed=seed):
        print(sid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
