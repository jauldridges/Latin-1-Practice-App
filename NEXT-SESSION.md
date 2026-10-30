# Starting a fresh Claude session on this project

Paste the block below into a new session. Everything else it needs is in the
repo — this file, `README.md`, `DEPLOY.md`, and the tests.

---

Repo: jauldridges/Latin-1-Practice-App, work on branch `main` unless I say otherwise.

**What this is.** A Latin I practice app for my ~89 students at Libertas Academy
(Blocks 3/4/5/7, FY27). Flask + Jinja + YAML, SQLite on my laptop and Postgres
when hosted on Render. Students practice vocabulary and morphosyntax with
Leitner spacing; I have a review tool for approving questions and a teacher
dashboard for who's practicing and what they don't know.

**Rules that don't change.**
- The app stores a **student ID number and nothing else** that identifies a
  person. No names, no emails, no display names. This is a privacy commitment
  made with school leadership. Never add a name field back, never derive one.
- Student sign-in is ID + a self-chosen 4-digit PIN, hashed. Teacher resets it.
- The review tool and teaching-approval screens need the teacher password from
  an environment variable. A student who finds the URL gets nothing.
- Python 3.9-compatible, no build step, mobile-first server-rendered HTML.
  It has to work on a school Chromebook at home when I'm not there.
- Run the full test suite before you tell me something's done. It should be
  ~781 passing (about 14 skip unless a local Postgres is running).
- Never say "mastery" to a student. The words are solid / shaky / not yet.
- American spelling: "practice" for noun and verb, never the British -ise form (a test enforces it).
- School time zone is Eastern (Massachusetts); `schooltime.py` sets it.
- Dates are written "Friday October 30" everywhere a person reads one
  (`dates.py`); spreadsheets and backups keep 2026-10-30.

**How I work.** Make things simple for me — I'd rather not go back to the
terminal. When you give me an update and say what's next, also tell me the step
after that.

**Where things stand.** 334 questions written; I've approved about 211 of them
in the review tool, so the newest 40 are waiting in the queue. Units 0-2
morphosyntax are covered, and every one of the 55 Units 0-1 morphosyntax nodes
now carries at least three questions, MS-159 included. Hosting, backups, end-of-year purge, PIN login and the
teacher dashboard are all built and tested. 120 student IDs are generated and
live only in `out/` on my machine — that folder is gitignored on purpose, and
re-running `make_ids.py` would produce different numbers.

**What I want next**, unless I say otherwise when we start:
1. A separate **Translation** tab using passages tagged with spec nodes. The
   **Reader** is built (README, "Reader"): one YAML file per story in
   `readings/`, every word glossed, my packet's underlined words glossed my
   way; I publish each story at Teacher dashboard -> Reader. New stories come
   from my class packets.
   (Built already, see README: Goals & deadlines, the Saturday-to-Friday
   homework week with on time / late / not done, the Homework tab, and the
   gradebook grid at /teacher/homework; and word audio — I record each vocab
   word at /teacher/audio and students get a 🔊 button; and vocabulary hints —
   each word in an example sentence, in vocab-examples.yaml. New words each
   week need a sentence there, using only words and grammar already taught.)
2. Unit 3 morphosyntax (23 nodes, none written yet; it starts Nov 30).
3. Approve the 40 new Units 0-1 questions in the review tool — that is my job,
   not the session's, but nothing reaches a student until it is done.
4. Questions for MW-089 (Unit 1, taught 22 Sep) and MW-090 (Unit 2, 21 Oct).
   Both were added to the spec in September and neither has any.

**Spaced repetition is FSRS (`fsrs.py`)**, graded by the students themselves
(Again / Hard / Good / Easy) on everything except drag-and-drop. See README,
"Spaced repetition". The grade is in `events.rating`; `result` stays the app's check.

**Rushing (`rush.py`) and the Magister (`magister.py`, `magister.yaml`).** Each
answer gets a rushed verdict (looked away / graded up / guessed) in
`events.rush`; the dashboard flags sittings a third rushed, and Goals &
deadlines decides whether rushed cards count. The cartoon Magister on the home
screen says only lines I've approved at Teacher dashboard -> The Magister. See
README, "Rushing" and "The Magister".

**Grammar practice is badges (`badges.py`, `badges.yaml`)** once I switch them
on at Goals & deadlines: the Grammar tab is a map of badges (groups of spec
topics), each earned with a 6-question check and kept with 3-question
refreshes as it fades. From the switch-over week the homework is 50 vocab cards
plus every badge up to date. New topics need a place in `badges.yaml` (a test
checks every Unit 0-2 grammar topic is in exactly one badge -- extend it to
Unit 3 when those topics are written). Each badge opens with a lesson (`badge_lessons.yaml`): explanation, animated worked
example, quick check, one line to remember; I approve them at Grammar badges ->
Badge lessons. A new badge needs a lesson too (a test checks every badge has one).

**Past National Latin Exams (`nle.py`, `nle/*.yaml`).** 15 past exams (592
questions), pre-approved: grammar ones join badge checks once their topic is
taught ("From the 2019 National Latin Exam"), and students sit whole exams or
mash-ups on the NLE tab, graded at the end, with a hint and the lesson for each
miss (the lesson leads back). Answers were worked out by hand -- I check them at
Teacher dashboard -> Practice NLE. A new exam is a new file in `nle/` in the
same shape (see README, "Practice NLE"); every question needs a `node`. Every
badge check asks at least one NLE question when the badge has one.

**How to study** is badge/Lesson 1 (study-skills nodes SK-001/SK-002, questions
in `latin1-items-unit00-study.yaml`): spaced practice and the laws, then a check.
**Student mode**: Teacher dashboard -> Try it as a student uses demo ID 0000000,
kept out of all class data.

**Lēgēs Magistrī** (`/leges`): the app's numbered laws -- how-to first, then
don'ts -- are Magister lines (categories leges-how / leges-dont in
`magister.yaml`), approved at Teacher dashboard -> The Magister. He quotes them
on the home screen as "Lēx IX — ...".
Next planned: a weekly diagnostic
sentence (translate, check against a model in pieces, plus tap-to-label) that
points to the badges to study, then a class-by-badges grid for me.

**Morphosyntax labeling questions use `format: label-words`** (tap-to-place:
boxes above each word, a bank of *case · job* labels). A verb is just "verb"
unless the question is about verb form. See README, "Label the words".

**Two things a session should know before touching the bank.**
- **Re-import overwrites a question I edited in the review tool.** New questions
  arrive unreviewed and existing approvals survive, but any wording I changed in
  the tool lives only in the database, and "Re-import bank (keeps decisions)"
  puts the file's version back. Before importing a new batch, hit **Export** at
  `/review` and give the session that file to diff against the bank first.
  (Checked on the 8 Sep export: my database was behind the repo on four
  questions and ahead on none, so that import was safe. It will not always be.)
- **Multiple-choice options are shuffled per student at render time**, so the
  answer is not always first. The bank still writes the answer as option `a` —
  that is the authoring convention and it is fine. Don't "fix" the YAML.

Read `README.md` and `DEPLOY.md` first, then tell me what you found before
changing anything.
