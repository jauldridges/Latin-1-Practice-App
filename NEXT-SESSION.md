# Starting a fresh Claude session on this project

Paste the block below into a new session. Everything else it needs is in the
repo — this file, `README.md`, `DEPLOY.md`, and the tests.

---

Repo: jauldridges/Latin-1-Practice-App, work on branch `main` unless I say otherwise.

**What this is.** A Latin I practice app for my ~89 students at Libertas Academy
(Blocks 3/4/5/7, FY27). Flask + Jinja + YAML, SQLite on my laptop and Postgres
when hosted on Render. Students practise vocabulary and morphosyntax with
Leitner spacing; I have a review tool for approving questions and a teacher
dashboard for who's practising and what they don't know.

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
  ~384 passing (about 14 skip unless a local Postgres is running).
- Never say "mastery" to a student. The words are solid / shaky / not yet.

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
1. Unit 3 morphosyntax (23 nodes, none written yet; it starts Nov 30).
2. Approve the 40 new Units 0-1 questions in the review tool — that is my job,
   not the session's, but nothing reaches a student until it is done.
3. Questions for MW-089 (Unit 1, taught 22 Sep) and MW-090 (Unit 2, 21 Oct).
   Both were added to the spec in September and neither has any.

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
