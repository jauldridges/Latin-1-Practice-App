"""
The eight mechanical checks. Run on import, before any human sees a question.
Anything caught is attached to the question as a flag reason and routed to the
flagged queue.

Each check returns zero or more Flag(check, level, detail) for one item, except
the cross-item checks (duplicate question) which look at the whole set.

Two of the checks are approximate and are labelled level "heuristic" rather than
"error". They are documented in the module docstring of each and in the project
README:

  Check 2 (vocabulary) can only reliably tell that a token is Latin when it
  carries a macron or is a Latin form it can generate; a macron-free,
  out-of-list Latin word buried in an English stem will slip past. It examines
  macron-bearing tokens and the Latin answer forms it can see, against the core
  list + generated inflected forms + content vocabulary.

  Check 4 (explain options are reasons) uses the presence of a causal word
  (because / since / so / as) as a proxy for "this option is a reason". Good
  reason-options are often phrased without one ("From the genitive...", "It
  shows the stem..."), so the literal rule is noisy. We report the literal count
  but only FLAG the stronger signal: an explain item where NO option contains a
  causal word.

  Check 6a as written ("macron_matters true but answers contain no macrons")
  fires on legitimate items whose macron lives in the stem's minimal pair rather
  than in the answer (e.g. a long-vowel recognition item). We flag only when
  neither the answers NOR the stem contain a macron, and report the literal
  count separately.
"""

import re
from collections import defaultdict, namedtuple

from answercheck import clean, strip_macrons

Flag = namedtuple("Flag", ["check", "level", "detail"])

_MACRON_CHARS = set("āēīōūȳĀĒĪŌŪȲ")
_CAUSAL = ("because", "since", " so ", " as ", "so that")
_WORD_RE = re.compile(r"[A-Za-zāēīōūȳĀĒĪŌŪȲ]+", re.UNICODE)
_ROMAN_NUMERAL_RE = re.compile(r"^[ivxlcdm]+$")


def _has_macron(text):
    return any(c in _MACRON_CHARS for c in str(text or ""))


def _tokens(text):
    return _WORD_RE.findall(str(text or ""))


def _vocab_units(text):
    """Whitespace-delimited units with internal hyphens/punctuation removed, so
    a syllabified or hyphenated form ("rē-GĪ-na") is treated as one Latin word
    ("rēgīna"), not three macron-bearing fragments. Keeps letters and macrons."""
    units = []
    for piece in str(text or "").split():
        joined = "".join(_WORD_RE.findall(piece))
        if joined:
            units.append(joined)
    return units


def correct_option_text(item):
    """For a choice item, the text of the correct option (or None)."""
    opts = item.get("options")
    ans = item.get("answer")
    if isinstance(opts, dict) and ans in opts:
        return opts[ans]
    return None


def _answer_strings(item):
    """Every string that functions as an answer, for the macron checks."""
    out = []
    ct = correct_option_text(item)
    if ct is not None:
        out.append(ct)
    for b in item.get("boxes") or []:
        for a in b.get("answer") or []:
            out.append(a)
    if item.get("translation_model_answer"):
        out.append(item["translation_model_answer"])
    if item.get("model_answer"):
        out.append(item["model_answer"])
    return out


_ENDING_RE = re.compile(r"-([A-Za-zāēīōūȳĀĒĪŌŪȲ]+)")


def _ending_tokens(text):
    """Tokens written as grammatical ENDINGS — "-ārum", "-ibus", "-ium".

    An ending is not a word and has no place on a vocabulary list, but the
    tokenizer drops the hyphen and it arrives looking like unknown Latin. From
    Unit 2 on, items talk about endings constantly (every declension and
    conjugation node does), so without this the vocabulary check would fire
    dozens of times on questions that are correct — and a check that cries wolf
    is one a reviewer learns to click past.
    """
    return {clean(m.group(1)) for m in _ENDING_RE.finditer(str(text or ""))}


def _glossed_tokens(stem):
    """Latin tokens that are glossed in the stem: anything inside ( ) or [ ],
    the token immediately before an opening ( or [, and a token immediately
    before the word 'means'. Approximate but enough for the macron check."""
    s = str(stem or "")
    glossed = set()
    for inside in re.findall(r"[\(\[]([^\)\]]*)[\)\]]", s):
        for t in _tokens(inside):
            glossed.add(clean(t))
    for m in re.finditer(r"([A-Za-zāēīōūȳĀĒĪŌŪȲ]+)\s*[\(\[]", s):
        glossed.add(clean(m.group(1)))
    for m in re.finditer(r"([A-Za-zāēīōūȳĀĒĪŌŪȲ]+)\s+means\b", s):
        glossed.add(clean(m.group(1)))
    return glossed


# --------------------------------------------------------------------------
# Per-item checks
# --------------------------------------------------------------------------

def check_duplicate_options(item):
    """1. Two options that are the same string (common with neuter plurals)."""
    opts = item.get("options")
    flags = []
    if isinstance(opts, dict):
        seen = {}
        for k, v in opts.items():
            key = str(v).strip()
            if key in seen:
                flags.append(Flag("duplicate_options", "error",
                                  f"options {seen[key]} and {k} are the same string: {v!r}"))
            else:
                seen[key] = k
    return flags


def check_vocabulary(item, allowed, level="heuristic"):
    """2. A Latin word outside the vocabulary. Reliable only for macron-bearing
    tokens and generable Latin forms; documented in the module docstring."""
    flags = []
    glossed = _glossed_tokens(item.get("stem"))
    # Fields to scan: the stem, the option values, and box answers.
    scan = [str(item.get("stem") or "")]
    if isinstance(item.get("options"), dict):
        scan.extend(str(v) for v in item["options"].values())
    for b in item.get("boxes") or []:
        scan.extend(str(a) for a in (b.get("answer") or []))

    reported = set()
    for text in scan:
        exempt = glossed | _ending_tokens(text)
        for tok in _vocab_units(text):
            if not _has_macron(tok):
                continue                     # only macron tokens are sure Latin
            n = clean(tok)
            if not n or len(n) == 1 or n in allowed or n in exempt:
                continue    # single letters (e.g. an illustrative "ā") aren't words
            if n.endswith("que") and n[:-3] in allowed:
                continue
            if _ROMAN_NUMERAL_RE.match(n):
                continue
            if n in reported:
                continue
            reported.add(n)
            flags.append(Flag("vocabulary", level,
                              f"Latin word not on core/content list and not glossed: {tok!r}"))
    return flags


def check_recall_has_options(item):
    """3. A recall question with options (should be write-in)."""
    if item.get("assess") == "recall" and (
            item.get("format") == "choice" or item.get("options")):
        return [Flag("recall_has_options", "error",
                     "recall item uses multiple-choice; recall must be write-in")]
    return []


def check_explain_reasons(item):
    """4. An explain question whose options may not be reasons. Approximate:
    causal-word proxy. Flags only when NO option carries a causal word; the
    literal per-option count is returned as a note for the import report."""
    flags = []
    if item.get("assess") != "explain":
        return flags
    opts = item.get("options")
    if not isinstance(opts, dict):
        return flags
    def has_causal(v):
        s = " " + str(v).lower() + " "
        return any(c in s for c in _CAUSAL)
    with_causal = [k for k, v in opts.items() if has_causal(v)]
    # The bare causal-word proxy (the spec's literal check 4) flags ~60% of
    # well-built explain items, because good reasons are routinely phrased
    # without because/since/so/as ("From the genitive...", "It shows the
    # stem..."). To be usable we require the second, stronger signal of the real
    # failure mode -- options that look like *answers* rather than reasons, i.e.
    # at least one very short option. Full-sentence reason-options are spared.
    shortest_words = min(len(str(v).split()) for v in opts.values())
    if len(with_causal) == 0 and shortest_words <= 3:
        flags.append(Flag("explain_reasons", "heuristic",
                          "no option contains a causal word (because/since/so/as) and "
                          "an option is short enough to be an answer rather than a reason"))
    return flags


def literal_explain_missing_causal(item):
    """The spec's literal check 4 reading, reported (not flagged) so its noise
    is visible: count options lacking a causal word."""
    if item.get("assess") != "explain":
        return 0
    opts = item.get("options")
    if not isinstance(opts, dict):
        return 0
    def has_causal(v):
        s = " " + str(v).lower() + " "
        return any(c in s for c in _CAUSAL)
    return sum(0 if has_causal(v) else 1 for v in opts.values())


def check_nodes_exist(item, valid_nodes):
    """5. A node that does not exist, in the tag or a what-went-wrong entry."""
    flags = []
    if item.get("node") not in valid_nodes:
        flags.append(Flag("node_missing", "error",
                          f"item node {item.get('node')!r} is not in the spec"))
    for w in item.get("what_went_wrong") or []:
        wn = w.get("node")
        if wn and wn not in valid_nodes:
            flags.append(Flag("node_missing", "error",
                              f"what-went-wrong node {wn!r} is not in the spec"))
    for t in item.get("touches") or []:
        if t not in valid_nodes:
            flags.append(Flag("node_missing", "error",
                              f"touches node {t!r} is not in the spec"))
    return flags


def check_macron(item):
    """6. Macron-flag mismatch, both directions."""
    flags = []
    mm = bool(item.get("macron_matters"))
    answers = _answer_strings(item)
    if mm:
        # 6a (refined): flagged macron_matters but no macron anywhere in the
        # answers OR the stem. The refinement avoids flagging items whose macron
        # is in the stem's minimal pair.
        if not any(_has_macron(a) for a in answers) and not _has_macron(item.get("stem")):
            flags.append(Flag("macron_flag", "heuristic",
                              "macron_matters is true but no macron appears in the "
                              "stem or the answers"))
    else:
        # 6b: not flagged, but the correct answer differs from a wrong option
        # only by a macron -> the distinction is a macron and should be flagged.
        opts = item.get("options")
        ct = correct_option_text(item)
        if isinstance(opts, dict) and ct is not None:
            ct_letters = clean(ct)                     # macron-stripped
            ct_kept = _keep_macron_clean(ct)
            for k, v in opts.items():
                if v is ct or v == ct:
                    continue
                if clean(v) == ct_letters and _keep_macron_clean(v) != ct_kept:
                    flags.append(Flag("macron_flag", "error",
                                      f"correct answer and option {k} differ only by a "
                                      f"macron but macron_matters is not set"))
                    break
    return flags


def _keep_macron_clean(text):
    """Clean but keep macrons (lower-case, strip punctuation/spaces)."""
    return clean(text, macron_matters=True)


def literal_macron_no_macron_in_answers(item):
    """The spec's literal check 6a: macron_matters true and no macron in the
    answers (ignoring the stem). Reported, not flagged."""
    if not item.get("macron_matters"):
        return False
    answers = _answer_strings(item)
    return not any(_has_macron(a) for a in answers)


def _box_lists(item):
    """All box lists in the item and in its v3 version."""
    boxes = list(item.get("boxes") or [])
    v3 = (item.get("versions") or {}).get("v3")
    if isinstance(v3, dict):
        boxes += list(v3.get("boxes") or [])
    return boxes


def check_box_length(item):
    """7. An answer box longer than four words."""
    flags = []
    for b in _box_lists(item):
        for a in b.get("answer") or []:
            if len(str(a).split()) > 4:
                flags.append(Flag("box_too_long", "error",
                                  f"box answer is more than four words: {a!r}"))
    return flags


# --------------------------------------------------------------------------
# Cross-item check
# --------------------------------------------------------------------------

def find_duplicate_questions(items):
    """8. Duplicate question: same node and same (cleaned) stem. Returns a dict
    item_id -> Flag for the second and later members of each duplicate group."""
    groups = defaultdict(list)
    for it in items:
        key = (it.get("node"), clean(it.get("stem")))
        groups[key].append(it)
    out = {}
    for (node, _stem), members in groups.items():
        if len(members) > 1:
            first = members[0].get("id")
            for dup in members[1:]:
                out[dup.get("id")] = Flag("duplicate_question", "error",
                                          f"same node ({node}) and stem as {first}")
    return out


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def run_all(items, valid_nodes, allowed, existing_items=None):
    """Run every check over `items`. `existing_items` is the already-approved
    bank (for cross-run duplicate detection); may be None.

    Returns dict item_id -> list[Flag], and a report dict of counts.
    """
    all_for_dupes = list(items) + list(existing_items or [])
    dupes = find_duplicate_questions(all_for_dupes)

    flags_by_item = defaultdict(list)
    literal_check4 = 0
    literal_check6 = 0

    for it in items:
        iid = it.get("id")
        fs = []
        fs += check_duplicate_options(it)
        fs += check_vocabulary(it, allowed)
        fs += check_recall_has_options(it)
        fs += check_explain_reasons(it)
        fs += check_nodes_exist(it, valid_nodes)
        fs += check_macron(it)
        fs += check_box_length(it)
        if iid in dupes:
            fs.append(dupes[iid])
        if fs:
            flags_by_item[iid].extend(fs)
        literal_check4 += 1 if literal_explain_missing_causal(it) else 0
        literal_check6 += 1 if literal_macron_no_macron_in_answers(it) else 0

    report = {
        "n_items": len(items),
        "n_flagged": len(flags_by_item),
        "by_check": defaultdict(int),
        "by_level": defaultdict(int),
        "literal_check4_explain_items_with_a_noncausal_option": literal_check4,
        "literal_check6a_macron_items_without_macron_answers": literal_check6,
    }
    for fs in flags_by_item.values():
        for f in fs:
            report["by_check"][f.check] += 1
            report["by_level"][f.level] += 1
    report["by_check"] = dict(report["by_check"])
    report["by_level"] = dict(report["by_level"])
    return dict(flags_by_item), report
