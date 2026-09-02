# Latin I — Review Tool & Vocabulary Drill

Two small local apps that share one answer-checker:

1. **Review tool** (teacher-facing) — turns the generated question bank into a
   reviewed one. Mechanical checks absorb the proofreading; the human spends
   attention on judgment.
2. **Vocabulary drill** (student-facing) — typed, spaced practice on the weekly
   core word list.
3. **Grammar practice** (student-facing) — serves the questions the teacher has
   approved, and classifies every miss through the what-went-wrong menu.
4. **Proctored quizzes** (both) — you hand-pick a fixed set; students answer
   straight through with no feedback, submit once, then review every question.

No teacher dashboard, no accounts, no question generation, no grading. Those are
out of scope by design.

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
| `practice.py` | Grammar-practice selection and grading (all four question formats). |
| `quiz.py` | Proctored quizzes: deferred grading, close handling, attempt summaries. |
| `stats.py` | Session and all-time progress figures, derived from the event history. |
| `server.py` | Flask app — both apps, both route groups. |
| `run.py` | Launcher. |
| `vocab.yaml` | The drill's 80 words **with glosses** (see the caveat below). |
| `teaching.yaml` | Teaching text for all 118 Unit 0–1 nodes. **Drafted, awaiting approval.** |
| `templates/`, `static/` | Mobile-first UI. |
| `tests/` | 116 tests. `python3 -m unittest discover -s tests`. |
| `latin1-*.yaml` | The three source files (never modified by the apps). |
| `QUERIES.md` | How to see student work — verified SQL, no dashboard needed. |

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

- **Review everything** — the default. One question after another across the
  whole bank until it is decided; approving never sends you back to a menu.
  It walks in **teaching order** (the node ids sort `CR` before `MS`, but the
  course runs MS → CR → RW → MW), marks the moment you cross into a new node,
  counts down the whole bank, and rolls into the flagged queue at the end.
  Stop whenever — every decision is already saved, and the button picks up
  where you left off.
- **Or one node at a time** — the old flow, still there under a fold: nodes
  with unreviewed counts so you can review one concept in a row. Its "nothing
  left here" screen now offers to continue with the rest instead of dead-ending
  at the queue. Separate **flagged queue** for anything a check caught or the
  generator marked `needs_review`.
- **Review screen** — the whole question, the correct answer, the
  what-went-wrong menu, tier and node, and any flags. One-thumb bar: **Approve /
  Edit / Reject / Skip**. Progress persists after every action, so you can close
  the phone and resume in place.
- **Edit** — inline YAML, save & approve. Broken YAML is rejected with the error,
  not saved.
- **Taking a decision back.** Auto-advance is what makes this tool fast and it
  is also what makes a mis-tap uncatchable — the decision is committed before
  the eye arrives. So an **undo strip** rides on the next question: always
  visible, never a gesture, `U` on the laptop. It steps back and *reopens* the
  question rather than silently reversing it. Identical after approve, reject
  and skip, and it is on the "everything is decided" screen too, so the last
  decision of a sitting is not the one you can't take back.
- **"Edit instead"** appears on the strip after a rejection, because the common
  case is not *this question is bad* but *this is nearly right and I'd rather
  fix it*. It reopens the editor with the rejection **cancelled** — otherwise
  abandoning the edit would silently leave it rejected. Rejecting itself is
  still one tap; the escape hatch is after, never before.
- **Session history** (`/review/history`) — every decision this sitting, newest
  first, with stem, node and verdict. Tapping one reopens that question with the
  decision changeable, because some mistakes only become visible five questions
  later. It lives in the signed cookie, so it survives closing the laptop.
- **Decisions append, they never overwrite.** `store.decisions` is the truth;
  `items.review_status` is a cache of the latest row. Changing your mind writes
  a new row and keeps the old one.
- **Changed your mind more than once?** That question gets flagged and listed at
  `/review/hard`. A verdict that went one way, then the other, then back is
  usually the question's fault. Undo does **not** count toward this: an undone
  verdict records what it retracted, so approve → undo → reject is one mis-tap
  corrected, not a flip-flop. (The change request asked for these in the flagged
  queue; they get their own list instead, because the flagged queue serves
  *undecided* questions and these are by definition decided several times over —
  putting them back in that rotation would hand them to you forever. The flag
  still goes on the item, so the export carries it to whoever generates the next
  batch.)
- **Skip** = *decide later*: the item is deferred to the end of the pass and
  returns after everything else, rather than disappearing. In continuous mode
  that means the end of the **whole bank**, not the end of the node — two
  passes, unskipped items first — because a skip that comes back one question
  later is not a skip.
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

## Grammar practice

The third app, and the reason the review work pays off.

- **Approved only.** Nothing unreviewed or rejected ever reaches a student.
  Contesting a question removes it from circulation immediately.
- **Never ahead of the lesson.** Selection is filtered by each node's teaching
  date in the spec, so a question cannot arrive before it has been taught —
  the "scope beats truth" rule, enforced in code rather than trusted.
- **All four formats:** multiple choice, boxes, self-check, and
  tag-then-translate. Boxes are graded and reported **per box** — four of six
  verb endings shows as four right and two wrong, not one red X — and honour
  `order_matters: false` by matching answers to boxes rather than by position.
- **The what-went-wrong menu** appears on a wrong answer only, never on a close
  one. Each choice is tagged to the node that explains that mistake, plus the
  three fixed choices, which are appended and never written per item.
- **Contesting is the live-fire path.** "I think my answer should be right"
  writes the contest to the record *and* returns the question to the flagged
  queue with the reason attached. That is the hook the earlier build left as a
  field; the grammar app is where it belongs, so it is now wired.
- **Every miss is classified**, not just counted. The `miss_reasons` table
  answers questions like "how many students this week said they matched the
  ending instead of the gender" with a single query.
- **Context** defaults to `practice`. A proctored session is launched by handing
  out a link carrying `?context=quiz` (or `homework`/`classwork`/`exam`), so
  practice data and proctored data stay distinguishable. Students never pick it.

**Teaching text** renders on the feedback screen when a question has it. All 213
questions currently have `teaching: ""` — that text is written and approved
separately, so the slot is there and empty by design.

## Teaching text

`teaching.yaml` holds an explanation for every one of the 118 Unit 0–1 nodes.
Each entry has three parts, per the exemplar file's `teaching_text` rule:

- **explain** — what the student needs to understand, ~45 words, phone-readable.
- **examples** — worked examples, drawn from the Unit 0–1 core vocabulary
  wherever possible; anything from outside is glossed on the spot.
- **when_wrong** — what to say after a miss, aimed at the specific error the
  what-went-wrong menu records.

**Everything is `status: draft` and every entry is drafted, not approved.** The
app shows a student the explanation for a node *only* when the teacher has
approved that node's exact current wording, at `/teaching`. Two consequences:

- Draft text is invisible to students. Nothing student-facing ships unread.
- The approval stores a fingerprint of the wording that was signed off. **Reword
  an approved entry in `teaching.yaml` and it reverts to draft** — edited text
  cannot inherit an old approval. The node shows as "edited since approval"
  until it is read again.

Approvals live in the app's SQLite store. The text lives in `teaching.yaml`, and
neither app ever writes to it: to reword something, edit the file and reload.

## Proctored quizzes

Practice gives feedback instantly, which is the point of practice and fatal in a
quiz. A quiz is therefore a genuinely different mode, not a tag on the same one:

- **You hand-pick the questions** from the approved bank, in order. The set is
  **frozen** on the quiz, so every student sits the same paper and re-importing
  the bank later cannot change a quiz someone has already taken.
- **No feedback until submit.** Nothing is graded, no answers revealed, no
  teaching text, no what-went-wrong menu, while the quiz is open.
- **Close is accepted silently.** A one-letter typo can't re-prompt without
  being a free hint, so it is accepted at the time and surfaces on the review
  screen as `close` — logged as close, never promoted to right, never punished
  as wrong. (The short-answer rule still applies: on a 3-character answer there
  is no such thing as close.)
- **Work saves as you go**, graded only at submit, so a dead phone or a closed
  tab loses nothing. A student can go back, change answers, and resume mid-quiz;
  one attempt per student per quiz.
- **A check-before-submit screen** lists which questions are still blank and
  jumps back to any of them. Submitting locks the attempt.
- **Then the review**: every question, what they wrote, right/close/wrong/blank,
  the correct answer, the approved teaching text on anything missed, and the
  what-went-wrong menu on wrong answers — which is a better moment for that menu
  than practice mode, since they are looking back at the whole paper.
- **Events are written at submit**, one per question, carrying the quiz's
  `context` (quiz/exam/classwork/homework) so proctored work sits in the same
  history as practice and is told apart by that field. A blank answer is
  recorded as wrong: leaving it blank is an outcome, not missing data.

Still no grading. The summary shows counts, never a percentage, and the app
never calls anything a score.

## How progress is remembered

**One table is the memory: `events`, in `data/review.sqlite`.** Every attempt in
every mode appends one row and nothing is ever updated or deleted.

**Nothing about a student's state is stored — it is all recomputed from that
history.** Which Leitner box a word is in, when it is next due, whether it counts
as solid/shaky/not-yet: each is derived by replaying the events for that word.
That is deliberate. It means you can change the definition of "solid" in
November and it applies correctly to work done in September; had the box number
been stored, changing the rule would have corrupted the past.

So the spaced repetition survives the year for exactly as long as the events do.
There is no separate state to lose or to fall out of sync.

**To see the work: the dashboard at `/teacher`.** `QUERIES.md` still holds the
verified SQL, but you should not need it day to day.

### Two honest limits

1. **Out of the box it only runs while your laptop is running, on your
   network.** Spaced repetition wants near-daily practice, and students cannot
   practise at home against a laptop that is closed. **`DEPLOY.md` is how you
   lift this** — about twenty minutes and ~$8/month. Read the first section of
   it before you do: it puts student data on a third-party server, which is a
   school-policy question, not a technical one.

2. **One file, no backup.** The whole year of student history is
   `data/review.sqlite`. Copy it weekly — the command is in `QUERIES.md`. If
   that file is lost, the schedules and the history go with it.

---

## Where the data lives

**On a laptop: one SQLite file** (`data/review.sqlite`). No server to install,
no connection string, copy the file to back it up. That is the right shape for
a laptop and it has not changed.

**Hosted: Postgres.** A web service's local disk does not survive a redeploy,
so on Render the year's practice history would vanish every time the app was
updated. `DATABASE_URL` decides which is in use — Render sets it, a laptop does
not. Nothing about the connection is ever committed.

`db.py` is a thin dialect layer rather than an ORM. The app's SQL is ordinary
and the differences that matter are few, so they live in one readable place:

| SQLite | Postgres |
|---|---|
| `?` | `%s` |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGSERIAL PRIMARY KEY` |
| `REAL` | `DOUBLE PRECISION` — Postgres `REAL` is 4 bytes and would quietly round every timestamp, corrupting every Leitner interval |
| `IS NOT ?` | `IS DISTINCT FROM %s` |
| `MAX(a, b)` | `GREATEST(a, b)` (the two-argument scalar form; the aggregate is left alone) |
| `PRAGMA table_info` | `information_schema` |
| `VACUUM` + WAL checkpoint | `VACUUM FULL` |

The rewriter skips string literals **and `--` comments**. Comments matter as
much as strings: this schema's comments contain apostrophes and semicolons, and
treating either as syntax split statements in the wrong places. That bug
silently dropped every table after the first two, and
`tests/test_postgres.py::test_every_table_in_the_schema_is_created` is what
catches it.

The schema and the name purge run **once at startup**, not per request. Against
a hosted database, doing that per request is eighteen `CREATE IF NOT EXISTS`
statements and a purge scan on every page a student opens.

### Moving a laptop database into the hosted one

    DATABASE_URL=postgresql://... python3 migrate.py data/review.sqlite

One way, once. It **purges names from the source first**, so a name-keyed row
is deleted rather than migrated into the database that was promised to hold
none. It **refuses to run twice** into a database that already has practice
data, because a second run would double every event and corrupt every
spaced-repetition schedule (`--force` if you genuinely mean it).

Verified by migrating a realistic laptop database — 213 questions, 160
decisions, 302 events, 9 students — and checking that counts, roster, approved
items, teaching approvals **and the derived Leitner boxes** come out identical
on the other side.

---

## Who a student is

**An ID number. Nothing else.**

The school committed to leadership that this app holds no student names — no
first name, no last name, no email, no display name. So there is no name field,
not even an empty one, and `tests/test_names_purged.py` fails if anybody adds
one back.

- Students type their ID number to practise. Nothing else is asked.
- The teacher screens show ID numbers. The paper that maps a number to a person
  stays off the machine.
- `identity.py` decides what a well-formed ID looks like: **4 to 10 digits** by
  default. Libertas's actual format was not specified, so override
  `LATIN_ID_PATTERN` with a regex if that is wrong. Leading zeros are
  significant — `04217` is not student `4217`.

This also closes a bug rather than working around it. Identity used to be a
typed name, which meant `Sam` and `Sam T.` were two students with two
spaced-repetition schedules and half a history each, silently. Numbers cannot
collide and nobody has to spell anything twice.

### The typo, which is the one new hazard

A mistyped name looks wrong. A mistyped **number** looks perfectly fine, and
files a student's work under nobody. Three guards:

1. **Format.** Anything not shaped like an ID is refused at the sign-in screen.
   Type a name and you get told it is not an ID.
2. **The class list.** A well-formed number that is not on the list gets a
   *"we don't have that number"* screen — never silent acceptance. The student
   can back out and retype, or confirm it is really theirs.
3. **Visibility.** Anyone who confirms an off-list number is surfaced on the
   dashboard and on the roster page, so a typo becomes a thing you can see and
   fix rather than a hole in the data.

### The class list — `/teacher/roster`

Paste **ID numbers**, one per line, with a block. Paste names and every line
comes back rejected with an explanation; that is the intended answer, not a bug.
IDs can also be loaded from a file via `store.load_student_ids_file()`
(`#` starts a comment).

### The purge

Any database built before this change was keyed on names. On startup the app
**deletes** that data rather than migrating it — the change request said purge,
and a migration would defeat the commitment:

- the roster's `display_name` column is dropped, not blanked;
- every practice row whose `student_id` is not ID-shaped is deleted, along with
  the history attached to it, because there is no way to keep one without the
  other;
- the freed pages are then checkpointed and vacuumed, so the names are gone from
  the **file itself** rather than merely unlinked. (A test greps the raw bytes
  of the database, including the `-wal` sidecar. Querying alone would have
  passed while the names sat there in plain text.)

It runs once, reports what it removed on the dashboard and on stdout, and is a
no-op forever after.

---

## Who can get in

Nothing is gated until you set a secret, so **the laptop workflow is unchanged**:
no password set, no door.

| Environment variable | Effect |
|---|---|
| `LATIN_TEACHER_PASSWORD` | Teacher sign-in guards `/teacher`, `/review`, `/teaching`, `/quiz`. Teacher tools disappear from the landing page for anyone not signed in. |
| `LATIN_CLASS_CODE` | Students type a shared class code once per device to reach `/drill`, `/practice` and quizzes. |
| `LATIN_PUBLIC=1` | Says the app is reachable from outside the LAN. Marks session cookies HTTPS-only, and **refuses to start** if no teacher password is set. |
| `LATIN_ID_PATTERN` | Regex for a valid student ID. Default `^[0-9]{4,10}$`. |
| `DATABASE_URL` | Postgres connection string. Set by Render; unset on a laptop, which then uses the local SQLite file. |
| `SECRET_KEY` | Signs the session cookies. Random per start locally; a deployment must set it or every restart signs everyone out. |

Gating happens in **one** `before_request` in `server.py`, keyed on URL prefix,
and anything unrecognised falls through to teacher-only. A route added later is
closed until someone opens it. `tests/test_auth.py` walks the real URL map and
asserts every route redirects to a door — that test, not a hand-written list, is
what keeps this honest.

---

## What works

All five build steps, verified in order:

1. Answer-checker + 25 tests (every spec-named case).
2. YAML loading + checks; clean on the 75 exemplars (0 error-level).
3. Review tool: import, queue, review, edit round-trip, skip-cycle, resume,
   export — smoke-tested through the HTTP layer.
4. Drill: both directions, close→retype, macron-optional, event logging.
5. Event record + solid/shaky/not-yet, derived from history.
6. Grammar practice: all four formats, taught-date gating, per-box grading, the
   what-went-wrong menu, and the live-fire contest path — driven end to end in a
   browser, not just unit-tested.
7. Teaching text for all 118 nodes, drafted and gated behind teacher approval;
   verified in the running app that draft text does not reach a student and
   approved text does.
8. Teacher dashboard + class list: roster paste-in, who practised over a
   window, what the class is weak on, what they said went wrong, per-student
   detail, CSV export — driven end to end in a browser (a rostered student
   signed in from the picker, practised, and their dashboard row moved from
   "nothing" to "started" with the attempt attached to the roster name).
9. Proctored quizzes: build, sit, resume, change answers, submit, review —
   driven end to end in a browser, including a check that no feedback leaks
   mid-quiz and that a submitted attempt is locked.
10. A door: teacher password, student class code, HTTPS-only cookies when
    deployed, and a refuse-to-start guard for the public-but-passwordless
    case. Rehearsed under gunicorn in a browser — a student took the class
    code, practised, and could not reach the dashboard; the teacher signed in,
    saw that practice land, and signing out closed it again.
11. Continuous review: 213 questions in one pass in teaching order, driven 40
    cards deep in a browser — the node order never regresses, a skip survives
    the rest of the pass, and editing stays in the flow instead of dropping
    you home.
12. Identity as an ID number, with the name purge — verified by a test that
    greps the raw bytes of a database built the old way, `-wal` sidecar
    included, and by driving the three sign-in outcomes in a browser: a typed
    name refused, a mistyped number challenged, a real number through.
13. Undo, edit-instead, session history and the append-only decision log —
    driven in a browser (approve → U → the same question reopens; reject →
    "Edit instead" → the editor with the rejection cancelled; eight decisions →
    history newest-first → tap one → decide it again; a verdict flipped back →
    flagged and listed).
14. Two-database storage: the whole app driven in a browser on real Postgres
    (drill, review, undo, dashboard) plus 27 dialect and live-Postgres tests,
    and a laptop-to-Postgres migration verified row-for-row including derived
    state.
15. Keyboard-only practice (Enter submits, Enter advances) and an always-visible
    progress strip on the drill and practice screens — both driven in a browser.

247 tests pass (12 skip without a Postgres to talk to) (`python3 -m unittest discover -s tests`).

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

- **Closeness is length-scaled, and that was a real bug.** "Within two
  characters" is right for `puella`/`puela` but wrong for short answers: every
  incorrect single letter is one edit from the correct one, so a student who
  wrote `q` where the answer was `w` was told "check your spelling", and `es`
  for `est` was treated as a typo rather than the form confusion the menu
  exists to count. Answers of 3 characters or fewer now require an exact match,
  4–5 allow one edit, 6+ allow two. Found by driving the running app, not by
  the tests.

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

SQLite (`data/review.sqlite`, WAL mode). The roster lives here too, so it
survives restarts but is **not** in the source YAML — back the file up. A few thousand questions and a few
hundred thousand events by June sit inside this comfortably. Delete the file to
reset; the source YAML is never touched. Built for one teacher and ~88 students
at light load, not for heavy concurrency.
