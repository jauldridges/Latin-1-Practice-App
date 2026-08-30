"""
Shared answer-checking module.

The single most important piece of the two applications: it decides whether a
student's typed answer is right, close, or wrong. Both the review tool and the
vocabulary drill call check() so the rule lives in exactly one place.

Specification (from latin1-item-exemplars.yaml, answer_checking section):

  Before comparing, strip from BOTH the typed answer and each accepted answer:
    - capital letters
    - macrons (a e i o u with a bar become plain a e i o u)
    - punctuation
    - extra or repeated spaces
    - a leading dash, so "-mus" and "mus" are the same
    - a leading "the" or "a"

  right  - the cleaned answer matches any accepted answer exactly.
  close  - the cleaned answer is within two characters (edit distance <= 2)
           of an accepted answer. Never counts as wrong, never triggers the
           follow-up menu; the caller re-prompts for spelling.
  wrong  - everything else.

  Exception: when macron_matters is True, the macron-stripping step is skipped
  on both sides, so a macron must match. Every other cleaning step still runs.
"""

import re
import unicodedata

# Explicit macron table, lower- and upper-case, so a macron is turned into its
# plain vowel rather than dropped. Handles precomposed forms; a NFC pass below
# also catches combining-macron sequences.
_MACRON_MAP = {
    "ā": "a",  # a-macron
    "ē": "e",  # e-macron
    "ī": "i",  # i-macron
    "ō": "o",  # o-macron
    "ū": "u",  # u-macron
    "Ā": "a", "Ē": "e", "Ī": "i", "Ō": "o", "Ū": "u",
    "ȳ": "y", "Ȳ": "y",  # y-macron (not used in the core list, cheap to include)
}

_MACRON_TABLE = {ord(k): v for k, v in _MACRON_MAP.items()}

# Any character that is not a letter, a digit, or whitespace is punctuation and
# is removed. Works on unicode letters, so macrons that survive (macron_matters)
# are kept.
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_LEADING_ARTICLE_RE = re.compile(r"^(the|a)\s+")


def strip_macrons(text):
    """Replace macron vowels with their plain form, including any that arrive as
    a base vowel plus a combining macron (U+0304)."""
    text = text.translate(_MACRON_TABLE)
    if "̄" in text:
        # Decompose, drop combining macrons, recompose.
        text = unicodedata.normalize("NFD", text)
        text = text.replace("̄", "")
        text = unicodedata.normalize("NFC", text)
    return text


def clean(text, macron_matters=False):
    """Apply the cleaning steps in order and return the comparable form."""
    if text is None:
        return ""
    s = str(text)
    # 1. capital letters
    s = s.lower()
    # 2. macrons (unless they are the whole point of the item)
    if not macron_matters:
        s = strip_macrons(s)
    # 3. punctuation -> removed. This also removes a leading dash, so "-mus"
    #    becomes "mus" (the spec calls the leading dash out separately; removing
    #    all punctuation subsumes it). Removing to nothing keeps single Latin
    #    tokens intact; multi-word English answers are separated by spaces, not
    #    punctuation, so they are unaffected.
    s = _PUNCT_RE.sub("", s)
    # 4. extra or repeated spaces
    s = _WS_RE.sub(" ", s).strip()
    # 5. a leading "the" or "a" (do this after space-collapsing so the token is
    #    cleanly at the front). Loop once more in case cleaning exposed another.
    prev = None
    while prev != s:
        prev = s
        s = _LEADING_ARTICLE_RE.sub("", s).strip()
    return s


def _edit_distance(a, b, cap=2):
    """Levenshtein distance between a and b, short-circuiting once it is known
    to exceed `cap` (we never care about distances larger than the close
    threshold)."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > cap:
        return cap + 1
    # Ensure a is the shorter for a small row.
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    previous = list(range(la + 1))
    for j in range(1, lb + 1):
        current = [j] + [0] * la
        best_in_row = current[0]
        bj = b[j - 1]
        for i in range(1, la + 1):
            cost = 0 if a[i - 1] == bj else 1
            current[i] = min(
                previous[i] + 1,      # deletion
                current[i - 1] + 1,   # insertion
                previous[i - 1] + cost,  # substitution
            )
            if current[i] < best_in_row:
                best_in_row = current[i]
        if best_in_row > cap:
            return cap + 1
        previous = current
    return previous[la]


def _close_allowance(accepted_clean, cap):
    """How many edits may still count as CLOSE, given how long the answer is.

    <=3 characters: none -- a one- or two-edit difference on a short answer is
    a different answer, not a slip. 4-5: one. 6+: two.
    """
    n = len(accepted_clean)
    if n <= 3:
        return 0
    if n <= 5:
        return min(1, cap)
    return min(2, cap)


def check(response, accepted, macron_matters=False, close_threshold=2):
    """Compare a typed response against a list of accepted answers.

    Returns one of "right", "close", "wrong".

    - response: the raw string the student typed.
    - accepted: a string or a list/tuple of accepted answer strings.
    - macron_matters: when True, macrons are not stripped and must match.
    - close_threshold: max edit distance (default 2) counted as "close".
    """
    if isinstance(accepted, (str, bytes)):
        accepted = [accepted]
    accepted = [a for a in (accepted or []) if a is not None]

    cleaned = clean(response, macron_matters)
    cleaned_accepted = [clean(a, macron_matters) for a in accepted]
    # Ignore any accepted answers that clean away to nothing.
    cleaned_accepted = [a for a in cleaned_accepted if a != ""]

    if cleaned == "" or not cleaned_accepted:
        # An empty typed answer is never "close" to a short word; treat as wrong.
        return "wrong"

    if cleaned in cleaned_accepted:
        return "right"

    if macron_matters:
        # On these items the macron is the whole point. If the letters match an
        # accepted answer but the macrons do not, the student made exactly the
        # error the item tests (e.g. "regina" for "rēgīna", or "liber" for
        # "līber"). That is wrong, not a forgivable "close" spelling slip. Only
        # a genuine letter typo may still count as close, below.
        letters = strip_macrons(cleaned)
        if any(letters == strip_macrons(a) for a in cleaned_accepted):
            return "wrong"

    # CLOSE is length-scaled. "Within two characters" is the right rule for a
    # word like puella, where puela is obviously a typo. It is the wrong rule
    # for very short answers: every wrong single letter is one edit from the
    # right one, so "q" would be marked a typo of "w", and "es" a typo of
    # "est" -- suppressing exactly the confusions the what-went-wrong menu
    # exists to count. Short answers therefore demand an exact match.
    for accepted_clean in cleaned_accepted:
        allowed = _close_allowance(accepted_clean, close_threshold)
        if allowed == 0:
            continue
        d = _edit_distance(cleaned, accepted_clean, allowed)
        if 1 <= d <= allowed:
            return "close"
    return "wrong"


__all__ = ["check", "clean", "strip_macrons"]
