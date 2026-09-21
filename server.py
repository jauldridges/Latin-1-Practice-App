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
import io
import os
import time
import uuid

import yaml
from flask import (Flask, g, redirect, render_template, request, Response,
                   session, url_for, abort)

import auth
import backup
import checks
import dataio
import drill
import identity
import practice
import quiz as quizlib
import stats
import store
import teacher
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
STUDENT_PREFIXES = ("/drill", "/practice", "/q/")


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
            "signed_in_student": current_student()}


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

@app.route("/")
def index():
    return render_template("index.html", counts=store.counts(get_db()))


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
    to practise as somebody else, and no amount of PIN checking at the door
    would have mattered while the rest of the app took your word for it
    afterwards.
    """
    return session.get(auth.STUDENT_KEY) or ""


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
        practice.option_seed(current_student(), item.get("id")))


def _signed_in_student():
    """The signed-in student, or the response that sends them to sign in."""
    sid = current_student()
    if not sid:
        return None, redirect(url_for("signin", next=request.full_path.rstrip("?")))
    return sid, None


@app.route("/drill")
def drill_home():
    return render_template("drill_home.html", weeks=drill.WEEK_ORDER,
                           week_labels=drill.WEEK_LABELS)


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
                           **_drill_stats(events))


@app.route("/drill/answer", methods=["POST"])
def drill_answer():
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
    store.record_event(db, student, item_id, drill.node_for(word), response, result,
                       latency_ms=latency_ms, context="practice", version="v1")
    if result == "close":
        # Close never counts against the student and never reveals the answer;
        # re-show the same card and let them retype. (The attempt is still
        # logged as a "close" event.)
        card = drill.card_for(word, ask)
        return render_template("drill_card.html", student=student, week=week,
                               direction=direction, card=card,
                               introduced=weeklabel(word.get("week")),
                               notice="So close — check your spelling and try again.",
                               **_drill_stats(store.events_for_student(db, student)))
    return render_template("drill_feedback.html", student=student, week=week,
                           direction=direction, word=word, ask=ask, response=response,
                           result=result, model=accepted[0],
                           introduced=weeklabel(word.get("week")),
                           **_drill_stats(store.events_for_student(db, student)))


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


@app.route("/practice")
def practice_home():
    db = get_db()
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
    approved = store.approved_items(db)
    events = store.events_for_student(db, student)
    item = practice.select_question(approved, events,
                                    allowed_nodes=_taught_now(), node_id=node)
    if item is None:
        return render_template("practice_none.html", student=student, node=node,
                               n_approved=len(approved))
    return render_template("practice_question.html", student=student, item=item,
                           node=node, context=ctx, notice=None,
                           label=_NODE_LABEL.get(item["node"], ""),
                           hint=approved_teaching_for(db, item.get("node")),
                           introduced=nodeweek(item.get("node")),
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
    else:                                   # self-check
        typed = request.form.get("typed", "")
        result = "self"

    # CLOSE never counts against the student and never opens the menu:
    # re-show the question and let them retype. The attempt is still logged.
    if result == "close":
        store.record_event(db, student, item_id, item.get("node"),
                           practice.response_summary(item, box_results, picked, typed),
                           "close", latency_ms=latency, context=ctx, version="v1")
        return render_template("practice_question.html", student=student, item=item,
                               node=node, context=ctx,
                               label=_NODE_LABEL.get(item["node"], ""),
                               hint=approved_teaching_for(db, item.get("node")),
                               introduced=nodeweek(item.get("node")),
                               notice="So close — check your spelling and try again.",
                               **_practice_stats(db, store.events_for_student(db, student)))

    if result != "self":
        store.record_event(db, student, item_id, item.get("node"),
                           practice.response_summary(item, box_results, picked, typed),
                           result, latency_ms=latency, context=ctx, version="v1")

    return render_template("practice_feedback.html", student=student, item=item,
                           node=node, context=ctx, result=result,
                           introduced=nodeweek(item.get("node")),
                           box_results=box_results, tag_results=tag_results,
                           picked=picked, typed=typed,
                           menu=practice.menu_for(item) if result == "wrong" else None,
                           teaching=approved_teaching_for(db, item.get("node")),
                           label=_NODE_LABEL.get(item["node"], ""))


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


@app.route("/drill/progress")
def drill_progress():
    db = get_db()
    student = current_student()
    events = store.events_for_student(db, student)
    rows = drill.progress_table(_DRILL_WORDS, events)
    summary = drill.progress_summary(rows)
    return render_template("drill_progress.html", student=student, rows=rows,
                           summary=summary, week_labels=drill.WEEK_LABELS)


# ==========================================================================
# The teacher dashboard
#
# Everything here answers one of two questions: did they practise, and what do
# they know. Both are read-only views over the same event history the students
# see; nothing on these pages writes an event or touches a grade.
#
# The roster is what makes the first question answerable. A student who did
# nothing leaves no events, so without a class list the dashboard could only
# ever show the kids who showed up.
# ==========================================================================

WINDOW_CHOICES = [(1, "Today"), (2, "Since yesterday"), (7, "Last 7 days"),
                  (30, "Last 30 days"), (0, "All time")]


def _window_args():
    """Read the window and block filter off the query string, once."""
    days = request.args.get("days", type=int)
    if days is None:
        days = 7
    section = request.args.get("section") or None
    if days <= 0:
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


@app.route("/teacher")
def teacher_home():
    db = get_db()
    w = _window_args()
    roster_rows = store.roster(db, active_only=True, section=w["section"])
    events = store.all_events(db, since=w["since"], until=w["until"], section=w["section"])
    table = teacher.class_activity(roster_rows, events, w["since"], w["until"])
    return render_template("teacher_home.html", w=w, table=table,
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
    return render_template(
        "teacher_student.html", w=w, student=student_id,
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
    w = _window_args()
    roster_rows = store.roster(db, active_only=True, section=w["section"])
    events = store.all_events(db, since=w["since"], until=w["until"], section=w["section"])
    table = teacher.class_activity(roster_rows, events, w["since"], w["until"])
    buf = io.StringIO()
    wtr = csv.writer(buf)
    # student_id, not name. There are no names in this system — the paper that
    # maps a number to a person stays off the machine, so this file is safe to
    # download and safe to lose.
    wtr.writerow(["student_id", "block", "state", "attempts", "days_practised",
                  "vocab", "grammar", "accuracy_pct", "last_practised", "window"])
    for r in table["rows"]:
        wtr.writerow([r["student_id"], r["section"] or "", r["state"], r["attempts"],
                      r["days"], r["vocab"], r["grammar"],
                      "" if r["accuracy"] is None else int(round(r["accuracy"] * 100)),
                      time.strftime("%Y-%m-%d %H:%M", time.localtime(r["last_at"])) if r["last_at"] else "",
                      _window_label(w["days"])])
    name = "practice-%s.csv" % time.strftime("%Y-%m-%d")
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=" + name})


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
