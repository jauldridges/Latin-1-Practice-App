"""The commitment: this app holds no student names.

These are the tests that would fail if a name field came back — by accident,
or by somebody adding one "just for the dashboard". They check the schema, the
write path, and the purge that clears a database built the old way.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import store  # noqa: E402


def fresh():
    path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    conn = store.connect(path)
    store.init_db(conn)
    return conn, path


class TestSchema(unittest.TestCase):
    def test_the_roster_has_no_name_column(self):
        conn, _ = fresh()
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(roster)")}
        self.assertEqual(cols, {"student_id", "section", "active", "added_at"})

    def test_no_table_anywhere_has_a_name_column(self):
        conn, _ = fresh()
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        offenders = []
        for t in tables:
            for r in conn.execute("PRAGMA table_info(%s)" % t):
                if "name" in r["name"].lower():
                    offenders.append("%s.%s" % (t, r["name"]))
        # items.source_file is a filename and sqlite_sequence.name holds TABLE
        # names — neither is a person.
        allowed = {"items.source_file", "sqlite_sequence.name"}
        self.assertEqual([o for o in offenders if o not in allowed], [])


class TestWritePath(unittest.TestCase):
    def test_a_name_cannot_be_added_to_the_roster(self):
        conn, _ = fresh()
        self.assertIsNone(store.add_student(conn, "Sam Tucker"))
        self.assertIsNone(store.add_student(conn, "sam"))
        self.assertEqual(store.roster(conn), [])

    def test_an_id_can(self):
        conn, _ = fresh()
        self.assertEqual(store.add_student(conn, "40217", "Block 3"), "40217")
        self.assertEqual(store.roster(conn)[0]["student_id"], "40217")

    def test_a_pasted_list_of_names_is_rejected_wholesale(self):
        conn, _ = fresh()
        added, existing, rejected = store.add_students_bulk(
            conn, ["Jordan Lee", "Kim Ruiz", "Sam Tucker"])
        self.assertEqual(added, [])
        self.assertEqual(len(rejected), 3)
        self.assertEqual(store.roster(conn), [])

    def test_a_pasted_list_of_ids_is_accepted(self):
        conn, _ = fresh()
        added, _, rejected = store.add_students_bulk(
            conn, ["40217", " 40-218 ", "", "40219"], "Block 3")
        self.assertEqual(added, ["40217", "40218", "40219"])
        self.assertEqual(rejected, [])

    def test_ids_load_from_a_file(self):
        conn, path = fresh()
        f = os.path.join(os.path.dirname(path), "ids.txt")
        with open(f, "w") as fh:
            fh.write("# Block 3\n40217\n40218   # a comment\n\n40219\n")
        added, _, rejected = store.load_student_ids_file(conn, f, "Block 3")
        self.assertEqual(added, ["40217", "40218", "40219"])
        self.assertEqual(rejected, [])


class TestPurge(unittest.TestCase):
    """A database built the old way, keyed on names, must come out clean."""

    def old_db(self):
        path = os.path.join(tempfile.mkdtemp(), "old.sqlite")
        c = sqlite3.connect(path)
        c.executescript("""
        CREATE TABLE roster (student_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
            section TEXT, active INTEGER DEFAULT 1, added_at REAL NOT NULL);
        CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
            timestamp REAL NOT NULL, item_id TEXT NOT NULL, spec_node_id TEXT, response TEXT,
            result TEXT NOT NULL, latency_ms INTEGER, context TEXT, version TEXT);
        CREATE TABLE miss_reasons (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
            timestamp REAL, item_id TEXT, item_node_id TEXT, reason_key TEXT, reason_text TEXT,
            reason_node TEXT, contested INTEGER);
        CREATE TABLE quiz_attempts (attempt_id TEXT PRIMARY KEY, quiz_id TEXT, student_id TEXT,
            started_at REAL, submitted_at REAL, answers_json TEXT DEFAULT '{}', results_json TEXT);
        INSERT INTO roster VALUES ('sam tucker','Sam Tucker','Block 3',1,0);
        INSERT INTO events (student_id,timestamp,item_id,result) VALUES ('sam tucker',1,'x','right');
        INSERT INTO events (student_id,timestamp,item_id,result) VALUES ('40217',2,'y','right');
        INSERT INTO miss_reasons (student_id,timestamp,item_id) VALUES ('kim ruiz',1,'x');
        INSERT INTO quiz_attempts VALUES ('q:s','q','sam tucker',1,NULL,'{}',NULL);
        """)
        c.commit()
        c.close()
        conn = store.connect(path)
        return conn

    def test_the_purge_removes_every_name_keyed_row(self):
        conn = self.old_db()
        report = store.init_db(conn)
        self.assertTrue(report["dropped_name_column"])
        self.assertEqual(report["events"], 1)
        self.assertEqual(report["miss_reasons"], 1)
        self.assertEqual(report["quiz_attempts"], 1)
        self.assertEqual(report["roster_rows"], 1)

    def test_id_keyed_practice_survives(self):
        conn = self.old_db()
        store.init_db(conn)
        rows = conn.execute("SELECT student_id FROM events").fetchall()
        self.assertEqual([r["student_id"] for r in rows], ["40217"])

    def test_no_name_string_is_left_anywhere_in_the_file(self):
        # The strongest form of the claim: grep the raw bytes of the database.
        conn = self.old_db()
        store.init_db(conn)
        path = conn.execute("PRAGMA database_list").fetchone()["file"]
        blob = b""
        for suffix in ("", "-wal", "-journal"):      # the sidecars count too
            try:
                with open(path + suffix, "rb") as fh:
                    blob += fh.read().lower()
            except FileNotFoundError:
                pass
        for name in (b"sam tucker", b"kim ruiz", b"display_name"):
            self.assertNotIn(name, blob, name.decode())

    def test_it_is_idempotent(self):
        conn = self.old_db()
        store.init_db(conn)
        again = store.purge_names(conn)
        self.assertEqual(again["events"], 0)
        self.assertFalse(again["dropped_name_column"])


if __name__ == "__main__":
    unittest.main()
