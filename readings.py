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
        for n, phrase in (q.get("hint") or {}).items():
            s = reading["by_n"].get(int(n))
            if s is None or _find(s, phrase) is None:
                out.append("question %s: its hint %r isn't in sentence %s" % (q.get("id"), phrase, n))
    return out


def word_id(n, i):
    """The id of piece i of sentence n on the page."""
    return "w%s-%s" % (n, i)


def _find(sentence, phrase):
    """Piece indexes covering `phrase` (its words, in order, punctuation
    ignored) in the sentence, or None."""
    flat = []                                 # (piece index, folded word)
    for i, p in enumerate(sentence["pieces"]):
        if p["kind"] == "word":
            flat += [(i, _fold(w)) for w in p["text"].split()]
    want = [_fold(w) for w in _TOKEN.findall(phrase or "") if w[0].isalpha()]
    for start in range(len(flat) - len(want) + 1):
        if want and [w for _, w in flat[start:start + len(want)]] == want:
            return sorted({i for i, _ in flat[start:start + len(want)]})
    return None


def hint_targets(reading, q):
    """The words "See hint" highlights: the question's hint phrases, or failing
    that, every word of the sentences it looks at."""
    out = []
    hint = q.get("hint") or {}
    if hint:
        for n, phrase in hint.items():
            s = reading["by_n"].get(int(n))
            found = _find(s, phrase) if s else None
            out += [word_id(int(n), i) for i in (found or [])]
    else:
        for n in q.get("look") or []:
            s = reading["by_n"].get(n)
            out += [word_id(n, i) for i, p in enumerate(s["pieces"]) if p["kind"] == "word"] if s else []
    return out


def grade_one(reading, qid, picked):
    """"right" | "wrong" | "blank" for one question, or None if there is no such question."""
    for q in reading.get("questions") or []:
        if q["id"] == qid:
            return "blank" if not picked else ("right" if picked == q["answer"] else "wrong")
    return None


def questions_by_paragraph(reading):
    """One list of questions per paragraph: each question sits with the
    paragraph holding the first sentence it asks about, so a student answers
    while reading rather than after. Questions keep their story order and
    their numbers (1, 2, 3 ... across the whole passage)."""
    paras = reading.get("paragraphs") or []
    where = {n: i for i, p in enumerate(paras) for n in p}
    out = [[] for _ in paras]
    for num, q in enumerate(reading.get("questions") or [], start=1):
        look = q.get("look") or []
        i = where.get(look[0], len(paras) - 1) if look else len(paras) - 1
        out[i].append(dict(q, number=num))
    return out


def grade(reading, picked):
    """{question id: "right" | "wrong" | "blank"} for a dict of picks."""
    out = {}
    for q in reading.get("questions") or []:
        p = picked.get(q["id"])
        out[q["id"]] = "blank" if not p else ("right" if p == q["answer"] else "wrong")
    return out
