"""
The Magister: a cartoon Roman teacher who says one thing each time a student
opens the app -- the expectations, how to study, a fact about memory, a reason
Latin is worth it -- and says "slow down" when they rush (rush.py).

His lines are in magister.yaml. A student sees a line only once the teacher
has approved that exact wording, the same rule as teaching text and
vocabulary hints: the approval is a fingerprint of the words, kept in the
teaching-approval table under a "magister:" key, so an edited line needs
approving again. The teacher can also edit any line (stored as an override,
the file is never written) and add lines of their own ("magister:custom-...").
"""

import hashlib
import os
import uuid

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "magister.yaml")
PREFIX = "magister:"

CATEGORIES = [
    ("leges-how", "Lēgēs Magistrī: how to use the app"),
    ("leges-dont", "Lēgēs Magistrī: what not to do"),
    ("rules", "Expectations"),
    ("study", "How to study"),
    ("science", "The science of memory"),
    ("latin", "Why Latin"),
    ("slowdown", "Slow-down messages"),
]
LEGES = ("leges-how", "leges-dont")                 # numbered in this order: how-to first
HOME = LEGES + ("rules", "study", "science", "latin")   # what the home screen rotates through

DEFAULT_SLOWDOWN = "Festīnā lentē — make haste slowly! Read each answer before you grade it."


def key(line_id):
    return PREFIX + str(line_id)


def new_custom_id():
    return "custom-" + uuid.uuid4().hex[:8]


def load(path=PATH):
    """[{"id", "category", "text", "note"}] in file order."""
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    return [{"id": str(l["id"]), "category": l.get("category", "rules"),
             "text": str(l.get("text") or "").strip(), "note": l.get("note") or ""}
            for l in doc.get("lines") or []]


def fingerprint(line):
    text = "%s\u0000%s" % (line.get("category", ""), (line.get("text") or "").strip())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def problems(line):
    out = []
    if not (line.get("text") or "").strip():
        out.append("say something")
    if len((line.get("text") or "")) > 400:
        out.append("keep it under 400 characters — it has to fit in a speech bubble")
    if line.get("category") not in dict(CATEGORIES):
        out.append("pick a kind of line")
    return out


_NUMERALS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
             (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def roman(n):
    out = ""
    for value, numeral in _NUMERALS:
        while n >= value:
            out += numeral
            n -= value
    return out


def number_leges(lines):
    """The laws among these lines, numbered I, II, III ...: every how-to law,
    then every what-not-to-do law, each kind in its own order. Pass only the
    approved lines: a law waiting for approval takes no number."""
    laws = [l for c in LEGES for l in lines if l.get("category") == c]
    return [dict(l, n=i, numeral=roman(i)) for i, l in enumerate(laws, 1)]


def rotate(lines, student, n):
    """The n-th line for this student: each student walks through all the
    lines in their own order before any repeats."""
    if not lines:
        return None
    order = sorted(lines, key=lambda l: hashlib.sha256(
        ("%s|%s" % (student, l["id"])).encode("utf-8")).hexdigest())
    return order[n % len(order)]
