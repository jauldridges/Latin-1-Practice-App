"""Each card counts toward homework once a day, and a finished topic stops.

In October 2026 a student answered MW-017's two questions 101 times to fill
the weekly grammar goal. Practice may repeat; homework credit may not.
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import checks   # noqa: E402
import dataio   # noqa: E402
import goals    # noqa: E402
import store    # noqa: E402
import teacher  # noqa: E402

RECALL, RECOG = "MW017-RECALL-01", "MW017-RECOG-01"


def ev(item, ts, result="right", rating=3, node="MW-017"):
    return {"item_id": item, "timestamp": ts, "result": result, "rating": rating,
            "spec_node_id": node, "context": "practice"}


def noon(y, m, d):
    return time.mktime((y, m, d, 12, 0, 0, 0, 0, -1))


class TestTheRule(unittest.TestCase):
    def test_the_same_question_counts_once_a_day(self):
        t = noon(2026, 10, 14)
        loop = [ev(RECALL if i % 2 else RECOG, t + i * 10) for i in range(100)]
        self.assertEqual(teacher.homework_counts(loop)["grammar"], 2)
        loop += [ev(RECALL, t + 86400)]                      # tomorrow it counts again
        self.assertEqual(teacher.homework_counts(loop)["grammar"], 3)

    def test_a_word_is_one_card_in_either_direction(self):
        t = noon(2026, 10, 14)
        evs = [ev("vocab:aqua:la_en", t, node=None), ev("vocab:aqua:en_la", t + 60, node=None),
               ev("vocab:via:la_en", t + 120, node=None)]
        self.assertEqual(teacher.homework_counts(evs)["vocab"], 2)

    def test_past_weeks_are_recounted(self):
        # 100 answers to two questions on one Wednesday: that week is not done.
        t = noon(2026, 10, 7)
        evs = [ev(RECALL if i % 2 else RECOG, t + i * 10) for i in range(100)]
        evs += [ev("vocab:w%d:la_en" % i, t + 2000 + i, node=None) for i in range(50)]
        weeks = goals.homework_weeks("2026-10-03", [])
        rows = {r["key"]: r for r in goals.homework_history(evs, None, weeks,
                                                             now=noon(2026, 10, 17))}
        wk = rows[goals.week_key(t)]
        self.assertEqual((wk["counts"]["grammar"], wk["status"]), (2, "not done"))


class _App(unittest.TestCase):
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
        flags, _ = checks.run_all(items, set(dataio.load_spec()),
                                  dataio.allowed_latin(dataio.load_exemplars()))
        store.import_items(self.db, items, flags, "t")
        for iid in (RECALL, RECOG):
            store.set_review(self.db, iid, "approved")
        store.add_student(self.db, "403217", "Block 3")
        self.c = server.app.test_client()
        self.c.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.c.post("/signin", data={"step": "pin", "student_id": "403217",
                                     "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def did(self, item, rating=3, ago=60):
        store.record_event(self.db, "403217", item, "MW-017", "x",
                           "right" if rating >= 3 else "wrong",
                           timestamp=time.time() - ago, rating=rating)

    def session(self):
        return self.c.get("/practice/session?node=MW-017").data.decode()


class TestAFinishedTopic(_App):
    def test_the_topic_stops_when_every_question_is_done_for_today(self):
        self.assertIn('name="item_id"', self.session())
        self.did(RECALL)
        self.did(RECOG, ago=30)
        body = self.session()
        self.assertIn("That's everything in this topic for today", body)
        self.assertNotIn('name="item_id"', body)
        self.assertIn('href="/practice/session"', body)       # on to a mix

    def test_a_question_graded_again_keeps_the_topic_open(self):
        self.did(RECOG)
        self.did(RECALL, rating=1, ago=600)                   # back after 5 minutes
        body = self.session()
        self.assertIn('value="%s"' % RECALL, body)
        self.assertIn("extra", body)                          # already counted today
        self.assertIn("won't add to this week's cards", body)

    def test_a_fresh_card_carries_no_note(self):
        self.assertNotIn("won't add to this week's cards", self.session())

    def test_the_home_screen_counts_the_loop_once(self):
        for i in range(40):
            self.did(RECALL if i % 2 else RECOG, ago=400 - i)
        self.assertIn("2 of 50 cards", self.c.get("/").data.decode())


if __name__ == "__main__":
    unittest.main()
