"""
Backup, restore, and the end-of-year deletion.

Render's Hobby Postgres keeps three days of point-in-time recovery. A problem
noticed in June cannot be fixed from a three-day window, so this exists: one
file, complete enough to rebuild the database from nothing, downloadable from
the review side without a terminal.

Three operations, and the third is the one to be careful with:

    export      every table to one JSON file
    restore     that file back into an empty database
    purge       export, then delete all student practice data

The format is JSON rather than pg_dump output for one reason: it must restore
into either database. A backup taken from the hosted Postgres has to be
loadable into a laptop's SQLite, or "we have a backup" means "we have a backup
as long as Render still exists".
"""

import json
import time

FORMAT = 1

# Everything, in an order where a row never arrives before what it refers to.
TABLES = ["items", "decisions", "roster", "student_pins", "events",
          "miss_reasons", "teaching_approvals", "quizzes", "quiz_attempts"]

# What belongs to students rather than to the course. The end-of-year purge
# empties these and leaves the question bank and its review decisions alone —
# next year's class needs the questions; it must not inherit anyone's history.
STUDENT_TABLES = ["events", "miss_reasons", "quiz_attempts", "student_pins", "roster"]

# Assigned by the database. Carrying them across dialects invites a collision
# with a sequence that does not know they exist.
SKIP_COLUMNS = {"events": {"id"}, "miss_reasons": {"id"}, "decisions": {"id"}}


def export(conn):
    """The whole database as one JSON-able dict."""
    out = {"format": FORMAT, "taken_at": time.time(),
           "taken_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
           "source": conn.target, "tables": {}, "counts": {}}
    for table in TABLES:
        cols = sorted(conn.table_columns(table) - SKIP_COLUMNS.get(table, set()))
        if not cols:
            continue
        rows = conn.execute("SELECT %s FROM %s" % (", ".join(cols), table)).fetchall()
        out["tables"][table] = {"columns": cols,
                                "rows": [[dict(r)[c] for c in cols] for r in rows]}
        out["counts"][table] = len(rows)
    return out


def export_json(conn):
    return json.dumps(export(conn), ensure_ascii=False, indent=1)


def restore(conn, data, replace=False):
    """Load an export back in.

    Refuses to merge into a database that already holds practice data unless
    told to replace it, because a half-restore that doubles every event is
    worse than no restore at all.
    """
    if data.get("format") != FORMAT:
        raise ValueError("unknown backup format: %r" % (data.get("format"),))
    existing = {t: conn.execute("SELECT COUNT(*) AS n FROM %s" % t).fetchone()["n"]
                for t in STUDENT_TABLES}
    if any(existing.values()) and not replace:
        raise ValueError("target already has data (%s) — pass replace=True to overwrite"
                         % ", ".join("%s=%d" % kv for kv in existing.items() if kv[1]))
    if replace:
        for table in reversed(TABLES):
            conn.execute("DELETE FROM %s" % table)
        conn.commit()

    loaded = {}
    for table in TABLES:
        block = data["tables"].get(table)
        if not block or not block["rows"]:
            continue
        cols = [c for c in block["columns"] if c in conn.table_columns(table)]
        idx = [block["columns"].index(c) for c in cols]
        sql = "INSERT INTO %s (%s) VALUES (%s)" % (
            table, ", ".join(cols), ",".join("?" * len(cols)))
        for row in block["rows"]:
            conn.execute(sql, tuple(row[i] for i in idx))
        loaded[table] = len(block["rows"])
    conn.commit()
    return loaded


def purge_students(conn):
    """Delete all student practice data. The question bank stays.

    Callers must have taken an export first — end_of_year() below does. The
    split matters: next year's class needs the questions and the review
    decisions, and must not inherit a single row of anyone's history.
    """
    removed = {}
    for table in STUDENT_TABLES:
        n = conn.execute("SELECT COUNT(*) AS n FROM %s" % table).fetchone()["n"]
        conn.execute("DELETE FROM %s" % table)
        removed[table] = n
    conn.commit()
    conn.reclaim_space(STUDENT_TABLES)
    return removed


def end_of_year(conn):
    """Export everything, then delete all student data. Returns (json, removed)."""
    blob = export_json(conn)
    return blob, purge_students(conn)
