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
        self.assertEqual((n["how-to-study"], n["origins"], n["sounds"]), (1, 2, 3))
        self.assertLess(n["subjects-objects"], n["first-declension"])
        self.assertLess(n["genitive"], n["dative"])

    def test_a_problem_is_named(self):
        bad = {"steps": [{"say": "x"}, {"check": {"ask": "?", "options": {"a": "1"}, "answer": "b"}}]}
        probs = " ".join(lessons.problems(bad))
        self.assertIn("worked example", probs)
        self.assertIn("answer is not one of its options", probs)


class TestHowToStudy(unittest.TestCase):
    """The first badge: how memory works and the Lēgēs Magistrī, then a check."""

    def test_the_badge_and_its_lesson(self):
        b = next(b for b in BADGES if b["id"] == "how-to-study")
        self.assertEqual(b["nodes"], ["SK-001", "SK-002"])
        self.assertTrue(all(n in SPEC for n in b["nodes"]))
        steps = LESSONS["how-to-study"]["steps"]
        text = str(steps).lower()
        self.assertIn("spaced practice", text)
        self.assertIn("lēgēs magistrī", text)
        self.assertEqual(lessons.kind(steps[-2]), "check")

    def test_the_worked_example_is_the_real_schedule(self):
        import fsrs
        ex = LESSONS["how-to-study"]["steps"][1]["example"]["words"]
        t, card = 1.7e9, None
        for w, nxt in zip(ex, ex[1:]):
            card = fsrs.review(card, fsrs.GOOD, t)
            gap = round((card.due - t) / 86400)
            self.assertIn("back in %d days" % gap, w["note"])
            self.assertEqual(int(nxt["w"].split()[1]) - int(w["w"].split()[1]), gap)
            t = card.due
        self.assertEqual(fsrs.state(card), "solid")              # after Day 15

    def test_its_check_questions(self):
        bank = [i for i in dataio.load_bank() if i["node"] in ("SK-001", "SK-002")]
        self.assertGreaterEqual(len([i for i in bank if i["node"] == "SK-001"]), 6)
        self.assertGreaterEqual(len([i for i in bank if i["node"] == "SK-002"]), 6)
        flags, _ = checks.run_all(bank, set(SPEC), dataio.allowed_latin(dataio.load_exemplars()))
        self.assertEqual({k: v for k, v in flags.items() if v}, {})
        text = " ".join(str(i) for i in bank).lower()
        self.assertNotIn("mastery", text)
        self.assertNotIn("lēx ", text)                              # law numbers move; never quoted


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

    def review(self, bid=None):
        return self.t.get("/teacher/lessons/%s" % (bid or self.BADGE))

    def test_nothing_shows_until_the_teacher_approves(self):
        self.assertIn("/badges", self.lesson(self.c).headers["Location"])
        page = self.c.get("/badges").data.decode()
        self.assertNotIn("Start lesson", page)
        self.assertIn("Earn this badge", page)
        self.assertIn("not yet approved", self.review().data.decode())

    def test_the_review_screen(self):
        # A teacher opening the student's lesson link lands on the review screen.
        self.assertIn("/teacher/lessons/%s" % self.BADGE, self.lesson(self.t).headers["Location"])
        page = self.review().data.decode()
        self.assertIn("Approve &amp; next", page)
        self.assertIn('id="showall"', page)
        self.assertIn("← All lessons", page)
        self.assertIn("Skip →", page)
        self.assertIn("Quick check in the lesson", page)
        self.assertIn("How do you tell several people", page)       # the lesson's quick check
        self.assertIn("The badge check asks from these", page)
        self.assertIn("<strong>Answer:</strong>", page)                # its approved questions
        self.assertNotIn("Back to the map", page)

    def test_approve_and_next_goes_to_the_next_unapproved_lesson(self):
        order = self.server._lesson_order()
        i = order.index(self.BADGE)
        # the one right after is already approved: it is skipped
        after = order[i + 1]
        self.t.post("/teacher/lessons", data={"action": "approve", "id": after})
        r = self.t.post("/teacher/lessons", data={"action": "approve", "id": self.BADGE, "then": "next"})
        self.assertTrue(r.headers["Location"].endswith("/teacher/lessons/%s" % order[i + 2]))
        self.assertIn("approved", self.review().data.decode())
        self.assertIn("Withdraw", self.review().data.decode())

    def test_the_last_approval_says_done(self):
        self.t.post("/teacher/lessons", data={"action": "approve_all"})
        self.t.post("/teacher/lessons", data={"action": "withdraw", "id": self.BADGE})
        r = self.t.post("/teacher/lessons", data={"action": "approve", "id": self.BADGE, "then": "next"})
        self.assertIn("done=1", r.headers["Location"])
        self.assertIn("Every lesson is approved", self.t.get(r.headers["Location"]).data.decode())

    def test_the_list_starts_reviewing(self):
        page = self.t.get("/teacher/lessons").data.decode()
        first = self.server._lesson_order()[0]
        self.assertIn('href="/teacher/lessons/%s">Start reviewing' % first, page)
        self.assertIn('href="/teacher/lessons/%s"><strong>' % self.BADGE, page)

    def test_waiting_questions_are_approved_from_the_review_screen(self):
        bid = "how-to-study"
        page = self.review(bid).data.decode()
        self.assertIn("17 more questions waiting for your approval", page)
        self.assertIn("Approve these 17 questions", page)
        self.assertNotIn("how-to-study", [b["id"] for b in badges.available(
            BADGES, SPEC, store.approved_items(self.db), time.strftime("%Y-%m-%d"))])
        r = self.t.post("/teacher/lessons", data={"action": "approve_questions", "id": bid, "then": "stay"})
        self.assertTrue(r.headers["Location"].endswith("/teacher/lessons/" + bid))
        page = self.review(bid).data.decode()
        self.assertNotIn("waiting for your approval", page)
        self.assertIn("The badge check asks from these 17 approved questions", page)
        self.assertIn("how-to-study", [b["id"] for b in badges.available(
            BADGES, SPEC, store.approved_items(self.db), time.strftime("%Y-%m-%d"))])
        self.assertIn("/login", self.c.post("/teacher/lessons", data={
            "action": "approve_questions", "id": bid}).headers["Location"])

    def test_a_student_cannot_review(self):
        self.assertIn("/login", self.c.get("/teacher/lessons/%s" % self.BADGE).headers["Location"])

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
