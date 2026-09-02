# Putting it online, so kids can practise at home

Right now the app runs on your laptop. That means practice only happens while
your laptop is open and the student is on the school network — which is the one
thing that breaks spaced repetition, because spacing wants near-daily practice
and most days are not school days.

This is what it takes to lift that. About twenty minutes and roughly $8/month.

---

## Read this part first

**The app now has a door.** It did not before. Anyone with the URL would have
been able to open the teacher dashboard and read all ~88 students' records.
Two things guard it:

| | Who | What they get |
|---|---|---|
| **Teacher password** | you | dashboard, review tool, quizzes, teaching text |
| **Class code** | your students | the drill, grammar practice, quizzes they sit |

Both are remembered on the device for a year, so it is one entry per phone, not
one per session.

**The app refuses to start** if you tell it it is public but leave the teacher
password empty. That is deliberate: the alternative is a deployment that
silently serves student records to the internet.

**What you should still check before doing this**, because they are your calls
and not mine:

1. **School policy.** You would be putting student practice records on a
   third-party server. Many districts require a signed data-privacy agreement
   (a DPA) with any vendor holding student data. Ask whoever handles ed-tech
   approvals at Libertas. This is the step people skip and regret.
2. **What is actually in the data.** ID numbers, what they typed as answers,
   and when. **No names** — see the identity section of the README. No emails,
   no addresses, no grades. The paper that maps an ID number to a person stays
   off the machine, which is what makes this data comparatively boring if it
   ever leaked.
3. **The class code is a shared secret, not a login.** A student who knows a
   classmate's ID number can practise as them. Nothing here is a grade, so the
   damage is a polluted practice schedule, not a stolen mark. Per-student PINs
   are the fix and are specified in the hosting change request.

---

## The twenty minutes

**1. Push the repo to GitHub.** Already done.

**2. Make a Render account** at render.com and connect that repo.

**3. Render reads `render.yaml`** and offers to create the service. Say yes.
It sets everything except the two secrets.

**4. Type the two secrets** when it asks:
   - `LATIN_TEACHER_PASSWORD` — pick something real; it is the only thing
     between the internet and every student's record.
   - `LATIN_CLASS_CODE` — something a fourteen-year-old can type from memory.
     `libertas-latin` is better than `Xk92!q`.

**5. Deploy.** You get a URL like `latin1.onrender.com`.

**6. Open it, sign in, paste your class list** at `/teacher/roster` — one name
per line, one block at a time. Nothing else works properly until this exists.

**7. Give the students the URL and the class code.** Tell them to add it to
their home screen; it behaves like an app from there.

### Cost

Render's **Starter** plan is $7/month, plus about $0.25/month for the 1 GB
disk. The free plan will not work: it sleeps after inactivity *and* it has no
persistent disk, which means the entire year of practice history is deleted on
every deploy. Do not use the free plan for this.

Fly.io is a fine alternative at a similar price if you prefer it; the same two
requirements hold — a **persistent volume** for `LATIN_DB`, and `LATIN_PUBLIC=1`
with a password set.

---

## The one thing that can lose the year

`LATIN_DB` **must** point at the mounted disk (`/data/review.sqlite`).
`render.yaml` already does this. If it ever points anywhere else, the file
lives in the container's temporary filesystem and every deploy silently starts
the year over.

**Back it up monthly.** From the Render shell:

    sqlite3 /data/review.sqlite ".backup /tmp/backup.sqlite"

then download it. Five minutes, once a month, against losing 88 students' Leitner
schedules.

---

## Running locally after all this

Unchanged. `start.command` still works, and with no `LATIN_TEACHER_PASSWORD`
and no `LATIN_CLASS_CODE` set, nothing is gated — same as before. The door only
appears when you set the secrets.

To rehearse the deployed behaviour on your laptop:

    LATIN_TEACHER_PASSWORD=test LATIN_CLASS_CODE=abc python3 run.py
