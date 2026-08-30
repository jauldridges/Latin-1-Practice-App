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
import sqlite3
import time

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
"""


def connect(db_path=DEFAULT_DB):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn):
    conn.executescript(_SCHEMA)
    # Tolerate an older DB that predates the skips column.
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(items)").fetchall()}
    if "skips" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN skips INTEGER DEFAULT 0")
    conn.commit()


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

def node_queue_counts(conn):
    """Nodes with unreviewed, unflagged items, newest-first by count."""
    rows = conn.execute(
        """SELECT node_id, COUNT(*) AS n
             FROM items
            WHERE review_status='unreviewed' AND flagged=0
         GROUP BY node_id ORDER BY node_id""").fetchall()
    return [(r["node_id"], r["n"]) for r in rows]


def next_unreviewed_in_node(conn, node_id):
    # Least-skipped first, so a "decide later" skip cycles the item to the back
    # and it returns after the rest of the node's queue.
    row = conn.execute(
        """SELECT * FROM items
            WHERE node_id=? AND review_status='unreviewed' AND flagged=0
         ORDER BY skips, item_id LIMIT 1""", (node_id,)).fetchone()
    return _row_to_item(row)


def next_flagged(conn):
    row = conn.execute(
        """SELECT * FROM items
            WHERE flagged=1 AND review_status='unreviewed'
         ORDER BY skips, node_id, item_id LIMIT 1""").fetchone()
    return _row_to_item(row)


def skip_item(conn, item_id):
    """Decide later: keep the item unreviewed but push it to the back."""
    conn.execute("UPDATE items SET skips=skips+1, updated_at=? WHERE item_id=?",
                 (time.time(), item_id))
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

def set_review(conn, item_id, status, reason=None, new_payload=None, edited=False):
    now = time.time()
    if new_payload is not None:
        conn.execute(
            "UPDATE items SET review_status=?, review_reason=?, payload=?, edited=?, updated_at=? WHERE item_id=?",
            (status, reason, json.dumps(new_payload, ensure_ascii=False), 1 if edited else 0, now, item_id))
    else:
        conn.execute(
            "UPDATE items SET review_status=?, review_reason=?, updated_at=? WHERE item_id=?",
            (status, reason, now, item_id))
    conn.commit()


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
        (student_id, timestamp or time.time(), item_id, spec_node_id,
         response, result, latency_ms, context, version))
    conn.commit()


def events_for_student(conn, student_id):
    rows = conn.execute(
        "SELECT * FROM events WHERE student_id=? ORDER BY timestamp", (student_id,)).fetchall()
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
        (student_id, timestamp or time.time(), item_id, item_node_id,
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


def all_students(conn):
    rows = conn.execute("SELECT DISTINCT student_id FROM events ORDER BY student_id").fetchall()
    return [r["student_id"] for r in rows]
