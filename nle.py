"""
Past National Latin Exams: real questions from the Latin I / Beginning Latin
exams (and two Introduction to Latin exams), used two ways.

  1. AS PRACTICE. Every question carries the course topic it tests (`node`), so
     the grammar ones join the badge checks and topic practice as soon as that
     topic -- and anything else it `needs` -- has been taught, flagged "From the
     2019 National Latin Exam" so students see what the exam asks.
  2. AS PRACTICE NLES (/nle). A whole past exam, or a mash-up from several, sat
     straight through like the real thing and graded at the end. Each miss
     offers the hint and the lesson for its topic, and the lesson leads back.

The exams are in nle/*.yaml, one per exam, transcribed from the PDFs (the
NLE's permission covers non-commercial classroom use). No answer keys were
supplied, so the answers were worked out by hand: the teacher can check them
on Teacher -> Practice NLE.

The questions are PRE-APPROVED: at startup sync() copies them into the
question bank as approved, the first time each appears. After that the bank is
the truth -- a question the teacher rejects stays rejected, and one edited in
the review tool keeps the edit over the file.

A question that needs its passage or its picture is `exam_only`: it is shown
only inside a practice NLE, never alone in a badge check.
"""

import copy
import glob
import hashlib
import json
import os
import random
import re
import time

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(ROOT, "nle")
PREFIX = "NLE-"
CONTEXT = "nle"
SETTING = "nle_synced"

# A question about a word's meaning has no grammar topic in the spec (the
# vocabulary is taught from weekly lists), so it is filed here.
VOCAB = "VOCAB"
EXTRA_LABELS = {VOCAB: "Vocabulary"}

KIND_TITLE = {"latin1": "Latin I", "beginning": "Beginning Latin",
              "reading": "Reading Comprehension", "intro": "Introduction to Latin"}

# The NLE's awards on a 40-question exam, highest first.
AWARDS = [(37, "Summa Cum Laude", "gold"), (33, "Maxima Cum Laude", "silver"),
          (30, "Magna Cum Laude", ""), (27, "Cum Laude", "")]

MASHUP_SIZES = (20, 40)


def item_id(exam_id, n):
    return "%s%s-%02d" % (PREFIX, exam_id, n)


def is_nle(item_or_id):
    iid = item_or_id.get("id") if isinstance(item_or_id, dict) else item_or_id
    return str(iid or "").startswith(PREFIX)


def label(exam):
    """What a question says about where it came from."""
    if exam["kind"] in ("latin1", "beginning"):
        return "%d National Latin Exam" % exam["year"]
    return "%d National Latin Exam (%s)" % (exam["year"], KIND_TITLE[exam["kind"]])


def _payload(exam, it):
    p = {
        "id": item_id(exam["id"], it["n"]),
        "node": it["node"],
        "assess": "recognize",
        "tier": 1,
        "format": "choice",
        "stem": it["stem"],
        "options": dict(it["options"]),
        "answer": it["answer"],
        "keep_order": True,          # A-D as printed: some options are map numbers or in order
        "nle": {"exam": exam["id"], "n": it["n"], "year": exam["year"], "label": label(exam)},
    }
    for k in ("needs", "underline", "image", "passage"):
        if it.get(k):
            p[k] = it[k]
    if it.get("passage") or it.get("image"):
        p["exam_only"] = True
    return p


_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_CACHE = {}


def load(path=DIR):
    """Every exam, newest first: {id, year, kind, title, label, passages{id: p},
    items[payload, in exam order]}. Read once per set of files: fifteen exams
    take half a second to parse, and the server is imported afresh per test."""
    files = sorted(glob.glob(os.path.join(path, "*.yaml")))
    stamp = tuple((f, os.path.getmtime(f)) for f in files)
    if _CACHE.get(path, (None,))[0] == stamp:
        return copy.deepcopy(_CACHE[path][1])
    out = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            doc = yaml.load(fh, Loader=_LOADER) or {}
        ex = dict(doc["exam"])
        ex["label"] = label(ex)
        ex["name"] = "%d %s" % (ex["year"], KIND_TITLE[ex["kind"]])
        ex["passages"] = {p["id"]: p for p in doc.get("passages") or []}
        ex["items"] = [_payload(ex, it) for it in doc.get("items") or []]
        out.append(ex)
    out.sort(key=lambda e: (-e["year"], e["kind"] != "beginning" and e["kind"] != "latin1", e["id"]))
    _CACHE[path] = (stamp, out)
    return copy.deepcopy(out)


def problems(exams, spec):
    """What is wrong with the exam files, in plain words. Empty is fine."""
    out = []
    for e in exams:
        for p in e["items"]:
            where = "%s q%d" % (e["id"], p["nle"]["n"])
            if p["node"] not in spec and p["node"] not in EXTRA_LABELS:
                out.append("%s: unknown topic %s" % (where, p["node"]))
            for n in p.get("needs") or []:
                if n not in spec:
                    out.append("%s: needs unknown topic %s" % (where, n))
            if p["answer"] not in p["options"]:
                out.append("%s: answer is not an option" % where)
            if p.get("passage") and p["passage"] not in e["passages"]:
                out.append("%s: no passage %s" % (where, p["passage"]))
            if p.get("image") and not os.path.exists(os.path.join(ROOT, "static", p["image"])):
                out.append("%s: missing picture %s" % (where, p["image"]))
    return out


# --------------------------------------------------------------------------
# Into the question bank, pre-approved
# --------------------------------------------------------------------------

def fingerprint(exams):
    blob = json.dumps([e["items"] for e in exams], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def sync(conn, exams):
    """Put every exam question in the bank, approved. Cheap when nothing has
    changed (one settings read). A new question arrives approved; an existing
    one gets the file's wording unless the teacher edited it in the review
    tool; a decision the teacher made is never overwritten."""
    import store
    fp = fingerprint(exams)
    if store.get_setting(conn, SETTING) == fp:
        return {"inserted": 0, "updated": 0}
    now = time.time()
    reason = "Pre-approved: past National Latin Exam"
    inserted = updated = 0
    # One transaction, plain statements: on the hosted database the first boot
    # writes ~600 questions, and a commit per question would be a slow start.
    for e in exams:
        for p in e["items"]:
            row = conn.execute("SELECT review_status, edited FROM items WHERE item_id=?",
                               (p["id"],)).fetchone()
            payload = json.dumps(p, ensure_ascii=False)
            approve = row is None or row["review_status"] == "unreviewed"
            if row is None:
                conn.execute(
                    """INSERT INTO items (item_id, node_id, assess, tier, fmt,
                           macron_matters, source_file, payload, review_status,
                           review_reason, flagged, flag_json, created_at, updated_at)
                       VALUES (?,?,?,?,?,0,?,?,'approved',?,0,'[]',?,?)""",
                    (p["id"], p["node"], p["assess"], p["tier"], p["format"],
                     "nle/%s.yaml" % e["id"], payload, reason, now, now))
                inserted += 1
            else:
                if not row["edited"]:
                    conn.execute("UPDATE items SET node_id=?, payload=?, updated_at=? WHERE item_id=?",
                                 (p["node"], payload, now, p["id"]))
                    updated += 1
                if approve:
                    conn.execute("UPDATE items SET review_status='approved', review_reason=?, "
                                 "updated_at=? WHERE item_id=?", (reason, now, p["id"]))
            if approve:
                conn.execute("INSERT INTO decisions (item_id, status, reason, edited, session_id, created_at) "
                             "VALUES (?,?,?,0,NULL,?)", (p["id"], "approved", reason, now))
    store.set_setting(conn, SETTING, fp)
    conn.commit()
    return {"inserted": inserted, "updated": updated}


# --------------------------------------------------------------------------
# What may be served where
# --------------------------------------------------------------------------

def needs_met(item, taught):
    """A question's own topic is checked by whoever serves it; this is the rest
    of what it leans on (a dative question written with a third-declension
    noun needs the third declension too)."""
    return all(n in taught for n in item.get("needs") or [])


def covered(item, taught):
    """Has the class met everything this question asks? Topics outside the
    spec (Vocabulary) count as covered."""
    node = item.get("node")
    if node not in EXTRA_LABELS and node not in taught:
        return False
    return needs_met(item, taught)


# --------------------------------------------------------------------------
# A practice NLE: a whole exam, or a mash-up
# --------------------------------------------------------------------------

def exam_ids(exam, live):
    """A whole exam in its printed order, minus anything rejected since."""
    return [p["id"] for p in exam["items"] if p["id"] in live]


def mashup(exams, live, taught, size, seed, seen=()):
    """A mixed exam from several years on what has been covered. `size` 20 is
    all single questions; 40 adds one reading passage with its questions, as
    the real exam ends with one. Questions this student has not met in a
    practice NLE come first. Laid out the way the exam is: language first,
    then culture and Latin in use, then the reading."""
    rng = random.Random(seed)
    seen = set(seen)
    single = [p for e in exams if e["kind"] != "reading" for p in e["items"]
              if p["id"] in live and not p.get("passage") and covered(p, taught)]
    rng.shuffle(single)
    single.sort(key=lambda p: p["id"] in seen)          # stable: unseen first
    reading = []
    if size >= 40:
        sets = []
        for e in exams:
            if e["kind"] == "reading":
                continue
            for pid, pas in e["passages"].items():
                qs = [p for p in e["items"] if p.get("passage") == pid and p["id"] in live]
                if 6 <= len(qs) <= 12:
                    sets.append(qs)
        if sets:
            rng.shuffle(sets)
            sets.sort(key=lambda qs: sum(p["id"] in seen for p in qs))
            reading = sets[0]
    want = max(0, size - len(reading))
    picked = []
    per_exam = {}
    cap = max(4, want // 4)                               # a mash-up: no exam dominates
    for p in single:
        if len(picked) >= want:
            break
        ex = p["nle"]["exam"]
        if per_exam.get(ex, 0) >= cap:
            continue
        per_exam[ex] = per_exam.get(ex, 0) + 1
        picked.append(p)
    for p in single:                                      # top up if the cap left a gap
        if len(picked) >= want:
            break
        if p not in picked:
            picked.append(p)
    culture = lambda p: p["node"].startswith(("RW", "MW"))
    picked.sort(key=lambda p: (culture(p), p["nle"]["n"], p["id"]))
    return [p["id"] for p in picked + reading]


def score_award(right, total):
    """The NLE award this score would earn on a 40-question exam, or None."""
    if total != 40:
        return None
    for cut, name, medal in AWARDS:
        if right >= cut:
            return {"name": name, "medal": medal}
    return None


# --------------------------------------------------------------------------
# Showing a question
# --------------------------------------------------------------------------

def mark_up(text, underline):
    """Escape, then underline each listed word or phrase where it stands as a
    whole word -- how the exam marks the part a question is about."""
    import html
    out = html.escape(str(text or ""), quote=False)
    for w in sorted(set(underline or []), key=len, reverse=True):
        ew = html.escape(w, quote=False)
        out = re.sub(r"(?<![\w>])%s(?![\w<])" % re.escape(ew), "<u>%s</u>" % ew, out)
    return out


_LINES = re.compile(r"\blines? (\d+)(?:\s*[-–]\s*(\d+))?")


def look_back(item):
    """For a reading question, the lines it points at: (first, last) or None."""
    m = _LINES.search(item.get("stem") or "")
    if not m:
        return None
    a = int(m.group(1))
    return (a, int(m.group(2) or a))
