"""
The vocabulary hint: the word in an example sentence.

A student asked for it -- "what if you give me the word in an example Latin
sentence" -- and it solves the problem the drill's hint used to have, which was
that anything said about a word's meaning IS the answer. A sentence gives
context instead: the other words are ones the student already knows, and the
sentence says something that only makes sense one way.

How much it shows depends on the direction of the card:

  Latin -> English   the sentence with the word in bold, and no English,
                     which would contain the answer.
  English -> Latin   the sentence with the word blanked out, plus its English,
                     which only repeats what the prompt already says.
  after answering    the sentence and its English, either way.

Sentences live in vocab-examples.yaml, one per drill word, with the word marked
*like this*. A student sees one only once the teacher has approved that exact
wording; the approval is a fingerprint of the text, kept in the same table as
teaching-text approvals under a "vocabhint:" key, so a reworded sentence
cannot inherit an old approval.
"""

import hashlib
import os
import re

import yaml

from answercheck import clean

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "vocab-examples.yaml")
PREFIX = "vocabhint:"
BLANK = "＿＿＿＿"

_MARK = re.compile(r"\*([^*]+)\*")


def key(word):
    """The drill's key for a word (lower case, macrons folded)."""
    return clean(word or "")


def approval_key(word):
    return PREFIX + key(word)


def load(path=PATH):
    """{word key: {"word", "latin", "en"}} from the YAML file."""
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    out = {}
    for e in doc.get("examples") or []:
        out[key(e.get("word"))] = {"word": e.get("word", ""), "latin": e.get("latin", ""),
                                   "en": e.get("en") or ""}
    return out


def problems(entry):
    """What would make a sentence unusable, in plain words. Empty is fine."""
    out = []
    marks = _MARK.findall(entry.get("latin") or "")
    if len(marks) != 1:
        out.append("mark the word with *asterisks* exactly once")
    if not (entry.get("latin") or "").replace("*", "").strip():
        out.append("the sentence is empty")
    return out


def fingerprint(entry):
    text = "%s\u0000%s" % ((entry.get("latin") or "").strip(), (entry.get("en") or "").strip())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def segments(entry, blank=False):
    """[(text, is_the_word)] -- the template bolds or blanks the word itself."""
    s = entry.get("latin") or ""
    out, pos = [], 0
    for m in _MARK.finditer(s):
        if m.start() > pos:
            out.append((s[pos:m.start()], False))
        out.append((BLANK if blank else m.group(1), True))
        pos = m.end()
    if pos < len(s):
        out.append((s[pos:], False))
    return out


def plain(entry):
    """The sentence with the marks taken out."""
    return (entry.get("latin") or "").replace("*", "")


def for_card(entry, ask):
    """What the hint on an unanswered card may show, by direction."""
    if not entry:
        return None
    latin = bool(entry.get("en"))      # a Latin sentence has an English; a phrase's is English
    if ask == "en_la":
        return {"segments": segments(entry, blank=True), "en": entry.get("en") or "", "latin": latin}
    return {"segments": segments(entry), "en": "", "latin": latin}
