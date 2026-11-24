"""Regenerate the end of docs/di-mode-design.md (Appendix B, the class's
grammar sequence, and Appendix C, every DI lesson as built) from
latin1-spec.yaml and di/first-declension.yaml. Everything before
"## Appendix B." is written by hand and kept as it is.

    python3 docs/di_design_appendix.py
"""
import collections
import sys
import yaml

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import di_run  # noqa: E402
import dates   # noqa: E402

out = []
w = out.append

# --- class sequence (morphosyntax) ---
spec = yaml.safe_load(open("latin1-spec.yaml", encoding="utf-8"))
ms = [n for n in spec["nodes"] if n["id"].startswith("MS")]
by_week = collections.OrderedDict()
for n in sorted(ms, key=lambda n: (str(n.get("week")), n["id"])):
    by_week.setdefault((n.get("unit"), n.get("week")), []).append(n)
w("## Appendix B. The class's grammar sequence this year\n")
w("From `latin1-spec.yaml` (the course's source of truth): every morphosyntax topic, by the week it is taught. "
  "The NLE (Introduction to Latin / Latin I) is March 8–12, 2027.\n")
for (unit, week), nodes in by_week.items():
    label = dates.day(str(week), year=True)
    w("**Unit %s · week of %s**\n" % (unit, label))
    for n in nodes:
        w("- %s %s" % (n["id"], n["label"]))
    w("")

# --- lessons as built ---
doc = di_run.load()
w("## Appendix C. Every lesson as built\n")
w("Copied from `di/first-declension.yaml`. Each line is one screen. Format codes are in section 4; "
  "**bold** marks the highlighted word; in F4 / F8E the English comes first, then the Latin with the "
  "blank, then the ending. The app works out every answer, translation and wrong choice from the Latin.\n")

def items(xs):
    for x in xs or []:
        if isinstance(x, dict):
            t = (x.get("text") or "").replace("\n\n", " / ")
            w("- *Model screen:* %s" % (t if not t.startswith("TABLE") else "(the ending table: %s)" % t[6:]))
        else:
            w("- `%s`" % x)

w("### Placement (18 items)\n")
items(doc["placement"])
w("\nMissed item → first lesson (in order): %s\n" % ", ".join(str(x) for x in doc["placement_rule"]))
for L in doc["lessons"]:
    n = L["n"]
    w("### Lesson %d · %s%s\n" % (n, L["title"], (" (%s)" % L["subtitle"]) if L.get("subtitle") else ""))
    if L.get("today"):
        w("*Today screen:* %s\n" % L["today"])
    A = L.get("A")
    if isinstance(A, dict) and (A.get("words") or A.get("review") or A.get("review_all") or A.get("warmup")):
        bits = []
        if A.get("words"):
            bits.append("new: " + ", ".join(A["words"]) + (" (twice)" if A.get("twice") else ""))
        if A.get("review"):
            bits.append("review: " + ", ".join(A["review"]))
        if A.get("review_all"):
            bits.append("review: every word so far" + (", %s of them, missed ones first" % A["review_max"]
                                                         if A.get("review_max") else ""))
        w("**Part A · Words** (%s)\n" % "; ".join(bits))
        if A.get("warmup"):
            items(A["warmup"])
            w("")
    if L.get("B1"):
        w("**Part B1 · The job in English**\n")
        items(L["B1"].get("models"))
        items(L["B1"].get("items"))
        w("")
    B = L.get("B") or {}
    names = L.get("names") or {}
    w("**Part B · %s**\n" % names.get("B", "New ending"))
    for key, label in (("models", "Model"), ("echo", "Echo"), ("test", "Test"), ("examples", "Example sequence")):
        if B.get(key):
            w("*%s*\n" % label)
            items(B[key])
            w("")
    if L.get("C"):
        w("**Part C · Look-alikes**\n")
        items(L["C"])
        w("")
    D = L.get("D")
    if D:
        w("**Part D · Review**: %s\n" % ("the delayed-test item from every lesson, 1–11" if D == "delayed"
                                          else "%s items from earlier lessons: last lesson's delayed test and this student's misses first" % D))
    E = L.get("E")
    if E:
        w("**Part E · Sentences**\n")
        if isinstance(E, dict):
            w("*Reading: %s*\n" % E["reading"]["title"])
            for line in E["reading"]["lines"]:
                w("> %s  " % line)
            w("")
            items(E.get("questions"))
        else:
            items(E)
        w("")
    if L.get("delayed"):
        w("**Delayed test (hardest item):** `%s`\n" % L["delayed"])
    F = L.get("F") or {}
    if F:
        w("**Part F · Lesson check** (%d to pass)\n" % di_run.pass_mark(L))
        for s in ("A", "B"):
            w("*Set %s*\n" % s)
            items(F.get(s))
            w("")
DOC = os.path.join("docs", "di-mode-design.md")
head = open(DOC, encoding="utf-8").read().split("## Appendix B.")[0]
open(DOC, "w", encoding="utf-8").write(head + "\n".join(out) + "\n")
print("wrote", DOC)
