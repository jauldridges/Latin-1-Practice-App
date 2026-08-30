"""Tests for proctored quizzes: deferred grading, close handling, resumability."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quiz    # noqa: E402
import store   # noqa: E402

ITEMS = {
    "C1": {"id": "C1", "node": "MS-002", "format": "choice",
           "options": {"a": "hard k", "b": "soft s"}, "answer": "a"},
    "B1": {"id": "B1", "node": "MS-001", "format": "boxes", "order_matters": False,
           "boxes": [{"label": "Letter", "answer": ["j"]},
                     {"label": "Letter", "answer": ["w"]}]},
    "B2": {"id": "B2", "node": "MS-022", "format": "boxes", "order_matters": False,
           "boxes": [{"label": "Noun", "answer": ["nauta"]},
                     {"label": "Noun", "answer": ["agricola"]},
                     {"label": "Noun", "answer": ["poeta"]}]},
    "S1": {"id": "S1", "node": "MS-047", "format": "self-check",
           "model_answer": "The sailor is good."},
}
ORDER = ["C1", "B1", "B2", "S1"]


class TestGrading(unittest.TestCase):
    def test_all_correct(self):
        answers = {"C1": "a", "B1": ["j", "w"], "B2": ["nauta", "agricola", "poeta"],
                   "S1": "the sailor is good"}
        r = quiz.grade_attempt(ITEMS, ORDER, answers)
        self.assertEqual(r["C1"]["result"], "right")
        self.assertEqual(r["B1"]["result"], "right")
        self.assertEqual(r["B2"]["result"], "right")
        self.assertEqual(r["S1"]["result"], "self")

    def test_close_is_accepted_not_reprompted(self):
        # A typo on a long enough word is CLOSE: recorded as close, never turned
        # into a mid-quiz "check your spelling" hint, never marked wrong.
        answers = {"B2": ["nauta", "agricol", "poeta"]}
        r = quiz.grade_attempt(ITEMS, ["B2"], answers)
        self.assertEqual(r["B2"]["result"], "close")

    def test_close_counts_as_accepted_in_the_summary(self):
        results = {"a": {"result": "right"}, "b": {"result": "close"},
                   "c": {"result": "wrong"}}
        s = quiz.summarise(results)
        self.assertEqual(s["accepted"], 2)          # right + close
        self.assertEqual(s["close"], 1)             # still visible on its own
        self.assertEqual(s["wrong"], 1)

    def test_wrong_letter_is_wrong_not_close(self):
        # The short-answer rule still holds inside a quiz.
        r = quiz.grade_attempt(ITEMS, ["B1"], {"B1": ["j", "q"]})
        self.assertEqual(r["B1"]["result"], "wrong")

    def test_blank_is_unanswered_not_wrong_at_grade_time(self):
        r = quiz.grade_attempt(ITEMS, ORDER, {"C1": "a"})
        self.assertEqual(r["B1"]["result"], "unanswered")
        self.assertEqual(r["S1"]["result"], "unanswered")

    def test_blank_becomes_wrong_in_the_event_record(self):
        # Leaving it blank is an outcome, so the history records it as wrong.
        results = quiz.grade_attempt(ITEMS, ORDER, {"C1": "a"})
        rows = quiz.events_for_attempt(results, ITEMS, "quiz")
        by_item = {r["item_id"]: r for r in rows}
        self.assertEqual(by_item["B1"]["result"], "wrong")
        self.assertEqual(by_item["C1"]["result"], "right")

    def test_self_check_items_are_not_evented_until_reported(self):
        results = quiz.grade_attempt(ITEMS, ORDER, {"S1": "something"})
        rows = quiz.events_for_attempt(results, ITEMS, "quiz")
        self.assertNotIn("S1", {r["item_id"] for r in rows})

    def test_events_carry_the_quiz_context_and_version(self):
        results = quiz.grade_attempt(ITEMS, ["C1"], {"C1": "b"})
        rows = quiz.events_for_attempt(results, ITEMS, "exam")
        self.assertEqual(rows[0]["context"], "exam")
        self.assertEqual(rows[0]["version"], "v1")
        self.assertEqual(rows[0]["spec_node_id"], "MS-002")


class TestProgress(unittest.TestCase):
    def test_unanswered_positions_are_one_based(self):
        answers = {"C1": "a", "B2": ["nauta", "agricola", "poeta"]}
        self.assertEqual(quiz.unanswered_positions(ITEMS, ORDER, answers), [2, 4])

    def test_answered_count(self):
        self.assertEqual(quiz.answered_count(ITEMS, ORDER, {"C1": "a"}), 1)

    def test_blank_box_list_counts_as_unanswered(self):
        self.assertTrue(quiz.answer_is_blank("boxes", ["", "  "]))
        self.assertFalse(quiz.answer_is_blank("boxes", ["", "j"]))


class TestAttemptLifecycle(unittest.TestCase):
    def setUp(self):
        self.p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_q.sqlite")
        self.db = store.connect(self.p)
        store.init_db(self.db)
        store.create_quiz(self.db, "qz", "Friday Quiz", ORDER, context="quiz")

    def tearDown(self):
        self.db.close()
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(self.p + suffix):
                os.remove(self.p + suffix)

    def test_quiz_is_frozen(self):
        q = store.get_quiz(self.db, "qz")
        self.assertEqual(q["item_ids"], ORDER)

    def test_answers_save_as_you_go_and_resume(self):
        a = store.get_or_start_attempt(self.db, "qz", "sam")
        store.save_attempt_answer(self.db, a["attempt_id"], "C1", "a")
        again = store.get_or_start_attempt(self.db, "qz", "sam")
        self.assertEqual(again["attempt_id"], a["attempt_id"])   # same sitting
        self.assertEqual(again["answers"]["C1"], "a")            # work preserved

    def test_nothing_is_graded_before_submit(self):
        a = store.get_or_start_attempt(self.db, "qz", "sam")
        store.save_attempt_answer(self.db, a["attempt_id"], "C1", "a")
        self.assertIsNone(store.get_attempt(self.db, a["attempt_id"])["results"])

    def test_submitted_work_is_locked(self):
        a = store.get_or_start_attempt(self.db, "qz", "sam")
        store.save_attempt_answer(self.db, a["attempt_id"], "C1", "a")
        results = quiz.grade_attempt(ITEMS, ORDER, {"C1": "a"})
        store.submit_attempt(self.db, a["attempt_id"], results)
        # further edits are refused
        self.assertFalse(store.save_attempt_answer(self.db, a["attempt_id"], "C1", "b"))
        self.assertEqual(store.get_attempt(self.db, a["attempt_id"])["answers"]["C1"], "a")

    def test_one_attempt_per_student_per_quiz(self):
        a = store.get_or_start_attempt(self.db, "qz", "sam")
        b = store.get_or_start_attempt(self.db, "qz", "sam")
        self.assertEqual(a["attempt_id"], b["attempt_id"])
        self.assertEqual(len(store.quiz_attempts(self.db, "qz")), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
