"""A grammar Hint is always more than the date a topic was introduced."""

import collections
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schooltime  # noqa: E402,F401
import badges      # noqa: E402
import checks      # noqa: E402
import dataio      # noqa: E402
import store       # noqa: E402

SPEC = dataio.load_spec()
TEACHING = dataio.load_teaching()


class TestTheText(unittest.TestCase):
    def test_every_topic_with_questions_has_teaching_text(self):
        # Without it, approving can never give a question a real hint.
        nodes = collections.Counter(i["node"] for i in dataio.load_bank())
        for n in nodes:
            entry = TEACHING.get(n) or {}
            self.assertTrue(str(entry.get("explain") or "").strip(), n)
            self.assertTrue(entry.get("examples"), n)
            self.assertTrue(str(entry.get("when_wrong") or "").strip(), n)

    def test_new_teaching_text_waits_for_approval(self):
        self.assertEqual({TEACHING[n]["status"] for n in ("MS-052", "MS-061", "MS-078")}, {"draft"})

    def test_every_badge_topic_is_covered(self):
        _, bs = badges.load()
        for b in bs:
            for n in b["nodes"]:
                self.assertIn(n, TEACHING, n)


class TestTheHint(unittest.TestCase):
    NODE, BADGE = "MS-049", "talking-to"

    def setUp(self):
        os.environ.pop("LATIN_PUBLIC", None)
        os.environ["LATIN_TEACHER_PASSWORD"] = "teacherpw"
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.db = store.connect(self.db_path)
        items = dataio.load_bank()
        flags, _ = checks.run_all(items, set(SPEC), dataio.allowed_latin(dataio.load_exemplars()))
        store.import_items(self.db, items, flags, "t")
        for i in items:
            if i["node"] == self.NODE:
                store.set_review(self.db, i["id"], "approved")
        store.add_student(self.db, "403217", "Block 3")
        self.t = server.app.test_client()
        self.t.post("/login", data={"password": "teacherpw", "next": "/teacher"})
        self.c = server.app.test_client()
        self.c.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.c.post("/signin", data={"step": "pin", "student_id": "403217",
                                     "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def hint(self):
        body = self.c.get("/practice/session?node=%s" % self.NODE).data.decode()
        return body.split('<details class="hintbox">')[1].split("</details>")[0]

    def test_before_anything_is_approved_only_the_date(self):
        h = self.hint()
        self.assertIn("Introduced", h)
        self.assertNotIn("Remember:", h)

    def test_an_approved_lesson_gives_every_question_a_hint(self):
        self.t.post("/teacher/lessons", data={"action": "approve", "id": self.BADGE})
        h = self.hint()
        self.assertIn("Remember:", h)
        self.assertIn("Vocative", h)
        self.assertIn('href="/badges/%s/lesson" target="_blank"' % self.BADGE, h)

    def test_approved_teaching_text_takes_over_and_the_lesson_stays_a_tap_away(self):
        self.t.post("/teacher/lessons", data={"action": "approve", "id": self.BADGE})
        self.t.post("/teaching/%s/approve" % self.NODE, data={"action": "approve"})
        h = self.hint()
        self.assertIn("speak directly to someone", h)              # MS-049's teaching text
        self.assertNotIn("Remember:", h)
        self.assertIn("Look back at Lesson", h)

    def test_the_teacher_sees_which_hints_are_ready(self):
        page = self.t.get("/teacher/badges").data.decode()
        self.assertIn("hints 0/2", page)
        self.assertIn("read &amp; approve", page)
        self.assertIn("MS-052", self.t.get("/teaching").data.decode())   # Unit 2 is there to approve


if __name__ == "__main__":
    unittest.main()
