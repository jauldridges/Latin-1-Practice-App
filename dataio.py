"""
Reading the source YAML files and deriving the reference data the mechanical
checks and the two apps need. Nothing here writes to the source files.

The three source files (repository root):
  latin1-spec.yaml          - 360 spec nodes. Never modified.
  latin1-item-exemplars.yaml - 75 hand-built questions + the vocabulary lists.
  latin1-items-unit01.yaml  - the generated bank under review.

The one derived thing worth explaining is generate_legal_forms(): it expands the
80 core lemmas into the inflected forms a student could legally meet in Units 0
and 1 (the two noun tables, the two verb conjugations, sum, the adjectives, the
imperatives and infinitives). The vocabulary check uses that set so a normal
inflected form such as "laudāmus" or "dōna" is recognised as in-scope.
"""

import os
import yaml

from answercheck import clean, strip_macrons

ROOT = os.path.dirname(os.path.abspath(__file__))

SPEC_FILE = os.path.join(ROOT, "latin1-spec.yaml")
EXEMPLAR_FILE = os.path.join(ROOT, "latin1-item-exemplars.yaml")
BANK_FILE = os.path.join(ROOT, "latin1-items-unit01.yaml")
TEACHING_FILE = os.path.join(ROOT, "teaching.yaml")


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_spec(path=SPEC_FILE):
    doc = load_yaml(path)
    return {n["id"]: n for n in doc["nodes"]}


def load_exemplars(path=EXEMPLAR_FILE):
    return load_yaml(path)


def load_bank(path=BANK_FILE):
    doc = load_yaml(path)
    return doc.get("items", [])


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

def _norm(tok):
    """Normalise a token the way the vocabulary check compares: lower-case,
    macron-stripped, punctuation removed."""
    return clean(tok, macron_matters=False)


def core_vocab_words(exemplars):
    """All 80 core words, flattened from the weekly lists, normalised."""
    out = set()
    weeks = exemplars.get("vocabulary_units_0_1", {})
    for week in weeks.values():
        for entry in week:
            for tok in str(entry).split():
                n = _norm(tok)
                if n:
                    out.add(n)
    return out


def content_vocab_words(exemplars):
    """Every token from the content-vocabulary lists (supplied/glossed Latin)
    plus the phrase list, normalised. These may appear in items freely."""
    out = set()
    content = exemplars.get("content_vocabulary_units_0_1", {})
    for group in content.values():
        for entry in group:
            for tok in str(entry).split():
                n = _norm(tok)
                if n:
                    out.add(n)
    # The week-of-aug-24 phrase list is core, but its individual tokens (sē,
    # māter, plūribus, ...) should also be recognised.
    weeks = exemplars.get("vocabulary_units_0_1", {})
    for entry in weeks.get("week_of_aug_24", []):
        for tok in str(entry).split():
            n = _norm(tok)
            if n:
                out.add(n)
    return out


# --- Core lemmas by morphological class (the 80 words are known; hard-coding
# --- the class is safer than guessing it from the ending, especially for the
# --- -er nouns and the irregular sum). Written macron-free; the generator
# --- works on the normalised forms and the check compares normalised too.

_FIRST_DECL = ["aqua", "terra", "via", "porta", "insula", "silva", "puella",
               "femina", "nauta", "agricola", "patria", "fama", "vita", "luna",
               "stella", "regina", "provincia", "poeta"]
_SECOND_US = ["dominus", "servus", "amicus"]
_SECOND_ER = {"puer": "puer", "ager": "agr", "vir": "vir"}   # nom -> stem
_SECOND_NEUTER = ["bellum", "oppidum", "donum", "verbum"]
_FIRST_CONJ = ["amo", "laudo", "porto", "voco", "specto", "narro", "paro",
               "servo", "supero", "pugno"]
_SECOND_CONJ = ["video", "habeo", "teneo", "moneo", "debeo"]
_SUM = ["sum", "es", "est", "sumus", "estis", "sunt"]
_ADJ_US = ["magnus", "parvus", "bonus", "malus", "multus", "longus", "altus",
           "novus", "clarus", "meus", "tuus"]
_ADJ_ER = {"pulcher": "pulchr", "miser": "miser", "liber": "liber",
           "noster": "nostr", "vester": "vestr"}
_PARTICLES = ["et", "non", "sed", "quod", "ubi", "nunc", "saepe", "semper",
              "que", "aut"]


def generate_legal_forms():
    """The inflected forms a Unit 0-1 student could legally meet, normalised."""
    forms = set()

    for w in _FIRST_DECL:
        stem = w[:-1]
        forms.update([w, stem + "am", stem + "ae", stem + "as"])

    for w in _SECOND_US:
        stem = w[:-2]
        forms.update([w, stem + "um", stem + "i", stem + "os", stem + "e"])

    for nom, stem in _SECOND_ER.items():
        forms.update([nom, stem + "um", stem + "i", stem + "os"])

    for w in _SECOND_NEUTER:
        stem = w[:-2]
        forms.update([w, stem + "a"])

    for w in _FIRST_CONJ:
        pstem = w[:-1] + "a"          # laudo -> lauda
        forms.update([w, pstem + "s", pstem + "t", pstem + "mus",
                      pstem + "tis", pstem + "nt", pstem + "re",
                      pstem, pstem + "te"])

    for w in _SECOND_CONJ:
        estem = w[:-1]                # video -> vide
        forms.update([w, estem + "s", estem + "t", estem + "mus",
                      estem + "tis", estem + "nt", estem + "re",
                      estem, estem + "te"])

    forms.update(_SUM)
    forms.add("esse")

    for w in _ADJ_US:
        stem = w[:-2]
        for end in ("us", "a", "um", "i", "os", "as", "ae", "am", "e"):
            forms.add(stem + end)

    for nom, stem in _ADJ_ER.items():
        forms.add(nom)
        for end in ("a", "um", "i", "os", "as", "ae", "am"):
            forms.add(stem + end)

    forms.update(_PARTICLES)

    return {_norm(f) for f in forms}


def allowed_latin(exemplars):
    """Everything the vocabulary check treats as legal Latin: the generated
    inflected forms, the core lemmas, and the content/phrase vocabulary."""
    allowed = set()
    allowed |= generate_legal_forms()
    allowed |= core_vocab_words(exemplars)
    allowed |= content_vocab_words(exemplars)
    return allowed


# --------------------------------------------------------------------------
# Vocabulary drill word list
# --------------------------------------------------------------------------

def load_drill_words(path=None):
    """The drill's word list with English glosses.

    NOTE: the source files list the 80 core words but carry NO English glosses
    (see the vocabulary section of the spec: gloss is named as an item field but
    the data is not in these files). The drill cannot exist without glosses, so
    they live in vocab.yaml, seeded here and meant to be teacher-edited. This is
    called out in the writeup; the glosses are mine, not from the canonical
    files.
    """
    if path is None:
        path = os.path.join(ROOT, "vocab.yaml")
    doc = load_yaml(path)
    return doc.get("words", [])


def load_teaching(path=TEACHING_FILE):
    """Teaching text, keyed by spec node. Drafted separately from the items and
    never written to by either app -- this file is the teacher's."""
    if not os.path.exists(path):
        return {}
    doc = load_yaml(path) or {}
    return doc.get("nodes", {}) or {}


def teaching_fingerprint(entry):
    """A hash of the text a teacher actually approved. If the wording later
    changes in teaching.yaml, the approval no longer matches and the entry
    reverts to draft -- so edited text cannot inherit an old approval."""
    import hashlib
    parts = [str(entry.get("explain", "")).strip(),
             "\n".join(str(x) for x in (entry.get("examples") or [])),
             str(entry.get("when_wrong", "")).strip()]
    return hashlib.sha256("\u0000".join(parts).encode("utf-8")).hexdigest()[:16]
