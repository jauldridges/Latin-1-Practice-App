"""
One web app, two tools:
  /review  - teacher-facing review tool (Application 1)
  /drill   - student-facing vocabulary drill (Application 2)

Both share answercheck.py. Data lives in a local SQLite file (store.py). Run
locally, open on a phone over the LAN. No accounts, no hosting.

    python run.py           # http://0.0.0.0:5000

The drill routes are added in build step 4; this file grows, it does not fork.
"""

import csv
import datetime
import io
import os
import time
import uuid
import zipfile

import yaml
from flask import (Flask, g, redirect, render_template, request, Response,
                   session, url_for, abort)
from markupsafe import Markup

import analysis
import auth
import backup
import badges
import checks
import dataio
import drill
import fsrs
import identity
import lessons
import practice
import quiz as quizlib
import goals
import magister
import nle
import schooltime  # noqa: F401  -- the school's clock, set before anything reads it
import stats
import store
import teacher
import readings
import rush
import vocabhints
from answercheck import check as check_answer

app = Flask(__name__)
DB_PATH = os.environ.get("LATIN_DB", store.DEFAULT_DB)

# Sessions carry the teacher login and the class code. On a laptop a random
# key per start is fine (it just means logging in again after a restart); a
# deployment must set SECRET_KEY or every restart signs everyone out.
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.permanent_session_lifetime = 60 * 60 * 24 * 365      # once per device, per year
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # HTTPS-only cookie when deployed; off locally, where there is no HTTPS and
    # a Secure cookie would simply never be sent.
    SESSION_COOKIE_SECURE=auth.is_public(),
)

_config_error = auth.check_config()
if _config_error:
    raise SystemExit("REFUSING TO START: " + _config_error)

# Source data is read once at startup. It never changes under the app.
_SPEC = dataio.load_spec()
_EXEMPLARS = dataio.load_exemplars()
_VALID_NODES = set(_SPEC)
_ALLOWED_LATIN = dataio.allowed_latin(_EXEMPLARS)
_NODE_LABEL = {nid: n.get("label", "") for nid, n in _SPEC.items()}
_NODE_LABEL.update(nle.EXTRA_LABELS)
_NLE = nle.load()                      # past National Latin Exams, newest first
_NLE_BY_ID = {e["id"]: e for e in _NLE}
_DRILL_WORDS = dataio.load_drill_words()
_TEACHING = dataio.load_teaching()


# What the name purge removed, the first time it found anything. Kept so the
# dashboard can say it out loud — a privacy commitment that happens silently is
# one nobody can check.
PURGE_REPORT = None


def _prepare_storage():
    """Create the schema and run the name purge — ONCE, at startup.

    This used to run on every request. On a local SQLite file that was merely
    wasteful; against a hosted Postgres it is eighteen CREATE IF NOT EXISTS
    statements and a purge scan on every page a student opens, over the
    network. Doing it at boot is the difference between a class of 25 opening
    the app at once and a class of 25 waiting.
    """
    global PURGE_REPORT
    conn = store.connect(DB_PATH)
    try:
        report = store.init_db(conn)
        synced = nle.sync(conn, _NLE)
        if synced["inserted"] or synced["updated"]:
            print("[nle] past-exam questions: %r" % (synced,), flush=True)
        if report and any(report.get(k) for k in
                          ("roster_rows", "events", "miss_reasons", "quiz_attempts")):
            PURGE_REPORT = report
            print("[purge] removed name-keyed data: %r" % (report,), flush=True)
        print("[storage] %s" % conn.target, flush=True)
    finally:
        conn.close()


def get_db():
    if "db" not in g:
        g.db = store.connect(DB_PATH)
    return g.db


@app.teardown_appcontext
def _close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# --------------------------------------------------------------------------
# The door
#
# Gated by URL prefix in one place rather than by a decorator on each of forty
# routes, because the failure mode of the decorator approach is forgetting one
# — and the one you forget is a leak. Anything unrecognised falls through to
# teacher-only, so a route added later is closed until someone opens it.
# --------------------------------------------------------------------------

OPEN_PREFIXES = ("/static", "/login", "/logout", "/signin", "/signout",
                 "/favicon", "/healthz")
TEACHER_PREFIXES = ("/review", "/teaching", "/teacher", "/quiz")
STUDENT_PREFIXES = ("/drill", "/practice", "/q/", "/due/", "/homework", "/nle")
AUDIO_PREFIX = "/audio/"
# A signed-in student or the teacher: recordings, and Reader passages, which
# the teacher opens to preview and to project in class.
SHARED_PREFIXES = (AUDIO_PREFIX, "/read", "/badges", "/leges")


def _here():
    """The URL to come back to after signing in. `full_path` leaves a bare '?'
    on paths with no query string, which then shows up in the address bar."""
    return request.full_path.rstrip("?")


@app.before_request
def _force_https():
    """Nothing is served over plain HTTP once deployed.

    Render terminates TLS and forwards the original scheme in
    X-Forwarded-Proto. Trusting that header is only safe because the app is
    never reachable except through Render's proxy — which is also why this is
    gated on LATIN_PUBLIC rather than being on everywhere: on a laptop there is
    no HTTPS to redirect to.
    """
    if not auth.is_public():
        return None
    if request.headers.get("X-Forwarded-Proto", "https") == "https":
        return None
    return redirect(request.url.replace("http://", "https://", 1), code=301)


@app.after_request
def _security_headers(resp):
    if auth.is_public():
        # A year of HSTS, so a student who once reached it over HTTPS can never
        # be downgraded on the school wifi.
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


@app.before_request
def _gate():
    path = request.path
    if path == "/" or path.startswith(OPEN_PREFIXES):
        return None
    if path.startswith(SHARED_PREFIXES):
        # The teacher hears her recordings on the recording page and previews
        # passages; students hear and read them. Nobody else.
        if auth.student_ok() or auth.is_teacher():
            return None
        return redirect(url_for("signin", next=_here()))
    if path.startswith(STUDENT_PREFIXES):
        if not auth.student_ok():
            return redirect(url_for("signin", next=_here()))
        return None
    # /review, /teaching, /teacher, /quiz — and anything not listed above.
    if not auth.is_teacher():
        return redirect(url_for("login", next=_here()))
    return None


@app.route("/healthz")
def healthz():
    """Is the app alive AND can it reach its database?

    Render restarts a service whose health check fails. A check that only
    proves Flask is running would keep a service alive that cannot serve a
    single page, so this touches the database — cheaply, one row.
    """
    try:
        get_db().execute("SELECT 1 AS ok").fetchone()
    except Exception as exc:                      # noqa: BLE001
        # The message can carry a host or a user name; the log line is enough.
        print("[healthz] database unreachable: %s" % type(exc).__name__, flush=True)
        return Response("database unreachable\n", status=503, mimetype="text/plain")
    return Response("ok\n", mimetype="text/plain")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not auth.teacher_gate_on():
        return redirect(url_for("index"))
    error = None
    nxt = request.values.get("next") or url_for("teacher_home")
    if request.method == "POST":
        if auth.matches(request.form.get("password"), auth.teacher_password()):
            session.permanent = True
            session[auth.TEACHER_KEY] = True
            return redirect(nxt)
        error = "That is not the password."
    return render_template("login.html", error=error, next=nxt), (200 if not error else 401)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/signin", methods=["GET", "POST"])
def signin():
    """The students' door: an ID number, then a PIN.

    Two steps rather than one form, because the second step depends on the
    first: a student who has never signed in is CHOOSING a PIN, and one who has
    is entering it. Asking for both at once would mean explaining that
    distinction on a screen nobody reads.

    Nothing here is a grade, so the PIN is four digits and there is no email
    recovery — there are no email addresses in this system. A forgotten PIN is
    cleared by the teacher.
    """
    db = get_db()
    nxt = request.values.get("next") or url_for("index")
    sid = identity.normalize(request.values.get("student_id"))
    step = request.form.get("step") or ("pin" if sid else "id")

    # --- step one: the number ---------------------------------------------
    if step == "id" or not sid:
        if request.method == "POST" or request.args.get("student_id"):
            if not identity.is_valid(sid):
                return render_template("signin_id.html", next=nxt, prefill=sid,
                                       id_hint=identity.describe_pattern(),
                                       error="That is not a valid student ID — it should be %s."
                                             % identity.describe_pattern()), 400
            if store.get_student(db, sid) is None and not request.form.get("confirm_unknown"):
                # Never silently accepted: a mistyped number is well-formed and
                # would file a student's work under nobody. Confirming carries
                # them through to the PIN step — without honouring that flag
                # here, "that is my number" looped back to this same screen.
                return render_template("student_unknown.html", student_id=sid,
                                       action=url_for("signin"),
                                       back_url=url_for("signin", next=nxt),
                                       extra={"next": nxt, "step": "id",
                                              "confirm_unknown": "1"})
            return render_template("signin_pin.html", student_id=sid, next=nxt,
                                   setting=not store.has_pin(db, sid), error=None)
        return render_template("signin_id.html", next=nxt, prefill="",
                               id_hint=identity.describe_pattern(), error=None)

    # --- step two: the PIN -------------------------------------------------
    known = store.get_student(db, sid) is not None
    confirmed_unknown = request.form.get("confirm_unknown")
    if not known and not confirmed_unknown:
        return redirect(url_for("signin", next=nxt))

    setting = not store.has_pin(db, sid)
    pin = (request.form.get("pin") or "").strip()
    again = (request.form.get("pin2") or "").strip()

    def fail(msg):
        return render_template("signin_pin.html", student_id=sid, next=nxt,
                               setting=setting, error=msg), 401

    if setting:
        if not identity.is_valid_pin(pin):
            return fail("A PIN is %d digits." % identity.PIN_LENGTH)
        if pin != again:
            return fail("Those two PINs are different. Try again.")
        store.set_pin(db, sid, pin)
    else:
        if not store.check_pin(db, sid, pin):
            return fail("That PIN isn't right. If you've forgotten it, ask your teacher to reset it.")

    session.permanent = True
    session[auth.STUDENT_KEY] = sid
    return redirect(nxt)


@app.route("/signout", methods=["GET", "POST"])
def signout():
    session.pop(auth.STUDENT_KEY, None)
    return redirect(url_for("signin"))


@app.context_processor
def _auth_flags():
    return {"is_teacher": auth.is_teacher(), "teacher_gate": auth.teacher_gate_on(),
            "signed_in_student": current_student(),
            "day_letters": goals.DAY_LETTERS}


_prepare_storage()


@app.template_filter("nodelabel")
def nodelabel(node_id):
    return _NODE_LABEL.get(node_id, "")


@app.template_filter("weeklabel")
def weeklabel(week):
    """"Week of Sep 14", from either shape the data uses.

    The drill's words carry a slug (week_of_sep_14) and the spec's nodes carry
    a date (2026-09-14). Both mean the same thing to a student, so both get the
    same sentence.
    """
    if not week:
        return ""
    w = str(week)
    if w in drill.WEEK_LABELS:
        return drill.WEEK_LABELS[w]
    try:
        d = time.strptime(w, "%Y-%m-%d")
        return "Week of " + time.strftime("%b ", d) + str(d.tm_mday)
    except ValueError:
        return w


def node_week(node_id):
    """When a spec node is introduced. Nodes taught as a module have no day,
    only a week, which is the right answer for them anyway."""
    n = _SPEC.get(node_id) or {}
    return n.get("week")


@app.template_filter("nodeweek")
def nodeweek(node_id):
    return weeklabel(node_week(node_id))


def _audio_versions():
    """{word_key: updated_at}, read once per request and only if a page asks."""
    if "audio_versions" not in g:
        g.audio_versions = store.word_audio_versions(get_db())
    return g.audio_versions


@app.template_global()
def say_url(latin):
    """The URL of the teacher's recording of this word, or None.

    The version in the query string changes when she re-records, so a phone
    that cached the old take fetches the new one."""
    key = drill._key(latin or "")
    v = _audio_versions().get(key)
    if v is None:
        return None
    return url_for("word_audio", key=key, v=int(v))


@app.template_filter("holds")
def holds(days):
    """How long a memory holds: "3 days", "2 wks" (fsrs.describe_days)."""
    return fsrs.describe_days(days or 0)


@app.template_filter("shortday")
def shortday(ts):
    """"Mon 5 Oct" -- the day a late week was finished."""
    if not ts:
        return ""
    lt = time.localtime(ts)
    return "%s %d %s" % (time.strftime("%a", lt), lt.tm_mday, time.strftime("%b", lt))


@app.template_filter("when")
def when(ts):
    """A timestamp as a teacher reads it: "2h ago", "yesterday", a date.
    Exact clock times are noise on a page whose question is 'recently?'."""
    if not ts:
        return "never"
    delta = time.time() - ts
    if delta < 90:
        return "just now"
    if delta < 3600:
        return "%dm ago" % (delta // 60)
    if delta < 6 * 3600:
        return "%dh ago" % (delta // 3600)
    today = time.strftime("%Y-%m-%d")
    day = time.strftime("%Y-%m-%d", time.localtime(ts))
    if day == today:
        return "today, " + time.strftime("%-I:%M%p", time.localtime(ts)).lower()
    if delta < 7 * 86400:
        return time.strftime("%a", time.localtime(ts))
    return time.strftime("%b %-d", time.localtime(ts))


# ==========================================================================
# Landing
# ==========================================================================

def weekly_targets(db):
    t = store.get_setting(db, "weekly_goal") or {}
    return dict(goals.DEFAULT_TARGETS, **{k: int(v) for k, v in t.items()
                                         if k in goals.DEFAULT_TARGETS})


def count_rushed_setting(db):
    """Do rushed cards count toward the weekly goal? Yes until the teacher says."""
    v = store.get_setting(db, "count_rushed")
    return True if v is None else bool(v)


@app.before_request
def _rushed_rule():
    """Every count in this request follows the teacher's switch."""
    if request.path.startswith(("/static", "/healthz", "/audio/")):
        return None
    teacher.COUNT_RUSHED = count_rushed_setting(get_db())
    return None


def homework_setting(db):
    """{"from": first homework week's Saturday, "off": [no-homework weeks]}."""
    s = store.get_setting(db, "homework") or {}
    return {"from": s.get("from") or goals.DEFAULT_HOMEWORK_FROM,
            "off": list(s.get("off") or [])}


_BADGE_ROWS, _BADGES = badges.load()
_BADGE_BY_ID = {b["id"]: b for b in _BADGES}


def badges_from(db):
    """The homework week grammar badges begin (a Saturday, YYYY-MM-DD), or
    None while the teacher hasn't switched them on (Goals & deadlines)."""
    return (store.get_setting(db, "badges") or {}).get("from") or None


def badge_rule(db):
    """What goals.py needs to count badges as the grammar homework, or None.
    Which badges a week asks for is worked out once per deadline per request."""
    frm = badges_from(db)
    if not frm:
        return None
    approved = store.approved_items(db)
    memo = {}

    def required(deadline):
        if deadline not in memo:
            friday = time.strftime("%Y-%m-%d", time.localtime(deadline - 3600))
            memo[deadline] = [b["id"] for b in badges.available(_BADGES, _SPEC, approved, friday)]
        return memo[deadline]
    return {"from": frm, "required": required}


def homework_history(db, events, now=None, rule=None):
    """One student's homework weeks, oldest first, from Goals & deadlines."""
    hs = homework_setting(db)
    weeks = goals.homework_weeks(hs["from"], hs["off"], now)
    return goals.homework_history(events, weekly_targets(db), weeks, now,
                                  badge_rule=rule or badge_rule(db))


def upcoming_assessments(db, limit=4):
    """Quizzes and tests from today onwards, soonest first."""
    today = time.strftime("%Y-%m-%d")
    out = []
    for a in store.list_assessments(db):
        if a["due_date"] >= today:
            a["when"] = goals.when_label(a["due_date"])
            a["days"] = goals.days_until(a["due_date"])
            out.append(a)
    return out[:limit]


def _practiceable(db):
    return {it["node"] for it in store.approved_items(db) if it["node"] in _taught_now()}


def load_games(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "games.yaml")):
    """The Games list on the student home screen, from games.yaml. Only https
    links with a title get through, so a typo can't put a broken or unsafe
    link in front of students."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return []
    out = []
    for gm in doc.get("games") or []:
        title, url = str(gm.get("title") or "").strip(), str(gm.get("url") or "").strip()
        if title and url.startswith("https://"):
            out.append({"title": title, "url": url, "about": str(gm.get("about") or "").strip()})
    return out


_GAMES = load_games()


@app.route("/")
def index():
    db = get_db()
    ctx = {"counts": store.counts(db)}
    student = current_student()
    if student and not auth.is_teacher():
        events = store.events_for_student(db, student)
        rule = badge_rule(db)
        ctx["goal"] = goals.weekly_progress(events, weekly_targets(db), badge_rule=rule)
        ctx["badge_titles"] = {b["id"]: b["title"] for b in _BADGES}
        history = homework_history(db, events, rule=rule)
        # Weeks still owed, oldest first: extra cards finish these (late).
        ctx["owed"] = [r for r in history if r["status"] == "not done"]
        ctx["week_off"] = goals.week_key(time.time()) in homework_setting(db)["off"]
        ctx["spacing"] = goals.spacing_flag(events)
        ctx["idle_days"] = goals.days_since_practice(events)
        ctx["upcoming"] = upcoming_assessments(db)
        ctx["due"] = due_today(db, student, events)
        # A different approved line each time the home screen opens.
        session["mg"] = session.get("mg", -1) + 1
        line = magister_says(db, student, magister.HOME, session["mg"])
        if line and line["category"] in magister.LEGES:
            # A law comes with its number: "Lēx IX — ...", and the way to all of them.
            lex = next((l for l in leges(db) if l["id"] == line["id"]), None)
            if lex:
                line = dict(line, text="Lēx %s — %s" % (lex["numeral"], line["text"]), lex=lex["n"])
        ctx["magister_line"] = line
        ctx["games"] = _GAMES
    return render_template("index.html", **ctx)


# ==========================================================================
# Application 1 — the review tool
# ==========================================================================

def ensure_seeded(db):
    """On first use, import the generated bank automatically so the teacher
    lands straight in a working queue instead of an empty screen. Runs the
    mechanical checks exactly as a manual import would. No-op once seeded."""
    if store.counts(db)["total"] > 0:
        return None
    items = dataio.load_bank()
    flags_by_item, report = checks.run_all(items, _VALID_NODES, _ALLOWED_LATIN)
    store.import_items(db, items, flags_by_item, ", ".join(os.path.basename(f) for f in dataio.bank_files()))
    return report


@app.route("/review")
def review_queue():
    db = get_db()
    ensure_seeded(db)
    # Teaching order, matching continuous review — the ids sort CR before MS,
    # but the course runs MS, CR, RW, MW.
    pending = dict(store.node_queue_counts(db))
    node_rows = [{"node": n, "label": _NODE_LABEL.get(n, ""), "count": pending[n]}
                 for n in _SPEC if n in pending]
    return render_template("review_queue.html", nodes=node_rows,
                           counts=store.counts(db),
                           n_hard=len(store.hard_to_call(db)))


@app.route("/review/import", methods=["POST"])
def review_import():
    db = get_db()
    items = dataio.load_bank()
    flags_by_item, report = checks.run_all(items, _VALID_NODES, _ALLOWED_LATIN)
    imported = store.import_items(db, items, flags_by_item, ", ".join(os.path.basename(f) for f in dataio.bank_files()))
    # Build a human import summary.
    summary = {
        "inserted": imported["inserted"], "updated": imported["updated"],
        "flagged": report["n_flagged"], "total": report["n_items"],
        "by_check": report["by_check"], "by_level": report["by_level"],
        "literal_check4": report["literal_check4_explain_items_with_a_noncausal_option"],
        "literal_check6a": report["literal_check6a_macron_items_without_macron_answers"],
    }
    return render_template("review_import.html", summary=summary, counts=store.counts(db))


@app.route("/review/node/<node_id>")
def review_node(node_id):
    db = get_db()
    item = store.next_unreviewed_in_node(db, node_id)
    if item is None:
        return render_template("review_done.html", where="node", node_id=node_id,
                               label=_NODE_LABEL.get(node_id, ""), counts=store.counts(db),
                               last=_last_action(), queue="node")
    remaining = dict(store.node_queue_counts(db)).get(node_id, 0)
    return render_template("review_item.html", item=item, queue="node",
                           node_id=node_id, remaining=remaining,
                           last=_last_action())


def review_session_id():
    """Which review sitting this is.

    Sessions are already resumable, so the id lives in the signed cookie and
    survives closing the laptop — which is what makes "the decisions I made
    this session" mean something the next morning. A new id is minted only when
    the teacher explicitly starts a fresh sitting.
    """
    sid = session.get("review_session")
    if not sid:
        sid = uuid.uuid4().hex[:12]
        session.permanent = True
        session["review_session"] = sid
    return sid


def _last_action():
    """The banner strip: what you just did, and the ways back out of it.

    This is where 2a's always-visible undo lives, and where 2b's
    after-a-rejection confirmation lives. Putting both on the next card rather
    than on a screen of their own is deliberate: auto-advance is what makes the
    tool fast, and a confirmation screen after every rejection would take that
    back one tap at a time.
    """
    db = get_db()
    d = store.last_undoable(db, review_session_id())
    if d is None:
        return None
    item = store.get_item(db, d["item_id"])
    return {"status": d["status"], "item_id": d["item_id"], "reason": d["reason"],
            "node_id": (item or {}).get("node_id", "")}


@app.route("/review/undo", methods=["POST"])
def review_undo():
    """Step back one question and reopen the decision.

    It does not silently reverse and move on: you land back on the question
    with the decision open, because the whole point is that you did not mean
    the last thing you did and want to look again.
    """
    db = get_db()
    queue = request.form.get("queue", "all")
    d = store.undo_last(db, review_session_id())
    if d is None:
        return redirect(url_for("review_queue"))
    return redirect(url_for("review_item", item_id=d["item_id"], queue=queue,
                            undone=d["status"]))


@app.route("/review/item/<item_id>")
def review_item(item_id):
    """One specific question, outside the queue order.

    Reached by undo and by tapping a session-history entry. The decision is
    open exactly as it is in the queue, so changing your mind is the same four
    keys as making it up the first time.
    """
    db = get_db()
    item = store.get_item(db, item_id)
    if item is None:
        abort(404)
    c = store.counts(db)
    return render_template(
        "review_item.html", item=item, queue=request.args.get("queue", "all"),
        node_id=item["node_id"], remaining=c["unreviewed"],
        node_remaining=dict(store.node_queue_counts(db)).get(item["node_id"], 0),
        entered_node=False, revisiting=True,
        undone=request.args.get("undone"),
        verdicts=store.verdict_path(db, item_id),
        last=_last_action())


@app.route("/review/hard")
def review_hard():
    """Questions whose verdict changed more than once.

    These need their own list rather than living in the flagged queue, even
    though the change request says to surface them there. The flagged queue
    serves UNDECIDED questions; a hard-to-call question has, by definition,
    been decided several times over, so putting it back in that rotation would
    hand it to you forever — every fresh decision lengthens the path that put
    it there. So the flag goes on the item (where the review screen shows it,
    and where the export carries it to whoever generates the next batch), and
    the queue page carries a count that links here.
    """
    db = get_db()
    rows = []
    for h in store.hard_to_call(db):
        item = store.get_item(db, h["item_id"])
        if item:
            rows.append({"item": item, "path": h["path"]})
    return render_template("review_hard.html", rows=rows,
                           queue=request.args.get("queue", "all"))


@app.route("/review/history")
def review_history():
    """Every decision in this sitting, most recent first.

    Some mistakes only become visible several questions later — a pattern you
    did not have until you had seen five more like it. Tapping an entry reopens
    that question with the decision changeable.
    """
    db = get_db()
    rows = store.session_decisions(db, review_session_id())
    return render_template("review_history.html", rows=rows,
                           queue=request.args.get("queue", "all"),
                           hard=store.hard_to_call(db))


def _next_continuous(db, exclude_item=None):
    """The next thing to look at anywhere in the bank.

    Spec order, not alphabetical: the node ids sort CR before MS, but the
    course teaches MS, CR, RW, MW. Reviewing in teaching order means each
    question arrives with the last one still in mind, which is most of why
    continuous review is faster than node-hopping.

    The flagged queue comes last. Those need slower attention, and they are
    better met once the fast ones have gone by than mixed in among them.
    """
    # Two passes. The first serves only items never skipped, so one clean
    # sweep of the bank happens before anything deferred comes back; the
    # second picks the deferred ones up. Without that split, skipping an item
    # in MS-003 hands it straight back as soon as MS-004 empties, which is the
    # opposite of "decide later".
    for fresh_only in (True, False):
        pending = dict(store.node_queue_counts(db, fresh_only=fresh_only))
        for node_id in _SPEC:
            if pending.get(node_id):
                item = store.next_unreviewed_in_node(db, node_id, exclude_item,
                                                     fresh_only=fresh_only)
                if item is not None:
                    return item
    return store.next_flagged(db, exclude_item)


@app.route("/review/all")
def review_all():
    """Continuous review: keep going until the whole bank is decided.

    Same screen and same keys as the per-node queue; it just never stops to
    send you home. Crossing from one node into the next is marked, because
    which node you are in changes what a good question looks like.
    """
    db = get_db()
    ensure_seeded(db)
    # The item just skipped, carried through the redirect so "decide later"
    # advances instead of handing the same card back.
    item = _next_continuous(db, request.args.get("after"))
    if item is None:
        # The strip belongs here too. Without it the LAST decision of a
        # sitting is the one decision you cannot take back, which is exactly
        # the one most likely to have been a tired mis-tap.
        return render_template("review_done.html", where="all",
                               counts=store.counts(db), last=_last_action(),
                               queue="all")
    c = store.counts(db)
    return render_template(
        "review_item.html", item=item, queue="all", node_id=item["node_id"],
        remaining=c["unreviewed"],
        node_remaining=dict(store.node_queue_counts(db)).get(item["node_id"], 0),
        entered_node=(request.args.get("node") != item["node_id"]),
        last=_last_action())


@app.route("/review/flagged")
def review_flagged():
    db = get_db()
    item = store.next_flagged(db)
    if item is None:
        return render_template("review_done.html", where="flagged",
                               counts=store.counts(db), last=_last_action(),
                               queue="flagged")
    remaining = store.counts(db)["flagged"]
    return render_template("review_item.html", item=item, queue="flagged",
                           node_id=item["node_id"], remaining=remaining,
                           last=_last_action())


@app.route("/review/action", methods=["POST"])
def review_action():
    db = get_db()
    item_id = request.form["item_id"]
    action = request.form["action"]
    queue = request.form.get("queue", "node")
    node_id = request.form.get("node_id", "")
    sess = review_session_id()
    if action == "approve":
        store.set_review(db, item_id, "approved", session_id=sess)
    elif action == "reject":
        reason = request.form.get("reason") or "rejected"
        store.set_review(db, item_id, "rejected", reason=reason, session_id=sess)
    elif action == "skip":
        store.skip_item(db, item_id, session_id=sess)
    else:
        abort(400)
    return _back_to_queue(queue, node_id, item_id if action == "skip" else None)


def _back_to_queue(queue, node_id, skipped=None):
    if queue == "all":
        return redirect(url_for("review_all", node=node_id, after=skipped))
    if queue == "flagged":
        return redirect(url_for("review_flagged"))
    return redirect(url_for("review_node", node_id=node_id))


@app.route("/review/edit/<item_id>", methods=["GET", "POST"])
def review_edit(item_id):
    db = get_db()
    item = store.get_item(db, item_id)
    if item is None:
        abort(404)
    queue = request.values.get("queue", "node")
    node_id = request.values.get("node_id", item["node_id"])
    if request.method == "GET" and request.args.get("from_reject"):
        # "Edit instead" reopens the question WITH THE REJECTION CANCELLED.
        # Arriving in the editor on a question still marked rejected would mean
        # abandoning the edit silently leaves it rejected — the opposite of what
        # the button says.
        store.undo_last(get_db(), review_session_id())
        return redirect(url_for("review_edit", item_id=item_id, queue=queue,
                                node_id=node_id, unrejected=1))
    if request.method == "POST":
        text = request.form["payload"]
        try:
            new_payload = yaml.safe_load(text)
            assert isinstance(new_payload, dict) and new_payload.get("id"), "must be a mapping with an id"
        except Exception as e:  # noqa: BLE001
            return render_template("review_edit.html", item=item, payload_text=text,
                                   error=str(e), queue=queue, node_id=node_id)
        store.set_review(db, item_id, "approved", new_payload=new_payload,
                         edited=True, session_id=review_session_id())
        return _back_to_queue(queue, node_id)
    payload_text = yaml.safe_dump(item["payload"], allow_unicode=True, sort_keys=False)
    return render_template("review_edit.html", item=item, payload_text=payload_text,
                           error=None, queue=queue, node_id=node_id,
                           unrejected=request.args.get("unrejected"))


@app.route("/review/export")
def review_export():
    db = get_db()
    payloads = store.approved_payloads(db)
    doc = {"items": payloads}
    text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    header = ("# Approved questions exported from the review tool\n"
              f"# {len(payloads)} items · {time.strftime('%Y-%m-%d %H:%M')}\n\n")
    return Response(header + text, mimetype="text/yaml",
                    headers={"Content-Disposition": "attachment; filename=latin1-items-approved.yaml"})


# ==========================================================================
# Application 2 — the vocabulary drill (build step 4, wired below)
# ==========================================================================

def _drill_stats(events):
    """Session and all-time figures for the drill, derived from history."""
    universe = {drill._key(w["latin"]) for w in _DRILL_WORDS}
    return {"sess": stats.session_stats(events),
            "alltime": stats.alltime_by_word(events, universe=universe)}


def _practice_stats(db, events):
    """Same two horizons for grammar practice, counted over the spec nodes the
    student could currently meet (approved questions from taught lessons)."""
    approved = store.approved_items(db)
    universe = {it["node"] for it in approved if it["node"] in _taught_now()}
    return {"sess": stats.session_stats(events),
            "alltime": stats.alltime_by_node(events, universe=universe)}


def current_student():
    """Who is signed in on this device.

    Read from the signed session and NEVER from the request. That is the
    difference between a student and a URL: `?student=40218` used to be enough
    to practice as somebody else, and no amount of PIN checking at the door
    would have mattered while the rest of the app took your word for it
    afterwards.
    """
    return session.get(auth.STUDENT_KEY) or ""


@app.template_global("hint_examples")
def _hint_examples(examples, item):
    """Worked examples safe to show before answering. See practice.hint_examples."""
    return practice.hint_examples(examples, item or {})


@app.template_global("shown_options")
def shown_options(item):
    """The options of a choice item, in the order THIS student sees them.

    A template global rather than a variable threaded through every route,
    because the seed comes from the signed session and must never come from
    anything the page was handed. Teacher screens deliberately do not use it:
    the review tool shows an item as written, answer first, which is what a
    person approving it needs to see.
    """
    return practice.display_options(
        item.get("options"),
        practice.option_seed(current_student(), item.get("id")),
        keep_order=bool(item.get("keep_order")))


@app.template_global("stem_html")
def stem_html(item):
    """A question's stem, escaped, with the words the exam underlines
    underlined (past-NLE questions; nothing else has any)."""
    return Markup(nle.mark_up((item or {}).get("stem"), (item or {}).get("underline")))


def _signed_in_student():
    """The signed-in student, or the response that sends them to sign in."""
    sid = current_student()
    if not sid:
        return None, redirect(url_for("signin", next=request.full_path.rstrip("?")))
    return sid, None


def due_today(db, student, events=None):
    """{"vocab": n, "grammar": n} reviews due now -- the day's finish line.
    Words and questions never seen don't count; they are new, not due."""
    if not student:
        return None
    events = events if events is not None else store.events_for_student(db, student)
    ready = practice.practiceable(store.approved_items(db), _taught_now())
    return {"vocab": drill.due_count(_DRILL_WORDS, events, "current"),
            "grammar": practice.due_count(ready, events)}


@app.route("/drill")
def drill_home():
    return render_template("drill_home.html", weeks=drill.WEEK_ORDER,
                           week_labels=drill.WEEK_LABELS,
                           due=due_today(get_db(), current_student()))


@app.route("/drill/start", methods=["POST"])
def drill_start():
    week = request.form.get("week", "current")
    direction = request.form.get("direction", "both")
    return redirect(url_for("drill_session", week=week, direction=direction))


@app.route("/drill/session")
def drill_session():
    db = get_db()
    student = current_student()
    week = request.args.get("week", "current")
    direction = request.args.get("direction", "both")
    events = store.events_for_student(db, student)
    card = drill.next_card(_DRILL_WORDS, events, week=week, direction=direction)
    if card is None:
        return render_template("drill_none.html", student=student, week=week)
    return render_template("drill_card.html", student=student, week=week,
                           direction=direction, card=card,
                           introduced=weeklabel(drill.find_word(_DRILL_WORDS, card.latin).get("week")),
                           nudge=slowdown_nudge(db, student, events),
                           extra=teacher.counted_today(events, "vocab:" + drill._key(card.latin)),
                           **_drill_stats(events))


def grade_form(action, fields, suggest, card, now=None):
    """What _grades.html needs: where to post, what to carry, which grade to
    suggest, and when each grade would bring the card back."""
    waits = {g: fsrs.describe_wait(sec) for g, sec in fsrs.preview(card, now).items()}
    return {"action": action, "fields": fields, "suggest": suggest, "waits": waits}


SUGGEST = {"right": fsrs.GOOD, "close": fsrs.HARD, "wrong": fsrs.AGAIN}


def _rating_from_form():
    r = request.form.get("rating", type=int)
    if r not in fsrs.GRADES:
        abort(400)
    return r


@app.route("/drill/answer", methods=["POST"])
def drill_answer():
    """Check a typed answer and show it with the four grades. Nothing is
    recorded yet: the answer goes into the history when the student grades it
    (drill_grade), so the grade and the answer are one record."""
    db = get_db()
    student = current_student()
    week = request.form.get("week", "current")
    direction = request.form.get("direction", "both")
    latin = request.form["latin"]
    ask = request.form["ask"]                 # 'la_en' or 'en_la'
    response = request.form.get("response", "")
    latency_ms = request.form.get("latency_ms", type=int)
    word = drill.find_word(_DRILL_WORDS, latin)
    if word is None:
        abort(400)
    accepted = drill.accepted_for(word, ask)
    result = check_answer(response, accepted, macron_matters=False)
    item_id = drill.item_id_for(word, ask)
    if result == "close":
        # Close never counts against the student and never reveals the answer;
        # re-show the same card and let them retype. Logged as a close with
        # rating 0: an attempt, not a review.
        store.record_event(db, student, item_id, drill.node_for(word), response, result,
                           latency_ms=latency_ms, context="practice", version="v1", rating=0)
        card = drill.card_for(word, ask)
        return render_template("drill_card.html", student=student, week=week,
                               direction=direction, card=card,
                               introduced=weeklabel(word.get("week")),
                               notice="So close — check your spelling and try again.",
                               **_drill_stats(store.events_for_student(db, student)))
    events = store.events_for_student(db, student)
    pending = dict(student_id=student, item_id=item_id, result=result, response=response,
                   timestamp=time.time(), context="practice", rating=SUGGEST[result])
    word_card = drill.card_state(drill._events_for_key(events, drill._key(word["latin"])))
    grades = grade_form(url_for("drill_grade"),
                        [("week", week), ("direction", direction), ("latin", latin),
                         ("ask", ask), ("response", response),
                         ("latency_ms", latency_ms if latency_ms is not None else "")],
                        SUGGEST[result], word_card)
    return render_template("drill_feedback.html", student=student, week=week,
                           direction=direction, word=word, ask=ask, response=response,
                           result=result, model=accepted[0], grades=grades,
                           introduced=weeklabel(word.get("week")),
                           **_drill_stats(events + [pending]))


@app.route("/drill/grade", methods=["POST"])
def drill_grade():
    """Record the answer with the student's own grade, then the next card.
    The answer is checked again here rather than trusted from the page."""
    db = get_db()
    student = current_student()
    word = drill.find_word(_DRILL_WORDS, request.form.get("latin", ""))
    ask = request.form.get("ask", "")
    if word is None or ask not in ("la_en", "en_la"):
        abort(400)
    rating = _rating_from_form()
    response = request.form.get("response", "")
    accepted = drill.accepted_for(word, ask)
    result = check_answer(response, accepted, macron_matters=False)
    latency = request.form.get("latency_ms", type=int)
    grade_ms = request.form.get("grade_ms", type=int)
    why = rush.verdict("vocab", result, rating, response, accepted, latency, grade_ms)
    store.record_event(db, student, drill.item_id_for(word, ask), drill.node_for(word),
                       response, result, latency_ms=latency, context="practice", version="v1",
                       rating=rating, grade_ms=grade_ms, rush=rush.encode(why))
    return redirect(url_for("drill_session", week=request.form.get("week", "current"),
                            direction=request.form.get("direction", "both")))


# ==========================================================================
# The Reader — a class passage, every word tappable, questions after
# ==========================================================================

_READINGS = readings.load_all()


def published_readings(db):
    return set(store.get_setting(db, "readings_published") or [])


def _reading_or_404(db, slug):
    r = _READINGS.get(slug)
    if r is None or (slug not in published_readings(db) and not auth.is_teacher()):
        abort(404)
    return r


def _question_item(q):
    """A question shaped like a choice item, so options shuffle per student the
    same way every other multiple-choice question in the app does."""
    return {"id": q["item_id"], "options": q.get("options") or {}, "answer": q.get("answer")}


@app.route("/read")
def reader_index():
    db = get_db()
    pub = published_readings(db)
    shown = [r for slug, r in _READINGS.items() if slug in pub or auth.is_teacher()]
    return render_template("reader_index.html", readings=shown, published=pub)


# What a student reads next to a checked question. reader.js carries the same
# words, so a check in place and a check by reload say the same thing.
_VERDICTS = {False: {"right": "✓ Right!", "wrong": "Not quite.", "blank": "Pick an answer first."},
             True: {"self": "Compare yours with this answer:", "right": "✓ You had it.",
                    "close": "Partly — look again at the hint.", "wrong": "Missed it — see the hint.",
                    "blank": "Write an answer first."}}


@app.template_global()
def verdict_text(result, written=False):
    return _VERDICTS[bool(written)].get(result or "", "")


def _record_reading(db, r, qid, picked, result):
    """One checked question becomes one event. A teacher previewing has no
    student session, so nothing is recorded for them."""
    student = current_student()
    # "self" is a written answer not yet compared with the model: it is
    # recorded when the student says how it went (reader_report).
    if not student or result in ("blank", "self"):
        return
    q = readings.question(r, qid)
    store.record_event(db, student, q["item_id"], readings.NODE,
                       str(picked or "")[:readings.MAX_TYPED], result,
                       context=readings.CONTEXT, version="v1")


@app.route("/read/<slug>", methods=["GET", "POST"])
def reader_page(slug):
    """The passage. Each question has its own Check button; reader.js checks it
    in place through reader_check. Without JavaScript the button posts here,
    which checks that one question (or, with no button named, all of them)."""
    db = get_db()
    r = _reading_or_404(db, slug)
    results, picked = {}, {}
    if request.method == "POST" and request.form.get("report"):
        # Without JavaScript: "I had it" / "Partly" / "I missed it" after a
        # written answer, posted as "<qid>:<had|partly|missed>".
        qid, _, said = request.form["report"].partition(":")
        q = readings.question(r, qid)
        if q is None or said not in readings.SELF_REPORT:
            abort(400)
        picked[qid] = request.form.get(qid, "")
        results[qid] = readings.SELF_REPORT[said]
        _record_reading(db, r, qid, picked[qid], results[qid])
        for other in r.get("questions") or []:
            picked.setdefault(other["id"], request.form.get(other["id"], ""))
    elif request.method == "POST":
        only = request.form.get("only")
        qids = [only] if only else [q["id"] for q in r.get("questions") or []]
        for qid in qids:
            picked[qid] = request.form.get(qid, "")
            res = readings.grade_one(r, qid, picked[qid])
            if res is None:
                abort(400)
            results[qid] = res
            _record_reading(db, r, qid, picked[qid], res)
        # keep every other choice the student had made
        for q in r.get("questions") or []:
            picked.setdefault(q["id"], request.form.get(q["id"], ""))
    return render_template("reader_page.html", r=r, results=results, picked=picked,
                           question_item=_question_item,
                           para_questions=readings.questions_by_paragraph(r),
                           hint_ids=lambda q: readings.hint_targets(r, q),
                           published=slug in published_readings(db))


@app.route("/read/<slug>/check", methods=["POST"])
def reader_check(slug):
    """Check one question in place: {"result": "right" | "wrong" | "blank"}, or
    for a written answer {"result": "self", "model": ...} -- the model answer
    is only sent once the student has written something."""
    db = get_db()
    r = _reading_or_404(db, slug)
    qid, picked = request.form.get("qid", ""), request.form.get("picked", "")
    res = readings.grade_one(r, qid, picked)
    if res is None:
        abort(404)
    _record_reading(db, r, qid, picked, res)
    if res == "self":
        return {"result": res, "model": readings.question(r, qid)["model"]}
    return {"result": res}


@app.route("/read/<slug>/report", methods=["POST"])
def reader_report(slug):
    """How a written answer compared with the model, in the student's words:
    had -> right, partly -> close, missed -> wrong. Recorded with what they wrote."""
    db = get_db()
    r = _reading_or_404(db, slug)
    qid, said = request.form.get("qid", ""), request.form.get("reported", "")
    q = readings.question(r, qid)
    typed = request.form.get("typed", "")
    if q is None or not readings.is_open(q) or said not in readings.SELF_REPORT \
            or not typed.strip():
        abort(400)
    res = readings.SELF_REPORT[said]
    _record_reading(db, r, qid, typed, res)
    return {"result": res}


@app.route("/teacher/reader", methods=["GET", "POST"])
def teacher_reader():
    """Publish or withdraw passages, and see how each student did on the
    questions -- their latest answer to each."""
    db = get_db()
    pub = published_readings(db)
    if request.method == "POST":
        slug = request.form.get("slug", "")
        if slug in _READINGS:
            if request.form.get("action") == "publish":
                pub.add(slug)
            else:
                pub.discard(slug)
            store.set_setting(db, "readings_published", sorted(pub))
        return redirect(url_for("teacher_reader"))
    roster_ids = [x["student_id"] for x in store.roster(db, active_only=True)]
    events = [e for e in store.all_events(db) if e.get("context") == readings.CONTEXT]
    rows = []
    for slug, r in _READINGS.items():
        qids = [q["item_id"] for q in r.get("questions") or []]
        latest = {}
        for e in events:                      # oldest first, so the last one wins
            if e["item_id"] in qids:
                latest.setdefault(e["student_id"], {})[e["item_id"]] = e
        students = []
        for sid in sorted(latest, key=lambda s: (s not in roster_ids, s)):
            got = latest[sid]
            students.append({"student_id": sid,
                             "right": sum(1 for e in got.values() if e["result"] == "right"),
                             "answered": len(got),
                             "last": max(e["timestamp"] for e in got.values())})
        # Written answers, word for word: each student's latest, per question.
        written = []
        for num, q in enumerate(r.get("questions") or [], start=1):
            if not readings.is_open(q):
                continue
            answers = [{"student_id": sid, "text": got[q["item_id"]]["response"],
                        "result": got[q["item_id"]]["result"]}
                       for sid, got in sorted(latest.items()) if q["item_id"] in got]
            written.append({"number": num, "ask": q["ask"], "model": q.get("model", ""),
                            "answers": answers})
        rows.append({"r": r, "problems": readings.problems(r), "published": slug in pub,
                     "students": students, "n_questions": len(qids), "written": written,
                     "not_yet": [s for s in roster_ids if s not in latest]})
    return render_template("teacher_reader.html", rows=rows)


# ==========================================================================
# The Magister — a cartoon teacher's lines, approved by the real one
# ==========================================================================

_MAGISTER = magister.load()


def magister_lines(db):
    """Every line in force -- the file's (with the teacher's edits) and the
    teacher's own -- each with its approval state, in category order."""
    overrides = store.teaching_overrides(db)
    approvals = store.teaching_approvals(db)
    lines = []
    for l in _MAGISTER:
        lines.append(dict(overrides.get(magister.key(l["id"])) or l, id=l["id"], note=l["note"],
                          edited=magister.key(l["id"]) in overrides, custom=False))
    for k, v in sorted(overrides.items()):
        if k.startswith(magister.PREFIX + "custom-"):
            lines.append(dict(v, id=k[len(magister.PREFIX):], note="", edited=False, custom=True))
    for l in lines:
        got = approvals.get(magister.key(l["id"]))
        l["state"] = ("approved" if got == magister.fingerprint(l) else "edited" if got else "draft")
    order = {c: i for i, (c, _) in enumerate(magister.CATEGORIES)}
    lines.sort(key=lambda l: order.get(l.get("category"), 99))
    return lines


def magister_says(db, student, categories, n):
    """An approved line from these categories for this student, or None."""
    ok = [l for l in magister_lines(db) if l["state"] == "approved" and l["category"] in categories]
    return magister.rotate(ok, student, n)


def leges(db):
    """The Lēgēs Magistrī: every approved law, numbered I, II, III ..."""
    return magister.number_leges([l for l in magister_lines(db) if l["state"] == "approved"])


@app.route("/leges")
def leges_page():
    """The Magister's laws, all on one page: how to use the app, then what not
    to do. Only the ones the teacher has approved, numbered as they stand."""
    db = get_db()
    laws = leges(db)
    waiting = sum(1 for l in magister_lines(db)
                  if l["category"] in magister.LEGES and l["state"] != "approved")
    return render_template("leges.html", how=[l for l in laws if l["category"] == "leges-how"],
                           dont=[l for l in laws if l["category"] == "leges-dont"],
                           waiting=waiting if auth.is_teacher() else 0,
                           student=current_student())


def slowdown_nudge(db, student, events):
    """What the Magister says after three rushed cards in a row, or None."""
    if not rush.rushing_now(events, now=time.time()):
        return None
    n = sum(1 for e in events if e.get("rush"))
    line = magister_says(db, student, ("slowdown",), n)
    return line["text"] if line else magister.DEFAULT_SLOWDOWN


@app.route("/teacher/magister")
def teacher_magister():
    db = get_db()
    lines = magister_lines(db)
    numbers = {l["id"]: l["numeral"] for l in leges(db)}
    for l in lines:
        l["numeral"] = numbers.get(l["id"])
    groups = [{"category": c, "label": label, "lines": [l for l in lines if l["category"] == c]}
              for c, label in magister.CATEGORIES]
    return render_template("teacher_magister.html", groups=groups,
                           n_approved=sum(1 for l in lines if l["state"] == "approved"),
                           total=len(lines), categories=magister.CATEGORIES,
                           error=request.args.get("error"), error_id=request.args.get("id"))


@app.route("/teacher/magister/save", methods=["POST"])
def teacher_magister_save():
    """approve | withdraw | edit (saves and approves) | add | delete (own lines),
    or approve_all."""
    db = get_db()
    action = request.form.get("action", "approve")
    lines = {l["id"]: l for l in magister_lines(db)}
    if action == "approve_all":
        for l in lines.values():
            store.approve_teaching(db, magister.key(l["id"]), magister.fingerprint(l))
        return redirect(url_for("teacher_magister"))
    if action == "add":
        lid = magister.new_custom_id()
        line = {"category": request.form.get("category", "rules"),
                "text": (request.form.get("text") or "").strip()}
    else:
        lid = request.form.get("id", "")
        if lid not in lines:
            abort(404)
        line = lines[lid]
    anchor = "#m-" + lid
    if action == "withdraw":
        store.unapprove_teaching(db, magister.key(lid))
    elif action == "delete" and line.get("custom"):
        store.clear_teaching_override(db, magister.key(lid))
        store.unapprove_teaching(db, magister.key(lid))
        anchor = ""
    elif action in ("edit", "add"):
        if action == "edit":
            line = {"category": request.form.get("category") or line["category"],
                    "text": (request.form.get("text") or "").strip()}
        bad = magister.problems(line)
        if bad:
            return redirect(url_for("teacher_magister", error=bad[0], id=lid) + anchor)
        entry = {"category": line["category"], "text": line["text"]}
        store.set_teaching_override(db, magister.key(lid), entry)
        store.approve_teaching(db, magister.key(lid), magister.fingerprint(entry))
    else:
        store.approve_teaching(db, magister.key(lid), magister.fingerprint(line))
    return redirect(url_for("teacher_magister") + anchor)


# ==========================================================================
# Vocabulary hints — the word in an example sentence, approved by the teacher
# ==========================================================================

_VOCAB_HINTS = vocabhints.load()


def vocab_hint_entry(db, latin):
    """The example sentence in force for a word: the teacher's edit if there is
    one, otherwise vocab-examples.yaml."""
    k = vocabhints.key(latin)
    return store.teaching_override(db, vocabhints.approval_key(latin)) or _VOCAB_HINTS.get(k)


def vocab_hint_state(db, latin, entry=None, approvals=None):
    entry = entry or vocab_hint_entry(db, latin)
    if not entry:
        return "none"
    got = (approvals if approvals is not None else store.teaching_approvals(db)).get(
        vocabhints.approval_key(latin))
    if got == vocabhints.fingerprint(entry):
        return "approved"
    return "edited" if got else "draft"


def approved_vocab_hint(latin):
    """The sentence a student may see, or None. Nothing unapproved gets out."""
    db = get_db()
    entry = vocab_hint_entry(db, latin)
    return entry if entry and vocab_hint_state(db, latin, entry) == "approved" else None


@app.template_global()
def vocab_card_hint(latin, ask):
    return vocabhints.for_card(approved_vocab_hint(latin), ask)


@app.template_global()
def vocab_example(latin):
    entry = approved_vocab_hint(latin)
    if not entry:
        return None
    return {"segments": vocabhints.segments(entry), "en": entry.get("en") or "",
            "latin": bool(entry.get("en"))}


@app.route("/teacher/vocab-hints")
def teacher_vocab_hints():
    db = get_db()
    approvals = store.teaching_approvals(db)
    groups = []
    for w in _DRILL_WORDS:
        wk = w.get("week") or ""
        if not groups or groups[-1]["week"] != wk:
            groups.append({"week": wk, "label": drill.WEEK_LABELS.get(wk, wk), "rows": []})
        entry = vocab_hint_entry(db, w["latin"])
        groups[-1]["rows"].append({
            "latin": w["latin"], "gloss": ", ".join(w.get("en") or [])[:40],
            "entry": entry, "segments": vocabhints.segments(entry) if entry else [],
            "state": vocab_hint_state(db, w["latin"], entry, approvals),
            "anchor": "h-" + vocabhints.key(w["latin"]).replace(" ", "-")})
    for grp in groups:
        grp["approved"] = sum(1 for r in grp["rows"] if r["state"] == "approved")
    rows = [r for grp in groups for r in grp["rows"]]
    return render_template("teacher_vocab_hints.html", groups=groups,
                           n_approved=sum(1 for r in rows if r["state"] == "approved"),
                           total=len(rows), error=request.args.get("error"),
                           error_word=request.args.get("word"))


@app.route("/teacher/vocab-hints/save", methods=["POST"])
def teacher_vocab_hint_save():
    """Approve, withdraw, or reword-and-approve one word's sentence."""
    db = get_db()
    latin = request.form.get("word", "")
    word = drill.find_word(_DRILL_WORDS, latin)
    if word is None:
        abort(404)
    akey = vocabhints.approval_key(latin)
    anchor = "#h-" + vocabhints.key(latin).replace(" ", "-")
    action = request.form.get("action", "approve")
    if action == "withdraw":
        store.unapprove_teaching(db, akey)
    elif action == "edit":
        entry = {"word": word["latin"], "latin": (request.form.get("latin") or "").strip(),
                 "en": (request.form.get("en") or "").strip()}
        bad = vocabhints.problems(entry)
        if bad:
            return redirect(url_for("teacher_vocab_hints", error=bad[0], word=latin) + anchor)
        store.set_teaching_override(db, akey, entry)
        store.approve_teaching(db, akey, vocabhints.fingerprint(entry))
    else:
        entry = vocab_hint_entry(db, latin)
        if entry:
            store.approve_teaching(db, akey, vocabhints.fingerprint(entry))
    return redirect(url_for("teacher_vocab_hints") + anchor)


@app.route("/teacher/vocab-hints/approve-all", methods=["POST"])
def teacher_vocab_hints_approve_all():
    """Every sentence on the page, as it reads now. The teacher's click."""
    db = get_db()
    for w in _DRILL_WORDS:
        entry = vocab_hint_entry(db, w["latin"])
        if entry:
            store.approve_teaching(db, vocabhints.approval_key(w["latin"]),
                                   vocabhints.fingerprint(entry))
    return redirect(url_for("teacher_vocab_hints"))


# ==========================================================================
# Teaching text — draft in teaching.yaml, approved here
# ==========================================================================

def teaching_entry(db, node_id):
    """The wording in force for a node: the teacher's edit if there is one,
    otherwise teaching.yaml. The file is still never written to."""
    if node_id is None:
        return None
    return store.teaching_override(db, node_id) or _TEACHING.get(node_id)


def teaching_state(db, node_id, entry=None):
    """approved / edited / draft, against the wording in force.

    `edited` means signed off once and changed since -- by a reword here or in
    the file -- and it is deliberately not shown to a student until it is read
    again. An old approval must not carry over to new words.
    """
    entry = entry or teaching_entry(db, node_id)
    if not entry:
        return None
    got = store.teaching_approvals(db).get(node_id)
    if got == dataio.teaching_fingerprint(entry):
        return "approved"
    return "edited" if got else "draft"


def approved_teaching_for(db, node_id):
    """The teaching text for a node, but only if the teacher has approved the
    exact wording in force. Draft or edited-since-approval text returns None,
    so nothing student-facing ships unread."""
    entry = teaching_entry(db, node_id)
    if not entry:
        return None
    if teaching_state(db, node_id, entry) == "approved":
        return entry
    return None


@app.template_global("teaching_for")
def _teaching_for(node_id):
    """The wording in force for a node, for the review screen.

    A template global rather than four more arguments threaded through the four
    routes that render a question -- and the next one somebody adds would have
    forgotten it.
    """
    return teaching_entry(get_db(), node_id)


@app.template_global("teaching_state_for")
def _teaching_state_for(node_id):
    return teaching_state(get_db(), node_id)


@app.route("/teaching")
def teaching_index():
    db = get_db()
    approvals = store.teaching_approvals(db)
    overrides = store.teaching_overrides(db)
    rows = []
    for nid in _TEACHING:
        entry = overrides.get(nid) or _TEACHING[nid]
        got = approvals.get(nid)
        if got == dataio.teaching_fingerprint(entry):
            state = "approved"
        elif got:
            state = "edited"          # signed off once, the words changed since
        else:
            state = "draft"
        rows.append({"node": nid, "label": entry.get("label", ""),
                     "state": state, "strand": nid.split("-")[0],
                     "reworded": nid in overrides})
    rows.sort(key=lambda r: r["node"])
    counts = {"approved": sum(1 for r in rows if r["state"] == "approved"),
              "draft": sum(1 for r in rows if r["state"] == "draft"),
              "edited": sum(1 for r in rows if r["state"] == "edited"),
              "total": len(rows)}
    return render_template("teaching_index.html", rows=rows, counts=counts)


@app.route("/teaching/<node_id>")
def teaching_read(node_id):
    db = get_db()
    entry = teaching_entry(db, node_id)
    if not entry:
        abort(404)
    state = teaching_state(db, node_id, entry)
    order = sorted(_TEACHING)
    i = order.index(node_id)
    return render_template("teaching_read.html", node=node_id, entry=entry,
                           state=state,
                           reworded=store.teaching_override(db, node_id) is not None,
                           nxt=order[i + 1] if i + 1 < len(order) else None,
                           prv=order[i - 1] if i > 0 else None)


@app.route("/teaching/<node_id>/edit", methods=["GET", "POST"])
def teaching_edit(node_id):
    """Reword a node's teaching text without leaving the app.

    The edit is stored in the database, not written back to teaching.yaml. A
    hosted service's disk does not survive a redeploy, so a file write would
    lose the teacher's words the next time the app was updated -- quietly, and
    in favour of wording they had already decided against.

    Saving always clears the approval, whatever it said before: the fingerprint
    covers the exact words, and new words have not been signed off yet. That is
    the same rule the file already obeys, applied to the same text arriving by
    a different door.
    """
    db = get_db()
    entry = teaching_entry(db, node_id)
    if not entry:
        abort(404)
    back = request.values.get("back") or url_for("teaching_read", node_id=node_id)
    if request.method == "POST":
        if request.form.get("action") == "revert":
            store.clear_teaching_override(db, node_id)
            store.unapprove_teaching(db, node_id)
            return redirect(back)
        examples = [ln.strip() for ln in
                    (request.form.get("examples") or "").splitlines() if ln.strip()]
        edited = dict(entry)
        edited["explain"] = (request.form.get("explain") or "").strip()
        edited["examples"] = examples
        edited["when_wrong"] = (request.form.get("when_wrong") or "").strip()
        edited["status"] = "draft"
        problem = None
        if not edited["explain"]:
            problem = "The explanation is what a student reads after a miss. It cannot be empty."
        elif not examples:
            problem = "Keep at least one worked example."
        elif not edited["when_wrong"]:
            problem = "The after-a-miss line cannot be empty."
        elif len(edited["explain"].split()) > 120:
            problem = ("The explanation is %d words. Keep it under 120 so it fits a phone."
                       % len(edited["explain"].split()))
        if problem:
            return render_template("teaching_edit.html", node=node_id, entry=edited,
                                   state=teaching_state(db, node_id),
                                   reworded=store.teaching_override(db, node_id) is not None,
                                   back=back, error=problem), 400
        store.set_teaching_override(db, node_id, edited)
        store.unapprove_teaching(db, node_id)
        return redirect(back)
    return render_template("teaching_edit.html", node=node_id, entry=entry,
                           state=teaching_state(db, node_id, entry),
                           reworded=store.teaching_override(db, node_id) is not None,
                           back=back, error=None)


@app.route("/teaching/approve-all", methods=["POST"])
def teaching_approve_all():
    """Sign off every node still waiting, in one action.

    Deliberately not the default path and deliberately not hidden: the per-node
    screen exists so wording is read before it reaches a student, and this
    skips that reading. It is here because the teacher who wrote the course can
    legitimately say they have read the lot -- but it is their click, and every
    node can still be withdrawn one at a time afterwards.
    """
    db = get_db()
    approvals = store.teaching_approvals(db)
    overrides = store.teaching_overrides(db)
    done = 0
    for nid in _TEACHING:
        entry = overrides.get(nid) or _TEACHING[nid]
        fp = dataio.teaching_fingerprint(entry)
        if approvals.get(nid) != fp:
            store.approve_teaching(db, nid, fp)
            done += 1
    return redirect(url_for("teaching_index", approved=done))


@app.route("/teaching/<node_id>/approve", methods=["POST"])
def teaching_approve(node_id):
    db = get_db()
    entry = teaching_entry(db, node_id)
    if not entry:
        abort(404)
    action = request.form.get("action", "approve")
    back = request.form.get("back")
    if action == "unapprove":
        store.unapprove_teaching(db, node_id)
        return redirect(back or url_for("teaching_read", node_id=node_id))
    store.approve_teaching(db, node_id, dataio.teaching_fingerprint(entry))
    if back:
        # Approved from the review screen: go back to the question, not away
        # from it. Reviewing is a flow and this must not interrupt it.
        return redirect(back)
    nxt = request.form.get("next")
    if nxt:
        return redirect(url_for("teaching_read", node_id=nxt))
    return redirect(url_for("teaching_index"))


# ==========================================================================
# Application 3 — grammar practice (serves APPROVED questions only)
# ==========================================================================

VALID_CONTEXTS = {"practice", "homework", "classwork", "quiz", "exam"}


def _taught_now():
    return practice.taught_nodes(_SPEC)


# --------------------------------------------------------------------------
# Grammar badges (badges.py): the map, and a badge check
# --------------------------------------------------------------------------

def _short_date(day):
    try:
        t = time.strptime(str(day), "%Y-%m-%d")
    except ValueError:
        return ""
    return "%s %d" % (time.strftime("%b", t), t.tm_mday)


def badge_map(db, student, now=None):
    """Everything the map shows: the tree of badges with this student's state,
    what each builds on, Start here, and what this week asks for."""
    now = now or time.time()
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    approved = store.approved_items(db)
    taught = practice.taught_nodes(_SPEC, today)
    avail = {b["id"] for b in badges.available(_BADGES, _SPEC, approved, today)}
    events = store.events_for_student(db, student) if student else []
    built_on = badges.foundations(_BADGES, _SPEC)
    order = sorted((b for b in _BADGES if b["id"] in avail),
                   key=lambda b: (badges.first_taught(b, _SPEC), _BADGES.index(b)))
    st = {bid: badges.status(events, bid, now) for bid in avail}
    start_here = None
    for b in order:
        if not st[b["id"]]["earned"] and all(
                st[p]["earned"] for p in built_on[b["id"]] if p in avail):
            start_here = b["id"]
            break
    family = {r["id"]: r["label"] for r in _BADGE_ROWS}
    approvals = store.teaching_approvals(db)
    direct = badges.direct_foundations(_BADGES, _SPEC)
    level = badges.levels(_BADGES, _SPEC)
    cards = {}
    for b in _BADGES:
        c = {"id": b["id"], "title": b["title"], "about": b["about"],
             "family": family.get(b["row"], ""),
             "available": b["id"] in avail,
             "coming": _short_date(badges.first_taught(b, _SPEC)),
             # taught already, but no approved questions to ask yet
             "unready": b["id"] not in avail and badges.first_taught(b, _SPEC) <= today,
             "builds_on": [_BADGE_BY_ID[p]["title"] for p in direct[b["id"]]],
             "parents": direct[b["id"]],
             "questions": len(badges.pool(b, approved, taught)),
             "start_here": b["id"] == start_here, "earned": False, "due": False,
             "n": _LESSON_NO[b["id"]],
             "lesson": lesson_for(db, b["id"], approvals) is not None}
        if c["available"]:
            c.update(st[b["id"]])
            card = fsrs.replay(badges.markers(events, b["id"], until=now + 1))
            if c["earned"] and card is not None and card.due > card.last:
                c["left"] = max(0.0, min(1.0, (card.due - now) / (card.due - card.last)))
        cards[b["id"]] = c
    # The tree: one row per level, each row ordered under its parents (the
    # mean position of the badges it builds on) so the lines rarely cross.
    tree, pos = [], {}
    for lv in range(max(level.values()) + 1 if level else 0):
        in_file = [b["id"] for b in _BADGES if level[b["id"]] == lv]
        ids = sorted(in_file, key=lambda i: (sum(pos[p] for p in direct[i]) / len(direct[i])
                                             if direct[i] else (in_file.index(i) + 0.5) / len(in_file)))
        for n, i in enumerate(ids):
            pos[i] = (n + 0.5) / len(ids)
        tree.append([cards[i] for i in ids])
    week = None
    rule = badge_rule(db)
    if student and rule:
        week = goals.weekly_progress(events, weekly_targets(db), now, badge_rule=rule)["badges"]
    return {"tree": tree, "cards": [cards[b["id"]] for b in _BADGES],
            "start_here": start_here, "week": week,
            "refresh": [b["id"] for b in order if st[b["id"]]["due"]],
            "n_available": len(avail),
            "n_up_to_date": sum(1 for b in avail if st[b]["up_to_date"])}


_LESSONS = lessons.load()
_LESSON_NO = lessons.numbered(_BADGES, _SPEC, badges.first_taught)


def lesson_for(db, bid, approvals=None):
    """The badge's lesson if the teacher approved this wording, else None."""
    lesson = _LESSONS.get(bid)
    if lesson is None:
        return None
    approvals = approvals if approvals is not None else store.teaching_approvals(db)
    return lesson if approvals.get(lessons.key(bid)) == lessons.fingerprint(lesson) else None


def _lesson_steps(lesson):
    """The steps, ready for the page: text already turned into safe HTML."""
    out = []
    for st in lesson["steps"]:
        k = lessons.kind(st)
        v = st[k]
        if k == "say":
            out.append({"kind": k, "paras": [Markup(p) for p in lessons.paragraphs(v)]})
        elif k == "remember":
            out.append({"kind": k, "text": Markup(lessons.inline(v))})
        elif k == "example":
            out.append({"kind": k, "intro": Markup(lessons.inline(v.get("intro"))),
                        "words": [{"w": w.get("w", ""), "tag": w.get("tag", ""),
                                   "note": Markup(lessons.inline(w.get("note", "")))}
                                  for w in v.get("words") or []],
                        "english": Markup(lessons.inline(v.get("english"))),
                        "after": Markup(lessons.inline(v.get("after", "")))})
        elif k == "table":
            out.append({"kind": k, "caption": Markup(lessons.inline(v.get("caption", ""))),
                        "head": [Markup(lessons.inline(h)) for h in v.get("head") or []],
                        "rows": [[Markup(lessons.inline(c)) for c in r] for r in v.get("rows") or []]})
        elif k == "check":
            out.append({"kind": k, "ask": Markup(lessons.inline(v.get("ask"))),
                        "options": [(o, Markup(lessons.inline(t)))
                                    for o, t in (v.get("options") or {}).items()],
                        "answer": v.get("answer"), "why": Markup(lessons.inline(v.get("why")))})
    return out


_NODE_BADGE = {n: b["id"] for b in _BADGES for n in b["nodes"]}


@app.template_global("lesson_hint")
def lesson_hint(node_id):
    """For a grammar question's Hint: the approved lesson its badge opens with
    -- {"n", "title", "bid", "remember"} -- or None. The Hint then never says
    only when a topic was introduced: while a topic's teaching text waits for
    approval, the lesson's one line to remember stands in for it, and the
    lesson itself is a tap away."""
    bid = _NODE_BADGE.get(node_id)
    if bid is None:
        return None
    if "hint_approvals" not in g:
        g.hint_approvals = store.teaching_approvals(get_db())
    lesson = lesson_for(get_db(), bid, g.hint_approvals)
    if lesson is None:
        return None
    remember = next((st["remember"] for st in lesson["steps"] if lessons.kind(st) == "remember"), "")
    return {"n": _LESSON_NO[bid], "title": _BADGE_BY_ID[bid]["title"], "bid": bid,
            "remember": Markup(lessons.inline(remember))}


@app.route("/badges/<bid>/lesson")
def badge_lesson(bid):
    """The lesson before a badge: a few steps, one at a time, then the check."""
    db = get_db()
    b = _BADGE_BY_ID.get(bid)
    if b is None:
        abort(404)
    student = current_student()
    teacher_view = auth.is_teacher()
    if teacher_view and not student and bid in _LESSONS:
        return redirect(url_for("teacher_lesson_review", bid=bid))
    lesson = lesson_for(db, bid) or (_LESSONS.get(bid) if teacher_view else None)
    if lesson is None:
        return redirect(url_for("badge_map_page") + "#b-" + bid)
    events = store.events_for_student(db, student) if student else []
    approved = lesson_for(db, bid) is not None
    family = {r["id"]: r["label"] for r in _BADGE_ROWS}.get(b["row"], "")
    # Opened from a practice NLE's results: the way back is the first thing on
    # the page and the last. Only a path inside the app's own practice NLEs is
    # honoured, so the link can never be pointed somewhere else.
    back = request.args.get("back") or ""
    back = back if back.startswith("/nle/s/") and "//" not in back else None
    return render_template("badge_lesson.html", b=b, steps=_lesson_steps(lesson),
                           number=_LESSON_NO[bid], total=len(_BADGES), family=family,
                           bst=badges.status(events, bid) if student else None,
                           student=student, preview=teacher_view and not student,
                           approved=approved, back=back)


@app.route("/teacher/lessons", methods=["GET", "POST"])
def teacher_lessons():
    """Every badge lesson in course order, to preview and approve."""
    db = get_db()
    if request.method == "POST":
        action, bid = request.form.get("action"), request.form.get("id", "")
        if action == "approve_all":
            for k, l in _LESSONS.items():
                if not lessons.problems(l):
                    store.approve_teaching(db, lessons.key(k), lessons.fingerprint(l))
        elif bid in _LESSONS and action == "approve" and not lessons.problems(_LESSONS[bid]):
            store.approve_teaching(db, lessons.key(bid), lessons.fingerprint(_LESSONS[bid]))
        elif bid in _LESSONS and action == "withdraw":
            store.unapprove_teaching(db, lessons.key(bid))
        then = request.form.get("then")
        if then == "next":
            nxt = _next_lesson_to_review(db, bid)
            if nxt:
                return redirect(url_for("teacher_lesson_review", bid=nxt))
            return redirect(url_for("teacher_lessons", done=1))
        if then == "stay" and bid in _LESSONS:
            return redirect(url_for("teacher_lesson_review", bid=bid))
        return redirect(url_for("teacher_lessons") + ("#l-" + bid if bid else ""))
    approvals = store.teaching_approvals(db)
    rows = []
    for b in sorted(_BADGES, key=lambda x: _LESSON_NO[x["id"]]):
        l = _LESSONS.get(b["id"])
        got = approvals.get(lessons.key(b["id"]))
        state = ("missing" if l is None else "approved" if got == lessons.fingerprint(l)
                 else "changed" if got else "draft")
        rows.append({"b": b, "n": _LESSON_NO[b["id"]], "state": state,
                     "steps": len(l["steps"]) if l else 0,
                     "problems": lessons.problems(l) if l else []})
    return render_template("teacher_lessons.html", rows=rows, done=request.args.get("done"),
                           n_approved=sum(1 for r in rows if r["state"] == "approved"),
                           first=_next_lesson_to_review(db, None))


def _lesson_order():
    return [b["id"] for b in sorted(_BADGES, key=lambda x: _LESSON_NO[x["id"]]) if b["id"] in _LESSONS]


def _next_lesson_to_review(db, after):
    """The next lesson, in course order after `after`, that isn't approved yet
    (wrapping round to the start), or None when every lesson is approved."""
    order = _lesson_order()
    approvals = store.teaching_approvals(db)
    start = order.index(after) + 1 if after in order else 0
    for bid in order[start:] + order[:start]:
        if bid != after and approvals.get(lessons.key(bid)) != lessons.fingerprint(_LESSONS[bid]):
            return bid
    return None


def _answer_text(item):
    """The right answer to a question, in a line, for the teacher's review."""
    fmt = item.get("format")
    if fmt == "choice":
        return (item.get("options") or {}).get(item.get("answer"), "")
    if fmt == "boxes":
        return " · ".join("%s%s" % ((b.get("label") + ": ") if b.get("label") else "",
                                    (b.get("answer") or [""])[0]) for b in item.get("boxes") or [])
    if fmt == practice.LABEL_WORDS:
        return " · ".join("%s = %s" % (t["word"], t["accepted"][0]) for t in practice.label_targets(item))
    if fmt == "tag-then-translate":
        tags = " · ".join("%s = %s, %s" % (t.get("word"), (t.get("case") or [""])[0], (t.get("job") or [""])[0])
                          for t in item.get("tag_boxes") or [])
        return "%s — %s" % (tags, item.get("translation_model_answer") or "")
    return item.get("model_answer") or item.get("answer") or ""


@app.route("/teacher/lessons/<bid>")
def teacher_lesson_review(bid):
    """One lesson to review: it plays as students see it, its checks for
    understanding are listed underneath, and Approve & next moves on."""
    db = get_db()
    b = _BADGE_BY_ID.get(bid)
    lesson = _LESSONS.get(bid)
    if b is None or lesson is None:
        abort(404)
    order = _lesson_order()
    i = order.index(bid)
    approvals = store.teaching_approvals(db)
    got = approvals.get(lessons.key(bid))
    state = ("approved" if got == lessons.fingerprint(lesson) else "changed" if got else "draft")
    checks_ = [st for st in _lesson_steps(lesson) if st["kind"] == "check"]
    approved_items = store.approved_items(db)
    nodes = set(b["nodes"])
    questions = [{"id": it["id"], "node": it["node"], "stem": practice.question_text(it),
                  "options": list((it.get("options") or {}).values()) if it.get("format") == "choice" else [],
                  "answer": _answer_text(it)}
                 for it in sorted(approved_items, key=lambda x: (x["node"], str(x["id"])))
                 if it.get("node") in nodes]
    family = {r["id"]: r["label"] for r in _BADGE_ROWS}.get(b["row"], "")
    return render_template("badge_lesson.html", b=b, steps=_lesson_steps(lesson),
                           number=_LESSON_NO[bid], total=len(_BADGES), family=family,
                           bst=None, student=None, preview=True, review=True,
                           approved=state == "approved", state=state,
                           problems=lessons.problems(lesson),
                           prev_id=order[i - 1] if i > 0 else None,
                           next_id=order[i + 1] if i + 1 < len(order) else None,
                           n_approved=sum(1 for k in order
                                          if approvals.get(lessons.key(k)) == lessons.fingerprint(_LESSONS[k])),
                           checks=checks_, questions=questions,
                           node_label=_NODE_LABEL)


@app.route("/teacher/badges")
def teacher_badges():
    """What each badge covers: its topics, when it appears, its approved
    questions -- the list the teacher approves (badges.yaml)."""
    db = get_db()
    approved = store.approved_items(db)
    taught_all = set(_SPEC)
    built_on = badges.foundations(_BADGES, _SPEC)
    per_node = {}
    for it in approved:
        per_node[it["node"]] = per_node.get(it["node"], 0) + 1
    rows = []
    for row in _BADGE_ROWS:
        out = []
        for b in _BADGES:
            if b["row"] != row["id"]:
                continue
            hinted = sum(1 for n in b["nodes"] if approved_teaching_for(db, n))
            out.append({"b": b, "first": _short_date(badges.first_taught(b, _SPEC)),
                        "hinted": hinted,
                        "lesson": lesson_for(db, b["id"]) is not None,
                        "topics": [{"id": n, "label": _NODE_LABEL.get(n, ""),
                                    "n": per_node.get(n, 0),
                                    "hint": approved_teaching_for(db, n) is not None}
                                   for n in b["nodes"]],
                        "questions": len(badges.pool(b, approved, taught_all)),
                        "builds_on": [_BADGE_BY_ID[p]["title"] for p in built_on[b["id"]]]})
        rows.append({"label": row["label"], "badges": out})
    return render_template("teacher_badges.html", rows=rows, on=badges_from(db),
                           earn=badges.EARN_N, refresh=badges.REFRESH_N)


@app.route("/badges")
def badge_map_page():
    db = get_db()
    student = current_student()
    return render_template("badges.html", m=badge_map(db, student), student=student,
                           on=bool(badges_from(db)),
                           titles={b["id"]: b["title"] for b in _BADGES})


@app.route("/badges/<bid>/start", methods=["POST"])
def badge_start(bid):
    """Begin a check: pick its questions and hand over to the practice screens,
    which carry node "badge:<id>" through every answer and back here."""
    db = get_db()
    student = current_student()
    b = _BADGE_BY_ID.get(bid)
    if b is None or not student:
        abort(404)
    items = badges.pool(b, store.approved_items(db), _taught_now())
    if not items:
        return redirect(url_for("badge_map_page"))
    events = store.events_for_student(db, student)
    mode = badges.status(events, bid)["next"]
    picked = badges.pick(items, events, badges.check_size(mode, len(items)))
    session["badge_run"] = {"b": bid, "mode": mode, "items": [it["id"] for it in picked],
                            "t": time.time()}
    return redirect(url_for("practice_session", node=badges.PREFIX + bid))


def badge_banner(node):
    """For the question screens: "Genitive · question 2 of 6", or None."""
    run = session.get("badge_run")
    if not run or not str(node or "").startswith(badges.PREFIX) or node[len(badges.PREFIX):] != run["b"]:
        return None
    events = store.events_for_student(get_db(), current_student())
    done = len(badges.answered(run["items"], events, run["t"]))
    return {"title": _BADGE_BY_ID[run["b"]]["title"], "mode": run["mode"],
            "i": min(done + 1, len(run["items"])), "n": len(run["items"])}


app.jinja_env.globals["badge_banner"] = badge_banner


def _badge_next(db, student, bid):
    """The next question of the check under way, or -- all answered -- its
    result, recorded once as the badge's event."""
    run = session.get("badge_run")
    if not run or run["b"] != bid or not student:
        return redirect(url_for("badge_map_page"))
    events = store.events_for_student(db, student)
    got = badges.answered(run["items"], events, run["t"])
    if len(got) < len(run["items"]):
        row = store.get_item(db, run["items"][len(got)])
        if row is None or row["review_status"] != "approved":
            session.pop("badge_run", None)            # the bank changed under the check
            return redirect(url_for("badge_map_page"))
        item = row["payload"]
        return render_template("practice_question.html", student=student, item=item,
                               node=badges.PREFIX + bid, context="practice", notice=None,
                               label=_NODE_LABEL.get(item["node"], ""),
                               hint=approved_teaching_for(db, item.get("node")),
                               introduced=nodeweek(item.get("node")),
                               nudge=slowdown_nudge(db, student, events),
                               **_practice_stats(db, events))
    n, right = len(got), sum(1 for _, ok in got if ok)
    passed = right >= badges.needed(run["mode"], n)
    store.record_event(db, student, badges.item_id(bid), None,
                       "%s %d/%d" % (run["mode"], right, n), "right" if passed else "wrong",
                       context=badges.CONTEXT, version="v1",
                       rating=fsrs.GOOD if passed else fsrs.AGAIN)
    session.pop("badge_run", None)
    session["badge_last"] = {"b": bid, "mode": run["mode"], "passed": passed,
                             "right": right, "n": n, "need": badges.needed(run["mode"], n),
                             "got": got}
    return redirect(url_for("badge_done", bid=bid))


@app.route("/badges/<bid>/done")
def badge_done(bid):
    db = get_db()
    student = current_student()
    last = session.get("badge_last")
    if not last or last["b"] != bid or bid not in _BADGE_BY_ID:
        return redirect(url_for("badge_map_page"))
    events = store.events_for_student(db, student)
    questions = []
    for iid, ok in last["got"]:
        row = store.get_item(db, iid)
        node = row["node_id"] if row else ""
        questions.append({"ok": ok, "label": _NODE_LABEL.get(node, node), "node": node})
    m = badge_map(db, student)
    nxt = m["start_here"] and _BADGE_BY_ID[m["start_here"]]
    return render_template("badge_done.html", b=_BADGE_BY_ID[bid], r=last,
                           st=badges.status(events, bid), questions=questions,
                           start_here=nxt, next_no=nxt and _LESSON_NO[nxt["id"]],
                           next_lesson=bool(nxt and lesson_for(db, nxt["id"])),
                           has_lesson=lesson_for(db, bid) is not None,
                           refresh=[_BADGE_BY_ID[x] for x in m["refresh"]])


@app.route("/practice")
def practice_home():
    db = get_db()
    # From the week the teacher switches badges on, the Grammar tab is the
    # badge map. The topic list stays reachable for extra practice.
    if badges_from(db) and not request.args.get("topics"):
        return redirect(url_for("badge_map_page"))
    taught = _taught_now()
    approved = store.approved_items(db)
    ready = practice.practiceable(approved, taught)
    by_node = {}
    for it in ready:
        by_node.setdefault(it["node"], 0)
        by_node[it["node"]] += 1
    nodes = [{"node": n, "label": _NODE_LABEL.get(n, ""), "count": c}
             for n, c in sorted(by_node.items())]
    return render_template("practice_home.html", nodes=nodes,
                           due=due_today(db, current_student()),
                           n_ready=len(ready), n_approved=len(approved),
                           n_locked=len(approved) - len(ready))


@app.route("/practice/start", methods=["POST"])
def practice_start():
    node = request.form.get("node") or ""
    ctx = request.form.get("context", "practice")
    return redirect(url_for("practice_session", node=node, context=ctx))


@app.route("/practice/session")
def practice_session():
    db = get_db()
    student = current_student()
    node = request.args.get("node") or None
    ctx = request.args.get("context", "practice")
    if ctx not in VALID_CONTEXTS:
        ctx = "practice"
    if node and node.startswith(badges.PREFIX):
        return _badge_next(db, student, node[len(badges.PREFIX):])
    approved = store.approved_items(db)
    events = store.events_for_student(db, student)
    # A comma-separated list is a set of topics -- what "Practice everything on
    # this quiz" sends. It is still cut to what has been taught: a question
    # never arrives before its lesson, whichever door the student came in by.
    if node and "," in node:
        wanted = {n for n in node.split(",") if n}
        item = practice.select_question(approved, events,
                                        allowed_nodes=wanted & _taught_now())
    else:
        if node and practice.topic_done_today(approved, events, node, taught=_taught_now()):
            return render_template("practice_topic_done.html", student=student,
                                   label=_NODE_LABEL.get(node, node))
        item = practice.select_question(approved, events,
                                        allowed_nodes=_taught_now(), node_id=node)
    if item is None:
        return render_template("practice_none.html", student=student, node=node,
                               n_approved=len(approved))
    return render_template("practice_question.html", student=student, item=item,
                           node=node, context=ctx, notice=None,
                           extra=teacher.counted_today(events, item["id"]),
                           label=_NODE_LABEL.get(item["node"], ""),
                           hint=approved_teaching_for(db, item.get("node")),
                           introduced=nodeweek(item.get("node")),
                           nudge=slowdown_nudge(db, student, events),
                           **_practice_stats(db, events))


@app.route("/practice/answer", methods=["POST"])
def practice_answer():
    db = get_db()
    student = current_student()
    item_id = request.form["item_id"]
    node = request.form.get("node") or None
    ctx = request.form.get("context", "practice")
    if ctx not in VALID_CONTEXTS:
        ctx = "practice"
    latency = request.form.get("latency_ms", type=int)

    row = store.get_item(db, item_id)
    if row is None or row["review_status"] != "approved":
        abort(404)
    item = row["payload"]
    fmt = item.get("format")

    box_results = tag_results = None
    picked = typed = None

    if fmt == "choice":
        picked = request.form.get("picked")
        result = practice.grade_choice(item, picked)
    elif fmt == "boxes":
        responses = request.form.getlist("box")
        result, box_results = practice.grade_boxes(item, responses)
    elif fmt == "tag-then-translate":
        cases = request.form.getlist("case")
        jobs = request.form.getlist("job")
        result, tag_results = practice.grade_tags(item, cases, jobs)
    elif fmt == practice.LABEL_WORDS:
        result, label_results = practice.grade_labels(item, request.form.getlist("pick"))
        typed = request.form.get("typed", "")
        why = rush.verdict("grammar", result, None, "", (), latency, None,
                           typed=False, boxes=len(label_results))
        store.record_event(db, student, item_id, item.get("node"),
                           practice.label_summary(label_results), result,
                           latency_ms=latency, context=ctx, version="v1", rush=rush.encode(why))
        return render_template("practice_feedback.html", student=student, item=item,
                               node=node, context=ctx, result=result,
                               introduced=nodeweek(item.get("node")),
                               box_results=None, tag_results=None,
                               label_results=label_results, picked=None, typed=typed,
                               menu=practice.menu_for(item) if result == "wrong" else None,
                               teaching=approved_teaching_for(db, item.get("node")),
                               label=_NODE_LABEL.get(item["node"], ""))
    else:                                   # self-check
        typed = request.form.get("typed", "")
        result = "self"

    # CLOSE never counts against the student and never opens the menu:
    # re-show the question and let them retype. Logged with rating 0 -- an
    # attempt, not a review.
    if result == "close":
        store.record_event(db, student, item_id, item.get("node"),
                           practice.response_summary(item, box_results, picked, typed),
                           "close", latency_ms=latency, context=ctx, version="v1", rating=0)
        return render_template("practice_question.html", student=student, item=item,
                               node=node, context=ctx,
                               label=_NODE_LABEL.get(item["node"], ""),
                               hint=approved_teaching_for(db, item.get("node")),
                               introduced=nodeweek(item.get("node")),
                               notice="So close — check your spelling and try again.",
                               **_practice_stats(db, store.events_for_student(db, student)))

    # Everything else is shown with the four grades and recorded when the
    # student grades it (practice_grade). The answer travels with the grade
    # and is checked again there.
    fields = [("item_id", item_id), ("node", node or ""), ("context", ctx),
              ("latency_ms", latency if latency is not None else "")]
    if fmt == "choice":
        fields.append(("picked", picked or ""))
    elif fmt == "boxes":
        fields += [("box", r) for r in request.form.getlist("box")]
    elif fmt == "tag-then-translate":
        fields += [("case", c) for c in request.form.getlist("case")]
        fields += [("job", j) for j in request.form.getlist("job")]
    else:
        fields.append(("typed", typed or ""))
    events = store.events_for_student(db, student)
    card = practice.question_cards([item], events)[item_id]
    grades = grade_form(url_for("practice_grade"), fields,
                        SUGGEST.get(result, fsrs.GOOD), card)
    return render_template("practice_feedback.html", student=student, item=item,
                           node=node, context=ctx, result=result,
                           introduced=nodeweek(item.get("node")),
                           box_results=box_results, tag_results=tag_results,
                           picked=picked, typed=typed, grades=grades,
                           reasons=practice.menu_for(item) if result == "wrong" else None,
                           menu=None,
                           teaching=approved_teaching_for(db, item.get("node")),
                           label=_NODE_LABEL.get(item["node"], ""))


# A self-checked answer has no check of its own: the grade says how it went.
SELF_RESULT = {fsrs.AGAIN: "wrong", fsrs.HARD: "close", fsrs.GOOD: "right", fsrs.EASY: "right"}


@app.route("/practice/grade", methods=["POST"])
def practice_grade():
    """Record a grammar answer with the student's own grade (and the
    what-went-wrong reason, if they picked one), then the next question."""
    db = get_db()
    student = current_student()
    item_id = request.form.get("item_id", "")
    node = request.form.get("node") or None
    ctx = request.form.get("context", "practice")
    if ctx not in VALID_CONTEXTS:
        ctx = "practice"
    row = store.get_item(db, item_id)
    if row is None or row["review_status"] != "approved":
        abort(404)
    item = row["payload"]
    fmt = item.get("format")
    if fmt == practice.LABEL_WORDS:
        abort(400)                       # graded by the app, never by the student
    rating = _rating_from_form()
    box_results = picked = typed = None
    if fmt == "choice":
        picked = request.form.get("picked")
        result = practice.grade_choice(item, picked)
    elif fmt == "boxes":
        result, box_results = practice.grade_boxes(item, request.form.getlist("box"))
    elif fmt == "tag-then-translate":
        result, _tags = practice.grade_tags(item, request.form.getlist("case"),
                                            request.form.getlist("job"))
        typed = " | ".join("%s/%s" % cj for cj in zip(request.form.getlist("case"),
                                                       request.form.getlist("job")))
    else:
        typed = request.form.get("typed", "")
        result = SELF_RESULT[rating]
    latency = request.form.get("latency_ms", type=int)
    grade_ms = request.form.get("grade_ms", type=int)
    if fmt == "choice":
        why = rush.verdict("grammar", result, rating, picked or "", (), latency, grade_ms, typed=False)
    elif fmt == "boxes":
        responses = request.form.getlist("box")
        why = rush.verdict("grammar", result, rating, " ".join(responses),
                           [" ".join((b.get("answer") or [""])[0] for b in item.get("boxes") or [])],
                           latency, grade_ms, boxes=len(responses))
    elif fmt == "tag-then-translate":
        why = rush.verdict("grammar", result, rating, typed or "", [], latency, grade_ms,
                           typed=False, boxes=2 * len(item.get("tag_boxes") or []))
    else:                                 # self-check: no check of its own
        why = rush.verdict("grammar", None, rating, typed or "", [], latency, grade_ms)
        if not (typed or "").strip() and rating >= fsrs.GOOD:
            why = why + ["graded_up"]
    store.record_event(db, student, item_id, item.get("node"),
                       practice.response_summary(item, box_results, picked, typed),
                       result, latency_ms=latency, context=ctx, version="v1",
                       rating=rating, grade_ms=grade_ms, rush=rush.encode(why))
    key = request.form.get("reason_key", "")
    if key:
        contested = (key == practice.CONTEST_KEY)
        store.record_miss_reason(db, student, item_id, row["node_id"], key,
                                 request.form.get("reason_text", ""),
                                 request.form.get("reason_node") or None, contested=contested)
        if contested:
            store.flag_item_live_fire(db, item_id, f"a student contested this question ({student})")
    return redirect(url_for("practice_session", node=node or "", context=ctx))


@app.route("/practice/selfreport", methods=["POST"])
def practice_selfreport():
    """Self-check and the translation half of tag-then-translate: the student
    reports how they did. What they typed is stored next to what they claimed."""
    db = get_db()
    student = current_student()
    item_id = request.form["item_id"]
    node = request.form.get("node") or None
    ctx = request.form.get("context", "practice")
    reported = request.form.get("reported", "")
    typed = request.form.get("typed", "")
    row = store.get_item(db, item_id)
    if row is None:
        abort(404)
    item = row["payload"]
    result = {"had": "right", "close": "close", "missed": "wrong"}.get(reported, "wrong")
    store.record_event(db, student, item_id, item.get("node"),
                       f"[self:{reported}] {typed}"[:200], result,
                       context=ctx, version="v1")
    if result == "wrong":
        return render_template("practice_feedback.html", student=student, item=item,
                               node=node, context=ctx, result="wrong",
                               introduced=nodeweek(item.get("node")),
                               box_results=None, tag_results=None, picked=None,
                               typed=typed, menu=practice.menu_for(item),
                               teaching=approved_teaching_for(db, item.get("node")),
                               label=_NODE_LABEL.get(item["node"], ""), self_done=True)
    return redirect(url_for("practice_session", node=node or "", context=ctx))


@app.route("/practice/menu", methods=["POST"])
def practice_menu():
    """Record what the student said went wrong, tagged to the node that explains
    that mistake. Contesting a question returns it to the flagged queue — this
    is the live-fire path."""
    db = get_db()
    student = current_student()
    item_id = request.form["item_id"]
    node = request.form.get("node") or None
    ctx = request.form.get("context", "practice")
    key = request.form.get("reason_key", "")
    text = request.form.get("reason_text", "")
    reason_node = request.form.get("reason_node") or None
    contested = (key == practice.CONTEST_KEY)

    row = store.get_item(db, item_id)
    item_node = row["node_id"] if row else None
    store.record_miss_reason(db, student, item_id, item_node, key, text,
                             reason_node, contested=contested)
    if contested:
        store.flag_item_live_fire(
            db, item_id, f"a student contested this question ({student})")
    return redirect(url_for("practice_session", node=node or "", context=ctx))


# ==========================================================================
# Proctored quizzes — frozen, hand-picked, no feedback until submit
# ==========================================================================

def _items_by_id(db, item_ids):
    out = {}
    for iid in item_ids:
        row = store.get_item(db, iid)
        if row is not None:
            out[iid] = row["payload"]
    return out


@app.route("/quiz")
def quiz_index():
    db = get_db()
    return render_template("quiz_index.html", quizzes=store.list_quizzes(db))


@app.route("/quiz/new", methods=["GET", "POST"])
def quiz_new():
    db = get_db()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip() or "Untitled quiz"
        ctx = request.form.get("context", "quiz")
        if ctx not in VALID_CONTEXTS or ctx == "practice":
            ctx = "quiz"
        picked = request.form.getlist("item")
        if not picked:
            return redirect(url_for("quiz_new"))
        qid = quizlib.new_quiz_id()
        store.create_quiz(db, qid, title, picked, context=ctx)
        return redirect(url_for("quiz_show", quiz_id=qid))

    approved = store.approved_items(db)
    taught = _taught_now()
    rows = [{"id": it["id"], "node": it["node"], "label": _NODE_LABEL.get(it["node"], ""),
             "stem": it.get("stem", ""), "assess": it.get("assess"), "tier": it.get("tier"),
             "fmt": it.get("format"), "taught": it["node"] in taught}
            for it in approved]
    rows.sort(key=lambda r: (r["node"], r["id"]))
    return render_template("quiz_new.html", rows=rows,
                           n_taught=sum(1 for r in rows if r["taught"]))


@app.route("/quiz/<quiz_id>")
def quiz_show(quiz_id):
    db = get_db()
    q = store.get_quiz(db, quiz_id)
    if q is None:
        abort(404)
    items = _items_by_id(db, q["item_ids"])
    attempts = store.quiz_attempts(db, quiz_id)
    rows = []
    for a in attempts:
        summ = quizlib.summarise(a["results"]) if a["results"] else None
        rows.append({"student": a["student_id"],
                     "submitted": bool(a["submitted_at"]), "summary": summ})
    return render_template("quiz_show.html", q=q, items=items, attempts=rows,
                           n=len(q["item_ids"]))


@app.route("/quiz/<quiz_id>/toggle", methods=["POST"])
def quiz_toggle(quiz_id):
    db = get_db()
    q = store.get_quiz(db, quiz_id)
    if q is None:
        abort(404)
    store.set_quiz_open(db, quiz_id, not q["open"])
    return redirect(url_for("quiz_show", quiz_id=quiz_id))


# ---- student side ----

@app.route("/q/<quiz_id>")
def quiz_start(quiz_id):
    db = get_db()
    q = store.get_quiz(db, quiz_id)
    if q is None:
        abort(404)
    return render_template("quiz_start.html", q=q, n=len(q["item_ids"]),
                           student=current_student())


@app.route("/q/<quiz_id>/take")
def quiz_take(quiz_id):
    db = get_db()
    q = store.get_quiz(db, quiz_id)
    if q is None:
        abort(404)
    student = current_student()
    if not student:
        return redirect(url_for("quiz_start", quiz_id=quiz_id))
    attempt = store.get_or_start_attempt(db, quiz_id, student)
    if attempt["submitted_at"]:
        return redirect(url_for("quiz_results", quiz_id=quiz_id))
    if not q["open"]:
        return render_template("quiz_closed.html", q=q)

    pos = request.args.get("n", type=int) or 1
    pos = max(1, min(pos, len(q["item_ids"])))
    iid = q["item_ids"][pos - 1]
    row = store.get_item(db, iid)
    if row is None:
        abort(404)
    items = _items_by_id(db, q["item_ids"])
    return render_template(
        "quiz_take.html", q=q, item=row["payload"], pos=pos, total=len(q["item_ids"]),
        student=student, saved=attempt["answers"].get(iid),
        answered=quizlib.answered_count(items, q["item_ids"], attempt["answers"]),
        label=_NODE_LABEL.get(row["payload"].get("node"), ""))


@app.route("/q/<quiz_id>/save", methods=["POST"])
def quiz_save(quiz_id):
    db = get_db()
    q = store.get_quiz(db, quiz_id)
    if q is None:
        abort(404)
    student = current_student()
    iid = request.form["item_id"]
    pos = request.form.get("pos", type=int) or 1
    goto = request.form.get("goto", "next")

    row = store.get_item(db, iid)
    fmt = row["payload"].get("format") if row else None
    if fmt == "choice":
        value = request.form.get("picked")
    elif fmt == "boxes":
        value = request.form.getlist("box")
    elif fmt == practice.LABEL_WORDS:
        value = {"pick": request.form.getlist("pick"), "typed": request.form.get("typed", "")}
    elif fmt == "tag-then-translate":
        value = {"case": request.form.getlist("case"),
                 "job": request.form.getlist("job"),
                 "typed": request.form.get("typed", "")}
    else:
        value = request.form.get("typed", "")

    attempt = store.get_or_start_attempt(db, quiz_id, student)
    store.save_attempt_answer(db, attempt["attempt_id"], iid, value)

    if goto == "check":
        return redirect(url_for("quiz_check", quiz_id=quiz_id))
    nxt = pos + 1 if goto == "next" else pos - 1
    if nxt > len(q["item_ids"]):
        return redirect(url_for("quiz_check", quiz_id=quiz_id))
    return redirect(url_for("quiz_take", quiz_id=quiz_id, n=max(1, nxt)))


@app.route("/q/<quiz_id>/check")
def quiz_check(quiz_id):
    db = get_db()
    q = store.get_quiz(db, quiz_id)
    if q is None:
        abort(404)
    student = current_student()
    attempt = store.get_or_start_attempt(db, quiz_id, student)
    if attempt["submitted_at"]:
        return redirect(url_for("quiz_results", quiz_id=quiz_id))
    items = _items_by_id(db, q["item_ids"])
    blanks = quizlib.unanswered_positions(items, q["item_ids"], attempt["answers"])
    return render_template("quiz_check.html", q=q, student=student, blanks=blanks,
                           total=len(q["item_ids"]))


@app.route("/q/<quiz_id>/submit", methods=["POST"])
def quiz_submit(quiz_id):
    db = get_db()
    q = store.get_quiz(db, quiz_id)
    if q is None:
        abort(404)
    student = current_student()
    attempt = store.get_or_start_attempt(db, quiz_id, student)
    if attempt["submitted_at"]:
        return redirect(url_for("quiz_results", quiz_id=quiz_id))

    items = _items_by_id(db, q["item_ids"])
    results = quizlib.grade_attempt(items, q["item_ids"], attempt["answers"])
    store.submit_attempt(db, attempt["attempt_id"], results)
    # One event per question, carrying the quiz's context so proctored work is
    # distinguishable from practice in the same history.
    for row in quizlib.events_for_attempt(results, items, q["context"]):
        store.record_event(db, student, row["item_id"], row["spec_node_id"],
                           row["response"], row["result"],
                           context=row["context"], version=row["version"])
    return redirect(url_for("quiz_results", quiz_id=quiz_id))


@app.route("/q/<quiz_id>/results")
def quiz_results(quiz_id):
    db = get_db()
    q = store.get_quiz(db, quiz_id)
    if q is None:
        abort(404)
    student = current_student()
    attempt = store.get_or_start_attempt(db, quiz_id, student)
    if not attempt["submitted_at"]:
        return redirect(url_for("quiz_check", quiz_id=quiz_id))
    items = _items_by_id(db, q["item_ids"])
    rows = []
    for i, iid in enumerate(q["item_ids"], start=1):
        item = items.get(iid)
        if item is None:
            continue
        rows.append({"pos": i, "item": item, "res": attempt["results"].get(iid, {}),
                     "teaching": approved_teaching_for(db, item.get("node")),
                     "menu": practice.menu_for(item),
                     "label": _NODE_LABEL.get(item.get("node"), "")})
    return render_template("quiz_results.html", q=q, student=student, rows=rows,
                           summary=quizlib.summarise(attempt["results"]))


# --------------------------------------------------------------------------
# Practice NLE: past National Latin Exams, sat straight through (nle.py)
#
# A sitting is stored as a quiz of its own (context "nle") with the student's
# one attempt, so it is saved as they go, backed up and wiped at year end like
# any quiz. Only the student who started it can open it.
# --------------------------------------------------------------------------

def _nle_live(db):
    """Past-NLE question ids still approved (the teacher may reject one)."""
    rows = db.execute("SELECT item_id FROM items WHERE review_status='approved' AND item_id LIKE ?",
                      (nle.PREFIX + "%",)).fetchall()
    return {r["item_id"] for r in rows}


def _nle_sitting(db, sid):
    """(quiz, attempt) for the signed-in student's own sitting, or abort."""
    q = store.get_quiz(db, sid)
    student = current_student()
    if q is None or q.get("context") != nle.CONTEXT or not student:
        abort(404)
    attempt = store.find_attempt(db, sid, student)
    if attempt is None:
        abort(404)
    return q, attempt


def _nle_score(results):
    right = sum(1 for r in (results or {}).values() if r.get("result") in ("right", "close"))
    return right, len(results or {})


@app.route("/nle")
def nle_home():
    db = get_db()
    student = current_student()
    sittings = store.student_sittings(db, student) if student else []
    going = [s for s in sittings if not s["submitted_at"]]
    done = []
    best = {}
    for s in sittings:
        if s["submitted_at"]:
            right, total = _nle_score(s["results"])
            done.append(dict(s, right=right, total=total))
            best[s["title"]] = max(best.get(s["title"], 0), right)
    exams = [{"id": e["id"], "name": e["name"], "kind": e["kind"], "n": len(e["items"]),
              "best": best.get(e["name"])} for e in _NLE]
    return render_template("nle_home.html", student=student, going=going, done=done[:12],
                           exams=exams, sizes=nle.MASHUP_SIZES)


@app.route("/nle/start", methods=["POST"])
def nle_start():
    db = get_db()
    student = current_student()
    live = _nle_live(db)
    if request.form.get("kind") == "exam":
        exam = _NLE_BY_ID.get(request.form.get("exam") or "")
        if exam is None:
            abort(404)
        title, ids = exam["name"], nle.exam_ids(exam, live)
        # Starting an exam already under way carries on with it.
        going = next((x for x in store.student_sittings(db, student)
                      if x["title"] == title and not x["submitted_at"]), None)
        if going:
            return redirect(url_for("nle_take", sid=going["quiz_id"]))
    else:
        size = request.form.get("size", type=int) or nle.MASHUP_SIZES[0]
        size = size if size in nle.MASHUP_SIZES else nle.MASHUP_SIZES[0]
        seen = {e["item_id"] for e in store.events_for_student(db, student)
                if e.get("context") == nle.CONTEXT}
        sid_seed = "%s|%s" % (student, time.time())
        title = "Mash-up · %d questions" % size
        ids = nle.mashup(_NLE, live, _taught_now(), size, sid_seed, seen)
    if not ids:
        return redirect(url_for("nle_home"))
    sid = "nle-" + quizlib.new_quiz_id()
    store.create_quiz(db, sid, title, ids, context=nle.CONTEXT)
    store.get_or_start_attempt(db, sid, student)
    return redirect(url_for("nle_take", sid=sid))


def _nle_passage(item):
    """The reading passage this question belongs to, ready for the page."""
    pid = item.get("passage")
    if not pid:
        return None
    exam = _NLE_BY_ID.get((item.get("nle") or {}).get("exam"))
    p = (exam or {}).get("passages", {}).get(pid)
    if p is None:
        return None
    return dict(p, lines=[dict(l, html=Markup(nle.mark_up(l["latin"], l.get("underline"))))
                          for l in p["lines"]])


@app.route("/nle/s/<sid>")
def nle_take(sid):
    db = get_db()
    q, attempt = _nle_sitting(db, sid)
    if attempt["submitted_at"]:
        return redirect(url_for("nle_results", sid=sid))
    ids = q["item_ids"]
    pos = max(1, min(request.args.get("n", type=int) or 1, len(ids)))
    items = _items_by_id(db, ids)
    item = items.get(ids[pos - 1])
    if item is None:
        abort(404)
    answers = attempt["answers"]
    return render_template(
        "nle_take.html", q=q, sid=sid, item=item, pos=pos, total=len(ids),
        saved=answers.get(item["id"]), passage=_nle_passage(item), hi=nle.look_back(item),
        covered=nle.covered(item, _taught_now()),
        grid=[{"n": i, "done": bool(answers.get(iid))} for i, iid in enumerate(ids, 1)],
        answered=sum(1 for iid in ids if answers.get(iid)), student=current_student())


@app.route("/nle/s/<sid>/save", methods=["POST"])
def nle_save(sid):
    db = get_db()
    q, attempt = _nle_sitting(db, sid)
    if attempt["submitted_at"]:
        return redirect(url_for("nle_results", sid=sid))
    iid = request.form.get("item_id", "")
    picked = request.form.get("picked")
    if iid in q["item_ids"] and picked:
        store.save_attempt_answer(db, attempt["attempt_id"], iid, picked)
    pos = request.form.get("pos", type=int) or 1
    goto = request.form.get("goto", "next")
    if goto == "finish":
        return redirect(url_for("nle_finish", sid=sid))
    if goto == "back":
        nxt = pos - 1
    elif goto.isdigit():
        nxt = int(goto)
    else:
        nxt = pos + 1
    if nxt > len(q["item_ids"]):
        return redirect(url_for("nle_finish", sid=sid))
    return redirect(url_for("nle_take", sid=sid, n=max(1, nxt)))


@app.route("/nle/s/<sid>/finish")
def nle_finish(sid):
    db = get_db()
    q, attempt = _nle_sitting(db, sid)
    if attempt["submitted_at"]:
        return redirect(url_for("nle_results", sid=sid))
    blanks = [i for i, iid in enumerate(q["item_ids"], 1) if not attempt["answers"].get(iid)]
    return render_template("nle_finish.html", q=q, sid=sid, blanks=blanks,
                           total=len(q["item_ids"]), student=current_student())


@app.route("/nle/s/<sid>/submit", methods=["POST"])
def nle_submit(sid):
    db = get_db()
    q, attempt = _nle_sitting(db, sid)
    if not attempt["submitted_at"]:
        items = _items_by_id(db, q["item_ids"])
        results = quizlib.grade_attempt(items, q["item_ids"], attempt["answers"])
        store.submit_attempt(db, attempt["attempt_id"], results)
        for row in quizlib.events_for_attempt(results, items, nle.CONTEXT):
            store.record_event(db, current_student(), row["item_id"], row["spec_node_id"],
                               row["response"], row["result"],
                               context=row["context"], version=row["version"])
    return redirect(url_for("nle_results", sid=sid))


def _nle_help(db, item, approvals):
    """What a miss offers: the hint (approved teaching text, else the lesson's
    line to remember, else the lines of the passage to look back at) and the
    lesson, when its badge has an approved one."""
    node = item.get("node")
    bid = _NODE_BADGE.get(node)
    lesson = lesson_for(db, bid, approvals) if bid else None
    out = {"label": _NODE_LABEL.get(node, node), "teaching": approved_teaching_for(db, node),
           "lesson": None, "remember": None, "lines": None}
    if lesson is not None:
        out["lesson"] = {"bid": bid, "n": _LESSON_NO[bid], "title": _BADGE_BY_ID[bid]["title"]}
        rem = next((st["remember"] for st in lesson["steps"] if lessons.kind(st) == "remember"), "")
        out["remember"] = Markup(lessons.inline(rem))
    span = nle.look_back(item)
    passage = _nle_passage(item)
    if span and passage:
        out["lines"] = [l for l in passage["lines"] if span[0] <= l["n"] <= span[1]]
    return out


@app.route("/nle/s/<sid>/results")
def nle_results(sid):
    db = get_db()
    q, attempt = _nle_sitting(db, sid)
    if not attempt["submitted_at"]:
        return redirect(url_for("nle_finish", sid=sid))
    items = _items_by_id(db, q["item_ids"])
    taught = _taught_now()
    approvals = store.teaching_approvals(db)
    rows, topics = [], {}
    for i, iid in enumerate(q["item_ids"], 1):
        item = items.get(iid)
        if item is None:
            continue
        res = attempt["results"].get(iid, {})
        ok = res.get("result") in ("right", "close")
        row = {"pos": i, "item": item, "ok": ok, "picked": res.get("picked"),
               "covered": nle.covered(item, taught), "passage": _nle_passage(item)}
        if not ok:
            row["help"] = _nle_help(db, item, approvals)
            t = topics.setdefault(item["node"], {"node": item["node"], "help": row["help"],
                                                 "missed": [], "covered": row["covered"]})
            t["missed"].append(i)
        rows.append(row)
    right, total = _nle_score(attempt["results"])
    cov = [r for r in rows if r["covered"]]
    work_on = sorted(topics.values(), key=lambda t: (not t["covered"], -len(t["missed"]), t["node"]))
    return render_template(
        "nle_results.html", q=q, sid=sid, rows=rows, right=right, total=total,
        award=nle.score_award(right, total), work_on=work_on,
        covered_right=sum(1 for r in cov if r["ok"]), covered_total=len(cov),
        back=url_for("nle_results", sid=sid), student=current_student())


@app.route("/teacher/nle")
def teacher_nle():
    """Every past exam in the app, and the class's practice NLEs."""
    db = get_db()
    live = _nle_live(db)
    exams = []
    for e in _NLE:
        n_live = sum(1 for p in e["items"] if p["id"] in live)
        exams.append({"id": e["id"], "name": e["name"], "n": len(e["items"]), "live": n_live,
                      "badge": sum(1 for p in e["items"] if not p.get("exam_only")
                                   and p["node"] in _NODE_BADGE)})
    sittings = []
    for s in store.context_sittings(db)[:60]:
        right, total = _nle_score(s["results"])
        sittings.append(dict(s, right=right, total=total,
                             when=time.strftime("%a %b %-d, %-I:%M %p", time.localtime(s["submitted_at"]))))
    return render_template("teacher_nle.html", exams=exams, sittings=sittings,
                           n_items=sum(e["n"] for e in exams))


@app.route("/teacher/nle/<exam_id>")
def teacher_nle_exam(exam_id):
    """One past exam as the app has it: each question, the answer the app
    marks right, and the topic it is filed under -- to check the key."""
    db = get_db()
    e = _NLE_BY_ID.get(exam_id)
    if e is None:
        abort(404)
    items = _items_by_id(db, [p["id"] for p in e["items"]])
    status = {r["item_id"]: r["review_status"] for r in db.execute(
        "SELECT item_id, review_status FROM items WHERE item_id LIKE ?",
        (nle.PREFIX + e["id"] + "-%",)).fetchall()}
    rows = []
    for p in e["items"]:
        it = items.get(p["id"], p)
        rows.append({"item": it, "status": status.get(p["id"], "?"),
                     "label": _NODE_LABEL.get(it["node"], it["node"]),
                     "badge": _BADGE_BY_ID[_NODE_BADGE[it["node"]]]["title"]
                     if it["node"] in _NODE_BADGE and not it.get("exam_only") else None,
                     "passage": _nle_passage(it)})
    return render_template("teacher_nle_exam.html", e=e, rows=rows)


@app.route("/drill/progress")
def drill_progress():
    db = get_db()
    student = current_student()
    events = store.events_for_student(db, student)
    rows = drill.progress_table(_DRILL_WORDS, events)
    summary = drill.progress_summary(rows)
    # Grammar sits on the same page, counted over the same topics the bar on
    # every question counts, so a student never sees two different answers.
    approved = store.approved_items(db)
    universe = {it["node"] for it in approved if it["node"] in _taught_now()}
    grammar = stats.grammar_progress(_SPEC, universe, events)
    gtotals = {"solid": 0, "shaky": 0, "not yet": 0}
    for g in grammar:
        for k in gtotals:
            gtotals[k] += g["counts"][k]
    return render_template("drill_progress.html", student=student, rows=rows,
                           summary=summary, week_labels=drill.WEEK_LABELS,
                           grammar=grammar, gtotals=gtotals,
                           gtotal=sum(gtotals.values()))


@app.route("/homework")
def homework_page():
    """Every homework week so far, newest first, and the all-time totals."""
    db = get_db()
    events = store.events_for_student(db, current_student())
    rule = badge_rule(db)
    history = homework_history(db, events, rule=rule)
    return render_template("homework.html", history=list(reversed(history)),
                           alltime=goals.all_time(events, history),
                           goal=goals.weekly_progress(events, weekly_targets(db), badge_rule=rule),
                           badge_titles={b["id"]: b["title"] for b in _BADGES})


# ==========================================================================
# The teacher dashboard
#
# Everything here answers one of two questions: did they practice, and what do
# they know. Both are read-only views over the same event history the students
# see; nothing on these pages writes an event or touches a grade.
#
# The roster is what makes the first question answerable. A student who did
# nothing leaves no events, so without a class list the dashboard could only
# ever show the kids who showed up.
# ==========================================================================

# ==========================================================================
# Deadlines: the weekly goal, and the quizzes and tests students prepare for
# ==========================================================================

ASSESSMENT_KINDS = [("quiz", "Quiz"), ("test", "Test"), ("exam", "Exam")]


def _week_topics(weeks, approved_counts):
    """Every spec topic taught in the given weeks, for the teacher's tick list."""
    rows = []
    for nid, n in _SPEC.items():
        if str(n.get("week")) in weeks:
            rows.append({"node": nid, "label": n.get("label", nid),
                         "week": str(n.get("week")), "day": str(n.get("day") or ""),
                         "questions": approved_counts.get(nid, 0)})
    rows.sort(key=lambda r: (r["day"], r["node"]))
    return rows


@app.route("/teacher/deadlines", methods=["GET", "POST"])
def teacher_deadlines():
    db = get_db()
    saved = None
    if request.method == "POST" and request.form.get("form") == "rushed":
        store.set_setting(db, "count_rushed", request.form.get("count_rushed") == "yes")
        saved = "rushed"
    elif request.method == "POST" and request.form.get("form") == "badges":
        start = (request.form.get("badges_from") or "").strip()
        if start and goals.days_until(start) is None:
            saved = "bad"
        else:
            store.set_setting(db, "badges",
                              {"from": goals.week_key(goals.key_start(start)) if start else None})
            saved = "badges"
    elif request.method == "POST" and request.form.get("form") == "homework":
        start = (request.form.get("from") or "").strip()
        if goals.days_until(start) is None:
            saved = "badweeks"
        else:
            first = goals.week_key(goals.key_start(start))
            listed = set(request.form.getlist("listed"))
            ticked = set(request.form.getlist("on"))
            off = set(homework_setting(db)["off"]) - listed | (listed - ticked)
            store.set_setting(db, "homework", {"from": first, "off": sorted(off)})
            saved = "weeks"
    elif request.method == "POST":
        try:
            targets = {k: max(0, int(request.form.get(k, ""))) for k in goals.DEFAULT_TARGETS}
            store.set_setting(db, "weekly_goal", targets)
            saved = "goal"
        except ValueError:
            saved = "bad"
    today = time.strftime("%Y-%m-%d")
    rows = []
    for a in store.list_assessments(db):
        a["when"] = goals.when_label(a["due_date"])
        a["past"] = a["due_date"] < today
        rows.append(a)
    hs = homework_setting(db)
    # Every week from the first to the end of the teaching calendar, so a
    # vacation can be marked before it arrives.
    last_teaching = max(goals.all_weeks(_SPEC, _DRILL_WORDS) or [hs["from"]])
    until = max(last_teaching, goals.week_key(time.time()))
    hw_weeks = [{"key": k, "label": goals.week_label(k), "on": k not in hs["off"]}
                for k in goals.homework_weeks(hs["from"], (), until=until)]
    this = goals.week_key(time.time())
    badge_weeks = [{"key": k, "label": goals.week_label(k)}
                   for k in goals.homework_weeks(this, (), until=until)[:6]]
    return render_template("teacher_deadlines.html", targets=weekly_targets(db),
                           count_rushed=count_rushed_setting(db),
                           badges_from=badges_from(db), badge_weeks=badge_weeks,
                           homework=hs, hw_weeks=hw_weeks,
                           this_week=goals.week_key(time.time()),
                           assessments=rows, saved=saved, kinds=dict(ASSESSMENT_KINDS))


@app.route("/teacher/deadlines/edit", methods=["GET", "POST"])
def teacher_deadline_edit():
    db = get_db()
    aid = request.values.get("id") or None
    current = store.get_assessment(db, aid) if aid else None
    if aid and current is None:
        abort(404)
    all_weeks = goals.all_weeks(_SPEC, _DRILL_WORDS)
    error = None
    if request.method == "POST":
        if request.form.get("action") == "delete" and current:
            store.delete_assessment(db, aid)
            return redirect(url_for("teacher_deadlines"))
        title = (request.form.get("title") or "").strip()
        kind = request.form.get("kind") or "quiz"
        due = (request.form.get("due_date") or "").strip()
        weeks = [w for w in request.form.getlist("week") if w in all_weeks]
        if not title:
            error = "Give it a title students will recognize, like \"Quiz: first declension\"."
        elif goals.days_until(due) is None:
            error = "Pick a date."
        elif not weeks:
            error = "Tick at least one week, or there is nothing for students to prepare."
        if not error:
            excluded = set(current["excluded_nodes"]) if current else set()
            listed = set(request.form.getlist("listed")) if request.form.get("topics_shown") else set()
            ticked = set(request.form.getlist("node"))
            # A week newly ticked brings its grammar topics in and leaves the
            # other strands -- Roman world, modern world, reading strategy --
            # offered but unticked. Two weeks of class is fifty topics across
            # every strand; a quiz on the nominative and accusative is not
            # testing the Norman Conquest, and its page should not say it is.
            added = set(weeks) - set((current or {}).get("weeks") or [])
            default_off = {nid for nid, n in _SPEC.items()
                           if str(n.get("week")) in added and not nid.startswith("MS-")}
            excluded = (excluded - listed) | (listed - ticked) | (default_off - listed)
            aid = store.save_assessment(db, title, kind, due, weeks, excluded,
                                        assessment_id=aid)
            return redirect(url_for("teacher_deadline_edit", id=aid, saved=1))
        current = {"id": aid, "title": title, "kind": kind, "due_date": due,
                   "weeks": weeks, "excluded_nodes": (current or {}).get("excluded_nodes", [])}
    approved_counts = {}
    for it in store.approved_items(db):
        approved_counts[it["node"]] = approved_counts.get(it["node"], 0) + 1
    topics = _week_topics(set((current or {}).get("weeks") or []), approved_counts)
    words = [w for w in _DRILL_WORDS
             if goals.word_week_date(w) in set((current or {}).get("weeks") or [])]
    return render_template("teacher_deadline_edit.html", a=current, all_weeks=all_weeks,
                           topics=topics, n_words=len(words), kinds=ASSESSMENT_KINDS,
                           error=error, saved=request.args.get("saved"))


@app.route("/due/<aid>")
def assessment_page(aid):
    """What a quiz or test covers, and where this student stands on it."""
    db = get_db()
    student = current_student()
    a = store.get_assessment(db, aid)
    if a is None:
        abort(404)
    nodes, words = goals.scope(a, _SPEC, _DRILL_WORDS, _practiceable(db))
    events = store.events_for_student(db, student)
    ready = goals.readiness(nodes, words, events, _SPEC)
    order = {w: i for i, w in enumerate(drill.WEEK_ORDER)}
    word_weeks = sorted({w["week"] for w in words}, key=lambda w: order.get(w, 99))
    # A trailing comma marks a set even when it holds one member, which is what
    # tells the practice and drill screens to scope rather than pick one topic.
    return render_template("assessment.html", a=a, ready=ready,
                           when=goals.when_label(a["due_date"]),
                           days=goals.days_until(a["due_date"]),
                           kind=dict(ASSESSMENT_KINDS).get(a["kind"], "Quiz"),
                           topics_param=",".join(nodes) + ",",
                           weeks_param=",".join(word_weeks) + ",",
                           word_weeks=word_weeks, week_labels=drill.WEEK_LABELS)


# Negative values are homework weeks (Saturday to Friday), the same weeks the
# students' home screens count.
THIS_HOMEWORK_WEEK, LAST_HOMEWORK_WEEK = -1, -2
WINDOW_CHOICES = [(THIS_HOMEWORK_WEEK, "This homework week (Sat–Fri)"),
                  (LAST_HOMEWORK_WEEK, "Last homework week"),
                  (1, "Today"), (2, "Since yesterday"), (7, "Last 7 days"),
                  (30, "Last 30 days"), (0, "All time")]


def _window_args(default=7):
    """Read the window and block filter off the query string, once."""
    days = request.args.get("days", type=int)
    if days is None:
        days = default
    section = request.args.get("section") or None
    now = time.time()
    if days == THIS_HOMEWORK_WEEK:
        since, until = goals.week_start(now), now
    elif days == LAST_HOMEWORK_WEEK:
        this = goals.week_start(now)
        since, until = goals.week_start(this - 3600), this - 0.001
    elif days <= 0:
        since, until = None, None
    else:
        since, until = teacher.window_bounds(days=days)
    return {"days": days, "section": section, "since": since, "until": until}


def _window_label(days):
    for d, lab in WINDOW_CHOICES:
        if d == days:
            return lab
    return "Last %d days" % days


def _vocab_universe():
    return {drill._key(w["latin"]) for w in _DRILL_WORDS}


def _grammar_universe(db):
    """The nodes a student could actually have met: approved questions whose
    lesson has been taught. Anything else would put a topic in the 'not yet'
    column that was never on the table."""
    taught = _taught_now()
    return {it["node"] for it in store.approved_items(db) if it["node"] in taught}


def _topic_label(topic):
    return "Vocabulary" if topic == "vocab" else "%s %s" % (topic, _NODE_LABEL.get(topic, ""))


@app.route("/teacher")
def teacher_home():
    db = get_db()
    w = _window_args(default=THIS_HOMEWORK_WEEK)
    roster_rows = store.roster(db, active_only=True, section=w["section"])
    events = store.all_events(db, since=w["since"], until=w["until"], section=w["section"])
    targets = weekly_targets(db)
    rule = badge_rule(db)
    this = goals.week_start()
    badge_now = bool(rule and goals.week_key(this) >= rule["from"])
    if badge_now:
        targets = dict(targets, grammar=0)          # grammar is badges this week
    table = teacher.class_activity(roster_rows, events, w["since"], w["until"],
                                   targets=targets)
    # Rushed sittings in the window (rush.py): a flag for a look, not a verdict.
    by_sid = teacher.by_student(events)
    if badge_now:
        # This homework week's badges, whatever the window: "did it" needs them.
        mine = teacher.by_student(store.all_events(db, section=w["section"]))
        for r in table["rows"]:
            r["badges"] = goals.badge_week(mine.get(r["student_id"], []), rule,
                                           this, goals.week_end(this))
            if r["state"] == "done" and r["badges"]["missing"]:
                r["state"] = "started"
        table["n_done"] = sum(1 for x in table["rows"] if x["state"] == "done")
        table["n_started"] = sum(1 for x in table["rows"] if x["state"] == "started")
    for r in table["rows"]:
        r["flags"] = rush.flagged_sittings(by_sid.get(r["student_id"], []))
        # Looping a topic (teacher.loops): the biggest day first.
        r["loops"] = sorted(teacher.loops(by_sid.get(r["student_id"], [])),
                            key=lambda x: -x["repeats"])
    table["n_flagged"] = sum(1 for r in table["rows"] if r["flags"])
    table["n_looping"] = sum(1 for r in table["rows"] if r["loops"])
    return render_template("teacher_home.html", w=w, table=table, badge_now=badge_now,
                           rush_reasons=rush.REASONS, topic_label=_topic_label, loop_min=teacher.LOOP_MIN,
                           targets=weekly_targets(db),
                           purge=PURGE_REPORT,
                           window_label=_window_label(w["days"]),
                           windows=WINDOW_CHOICES, sections=store.sections(db),
                           n_roster=len(store.roster(db, active_only=True)))


@app.route("/teacher/knows")
def teacher_knows():
    """What the class finds hard, weakest first — one table for grammar, one
    for vocabulary, because they are different kinds of forgetting."""
    db = get_db()
    w = _window_args()
    events = store.all_events(db, since=w["since"], until=w["until"], section=w["section"])
    nodes = teacher.difficulty(events, teacher.node_key, universe=_grammar_universe(db))
    words = teacher.difficulty(events, teacher.word_key, universe=_vocab_universe())
    glosses = {drill._key(x["latin"]): x for x in _DRILL_WORDS}
    def split(rows):
        """Weak, secure, untouched.

        A page that lists 80 words at 100% alongside the six they are missing
        buries the answer to the only question being asked. The secure and
        untouched rows are kept, but folded away."""
        weak = [r for r in rows if r["attempts"] and r["accuracy"] < teacher.SECURE]
        secure = [r for r in rows if r["attempts"] and r["accuracy"] >= teacher.SECURE]
        return weak, secure, [r for r in rows if not r["attempts"]]
    nodes_w, nodes_s, nodes_u = split(nodes)
    words_w, words_s, words_u = split(words)
    return render_template("teacher_knows.html", w=w,
                           nodes=nodes_w, nodes_secure=nodes_s, nodes_untouched=nodes_u,
                           words=words_w, words_secure=words_s, words_untouched=words_u,
                           secure_pct=int(teacher.SECURE * 100),
                           glosses=glosses, window_label=_window_label(w["days"]),
                           windows=WINDOW_CHOICES, sections=store.sections(db))


@app.route("/teacher/misses")
def teacher_misses():
    db = get_db()
    w = _window_args()
    rows = store.all_miss_reasons(db, since=w["since"], section=w["section"])
    return render_template("teacher_misses.html", w=w,
                           reasons=teacher.miss_reason_counts(rows),
                           contested=teacher.contested_items(rows)[:40],
                           window_label=_window_label(w["days"]),
                           windows=WINDOW_CHOICES, sections=store.sections(db))


def _student_badges(db, events):
    """One student's badges for the teacher: every badge on the map today."""
    today = time.strftime("%Y-%m-%d")
    out = []
    for b in badges.available(_BADGES, _SPEC, store.approved_items(db), today):
        st = badges.status(events, b["id"])
        ms = badges.markers(events, b["id"])
        out.append(dict(st, title=b["title"], last=ms[-1] if ms else None))
    return out


@app.template_filter("badgetitle")
def badgetitle(bid):
    return _BADGE_BY_ID[bid]["title"] if bid in _BADGE_BY_ID else bid


@app.route("/teacher/student/<path:student_id>")
def teacher_student(student_id):
    db = get_db()
    w = _window_args()
    events = store.events_for_student(db, student_id)
    act = teacher.activity(events, w["since"], w["until"])
    person = store.get_student(db, student_id)
    vocab_rows = drill.progress_table(_DRILL_WORDS, events)
    node_rows = teacher.difficulty(events, teacher.node_key, universe=_grammar_universe(db))
    misses = store.miss_reasons_for_student(db, student_id, since=w["since"])
    in_window = teacher.in_window(events, w["since"], w["until"])
    return render_template(
        "teacher_student.html", w=w, student=student_id,
        rushed=list(reversed(rush.flagged_sittings(in_window))), rush_reasons=rush.REASONS,
        looping=list(reversed(teacher.loops(in_window))), topic_label=_topic_label,
        badge_rows=_student_badges(db, events),
        homework=list(reversed(homework_history(db, events))),
        person=person, act=act, has_pin=store.has_pin(db, student_id),

        vocab=drill.progress_summary(vocab_rows), vocab_rows=vocab_rows,
        nodes=node_rows,
        alltime_nodes=stats.alltime_by_node(events, universe=_grammar_universe(db)),
        reasons=teacher.miss_reason_counts(misses)[:10],
        recent=list(reversed(events))[:25],
        window_label=_window_label(w["days"]), windows=WINDOW_CHOICES)


@app.route("/teacher/export.csv")
def teacher_export():
    """The homework table as a spreadsheet, so a printout or a gradebook paste
    never needs the terminal."""
    db = get_db()
    w = _window_args(default=THIS_HOMEWORK_WEEK)
    roster_rows = store.roster(db, active_only=True, section=w["section"])
    events = store.all_events(db, since=w["since"], until=w["until"], section=w["section"])
    table = teacher.class_activity(roster_rows, events, w["since"], w["until"],
                                   targets=weekly_targets(db))
    buf = io.StringIO()
    wtr = csv.writer(buf)
    # student_id, not name. There are no names in this system — the paper that
    # maps a number to a person stays off the machine, so this file is safe to
    # download and safe to lose.
    wtr.writerow(["student_id", "block", "state", "attempts", "days_practiced",
                  "vocab_cards", "grammar_cards", "accuracy_pct", "last_practiced", "window"])
    for r in table["rows"]:
        wtr.writerow([r["student_id"], r["section"] or "", r["state"], r["attempts"],
                      r["days"], r["hw"]["vocab"], r["hw"]["grammar"],
                      "" if r["accuracy"] is None else int(round(r["accuracy"] * 100)),
                      time.strftime("%Y-%m-%d %H:%M", time.localtime(r["last_at"])) if r["last_at"] else "",
                      _window_label(w["days"])])
    name = "practice-%s.csv" % time.strftime("%Y-%m-%d")
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=" + name})


def _class_homework(db, section=None):
    """(weeks newest first, rows) -- every rostered student's homework weeks."""
    roster_rows = store.roster(db, active_only=True, section=section)
    grouped = teacher.by_student(store.all_events(db, section=section))
    hs = homework_setting(db)
    weeks = goals.homework_weeks(hs["from"], hs["off"])
    targets = weekly_targets(db)
    rule = badge_rule(db)
    rows = []
    for r in roster_rows:
        hist = goals.homework_history(grouped.get(r["student_id"], []), targets, weeks,
                                      badge_rule=rule)
        rows.append({"student_id": r["student_id"], "section": r.get("section"),
                     "weeks": list(reversed(hist)),
                     "summary": goals.all_time([], hist)})
    rows.sort(key=lambda x: (x["section"] or "", x["student_id"]))
    return list(reversed(weeks)), rows


@app.route("/teacher/homework")
def teacher_homework():
    """The gradebook view: one row per student, one column per homework week."""
    db = get_db()
    section = request.args.get("section") or None
    weeks, rows = _class_homework(db, section)
    return render_template("teacher_homework.html", weeks=weeks, rows=rows,
                           labels={k: goals.week_label(k) for k in weeks},
                           section=section, sections=store.sections(db),
                           targets=weekly_targets(db))


@app.route("/teacher/homework.csv")
def teacher_homework_export():
    """The same grid as a spreadsheet, for pasting into the gradebook."""
    db = get_db()
    section = request.args.get("section") or None
    weeks, rows = _class_homework(db, section)
    buf = io.StringIO()
    wtr = csv.writer(buf)
    # student_id, not name: see teacher_export.
    wtr.writerow(["student_id", "block"] + [goals.week_label(k) for k in weeks])
    for r in rows:
        cells = []
        for h in r["weeks"]:
            if h["status"] in ("on time", "late"):
                cells.append(h["status"])
            elif h.get("badges"):
                b = h["badges"]
                cells.append("%s (vocab %d/%d, badges %d/%d)" % (
                    h["status"], h["counts"]["vocab"], h["targets"]["vocab"],
                    len(b["required"]) - len(b["missing"]), len(b["required"])))
            else:
                cells.append("%s (%d/%d)" % (h["status"], h["total"], h["goal"]))
        wtr.writerow([r["student_id"], r["section"] or ""] + cells)
    name = "homework-%s.csv" % time.strftime("%Y-%m-%d")
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=" + name})


# --------------------------------------------------------------------------
# Data for analysis: every answer, sitting and skill, split around an exam
# --------------------------------------------------------------------------

def _skill_catalog():
    """{(kind, skill_id): {"name", "unit", "week"}} for every skill there is."""
    cat = {}
    for nid, n in _SPEC.items():
        cat[("grammar", nid)] = {"name": n.get("label", ""), "unit": n.get("unit", ""),
                                 "week": str(n.get("week") or "")}
    for w in _DRILL_WORDS:
        cat[("vocab", drill._key(w["latin"]))] = {
            "name": "%s = %s" % (w["latin"], ", ".join(w.get("en") or [])),
            "unit": "", "week": goals.word_week_date(w)}
    for r in _READINGS.values():
        cat[("reading", r["slug"])] = {"name": r.get("title", r["slug"]), "unit": "",
                                       "week": str(r.get("week") or "")}
    return cat


def _analysis_exam(db):
    """(assessment or None, exam date or None) from the query string: a test the
    app knows about, or any date typed in."""
    a = store.get_assessment(db, request.args.get("exam") or "") if request.args.get("exam") else None
    raw = a["due_date"] if a else (request.args.get("date") or "").strip()
    try:
        return a, datetime.date(*time.strptime(raw, "%Y-%m-%d")[:3]) if raw else None
    except ValueError:
        return a, None


@app.route("/teacher/analysis")
def teacher_analysis():
    db = get_db()
    tests = store.list_assessments(db)
    past = [a for a in tests if (goals.days_until(a["due_date"]) or 0) <= 0]
    # The default is the latest test or exam already given, else the latest anything.
    pick = ([a for a in past if a["kind"] in ("test", "exam")] or past or [None])[-1]
    return render_template("teacher_analysis.html", tests=tests, pick=pick,
                           sections=store.sections(db), kinds=dict(ASSESSMENT_KINDS),
                           bad=request.args.get("bad"))


@app.route("/teacher/analysis.zip")
def teacher_analysis_zip():
    """Six spreadsheets and a README in one zip, by student ID only."""
    db = get_db()
    section = request.args.get("section") or None
    a, exam_date = _analysis_exam(db)
    if request.args.get("date") and exam_date is None:
        return redirect(url_for("teacher_analysis", bad="date"))
    nodes, words = goals.scope(a, _SPEC, _DRILL_WORDS, _practiceable(db)) if a else ([], [])
    roster_rows = store.roster(db, active_only=False, section=section)
    events = store.all_events(db, section=section)
    _, hw_rows = _class_homework(db, section)
    quiz_rows = []
    for q in store.list_quizzes(db, include_nle=True):
        for att in store.quiz_attempts(db, q["quiz_id"]):
            if att.get("submitted_at") and (not section or att["student_id"] in
                                            {r["student_id"] for r in roster_rows}):
                quiz_rows.append(dict(att, title=q["title"], context=q["context"]))
    fmts = {r["item_id"]: r["fmt"] or "" for r in
            db.execute("SELECT item_id, fmt FROM items").fetchall()}
    files = analysis.build(
        events, roster_rows, _skill_catalog(), exam_date=exam_date,
        exam_nodes=nodes, exam_words=[drill._key(w["latin"]) for w in words],
        homework={r["student_id"]: r["summary"] for r in hw_rows},
        quiz_rows=quiz_rows, item_formats=fmts)
    if a:
        exam = "%s (%s), %s -- what it covered is marked on_exam" % (
            a["title"], dict(ASSESSMENT_KINDS).get(a["kind"], a["kind"]), a["due_date"])
    elif exam_date:
        exam = "%s (a date only: on_exam is left blank)" % exam_date
    else:
        exam = "none chosen (the before/after columns are blank)"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", analysis.DICTIONARY.format(
            downloaded=time.strftime("%Y-%m-%d %H:%M"), exam=exam,
            block=section or "all blocks"))
        for fname, rows in files.items():
            out = io.StringIO()
            csv.writer(out).writerows(rows)
            z.writestr(fname, out.getvalue())
    name = "latin1-practice-data-%s.zip" % time.strftime("%Y-%m-%d")
    return Response(buf.getvalue(), mimetype="application/zip",
                    headers={"Content-Disposition": "attachment; filename=" + name})


# --------------------------------------------------------------------------
# Word audio: the teacher records each vocabulary word, students hear it
# --------------------------------------------------------------------------

AUDIO_MAX_BYTES = 1500000        # ~30 seconds of the WAV the page records; a word is ~50 KB


def _word_keys():
    return {drill._key(w["latin"]) for w in _DRILL_WORDS}


@app.route("/audio/<key>")
def word_audio(key):
    got = store.get_word_audio(get_db(), key)
    if got is None:
        abort(404)
    mime, data = got
    resp = Response(data, mimetype=mime)
    # The URL carries the recording's version, so it can be cached for good.
    resp.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return resp


@app.route("/teacher/audio")
def teacher_audio():
    """One row per vocabulary word, grouped by week, with a Record button."""
    versions = store.word_audio_versions(get_db())
    groups = []
    for w in _DRILL_WORDS:
        wk = w.get("week") or ""
        if not groups or groups[-1]["week"] != wk:
            groups.append({"week": wk, "label": drill.WEEK_LABELS.get(wk, wk), "rows": []})
        key = drill._key(w["latin"])
        groups[-1]["rows"].append({"key": key, "latin": w["latin"],
                                   "en": ", ".join(w.get("en") or [])[:40],
                                   "has": key in versions})
    for grp in groups:
        grp["done"] = sum(1 for r in grp["rows"] if r["has"])
    total = sum(len(grp["rows"]) for grp in groups)
    return render_template("teacher_audio.html", groups=groups, total=total,
                           recorded=sum(grp["done"] for grp in groups))


@app.route("/teacher/audio/save", methods=["POST"])
def teacher_audio_save():
    """The page posts the WAV it recorded as the request body."""
    key = request.args.get("key", "")
    if key not in _word_keys():
        abort(404)
    data = request.get_data(cache=False)
    if not data or len(data) > AUDIO_MAX_BYTES or not (data[:4] == b"RIFF" and data[8:12] == b"WAVE"):
        return Response("not a recording", status=400)
    store.save_word_audio(get_db(), key, "audio/wav", data)
    return {"ok": True, "url": say_url_for_key(key)}


def say_url_for_key(key):
    g.pop("audio_versions", None)
    v = _audio_versions().get(key)
    return url_for("word_audio", key=key, v=int(v)) if v is not None else None


@app.route("/teacher/audio/delete", methods=["POST"])
def teacher_audio_delete():
    key = request.form.get("key", "")
    if key in _word_keys():
        store.delete_word_audio(get_db(), key)
    return redirect(url_for("teacher_audio") + "#w-" + key.replace(" ", "-"))


# --------------------------------------------------------------------------
# Backups and the end of the year
# --------------------------------------------------------------------------

@app.route("/teacher/backup")
def teacher_backup():
    """The whole database as one file.

    Render's Hobby Postgres keeps three days of point-in-time recovery, and a
    problem noticed in June cannot be fixed from a three-day window. JSON
    rather than pg_dump so it restores into either database — a backup that
    only loads back into Render is a backup that depends on Render existing.
    """
    blob = backup.export_json(get_db())
    name = "latin1-backup-%s.json" % time.strftime("%Y-%m-%d")
    return Response(blob, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=" + name})


@app.route("/teacher/data")
def teacher_data():
    db = get_db()
    return render_template("teacher_data.html", counts=backup.export(db)["counts"],
                           student_tables=backup.STUDENT_TABLES,
                           storage=db.target,
                           done=request.args.get("purged"),
                           removed=request.args.getlist("removed"))


@app.route("/teacher/data/end-of-year", methods=["POST"])
def teacher_end_of_year():
    """Export everything, then delete all student practice data.

    Leadership was told the data is deleted at the end of the year, so this is
    built rather than left as a manual job. It is guarded by typing the year,
    not by an "are you sure" — a confirmation you can dismiss by reflex is not
    a confirmation, and this one is not reversible.

    The export is streamed back as the response, so the only way to run it is
    to also receive the backup. Losing a year of history because someone
    purged without downloading first is exactly the failure this is meant to
    prevent.
    """
    db = get_db()
    year = str(time.localtime().tm_year)
    if (request.form.get("confirm") or "").strip() != year:
        return redirect(url_for("teacher_data", bad_confirm=1))
    blob, removed = backup.end_of_year(db)
    print("[end-of-year] deleted %r" % (removed,), flush=True)
    name = "latin1-final-%s.json" % time.strftime("%Y-%m-%d")
    summary = "; ".join("%s=%d" % kv for kv in sorted(removed.items()))
    return Response(blob, mimetype="application/json", headers={
        "Content-Disposition": "attachment; filename=" + name,
        "X-Deleted": summary,
    })


# --------------------------------------------------------------------------
# Roster management, in the app rather than in sqlite3
# --------------------------------------------------------------------------

@app.route("/teacher/roster")
def teacher_roster():
    db = get_db()
    section = request.args.get("section") or None
    rows = store.roster(db, active_only=False, section=section)
    known = {r["student_id"] for r in rows}
    seen = set(store.all_students(db))
    return render_template("teacher_roster.html", rows=rows,
                           sections=store.sections(db), section=section,
                           rejected=request.args.getlist("rejected"),
                           pinned=store.students_with_pins(db),
                           unrostered=sorted(seen - known))


@app.route("/teacher/roster/add", methods=["POST"])
def teacher_roster_add():
    """Paste a class list of ID numbers, one per line."""
    db = get_db()
    section = (request.form.get("section") or "").strip() or None
    lines = (request.form.get("ids") or "").replace(",", "\n").splitlines()
    added, existing, rejected = store.add_students_bulk(db, lines, section)
    # Rejected lines are echoed back rather than counted, because the message
    # that matters is "these were names, and names are not stored here".
    return redirect(url_for("teacher_roster", section=section, added=len(added),
                            existing=len(existing), rejected=rejected[:12]))


@app.route("/teacher/pin/reset", methods=["POST"])
def teacher_pin_reset():
    """Clear a student's PIN so they can choose a new one.

    This is the whole of password recovery in this app, and it is enough:
    there are no email addresses here to send a link to, and the person who
    can confirm the student is who they say they are is standing in front of
    them.
    """
    db = get_db()
    sid = identity.normalize(request.form.get("student_id"))
    store.clear_pin(db, sid)
    back = request.form.get("back") or url_for("teacher_roster")
    return redirect(back + ("&" if "?" in back else "?") + "pin_reset=" + sid)


@app.route("/teacher/roster/update", methods=["POST"])
def teacher_roster_update():
    db = get_db()
    sid = request.form["student_id"]
    action = request.form.get("action")
    if action == "deactivate":
        store.set_student_active(db, sid, False)
    elif action == "activate":
        store.set_student_active(db, sid, True)
    elif action == "remove":
        store.remove_student(db, sid)          # class list only; history stays
    return redirect(url_for("teacher_roster",
                            section=(request.form.get("back_section") or None)))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
