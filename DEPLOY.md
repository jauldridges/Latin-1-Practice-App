# Putting it on Render, so kids can practise at home

Devices are 1:1 and go home. That is the whole point of this change: practice
that only happens while your laptop is open and the student is on school wifi is
practice that mostly does not happen.

**About twenty minutes, and $13/month.**

| Piece | Plan | Cost |
|---|---|---|
| Workspace | Hobby | $0 |
| Web service | Starter — 0.5 CPU, 512 MB | $7/mo |
| Postgres | Basic — 0.1 CPU, 256 MB, 1 GB | $6/mo |

---

## Before the twenty minutes: two things that are not mine to decide

**1. The data-privacy question.** You would be putting student practice records
on a third-party server. Many districts require a signed data-privacy agreement
with any vendor holding student data. Ask whoever handles ed-tech approvals at
Libertas. **This is the step people skip and regret.**

What is actually in there is deliberately boring: **ID numbers**, what students
typed as answers, and when. No names, no emails, no addresses, no grades — see
the identity section of the README. The paper that maps an ID number to a person
stays off the machine. That does not make the question go away, but it is the
answer to most of it.

**2. The content filter — ask your IT contact NOW, before students hear about
the app.** The school's filter has to allow the app's domain on student
Chromebooks **at home**, not just on the school network. This is not my part and
I cannot test it, but it will break everything if it is wrong, and it breaks
*silently and completely*: a blocked domain shows a student a generic error, and
you will hear "it doesn't work" with no way to tell that from a bug. Send your
IT contact the URL as soon as Render gives it to you, and confirm before you
announce the app.

---

## The twenty minutes

**1. Make a Render account** at [render.com](https://render.com) and connect
this GitHub repository.

**2. Render reads `render.yaml`** and offers to create a **Blueprint** — a web
service *and* a Postgres database. Say yes. It wires the database connection
string into the app for you; you never see or paste it.

**3. It will ask you for two values.** These are the only things you type:

   - **`LATIN_TEACHER_PASSWORD`** — pick something real. It is the only thing
     between the internet and every student's practice record.
   - **`LATIN_ID_PATTERN`** — *leave this blank.* The default already matches
     the numbers `make_ids.py` generated for you. It exists only in case you
     ever switch to a different ID scheme.

   Render generates `SECRET_KEY` itself. You do not touch it.

**4. Deploy.** You get a URL like `latin1.onrender.com`. First boot creates the
database tables automatically.

**5. Send that URL to your IT contact** for the content filter (see above).

**6. Open the URL, sign in with your teacher password**, and go to
**Class list**. Paste your **ID numbers** from `student-ids.txt`, one per line,
one block at a time.
Nothing works properly until this exists — it is both the dashboard's
denominator and the guard against a mistyped number.

**7. Move your existing data across, if you want to keep it.** Optional. If your
laptop has review decisions and practice you care about:

   - In Render, open your web service → **Shell**.
   - You will need the laptop file. Easiest route: from **your laptop**, run
     `python3 migrate.py` pointed at the hosted database — Render shows the
     external connection string under your database → **Connect** → *External*:

         DATABASE_URL='paste-the-external-url-here' python3 migrate.py data/review.sqlite

   It refuses to run twice, and it deletes name-keyed rows from the laptop copy
   before copying rather than carrying them across.

**8. Give the students the URL.** They sign in with their own ID number and
choose a four-digit PIN the first time. Tell them to add it to their phone's
home screen — it behaves like an app from there.

**9. Set yourself a monthly reminder** to open **Backup & end of year** and
download a backup. Render's plan keeps three days of recovery; a problem you
notice in June cannot be fixed from a three-day window.

---

## When the deploy fails

**"Exited with status 127".** That is the shell saying *command not found*: Render
ran `gunicorn ...` and there was no gunicorn installed. The start command and the
dependency list in this repo are both correct — `requirements-hosted.txt` lists
gunicorn and psycopg on top of the laptop requirements — so a 127 means the build
step that ran was **not** the one in `render.yaml`.

Almost always that is because the service was created with **New → Web Service**
instead of **New → Blueprint**. A hand-made Python service ignores `render.yaml`
and uses Render's own default build, `pip install -r requirements.txt`, which
installs Flask and PyYAML and deliberately not gunicorn. Then there is nothing to
start.

To confirm: open the service → **Logs**, and read the build section. If it says
`pip install -r requirements.txt`, with no `-hosted`, that is the whole story.

**Fix it by deleting the service and creating it again from the Blueprint** — not
by editing the build command. Editing the build command makes it boot, and leaves
three things wrong that are much harder to notice than a crash:

- **No database.** The Blueprint creates the Postgres and injects `DATABASE_URL`.
  Without it the app falls back to a SQLite file on the service's own disk, which
  does not survive a redeploy — the year's practice history would vanish the next
  time you pushed a change, silently.
- **No `LATIN_PUBLIC=1`**, which is what marks cookies HTTPS-only and what makes
  the app refuse to start with no teacher password.
- **No `LATIN_TEACHER_PASSWORD` and no generated `SECRET_KEY`.** With the previous
  point, that means the teacher dashboard, the review tool and every student's
  record on a public URL with no door on it.

Deleting costs nothing before you have migrated any data. Do it early.

**A build that fails instead of a start that fails** looks different: you get an
error inside the build log itself, and the usual cause is the psycopg wheel or a
wrong **Root Directory** (which makes `requirements-hosted.txt` not found). Check
the Root Directory is empty — this repo has no subdirectory.

---

## What is guarded, and what is not

**The review tool and the teaching-approval screen require the teacher
password.** A student who guesses `/review` or `/teacher` gets the login screen
and nothing else — no data, no hint. Gating is one check in `server.py` keyed on
URL prefix, and anything unrecognised defaults to teacher-only, so a page added
later is closed until someone opens it. A test walks the app's real URL map and
asserts every route redirects to a door.

**Students sign in with an ID number and a PIN they choose.** The PIN stops one
student practising as another. It is four digits and it is not a password —
nothing behind it is a grade — and it would not stop someone determined. You
clear a forgotten one from the roster.

**HTTPS only.** Render terminates TLS; the app redirects any plain HTTP request
and sets HSTS for a year, so a student who once reached it over HTTPS cannot be
downgraded on school wifi.

**Nothing sensitive is committed or logged.** No password, no connection string.
Logs carry paths and status codes; database errors log the exception *type*, not
the message, because a psycopg message can carry a host and a user name.

---

## Will 512 MB and half a CPU hold 25 students at once?

**I expect so, and here is the honest basis for that.** The app is IO-bound: one
short database round trip per page, server-rendered HTML, no build step, no
background work. Driven locally against a real Postgres it served 25 concurrent
drill sessions in 0.26 s and 20 dashboard loads in 0.48 s. That was without
network latency between app and database, so treat it as a lower bound.

The one CPU-heavy thing is the PIN hash (PBKDF2, ~140 ms here, probably ~300 ms
on half a CPU). That happens **once per device per year**, not per page — so the
worst case is the first lesson where a whole class signs in at once, and eight
threads absorb that.

**If it does turn out to be too small, I will say so rather than quietly sizing
up**, because the next tier is $25/mo and that is not what was approved. The
first thing to try instead is a connection pool — the app currently opens a
fresh database connection per request, which is simple and robust but pays a
handshake every time. That is a code change, not a bigger invoice.

---

## Running locally after all this

Unchanged. `start.command` still works and still uses the local SQLite file — no
`DATABASE_URL`, no Postgres. With no `LATIN_TEACHER_PASSWORD` the teacher tools
are ungated, exactly as before. Students always sign in.

To rehearse the deployed behaviour on your laptop:

    LATIN_TEACHER_PASSWORD=test python3 run.py

---

## Restoring a backup

The backup is one JSON file and it restores into **either** database — the
hosted Postgres or a laptop's SQLite. That is deliberate: a backup that only
loads back into Render is a backup that depends on Render existing.

    python3 -c "import json, store, backup; \
      conn = store.connect('data/restored.sqlite'); store.init_db(conn); \
      backup.restore(conn, json.load(open('latin1-backup-2027-01-15.json')))"

It refuses to load into a database that already holds practice data unless you
pass `replace=True`, because a half-restore that doubles every event is worse
than no restore.

Tested, not assumed: `tests/test_backup.py` takes a backup from Postgres,
restores it into SQLite, and compares the **derived Leitner boxes** — not just
row counts. A backup that kept every row but lost the timestamps would pass a
count check and silently reset every student's schedule.
