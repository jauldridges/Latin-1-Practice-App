"""Standards-based grading: no homework, progress on everything taught so far."""

import html
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import drill     # noqa: E402
import magister  # noqa: E402
import sofar     # noqa: E402
import store     # noqa: E402


class TestTheSummary(unittest.TestCase):
    WORDS = [{"latin": "aqua", "en": ["water"], "week": "week_of_aug_24"},
             {"latin": "rēx", "en": ["king"], "week": "week_of_nov_2"}]

    def test_only_words_already_taught_count(self):
        self.assertEqual([w["latin"] for w in sofar.taught_words(self.WORDS, "2026-10-01")], ["aqua"])
        self.assertEqual(len(sofar.taught_words(self.WORDS, "2026-11-02")), 2)

    def test_counts_come_out_in_the_apps_own_states(self):
        now = time.mktime((2026, 11, 3, 12, 0, 0, 0, 0, -1))
        events = [{"item_id": "vocab:aqua:la_en", "result": "right", "rating": 3,
                   "timestamp": now - 3600, "spec_node_id": None}]
        s = sofar.summary(self.WORDS, events, {}, set(), now=now)
        self.assertEqual(s["words"]["total"], 2)
        self.assertEqual(s["words"]["practiced"], 1)
        self.assertEqual(s["words"]["solid"] + s["words"]["shaky"] + s["words"]["not yet"], 2)
        self.assertEqual(s["week"]["words"], 1)                 # rēx, this week
        self.assertEqual(s["week"]["words_started"], 0)
        self.assertIsNone(s["badges"])                          # badges off


class TestModes(unittest.TestCase):
    def test_every_homework_line_has_a_standards_twin(self):
        lines = magister.load()
        ids = {l["id"] for l in lines}
        hw = [l for l in lines if l["mode"] == "homework"]
        self.assertTrue(hw)
        for l in hw:
            self.assertIn(l["id"] + "-sbg", ids)
        # and no line without a mode talks about homework
        for l in lines:
            if not l["mode"]:
                self.assertNotIn("homework", l["text"].lower(), l["id"])
        for l in lines:
            if l["mode"] == "standards":
                self.assertNotIn("homework to do", l["text"].lower())

    def test_for_mode(self):
        lines = [{"id": "a", "mode": ""}, {"id": "b", "mode": "homework"}, {"id": "c", "mode": "standards"}]
        self.assertEqual([l["id"] for l in magister.for_mode(lines, "standards")], ["a", "c"])
        self.assertEqual([l["id"] for l in magister.for_mode(lines, "homework")], ["a", "b"])


class TestTheSwitch(unittest.TestCase):
    def setUp(self):
        os.environ.pop("LATIN_PUBLIC", None)
        os.environ["LATIN_TEACHER_PASSWORD"] = "teacherpw"
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.db = store.connect(self.db_path)
        store.add_student(self.db, "403217", "Block 3")
        self.teacher = server.app.test_client()
        self.teacher.post("/login", data={"password": "teacherpw", "next": "/teacher"})
        self.student = server.app.test_client()
        self.student.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.student.post("/signin", data={"step": "pin", "student_id": "403217",
                                           "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def home(self):
        return html.unescape(self.student.get("/").data.decode())

    def switch(self, mode):
        return self.teacher.post("/teacher/deadlines", data={"form": "grading", "mode": mode})

    def test_homework_until_the_teacher_switches(self):
        self.assertEqual(self.server.grading_mode(self.db), "homework")
        body = self.home()
        self.assertIn("This week's homework", body)
        self.assertIn(">Homework</a>", body)
        self.assertNotIn("Your Latin so far", body)

    def test_standards_mode_shows_progress_not_homework(self):
        self.switch("standards")
        self.assertEqual(self.server.grading_mode(self.db), "standards")
        body = self.home()
        self.assertIn("Your Latin so far", body)
        self.assertIn("solid", body)
        self.assertNotIn("This week's homework", body)
        self.assertNotIn(">Homework</a>", body)                  # the tab
        self.assertNotIn("My homework, week by week", body)
        self.assertNotIn("mastery", body.lower())
        r = self.student.get("/homework")                        # an old bookmark
        self.assertEqual(r.status_code, 302)
        self.assertIn("/drill/progress", r.headers["Location"])
        # and back again: nothing was lost
        self.switch("homework")
        self.assertIn("This week's homework", self.home())

    def test_a_student_cannot_flip_it(self):
        self.student.post("/teacher/deadlines", data={"form": "grading", "mode": "standards"})
        self.assertEqual(self.server.grading_mode(self.db), "homework")

    def test_a_nonsense_mode_is_ignored(self):
        self.switch("pass-fail")
        self.assertEqual(self.server.grading_mode(self.db), "homework")

    def test_the_magister_and_the_laws_follow_the_mode(self):
        lines = {l["id"]: l for l in magister.load()}
        for lid in ("lex-how-02", "lex-how-02-sbg", "rules-01", "rules-01-sbg"):
            store.approve_teaching(self.db, magister.key(lid), magister.fingerprint(lines[lid]))
        laws = lambda: {l["id"]: l["numeral"] for l in self.server.leges(self.db)}   # noqa: E731
        self.assertEqual(laws(), {"lex-how-02": "I"})
        self.switch("standards")
        self.assertEqual(laws(), {"lex-how-02-sbg": "I"})        # the same number, the new words
        said = {self.server.magister_says(self.db, "403217", magister.HOME, n)["id"] for n in range(6)}
        self.assertEqual(said, {"lex-how-02-sbg", "rules-01-sbg"})
        leges_page = html.unescape(self.student.get("/leges").data.decode())
        self.assertIn("no homework to hand in", leges_page)
        self.assertNotIn("Saturday to Friday", leges_page)


if __name__ == "__main__":
    unittest.main()
