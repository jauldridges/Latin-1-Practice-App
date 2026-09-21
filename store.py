"""
The apps' own storage. SQLite, on disk, one file. Never touches the source YAML.

Two things live here:
  items  - one row per generated question, with its review decision and any
           mechanical-check flags. The full question is kept as JSON so the
           review screen can render it and the exporter can reproduce it.
  events - the append-only practice record. One row per attempt, never updated
           in place; a student's state is derived from the history.

The live-fire hook (a student contesting a question, or a class getting one
wrong at an unusual rate) is left as the function flag_item_live_fire(), unused
for now, so the field exists before the feature does.
"""

import json
import os
import time

import db as dbmod
import identity

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "review.sqlite")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id        TEXT PRIMARY KEY,
    node_id        TEXT NOT NULL,
    assess         TEXT,
    tier           INTEGER,
    fmt            TEXT,
    macron_matters INTEGER DEFAULT 0,
    source_file    TEXT,
    payload        TEXT NOT NULL,          -- JSON of the full item
    review_status  TEXT NOT NULL DEFAULT 'unreviewed',  -- unreviewed|approved|rejected
    review_reason  TEXT,
    edited         INTEGER DEFAULT 0,
    skips          INTEGER DEFAULT 0,     -- "decide later": count, cycles to back
    flagged        INTEGER DEFAULT 0,
    flag_json      TEXT DEFAULT '[]',      -- JSON list of {check,level,detail}
    created_at     REAL,
    updated_at     REAL
);
CREATE INDEX IF NOT EXISTS idx_items_node ON items(node_id);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(review_status);

CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    timestamp     REAL NOT NULL,
    item_id       TEXT NOT NULL,
    spec_node_id  TEXT,
    response      TEXT,
    result        TEXT NOT NULL,           -- right|close|wrong
    latency_ms    INTEGER,
    context       TEXT DEFAULT 'practice', -- practice|homework|classwork|quiz|exam
    version       TEXT DEFAULT 'v1'        -- v1|v2|v3
);
CREATE INDEX IF NOT EXISTS idx_events_student ON events(student_id);
CREATE INDEX IF NOT EXISTS idx_events_item ON events(item_id);

-- What the student said went wrong, tagged to the node that explains that
-- mistake. This is the diagnostic record: "how many students this week said
-- they matched the ending instead of the gender" is a real question with a
-- real answer, and this table is where it is answered.
CREATE TABLE IF NOT EXISTS miss_reasons (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    timestamp     REAL NOT NULL,
    item_id       TEXT NOT NULL,
    item_node_id  TEXT,
    reason_key    TEXT,
    reason_text   TEXT,
    reason_node   TEXT,             -- the node that explains this mistake
    contested     INTEGER DEFAULT 0 -- "I think my answer should be right"
);
CREATE INDEX IF NOT EXISTS idx_miss_item ON miss_reasons(item_id);
CREATE INDEX IF NOT EXISTS idx_miss_node ON miss_reasons(reason_node);

-- Teacher approval of teaching text. The text itself lives in teaching.yaml
-- (which neither app writes to); only the approval lives here. The fingerprint
-- is a hash of the approved wording, so text edited after approval reverts to
-- draft rather than inheriting the old sign-off.
CREATE TABLE IF NOT EXISTS teaching_approvals (
    node_id      TEXT PRIMARY KEY,
    fingerprint  TEXT NOT NULL,
    approved_at  REAL NOT NULL
);

-- Teaching text the teacher reworded in the app. teaching.yaml stays the
-- source and is still never written to; a row here overrides it for one node.
-- It has to live in the database rather than in the file because a hosted
-- service's disk does not survive a redeploy: an edit written to the file
-- would vanish the next time the app was updated, silently, taking a node's
-- explanation back to wording the teacher had already replaced.
CREATE TABLE IF NOT EXISTS teaching_overrides (
    node_id     TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    updated_at  REAL NOT NULL
);

-- A proctored quiz: a FROZEN, hand-picked, ordered set of approved questions.
-- Frozen matters: every student sits the same paper, and the paper does not
-- change under them if the bank is re-imported later.
CREATE TABLE IF NOT EXISTS quizzes (
    quiz_id     TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    context     TEXT NOT NULL DEFAULT 'quiz',   -- quiz|exam|classwork|homework
    item_ids    TEXT NOT NULL,                  -- JSON ordered list
    created_at  REAL NOT NULL,
    open        INTEGER DEFAULT 1               -- 0 = closed, no new attempts
);

-- One student's sitting. answers_json holds work in progress, saved as they go
-- so a dead phone loses nothing; nothing is graded until submitted_at is set.
CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id   TEXT PRIMARY KEY,
    quiz_id      TEXT NOT NULL,
    student_id   TEXT NOT NULL,
    started_at   REAL NOT NULL,
    submitted_at REAL,
    answers_json TEXT NOT NULL DEFAULT '{}',    -- item_id -> raw response
    results_json TEXT                           -- item_id -> graded result, set at submit
);
CREATE INDEX IF NOT EXISTS idx_attempt_quiz ON quiz_attempts(quiz_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempt_one ON quiz_attempts(quiz_id, student_id);

-- Every review decision ever made, in order, never updated in place.
--
-- items.review_status is a CACHE of the latest row here, kept so the queue
-- queries stay one indexed lookup. This table is the truth.
--
-- Why keep the old ones: a question whose verdict flipped and flipped back was
-- genuinely hard to call, and that is worth knowing both when re-reading it and
-- when generating the next batch. It is also what makes undo honest — the
-- earlier decision is retracted in the record rather than erased from it.
CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     TEXT NOT NULL,
    status      TEXT NOT NULL,        -- approved|rejected|skipped|undone
    reason      TEXT,
    edited      INTEGER DEFAULT 0,
    session_id  TEXT,                 -- which review sitting made it
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dec_item ON decisions(item_id);
CREATE INDEX IF NOT EXISTS idx_dec_session ON decisions(session_id, id);

-- The class list: the ID numbers this app will accept, and nothing else.
--
-- Two jobs. It is the denominator — without it the dashboard can only show
-- who HAS practised, since a student who did nothing leaves no events. And it
-- is the typo guard: an ID that is well-formed but not on this list is not
-- silently accepted.
--
-- There is deliberately no name column. Not an empty one, not a nullable one:
-- an empty column invites someone to fill it. `section` is a class block, not
-- a person.
CREATE TABLE IF NOT EXISTS roster (
    student_id   TEXT PRIMARY KEY,      -- the ID number, exactly as issued
    section      TEXT,                  -- Block 3 / 4 / 5 / 7
    active       INTEGER DEFAULT 1,
    added_at     REAL NOT NULL
);

-- A student's PIN, hashed. Never the PIN itself.
--
-- This exists to stop one student practising as another, not to secure
-- anything valuable: nothing behind it is a grade. Four digits is enough for
-- that job, and anything heavier fails the real test — a fourteen-year-old
-- locked out at 9pm does not do their homework, they give up.
--
-- Hashed anyway, with a per-student salt and enough rounds to make a stolen
-- table useless, because four digits is 10,000 guesses and an unsalted hash of
-- one is a lookup table.
CREATE TABLE IF NOT EXISTS student_pins (
    student_id  TEXT PRIMARY KEY,
    algo        TEXT NOT NULL,          -- e.g. pbkdf2_sha256$200000
    salt        TEXT NOT NULL,
    hash        TEXT NOT NULL,
    set_at      REAL NOT NULL
);
"""


def normalize_student(student_id):
    """The student key used in the data: an ID number, never a name.

    Thin wrapper over identity.normalize() so every write and read goes through
    one function. See identity.py for why this system holds no names.
    """
    return identity.normalize(student_id)


def connect(db_path=DEFAULT_DB):
    """The database this deployment is configured for.

    DATABASE_URL points at Postgres when hosted; without it this is the local
    SQLite file, unchanged. See db.py — every difference between the two lives
    there, not here.
    """
    return dbmod.connect(sqlite_path=db_path)



def init_db(conn):
    conn.executescript(_SCHEMA)
    # Tolerate an older DB that predates the skips column.
    if "skips" not in conn.table_columns("items"):
        conn.execute("ALTER TABLE items ADD COLUMN skips INTEGER DEFAULT 0")
    conn.commit()
    return purge_names(conn)


# --------------------------------------------------------------------------
# The purge
# --------------------------------------------------------------------------

def _is_digits(value):
    """True for an id made only of digits — i.e. not a name."""
    return bool(value) and str(value).isdigit()


def purge_names(conn):
    """Remove every trace of name-based identity from an existing database.

    This runs on every startup, and it is destructive on purpose. The app used
    to key student records on typed names; the school has since committed that
    it holds none. A migration would defeat that commitment, so the change
    request says purge and do not migrate, and this does exactly that:

      * the roster's display_name column is dropped, not blanked — an empty
        column invites someone to fill it later. Because every row in that
        table was keyed on a name, the rows go too.
      * every practice row whose student_id is not shaped like an ID number is
        deleted. A student_id that is not a number is a name, and there is no
        version of keeping it that is compatible with what was promised.

    Idempotent: on a database that never held names it deletes nothing and
    returns zeros. Returns a report so the caller can say out loud what went,
    because a silent purge is not a purge anyone can trust.
    """
    report = {"roster_rows": 0, "events": 0, "miss_reasons": 0,
              "quiz_attempts": 0, "dropped_name_column": False}

    if "display_name" in conn.table_columns("roster"):
        report["roster_rows"] = conn.execute("SELECT COUNT(*) AS n FROM roster").fetchone()["n"]
        # SQLite before 3.35 cannot DROP COLUMN, and every row here is
        # name-keyed anyway, so the table is rebuilt empty.
        conn.execute("DROP TABLE IF EXISTS roster")
        conn.executescript(_SCHEMA)
        report["dropped_name_column"] = True

    # Practice rows keyed on something that is not an ID number.
    #
    # The test is "contains a non-digit", NOT "matches the current ID pattern".
    # Those look the same today and are not: the pattern is configurable, so
    # tightening it — as happened when the six-digit generator arrived — would
    # otherwise silently delete a year of real practice from students whose
    # perfectly good ids no longer matched. A name is a name whatever the
    # pattern says, and only names are what this purge is for.
    for table in ("events", "miss_reasons", "quiz_attempts"):
        ids = [r["student_id"] for r in
               conn.execute("SELECT DISTINCT student_id FROM %s" % table).fetchall()]
        bad = [i for i in ids if not _is_digits(i)]
        if bad:
            marks = ",".join("?" * len(bad))
            cur = conn.execute(
                "DELETE FROM %s WHERE student_id IN (%s)" % (table, marks), bad)
            report[table] = cur.rowcount
    conn.commit()

    if any(report[k] for k in ("roster_rows", "events", "miss_reasons", "quiz_attempts")):
        # DELETE only marks the space reusable; the names stay readable in
        # storage until something overwrites them. Found by a test that greps
        # the raw bytes rather than querying. See db.Conn.reclaim_space.
        conn.reclaim_space(("roster", "events", "miss_reasons", "quiz_attempts"))
        report["scrubbed"] = True
    return report


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------

def import_items(conn, items, flags_by_item, source_file):
    """Upsert generated items with their flags.

    New item_ids are inserted as unreviewed. Existing item_ids keep their review
    decision (so re-importing a regenerated bank does not wipe prior work) but
    have their payload and flags refreshed. Returns a small stats dict.
    """
    now = time.time()
    inserted = updated = 0
    for it in items:
        iid = it.get("id")
        if not iid:
            continue
        fs = [f._asdict() if hasattr(f, "_asdict") else f for f in flags_by_item.get(iid, [])]
        flagged = 1 if fs else 0
        row = conn.execute("SELECT item_id FROM items WHERE item_id=?", (iid,)).fetchone()
        payload = json.dumps(it, ensure_ascii=False)
        if row is None:
            conn.execute(
                """INSERT INTO items (item_id, node_id, assess, tier, fmt,
                       macron_matters, source_file, payload, review_status,
                       flagged, flag_json, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,'unreviewed',?,?,?,?)""",
                (iid, it.get("node"), it.get("assess"), it.get("tier"),
                 it.get("format"), 1 if it.get("macron_matters") else 0,
                 source_file, payload, flagged, json.dumps(fs, ensure_ascii=False),
                 now, now))
            inserted += 1
        else:
            conn.execute(
                """UPDATE items SET node_id=?, assess=?, tier=?, fmt=?,
                       macron_matters=?, source_file=?, payload=?, flagged=?,
                       flag_json=?, updated_at=? WHERE item_id=?""",
                (it.get("node"), it.get("assess"), it.get("tier"),
                 it.get("format"), 1 if it.get("macron_matters") else 0,
                 source_file, payload, flagged, json.dumps(fs, ensure_ascii=False),
                 now, iid))
            updated += 1
    conn.commit()
    return {"inserted": inserted, "updated": updated,
            "flagged": sum(1 for i in items if flags_by_item.get(i.get("id")))}


# --------------------------------------------------------------------------
# Queue reads
# --------------------------------------------------------------------------

def node_queue_counts(conn, fresh_only=False):
    """Nodes with unreviewed, unflagged items.

    fresh_only drops items that have been skipped at least once. Continuous
    review uses it to make one clean pass over everything before circling back
    to the deferred ones — otherwise a skip in an early node is served again as
    soon as the node after it empties, which is not what "decide later" means.
    """
    rows = conn.execute(
        """SELECT node_id, COUNT(*) AS n
             FROM items
            WHERE review_status='unreviewed' AND flagged=0
              AND (0 = ? OR skips = 0)
         GROUP BY node_id ORDER BY node_id""", (1 if fresh_only else 0,)).fetchall()
    return [(r["node_id"], r["n"]) for r in rows]


def next_unreviewed_in_node(conn, node_id, exclude_item=None, fresh_only=False):
    # Least-skipped first, so a "decide later" skip cycles the item to the back
    # and it returns after the rest of the node's queue.
    #
    # exclude_item is the item just skipped. Without it, skipping the LAST item
    # in a node serves that same item straight back, because it is still the
    # least-skipped thing left. Skip has to move on, or it is not a skip.
    row = conn.execute(
        """SELECT * FROM items
            WHERE node_id=? AND review_status='unreviewed' AND flagged=0
              AND item_id IS NOT ?
              AND (0 = ? OR skips = 0)
         ORDER BY skips, item_id LIMIT 1""",
        (node_id, exclude_item, 1 if fresh_only else 0)).fetchone()
    return _row_to_item(row)


def next_flagged(conn, exclude_item=None):
    row = conn.execute(
        """SELECT * FROM items
            WHERE flagged=1 AND review_status='unreviewed'
              AND item_id IS NOT ?
         ORDER BY skips, node_id, item_id LIMIT 1""", (exclude_item,)).fetchone()
    return _row_to_item(row)


def skip_item(conn, item_id, session_id=None):
    """Decide later: keep the item unreviewed but push it to the back.

    Logged like any other decision so it can be undone — a skip is just as
    easy to mis-tap as an approve.
    """
    now = time.time()
    conn.execute("UPDATE items SET skips=skips+1, updated_at=? WHERE item_id=?",
                 (now, item_id))
    conn.execute(
        """INSERT INTO decisions (item_id, status, reason, edited, session_id, created_at)
           VALUES (?,?,?,?,?,?)""",
        (item_id, "skipped", None, 0, session_id, now))
    conn.commit()


def counts(conn):
    def one(where, args=()):
        return conn.execute(f"SELECT COUNT(*) AS n FROM items WHERE {where}", args).fetchone()["n"]
    return {
        "total": one("1=1"),
        "unreviewed": one("review_status='unreviewed' AND flagged=0"),
        "flagged": one("flagged=1 AND review_status='unreviewed'"),
        "approved": one("review_status='approved'"),
        "rejected": one("review_status='rejected'"),
        "deferred": one("review_status='unreviewed' AND flagged=0 AND skips>0"),
    }


def get_item(conn, item_id):
    return _row_to_item(conn.execute("SELECT * FROM items WHERE item_id=?", (item_id,)).fetchone())


def _row_to_item(row):
    if row is None:
        return None
    d = dict(row)
    d["payload"] = json.loads(d["payload"])
    d["flags"] = json.loads(d["flag_json"] or "[]")
    return d


# --------------------------------------------------------------------------
# Review actions
# --------------------------------------------------------------------------

def set_review(conn, item_id, status, reason=None, new_payload=None, edited=False,
               session_id=None, log=True):
    """Record a decision.

    Appends to the decision log and refreshes the items cache from it. The
    append is the point: changing your mind writes a new row, it does not
    overwrite the old one.
    """
    now = time.time()
    if new_payload is not None:
        conn.execute(
            "UPDATE items SET review_status=?, review_reason=?, payload=?, edited=?, updated_at=? WHERE item_id=?",
            (status, reason, json.dumps(new_payload, ensure_ascii=False), 1 if edited else 0, now, item_id))
    else:
        conn.execute(
            "UPDATE items SET review_status=?, review_reason=?, updated_at=? WHERE item_id=?",
            (status, reason, now, item_id))
    if log:
        conn.execute(
            """INSERT INTO decisions (item_id, status, reason, edited, session_id, created_at)
               VALUES (?,?,?,?,?,?)""",
            (item_id, status, reason, 1 if edited else 0, session_id, now))
    conn.commit()
    if log:
        refresh_hard_to_call(conn, item_id)


# --------------------------------------------------------------------------
# The decision log
# --------------------------------------------------------------------------

TERMINAL = ("approved", "rejected")


def decisions_for(conn, item_id):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM decisions WHERE item_id=? ORDER BY id", (item_id,)).fetchall()]


def verdict_path(conn, item_id):
    """The sequence of verdicts this question actually received, with
    consecutive repeats collapsed.

    Skips and undos are not verdicts and drop out, which matters: approve →
    undo → approve is a mis-tap corrected, one verdict, not three. Only a
    genuine change of mind lengthens this list.
    """
    kept = []
    for d in decisions_for(conn, item_id):
        if d["status"] in TERMINAL:
            kept.append(d["status"])
        elif d["status"] == "undone" and d["reason"] in TERMINAL and kept:
            # An undone row carries the verdict it retracted. Popping only for
            # a retracted VERDICT matters: an undone skip must not swallow the
            # approve that came before it.
            kept.pop()
    path = []
    for v in kept:
        if not path or path[-1] != v:
            path.append(v)
    return path


def refresh_hard_to_call(conn, item_id):
    """Flag a question whose verdict changed more than once.

    A path of length 3 means it went one way, then the other, then back. That
    is not a mis-tap; it is a question that is genuinely hard to call, and it
    is worth a second look now and worth knowing about when the next batch is
    generated. Below that, nothing happens — a single change of mind is normal
    and flagging it would drown the queue.
    """
    if len(verdict_path(conn, item_id)) < 3:
        return False
    row = conn.execute("SELECT flag_json FROM items WHERE item_id=?", (item_id,)).fetchone()
    if row is None:
        return False
    flags = json.loads(row["flag_json"] or "[]")
    if any(f.get("check") == "hard-to-call" for f in flags):
        return True
    flags.append({"check": "hard-to-call", "level": "heuristic",
                  "detail": "You changed your mind about this one more than once."})
    conn.execute("UPDATE items SET flagged=1, flag_json=? WHERE item_id=?",
                 (json.dumps(flags), item_id))
    conn.commit()
    return True


def hard_to_call(conn):
    """Every question whose verdict changed more than once, with its path."""
    out = []
    for r in conn.execute("SELECT DISTINCT item_id FROM decisions").fetchall():
        path = verdict_path(conn, r["item_id"])
        if len(path) >= 3:
            out.append({"item_id": r["item_id"], "path": path})
    return sorted(out, key=lambda d: -len(d["path"]))


def session_decisions(conn, session_id, limit=200):
    """This sitting's decisions, most recent first, with the question attached.

    Undone decisions stay in the list, marked, rather than vanishing: the
    history is a record of what happened, and "I undid that" is part of it.
    """
    rows = conn.execute(
        """SELECT d.*, i.node_id, i.payload FROM decisions d
             LEFT JOIN items i ON i.item_id = d.item_id
            WHERE d.session_id = ? ORDER BY d.id DESC LIMIT ?""",
        (session_id, limit)).fetchall()
    undone = set()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"]) if d.get("payload") else {}
        if d["status"] == "undone":
            undone.add(d["item_id"])
            continue                       # the undo itself is not a list entry
        d["undone"] = d["item_id"] in undone
        out.append(d)
    return out


def last_undoable(conn, session_id):
    """The most recent decision in this sitting that has not been undone."""
    rows = conn.execute(
        "SELECT * FROM decisions WHERE session_id=? ORDER BY id DESC LIMIT 40",
        (session_id,)).fetchall()
    undone = set()
    for r in rows:
        if r["status"] == "undone":
            undone.add(r["item_id"])
            continue
        if r["item_id"] not in undone:
            return dict(r)
        undone.discard(r["item_id"])
    return None


def undo_last(conn, session_id):
    """Retract the last decision and reopen the question.

    Appends an 'undone' row rather than deleting the decision, then puts the
    item back to unreviewed so the queue serves it again. Returns the decision
    that was retracted, or None if there is nothing to undo.
    """
    d = last_undoable(conn, session_id)
    if d is None:
        return None
    # The undone row records WHAT it retracted, so verdict_path can tell an
    # undone approve from an undone skip.
    conn.execute(
        """INSERT INTO decisions (item_id, status, reason, edited, session_id, created_at)
           VALUES (?,?,?,?,?,?)""",
        (d["item_id"], "undone", d["status"], 0, session_id, time.time()))
    if d["status"] == "skipped":
        # A skip pushed it to the back of the pass; undoing brings it forward.
        conn.execute("UPDATE items SET skips=MAX(skips-1,0) WHERE item_id=?", (d["item_id"],))
    conn.execute(
        "UPDATE items SET review_status='unreviewed', review_reason=NULL, updated_at=? WHERE item_id=?",
        (time.time(), d["item_id"]))
    conn.commit()
    return d


def approved_payloads(conn):
    rows = conn.execute(
        "SELECT payload FROM items WHERE review_status='approved' ORDER BY node_id, item_id").fetchall()
    return [json.loads(r["payload"]) for r in rows]


def rejected_summary(conn):
    rows = conn.execute(
        "SELECT item_id, node_id, review_reason FROM items WHERE review_status='rejected' ORDER BY node_id, item_id").fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Live-fire hook (field, not feature)
# --------------------------------------------------------------------------

def flag_item_live_fire(conn, item_id, reason):
    """Return a question to the flagged queue because classroom use exposed it
    (a student contested it, or a class missed it at an unusual rate). Left
    unwired on purpose: the field exists so the feature can be added without a
    migration."""
    row = get_item(conn, item_id)
    if row is None:
        return False
    flags = row["flags"] + [{"check": "live_fire", "level": "field", "detail": reason}]
    conn.execute(
        "UPDATE items SET flagged=1, review_status='unreviewed', flag_json=?, updated_at=? WHERE item_id=?",
        (json.dumps(flags, ensure_ascii=False), time.time(), item_id))
    conn.commit()
    return True


# --------------------------------------------------------------------------
# Events (used by the drill; the record is shared)
# --------------------------------------------------------------------------

def record_event(conn, student_id, item_id, spec_node_id, response, result,
                 latency_ms=None, context="practice", version="v1", timestamp=None):
    conn.execute(
        """INSERT INTO events (student_id, timestamp, item_id, spec_node_id,
               response, result, latency_ms, context, version)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (normalize_student(student_id), timestamp or time.time(), item_id, spec_node_id,
         response, result, latency_ms, context, version))
    conn.commit()


def events_for_student(conn, student_id):
    rows = conn.execute(
        "SELECT * FROM events WHERE student_id=? ORDER BY timestamp",
        (normalize_student(student_id),)).fetchall()
    return [dict(r) for r in rows]


def approved_items(conn, node_id=None):
    """The approved question payloads — what the grammar practice app serves.
    Nothing unreviewed or rejected ever reaches a student."""
    if node_id:
        rows = conn.execute(
            "SELECT payload FROM items WHERE review_status='approved' AND node_id=? ORDER BY item_id",
            (node_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT payload FROM items WHERE review_status='approved' ORDER BY node_id, item_id").fetchall()
    return [json.loads(r["payload"]) for r in rows]


def approved_node_counts(conn):
    rows = conn.execute(
        """SELECT node_id, COUNT(*) AS n FROM items
            WHERE review_status='approved' GROUP BY node_id ORDER BY node_id""").fetchall()
    return [(r["node_id"], r["n"]) for r in rows]


def record_miss_reason(conn, student_id, item_id, item_node_id, reason_key,
                       reason_text, reason_node, contested=False, timestamp=None):
    """Append one what-went-wrong selection."""
    conn.execute(
        """INSERT INTO miss_reasons (student_id, timestamp, item_id, item_node_id,
               reason_key, reason_text, reason_node, contested)
           VALUES (?,?,?,?,?,?,?,?)""",
        (normalize_student(student_id), timestamp or time.time(), item_id, item_node_id,
         reason_key, reason_text, reason_node, 1 if contested else 0))
    conn.commit()


def approve_teaching(conn, node_id, fingerprint):
    conn.execute(
        """INSERT INTO teaching_approvals (node_id, fingerprint, approved_at)
           VALUES (?,?,?)
           ON CONFLICT(node_id) DO UPDATE SET fingerprint=excluded.fingerprint,
                                              approved_at=excluded.approved_at""",
        (node_id, fingerprint, time.time()))
    conn.commit()


def unapprove_teaching(conn, node_id):
    conn.execute("DELETE FROM teaching_approvals WHERE node_id=?", (node_id,))
    conn.commit()


def set_teaching_override(conn, node_id, entry):
    """Store a reworded teaching entry. The file keeps its copy; this wins."""
    conn.execute(
        """INSERT INTO teaching_overrides (node_id, payload, updated_at)
           VALUES (?,?,?)
           ON CONFLICT(node_id) DO UPDATE SET payload=excluded.payload,
                                              updated_at=excluded.updated_at""",
        (node_id, json.dumps(entry, ensure_ascii=False), time.time()))
    conn.commit()


def teaching_override(conn, node_id):
    row = conn.execute("SELECT payload FROM teaching_overrides WHERE node_id=?",
                       (node_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def clear_teaching_override(conn, node_id):
    """Put a node back to the file's wording."""
    conn.execute("DELETE FROM teaching_overrides WHERE node_id=?", (node_id,))
    conn.commit()


def teaching_overrides(conn):
    rows = conn.execute("SELECT node_id, payload FROM teaching_overrides").fetchall()
    return {r["node_id"]: json.loads(r["payload"]) for r in rows}


def teaching_approvals(conn):
    """node_id -> fingerprint of the text that was approved."""
    return {r["node_id"]: r["fingerprint"]
            for r in conn.execute("SELECT node_id, fingerprint FROM teaching_approvals").fetchall()}


# --------------------------------------------------------------------------
# Quizzes
# --------------------------------------------------------------------------

def create_quiz(conn, quiz_id, title, item_ids, context="quiz"):
    conn.execute(
        "INSERT INTO quizzes (quiz_id, title, context, item_ids, created_at, open) VALUES (?,?,?,?,?,1)",
        (quiz_id, title, context, json.dumps(list(item_ids)), time.time()))
    conn.commit()


def get_quiz(conn, quiz_id):
    r = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["item_ids"] = json.loads(d["item_ids"])
    return d


def list_quizzes(conn):
    out = []
    for r in conn.execute("SELECT * FROM quizzes ORDER BY created_at DESC").fetchall():
        d = dict(r)
        d["item_ids"] = json.loads(d["item_ids"])
        d["attempts"] = conn.execute(
            "SELECT COUNT(*) AS n FROM quiz_attempts WHERE quiz_id=? AND submitted_at IS NOT NULL",
            (d["quiz_id"],)).fetchone()["n"]
        out.append(d)
    return out


def set_quiz_open(conn, quiz_id, is_open):
    conn.execute("UPDATE quizzes SET open=? WHERE quiz_id=?", (1 if is_open else 0, quiz_id))
    conn.commit()


def delete_quiz(conn, quiz_id):
    conn.execute("DELETE FROM quiz_attempts WHERE quiz_id=?", (quiz_id,))
    conn.execute("DELETE FROM quizzes WHERE quiz_id=?", (quiz_id,))
    conn.commit()


def get_or_start_attempt(conn, quiz_id, student_id):
    """Resume an existing sitting or begin one. A student has at most one
    attempt per quiz, so reopening the link mid-quiz returns them to their work
    rather than starting over."""
    student_id = normalize_student(student_id)
    r = conn.execute("SELECT * FROM quiz_attempts WHERE quiz_id=? AND student_id=?",
                     (quiz_id, student_id)).fetchone()
    if r is None:
        aid = f"{quiz_id}:{student_id}"
        conn.execute(
            "INSERT INTO quiz_attempts (attempt_id, quiz_id, student_id, started_at, answers_json) VALUES (?,?,?,?,'{}')",
            (aid, quiz_id, student_id, time.time()))
        conn.commit()
        r = conn.execute("SELECT * FROM quiz_attempts WHERE attempt_id=?", (aid,)).fetchone()
    d = dict(r)
    d["answers"] = json.loads(d["answers_json"] or "{}")
    d["results"] = json.loads(d["results_json"]) if d.get("results_json") else None
    return d


def save_attempt_answer(conn, attempt_id, item_id, response):
    """Store one in-progress answer. Never grades; grading happens at submit."""
    r = conn.execute("SELECT answers_json, submitted_at FROM quiz_attempts WHERE attempt_id=?",
                     (attempt_id,)).fetchone()
    if r is None or r["submitted_at"]:
        return False               # submitted work is locked
    answers = json.loads(r["answers_json"] or "{}")
    answers[item_id] = response
    conn.execute("UPDATE quiz_attempts SET answers_json=? WHERE attempt_id=?",
                 (json.dumps(answers, ensure_ascii=False), attempt_id))
    conn.commit()
    return True


def submit_attempt(conn, attempt_id, results):
    conn.execute(
        "UPDATE quiz_attempts SET submitted_at=?, results_json=? WHERE attempt_id=? AND submitted_at IS NULL",
        (time.time(), json.dumps(results, ensure_ascii=False), attempt_id))
    conn.commit()


def get_attempt(conn, attempt_id):
    r = conn.execute("SELECT * FROM quiz_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["answers"] = json.loads(d["answers_json"] or "{}")
    d["results"] = json.loads(d["results_json"]) if d.get("results_json") else None
    return d


def quiz_attempts(conn, quiz_id):
    out = []
    for r in conn.execute(
            "SELECT * FROM quiz_attempts WHERE quiz_id=? ORDER BY student_id", (quiz_id,)).fetchall():
        d = dict(r)
        d["answers"] = json.loads(d["answers_json"] or "{}")
        d["results"] = json.loads(d["results_json"]) if d.get("results_json") else None
        out.append(d)
    return out


# --------------------------------------------------------------------------
# Roster
# --------------------------------------------------------------------------

def add_student(conn, student_id, section=None):
    """Add one ID number to the class list. Returns the stored id, or None if
    the number is not shaped like an ID — a name typed here is refused rather
    than stored."""
    key = normalize_student(student_id)
    if not key or not identity.is_valid(key):
        return None
    conn.execute(
        """INSERT INTO roster (student_id, section, active, added_at)
           VALUES (?,?,1,?)
           ON CONFLICT(student_id) DO UPDATE SET
                 section=COALESCE(excluded.section, roster.section),
                 active=1""",
        (key, section, time.time()))
    conn.commit()
    return key


def set_student_active(conn, student_id, active):
    conn.execute("UPDATE roster SET active=? WHERE student_id=?",
                 (1 if active else 0, normalize_student(student_id)))
    conn.commit()


def remove_student(conn, student_id):
    """Removes from the class list only. Their event history is never deleted."""
    conn.execute("DELETE FROM roster WHERE student_id=?", (normalize_student(student_id),))
    conn.commit()


def roster(conn, active_only=True, section=None):
    q = "SELECT * FROM roster"
    where, args = [], []
    if active_only:
        where.append("active=1")
    if section:
        where.append("section=?")
        args.append(section)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY section IS NULL, section, student_id"
    return [dict(r) for r in conn.execute(q, args).fetchall()]


def sections(conn):
    rows = conn.execute(
        "SELECT DISTINCT section FROM roster WHERE section IS NOT NULL AND section<>'' ORDER BY section"
    ).fetchall()
    return [r["section"] for r in rows]


def get_student(conn, student_id):
    r = conn.execute("SELECT * FROM roster WHERE student_id=?",
                     (normalize_student(student_id),)).fetchone()
    return dict(r) if r else None


def set_pin(conn, student_id, pin):
    """Store a PIN. Replaces any existing one — that is also how a reset works."""
    key = normalize_student(student_id)
    algo, salt, digest = identity.hash_pin(pin)
    conn.execute("DELETE FROM student_pins WHERE student_id=?", (key,))
    conn.execute(
        """INSERT INTO student_pins (student_id, algo, salt, hash, set_at)
           VALUES (?,?,?,?,?)""",
        (key, algo, salt, digest, time.time()))
    conn.commit()
    return True


def has_pin(conn, student_id):
    r = conn.execute("SELECT 1 AS x FROM student_pins WHERE student_id=?",
                     (normalize_student(student_id),)).fetchone()
    return r is not None


def check_pin(conn, student_id, pin):
    r = conn.execute("SELECT * FROM student_pins WHERE student_id=?",
                     (normalize_student(student_id),)).fetchone()
    if r is None:
        return False
    return identity.verify_pin(pin, r["algo"], r["salt"], r["hash"])


def clear_pin(conn, student_id):
    """The teacher's reset. The student chooses a new PIN next time they sign
    in — there is no email address in this system to send one to."""
    conn.execute("DELETE FROM student_pins WHERE student_id=?",
                 (normalize_student(student_id),))
    conn.commit()


def students_with_pins(conn):
    return {r["student_id"] for r in
            conn.execute("SELECT student_id FROM student_pins").fetchall()}


def all_students(conn):
    rows = conn.execute("SELECT DISTINCT student_id FROM events ORDER BY student_id").fetchall()
    return [r["student_id"] for r in rows]


# --------------------------------------------------------------------------
# Whole-class reads (the dashboard)
# --------------------------------------------------------------------------

def all_events(conn, since=None, until=None, section=None):
    """Every attempt, optionally windowed, optionally one block only.

    The dashboard derives everything from this one list rather than issuing a
    query per student: 88 students times a year of practice is small enough to
    hold in memory, and one read means every figure on the page describes the
    same instant.
    """
    q = "SELECT * FROM events"
    where, args = [], []
    if since is not None:
        where.append("timestamp >= ?"); args.append(since)
    if until is not None:
        where.append("timestamp <= ?"); args.append(until)
    if section:
        where.append("student_id IN (SELECT student_id FROM roster WHERE section=?)")
        args.append(section)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY timestamp"
    return [dict(r) for r in conn.execute(q, args).fetchall()]


def all_miss_reasons(conn, since=None, section=None):
    q = "SELECT * FROM miss_reasons"
    where, args = [], []
    if since is not None:
        where.append("timestamp >= ?"); args.append(since)
    if section:
        where.append("student_id IN (SELECT student_id FROM roster WHERE section=?)")
        args.append(section)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY timestamp DESC"
    return [dict(r) for r in conn.execute(q, args).fetchall()]


def add_students_bulk(conn, lines, section=None):
    """Paste a class list of ID numbers, one per line.

    Returns (added, existing, rejected). Blank lines and duplicates inside the
    paste are dropped rather than refused, because a list copied out of a
    gradebook always has both.

    IDs already on the list are reported separately, not silently absorbed:
    re-adding an existing ID with a block set MOVES it to that block, and a
    paste that quietly reassigned half of Block 3 would be worse than an error.

    Anything that is not shaped like an ID is REJECTED and handed back, not
    stored. That is the line that keeps names out: paste a class list of names
    here and every line comes back rejected, which is the intended answer.
    """
    added, existing, rejected = [], [], []
    seen = set()
    for raw in lines:
        key = normalize_student(raw)
        if not key or key in seen:
            continue
        if not identity.is_valid(key):
            rejected.append(str(raw).strip()[:40])
            continue
        seen.add(key)
        was = get_student(conn, key)
        add_student(conn, key, section)
        (existing if was else added).append(key)
    return added, existing, rejected


def load_student_ids_file(conn, path, section=None):
    """Load the valid-ID list from a file, as the change request asks.

    One ID per line; '#' starts a comment. The file holds numbers only — the
    paper that maps a number to an actual student stays off the machine.
    """
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        lines = [ln.split("#", 1)[0] for ln in fh]
    return add_students_bulk(conn, lines, section)


def miss_reasons_for_student(conn, student_id, since=None):
    q = "SELECT * FROM miss_reasons WHERE student_id=?"
    args = [normalize_student(student_id)]
    if since is not None:
        q += " AND timestamp >= ?"
        args.append(since)
    q += " ORDER BY timestamp DESC"
    return [dict(r) for r in conn.execute(q, args).fetchall()]
