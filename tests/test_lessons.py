"""Badge lessons: every badge opens with one, and only approved ones show."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schooltime  # noqa: E402,F401
import badges      # noqa: E402
import checks      # noqa: E402
import dataio      # noqa: E402
import goals       # noqa: E402
import lessons     # noqa: E402
import store       # noqa: E402

SPEC = dataio.load_spec()
ROWS, BADGES = badges.load()
LESSONS = lessons.load()


class TestTheLessons(unittest.TestCase):
    def test_every_badge_has_a_well_formed_lesson(self):
        self.assertEqual(sorted(LESSONS), sorted(b["id"] for b in BADGES))
        for bid, l in LESSONS.items():
            self.assertEqual(lessons.problems(l), [], bid)
            kinds = [lessons.kind(s) for s in l["steps"]]
            self.assertEqual(kinds[0], "say", bid)                 # it starts by explaining
            self.assertIn("check", kinds, bid)
            self.assertEqual(kinds[-1], "remember", bid)          # and ends with the line to keep
            self.assertLessEqual(len(kinds), 6, bid)              # short on purpose

    def test_words_a_student_reads(self):
        with open(lessons.PATH, encoding="utf-8") as f:
            text = f.read().lower()
        self.assertNotIn("mastery", text)
        self.assertNotIn("practi" + "se", text)

    def test_markup_is_escaped(self):
        self.assertEqual(lessons.inline("*puella* <b>"), '<em class="la">puella</em> &lt;b&gt;')
        self.assertEqual(lessons.inline("puell**ae**"), "puell<strong>ae</strong>")

    def test_lessons_are_numbered_in_teaching_order(self):
        n = lessons.numbered(BADGES, SPEC, badges.first_taught)
        self.assertEqual(sorted(n.values()), list(range(1, len(BADGES) + 1)))
        self.assertEqual((n["origins"], n["sounds"]), (1, 2))
        self.assertLess(n["subjects-objects"], n["first-declension"])
        self.assertLess(n["genitive"], n["dative"])

    def test_a_problem_is_named(self):
        bad = {"steps": [{"say": "x"}, {"check": {"ask": "?", "options": {"a": "1"}, "answer": "b"}}]}
        probs = " ".join(lessons.problems(bad))
        self.assertIn("worked example", probs)
        self.assertIn("answer is not one of its options", probs)


class TestTheScreens(unittest.TestCase):
    BADGE = "talking-to"

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
        items = dataio.load_bank()
        flags, _ = checks.run_all(items, set(SPEC), dataio.allowed_latin(dataio.load_exemplars()))
        store.import_items(self.db, items, flags, "t")
        nodes = {n for b in BADGES if b["id"] == self.BADGE for n in b["nodes"]}
        for i in items:
            if i["node"] in nodes:
                store.set_review(self.db, i["id"], "approved")
        store.add_student(self.db, "403217", "Block 3")
        self.t = server.app.test_client()
        self.t.post("/login", data={"password": "teacherpw", "next": "/teacher"})
        self.t.post("/teacher/deadlines", data={"form": "badges",
                                                "badges_from": goals.week_key(time.time())})
        self.c = server.app.test_client()
        self.c.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.c.post("/signin", data={"step": "pin", "student_id": "403217",
                                     "pin": "1234", "pin2": "1234", "next": "/"})
        self.n = server._LESSON_NO[self.BADGE]

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def lesson(self, who):
        return who.get("/badges/%s/lesson" % self.BADGE)

    def test_nothing_shows_until_the_teacher_approves(self):
        self.assertIn("/badges", self.lesson(self.c).headers["Location"])
        page = self.c.get("/badges").data.decode()
        self.assertNotIn("Start lesson", page)
        self.assertIn("Earn this badge", page)
        preview = self.lesson(self.t).data.decode()
        self.assertIn("teacher preview", preview)
        self.assertIn("Not approved yet", preview)

    def test_the_preview_leads_back_to_the_lessons_and_can_approve(self):
        preview = self.lesson(self.t).data.decode()
        self.assertIn('href="/teacher/lessons#l-%s">← Back to the lessons' % self.BADGE, preview)
        self.assertNotIn("Back to the map", preview)
        self.assertIn("Approve this lesson", preview)
        self.assertIn('id="showall"', preview)
        r = self.t.post("/teacher/lessons", data={"action": "approve", "id": self.BADGE})
        self.assertIn("/teacher/lessons#l-%s" % self.BADGE, r.headers["Location"])
        self.assertIn("Withdraw", self.lesson(self.t).data.decode())
        self.assertIn("Back to the map", self.lesson(self.c).data.decode())   # students: the map

    def test_an_approved_lesson_comes_before_the_check(self):
        self.t.post("/teacher/lessons", data={"action": "approve", "id": self.BADGE})
        page = self.c.get("/badges").data.decode()
        self.assertIn("Start lesson %d" % self.n, page)
        body = self.lesson(self.c).data.decode()
        self.assertIn("Lesson %d of %d" % (self.n, len(BADGES)), body)
        self.assertIn("Worked example", body)
        self.assertIn('class="lw"', body)
        self.assertIn("Quick check", body)
        self.assertIn("Start the check", body)
        self.assertIn("Talking to someone", body)

    def test_rewording_needs_approval_again(self):
        store.approve_teaching(self.db, lessons.key(self.BADGE), "an-older-wording")
        self.assertIn("/badges", self.lesson(self.c).headers["Location"])
        self.assertIn("changed since approval", self.t.get("/teacher/lessons").data.decode())

    def test_approve_all_and_withdraw(self):
        self.t.post("/teacher/lessons", data={"action": "approve_all"})
        self.assertIn("%d</strong> of %d lessons approved" % (len(BADGES), len(BADGES)),
                      self.t.get("/teacher/lessons").data.decode())
        self.t.post("/teacher/lessons", data={"action": "withdraw", "id": self.BADGE})
        self.assertIn("/badges", self.lesson(self.c).headers["Location"])

    def test_a_student_cannot_approve(self):
        r = self.c.post("/teacher/lessons", data={"action": "approve_all"})
        self.assertIn("/login", r.headers["Location"])
        self.assertEqual(self.server.lesson_for(self.db, self.BADGE), None)

    def test_the_map_numbers_the_lessons(self):
        page = self.c.get("/badges").data.decode()
        self.assertIn("Lesson %d · Verbs" % self.n, page)
        self.assertIn('<span class="node-icon">%d</span>' % self.n, page)


if __name__ == "__main__":
    unittest.main()
