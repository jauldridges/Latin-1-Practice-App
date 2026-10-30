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
| `vocab.yaml` | The drill's words **with glosses**: the 80 Unit 0–1 core words, then each week's new words (see the caveat below). |
| `teaching.yaml` | Teaching text for all 120 Unit 0–1 nodes. **Drafted, awaiting approval.** |
| `templates/`, `static/` | Mobile-first UI. |
| `make_slips.py` | Printable slips to hand out, and the paper ID-to-name record. |
| `rush.py` | The three "rushed" rules, sittings, and the dashboard flag. |
| `magister.py`, `magister.yaml` | The cartoon Magister and his lines (teacher-approved). |
| `lessons.py`, `badge_lessons.yaml` | The lesson at the start of each badge (teacher-approved). |
| `badges.py`, `badges.yaml` | Grammar badges: the map, checks, fading, and the homework rule. |
| `analysis.py` | Data for analysis: the zip of spreadsheets split around an exam. |
| `dates.py` | How every date a person reads is written: "Friday October 30". |
| `nle.py`, `nle/`, `static/nle/` | Past National Latin Exams: 15 exams, pre-approved, in badge checks and Practice NLE. |
| `tests/` | 781 tests. `python3 -m unittest discover -s tests`. |
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

Running the current generated bank (334 items): **0 error-level flags**, 14
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

- The 80 Unit 0–1 core words, then each week's new words from its class packet:
  Week 8 (week of Monday October 12: -ve, the one new word it names; its word
  table is filled in in class), Week 9 (October 19: the 16 words of Vocabulary
  Parts A–B, deus and dea as two), and Week 10 (October 26: the 16 words of
  Parts A–C, the dative week) — 114 words, both directions, **typed** (no multiple choice), checked by
  the shared module. Macrons never required. A new week needs its words in
  `vocab.yaml`, its Monday in `drill.py` (`WEEK_ORDER`, `_WEEK_MONDAY`), its
  forms in `dataio.py`'s lists, and a hint sentence each in `vocab-examples.yaml`
  (tests check all four).
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
  fixed choices, which are appended and never written per item.

- **"I don't know" is not one of them any more.** The exemplar file lists it
  first of three fixed choices, and a week with a real class was enough: it was
  most of the answers. That is not a diagnosis, and sitting at the top of the
  list it crowded out the reasons that are. Taking it out is a deliberate
  deviation from the spec, made on evidence.

  What went in alongside matters more than what came out. In practice the menu
  *replaces* the Next button — a wrong answer cannot be left behind without
  answering it — so every remaining choice is a claim about why you were wrong.
  A student who genuinely has no idea would have been cornered into inventing
  one, which puts a sentence in your "what they say went wrong" table that
  nobody meant, or into "I think my answer should be right", which pulls a
  sound question out of circulation and into the flagged queue. So the screen
  carries a quiet link — *None of these — next question* — that is deliberately
  less inviting than the reasons and records nothing at all. An empty answer is
  better evidence than one nobody meant. (In a quiz review the menu sits behind
  a fold and can simply be ignored, so only the practice screen needs this.)
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

## What a student sees

Audited in September 2026 by driving the app as a signed-in student at phone
(390px) and Chromebook (1366px) widths, with a teacher password set so the
screens were the ones students actually get. Two findings were bugs, not looks:

- **The feedback screen printed the wrong letter.** Options are shuffled per
  student, but after a wrong answer the screen labelled the right answer with
  the file's key — so a student who saw *nauta* as option **d** was told the
  answer was **a**, an option they had never been shown as correct. It now uses
  the same per-student letters as the question, and marks *your answer* and
  *right answer* in words as well.
- **Some hints gave the answer away.** Teaching text is written per node and is
  used twice: as a hint before answering and as an explanation after. Its
  worked examples are often the very sentences the questions use — the MS-014
  hint read *"Nauta puellam spectat — nauta is nominative"* on the question
  *"In Nauta puellam spectat, which word is the subject?"*. The hint now leaves
  out any example that repeats three or more words of the question or contains
  its answer. The explanation after answering still shows every example, and
  the approved wording itself is untouched — this filters one moment rather
  than editing the text.

And the rest, which is about reading and finding your way:

- **Three tabs on every student screen** — Vocabulary, Grammar, My progress —
  with the student's number and *sign out* on the right of the header. Before,
  the only way between the drill and grammar was the "Latin I" wordmark.
- **No spec codes.** "MS-014" means nothing to a fourteen-year-old; the topic
  label stays, and the topic list no longer leads with codes.
- **Two equal choices on the landing page.** Vocabulary was green and Grammar
  grey, which said one mattered less.
- **Options:** single Latin words stay in italics, English sentences do not
  (every option used to be italic, including *"There is no subject."*); bigger
  tap targets; the chosen option highlights.
- **Feedback:** after a right answer the explanation folds behind *Why is that
  right?* so the next question is one tap away; after a wrong one, the line
  aimed at the mistake comes first and the worked examples fold away, so the
  required *What happened?* menu is not buried below a wall of text.
- **My progress covers grammar too.** Below the words, every topic from class so
  far, grouped by the week it was taught, each marked solid / shaky / not yet
  and each with a **Practice** button that goes straight to questions on that
  one topic. It counts over the same topics the bar on every question counts,
  so a student never sees two different answers, and a test holds them equal.
- **My progress** folds each week to one line of counts, with only the current
  week open. It was about 5,200 pixels tall on a phone; it is now about 2,000.
  The Leitner *Box* column is gone from the student's view.
- **No teacher language on student screens** — "113 approved question(s) are
  waiting on lessons not yet taught" is a teacher's fact, not a student's.

Teacher screens are unchanged. `tests/test_student_ux.py` holds all of this,
and the letter test was checked by putting the old template back: it fails
naming the letter the student saw and the letter the old screen printed.

## Goals & deadlines, and homework

Teacher dashboard → **Goals & deadlines** (`/teacher/deadlines`) sets three
things, all of which show up on students' screens.

**The weekly homework goal** is two numbers — vocabulary cards and grammar
cards — 50 and 50 unless changed. A **homework week runs Saturday to Friday**,
because the quiz is on Friday; a week is done when both numbers are met. A
retype after a near-miss counts once (the same rule as the stats bar), **each
card counts at most once a day** (a word in either direction is one card), and
answers in a proctored quiz or exam don't count (`teacher.homework_cards`). The
once-a-day rule came from a student who answered a two-question topic 101 times;
it applies to past weeks too. A card already counted today says so on screen
("extra practice"), and a single topic whose questions are all done until
tomorrow stops with "That's everything in this topic for today" and offers a
mix instead of looping. Nothing is stored: every count is read
from the event history, so changing the goal mid-year re-reads every week.

**On time, late, not done.** A week met by Friday night is *on time* (green ✓,
full credit). A week can be finished afterwards and is then *late* (yellow,
partial credit). Which week a card goes to:

1. a card counts for its own week while that week is short of the goal;
2. once its own week is met, it finishes the **oldest** unfinished earlier week,
   same kind (extra vocabulary never pays for missing grammar).

The current week comes first on purpose: the other way round, one missed week
would make every later week late forever for a student doing exactly the
homework. **Homework weeks** on the same page sets the first week (it defaults
to Sat 26 Sep 2026, when this went live) and lets any week be marked as
no-homework (a vacation): nobody owes it, and cards done in it finish an older
week.

**What students see.** The home screen shows *This week's homework · due
Friday*, two bars, seven day-dots (Saturday first), and — if a week is owed —
a yellow note saying which one and how to finish it. A spacing line is always
there; it turns into an amber flag after more than two days without practice.
The **Homework** tab (`/homework`) shows all-time cards, days practiced and
weeks on time / late / not done, then every week newest first.

**What the teacher sees.** *Who practiced* now defaults to **this homework week**
(or *last homework week*), and **Did it** means the weekly goal met, counted
exactly as the student's home screen counts it — it used to mean 20 answers in a
rolling seven days. **Homework, week by week** (`/teacher/homework`) is the
gradebook grid: one row per rostered student, one column per week (named by its
Friday), ✓ / *late* / the number of cards done; it downloads as a spreadsheet
("on time", "late", "not done (62/100)"). Each student's page lists their weeks too.

**Quizzes and tests** each have a title, a kind (quiz / test / exam), one date
for everyone, and the teaching weeks they cover. Ticking weeks brings in every
word introduced those weeks and every grammar topic taught those weeks; Roman
world, modern world and reading topics start unticked, and any topic can be
unticked. A student's home screen lists the next four under **Coming up**, and
each opens a page (`/due/<id>`) with *right on your last try* as the big number,
solid / shaky / not yet under it (solid needs a week, so it cannot move in four
days; the page says so), every topic and word, and **Practice these topics** /
**Practice these words** buttons restricted to exactly that scope and to what has
been taught.

**The clock is the school's.** `schooltime.py` sets the process time zone to
America/New_York (override with `LATIN_TIMEZONE`). Render runs in UTC, where
Friday ends at 8pm in Massachusetts; without this a Friday-evening finish would
count late. Stored timestamps are unaffected.

Tables `settings` and `assessments` hold all this; both are in the backup and the
migration, neither is student data, and the end-of-year purge leaves them.
`goals.py` holds the logic, `tests/test_goals.py` the tests.

## Spaced repetition: FSRS, graded by the student

Vocabulary and grammar are scheduled by **FSRS** (`fsrs.py`), which replaced
five Leitner boxes in October 2026. Students saw "shaky" on nearly everything:
"solid" needed a right answer a week after first meeting a word however well it
was known, "shaky" covered everything from one lucky answer to eight in a row,
and one miss threw a word back to the start.

FSRS keeps two numbers per card: **stability** (about how many days until the
chance of remembering drops to 90%) and **difficulty**. It is the published
FSRS-5 algorithm with its standard weights, written out in `fsrs.py` rather than
installed. A card is a word (both directions together) or a grammar question; a
topic's strength replays all its questions' answers as one card.

**Students grade nearly everything themselves.** After every answer they see
the check and the right answer, then four colored buttons: 🔴 **Again**, 🟠 **Hard**,
🟢 **Good**, 🔵 **Easy**, each saying when the card would come back ("5 min",
"3 days", "1 mo"). Keys 1–4 work; Enter takes the suggested grade (outlined: Good
for right, Again for wrong). A wrong typed answer says "Only a spelling slip?
Grade it by how well you knew it" — the teacher's call, because spelling makes
the app's own check unreliable and judging your own recall is worth practicing.
On a miss, "What happened?" is an optional pick that goes with the grade.
**Drag-and-drop questions are graded by the app** (right → Good, wrong → Again).
The Reader keeps its own I had it / Partly / I missed it and is not scheduled.

The answer is recorded **when it is graded** (`/drill/grade`, `/practice/grade`),
re-checked on the server, with the grade in the new `events.rating` column
(1–4; 0 for a typo retyped on the spot; NULL for older answers and app-graded
ones, read from `result`: right → Good, wrong → Again). `result` is always the
app's own check, so the dashboard, accuracy and homework counts are unchanged.
Nothing is stored about a card: September's answers replayed into stabilities on
the first day, so nobody lost progress.

**Scheduling** (`fsrs.pick`): due cards first, most likely forgotten first; then
new ones in teaching order; then, with nothing left for today, extra practice on
the weakest, so the 50 + 50 can always be reached. Never the card just answered
while another is left. Again comes back in 5 minutes.

**What students see.** solid / shaky / not yet stay, now read from stability:
*not yet* never got it, *solid* holds three weeks or more, *shaky* in between.
Every word and topic on My Progress has a strength bar that grows ("holds 9
days"); the session bar counts "↑ N stronger" (cards remembered this sitting);
the home screen and the Vocabulary and Grammar pages show how many are **due
today**. `tests/test_fsrs.py`, `tests/test_drill.py`.

## Grammar badges

The Grammar tab is a **tree of badges** (`badges.yaml`, `badges.py`): each a
group of spec topics, drawn as a circle, with lines taken from the spec's
prereqs (shortcut lines removed: `badges.direct_foundations`) and rows by how
deep a badge sits (`badges.levels`). Tap a circle -- or point to it with a
mouse -- for its description: complete sentences, "This badge covers ...",
written for a student who missed the lesson (tested). A ring around each
earned circle shrinks as the badge fades; a red dot marks this week's to-dos.
A badge appears the day its first topic is taught (greyed and dashed before).
**Earning** it is a 6-question check across its topics (5 right); once earned it
**fades** on the same memory model as every card (`fsrs.py`, run on the badge
itself: pass = Good, not passed = Again), and a 3-question **refresh** (2 right)
keeps it. A first pass holds about 3 days, then about 10, a month, and so on.
"Right" is the app's own check (right or close); only a question the app can't
check uses the student's grade. Questions are picked across topics, least
recently seen first, so a retake asks different ones where the badge has them.

**Hints.** A grammar question's Hint is never just the date: it shows the
topic's teaching text once the teacher approves it (`teaching.yaml`, now with
all Unit 2 topics drafted; a test checks every topic with questions has
text), and until then the badge lesson's line to remember. Either way it ends
with "Look back at Lesson N" (a new tab, so a check under way is kept). The
teacher's Grammar badges page shows "hints 3/5" per badge with links to read
and approve. `tests/test_hints.py`.

**Lessons.** Each badge opens with a short lesson (`badge_lessons.yaml`,
`lessons.py`), numbered in teaching order ("Lesson 5 of 20"): a few steps shown
one at a time -- the idea in two or three sentences, a worked example that
animates (each Latin word lights up and its label drops in, then the English),
an endings table whose rows appear one by one, a one-tap quick check answered
on the page (never recorded), and one line to remember -- then "Start the
check". The not-yet circles on the map show their lesson number; a passed
badge offers "Next: Lesson 6". Refreshes skip the lesson, but "Read lesson 5
again" is always there. Lessons need the teacher's approval (Teacher dashboard
-> Grammar badges -> Badge lessons; fingerprint under `lesson:<id>`); without
one, a badge starts at its check. The teacher reviews at
`/teacher/lessons/<id>`: the lesson plays as students see it under a bar
with Previous / Approve & next / Skip / Show every step, and below it the
checks for understanding -- the lesson's quick check with its answer, and
every approved question the badge check can ask, with answers. Approve & next
goes to the next lesson not yet approved; "Start reviewing" on the list picks
up where the teacher left off. Examples use only class vocabulary.
`tests/test_lessons.py`.

A finished check is one event (`badge:<id>`, context `badge`, score in
`response`); the questions inside it are ordinary practice events. The record
is left out of card counts, accuracy, rushing and the session bar.

**Homework.** Goals & deadlines -> Grammar badges switches it on from a
homework week: the Grammar tab becomes the map, and from that week the homework
is the vocabulary cards **and every badge up to date** -- each badge on the map
by Friday earned, and refreshed if it was fading (passed during the week, or
not needing a refresh at the deadline). Grammar cards stop counting from that
week (they still make up older unfinished card weeks); earlier weeks keep the
50 + 50 rule. A badge passed after Friday finishes the week late. The home
card, Homework tab, dashboard ("Badges 4/6"), homework grid and CSV, and the
student page (a badge table) all show it. Teacher dashboard -> Grammar badges
lists each badge's topics and approved-question count. The old topic list is
still at `/practice?topics=1` ("Extra practice by topic").

The grouping is a DRAFT for the teacher (Oct 2026): every Unit 0-2 grammar
topic is in exactly one badge (tested). `tests/test_badges.py`.

**How to study** is badge and Lesson 1, and not grammar: its topics are two
study-skills spec nodes, SK-001 (how memory works: spaced practice, forgetting,
honest grades) and SK-002 (the Lēgēs Magistrī). The lesson explains spaced
practice with a worked example taken from the real scheduler (Day 1 → 3 days →
11 days → solid by Day 15; a test replays it through `fsrs.py`), sums up the
laws in a Do / Don't table, and ends with a quick check; the badge check then
asks 6 of its 17 questions (`latin1-items-unit00-study.yaml`), five right to
earn it. Once badges are on it is homework like any badge, so every student
earns it first.

The lesson review screen (Badge lessons → a lesson) lists a badge's questions
still waiting for approval — in the review queue or in a bank file not yet
imported — under its approved ones, with **Approve these N questions**; a
flagged or rejected question is left to the Review tool.

## Dates

Every date a person reads is written “Friday October 30” — weekday, month, day,
with the year only where it's needed (`dates.py`; homework weeks are “Saturday
October 24 – Friday October 30”, vocabulary weeks “Week of Monday September
14”). Spreadsheet and backup files keep `2026-10-30` for the programs that read
them. `tests/test_dates.py`.

## Student mode

**Try it as a student** (Teacher dashboard, and the home screen's teacher
buttons) signs the teacher's browser in as the demo student `0000000`: seven
digits, so it can never be a real student's ID, and never on the class list.
Every page then looks exactly as it does to a student, under a bar that says
so, with **Start over** (deletes everything the demo student did) and **Back to
teacher view**. The demo student is left out of every whole-class read — the
dashboard, homework grid, misses, quiz and practice-NLE lists, and Data for
analysis. `tests/test_student_mode.py`.

## Practice NLE

Fifteen past National Latin Exams, transcribed from the PDFs into `nle/*.yaml`
(one per exam; pictures and maps in `static/nle/`): Latin I 2014, 2016,
2018–2020; Beginning Latin 2021–2026; the 2025 and 2026 Reading Comprehension
exams; Introduction to Latin 2013 and 2015 — 592 questions. Used with the NLE's
permission for non-commercial classroom practice. No answer keys came with the
PDFs, so the answers were worked out by hand; Teacher dashboard → **Practice
NLE** → an exam shows each question with the answer the app counts right and
its topic, to check against the key.

Every question carries the course topic it tests (`node`: a spec node, or
`VOCAB` for a word's meaning), plus any other topic it leans on (`needs`: a
dative question written with *senātōrī* needs the third declension). The words
the exam underlines are underlined (`underline`).

- **Pre-approved.** At startup `nle.sync()` copies the questions into the bank
  as approved, the first time each appears. After that the bank is the truth:
  reject one in the Review tool and it stays rejected; edit one and the edit
  survives the next deploy.
- **In badge checks and topic practice**, a grammar question joins its badge's
  pool once its topic and everything in `needs` has been taught, and every
  badge check (earn or refresh) asks at least one when the badge has any, labelled
  “From the 2019 National Latin Exam”, options in the printed A–D order. A
  question that needs its reading passage or picture (`exam_only`) appears only
  in Practice NLE.
- **Practice NLE** (the NLE tab, `/nle`): a whole past exam as printed
  (questions on things not covered yet are marked), or a mash-up — 20 single
  questions from several years on what has been covered, or 40 ending with one
  reading passage; questions a student hasn't met in a practice NLE come first.
  Answers save as they go; nothing is graded until the student finishes, as on
  the real exam. The results give the score (and the award a 40-question score
  would earn), what to work on by topic, and every question with the right
  answer. Each miss has a Hint (the approved teaching text, else the lesson's
  line to remember, plus the passage lines a reading question points to) and,
  when the topic's badge has an approved lesson, **Do Lesson N** — the lesson
  opens with “← Back to your practice NLE”, which returns to that question.
- A sitting is stored as a quiz (context `nle`) with the student's one attempt,
  so it is backed up and wiped at year end like any quiz, and only the student
  who started it can open it. Answers are recorded as events with context
  `nle`: they never count as homework, and Data for analysis files them with
  the quizzes. The teacher's Quizzes list leaves them out.

`tests/test_nle.py`.

## Data for analysis

Teacher dashboard → **Data for analysis** downloads one zip: `students.csv`
(one row per student), `sittings.csv`, `skills_by_student.csv`, `answers.csv`
(every answer), `in_app_quizzes.csv`, `skill_list.csv`, and a `README.txt` that
defines every column. Pick a quiz/test from Goals & deadlines (or type a date)
and every row is marked before / exam day / after, with what the test covered
marked `on_exam`. Student IDs only; what students typed is left out. Time is an
estimate from the gaps between answers, each capped at five minutes.
`tests/test_analysis.py`.

## Looping

`teacher.loops` flags a day when a student answered, ten or more times, cards
in one topic (a grammar topic, or vocabulary) that they had already got right
that day -- the pattern of a student filling the 50 + 50 from a two-question
topic. A card missed and relearned is not a repeat. The dashboard shows
"⟳ looped MW-017 ×38" next to the student, and their page has a "⟳ Looping"
table. The repeats already don't count (each card counts once a day); the flag
is so the teacher can talk to the student. `tests/test_once_a_day.py`.

## Rushing

`rush.py` marks a single answer **rushed** for any of three reasons, stored
in `events.rush` (the grade-button timer is `events.grade_ms`). A right answer
is never rushed.

| Reason | When |
|---|---|
| **looked_away** | wrong or blank, and a grade button pressed under 1.5 s after the answer appeared |
| **graded_up** | Good or Easy on a blank, on a typed answer less than half like the real one (bad spelling of the right word passes), or on a wrong multiple-choice pick |
| **guessed** | wrong, and answered faster than reading allows: 1.5 s for vocabulary, 2.5 s for grammar, 1 s per box on drag-and-drop |

A **sitting** (answers with no gap over 30 minutes) is flagged on the dashboard
when it has 10+ cards and a third or more were rushed: "⚑ 14 of 20 rushed",
with the sitting card by card on the student's page. Three rushed in a row
brings the Magister's slow-down message on the card screen.

Goals & deadlines → **Rushed cards** decides whether rushed cards count toward
the weekly 50 + 50 (default: they count, and are only flagged). The rules apply
to answers from the day this shipped; older answers carry no verdict.
`tests/test_rush.py`.

## The Magister

The Magister -- a student's pencil caricature of the teacher, cleaned up
(`static/magister.png`; the student's signature was left off, since the app
carries no student names) -- on the student home screen says one line per visit, rotating through Expectations, How to study,
The science of memory and Why Latin; each student hears every approved line
before any repeats. Slow-down messages are a fifth group, shown only after
three rushed cards in a row (with a built-in default if none is approved).

He says **only approved lines**: same fingerprint rule as teaching text, under
`magister:` keys. Teacher dashboard → **The Magister** approves, withdraws,
edits (saves and approves) and adds the teacher's own lines; `magister.yaml` is
never written. Notes marked "for you" are teacher-only — rules-07/rules-08 and
slowdown-02/slowdown-06 are pairs that say opposite things about whether
rushed cards count, so approve the one that matches the switch.
`tests/test_magister.py`.

### Lēgēs Magistrī

The app's laws, as two more groups of Magister lines: `leges-how` (how to use
the app for homework and studying) and `leges-dont` (what not to do). The
approved ones are numbered I, II, III … — every how-to law first, then every
don't — and listed together at `/leges` (the "Lēgēs Magistrī" link under the
home screen; the teacher can open it too, with a count of laws still waiting).
They join the home-screen rotation, and when the Magister says one it comes
with its number, "Lēx IX — …", and a link to it on the page. A law takes its
number when approved, so withdrawing one renumbers the rest. Sixteen are
drafted in `magister.yaml` (lex-how-04, on badges, waits for badges to be
switched on). They overlap the older Expectations lines on purpose: approve
the laws and withdraw whichever Expectations lines now say the same thing.

## Label the words (tap-to-place)

`format: label-words` shows a whole Latin sentence with an empty box above each
word and a bank of labels below. A student taps a label and then a box (or a
box and then a label), or drags a label onto a box. Tapping is the main way in
because HTML drag-and-drop is clumsy on a Chromebook trackpad and absent on a
phone; every control is a button, so the keyboard works too. Tapping a filled
box empties it.

```yaml
format: label-words
stem: "Label each word with its case and its job. Then write the English."
sentence:                       # in order; a word with no answer gets no box
  - {latin: "Fēmina", answer: "nominative · subject"}
  - {latin: "aquam",  answer: "accusative · direct object"}   # or a list of accepted labels
  - {latin: "portat.", answer: "verb"}
bank: ["nominative · subject", "nominative · predicate", "accusative · direct object",
       "vocative · direct address", "verb"]
translation_model_answer: "The woman carries the water."      # optional, not graded
replaces: MS015-TRANS-01                                       # optional
```

**The teacher's rules for these.** This is the format for case-and-job
morphosyntax questions from now on. Labels are *case · job*. A verb is just
**verb** unless the question is about the verb's own form (a test holds this).
Banks offer only cases taught by the question's week.

**Why it can't be done by elimination.** Labels are reusable (two words can both
be "nominative · subject"), and every bank must hold at least one label the
sentence doesn't use. Check 9 in `checks.py` refuses an item whose answer isn't
in its bank, whose bank has no spare label, or that has fewer than two boxes.

**Grading.** Right only if every box is right; there is no *close*, since nothing
is typed. Feedback redraws the sentence with each box green or red and the right
label under a red one, then the usual *What happened?* menu. The English, when
the question has one, is written after labeling and compared with the model,
not graded. The same widget runs in proctored quizzes (no warning about empty
boxes there) and in the review tool, which shows the sentence with the answers in
place and the bank.

**Two kinds of bank.** Case and job, as above; or the English for each word as it
works in this sentence ("the girls", "of the sailor"), which tests how a case is
translated and becomes most useful from the genitive on.

**Replacing a question.** A new question can name one it `replaces`. The old one
stays approved, keeps its history, and stops being served the moment the new one
is approved (`store.approved_items`) — never before, so there is no gap. The
duplicate-question check ignores such a pair. The six typed "label each word"
questions are replaced this way (`latin1-items-unit01-labels.yaml`).
`tests/test_label_words.py`.

## Games

The teacher's own games, hosted elsewhere, listed under **Games** on the student
home screen. The list is `games.yaml`: a `title` (the link text) and a `url`
(must start with `https://`) per game, plus an optional one-line `about`. A
game without a title or with a non-https address is left out rather than shown.
Links open in a new tab so the practice app is still open when the game ends.
`tests/test_games.py`.

## Reader

Class stories, one YAML file each in `readings/` (format in `readings.py`),
named by packet week (`08-cincinnatus.yaml`, `09a-dei-primi.yaml` ...) so they
list in teaching order; the URL comes from the `slug` inside, not the file name.
Week 9: three stories from the story packet (the first gods; Jupiter's
children; Ceres and Proserpina). That packet had no question pages, so their
questions are the app's own until the teacher sends the packet's.
Week 10: four stories (Cornelia; Cornelia and her sons; the patricians and the
plebeians; the Gracchi). Each has the class packet's five Stretch questions
(`p1`–`p5`, written answers with a model) among the app's own quick checks
(`q…`), and its Core sentences (`core: true`) show their number in a red box,
as in the packet: translate every Core sentence in the class packet.
Every word on screen is a button: tap it and its gloss pops up right beside it
(below the word, or above it near the bottom of the screen), with an arrow
pointing at the word; tapping anywhere else or Escape closes it. A bar at the
bottom of the screen was tried first and was too easy to miss. The words the
teacher underlined in her packet are underlined on screen and glossed exactly as
the packet glosses them, grammar label included ("king · Direct Object,
accusative"); every other word has a short gloss too ("has — from habeō"), so
nothing on the page is a dead end. A phrase the packet glosses as one unit
("in perīculō", "populus Italicus") is one tap.

English multiple-choice questions (CR-009) sit beside the story, in story
order, so students answer as they read: on a Chromebook or wider they fill a
column to the right that stays on screen and scrolls by itself, grouped by
sentences; on a phone each group follows the paragraph it asks about
(`readings.questions_by_paragraph`; `static/reader.js` moves the groups).
Options shuffle per student like every other multiple-choice question.

**Two kinds of question.** Multiple choice (`options` + `answer`), and written
answers (`model`): the student writes in English, presses Check, sees the model
answer (only once they have written something), and marks *I had it* / *Partly*
/ *I missed it*, recorded as right / close / wrong with what they wrote. The
teacher's Reader page lists every student's latest written answer to each
question, word for word, with how they said it went. *Fābula dē Cincinnātō*
carries the Week 8 packet's nine questions in the packet's wording (p1–p9, five
of them written) and eight of the app's own multiple-choice warm-ups beside them.

**Each question has its own Check button**, answered in place without leaving
the page (`/read/<slug>/check`), with a running "N of 10 questions right". A
miss shows **See hint**, which lights up the Latin that answers the question and
scrolls to it. Each question's `hint` names those words (sentence number →
words, punctuation ignored); the file check refuses a hint that isn't in the
story. Without JavaScript the same button posts the form and checks that one
question. Every check is recorded with context `reading` and node CR-009, and is
**not** a homework card (`teacher.NOT_HOMEWORK`); the teacher's results show each
student's latest answer to each question.

**Teacher dashboard → Reader** (`/teacher/reader`): Preview, Publish to students /
Unpublish, any problem with the file (an unglossed word, a gloss for a word that
isn't there, an answer that isn't an option), and each student's latest answer to
each question. Students see a story only once it is published; the teacher can
always open it, and the **AA** button makes the text big enough for a projector.
A teacher checking answers sees the result and nothing is recorded.

The first story is *Fābula dē Cincinnātō* (Week 8 packet, page 9). Three changes
from the packet, listed at the top of the file: the title's case after *dē*, and
the glosses for *prohibēre* and *nōminat*, which the packet glosses as *prohibet*
and *creat*. `tests/test_reader.py`.

## Vocabulary hints

A student asked: "what if you give me the word in an example Latin sentence?"
`vocab-examples.yaml` holds one sentence per drill word, the word marked
`*like this*`. The week-of-Aug-24 phrases (Latin used in English) get an English
sentence that uses the phrase. Every Latin sentence uses only the 80 drill words
and only the grammar taught by the end of September (nominative, accusative,
vocative, present, *sum*, agreement, imperatives, *dēbeō* + infinitive).

| Card | The hint shows |
|---|---|
| Latin → English | the sentence with the word in **bold**, and no English, which would be the answer |
| English → Latin | the sentence with the word **blanked out**, plus its English |
| after answering | the sentence and its English, either way |

Nothing reaches a student until the teacher approves it at **Teacher dashboard →
Vocabulary hints** (`/teacher/vocab-hints`): Approve, Withdraw, Edit (which saves
and approves) per word, or Approve all. Approval is a fingerprint of the exact
wording, kept in the teaching-text tables under a `vocabhint:` key, so a reworded
sentence goes back to unapproved; the teaching-text pages never see these keys.
`vocabhints.py`, `tests/test_vocab_hints.py` (including that a blanked sentence
never shows the word elsewhere, and that every Latin word is on the list).

## Word audio

**Record the vocabulary** (teacher dashboard, or the landing page, `/teacher/audio`)
lists every drill word by week. Record, say the word, Stop: it saves, plays back,
and moves focus to the next word's Record button, so Enter / say it / Enter goes
down the list without the mouse. Re-recording replaces a take; ✕ deletes one.

The page builds a **16-bit mono WAV at 22 kHz** in the browser from the
microphone's samples rather than using the browser's own recorder, because WAV
plays everywhere and the compressed formats Chrome records do not play on every
student's phone. Silence at either end is trimmed and the peak evened out to the
same loudness. A word is ~30–50 KB. (It uses ScriptProcessorNode, which Chrome
calls deprecated and still supports everywhere; AudioWorklet would need a
separate script file for no gain here.)

Recordings live in the `word_audio` table as base64 text (the two databases
disagree about binary columns, and backups are JSON), keyed like the drill keys
words, so a recording follows its word. The table is in the backup and the
migration and is not student data: the year-end purge leaves it.

Students get a 🔊 button on the Latin → English card, on the answer screen, on
My progress and on a quiz page's word list — and **never on the English → Latin
card, where it would be the answer**. Words with no recording have no button.
`/audio/<word>` is open to a signed-in student or the teacher and nobody else,
and its URL carries the recording's version so phones cache it for good and
fetch a new take when there is one. Saving accepts only a WAV (checked by its
header), only for a real drill word, only up to 1.5 MB. `tests/test_audio.py`.

## Teaching text

`teaching.yaml` holds an explanation for every one of the 120 Unit 0–1 nodes.
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

### Approving it where you are already reading

A question and the explanation a student gets when they miss it are one
decision, so the review screen carries both. Under every question is its node's
teaching text with its own state — *not yet approved*, *approved teaching
text*, or *edited since approval* — an **Approve teaching text** button, and an
**Edit teaching text** link. Approving returns you to the question rather than
to the teaching section, because reviewing is a flow and the point is not to
interrupt it. Splitting the two across separate screens is why the second half
went undone for a month.

**Rewording happens in the app, and the edit goes in the database.** The file
is still never written to. That is not tidiness: a hosted service's disk does
not survive a redeploy, so an edit written to `teaching.yaml` would vanish the
next time the app was updated — silently, and in favour of wording the teacher
had already replaced. A row in `teaching_overrides` overrides the file for one
node; `teaching.yaml` keeps the original, and *Back to the file's wording*
restores it.

Saving an edit always clears that node's approval, whichever door the text came
in by. The fingerprint covers the exact words and new words have not been read
yet, so a reword takes the node off students until it is approved again.

**Approve all** exists on `/teaching`, folded away behind a summary. It skips
the reading the per-node screen is for, which is why it is neither the default
nor hidden: a teacher who wrote the course can legitimately say they have read
the lot. It is their click, and any node can still be withdrawn afterwards.

Approvals live in the app's store, and so do any rewordings — both travel with
a backup and a migration, because an edit a backup does not carry is an edit
the teacher loses.

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
   practice at home against a laptop that is closed. **`DEPLOY.md` is how you
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

- Students type their ID number to practice. Nothing else is asked.
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

### Handing the numbers out — `make_slips.py`

    python3 make_slips.py

Reads `out/student-ids.txt` and writes two printable pages beside it:

- **`out/slips.html`** — one slip per student, twelve to a page with cut lines.
  Each carries the address, the number in large type, and the one instruction
  that matters: choose a four-digit PIN the first time and use the same one
  after that. A slip carries no name, so one dropped in a corridor identifies
  nobody.
- **`out/id-record.html`** — the same numbers in the same order, numbered to
  match the slips, with **blank columns for the name and the block**.

The record sheet is blank by design and there is no version of it that is not.
The app holds a number and nothing else that identifies a person, which means
the link between a number and a child exists in exactly one place: paper, in a
classroom. So the generator prints numbers and leaves names to handwriting, and
`tests/test_make_slips.py` asserts that a name in the source file is refused
rather than helpfully printed.

Both files land in `out/`, which is gitignored, for the same reason the ID list
is: publishing every valid ID would leave only the PIN.

It reads a plain list of numbers, and also the dashboard's own CSV export, whose
first column is the student id:

    python3 make_slips.py ~/Downloads/practice-2026-09-15.csv

**Both sheets are laid out to a height budget**, not to fill the paper. US
Letter is the shorter page, so it sets the limit: 259mm of printable area
inside 10mm margins, and the sheets use about 220mm of it. The first print run
did fill the page exactly, and the result was the last row of slips printing on
a page of its own — fatal for a sheet you are going to cut up — while the
record sheet took nine physical pages to print five logical ones with every
label still reading "of 5". The leftover millimetres absorb a printer's
unprintable edge and a "Default" margin that is not 10mm.
`tests/test_make_slips.py` asserts the budget and that the constants really
drive the CSS, so the numbers are a constraint rather than a comment.

That matters once the roster is loaded. From then on the **hosted class list is
the authoritative copy** of the numbers and `out/student-ids.txt` is only the
first draft of it — so if the local file is ever lost, the app hands the list
back rather than the numbers being gone. **Re-running `make_ids.py` at that
point is the wrong move**: it issues 120 different numbers, and slips printed
from them would name students the roster has never heard of.

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

Four digits, deliberately. The PIN's job is to stop one student practicing as
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
more than the PIN does. `?student=40218` used to be enough to practice as
somebody else, and a PIN at the door means nothing while every screen behind it
takes your word for it. Student ids no longer appear in URLs at all, and
`tests/test_pins.py::TestIdentityComesFromTheSession` asserts it.

The shared class code is **gone**. It let anyone who knew it practice as anyone,
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
7. Teaching text for all 120 nodes, drafted and gated behind teacher approval;
   verified in the running app that draft text does not reach a student and
   approved text does.
8. Teacher dashboard + class list: roster paste-in, who practiced over a
   window, what the class is weak on, what they said went wrong, per-student
   detail, CSV export — driven end to end in a browser (a rostered student
   signed in from the picker, practiced, and their dashboard row moved from
   "nothing" to "started" with the attempt attached to the roster name).
9. Proctored quizzes: build, sit, resume, change answers, submit, review —
   driven end to end in a browser, including a check that no feedback leaks
   mid-quiz and that a submitted attempt is locked.
10. A door: teacher password, HTTPS-only cookies when
    deployed, and a refuse-to-start guard for the public-but-passwordless
    case. Rehearsed under gunicorn in a browser — a student took the class
    code, practiced, and could not reach the dashboard; the teacher signed in,
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

781 tests pass (14 skip without a Postgres to talk to) (`python3 -m unittest discover -s tests`).

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

### The option order a student sees

Every choice item in the bank is written with its answer as option `a`. That is
the authoring convention and it stays: a reviewer reading the YAML should see
the answer without hunting for it.

For a while the templates then rendered the options in that order, which meant
the right answer was always the first thing on the screen, in practice and in a
proctored quiz alike. A student who tapped the top option every time scored full
marks on every multiple-choice question in the course without reading any Latin
— and the dashboard would then have reported the class as solid on things they
could not do, which is worse than the marks, because that is the data you teach
from next week.

The order now moves at render time. `practice.display_options` returns the
options in an order derived from the student's ID and the question's ID, and
relabels them a/b/c/d down the page. Two things it deliberately does not do:

- **It never changes what the browser posts back.** The submit value is still
  the item's own key, so grading, saved quiz answers, the event record and the
  review tool all keep working on the letters the YAML uses. Only the order and
  the printed label move, which is why this was a safe change to make mid-course
  with student history already in the database.
- **It never uses `random`.** The order comes from a SHA-256 of the seed, so it
  is identical on every machine and every Python version. A quiz review screen
  has to show a student the same lettering they answered under, days later and
  possibly after a redeploy.

Per student, so no two students can compare positions. Per question, so nobody
learns "the answer is second for me" and applies it to the next one. Stable for
that pair for ever, so a refresh does not reshuffle.

**The review tool is not shuffled**, on purpose: a teacher approving a question
needs to see it as written, answer first.

`tests/test_option_order.py` measures the property over the real bank rather
than trusting the function — for five students across all 214 choice items, no
screen position holds the answer more than about a quarter of the time — and
drives a served question through the running app. Reverting either template
fails it.

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
- **The fixed what-went-wrong menu is two choices, not three.** `"I don't know"`
  was removed after the app met a class; see the grammar-practice section for
  what replaced it and why the menu still cannot corner a student.

## Storage & reset

SQLite (`data/review.sqlite`, WAL mode). The roster lives here too, so it
survives restarts but is **not** in the source YAML — back the file up. A few thousand questions and a few
hundred thousand events by June sit inside this comfortably. Delete the file to
reset; the source YAML is never touched. Built for one teacher and ~88 students
at light load, not for heavy concurrency.
