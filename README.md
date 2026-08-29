# Latin I — Review Tool & Vocabulary Drill

Two small local apps that share one answer-checker:

1. **Review tool** (teacher-facing) — turns the generated question bank into a
   reviewed one. Mechanical checks absorb the proofreading; the human spends
   attention on judgment.
2. **Vocabulary drill** (student-facing) — typed, spaced practice on the weekly
   core word list.

No teacher dashboard, no accounts, no grammar app, no question generation, no
grading. Those are out of scope by design.

## Run it

### Easiest (macOS): double-click `start.command`

In Finder, open the project folder and double-click **`start.command`**. It sets
itself up the first time (about a minute), then opens the app in your browser.
Double-click it again any time you want to start.

*If macOS says it can't be opened because it's from an unidentified developer:*
right-click the file → **Open** → **Open**. You only do that once.

### Or from Terminal

```bash
cd Latin-1-Practice-App
./start.command
```

### Or by hand

On a Mac the commands are `python3` and `pip3` — plain `python`/`pip` usually
don't exist, which is the most common first-run stumble:

```bash
python3 -m pip install -r requirements.txt
python3 run.py
```

Whichever route, the terminal prints the two addresses to use: one for this
laptop and one for a phone on the same wifi. It starts on port 5000 when that
is free and moves to 5050 when it isn't — macOS runs AirPlay Receiver on 5000,
so a Mac usually lands on 5050. Force a specific port with `PORT=8000 python3
run.py`.
The review bank imports itself on first visit, so you go straight to a working
queue.

**No Python on the Mac?** Run `xcode-select --install` in Terminal, or download
it from [python.org/downloads](https://www.python.org/downloads/).

Everything is local: source YAML is read-only, and the app's own data (review
decisions + practice events) lives in `data/review.sqlite`. Delete that file to
start clean.

## Layout

| File | What it is |
|------|-----------|
| `answercheck.py` | **Shared** right/close/wrong module. Built first, tested alone. |
| `dataio.py` | Reads the source YAML; generates the legal Unit 0–1 inflected forms. |
| `checks.py` | The eight mechanical checks. |
| `store.py` | SQLite store: items + review state, and the append-only event record. |
| `drill.py` | Drill card selection, Leitner boxes, solid/shaky/not-yet. |
| `server.py` | Flask app — both apps, both route groups. |
| `run.py` | Launcher. |
| `vocab.yaml` | The drill's 80 words **with glosses** (see the caveat below). |
| `templates/`, `static/` | Mobile-first UI. |
| `tests/` | 50 tests. `python3 -m unittest discover -s tests`. |
| `latin1-*.yaml` | The three source files (never modified by the apps). |

## The shared answer-checker

`answercheck.check(response, accepted, macron_matters=False)` → `right` /
`close` / `wrong`. Before comparing it strips, from both sides: capitals,
macrons, punctuation, repeated spaces, a leading dash (`-mus` = `mus`), and a
leading `the`/`a`. `close` = within two edits of an accepted answer; it never
counts as wrong and, in the drill, prompts a retype without revealing the
answer.

One deliberate call: on `macron_matters` items, an answer that is right on the
letters but missing the distinguishing macron (`regina` for `rēgīna`, `liber`
for `līber`) is **wrong**, not `close`. The spec's required case says such an
answer must "not match"; treating it as a forgivable typo would defeat the point
of a macron-critical item. A genuine letter typo on those items is still
`close`.

## Review tool

- **Queue picker** — nodes with unreviewed counts, grouped so you review a
  concept in a row. Separate **flagged queue** for anything a check caught or the
  generator marked `needs_review`.
- **Review screen** — the whole question, the correct answer, the
  what-went-wrong menu, tier and node, and any flags. One-thumb bar: **Approve /
  Edit / Reject / Skip**. Progress persists after every action, so you can close
  the phone and resume in place.
- **Edit** — inline YAML, save & approve. Broken YAML is rejected with the error,
  not saved.
- **Skip** = *decide later*: the item cycles to the back of its queue and returns
  after the rest, rather than disappearing.
- **Export** — approved questions out as YAML in the exemplar shape. Rejected
  ones stay in the store with their reason, so a later generation run can be
  compared against what failed.
- **Live-fire hook** — `store.flag_item_live_fire()` exists and is wired to the
  data, but unused: the field is built, the feature is not (per spec).

### The eight mechanical checks

Run on import, before any human sees a question. Validated against the 75
known-good exemplars: **zero error-level flags**, one explainable heuristic flag.

| # | Check | Level | Notes |
|---|-------|-------|-------|
| 1 | Two options that are the same string | error | catches neuter subject/object identical forms |
| 2 | Latin word outside the vocabulary | heuristic | **approximate — see below** |
| 3 | Recall question with options | error | recall must be write-in |
| 4 | Explain options aren't reasons | heuristic | **approximate — see below** |
| 5 | Node doesn't exist (tag or what-went-wrong) | error | |
| 6 | Macron-flag mismatch (both directions) | error / heuristic | **6a approximate — see below** |
| 7 | Answer box longer than four words | error | |
| 8 | Duplicate question (same node + stem) | error | across the import and the store |

The import screen reports the counts and warns if check 1 or 2 catches more than
a small fraction — the signal that a generation run has a *systematic* problem
worth fixing at the source.

Running the current generated bank (213 items): **0 error-level flags**, 14
heuristic flags (10 explain-reason, 4 vocabulary — two of which, `Rōmānus` and
`Salvē`, are real off-list words already marked `needs_review`).

## Vocabulary drill

- 80 core words, both directions, **typed** (no multiple choice), checked by the
  shared module. Macrons never required.
- **Leitner boxes**, nothing fancier: right moves a word up a box and pushes it
  out; wrong drops it to box 1; close leaves it. Intervals 0 / 1 / 3 / 7 / 21
  days.
- **State is derived from history, never stored.** Each attempt appends one event:
  `student_id, timestamp, item_id, spec_node_id, response, result, latency_ms,
  context, version`. `context` is `practice` here; `version` is carried (`v1`)
  from day one though only v1 exists.
- **solid / shaky / not yet** (these exact words; the app never says "mastery").
  *solid* needs several rights, on more than one day, including at least one a
  week or more after the word was first seen — that delayed success is the whole
  point. A student sees only their own progress.

---

## What works

All five build steps, verified in order:

1. Answer-checker + 25 tests (every spec-named case).
2. YAML loading + checks; clean on the 75 exemplars (0 error-level).
3. Review tool: import, queue, review, edit round-trip, skip-cycle, resume,
   export — smoke-tested through the HTTP layer.
4. Drill: both directions, close→retype, macron-optional, event logging.
5. Event record + solid/shaky/not-yet, derived from history.

50 tests pass (`python3 -m unittest discover -s tests`).

## What is approximate, and how it can be fooled

Said plainly, because these will mislead if trusted blindly:

- **Check 2 (vocabulary) has real recall gaps.** Without a Latin lexicon, the only
  tokens it can be *sure* are Latin are ones carrying a macron (plus the inflected
  forms it can generate from the 80 lemmas, and the content-vocabulary list). So
  it reliably catches a macron-bearing out-of-list word, or an out-of-list form in
  an answer — but a **macron-free out-of-scope Latin word buried in an English
  stem will slip past it** (e.g. a stray `rosa`). It also can't tell a proper noun
  from a common noun, so supplied names are simply allowed. It is precise (it
  won't cry wolf on English prose) at the cost of completeness. The generated
  bank's flags are all correct; don't read a clean check-2 as "no off-list words
  exist."

- **Check 4 (explain options are reasons) is a proxy, not a proof.** The spec's
  literal rule — flag if an option lacks a causal word (because/since/so/as) —
  flags ~60% of *well-built* explain items, because good reasons are routinely
  phrased without one ("From the genitive…", "It shows the stem…"). Implemented
  literally it is unusable. This tool instead flags only when **no** option has a
  causal word **and** some option is short enough to look like an answer rather
  than a reason — the actual "you wrote a recognize item and mistagged it"
  failure. The literal count is still shown on the import screen for transparency.
  It can still be fooled: a genuinely mis-built explain item whose wrong "answers"
  happen to be long sentences will not trip it.

- **Check 6a (macron_matters but no macron)** as written fires on legitimate items
  whose macron lives in a stem minimal pair, not the answer. This tool flags only
  when there is **no** macron in the stem *or* the answers. Even so it flags
  `EX-RECOG-003` — a known-good exemplar that sets `macron_matters: true` with no
  macron anywhere in the item. The check is right to notice; that exemplar's flag
  is decorative. Literal count is reported too.

- **Short-answer closeness.** "within two characters" means a two-letter word like
  `es` is one edit from `est`, so a wrong short neighbour comes back as `close`,
  not `wrong`. This is faithful to the spec and fine in practice (close is
  low-stakes and prompts a retype), but it means the drill is lenient on very
  short answers. Covered by a test that documents it.

## Where this deviated from the spec, and why

- **Framework:** Flask + PyYAML (the spec left the choice open — "whatever is
  fastest"). One `pip install`; server-rendered mobile-first HTML, no build step.
- **The drill's glosses are not from the source files.** The source YAML lists the
  80 words but carries **no English glosses** (the spec names `gloss` as a field,
  but the data isn't there). The drill can't run without them, so they're seeded
  in `vocab.yaml`, clearly marked as mine and teacher-editable. **Please check
  them** — they're first-year-Latin standard, but they're my glosses, not Jack's.
- **Skip** is "decide later" (cycles to the back), not a terminal `skipped`
  status, so skipped items actually come back.
- **`spec_node_id` is `null` for drill events** — vocabulary is deliberately not
  in the spec node list, so there is no node to attach.
- **`version` is always `v1` in the drill** — there are no v2/v3 vocabulary cards;
  the field is carried anyway, as instructed.

## Storage & reset

SQLite (`data/review.sqlite`, WAL mode). A few thousand questions and a few
hundred thousand events by June sit inside this comfortably. Delete the file to
reset; the source YAML is never touched. Built for one teacher and ~88 students
at light load, not for heavy concurrency.
