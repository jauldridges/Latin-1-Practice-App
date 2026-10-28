"""
Badge lessons: the short, step-by-step lesson a student meets before a badge's
first check, so the map feels like a course -- Lesson 1, Lesson 2 -- rather
than a quiz bank. The lessons are in badge_lessons.yaml, one per badge.

A lesson is a few STEPS, revealed one at a time:

  say:      a paragraph or two. *Latin* is set in Latin style, **bold** is bold;
            a blank line starts a new paragraph.
  example:  a worked example, animated: the Latin words appear, then one at a
            time each lights up and its label drops in under it (its job, and
            why), then the English. {intro, words: [{w, tag, note}], english,
            after}. A word with no tag is shown but not labeled.
  table:    endings, the rows appearing one by one. {caption, head, rows};
            **bold** marks the ending.
  check:    a one-tap quick check, answered on the page and never recorded --
            a moment to think, not a grade. {ask, options, answer, why}
  remember: the one line to keep, at the end.

A student sees a lesson only once the teacher has approved that exact wording
(teacher -> Grammar badges -> Lessons), the same rule as teaching text and the
Magister: the approval is a fingerprint under "lesson:<badge id>", so a lesson
edited afterwards needs approving again. Without an approved lesson a badge
starts straight at its check, as before.
"""

import hashlib
import html
import json
import os
import re

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "badge_lessons.yaml")
PREFIX = "lesson:"
KINDS = ("say", "example", "table", "check", "remember")


def key(badge_id):
    return PREFIX + badge_id


def load(path=PATH):
    """{badge id: {"steps": [...]}}."""
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    return {str(k): {"steps": list((v or {}).get("steps") or [])}
            for k, v in (doc.get("lessons") or {}).items()}


def fingerprint(lesson):
    blob = json.dumps(lesson.get("steps") or [], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def kind(step):
    for k in KINDS:
        if k in step:
            return k
    return None


def problems(lesson):
    """What is wrong with a lesson, in plain words. Empty is fine."""
    out = []
    steps = lesson.get("steps") or []
    if not steps:
        out.append("no steps")
    if not any(kind(s) == "example" for s in steps):
        out.append("no worked example")
    for i, s in enumerate(steps, 1):
        k = kind(s)
        if k is None:
            out.append("step %d: say, example, table, check or remember?" % i)
        elif k == "example":
            ex = s["example"] or {}
            if not ex.get("words") or not ex.get("english"):
                out.append("step %d: an example needs words and the English" % i)
            for w in ex.get("words") or []:
                if not str(w.get("w") or "").strip():
                    out.append("step %d: a word with no Latin" % i)
        elif k == "table":
            t = s["table"] or {}
            n = len(t.get("head") or [])
            if not n or any(len(r) != n for r in t.get("rows") or []):
                out.append("step %d: every table row needs as many cells as the heading" % i)
        elif k == "check":
            c = s["check"] or {}
            if c.get("answer") not in (c.get("options") or {}):
                out.append("step %d: the quick check's answer is not one of its options" % i)
            if not str(c.get("why") or "").strip():
                out.append("step %d: the quick check needs a why" % i)
    return out


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LATIN = re.compile(r"\*(.+?)\*")


_QUOTED = re.compile(r'"([^"]*)"')


def inline(text):
    """**bold** and *Latin*, "straight quotes" made curly, everything else escaped."""
    t = _QUOTED.sub("\u201c\\1\u201d", str(text or ""))
    t = html.escape(t, quote=False)
    t = _BOLD.sub(r"<strong>\1</strong>", t)
    t = _LATIN.sub(r'<em class="la">\1</em>', t)
    return t


def paragraphs(text):
    return ["%s" % inline(p.strip()) for p in re.split(r"\n\s*\n", str(text or "")) if p.strip()]


def numbered(badges, spec, first_taught):
    """{badge id: lesson number}: the order the class meets them, which is the
    order their first topics are taught (then the order in badges.yaml)."""
    order = sorted(badges, key=lambda b: (first_taught(b, spec), badges.index(b)))
    return {b["id"]: n for n, b in enumerate(order, 1)}
