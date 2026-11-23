"""
DI mode: running a lesson.

The lessons are data (di/first-declension.yaml); di.py reads the Latin. This
module turns each item line into screens (steps), lays a lesson out as a
sequence of screens, and moves a student through it the way the DI plan says
(sections 3, 5, 6):

  * every lesson runs Parts A–F in order (B1 in Lessons 6, 8, 10);
  * a wrong answer in Parts A–E brings the correction: the model (the right
    answer, one line of rule, the audio), the same item straight away, the
    two items before it plus the missed one again, and the missed item 3–6
    items later and in the next lesson's Part D;
  * a right answer to a one-tap item slower than 6 seconds comes back later
    in the lesson, with no correction;
  * Part F is the check: fresh items, no help, 7 of 8 right first try is
    Ready (Lesson 12: 14 of 16); below that is Again: Part B's examples and
    Part C rerun, then the other check set;
  * the placement test runs once, with no corrections, and places the
    student at the first lesson with a missed item.

A run's state is a small JSON document kept per student in the settings
table (store.get_setting), so a student can stop and pick up again on any
device. Every answer is written to the event log (context "di"), which is
where progress, the teacher's view and the flags come from: DI mode grades
nothing, and none of it counts toward homework or practice.
"""

import hashlib
import json
import os
import random
import re
import time

import yaml

import di

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "di", "first-declension.yaml")
CONTEXT = "di"
SLOW_MS = 6000
ONE_TAP = {"F1", "F2", "F3", "F5", "F7"}
LAST = 12
NEXT = "next"

_DOC = None


def load(path=PATH):
    global _DOC
    if _DOC is None or path != PATH:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        doc["by_n"] = {L["n"]: L for L in doc["lessons"]}
        if path != PATH:
            return doc
        _DOC = doc
    return _DOC


def lesson(n):
    return load()["by_n"].get(int(n))


# --------------------------------------------------------------------------
# Words a lesson knows (for meaning distractors and the content checks)
# --------------------------------------------------------------------------

def words_taught(n):
    """Every Part A word of Lessons 0..n."""
    out = []
    for m in range(0, int(n) + 1):
        L = lesson(m)
        if L:
            out += list(((L.get("A") or {}) if isinstance(L.get("A"), dict) else {}).get("words") or [])
    return out


def stems_taught(n):
    stems = set()
    for w in words_taught(n):
        for part in w.split(","):
            t = di.word(part.strip())
            if t["kind"] in ("noun", "verb", "prep"):
                stems.add((t["kind"], t["stem"]))
            elif t["kind"] in ("et", "non"):
                stems.add((t["kind"], t["kind"]))
    return stems


# --------------------------------------------------------------------------
# Item lines -> screens
# --------------------------------------------------------------------------

def _fields(line):
    """("F2", "Nauta **puellam** vocat.", ["..."], {"buttons": [...], "gloss": "..."})"""
    code, _, rest = str(line).partition(" ")
    parts = [p.strip() for p in rest.split(" | ")]
    opts = {}
    keep = []
    for p in parts:
        if p.startswith("buttons:"):
            opts["buttons"] = p[len("buttons:"):].split()
        elif p.startswith("gloss:"):
            opts["gloss"] = p[len("gloss:"):].strip()
        else:
            keep.append(p)
    return code, keep[0] if keep else "", keep[1:], opts


def _md(text):
    """**bold**, *Latin*, a blank line between paragraphs; everything escaped."""
    import lessons
    paras = re.split(r"\n\s*\n", str(text or "").strip())
    return "".join("<p>%s</p>" % lessons.inline(p.strip()) for p in paras if p.strip())


def _md_inline(text):
    import lessons
    return lessons.inline(text)


def _end(latin):
    m = re.search(r"[.!?]\s*$", latin or "")
    return m.group(0).strip() if m else ""


def _plain(latin):
    return latin.replace("**", "")


def _job_options(n, only=None, include_verb=False):
    jobs = only or [j for j in ("verb", "subject", "dobj", "poss", "tofor", "objprep")
                    if include_verb or j != "verb"]
    opts = []
    for j, label, case in di.job_buttons(n, jobs):
        opts.append({"v": j, "label": label, "sub": case})
    return opts


def _shuffle(opts, key):
    k = int(hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:8], 16)
    rnd = random.Random(k)
    opts = list(opts)
    rnd.shuffle(opts)
    return opts


TABLE_ROWS = {"nom": ("Subject", "nominative", "-a", "-ae"),
              "gen": ("Possession", "genitive", "-ae", "-ārum"),
              "dat": ("To / for", "dative", "-ae", "-īs"),
              "acc": ("Direct object", "accusative", "-am", "-ās"),
              "abl": ("Object of the preposition", "ablative", "-ā", "-īs")}

E_RULE = {"subject": "does the verb: the **subject**.",
          "dobj": "receives the verb: the **direct object**.",
          "poss": "is the owner: **possession**.",
          "tofor": "gets the direct object: **to / for**.",
          "objprep": "comes after the preposition: the **object of the preposition**.",
          "verb": "is the action word: the **verb**."}


def _choice(prompt, show, options, answer, rule, audio=None, fmt="", onetap=False, gloss=None):
    return {"kind": "choice", "prompt": prompt, "show": show, "options": options,
            "answer": [answer] if isinstance(answer, str) else list(answer), "rule": rule,
            "audio": audio, "fmt": fmt, "onetap": onetap, "gloss": gloss}


def _tap(prompt, toks, end, answer, rule, extra=None, audio=None, fmt="", english=False, gloss=None):
    return {"kind": "tap", "prompt": prompt, "tokens": toks, "end": end,
            "answer": [str(a) for a in answer], "rule": rule, "extra": extra or [],
            "audio": audio, "fmt": fmt, "onetap": False, "english": english, "gloss": gloss}


def _latin_show(latin, highlight=None):
    """Display of a Latin sentence; `highlight` is a token index to bold."""
    if highlight is None:
        return {"html": _md_inline(latin), "latin": True}
    toks = di.tokens(latin)
    words = []
    for t in toks:
        w = t["w"]
        words.append("**%s**" % w if t["i"] == highlight else w)
    return {"html": _md_inline(" ".join(words) + _end(latin)), "latin": True}


def _tokens_for_tap(latin):
    return [{"i": t["i"], "w": t["w"]} for t in di.tokens(_plain(latin))]


def _job_step(n, latin, idx, form, job, buttons=None, fmt="F2", key="", gloss=None):
    opts = _job_options(n, buttons)
    if job not in [o["v"] for o in opts]:
        opts = _job_options(max(n, di.JOB_FROM.get(job, 0)), (buttons or []) + [job] if buttons else None)
    return _choice("What job does the highlighted word do?", _latin_show(_plain(latin), idx),
                   opts, job, di.rule_line(form, job), audio=_plain(latin), fmt=fmt,
                   onetap=fmt == "F2", gloss=gloss)


def _number_step(latin, idx, tok, key="", fmt="F3"):
    num = tok["num"]
    show = _latin_show(_plain(latin), idx) if idx is not None else {"html": _md_inline("*%s*" % tok["w"]), "latin": True}
    opts = [{"v": "sg", "label": "One", "sub": ""}, {"v": "pl", "label": "More than one", "sub": ""}]
    rule = "*%s* ends in **-%s**: %s." % (tok["w"], tok["ending"], "more than one" if num == "pl" else "one")
    return _choice("One, or more than one?", show, opts, num, rule, audio=tok["w"], fmt=fmt, onetap=True)


def _translation_step(n, latin, key, focus):
    ch = di.choices(_plain(latin), focus=focus, key=key)
    opts = [{"v": str(i), "label": t, "sub": ""} for i, (t, _) in enumerate(ch)]
    right = next(str(i) for i, (_, r) in enumerate(ch) if r)
    right_text = next(t for t, r in ch if r)
    p = di.parse(_plain(latin))
    tok = next((t for t in p["tokens"] if focus and t.get("ending") == focus and t["kind"] == "noun"), None)
    rule = "**%s**" % right_text
    if tok is not None:
        rule += "\n\n" + di.rule_line(tok["w"], tok["job"])
    return _choice("Which is the translation?", {"html": _md_inline(_plain(latin)), "latin": True},
                   opts, right, rule, audio=_plain(latin), fmt="F6")


def _subject_num_for_blank(latin):
    toks = di.tokens(latin)
    preps = {t["i"] + 1 for t in toks if t["kind"] == "prep"}
    for t in toks:
        if t["kind"] == "noun" and t["i"] not in preps and t["ending"] == "a":
            return "sg"
    if any(t["kind"] == "noun" and t["ending"] == "ae" for t in toks):
        return "pl"
    return "sg"


def _f5_step(latin, fmt="F5"):
    """Pick -t or -nt for a verb stem written stem__ (or for the verb of a
    whole sentence, shown as its stem)."""
    toks = di.tokens(latin)
    if "__" in latin:
        num = _subject_num_for_blank(latin)
        # Every verb in the strand is first conjugation: keep its -a- (porta__,
        # not port__), so -t and -nt each make a real verb.
        shown = re.sub(r"(\S+?)__", lambda m: m.group(1) + ("" if m.group(1).endswith("a") else "a") + "__",
                       latin)
    else:
        verb = next(t for t in toks if t["kind"] == "verb")
        num = verb["num"]
        stem = verb["w"][:-1] if num == "sg" else verb["w"][:-2]       # portat, portant -> porta
        shown = latin.replace(verb["w"], stem + "__", 1)
    subj = next((t for t in di.parse(latin.replace("__", "at" if num == "sg" else "ant"))["tokens"]
                 if t.get("job") == "subject"), None)
    rule = di.verb_rule(num)
    if subj is not None:
        rule = "*%s* is %s. %s" % (subj["w"], "more than one" if num == "pl" else "one", rule)
    opts = [{"v": "t", "label": "-t", "sub": ""}, {"v": "nt", "label": "-nt", "sub": ""}]
    return _choice("Which verb ending?", {"html": _md_inline(shown.replace("__", "___")), "latin": True},
                   opts, "nt" if num == "pl" else "t", rule, fmt=fmt, onetap=True)


def _context(body, more):
    """F4 / F8E: (English sentence with the target in **bold**, Latin
    sentence with the word's stem and ___, the ending)."""
    return body.strip(), more[0].strip(), more[1].strip()


def _filled_word(latin, ending):
    word = next(w for w in latin.split() if "___" in w)
    return word.replace("___", ending).strip(".,;")


def _bold_text(en):
    return en.split("**")[1] if "**" in en else en


def _context_html(en, latin):
    return ("<p class=\"di-cue\">%s</p><p class=\"di-stem\"><em class=\"la\">%s</em></p>"
            % (_md_inline(en), _md_inline(latin)))


def steps_for(ref, n=None):
    """The screens of one item (or note / model), in order."""
    raw, n = resolve(ref, n)
    if isinstance(raw, dict):                           # a model screen, a reading, the intro
        if raw.get("intro"):
            return [{"kind": "intro", "fmt": "INTRO"}]
        if "lines" in raw:
            return [{"kind": "reading", "title": raw.get("title", ""),
                     "lines": [_md_inline("*%s*" % l) for l in raw["lines"]],
                     "audio": " ".join(raw["lines"]), "fmt": "READ"}]
        text = raw.get("text", "")
        table = None
        if text.startswith("TABLE"):
            table = [TABLE_ROWS[r] for r in text.split()[1:]]
            text = ""
        audio = raw.get("audio")
        return [{"kind": "model", "html": _md(text), "table": table, "audio": audio,
                 "plain": bool(raw.get("plain")), "fmt": "MODEL"}]
    code, body, more, opts = _fields(raw)
    gloss = opts.get("gloss")
    L = lesson(n) or {}
    focus = L.get("new")
    key = "%s|%s" % (ref, raw)

    if code == "NOTE":
        return [{"kind": "note", "html": _md(body), "fmt": "NOTE"}]

    if code == "F1":
        pool = words_taught(n)
        ch = di.meaning_choices(body, pool, key=key)
        opts_ = [{"v": str(i), "label": t, "sub": ""} for i, (t, _) in enumerate(ch)]
        right = next(str(i) for i, (_, r) in enumerate(ch) if r)
        right_text = next(t for t, r in ch if r)
        return [_choice("What does it mean?", {"html": _md_inline("*%s*" % body), "latin": True}, opts_, right,
                        "*%s* means **%s**." % (body, right_text), audio=body.split(",")[0], fmt="F1",
                        onetap=True)]

    if code in ("F2", "F2F3", "F3F2", "F2T"):
        p = di.parse(body)
        tok = next(t for t in p["tokens"] if t.get("bold"))
        job = tok["job"]
        jstep = _job_step(n, body, tok["i"], tok["w"], job, opts.get("buttons"), fmt="F2", key=key, gloss=gloss)
        if code == "F2":
            return [jstep]
        nstep = _number_step(body, tok["i"], tok)
        if code == "F2F3":
            return [jstep, nstep]
        if code == "F3F2":
            return [nstep, jstep]
        return [jstep, _translation_step(n, body, key, focus)]

    if code == "F3":
        if "**" in body:
            p = di.parse(body)
            tok = next(t for t in p["tokens"] if t.get("bold"))
            return [_number_step(body, tok["i"], tok)]
        t = di.word(body)
        if t.get("ending") == "ae":                     # on its own, -ae is the plural subject
            t = dict(t, num="pl")
        return [_number_step(body, None, t)]

    if code == "F4":
        en, latin, ending = _context(body, more)
        form = _filled_word(latin, ending)
        rule = "“%s”: *%s*, with **-%s**." % (_bold_text(en), form, ending)
        opts_ = [{"v": e, "label": "-" + e, "sub": ""} for e in di.ending_buttons(max(n, di.ENDING_FROM[ending]))]
        return [_choice("Which ending does the Latin need?", {"html": _context_html(en, latin), "latin": True},
                        opts_, ending, rule, audio=latin.replace("___", ending), fmt="F4")]

    if code == "F5":
        return [_f5_step(body)]

    if code in ("F6", "F6N", "F6V"):
        latin = _plain(body)
        p = di.parse(latin)
        toks = _tokens_for_tap(latin)
        end = _end(latin)
        out = []
        verbs = [t for t in p["tokens"] if t["kind"] == "verb"]
        if code == "F6V":
            out.append(_f5_step(latin, fmt="F6"))
        elif len(verbs) == 1:
            out.append(_tap("Tap the verb.", toks, end, [verbs[0]["i"]], di.rule_line(verbs[0]["w"], "verb"),
                            audio=latin, fmt="F6", gloss=gloss))
        else:
            for k, v in enumerate(verbs):
                out.append(_tap("Tap the %s verb." % ("first" if k == 0 else "second"), toks, end, [v["i"]],
                                di.rule_line(v["w"], "verb"), audio=latin, fmt="F6", gloss=gloss))
        subj = p["clauses"][0]["subject"]
        if subj:
            out.append(_tap("Tap the subject.", toks, end, [t["i"] for t in subj],
                            di.rule_line(subj[0]["w"], "subject"), audio=latin, fmt="F6", gloss=gloss))
        subj_i = {t["i"] for t in subj}
        for t in p["tokens"]:
            if t["kind"] == "noun" and t["i"] not in subj_i:
                out.append(_job_step(n, latin, t["i"], t["w"], t["job"], fmt="F6", key=key, gloss=gloss))
                if code == "F6N" and t["job"] == "dobj":
                    out.append(_number_step(latin, t["i"], t, fmt="F6"))
        out.append(_translation_step(n, latin, key, focus))
        return out

    if code == "F7":
        e = di.ending_of(body)
        opts_ = [{"v": x, "label": "-" + x, "sub": ""} for x in di.ending_buttons(max(n, di.ENDING_FROM[e]))]
        return [dict(_choice("Listen. Which ending do you hear?", {"html": "", "latin": True, "echo": body},
                             opts_, e, "*%s* ends in **-%s**." % (body, e), audio=body, fmt="F7", onetap=True),
                     echo=body)]

    if code == "F8":
        latin = _plain(body)
        return [{"kind": "type", "mode": "english", "prompt": "Type the English.",
                 "show": {"html": _md_inline(latin), "latin": True}, "latin": latin,
                 "rule": "**%s**" % di.translate(latin), "audio": latin, "fmt": "F8"}]

    if code == "F8E":
        en, latin, ending = _context(body, more)
        form = _filled_word(latin, ending)
        return [{"kind": "type", "mode": "ending", "prompt": "Type the ending the Latin needs. Macrons aren't needed.",
                 "show": {"html": _context_html(en, latin), "latin": True},
                 "answer": ending, "rule": "“%s”: *%s*, with **-%s**." % (_bold_text(en), form, ending),
                 "audio": latin.replace("___", ending), "fmt": "F8"}]

    if code == "E3":
        chunks = [c.strip() for c in body.split(" / ")]
        toks = [{"i": i, "w": c} for i, c in enumerate(chunks)]
        out = [_tap("Tap the verb.", toks, ".", [1], "*%s* %s" % (chunks[1], E_RULE["verb"]), fmt="E", english=True),
               _tap("Tap the subject.", toks, ".", [0], "*%s* %s" % (chunks[0], E_RULE["subject"]), fmt="E",
                    english=True)]
        if len(chunks) > 2:
            out.append(_tap("Tap the direct object.", toks, ".", [2], "*%s* %s" % (chunks[2], E_RULE["dobj"]),
                            extra=[{"v": "none", "label": "No direct object"}], fmt="E", english=True))
        else:
            out.append(_tap("Tap the direct object.", toks, ".", ["none"],
                            "Nothing receives the verb: **no direct object**.",
                            extra=[{"v": "none", "label": "No direct object"}], fmt="E", english=True))
        return out

    if code == "E2":
        job = more[0]
        only = opts.get("buttons") or ["subject", "dobj"]
        bold = re.search(r"\*\*([^*]+)\*\*", body).group(1)
        options = [{"v": j, "label": di.JOB_LABEL[j],
                    "sub": di.CASE_NAME.get(j, "") if di.CASE_FROM.get(j, 99) <= n else ""} for j in only]
        return [_choice("What job does the highlighted word do?", {"html": _md_inline(body), "latin": False},
                        options, job, "*%s* %s" % (bold, E_RULE[job]), fmt="E", onetap=True)]

    if code == "ET":
        answer, prompt = more[0], more[1]
        pieces = re.split(r"(\[[^\]]+\])", body)
        toks, plain_parts = [], []
        for piece in pieces:
            if piece.startswith("["):
                toks.append({"i": len(toks), "w": piece[1:-1]})
                plain_parts.append(("tap", len(toks) - 1))
            elif piece.strip():
                plain_parts.append(("text", piece.strip()))
        extra = [{"v": "none", "label": "No direct object"}] if "direct object" in prompt else []
        if answer == "none":
            ans = ["none"]
            rule = "Nothing receives the verb: **no direct object**."
        else:
            ans = [str(next(t["i"] for t in toks if t["w"] == answer))]
            what = {"Tap the subject.": E_RULE["subject"], "Tap the direct object.": E_RULE["dobj"],
                    "Tap the verb.": E_RULE["verb"], "Tap the owner.": E_RULE["poss"],
                    "Tap who gets it.": E_RULE["tofor"],
                    "Tap the object of the preposition.": E_RULE["objprep"]}.get(prompt, "")
            rule = "*%s* %s" % (answer, what)
        step = _tap(prompt, toks, "", ans, rule, extra=extra, fmt="E", english=True)
        step["layout"] = plain_parts
        return [step]

    if code == "EV":
        shown, answer = body, more[0]
        base = shown.split("__")[0].split()[-1]
        suffix = "es" if re.search(r"(ch|sh|s|x)$", base) else "s"
        options = [{"v": suffix, "label": "-" + suffix, "sub": ""}, {"v": "none", "label": "no ending", "sub": ""}]
        rule = "One: *%s%s*. More than one: *%s*." % (base, suffix, base)
        return [_choice("Which ending does the verb take?", {"html": _md_inline(shown.replace("__", "___")), "latin": False},
                        options, answer if answer != "none" else "none", rule, fmt="E", onetap=True)]

    if code == "Q":
        right, wrongs = more[0], more[1:]
        options = _shuffle([{"v": "r", "label": right, "sub": ""}] +
                           [{"v": "w%d" % i, "label": w, "sub": ""} for i, w in enumerate(wrongs)], key)
        return [_choice(body, {"html": "", "latin": False}, options, "r", "**%s**" % right, fmt="F1")]

    raise ValueError("unknown item code %r in %s" % (code, ref))


# --------------------------------------------------------------------------
# References: "3/B/examples/4", "12/E/reading", "P/5", "1/A/w/puella"
# --------------------------------------------------------------------------

def resolve(ref, n=None):
    """(the raw item: a line or a model dict, its lesson number)."""
    bits = ref.split("/")
    doc = load()
    if len(bits) == 2 and bits[1] == "intro":          # the "Today" screen at the start of a run
        return {"intro": True}, (12 if bits[0] == "P" else int(bits[0]))
    if bits[0] == "P":
        return doc["placement"][int(bits[1])], 12
    L = doc["by_n"][int(bits[0])]
    n = L["n"]
    part = bits[1]
    if part == "A":
        A = L.get("A") or {}
        if bits[2] == "w":
            return "F1 " + "/".join(bits[3:]), n
        return A[bits[2]][int(bits[3])], n
    if part == "delayed":
        return L["delayed"], n
    if part == "D":
        return resolve("/".join(bits[2:]))[0], n
    val = L[part]
    if part == "F":
        return val[bits[2]][int(bits[3])], n
    if isinstance(val, list):
        return val[int(bits[2])], n
    if bits[2] == "reading" and len(bits) == 3:
        return val["reading"], n
    if bits[2] == "reading":
        return "F6 " + val["reading"]["lines"][int(bits[3])], n
    return val[bits[2]][int(bits[3])], n


def is_item(ref):
    raw, _ = resolve(ref)
    return isinstance(raw, str) and not raw.startswith("NOTE")


def item_code(ref):
    raw, _ = resolve(ref)
    return "MODEL" if isinstance(raw, dict) else str(raw).split(" ", 1)[0]


# --------------------------------------------------------------------------
# Laying a lesson out
# --------------------------------------------------------------------------

# Why each part is there, said to the student once, when the part begins.
PART_WHY = {
    "A": "Words first: you can't read an ending on a word you don't know.",
    "B1": "The job in English first, so you know what the Latin ending has to show.",
    "B": "Today's new ending, one small step at a time: see it, hear it, use it.",
    "C": "Endings that look alike. This is where mistakes happen, so you practice telling them apart.",
    "D": "Older endings come back so you keep them. The ones you missed come first.",
    "E": "The endings in whole sentences, the way you'll meet them in a story.",
    "F": "{k} new questions, no help. {p} right on the first try opens the next lesson.",
    "P": "No help, on purpose: it finds the first lesson you need, so you skip what you know.",
}
TAPS_WHY = ("Why so many taps? Each one is a decision you make every time you read Latin: find the "
            "verb, find the subject, read each ending's job, put it together. Doing them one at a "
            "time now is what makes reading fast later.")


def part_why(L, part):
    text = PART_WHY.get(part, "")
    if part == "F" and L:
        F = L.get("F") or {}
        text = text.format(k=len(F.get("A") or []), p=pass_mark(L))
    return ((L or {}).get("why") or {}).get(part) or text


def step_why(st, n):
    """One grey line under a step: why this step, in this order."""
    p, f, kind = st.get("prompt", ""), st.get("fmt", ""), st["kind"]
    if f == "E":
        return "Find the job in English first; the Latin ending will show the same job."
    if p.startswith("Tap the") and p.endswith("verb."):
        return ("Start with the verb: -t means look for one subject, -nt more than one." if n >= 4
                else "Start with the verb: it says what happens, and the subject has to fit it.")
    if p == "Tap the subject.":
        return "Then the subject: the word whose ending fits the verb."
    if p == "What job does the highlighted word do?":
        return ("Every other ending tells you that word's job." if f == "F6"
                else "The ending tells you the job, wherever the word sits in the sentence.")
    if p == "One, or more than one?":
        return "The ending also tells you one or more than one, and the English changes with it."
    if p == "Which is the translation?":
        return "Now put the jobs together. The wrong choices mix up one job or one number."
    if p in ("Which verb ending?", "Which ending does the verb take?"):
        return "The verb has to match its subject: one, or more than one."
    if f == "F4" or (kind == "type" and st.get("mode") == "ending"):
        return "Latin shows the job with the ending. Read the English, then give the word that job's ending."
    if f == "F7":
        return "Hear the ending on its own first, so you can catch it inside a sentence."
    if p == "What does it mean?":
        return ""
    if kind == "type":
        return "Type it yourself: this shows you can do every step without buttons."
    if f == "Q":
        return "If you can answer this, you read the endings right."
    return ""


def intro(state):
    """The "Today" screen: what this run is, and why each part is in it."""
    n, mode = state["n"], state["mode"]
    L = lesson(n) if mode != "placement" else None
    names = dict(PART_NAMES, **((L or {}).get("names") or {}))
    order, count = [], {}
    for e in state["seq"]:
        if e["p"] == "I" or e.get("k") or e.get("f"):
            continue
        if e["p"] not in count:
            order.append(e["p"])
            count[e["p"]] = 0
        count[e["p"]] += 1
    parts = [{"part": p, "name": names.get(p, ""), "why": part_why(L, p), "count": count[p]} for p in order]
    if mode == "placement":
        lead = "18 questions, about 5 minutes."
    elif mode == "again":
        lead = ("One more run at the examples and the look-alikes, then a new check. A second run is "
                "normal: it's what this is for.")
    elif mode == "check":
        lead = "Just the check."
    else:
        lead = (L or {}).get("today") or ""
    return {"title": "Placement check" if mode == "placement" else "Lesson %d: %s" % (n, L["title"]),
            "lead": lead, "parts": parts, "taps": TAPS_WHY if mode in ("full", "again") else ""}


PART_NAMES = {"A": "Words", "B1": "The job in English", "B": "New ending", "C": "Look-alikes",
              "D": "Review", "E": "Sentences", "F": "Lesson check", "P": "Placement"}


def _rng(*key):
    return random.Random(int(hashlib.sha256("|".join(map(str, key)).encode("utf-8")).hexdigest()[:8], 16))


def _entries(prefix, items, part):
    return [{"r": "%s/%d" % (prefix, i), "p": part} for i in range(len(items or []))]


def part_a(L, rnd, missed_words=()):
    n = L["n"]
    A = L.get("A") or {}
    if isinstance(A, list):
        return []
    words = list(A.get("words") or [])
    if A.get("twice"):
        words = words + words
    review = list(A.get("review") or [])
    if A.get("review_all"):
        review = [w for w in words_taught(n - 1) if w not in words]
    seq = words + review
    rnd.shuffle(seq)
    if missed_words:                                    # Lesson 12: missed words first
        seq.sort(key=lambda w: w not in missed_words)
    if A.get("review_max"):
        seq = seq[:len(words) + int(A["review_max"])]
    out = [{"r": "%d/A/w/%s" % (n, w), "p": "A"} for w in seq]
    out += _entries("%d/A/warmup" % n, A.get("warmup"), "A")
    return out


def part_b(L):
    n = L["n"]
    out = []
    if L.get("B1"):
        out += _entries("%d/B1/models" % n, L["B1"].get("models"), "B1")
        out += _entries("%d/B1/items" % n, L["B1"].get("items"), "B1")
    B = L.get("B") or {}
    out += _entries("%d/B/models" % n, B.get("models"), "B")
    out += _entries("%d/B/echo" % n, B.get("echo"), "B")
    out += _entries("%d/B/test" % n, B.get("test"), "B")
    out += _entries("%d/B/examples" % n, B.get("examples"), "B")
    return out


def part_b_examples(L):
    return _entries("%d/B/examples" % L["n"], (L.get("B") or {}).get("examples"), "B")


def part_c(L):
    return _entries("%d/C" % L["n"], L.get("C"), "C")


def review_pool(n):
    """Earlier lessons' items a Part D can draw on (Part B examples, C, E and
    the delayed tests): English items only from Lesson 0."""
    pool = []
    for m in range(0, n):
        L = lesson(m)
        for e in part_b_examples(L) + part_c(L) + (_entries("%d/E" % m, L["E"], "E") if isinstance(L.get("E"), list) else []):
            if is_item(e["r"]) and (m == 0 or not item_code(e["r"]).startswith("E")):
                pool.append(e["r"])
        if L.get("delayed") and m:
            pool.append("%d/delayed" % m)
    return pool


def part_d(L, rnd, missed=()):
    n = L["n"]
    D = L.get("D") or 0
    if D == "delayed":
        refs = ["%d/delayed" % m for m in range(1, n) if lesson(m).get("delayed")]
        return [{"r": "%d/D/%s" % (n, r), "p": "D"} for r in refs]
    k = int(D)
    if not k:
        return []
    pool = review_pool(n)
    prev_delayed = "%d/delayed" % (n - 1) if n - 1 >= 1 and lesson(n - 1).get("delayed") else None
    must = [r for r in pool if r in missed and r.split("/")[0] == str(n - 1)]
    if prev_delayed:
        must = [prev_delayed] + [r for r in must if r != prev_delayed]
    rest = [r for r in pool if r not in must]
    weighted = [r for r in rest if r in missed] + \
        sorted([r for r in rest if r not in missed], key=lambda r: (-int(r.split("/")[0]), rnd.random()))
    picks = (must + weighted)[:max(k, len(must))]
    rnd.shuffle(picks)
    return [{"r": "%d/D/%s" % (n, r), "p": "D"} for r in picks]


def part_e(L):
    n = L["n"]
    E = L.get("E")
    out = []
    if isinstance(E, dict):
        out.append({"r": "%d/E/reading" % n, "p": "E"})
        out += [{"r": "%d/E/reading/%d" % (n, i), "p": "E"} for i in range(len(E["reading"]["lines"]))]
        out += _entries("%d/E/questions" % n, E.get("questions"), "E")
    else:
        out += _entries("%d/E" % n, E, "E")
    if L.get("delayed"):
        out.append({"r": "%d/delayed" % n, "p": "E", "f": "delayed"})
    return out


def part_f(L, which):
    return _entries("%d/F/%s" % (L["n"], which), (L.get("F") or {}).get(which), "F")


def pass_mark(L):
    F = L.get("F") or {}
    return int(F.get("pass") or (len(F.get("A") or []) - 1))


def build(n, mode, check_set, student, run, missed=(), missed_words=()):
    """The screens of one run of lesson n: full, again (B examples + C + the
    check), or check (the check alone)."""
    L = lesson(n)
    rnd = _rng(student, n, run)
    if mode == "check":
        return part_f(L, check_set)
    if mode == "again":
        return part_b_examples(L) + part_c(L) + part_f(L, check_set)
    return (part_a(L, rnd, missed_words) + part_b(L) + part_c(L) + part_d(L, rnd, missed) +
            part_e(L) + part_f(L, check_set))


def build_placement():
    return [{"r": "P/%d" % i, "p": "P"} for i in range(len(load()["placement"]))]


def placement_lesson(missed_indexes):
    rule = load()["placement_rule"]
    if not missed_indexes:
        return LAST
    return min(rule[i] for i in missed_indexes)


# --------------------------------------------------------------------------
# The run: state, answers, corrections
# --------------------------------------------------------------------------

def new_state(n, mode, student, run, check_set="A", missed=(), missed_words=()):
    if mode == "placement":
        seq = [{"r": "P/intro", "p": "I"}] + build_placement()
    else:
        seq = [{"r": "%d/intro" % n, "p": "I"}] + build(n, mode, check_set, student, run, missed, missed_words)
    return {"v": 1, "n": n, "mode": mode, "set": check_set, "run": run, "seq": seq, "pos": 0,
            "step": 0, "lat": 0, "score": [], "missed": [], "t": time.time(), "done": None}


def current(state):
    """(entry, steps, step) for the screen to show, or (None, None, None)."""
    if state.get("done") or state["pos"] >= len(state["seq"]):
        return None, None, None
    e = state["seq"][state["pos"]]
    if e.get("k") == "corr":
        steps = steps_for(e["r"])
        st = dict(steps[e.get("s", 0)])
        return e, [{"kind": "correction", "step": st, "fmt": "CORR"}], 0
    steps = steps_for(e["r"])
    return e, steps, min(state["step"], len(steps) - 1)


def _is_check(e):
    return e["p"] in ("F", "P")


def _item_entries_before(seq, pos, k=2):
    out = []
    i = pos - 1
    while i >= 0 and len(out) < k:
        e = seq[i]
        if not e.get("k") and is_item(e["r"]) and not _is_check(e):
            out.append({"r": e["r"], "p": e["p"], "f": "backup"})
        i -= 1
    return list(reversed(out))


def judge(step, value):
    """right | close | wrong."""
    if step["kind"] in ("choice", "tap"):
        return "right" if str(value) in step["answer"] else "wrong"
    if step["kind"] == "type":
        if step["mode"] == "english":
            return di.check_english(value, step["latin"])
        return di.check_ending(value, step["answer"])
    return "right"


def answer(state, value, latency_ms=None):
    """Apply one answer. Returns (state, outcome) where outcome is
    {"result": right|wrong|close|next, "event": {...} or None, "finished": bool}."""
    e, steps, k = current(state)
    if e is None:
        return state, {"result": "next", "event": None, "finished": True}
    st = steps[k]
    if st["kind"] in ("model", "note", "reading", "correction", "intro"):
        state["pos"] += 1
        state["step"] = 0
        return state, _after(state, {"result": "next", "event": None})
    res = judge(st, value)
    if res == "close":
        return state, {"result": "close", "event": None, "finished": False}
    state["lat"] = state.get("lat", 0) + int(latency_ms or 0)
    if res == "right" and k + 1 < len(steps):
        state["step"] = k + 1
        return state, {"result": "right", "event": None, "finished": False}
    # the item is over: right through every step, or missed at step k
    right = res == "right"
    first = not e.get("f")
    event = {"ref": e["r"], "part": e["p"], "fmt": steps[0].get("fmt") or item_code(e["r"]),
             "right": right, "first": first, "flag": e.get("f") or "", "lat": state["lat"],
             "answer": str(value)[:120]}
    seq, pos = state["seq"], state["pos"]
    if _is_check(e):
        state["score"].append(right)
        if not right:
            state["missed"].append(pos)
    elif not right:
        # A first miss gets the whole correction: model, test, back up, delayed test.
        # A miss on a back-up or delayed item gets the model and one test; a miss on
        # a test gets the model only. That keeps a lesson from growing without end.
        flag = e.get("f")
        corr = [{"r": e["r"], "p": e["p"], "k": "corr", "s": k}]
        if flag != "test":
            corr.append({"r": e["r"], "p": e["p"], "f": "test"})
        if not flag or flag == "slow":
            back = _item_entries_before(seq, pos) + [{"r": e["r"], "p": e["p"], "f": "backup"}]
            seq[pos + 1:pos + 1] = corr + back
            later = pos + 1 + len(corr) + len(back) + 4
            seq.insert(min(later, _first_check(seq)), {"r": e["r"], "p": e["p"], "f": "delayed"})
        else:
            seq[pos + 1:pos + 1] = corr
        event["corrected"] = True
    elif (latency_ms is not None and state["lat"] > SLOW_MS and event["fmt"] in ONE_TAP
          and e.get("f") != "slow" and len(steps) == 1):
        seq.insert(min(pos + 5, _first_check(seq)), {"r": e["r"], "p": e["p"], "f": "slow"})
        event["slow"] = True
    state["pos"] = pos + 1
    state["step"] = 0
    state["lat"] = 0
    return state, _after(state, {"result": "right" if right else "wrong", "event": event})


def _first_check(seq):
    return next((i for i, e in enumerate(seq) if _is_check(e)), len(seq))


def _after(state, outcome):
    finished = state["pos"] >= len(state["seq"])
    outcome["finished"] = finished
    if finished and not state.get("done"):
        if state["mode"] == "placement":
            missed = [int(state["seq"][i]["r"].split("/")[1]) for i in state["missed"]]
            state["done"] = {"kind": "placement", "lesson": placement_lesson(missed)}
        else:
            L = lesson(state["n"])
            right = sum(1 for x in state["score"] if x)
            ready = right >= pass_mark(L)
            state["done"] = {"kind": "check", "ready": ready, "score": right, "of": len(state["score"]),
                             "set": state["set"]}
    return outcome


# --------------------------------------------------------------------------
# Progress, from the event log
# --------------------------------------------------------------------------

def di_events(events):
    return [e for e in events if e.get("context") == CONTEXT]


def response(e):
    try:
        return json.loads(e.get("response") or "{}")
    except (ValueError, TypeError):
        return {}


def progress(events):
    """{"placed": lesson or None, "ready": {n, ...}, "unlocked": n, "again_streak": {n: k},
    "lessons": [{"n", "state"}]} -- state: ready | current | open | locked."""
    ev = di_events(events)
    placed = None
    ready = set()
    streak = {}
    for e in ev:
        if e["item_id"] == "di:placement":
            try:
                placed = int(str(e["result"]).lstrip("L"))
            except ValueError:
                pass
        elif e["item_id"].startswith("di:check:"):
            n = int(e["item_id"].split(":")[2])
            if e["result"] == "ready":
                ready.add(n)
                streak[n] = 0
            else:
                streak[n] = streak.get(n, 0) + 1
    top = max(ready) + 1 if ready else 0
    unlocked = min(LAST, max(placed or 0, top))
    lessons = []
    for L in load()["lessons"]:
        n = L["n"]
        if n in ready:
            state = "ready"
        elif n == unlocked:
            state = "current"
        elif n < unlocked:
            state = "open"
        else:
            state = "locked"
        lessons.append({"n": n, "title": L["title"], "subtitle": L.get("subtitle", ""), "state": state,
                        "agains": streak.get(n, 0)})
    return {"placed": placed, "ready": ready, "unlocked": unlocked, "streak": streak,
            "lessons": lessons, "finished": LAST in ready}


def missed_refs(events):
    """Items this student has missed (any try), as plain refs."""
    out = set()
    for e in di_events(events):
        if e["result"] == "wrong" and not e["item_id"].startswith(("di:check", "di:placement")):
            ref = e["item_id"][3:]
            bits = ref.split("/")
            if len(bits) > 2 and bits[1] == "D":
                ref = "/".join(bits[2:])
            out.add(ref)
    return out


def missed_words(events):
    return {r.split("/")[3] for r in missed_refs(events) if "/A/w/" in r}


# --------------------------------------------------------------------------
# Checking the content against the writing rules
# --------------------------------------------------------------------------

def all_refs():
    refs = [e["r"] for e in build_placement()]
    for L in load()["lessons"]:
        n = L["n"]
        for e in (part_a(L, random.Random(0)) + part_b(L) + part_c(L) + part_e(L) +
                  part_f(L, "A") + part_f(L, "B")):
            refs.append(e["r"])
    return refs


def problems():
    """What is wrong with the content, in plain words. Empty is fine."""
    out = []
    for ref in all_refs():
        try:
            steps = steps_for(ref)
        except Exception as exc:                      # noqa: BLE001
            out.append("%s: %s" % (ref, exc))
            continue
        raw, n = resolve(ref)
        for st in steps:
            if st["kind"] == "choice":
                vals = [o["v"] for o in st["options"]]
                if not set(st["answer"]) & set(vals):
                    out.append("%s: the answer isn't among the buttons" % ref)
                labels = [o["label"] for o in st["options"]]
                if len(set(labels)) != len(labels):
                    out.append("%s: two buttons say the same thing" % ref)
                if st["prompt"] in ("Which is the translation?", "What does it mean?") and len(labels) != 3:
                    out.append("%s: a translation or meaning needs exactly three choices" % ref)
        # every word in an item taught by its lesson (the placement covers all)
        if isinstance(raw, str) and ref[0] != "P" and raw.split(" ", 1)[0][0] == "F":
            code, body, more, opts = _fields(raw)
            if code in ("F4", "F8E"):
                en, latin, ending = _context(body, more)
                if "**" not in en or latin.count("___") != 1:
                    out.append("%s: needs an English sentence with the target in **bold** and a Latin one with ___" % ref)
                    continue
                said = di.translate(latin.replace("___", ending))
                if said != en.replace("**", ""):
                    out.append("%s: the Latin says “%s”, not “%s”" % (ref, said, en.replace("**", "")))
                body = latin.replace("___", ending)
            known = stems_taught(n)
            glossed = {w.strip().split("=")[0].strip() for w in (opts.get("gloss") or "").split(",") if w}
            for t in di.tokens(_plain(body.replace("__", "at"))):
                if t["kind"] in ("noun", "verb", "prep"):
                    if (t["kind"], t["stem"]) not in known and t["w"] not in glossed:
                        # the verb in -nt and -t are taught as a pair from Lesson 4
                        if t["kind"] == "verb" and ("verb", t["stem"]) in known:
                            continue
                        out.append("%s: %s isn't taught by Lesson %d" % (ref, t["w"], n))
                elif t["kind"] in ("et", "non") and (t["kind"], t["kind"]) not in known:
                    out.append("%s: %s isn't taught by Lesson %d" % (ref, t["w"], n))
    return out


# --------------------------------------------------------------------------
# The teacher's view (plan, section 12)
# --------------------------------------------------------------------------

def _median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


def lesson_of_ref(ref):
    bits = ref.split("/")
    return None if bits[0] == "P" else int(bits[0])


def report(all_events, students, week_start=None):
    """{"students": [...], "lessons": [...], "items": [...]} from every
    student's DI events. Item rates count first tries only (an item's first
    appearance in a run, not its test, back-up or delayed rerun)."""
    by_student = {}
    for e in di_events(all_events):
        by_student.setdefault(e["student_id"], []).append(e)
    rows = []
    for sid in sorted(set(students) | set(by_student)):
        ev = by_student.get(sid, [])
        pr = progress(ev)
        checks = [e for e in ev if e["item_id"].startswith("di:check:")]
        week = [e for e in ev if week_start is None or e["timestamp"] >= week_start]
        secs = sum(min(int(e.get("latency_ms") or 0), 60000) for e in week) / 1000.0
        rows.append({"student_id": sid, "started": bool(ev), "current": pr["unlocked"],
                     "passed": len(pr["ready"]), "agains": sum(1 for e in checks if e["result"] == "again"),
                     "flag": [n for n, k in pr["streak"].items() if k >= 2 and n not in pr["ready"]],
                     "placed": pr["placed"], "minutes": int(round(secs / 60.0)), "finished": pr["finished"]})
    # items: first-try correct rate
    items = {}
    for e in di_events(all_events):
        if e["item_id"].startswith(("di:check:", "di:placement")):
            continue
        r = response(e)
        if not r.get("first", True):
            continue
        ref = e["item_id"][3:]
        bits = ref.split("/")
        if len(bits) > 2 and bits[1] == "D":
            ref = "/".join(bits[2:])
        it = items.setdefault(ref, {"ref": ref, "n": 0, "right": 0})
        it["n"] += 1
        it["right"] += 1 if e["result"] == "right" else 0
    item_rows = []
    for ref, it in items.items():
        rate = it["right"] / float(it["n"])
        part = ref.split("/")[1] if ref[0] != "P" else "P"
        try:
            raw, _ = resolve(ref)
        except (KeyError, IndexError, ValueError):
            continue
        advice = ""
        if it["n"] >= 3 and rate < 0.5:
            advice = "Below 50%: rewrite it, or add steps before it in the example sequence."
        elif it["n"] >= 3 and rate > 0.95 and part in ("B", "C"):
            advice = "Above 95% in Part %s: it teaches nothing new; try a harder minimal pair." % part
        item_rows.append(dict(it, rate=rate, part=part, line=raw if isinstance(raw, str) else "(model)",
                              lesson=lesson_of_ref(ref), advice=advice))
    item_rows.sort(key=lambda r: (r["lesson"] if r["lesson"] is not None else -1, r["rate"]))
    # lessons
    lesson_rows = []
    for L in load()["lessons"]:
        n = L["n"]
        times, first_checks = [], []
        for sid, ev in by_student.items():
            mine = [e for e in ev if e["item_id"].startswith("di:%d/" % n)]
            if mine:
                times.append(sum(min(int(e.get("latency_ms") or 0), 60000) for e in mine) / 60000.0)
            chk = [e for e in ev if e["item_id"] == "di:check:%d" % n]
            if chk:
                first_checks.append(chk[0]["result"] == "ready")
        its = [r for r in item_rows if r["lesson"] == n and r["n"]]
        worst = min(its, key=lambda r: r["rate"]) if its else None
        ex = [r for r in its if r["part"] == "B" and "/examples/" in r["ref"]]
        ex_rate = (sum(r["right"] for r in ex) / float(sum(r["n"] for r in ex))) if ex else None
        lesson_rows.append({"n": n, "title": L["title"], "median_min": _median(times),
                            "ready_first": (sum(first_checks) / float(len(first_checks))) if first_checks else None,
                            "n_checked": len(first_checks), "worst": worst, "examples_rate": ex_rate,
                            "slow_sequence": ex_rate is not None and ex_rate < 0.7 and sum(r["n"] for r in ex) >= 10})
    return {"students": rows, "lessons": lesson_rows, "items": item_rows}
