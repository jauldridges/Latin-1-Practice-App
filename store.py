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


def all_students(conn):
    rows = conn.execute("SELECT DISTINCT student_id FROM events ORDER BY student_id").fetchall()
    return [r["student_id"] for r in rows]
