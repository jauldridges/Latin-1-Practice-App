"""Rushing: the rules, the teacher's flags and switch, and the slow-down message."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import magister  # noqa: E402
import rush      # noqa: E402
import store     # noqa: E402
import teacher   # noqa: E402


class TestTheRules(unittest.TestCase):
    def v(self, **kw):
        base = dict(kind="vocab", result="wrong", rating=1, response="zzz", accepted=["water"],
                    latency_ms=4000, grade_ms=3000)
        base.update(kw)
        return rush.verdict(**base)

    def test_a_right_answer_is_never_rushed(self):
        self.assertEqual(self.v(result="right", response="water", rating=4,
                                latency_ms=200, grade_ms=100), [])

    def test_honest_flashcard_study_is_not_rushed(self):
        # blank, read the answer for a few seconds, Again
        self.assertEqual(self.v(response="", rating=1), [])

    def test_grading_before_reading_the_answer(self):
        self.assertEqual(self.v(grade_ms=900), ["looked_away"])

    def test_good_on_a_non_answer(self):
        self.assertEqual(self.v(rating=3), ["graded_up"])
        self.assertEqual(self.v(rating=4, response=""), ["graded_up"])

    def test_a_bad_spelling_of_a_real_answer_may_be_graded_good(self):
        self.assertEqual(self.v(rating=3, response="watre"), [])

    def test_a_wrong_multiple_choice_pick_graded_good(self):
        self.assertEqual(self.v(kind="grammar", rating=3, response="c", accepted=(), typed=False),
                         ["graded_up"])

    def test_a_wrong_answer_faster_than_reading(self):
        self.assertEqual(self.v(latency_ms=1200), ["guessed"])
        self.assertEqual(self.v(kind="grammar", latency_ms=2000, typed=False), ["guessed"])
        self.assertEqual(self.v(kind="grammar", latency_ms=3000, typed=False), [])
        # drag and drop: under a second per box
        self.assertEqual(rush.verdict("grammar", "wrong", None, latency_ms=2500, typed=False, boxes=3),
                         ["guessed"])

    def test_a_sitting_is_flagged_at_a_third_of_ten_or_more(self):
        t = 1_000_000.0
        evs = [{"timestamp": t + i * 20, "rating": 3, "context": "practice",
                "rush": "graded_up" if i < 4 else None} for i in range(12)]
        flags = rush.flagged_sittings(evs)
        self.assertEqual((flags[0]["cards"], flags[0]["rushed"]), (12, 4))
        self.assertEqual(flags[0]["reasons"], {"graded_up": 4})
        self.assertEqual(rush.flagged_sittings(evs[:9]), [])            # fewer than 10 cards
        evs[3]["rush"] = None
        self.assertEqual(rush.flagged_sittings(evs), [])                # 3 of 12 is under a third

    def test_three_in_a_row_is_the_moment_to_say_slow_down(self):
        t = time.time()
        evs = [{"timestamp": t - 30 + i, "rating": 3, "context": "practice", "rush": "guessed"}
               for i in range(3)]
        self.assertTrue(rush.rushing_now(evs, now=t))
        evs.append({"timestamp": t, "rating": 3, "context": "practice", "rush": None})
        self.assertFalse(rush.rushing_now(evs, now=t))


class _App(unittest.TestCase):
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
        teacher.COUNT_RUSHED = True

    def grade(self, response, rating, grade_ms, latency_ms=4000, latin="aqua"):
        self.student.post("/drill/grade", data={"week": "week_of_aug_31", "direction": "la_en",
                                                "latin": latin, "ask": "la_en", "response": response,
                                                "rating": str(rating), "grade_ms": str(grade_ms),
                                                "latency_ms": str(latency_ms)})

    def rushed_sitting(self, n=12):
        for i in range(n):
            self.grade("zzz", 4, 300)


class TestRecording(_App):
    def test_the_verdict_is_stored_with_the_answer(self):
        self.grade("zzz", 4, 400)
        self.grade("water", 3, 300, latency_ms=900)
        evs = store.events_for_student(self.db, "403217")
        self.assertEqual(evs[0]["rush"], "looked_away,graded_up")
        self.assertEqual(evs[0]["grade_ms"], 400)
        self.assertIsNone(evs[1]["rush"])

    def test_the_grade_buttons_time_the_answer(self):
        body = self.student.post("/drill/answer", data={"week": "week_of_aug_31", "direction": "la_en",
                                                        "latin": "aqua", "ask": "la_en",
                                                        "response": "zzz"}).data.decode()
        self.assertIn('name="grade_ms"', body)


class TestTheTeacher(_App):
    def test_the_dashboard_flags_a_rushed_sitting(self):
        self.rushed_sitting()
        body = self.teacher.get("/teacher").data.decode()
        self.assertIn("⚑ 12 of 12 rushed", body)
        page = self.teacher.get("/teacher/student/403217").data.decode()
        self.assertIn('id="rushed"', page)
        self.assertIn("graded Good or Easy on a non-answer", page)

    def test_rushed_cards_count_until_the_teacher_says_otherwise(self):
        self.grade("zzz", 4, 300)
        self.grade("land", 3, 3000, latin="terra")
        page = self.teacher.get("/teacher/deadlines").data.decode()
        self.assertIn("Rushed cards", page)
        self.assertIn('value="yes" checked', page)
        self.assertIn("2 of 50 cards", self.student.get("/").data.decode())
        self.teacher.post("/teacher/deadlines", data={"form": "rushed", "count_rushed": "no"})
        self.assertEqual(store.get_setting(self.db, "count_rushed"), False)
        self.assertIn("1 of 50 cards", self.student.get("/").data.decode())

    def test_a_student_cannot_change_the_switch(self):
        r = self.student.post("/teacher/deadlines", data={"form": "rushed", "count_rushed": "no"})
        self.assertIn("/login", r.headers["Location"])
        self.assertIsNone(store.get_setting(self.db, "count_rushed"))


class TestTheSlowDownMessage(_App):
    def test_three_rushed_cards_in_a_row_bring_the_magister(self):
        self.assertNotIn('class="magister small"', self.student.get("/drill/session").data.decode())
        self.rushed_sitting(3)
        body = self.student.get("/drill/session").data.decode()
        self.assertIn('class="magister small"', body)
        self.assertIn(magister.DEFAULT_SLOWDOWN, body)       # nothing approved yet: the default

    def test_an_approved_slow_down_line_is_used(self):
        self.teacher.post("/teacher/magister/save", data={"action": "approve", "id": "slowdown-03"})
        self.rushed_sitting(3)
        self.assertIn("Even Caesar read his maps", self.student.get("/drill/session").data.decode())


if __name__ == "__main__":
    unittest.main()
