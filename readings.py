"""
The Reader: a class passage where any word can be tapped for its gloss, with
comprehension questions after.

One YAML file per passage in readings/. Each sentence is plain text plus two
gloss maps keyed by the word as it appears in that sentence:

  new:    the words the teacher underlined in her packet, glossed as she
          glosses them. These are underlined on screen too, so the page looks
          like the paper the class has.
  words:  every other word, so a student can tap anything. A tap on a word
          they should already know still helps, and costs them a moment.

A gloss is "meaning · note", the note being the grammar label the packet
uses ("Direct Object, accusative"). A key may be several words ("in perīculō")
and is matched as a unit, longest first.

Questions are English multiple choice (CR-009), each naming the sentences that
answer it. Answers are recorded as events with context "reading": they show up
in the teacher's results for the passage, and they are not homework cards --
reading is not on the 50 + 50 (teacher.NOT_HOMEWORK).

A passage reaches students only once the teacher publishes it (Teacher
dashboard -> Reader), and the teacher can always open it to preview or project.
"""

import glob
import os
import re

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(ROOT, "readings")
CONTEXT = "reading"
NODE = "CR-009"          # Answer comprehension questions in English about a Latin passage

_TOKEN = re.compile(r"[^\W\d_]+|\d+|\s+|[^\w\s]", re.UNICODE)


def item_id(slug, qid):
    return "read:%s:%s" % (slug, qid)


def _fold(word):
    return (word or "").lower()


def tokenize(text):
    return _TOKEN.findall(text or "")


def _split_gloss(g):
    g = str(g or "")
    if " · " in g:
        meaning, note = g.split(" · ", 1)
        return meaning.strip(), note.strip()
    return g.strip(), ""


def pieces(sentence):
    """The sentence as [{"text", "kind", "gloss", "note", "new"}], with every
    glossed word or phrase one piece. kind is word, space or punct."""
    glosses = {}
    for new, src in ((True, sentence.get("new") or {}), (False, sentence.get("words") or {})):
        for k, v in src.items():
            glosses.setdefault(tuple(_fold(w) for w in str(k).split()), (v, new))
    longest = max((len(k) for k in glosses), default=1)
    toks = tokenize(sentence.get("text"))
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t.isspace():
            out.append({"text": t, "kind": "space"})
            i += 1
            continue
        if not t[0].isalpha():               # punctuation, and numbers like 458
            out.append({"text": t, "kind": "punct"})
            i += 1
            continue
        matched = False
        for n in range(longest, 0, -1):
            # n words need 2n-1 tokens: word, space, word ...
            span = toks[i:i + 2 * n - 1]
            if len(span) < 2 * n - 1:
                continue
            words = span[0::2]
            if any(not s.isspace() for s in span[1::2]):
                continue
            key = tuple(_fold(w) for w in words)
            if key in glosses:
                g, new = glosses[key]
                meaning, note = _split_gloss(g)
                out.append({"text": "".join(span), "kind": "word", "gloss": meaning,
                            "note": note, "new": new})
                i += len(span)
                matched = True
                break
        if not matched:
            out.append({"text": t, "kind": "word", "gloss": "", "note": "", "new": False})
            i += 1
    return out


def load_one(path):
    with open(path, encoding="utf-8") as f:
        r = yaml.safe_load(f) or {}
    r["path"] = path
    r["by_n"] = {s["n"]: s for s in r.get("sentences") or []}
    for s in r.get("sentences") or []:
        s["pieces"] = pieces(s)
    for q in r.get("questions") or []:
        q["item_id"] = item_id(r["slug"], q["id"])
    return r


def load_all(folder=FOLDER):
    """{slug: reading}, in file-name order."""
    out = {}
    for p in sorted(glob.glob(os.path.join(folder, "*.yaml"))):
        r = load_one(p)
        out[r["slug"]] = r
    return out


def problems(reading):
    """What is wrong with a passage, in plain words. Empty is fine."""
    out = []
    ns = [s.get("n") for s in reading.get("sentences") or []]
    if ns != list(range(1, len(ns) + 1)):
        out.append("sentences must be numbered 1, 2, 3 ... in order")
    in_paragraphs = [n for p in reading.get("paragraphs") or [] for n in p]
    if sorted(in_paragraphs) != sorted(ns):
        out.append("every sentence must be in exactly one paragraph")
    for s in reading.get("sentences") or []:
        used = {_fold(p["text"]) for p in s["pieces"] if p["kind"] == "word"}
        for src in ("new", "words"):
            for k in (s.get(src) or {}):
                if " ".join(_fold(w) for w in str(k).split()) not in used:
                    out.append("sentence %s: %r is glossed but not in the sentence" % (s["n"], k))
        for p in s["pieces"]:
            if p["kind"] == "word" and not p["gloss"]:
                out.append("sentence %s: %r has no gloss" % (s["n"], p["text"]))
    for q in reading.get("questions") or []:
        if q.get("answer") not in (q.get("options") or {}):
            out.append("question %s: its answer is not one of its options" % q.get("id"))
        if any(n not in reading["by_n"] for n in q.get("look") or []):
            out.append("question %s: it points at a sentence that doesn't exist" % q.get("id"))
    return out


def grade(reading, picked):
    """{question id: "right" | "wrong" | "blank"} for a dict of picks."""
    out = {}
    for q in reading.get("questions") or []:
        p = picked.get(q["id"])
        out[q["id"]] = "blank" if not p else ("right" if p == q["answer"] else "wrong")
    return out
