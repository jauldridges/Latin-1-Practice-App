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

It pulls the latest version first, then starts. It prints the branch and commit
it is running, because "Already up to date" on the wrong branch sounds like
success and starts the old app. If there are uncommitted local changes it leaves
them alone and starts what is on disk rather than clobbering your work.

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
| `tests/` | 370 tests. `python3 -m unittest discover -s tests`. |
| `latin1-*.yaml` | The source files — spec, exemplars, and the question banks (never modified by the apps). |
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
### Telling a student when they met a thing

Every vocabulary word carries the week it was introduced, and every grammar
node carries one in the spec. The same sentence — "Introduced Week of Sep 14" —
is built from both by the `weeklabel` filter, so a student cannot tell the two
halves of the app store it differently.

It appears in three places, and the difference between them is deliberate:

- **The feedback screen**, after they answer. Free orientation, no cost.
- **A Hint, on the question itself.** Collapsed by default and opened on
  purpose — a hint a student chooses to take is a different thing from one the
  page hands them. On a grammar question it also carries the teaching note,
  through the same approval gate as the after-a-miss explanation, so nothing
  unread reaches a student. On a **vocabulary** card it carries the week only:
  a drill word has no spec node and therefore no teaching text, and inventing
  one would mean telling the student what the word means, which is the answer
  rather than a hint.
- **`/drill/progress`, grouped by week.** The most useful of the three. A flat
  list of eighty words tells a student they have work to do; the same list
  under week headings tells them *where*, and "shaky on the week of Sep 14" is
  something a fourteen-year-old can act on tonight.

Taking a hint is **not recorded**. It could be — "who needed a hint" is a real
question — but every consumer of the event log (session counts, readiness,
Leitner boxes, dashboard accuracy) would have to learn to ignore a new kind of
row first, and that is a change to every student's schedule in service of a
feature nobody asked for yet.

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

Running the current generated bank (331 items): **0 error-level flags**, 14
heuristic flags (10 explain-reason, 4 vocabulary — two of which, `Rōmānus` and
`Salvē`, are real off-list words already marked `needs_review`). That flag count
has not moved since the bank was 213 items: Unit 2 and the Unit 0–1 third
questions each added zero.

### Three questions per node, and why the third one is a different shape

Repeat practice is only practice if the second visit is a different question.
Selection serves unseen items first, so a node holding one question hands the
same card back for ever, and a node holding two runs out on the third visit.
Every Units 0–1 and Unit 2 morphosyntax node now carries at least three.

The Units 0–1 third questions are in their own file,
`latin1-items-unit01-more.yaml`, rather than added to a bank whose every item
already carries a review decision. The loader reads every
`latin1-items-unit*.yaml`, so nothing in the code knows the difference.

Ten of those nodes had stopped short **on purpose**, and the original bank said
so in its own `review.fewer_items_written` section: the eight cells of the noun
tables would turn into paradigm recitation, and a single-fact node would only
restate itself. That argument was against a third *drill*, not a third
*question*. So no item in that file repeats a shape its node already has — where
a node had a parse and a produce, the third is a discrimination across four
different nouns, or a production cued by English meaning rather than by a
paradigm slot, or an error to diagnose. Each item's `note` names the shape it
adds and why the node needed it, so the next person to touch the bank can tell a
considered third question from padding.

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
- IDs are **issued by this project**, not taken from the school's system —
  `make_ids.py` generates them and the teacher keeps the paper that says which
  number went to whom. So the format is a choice rather than a constraint:
  **six digits, never starting with zero**. Override `LATIN_ID_PATTERN` if you
  ever need to accept another scheme.

### Why the numbers look the way they do

`make_ids.py` makes four decisions, and the last one is the interesting one.

**Six digits, fixed length.** A typo that drops or doubles a digit is refused at
the sign-in screen instead of becoming a mystery "we don't have that number".

**Never a leading zero.** This list ends up in a spreadsheet eventually, and
spreadsheets eat leading zeros silently — `042173` becoming `42173` would
quietly unperson a student.

**Random, not sequential.** Sequential ids let a student reach a classmate's
account by adding one, and the PIN is the only other thing in the way.

**No two ids within one typo of each other.** 120 numbers scattered through
900,000 already makes a collision unlikely; at this size "unlikely" is free to
turn into "never", so the generator enforces it — no issued id can be reached
from another by changing one digit or swapping two neighbours. Those are the
two mistakes people actually make. The verified result for the current set:
a single-digit typo lands on another student in **0** ways and on nothing in
**6,879**. `tests/test_make_ids.py` checks the property exhaustively rather than
statistically.

The generated list is **never committed**. Sign-in is ID + PIN, so publishing
every valid ID in a public repository would leave only the PIN.

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
| — | Students sign in with an ID number and a PIN. Unlike the teacher password that gate is always on: there is no environment variable to turn it off. |
| `LATIN_PUBLIC=1` | Says the app is reachable from outside the LAN. Marks session cookies HTTPS-only, and **refuses to start** if no teacher password is set. |
| `LATIN_ID_PATTERN` | Regex for a valid student ID. Default `^[1-9][0-9]{5}$` — six digits, no leading zero, matching what `make_ids.py` issues. |
| `DATABASE_URL` | Postgres connection string. Set by Render; unset on a laptop, which then uses the local SQLite file. |
| `SECRET_KEY` | Signs the session cookies. Random per start locally; a deployment must set it or every restart signs everyone out. |

Gating happens in **one** `before_request` in `server.py`, keyed on URL prefix,
and anything unrecognised falls through to teacher-only. A route added later is
closed until someone opens it. `tests/test_auth.py` walks the real URL map and
asserts every route redirects to a door — that test, not a hand-written list, is
what keeps this honest.

### The students' door: ID + PIN

A student types their ID number, then a **four-digit PIN they choose the first
time**. Two screens rather than one form, because the second depends on the
first: a first-timer is *choosing* a PIN and a returning student is *entering*
one, and explaining that distinction on a single screen is explaining it to
nobody.

Four digits, deliberately. The PIN's job is to stop one student practising as
another — nothing behind it is a grade — and the failure mode that actually
kills home practice is a fourteen-year-old locked out at 9pm. **A forgotten PIN
is cleared by the teacher**, from the roster page or the student's page. That is
all of password recovery here and it is enough: there are no email addresses in
this system, and the person who can confirm a student is who they say they are
is standing in front of them.

PINs are stored hashed — PBKDF2-SHA256, per-student salt, 200,000 rounds, and
the stored round count is honoured on verify so it can be raised later without
locking anyone out. No iteration count makes 10,000 possibilities safe against
someone determined; what the salt buys is that the table is not a plain lookup.

**Identity comes from the signed session, never from the request.** That matters
more than the PIN does. `?student=40218` used to be enough to practise as
somebody else, and a PIN at the door means nothing while every screen behind it
takes your word for it. Student ids no longer appear in URLs at all, and
`tests/test_pins.py::TestIdentityComesFromTheSession` asserts it.

The shared class code is **gone**. It let anyone who knew it practise as anyone,
which is precisely what the PIN exists to prevent.

---

## Backups, and the end of the year

**`/teacher/data`** — one page, no terminal.

**Backup** downloads the whole database as a single JSON file. JSON rather than
`pg_dump` output for one reason: it restores into **either** database. A backup
that only loads back into Render is a backup that depends on Render existing.
Render's plan keeps three days of point-in-time recovery, and a problem noticed
in June cannot be fixed from a three-day window — **download one monthly and
keep it somewhere that is not Render.**

**End of year** exports everything and then deletes all student practice data:
events, miss reasons, quiz attempts, PINs, roster. The question bank and your
review decisions stay, because next year's class needs the questions and must
not inherit a single row of anyone's history.

Two things about that button:

- It is confirmed by **typing the year**, not by an "are you sure". A
  confirmation you can dismiss by reflex is not a confirmation, and this one is
  not reversible.
- **The backup is the response.** There is no way to run the purge without also
  receiving the file, because losing a year of history to a purge-without-
  download is exactly the failure it exists to prevent.

Restoring refuses to load into a database that already holds practice data
unless you pass `replace=True` — a half-restore that doubles every event is
worse than no restore.

**Tested, not assumed.** `tests/test_backup.py` round-trips Postgres → SQLite
and SQLite → Postgres and compares the **derived Leitner boxes**, not row
counts: a backup that kept every row but lost the timestamps would pass a count
check and silently reset every student's schedule.

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
10. A door: teacher password, HTTPS-only cookies when
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
15. Student sign-in: the whole journey driven in a browser on Postgres — a
    name refused, an unknown number challenged, a PIN chosen, a mistyped
    confirmation caught, sign out, the wrong PIN refused, the right one
    accepted, and a teacher reset sending them back to "choose a PIN".
16. Backup and end-of-year: a real backup taken through the web UI from a
    Postgres holding a migrated year (213 questions, 301 events, 9 students),
    restored into an empty SQLite, and compared — counts, roster, approvals,
    readiness and Leitner boxes all identical.
17. Deployment: run under gunicorn on Postgres exactly as `render.yaml`
    specifies, and the change request's three confirmations performed rather
    than asserted — every teacher URL redirects to the login and leaks nothing;
    no name, and no column named `*name*`, exists anywhere in the hosted
    database (checked against a `pg_dump`); the backup restores.
18. Keyboard-only practice (Enter submits, Enter advances) and an always-visible
    progress strip on the drill and practice screens — both driven in a browser.

370 tests pass (14 skip without a Postgres to talk to) (`python3 -m unittest discover -s tests`).

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

- **Every multiple-choice answer is option `a`, and nothing shuffles.** All 212
  choice items in the bank were written with the correct answer first, and the
  templates render `item.options` in the order the YAML lists them. So in
  practice *and* in a proctored quiz, the right answer is always the first one on
  screen: a student who taps the top option every time scores full marks on every
  multiple-choice question in the course without reading the Latin. Nothing in
  the tests catches it, because nothing is wrong with any individual question.
  The fix belongs in rendering — a per-student shuffle, seeded so a refresh does
  not reshuffle — not in rewriting 212 answer keys, which would fix the bank and
  leave the next batch of questions to reintroduce it. **Not yet done.**

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
