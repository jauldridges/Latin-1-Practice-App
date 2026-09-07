"""Tests for the hint, and for showing when a thing was introduced.

The rule that matters: a hint may never reach a student carrying teaching text
the teacher has not approved. That gate already exists for the after-a-miss
explanation; the hint reuses it rather than inventing a second path, and these
tests hold that it really is the same gate.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dataio  # noqa: E402
import store  # noqa: E402


class TestWeekLabel(unittest.TestCase):
    def setUp(self):
        os.environ["LATIN_DB"] = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        sys.modules.pop("server", None)
        import server
        self.server = server

    def tearDown(self):
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def test_a_drill_week_slug(self):
        self.assertEqual(self.server.weeklabel("week_of_sep_14"), "Week of Sep 14")

    def test_a_spec_week_date(self):
        # The two halves of the app store the same idea differently; a student
        # should not be able to tell.
        self.assertEqual(self.server.weeklabel("2026-09-14"), "Week of Sep 14")

    def test_no_leading_zero_on_the_day(self):
        self.assertEqual(self.server.weeklabel("2026-10-05"), "Week of Oct 5")

    def test_nothing_in_nothing_out(self):
        self.assertEqual(self.server.weeklabel(None), "")
        self.assertEqual(self.server.weeklabel(""), "")

    def test_an_unparseable_value_passes_through(self):
        self.assertEqual(self.server.weeklabel("sometime"), "sometime")

    def test_every_bank_node_yields_a_label(self):
        spec = dataio.load_spec()
        blank = [i["id"] for i in dataio.load_bank()
                 if not self.server.weeklabel(spec[i["node"]].get("week"))]
        self.assertEqual(blank, [])


class TestHintGate(unittest.TestCase):
    """The hint carries teaching text only when that exact wording is approved."""

    def setUp(self):
        for k in ("LATIN_TEACHER_PASSWORD", "LATIN_PUBLIC"):
            os.environ.pop(k, None)
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.client = server.app.test_client()
        self.conn = store.connect(self.db_path)
        store.init_db(self.conn)
        store.add_student(self.conn, "751992", "Test")
        self.client.post("/signin", data={"step": "pin", "student_id": "751992",
                                          "pin": "1111", "pin2": "1111",
                                          "confirm_unknown": "1", "next": "/drill"})

    def tearDown(self):
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def test_the_drill_card_hint_shows_the_week(self):
        body = self.client.get("/drill/session?week=all&direction=both").data.decode()
        self.assertIn("Hint", body)
        self.assertIn("Introduced Week of", body)

    def test_the_drill_hint_carries_no_teaching_text(self):
        # A vocabulary card has no spec node and therefore no teaching text.
        # Inventing one would mean telling the student the word's meaning,
        # which is the answer rather than a hint.
        body = self.client.get("/drill/session?week=all&direction=both").data.decode()
        self.assertIn("Introduced Week of", body)
        self.assertNotIn("hint.explain", body)

    def test_the_feedback_screen_names_the_week(self):
        import drill
        word = dataio.load_drill_words()[0]
        r = self.client.post("/drill/answer", data={
            "latin": word["latin"], "ask": "la_en", "response": "zzz",
            "week": "all", "direction": "both"})
        self.assertIn("Introduced Week of", r.data.decode())

    def test_unapproved_teaching_never_reaches_the_hint(self):
        # Nothing is approved in a fresh database, so no explain text may
        # appear anywhere on a practice question.
        self.client.get("/practice")
        approved = store.approved_items(self.conn)
        self.assertEqual(approved, [])          # nothing approved to serve yet
        teaching = dataio.load_teaching()
        sample = list(teaching.values())[0]
        body = self.client.get("/practice").data.decode()
        self.assertNotIn(sample["explain"][:40], body)


if __name__ == "__main__":
    unittest.main()
