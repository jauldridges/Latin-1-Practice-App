"""The grey line above every prompt: why the spacing system chose this card now."""

import html
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fsrs   # noqa: E402
import store  # noqa: E402

NOW = time.mktime((2026, 11, 9, 15, 0, 0, 0, 0, -1))
DAY = fsrs.DAY


class TestTheSentence(unittest.TestCase):
    def test_new(self):
        self.assertEqual(fsrs.why_now(None, NOW), "New word: this is your first time seeing it.")
        self.assertIn("New question", fsrs.why_now(None, NOW, thing="question"))

    def test_a_recent_miss(self):
        c = fsrs.review(None, fsrs.AGAIN, NOW - 6 * 60)
        self.assertEqual(fsrs.why_now(c, NOW), "You missed this 6 minutes ago. Missed cards come "
                                               "back within minutes until they stick.")

    def test_a_review_as_it_fades(self):
        c = fsrs.review(None, fsrs.GOOD, NOW - 4 * DAY)
        self.assertTrue(c.due <= NOW)
        self.assertIn("Last seen 4 days ago, just as it was starting to fade", fsrs.why_now(c, NOW))

    def test_long_overdue(self):
        c = fsrs.review(None, fsrs.GOOD, NOW - 40 * DAY)
        self.assertIn("it was due a while ago", fsrs.why_now(c, NOW))

    def test_a_miss_shown_again_before_its_time(self):
        c = fsrs.review(None, fsrs.AGAIN, NOW - 60)
        self.assertTrue(c.due > NOW)
        self.assertEqual(fsrs.why_now(c, NOW), "You missed this 1 minute ago, so it's back for another try.")

    def test_extra_practice_says_when_the_real_review_is(self):
        c = fsrs.review(None, fsrs.GOOD, NOW - 3600)
        s = fsrs.why_now(c, NOW)
        self.assertIn("Nothing is due right now, so this is extra practice", s)
        self.assertIn("in 3 days", s)

    def test_times_read_like_english(self):
        self.assertEqual(fsrs._ago(60), "1 minute ago")
        self.assertEqual(fsrs._ago(2 * 3600), "2 hours ago")
        self.assertEqual(fsrs._ago(1.2 * DAY), "yesterday")
        self.assertEqual(fsrs._ago(90 * DAY), "about 3 months ago")
        self.assertEqual(fsrs._in(DAY), "tomorrow")
        self.assertEqual(fsrs._in(70 * DAY), "in about 2 months")

    def test_never_says_mastery(self):
        cards = [None, fsrs.review(None, fsrs.AGAIN, NOW - 60), fsrs.review(None, fsrs.GOOD, NOW - 99 * DAY)]
        for c in cards:
            self.assertNotIn("master", fsrs.why_now(c, NOW).lower())


class TestOnTheScreens(unittest.TestCase):
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
        self.student = server.app.test_client()
        self.student.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.student.post("/signin", data={"step": "pin", "student_id": "403217",
                                           "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def page(self, url):
        return html.unescape(self.student.get(url).data.decode())

    def test_a_vocabulary_card_says_why_above_the_prompt(self):
        body = self.page("/drill/session?week=all&direction=la_en")
        self.assertIn('class="why-now"', body)
        self.assertIn("New word: this is your first time seeing it.", body)
        self.assertLess(body.index('class="why-now"'), body.index('class="prompt'))
        self.assertNotIn("mastery", body.lower())

    def test_a_grammar_question_says_why_above_the_question(self):
        body = self.page("/practice/session")
        if 'class="stem"' not in body:
            self.skipTest("no approved grammar questions in a fresh database")
        self.assertIn('class="why-now"', body)
        self.assertLess(body.index('class="why-now"'), body.index('class="stem"'))
