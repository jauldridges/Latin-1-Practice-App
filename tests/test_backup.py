"""Tests for backup, restore, and the end-of-year deletion.

The change request says: confirm the backup actually restores — test it, do not
assume it. So the central test does a full round trip and compares derived
student state, not just row counts: a backup that restores the events but loses
their timestamps would pass a count check and quietly reset every
spaced-repetition schedule.
"""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backup  # noqa: E402
import db as dbmod  # noqa: E402
import drill  # noqa: E402
import store  # noqa: E402

PG_URL = os.environ.get("LATIN_TEST_PG_URL", "")


def fresh(name="t.sqlite"):
    conn = store.connect(os.path.join(tempfile.mkdtemp(), name))
    store.init_db(conn)
    return conn


def populate(conn):
    store.import_items(conn, [
        {"id": "Q1", "node": "MS-001", "assess": "recognise", "tier": 1, "format": "choice"},
        {"id": "Q2", "node": "CR-001", "assess": "apply", "tier": 2, "format": "boxes"},
    ], {}, "test")
    store.set_review(conn, "Q1", "approved", session_id="s")
    store.set_review(conn, "Q2", "rejected", reason="duplicate", session_id="s")
    store.add_student(conn, "403217", "Block 3")
    store.add_student(conn, "418206", "Block 4")
    store.set_pin(conn, "403217", "1234")
    now = time.time()
    for i in range(6):
        store.record_event(conn, "403217", "vocab:puella:la_en", None, "girl",
                           "right" if i % 2 else "wrong", timestamp=now - i * 86400)
    store.record_miss_reason(conn, "403217", "Q1", "MS-001", "k", "I guessed", "MS-001")
    store.approve_teaching(conn, "MS-001", "fp")
    store.create_quiz(conn, "q1", "Check", ["Q1"])
    a = store.get_or_start_attempt(conn, "q1", "403217")
    store.save_attempt_answer(conn, a["attempt_id"], "Q1", "a")
    return conn


class TestExport(unittest.TestCase):
    def setUp(self):
        self.conn = populate(fresh())

    def test_every_table_is_in_the_export(self):
        data = backup.export(self.conn)
        self.assertEqual(sorted(data["tables"]), sorted(backup.TABLES))

    def test_it_is_json(self):
        json.loads(backup.export_json(self.conn))

    def test_counts_are_reported(self):
        counts = backup.export(self.conn)["counts"]
        self.assertEqual(counts["events"], 6)
        self.assertEqual(counts["roster"], 2)
        self.assertEqual(counts["decisions"], 2)


class TestRoundTrip(unittest.TestCase):
    """Take a backup, restore it somewhere empty, and compare."""

    def snapshot(self, conn):
        events = store.events_for_student(conn, "403217")
        words = [{"latin": "puella", "en": ["girl"], "week": drill.WEEK_ORDER[0]}]
        return {
            "counts": store.counts(conn),
            "approved": [p["id"] for p in store.approved_payloads(conn)],
            "roster": [(r["student_id"], r["section"]) for r in store.roster(conn)],
            "decisions": [(d["item_id"], d["status"]) for d in store.decisions_for(conn, "Q1")],
            "teaching": store.teaching_approvals(conn),
            "event_times": [round(e["timestamp"], 3) for e in events],
            # Derived state: the figure that would silently break if timestamps
            # were lost, while every row count still matched.
            "boxes": [(r.latin, r.box, r.state) for r in drill.progress_table(words, events)],
            "pin_works": store.check_pin(conn, "403217", "1234"),
        }

    def test_a_backup_restores(self):
        src = populate(fresh("src.sqlite"))
        data = json.loads(backup.export_json(src))
        dst = fresh("dst.sqlite")
        loaded = backup.restore(dst, data)
        self.assertEqual(loaded["events"], 6)
        self.assertEqual(self.snapshot(src), self.snapshot(dst))

    def test_the_pin_still_works_after_a_restore(self):
        src = populate(fresh("src.sqlite"))
        dst = fresh("dst.sqlite")
        backup.restore(dst, json.loads(backup.export_json(src)))
        self.assertTrue(store.check_pin(dst, "403217", "1234"))
        self.assertFalse(store.check_pin(dst, "403217", "9999"))

    def test_restoring_onto_live_data_is_refused(self):
        src = populate(fresh("src.sqlite"))
        dst = populate(fresh("dst.sqlite"))
        with self.assertRaises(ValueError):
            backup.restore(dst, json.loads(backup.export_json(src)))

    def test_replace_is_allowed_explicitly(self):
        src = populate(fresh("src.sqlite"))
        dst = populate(fresh("dst.sqlite"))
        backup.restore(dst, json.loads(backup.export_json(src)), replace=True)
        self.assertEqual(len(store.events_for_student(dst, "403217")), 6)

    def test_an_unknown_format_is_refused(self):
        with self.assertRaises(ValueError):
            backup.restore(fresh(), {"format": 99, "tables": {}})


class TestEndOfYear(unittest.TestCase):
    def setUp(self):
        self.conn = populate(fresh())

    def test_student_data_goes(self):
        _, removed = backup.end_of_year(self.conn)
        self.assertEqual(removed["events"], 6)
        self.assertEqual(removed["roster"], 2)
        self.assertEqual(store.all_events(self.conn), [])
        self.assertEqual(store.roster(self.conn), [])
        self.assertFalse(store.has_pin(self.conn, "403217"))

    def test_the_question_bank_stays(self):
        # Next year's class needs the questions and the review decisions; it
        # must not inherit a single row of anyone's history.
        backup.end_of_year(self.conn)
        self.assertEqual(store.counts(self.conn)["total"], 2)
        self.assertEqual(store.approved_payloads(self.conn)[0]["id"], "Q1")
        self.assertEqual(len(store.decisions_for(self.conn, "Q1")), 1)

    def test_the_export_is_taken_before_the_deletion(self):
        blob, _ = backup.end_of_year(self.conn)
        data = json.loads(blob)
        self.assertEqual(data["counts"]["events"], 6)

    def test_and_that_export_restores(self):
        blob, _ = backup.end_of_year(self.conn)
        dst = fresh("dst.sqlite")
        backup.restore(dst, json.loads(blob))
        self.assertEqual(len(store.all_events(dst)), 6)
        self.assertTrue(store.check_pin(dst, "403217", "1234"))


@unittest.skipUnless(PG_URL, "set LATIN_TEST_PG_URL to run against a real Postgres")
class TestAcrossDatabases(unittest.TestCase):
    """A backup taken from Postgres must restore into SQLite.

    Otherwise "we have a backup" means "we have a backup as long as Render
    still exists", which is not the same sentence.
    """

    def test_postgres_out_sqlite_in(self):
        pg = dbmod.connect(url=PG_URL)
        pg.execute("DROP SCHEMA public CASCADE")
        pg.execute("CREATE SCHEMA public")
        pg.commit()
        store.init_db(pg)
        populate(pg)
        data = json.loads(backup.export_json(pg))

        lite = fresh("from_pg.sqlite")
        backup.restore(lite, data)
        self.assertEqual(len(store.all_events(lite)), 6)
        self.assertEqual([r["student_id"] for r in store.roster(lite)], ["403217", "418206"])
        self.assertTrue(store.check_pin(lite, "403217", "1234"))
        self.assertEqual(store.approved_payloads(lite)[0]["id"], "Q1")
        pg.close()

    def test_sqlite_out_postgres_in(self):
        src = populate(fresh("src.sqlite"))
        data = json.loads(backup.export_json(src))
        pg = dbmod.connect(url=PG_URL)
        pg.execute("DROP SCHEMA public CASCADE")
        pg.execute("CREATE SCHEMA public")
        pg.commit()
        store.init_db(pg)
        backup.restore(pg, data)
        self.assertEqual(len(store.all_events(pg)), 6)
        self.assertTrue(store.check_pin(pg, "403217", "1234"))
        pg.close()


if __name__ == "__main__":
    unittest.main()


class TestRoutes(unittest.TestCase):
    """From the review side, without a terminal — which is the requirement."""

    def setUp(self):
        for k in ("LATIN_TEACHER_PASSWORD", "LATIN_PUBLIC"):
            os.environ.pop(k, None)
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        self.conn = store.connect(self.db_path)
        populate(self.conn)

    def tearDown(self):
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def test_the_backup_downloads_as_a_file(self):
        r = self.client.get("/teacher/backup")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertEqual(json.loads(r.data)["counts"]["events"], 6)

    def test_the_page_shows_what_is_in_there(self):
        body = self.client.get("/teacher/data").data.decode()
        self.assertIn("student data", body)
        self.assertIn("End of year", body)

    def test_the_year_must_be_typed(self):
        r = self.client.post("/teacher/data/end-of-year", data={"confirm": "yes"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("bad_confirm", r.headers["Location"])
        self.assertEqual(len(store.all_events(self.conn)), 6)   # nothing deleted

    def test_the_right_year_runs_it_and_hands_back_the_backup(self):
        year = str(time.localtime().tm_year)
        r = self.client.post("/teacher/data/end-of-year", data={"confirm": year})
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertIn("events=6", r.headers["X-Deleted"])
        # The response IS the backup — there is no way to purge without it.
        self.assertEqual(json.loads(r.data)["counts"]["events"], 6)
        self.assertEqual(store.all_events(self.conn), [])
        self.assertEqual(store.counts(self.conn)["total"], 2)   # bank survives

    def test_backup_routes_are_behind_the_teacher_password(self):
        os.environ["LATIN_TEACHER_PASSWORD"] = "hunter2"
        sys.modules.pop("server", None)
        import server
        c = server.app.test_client()
        for path in ("/teacher/backup", "/teacher/data"):
            r = c.get(path)
            self.assertEqual(r.status_code, 302, path)
            self.assertIn("/login", r.headers["Location"])
