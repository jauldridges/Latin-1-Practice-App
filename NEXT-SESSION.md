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
  ~370 passing (about 14 skip unless a local Postgres is running).
- Never say "mastery" to a student. The words are solid / shaky / not yet.

**How I work.** Make things simple for me — I'd rather not go back to the
terminal. When you give me an update and say what's next, also tell me the step
after that.

**Where things stand.** 294 questions written; I've approved about 211 of them
in the review tool. Units 0-2 morphosyntax are covered. Hosting, backups,
end-of-year purge, PIN login and the teacher dashboard are all built and tested.
120 student IDs are generated and live only in `out/` on my machine — that
folder is gitignored on purpose, and re-running `make_ids.py` would produce
different numbers.

**What I want next**, unless I say otherwise when we start:
1. Deepen Units 0-1 morphosyntax — 35 of those 54 nodes have fewer than three
   questions, so repeat practice hands back the same card.
2. Then Unit 3 morphosyntax (23 nodes, none written yet; it starts Nov 30).

Read `README.md` and `DEPLOY.md` first, then tell me what you found before
changing anything.
