"""Tests for the two-database storage layer.

The translation tests always run — they need no database. The live tests run
only when LATIN_TEST_PG_URL points at a Postgres, and are the ones that
actually matter: a dialect layer that has never met the other dialect is a
guess.

    LATIN_TEST_PG_URL=postgresql://... python3 -m unittest tests.test_postgres
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
import store  # noqa: E402

PG_URL = os.environ.get("LATIN_TEST_PG_URL", "")


class TestDialectChoice(unittest.TestCase):
    def test_a_url_selects_postgres(self):
        self.assertEqual(db.dialect_for("postgresql://h/d"), db.POSTGRES)
        self.assertEqual(db.dialect_for("postgres://h/d"), db.POSTGRES)

    def test_no_url_means_the_local_file(self):
        self.assertEqual(db.dialect_for(""), db.SQLITE)

    def test_the_password_never_reaches_a_log(self):
        self.assertEqual(db.safe_target("postgresql://me:hunter2@h:5432/d"),
                         "postgresql://me:***@h:5432/d")


class TestTranslation(unittest.TestCase):
    def test_placeholders(self):
        self.assertEqual(db.to_postgres("SELECT * FROM t WHERE a=? AND b=?"),
                         "SELECT * FROM t WHERE a=%s AND b=%s")

    def test_autoincrement_becomes_a_sequence(self):
        self.assertIn("BIGSERIAL PRIMARY KEY",
                      db.to_postgres("id INTEGER PRIMARY KEY AUTOINCREMENT"))

    def test_real_becomes_double(self):
        # Postgres REAL is four bytes and would quietly round timestamps.
        self.assertIn("DOUBLE PRECISION", db.to_postgres("added_at REAL NOT NULL"))

    def test_is_not_becomes_is_distinct_from(self):
        self.assertEqual(db.to_postgres("WHERE item_id IS NOT ?"),
                         "WHERE item_id IS DISTINCT FROM %s")

    def test_two_argument_max_becomes_greatest(self):
        self.assertEqual(db.to_postgres("SET skips=MAX(skips-1,0)"),
                         "SET skips=GREATEST(skips-1,0)")

    def test_aggregate_max_is_left_alone(self):
        self.assertIn("MAX(timestamp)", db.to_postgres("SELECT MAX(timestamp) FROM events"))

    def test_string_literals_are_not_rewritten(self):
        sql = "SELECT * FROM items WHERE review_status='unreviewed' AND x=?"
        self.assertIn("'unreviewed'", db.to_postgres(sql))

    def test_a_literal_question_mark_survives(self):
        self.assertIn("'why?'", db.to_postgres("SELECT * FROM t WHERE a='why?' AND b=?"))


class TestStatementSplitting(unittest.TestCase):
    def test_every_table_in_the_schema_is_created(self):
        import re
        declared = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", store._SCHEMA))
        built = set()
        for s in db._statements(store._SCHEMA):
            built.update(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", s))
        # Every table after the first two once went missing here, because their
        # blocks open with a comment and the splitter discarded those.
        self.assertEqual(declared, built)

    def test_a_semicolon_inside_a_comment_does_not_split(self):
        script = "-- a note; with a semicolon\nCREATE TABLE a (x TEXT);"
        self.assertEqual(len(db._statements(script)), 1)

    def test_an_apostrophe_inside_a_comment_does_not_open_a_string(self):
        script = "-- the student's practice\nCREATE TABLE a (x TEXT);\nCREATE TABLE b (y TEXT);"
        self.assertEqual(len(db._statements(script)), 2)

    def test_a_semicolon_inside_a_string_does_not_split(self):
        self.assertEqual(len(db._statements("INSERT INTO t VALUES ('a;b');")), 1)


@unittest.skipUnless(PG_URL, "set LATIN_TEST_PG_URL to run against a real Postgres")
class TestLivePostgres(unittest.TestCase):
    """The same behaviour the SQLite tests assert, on the other database."""

    def setUp(self):
        self.conn = db.connect(url=PG_URL)
        self.conn.execute("DROP SCHEMA public CASCADE")
        self.conn.execute("CREATE SCHEMA public")
        self.conn.commit()
        store.init_db(self.conn)
        store.import_items(self.conn, [
            {"id": "Q1", "node": "MS-001", "assess": "recognise", "tier": 1, "format": "choice"},
            {"id": "Q2", "node": "CR-001", "assess": "apply", "tier": 2, "format": "boxes"},
        ], {}, "test")

    def tearDown(self):
        self.conn.close()

    def test_it_really_is_postgres(self):
        self.assertEqual(self.conn.dialect, db.POSTGRES)

    def test_counts(self):
        self.assertEqual(store.counts(self.conn)["unreviewed"], 2)

    def test_decisions_append_and_the_latest_wins(self):
        store.set_review(self.conn, "Q1", "approved", session_id="s")
        store.set_review(self.conn, "Q1", "rejected", session_id="s")
        self.assertEqual([d["status"] for d in store.decisions_for(self.conn, "Q1")],
                         ["approved", "rejected"])
        self.assertEqual(store.get_item(self.conn, "Q1")["review_status"], "rejected")

    def test_hard_to_call_flagging(self):
        for st in ("approved", "rejected", "approved"):
            store.set_review(self.conn, "Q1", st, session_id="s")
        self.assertEqual([h["item_id"] for h in store.hard_to_call(self.conn)], ["Q1"])
        self.assertEqual(store.get_item(self.conn, "Q1")["flagged"], 1)

    def test_undo(self):
        store.set_review(self.conn, "Q1", "approved", session_id="s")
        self.assertEqual(store.undo_last(self.conn, "s")["status"], "approved")
        self.assertEqual(store.get_item(self.conn, "Q1")["review_status"], "unreviewed")

    def test_undo_of_a_skip_uses_greatest_not_max(self):
        # MAX(skips-1,0) is SQLite's scalar max and is an aggregate in Postgres.
        store.skip_item(self.conn, "Q2", session_id="s")
        store.undo_last(self.conn, "s")
        self.assertEqual(store.get_item(self.conn, "Q2")["skips"], 0)

    def test_exclude_item_uses_is_distinct_from(self):
        # "item_id IS NOT ?" is valid SQLite and a syntax error in Postgres.
        self.assertEqual(store.next_unreviewed_in_node(self.conn, "CR-001")["item_id"], "Q2")
        self.assertIsNone(store.next_unreviewed_in_node(self.conn, "CR-001", exclude_item="Q2"))

    def test_roster_upsert_and_id_validation(self):
        self.assertEqual(store.add_student(self.conn, "40217", "Block 3"), "40217")
        self.assertIsNone(store.add_student(self.conn, "Sam Tucker"))
        store.add_student(self.conn, "40217", "Block 4")          # ON CONFLICT path
        self.assertEqual(store.roster(self.conn)[0]["section"], "Block 4")

    def test_events_round_trip(self):
        store.record_event(self.conn, "40217", "vocab:puella:la_en", None, "girl", "right")
        self.assertEqual(len(store.events_for_student(self.conn, "40217")), 1)
        self.assertEqual(len(store.all_events(self.conn)), 1)

    def test_quiz_attempt_round_trip(self):
        store.create_quiz(self.conn, "q1", "Test", ["Q1"])
        a = store.get_or_start_attempt(self.conn, "q1", "40217")
        store.save_attempt_answer(self.conn, a["attempt_id"], "Q1", "a")
        self.assertEqual(store.get_attempt(self.conn, a["attempt_id"])["answers"], {"Q1": "a"})

    def test_timestamps_keep_their_precision(self):
        # REAL in Postgres is 4 bytes; a unix timestamp stored in one is wrong
        # by seconds, which would corrupt every Leitner interval.
        import time
        t = time.time()
        store.record_event(self.conn, "40217", "x", None, "", "right", timestamp=t)
        got = store.events_for_student(self.conn, "40217")[0]["timestamp"]
        self.assertAlmostEqual(got, t, places=3)

    def test_the_name_purge_runs_here_too(self):
        store.record_event(self.conn, "40217", "x", None, "", "right")
        self.conn.execute(
            "INSERT INTO events (student_id, timestamp, item_id, result) VALUES (?,?,?,?)",
            ("sam tucker", 1.0, "y", "right"))
        self.conn.commit()
        report = store.purge_names(self.conn)
        self.assertEqual(report["events"], 1)
        left = {r["student_id"] for r in self.conn.execute("SELECT student_id FROM events").fetchall()}
        self.assertEqual(left, {"40217"})


if __name__ == "__main__":
    unittest.main()
