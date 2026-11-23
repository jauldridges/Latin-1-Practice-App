"""
DI mode: the first-declension strand's grammar engine.

DI mode (direct instruction) teaches the first declension a lesson at a time
(di_run.py runs the lessons; di/first-declension.yaml holds them). Every
sentence in the strand is built from a closed set of words and follows the
strand's writing rules (the teacher's DI plan, section 7), so the jobs in it
can be read off mechanically. This module does that reading, once, for
everything a lesson screen needs:

  parse(latin)      each word's job: verb, subject, direct object,
                    possession, to/for, object of the preposition
  english(parse)    the translation, in the plan's own wording
  choices(...)      the three translations: the right one, the one that
                    swaps subject and object, and one that changes one
                    thing only (the number, or the job of one word)
  rule_line(...)    the one line a correction shows
  check_english / check_ending   typed answers (macrons never required)

Deriving rather than hand-writing every answer keeps the three translations
in one voice (a distractor written in a different style is a giveaway) and
keeps the rules in one place. The tests hold the English to the plan's own
translations wherever the plan gives one.

The -ae and -īs look-alikes are settled by the plan's writing rules:
  * -ae: the subject when the verb ends in -nt and no other word is the
    subject; otherwise possession with spectat, laudat, amat, vocat, and to/for
    with nārrat, parat, portat, servat. (Rule 2: a genitive -ae sits right
    after its noun in sentences with the first group; a dative -ae comes
    before the object with the second.)
  * -īs: object of the preposition after in, cum, ē/ex, ā/ab; otherwise
    to/for.
  * -ā (long, in print) after a preposition; -a (short) is the subject.
"""

import hashlib
import re
import unicodedata

# --------------------------------------------------------------------------
# The strand's words
# --------------------------------------------------------------------------

# stem: (singular, plural, gloss for a Part A meaning item)
NOUNS = {
    "aqu": ("water", "waters", "water"),
    "terr": ("land", "lands", "land"),
    "vi": ("road", "roads", "road, street"),
    "port": ("gate", "gates", "gate"),
    "īnsul": ("island", "islands", "island"),
    "silv": ("forest", "forests", "forest"),
    "puell": ("girl", "girls", "girl"),
    "fēmin": ("woman", "women", "woman"),
    "naut": ("sailor", "sailors", "sailor"),
    "agricol": ("farmer", "farmers", "farmer"),
    "patri": ("homeland", "homelands", "homeland"),
    "fām": ("fame", "fames", "fame, reputation"),
    "vīt": ("life", "lives", "life"),
    "lūn": ("moon", "moons", "moon"),
    "stēll": ("star", "stars", "star"),
    "fābul": ("story", "stories", "story"),
}
# Nouns whose number isn't flipped to make a distractor ("the fames").
MASS = {"aqu", "fām", "vīt", "patri"}

# stem: (3rd singular, plural / base form)
VERBS = {
    "am": ("loves", "love"), "laud": ("praises", "praise"), "port": ("carries", "carry"),
    "voc": ("calls", "call"), "spect": ("watches", "watch"), "nārr": ("tells", "tell"),
    "par": ("prepares", "prepare"), "serv": ("saves", "save"), "pugn": ("fights", "fight"),
}
# Rule 2: which verbs a non-subject -ae goes with.
GENITIVE_VERBS = {"spect", "laud", "am", "voc"}
DATIVE_VERBS = {"nārr", "par", "port", "serv"}
# How a to/for word reads with each verb ("tells a story to", "carries water for").
DATIVE_WORD = {"nārr": "to"}

PREPS = {"in": "in", "cum": "with", "ē": "out of", "ex": "out of", "ā": "away from",
         "ab": "away from"}
PREP_GLOSS = {"in": "in, on", "cum": "with", "ē": "out of", "ex": "out of",
              "ā": "away from", "ab": "away from"}
PARTICLES = {"et": "and", "nōn": "not"}

# ending: number (the case comes from the job)
ENDINGS = ["ārum", "ās", "am", "ae", "īs", "ā", "a"]
PLURAL_ENDINGS = {"ārum", "ās", "īs"}

# --------------------------------------------------------------------------
# Jobs, and when each one's button appears
# --------------------------------------------------------------------------

JOBS = ["verb", "subject", "dobj", "poss", "tofor", "objprep", "nodobj"]
JOB_LABEL = {"verb": "Verb", "subject": "Subject", "dobj": "Direct object",
             "poss": "Possession", "tofor": "To / for", "objprep": "Object of the preposition",
             "nodobj": "No direct object"}
CASE_NAME = {"subject": "nominative", "dobj": "accusative", "poss": "genitive",
             "tofor": "dative", "objprep": "ablative"}
# The lesson a job's button first appears, and the lesson its case name does
# (when its Latin ending is taught).
JOB_FROM = {"verb": 0, "subject": 0, "dobj": 0, "poss": 6, "tofor": 8, "objprep": 10}
CASE_FROM = {"subject": 1, "dobj": 2, "poss": 6, "tofor": 8, "objprep": 10}
# The lesson each ending button appears.
ENDING_FROM = {"a": 1, "am": 2, "ās": 3, "ae": 4, "ārum": 6, "īs": 8, "ā": 10}


def job_buttons(lesson, jobs=None):
    """[(job, label, case name or "")] for a job question in this lesson."""
    out = []
    for j in jobs or ["verb", "subject", "dobj", "poss", "tofor", "objprep"]:
        if JOB_FROM.get(j, 99) <= lesson:
            case = CASE_NAME.get(j, "") if CASE_FROM.get(j, 99) <= lesson else ""
            out.append((j, JOB_LABEL[j], case))
    return out


def ending_buttons(lesson):
    return [e for e in ["a", "am", "ās", "ae", "ārum", "īs", "ā"] if ENDING_FROM[e] <= lesson]


# --------------------------------------------------------------------------
# Reading a word
# --------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-zĀāĒēĪīŌōŪū_]+")


def nfc(s):
    return unicodedata.normalize("NFC", str(s or ""))


def strip_macrons(s):
    return "".join(c for c in unicodedata.normalize("NFD", nfc(s)) if unicodedata.category(c) != "Mn")


def word(form):
    """One word: {"w", "kind", "stem", "ending", "num"}. kind is noun, verb,
    prep, et, non, or "?" for a word outside the strand."""
    w = nfc(form)
    low = w.lower()
    if low in PREPS:
        return {"w": w, "kind": "prep", "stem": low}
    if low == "et":
        return {"w": w, "kind": "et"}
    if low == "nōn":
        return {"w": w, "kind": "non"}
    for stem in VERBS:
        for end, num in (("ant", "pl"), ("at", "sg"), ("__", "?")):
            if low == stem + end:
                return {"w": w, "kind": "verb", "stem": stem, "num": num,
                        "ending": "nt" if num == "pl" else "t" if num == "sg" else ""}
    for stem in sorted(NOUNS, key=len, reverse=True):
        if low.startswith(stem):
            end = low[len(stem):]
            if end in ENDINGS:
                return {"w": w, "kind": "noun", "stem": stem, "ending": end,
                        "num": "pl" if end in PLURAL_ENDINGS else "sg"}
    return {"w": w, "kind": "?"}


def ending_of(form):
    """The first-declension ending of a noun form ("puellās" -> "ās")."""
    t = word(form)
    return t.get("ending") if t["kind"] == "noun" else None


# --------------------------------------------------------------------------
# Reading a sentence
# --------------------------------------------------------------------------

def tokens(latin):
    """The words of a sentence (punctuation dropped), each read by word(), with
    `bold` set on a word written **like this**."""
    out = []
    for m in re.finditer(r"\*\*([^*]+)\*\*|" + _WORD.pattern, nfc(latin)):
        if m.group(1):
            for w in _WORD.findall(m.group(1)):
                out.append(dict(word(w), bold=True))
        else:
            out.append(dict(word(m.group(0)), bold=False))
    for i, t in enumerate(out):
        t["i"] = i
    return out


def _clauses(toks):
    """Split at an et that joins two verbs: [[token, ...], ...]."""
    verbs = [t["i"] for t in toks if t["kind"] == "verb"]
    if len(verbs) < 2:
        return [toks]
    cut = next(t["i"] for t in toks if t["kind"] == "et" and verbs[0] < t["i"] < verbs[1])
    return [toks[:cut], toks[cut + 1:]]


def parse(latin):
    """{"tokens": [...], "clauses": [{"verb", "subject", "neg", "nouns"}]}.

    Every noun token gets a `job` (subject, dobj, poss, tofor, objprep) and
    poss tokens a `head` (the index of the noun they belong to). Verbs get
    job "verb". Raises ValueError on a sentence the strand's rules can't read.
    """
    toks = tokens(latin)
    if any(t["kind"] == "?" for t in toks):
        raise ValueError("not a strand word: %s" % [t["w"] for t in toks if t["kind"] == "?"])
    clauses = []
    shared_subject = None
    for ct in _clauses(toks):
        verb = next((t for t in ct if t["kind"] == "verb"), None)
        if verb is not None:
            verb["job"] = "verb"
        nouns = [t for t in ct if t["kind"] == "noun"]
        # objects of a preposition
        for a, b in zip(ct, ct[1:]):
            if a["kind"] == "prep" and b["kind"] == "noun":
                b["job"] = "objprep"
                b["prep"] = a["stem"]
        for t in nouns:
            if t.get("job"):
                continue
            e = t["ending"]
            if e in ("am", "ās"):
                t["job"] = "dobj"
            elif e == "ārum":
                t["job"] = "poss"
            elif e == "a":
                t["job"] = "subject"
            elif e == "īs":
                t["job"] = "tofor"
            elif e == "ā":
                raise ValueError("-ā without a preposition: %s" % t["w"])
        # -ae: the subject first (a verb in -nt and no other subject: the
        # first -ae not sitting right after a noun, else the only one), then
        # rule 2 for the rest
        ae = [t for t in nouns if t["ending"] == "ae" and not t.get("job")]
        has_subject = any(t.get("job") == "subject" for t in nouns)
        plural_verb = verb is not None and verb["num"] == "pl"

        def after_noun_(t):
            prev = toks[t["i"] - 1] if t["i"] > 0 else None
            return prev is not None and prev["kind"] == "noun"
        if plural_verb and not has_subject and ae:
            pick = next((t for t in ae if not after_noun_(t)), ae[0])
            pick["job"] = "subject"
            has_subject = True
        for t in ae:
            if t.get("job"):
                continue
            after_noun = after_noun_(t)
            if verb is None:                        # a phrase: the head noun
                t["job"] = "poss" if after_noun else "subject"
            elif verb["stem"] in GENITIVE_VERBS:
                t["job"] = "poss"
            elif verb["stem"] in DATIVE_VERBS:
                t["job"] = "tofor"
            else:
                t["job"] = "poss" if after_noun else "tofor"
        for t in nouns:                              # -ae: one or more by its job
            if t["ending"] == "ae":
                t["num"] = "pl" if t["job"] == "subject" else "sg"
        for t in nouns:                              # what each possession belongs to
            if t["job"] == "poss":
                prev = toks[t["i"] - 1] if t["i"] > 0 else None
                t["head"] = prev["i"] if prev is not None and prev["kind"] == "noun" else None
        subject = [t for t in nouns if t["job"] == "subject"]
        if not subject and shared_subject is not None and verb is not None:
            subject = shared_subject
        if subject:
            shared_subject = subject
        clauses.append({"verb": verb, "subject": subject, "neg": any(t["kind"] == "non" for t in ct),
                        "nouns": nouns, "tokens": ct})
    return {"tokens": toks, "clauses": clauses, "latin": nfc(latin)}


def job_of(latin, index=None):
    """The job of the **bold** word (or of token `index`)."""
    p = parse(latin)
    for t in p["tokens"]:
        if (index is None and t.get("bold")) or t["i"] == index:
            return t.get("job")
    return None


# --------------------------------------------------------------------------
# English
# --------------------------------------------------------------------------

def _num(t, flips):
    n = t["num"]
    if t["i"] in flips:
        n = "pl" if n == "sg" else "sg"
    return n


def _noun_en(t, flips):
    sg, pl, _ = NOUNS[t["stem"]]
    return pl if _num(t, flips) == "pl" else sg


def _np(t, p, jobs, flips, ctx):
    """A noun phrase in English, with its possession attached."""
    stem = t["stem"]
    n = _num(t, flips)
    noun = _noun_en(t, flips)
    if stem == "vi" and jobs[t["i"]] == "objprep":
        noun = "street" if n == "sg" else "streets"
    owners = [o for o in p["tokens"] if jobs.get(o["i"]) == "poss" and o.get("head") == t["i"]]
    job = jobs[t["i"]]
    if owners:
        of = " and ".join(_np(o, p, jobs, flips, ctx) for o in owners)
        return "the %s of %s" % (noun, of)
    if job in ("dobj",):
        if stem in ("fām", "vīt"):
            return noun
        if stem == "aqu" and ctx.get("adjunct"):
            return noun
        if stem == "fābul":
            return "a story" if n == "sg" else "stories"
        if stem == "vi" and ctx.get("verb") == "par":
            return "a road" if n == "sg" else "roads"
    return "the " + noun


def _prep_phrase(t, p, jobs, flips, phrase=False):
    prep = t["prep"]
    word_ = PREPS[prep]
    if prep == "in" and t["stem"] == "īnsul":
        word_ = "on"
    if prep in ("ā", "ab") and not phrase:
        word_ = "from"
    return "%s %s" % (word_, _np(t, p, jobs, flips, {}))


def _join(xs):
    return " and ".join(xs)


def english(p, jobs=None, flips=(), negate=False, someone=False):
    """The translation of a parsed sentence or phrase.

    `jobs` overrides token jobs ({index: job}), `flips` flips the number of
    tokens, `negate` toggles nōn, `someone` turns a lone subject into the
    object of "Someone": the variations distractors are made of.
    """
    base = {t["i"]: t.get("job") for t in p["tokens"]}
    base.update(jobs or {})
    jobs = base
    flips = set(flips)
    if not any(c["verb"] for c in p["clauses"]):
        return _phrase(p, jobs, flips)
    out = []
    first_plural = False
    for ci, c in enumerate(p["clauses"]):
        nouns = c["nouns"]
        subj = [t for t in nouns if jobs[t["i"]] == "subject"] or (c["subject"] if ci else [])
        objs = [t for t in nouns if jobs[t["i"]] == "dobj"]
        dats = [t for t in nouns if jobs[t["i"]] == "tofor"]
        preps = [t for t in nouns if jobs[t["i"]] == "objprep"]
        verb = c["verb"]
        ctx = {"adjunct": bool(dats or preps), "verb": verb["stem"]}
        neg = c["neg"] != negate
        if someone and subj and not objs:
            objs, subj = subj, []
        if ci and not [t for t in nouns if jobs[t["i"]] == "subject"]:
            plural, s = first_plural, ""            # the first clause's subject, shared
        elif subj:
            plural = len(subj) > 1 or _num(subj[0], flips) == "pl"
            s = _join(_np(t, p, jobs, flips, ctx) for t in subj)
        else:
            plural, s = False, "someone"
        if not ci:
            first_plural = plural
        v3, vbase = VERBS[verb["stem"]]
        if neg:
            vp = ("do not " if plural else "does not ") + vbase
        else:
            vp = vbase if plural else v3
        parts = [] if ci else [s]
        parts.append(vp)
        if objs:
            parts.append(_join(_np(t, p, jobs, flips, ctx) for t in objs))
        for t in dats:
            parts.append("%s %s" % (DATIVE_WORD.get(verb["stem"], "for"), _np(t, p, jobs, flips, ctx)))
        for t in preps:
            parts.append(_prep_phrase(t, p, jobs, flips))
        out.append(" ".join(parts))
    text = " and ".join(out) + "."
    return text[0].upper() + text[1:]


def _phrase(p, jobs, flips):
    toks = p["tokens"]
    nouns = [t for t in toks if t["kind"] == "noun"]
    if toks and toks[0]["kind"] == "prep":
        return _prep_phrase(dict(nouns[0], prep=toks[0]["stem"]), p, jobs, flips, phrase=True)
    head = next(t for t in nouns if jobs[t["i"]] != "poss")
    jobs = dict(jobs)
    jobs[head["i"]] = "subject"
    return _np(head, p, jobs, flips, {})


def translate(latin):
    return english(parse(latin))


# --------------------------------------------------------------------------
# Three translation choices
# --------------------------------------------------------------------------

def _seeded(key):
    return int(hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:8], 16)


def choices(latin, focus=None, key=None):
    """[(text, right)] -- three translations in a fixed shuffled order: the
    right one; one that swaps subject and object; one that changes one thing
    only (the number, or the job of one word). `focus` is the lesson's new
    ending: the changed word is one carrying it when there is one."""
    p = parse(latin)
    right = english(p)
    seen = {right}
    out = [(right, True)]
    toks = p["tokens"]
    nouns = [t for t in toks if t["kind"] == "noun"]
    c = p["clauses"][0]

    # 1. swap subject and direct object (or the subject and another noun)
    swap = None
    subj = [t for t in c["nouns"] if t.get("job") == "subject"]
    obj = [t for t in c["nouns"] if t.get("job") == "dobj"]
    if subj and obj:
        swap = english(p, jobs={subj[0]["i"]: "dobj", obj[0]["i"]: "subject"})
    elif subj:
        # Swapping only makes sense with a partner (cum): "the girls fight
        # with the sailor". Otherwise the subject's number changes instead.
        other = next((t for t in c["nouns"] if t.get("job") == "objprep" and t.get("prep") == "cum"), None)
        has_other = any(t.get("job") in ("tofor", "objprep") for t in c["nouns"])
        if has_other and other is None and subj[0]["stem"] not in MASS:
            swap = english(p, flips=[subj[0]["i"]])
        elif other is not None:
            jobs = {subj[0]["i"]: other["job"], other["i"]: "subject"}
            pp = parse(latin)
            if other["job"] == "objprep":
                pp["tokens"][subj[0]["i"]]["prep"] = other["prep"]
            swap = english(pp, jobs=jobs)
        else:
            swap = english(p, someone=True)
    if swap and swap not in seen:
        out.append((swap, False))
        seen.add(swap)

    # 2. change one thing: the job of a dative -ae, else the number of one word
    one = None
    focused = [t for t in nouns if focus and t["ending"] == focus]
    for t in focused:
        if t.get("job") == "tofor" and t["ending"] == "ae" and obj:
            pp = parse(latin)
            pp["tokens"][t["i"]]["head"] = obj[0]["i"]
            cand = english(pp, jobs={t["i"]: "poss"})
            if cand not in seen:
                one = cand
                break
    order = focused + obj + subj + [t for t in nouns if t not in focused + obj + subj]
    for t in order:
        if one:
            break
        if t["stem"] in MASS:
            continue
        cand = english(p, flips=[t["i"]])
        if cand not in seen:
            one = cand
    if not one:
        one = english(p, negate=True)
    out.append((one, False))
    seen.add(one)
    while len(out) < 3:                      # a last resort: never fewer than three
        out.append((english(p, negate=True) if len(out) == 1 else english(p, someone=True), False))
    k = _seeded(key or latin)
    order = [(0, 1, 2), (1, 0, 2), (2, 0, 1), (0, 2, 1), (1, 2, 0), (2, 1, 0)][k % 6]
    return [out[i] for i in order]


# --------------------------------------------------------------------------
# Meanings (F1)
# --------------------------------------------------------------------------

def gloss(form):
    """The meaning of one strand word, as a Part A item shows it."""
    t = word(form)
    if t["kind"] == "noun":
        return NOUNS[t["stem"]][2]
    if t["kind"] == "verb":
        return VERBS[t["stem"]][0] if t["num"] == "sg" else "%s (more than one)" % VERBS[t["stem"]][1]
    if t["kind"] == "prep":
        return PREP_GLOSS[t["stem"]]
    return PARTICLES.get(t["kind"] if t["kind"] != "non" else "nōn", "")


def kind_of(form):
    t = word(form)
    return "noun" if t["kind"] == "noun" else "verb" if t["kind"] == "verb" else "word"


def meaning_choices(latin, pool, key=None):
    """[(text, right)] for an F1 item. A word: its meaning and two other words'
    of the same kind from `pool` (the words the student knows). A phrase:
    its translation, the number changed, and either the owner and owned
    swapped or another preposition."""
    if len(_WORD.findall(latin)) == 1 or latin.strip().lower() in ("ē, ex", "ā, ab"):
        right = gloss(latin.split(",")[0])
        kind = kind_of(latin.split(",")[0])
        others = sorted({gloss(w) for w in pool if kind_of(w) == kind and gloss(w) != right})
        if len(others) < 2:
            others = sorted({gloss(w) for w in pool if gloss(w) != right} |
                            {"house", "river", "king"} - {right})
        k = _seeded(key or latin)
        picks = [others[k % len(others)], others[(k // 7 + 1) % len(others)]]
        if picks[0] == picks[1]:
            picks[1] = others[(k + 1) % len(others)]
        opts = [(right, True), (picks[0], False), (picks[1], False)]
    else:
        p = parse(latin)
        right = english(p)
        nouns = [t for t in p["tokens"] if t["kind"] == "noun"]
        opts = [(right, True)]
        if p["tokens"][0]["kind"] == "prep":
            t = nouns[0]
            opts.append((english(p, flips=[t["i"]]), False))
            other = {"in": "cum", "cum": "in", "ē": "ā", "ex": "ab", "ā": "ē", "ab": "ex"}[p["tokens"][0]["stem"]]
            q = parse(other + " " + t["w"])
            opts.append((english(q), False))
        else:
            head, owner = nouns[0], nouns[-1]
            flip = owner if owner["stem"] not in MASS else head
            opts.append((english(p, flips=[flip["i"]]), False))
            # the owner and the owned the other way round
            swapped = "the %s of the %s" % (_noun_en(owner, set()), _noun_en(head, set()))
            opts.append((swapped, False))
    k = _seeded(key or latin)
    order = [(0, 1, 2), (1, 0, 2), (2, 0, 1), (0, 2, 1), (1, 2, 0), (2, 1, 0)][k % 6]
    return [opts[i] for i in order]


# --------------------------------------------------------------------------
# Corrections
# --------------------------------------------------------------------------

RULES = {
    ("a", "subject"): "-a marks the subject.",
    ("am", "dobj"): "-am marks the direct object.",
    ("ās", "dobj"): "-ās marks a plural direct object.",
    ("ae", "subject"): "-ae with a verb in -nt marks a plural subject.",
    ("ārum", "poss"): "-ārum shows possession: “of the ___s.”",
    ("ae", "poss"): "Here -ae shows possession: “of the ___.”",
    ("īs", "tofor"): "-īs means “to the ___s” or “for the ___s.”",
    ("ae", "tofor"): "Here -ae means “to the ___” or “for the ___.”",
    ("ā", "objprep"): "After a preposition, -ā marks the object of the preposition.",
    ("īs", "objprep"): "After a preposition, -īs marks a plural object of the preposition.",
}


def rule_line(form, job):
    """“*Puellam* ends in **-am**. -am marks the direct object.”"""
    if job == "verb":
        return "*%s* is the verb: the action." % form
    e = ending_of(form)
    if e and (e, job) in RULES:
        return "*%s* ends in **-%s**. %s" % (form, e, RULES[(e, job)])
    return "*%s*: %s." % (form, JOB_LABEL.get(job, job).lower())


def number_rule(form):
    e = ending_of(form)
    if e in PLURAL_ENDINGS or (e == "ae" and False):
        return "*%s* ends in **-%s**: more than one." % (form, e)
    return "*%s* ends in **-%s**: one." % (form, e)


def verb_rule(subject_num):
    return ("A plural subject takes a verb in **-nt**." if subject_num == "pl"
            else "A subject that is one takes a verb in **-t**.")


# --------------------------------------------------------------------------
# Typed answers (F8)
# --------------------------------------------------------------------------

_ARTICLES = {"the", "a", "an"}


def _norm_en(s):
    s = strip_macrons(s).lower().replace("’", "'")
    s = re.sub(r"'s\b|s'(?=\s|$)", lambda m: "s", s)        # girl's -> girls, girls' -> girls
    s = re.sub(r"[^a-z ]+", " ", s)
    return " ".join(w for w in s.split() if w not in _ARTICLES)


def english_variants(latin):
    """Every wording of the translation a typed answer may match: articles
    never matter; to/for either way; the to/for word before the object ("tells
    the girls a story"); "from" or "away from"; island "in" or "on"; road or
    street; possession with 's."""
    p = parse(latin)
    base = english(p)
    out = {base}
    swaps = [(" to ", " for "), (" for ", " to "), (" from ", " away from "), (" away from ", " from "),
             (" on the island", " in the island"), (" street", " road"), (" road", " street"),
             ("water", "the water"), (" a story", " the story")]
    for a, b in swaps:
        for s in list(out):
            if a in s:
                out.add(s.replace(a, b))
    # "tells the girls a story": the to/for word straight after the verb
    c = p["clauses"][0]
    dats = [t for t in c["nouns"] if t.get("job") == "tofor"]
    objs = [t for t in c["nouns"] if t.get("job") == "dobj"]
    if dats and objs and len(p["clauses"]) == 1:
        jobs = {t["i"]: t.get("job") for t in p["tokens"]}
        flips = set()
        ctx = {"adjunct": True}
        obj_np = " and ".join(_np(t, p, jobs, flips, ctx) for t in objs)
        dat_np = " and ".join(_np(t, p, jobs, flips, ctx) for t in dats)
        word_ = DATIVE_WORD.get(c["verb"]["stem"], "for")
        for s in list(out):
            frag = "%s %s %s" % (obj_np, word_, dat_np)
            if frag in s:
                out.add(s.replace(frag, "%s %s" % (dat_np, obj_np)))
    # possession with 's
    for t in p["tokens"]:
        if t.get("job") == "poss" and t.get("head") is not None:
            head = p["tokens"][t["head"]]
            jobs = {x["i"]: x.get("job") for x in p["tokens"]}
            long_ = "%s of the %s" % (_noun_en(head, set()), _noun_en(t, set()))
            owner = _noun_en(t, set())
            short = "%s%s %s" % (owner, "'" if owner.endswith("s") else "'s", _noun_en(head, set()))
            for s in list(out):
                if long_ in s:
                    out.add(s.replace(long_, short))
    return {_norm_en(s) for s in out}


def _distance(a, b, cap=4):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def check_english(typed, latin):
    """right | close | wrong for a typed translation. Close (a slip of a few
    letters) is handed back to retype, as everywhere else in the app."""
    t = _norm_en(typed)
    if not t:
        return "wrong"
    variants = english_variants(latin)
    if t in variants:
        return "right"
    if min(_distance(t, v) for v in variants) <= 2:
        return "close"
    return "wrong"


def check_ending(typed, answer):
    t = strip_macrons(typed).lower().strip().lstrip("-").strip()
    return "right" if t and t == strip_macrons(answer).lower().lstrip("-") else "wrong"
