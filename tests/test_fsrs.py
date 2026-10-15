"""FSRS: the engine, and students grading their own answers."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import checks   # noqa: E402
import dataio   # noqa: E402
import fsrs     # noqa: E402
import stats    # noqa: E402
import store    # noqa: E402
import teacher  # noqa: E402

DAY = 86400.0
T0 = time.mktime((2026, 9, 1, 15, 0, 0, 0, 0, -1))


class TestTheEngine(unittest.TestCase):
    def test_recall_is_ninety_percent_at_stability(self):
        self.assertAlmostEqual(fsrs.retrievability(10, 10), 0.9, places=6)
        self.assertAlmostEqual(fsrs.interval_days(10), 10, places=6)

    def test_first_grades_start_where_fsrs_starts(self):
        for g, s0 in zip(fsrs.GRADES, fsrs.W[:4]):
            self.assertAlmostEqual(fsrs.review(None, g, T0).stability, s0)

    def test_better_grades_mean_longer_memories(self):
        c = fsrs.review(None, fsrs.GOOD, T0)
        later = T0 + 3 * DAY
        s = [fsrs.review(c, g, later).stability for g in fsrs.GRADES]
        self.assertEqual(s, sorted(s))
        self.assertLess(s[0], c.stability)                # Again: a setback

    def test_good_on_schedule_makes_it_solid_within_weeks(self):
        c, t, solid_at = None, T0, None
        states = []
        for _ in range(4):
            c = fsrs.review(c, fsrs.GOOD, t)
            states.append(fsrs.state(c))
            if solid_at is None and states[-1] == "solid":
                solid_at = t
            t = c.due
        self.assertEqual(states[0], "shaky")
        self.assertIsNotNone(solid_at)
        self.assertLess(solid_at - T0, 21 * DAY)     # three on-time reviews: about two weeks

    def test_again_comes_back_in_the_same_sitting(self):
        c = fsrs.review(None, fsrs.AGAIN, T0)
        self.assertEqual(c.due - T0, fsrs.RELEARN_SECONDS)
        self.assertEqual(fsrs.state(c), "not yet")

    def test_old_answers_replay_from_what_the_app_checked(self):
        evs = [{"timestamp": T0, "result": "wrong", "rating": None},
               {"timestamp": T0 + 60, "result": "close", "rating": None},   # retyped typo
               {"timestamp": T0 + 120, "result": "right", "rating": None}]
        c = fsrs.replay(evs)
        self.assertEqual((c.reps, c.successes), (2, 1))

    def test_a_students_grade_beats_the_check(self):
        # A badly spelled right answer the app marked wrong, graded Good.
        c = fsrs.replay([{"timestamp": T0, "result": "wrong", "rating": 3}])
        self.assertEqual(c.last_grade, fsrs.GOOD)
        self.assertEqual(fsrs.state(c), "shaky")

    def test_rating_zero_is_not_a_review(self):
        self.assertIsNone(fsrs.replay([{"timestamp": T0, "result": "close", "rating": 0}]))

    def test_the_buttons_say_when(self):
        waits = {g: fsrs.describe_wait(s) for g, s in fsrs.preview(None, T0).items()}
        self.assertEqual(waits, {1: "5 min", 2: "1 day", 3: "3 days", 4: "16 days"})

    def test_when_everything_is_done_practice_goes_on(self):
        c = fsrs.review(None, fsrs.EASY, T0)
        cards = {"a": c, "b": fsrs.review(None, fsrs.GOOD, T0)}
        self.assertEqual(fsrs.pick(cards, ["a", "b"], now=T0 + 60), "b")   # the weaker


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
        self.items = {i["id"]: i for i in dataio.load_bank()}
        flags, _ = checks.run_all(list(self.items.values()), set(dataio.load_spec()),
                                  dataio.allowed_latin(dataio.load_exemplars()))
        store.import_items(self.db, list(self.items.values()), flags, "t")
        store.add_student(self.db, "403217", "Block 3")
        self.c = server.app.test_client()
        self.c.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.c.post("/signin", data={"step": "pin", "student_id": "403217",
                                     "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def events(self):
        return store.events_for_student(self.db, "403217")


class TestTheDrill(_App):
    def answer(self, response):
        body = self.c.get("/drill/session?week=week_of_aug_31&direction=la_en").data.decode()
        latin = body.split('name="latin" value="')[1].split('"')[0]
        fb = self.c.post("/drill/answer", data={"week": "week_of_aug_31", "direction": "la_en",
                                                "latin": latin, "ask": "la_en",
                                                "response": response, "latency_ms": "900"})
        return latin, fb.data.decode()

    def test_the_answer_shows_four_grades_and_records_nothing_yet(self):
        latin, body = self.answer("zzz")
        for name in ("Again", "Hard", "Good", "Easy"):
            self.assertIn('<span class="g-name">%s</span>' % name, body)
        self.assertIn('class="grade g1 suggest"', body)          # a miss suggests Again
        self.assertIn("Only a spelling slip?", body)
        self.assertEqual(self.events(), [])

    def test_grading_records_the_answer_with_the_grade(self):
        latin, _ = self.answer("zzz")
        r = self.c.post("/drill/grade", data={"week": "week_of_aug_31", "direction": "la_en",
                                              "latin": latin, "ask": "la_en", "response": "zzz",
                                              "latency_ms": "900", "rating": "3"})
        self.assertEqual(r.status_code, 302)
        ev = self.events()[-1]
        self.assertEqual((ev["result"], ev["rating"], ev["response"]), ("wrong", 3, "zzz"))

    def test_a_typo_is_retyped_and_counts_once(self):
        body = self.c.get("/drill/session?week=week_of_aug_31&direction=la_en").data.decode()
        latin = body.split('name="latin" value="')[1].split('"')[0]
        import drill
        right = drill.find_word(self.server._DRILL_WORDS, latin)["en"][0]
        typo = right[:-1] + ("x" if right[-1] != "x" else "y")
        self.c.post("/drill/answer", data={"week": "week_of_aug_31", "direction": "la_en",
                                           "latin": latin, "ask": "la_en", "response": typo})
        self.c.post("/drill/grade", data={"week": "week_of_aug_31", "direction": "la_en",
                                          "latin": latin, "ask": "la_en", "response": right,
                                          "rating": "3"})
        evs = self.events()
        self.assertEqual([(e["result"], e["rating"]) for e in evs], [("close", 0), ("right", 3)])
        self.assertEqual(teacher.homework_counts(evs)["vocab"], 1)

    def test_a_grade_must_be_one_of_the_four(self):
        r = self.c.post("/drill/grade", data={"latin": "aqua", "ask": "la_en", "response": "water",
                                              "rating": "5"})
        self.assertEqual(r.status_code, 400)


class TestGrammar(_App):
    def choice_item(self, node="MS-014"):
        store.set_review(self.db, [i for i in self.items.values()
                                   if i["node"] == node and i.get("format") == "choice"][0]["id"],
                         "approved")
        body = self.c.get("/practice/session?node=%s" % node).data.decode()
        iid = body.split('name="item_id" value="')[1].split('"')[0]
        return self.items[iid]

    def test_a_wrong_choice_offers_grades_and_the_menu_together(self):
        item = self.choice_item()
        wrong = [k for k in item["options"] if k != item["answer"]][0]
        body = self.c.post("/practice/answer", data={"item_id": item["id"], "picked": wrong,
                                                     "node": "MS-014", "context": "practice"}).data.decode()
        self.assertIn('class="grade g1 suggest"', body)
        self.assertIn("What happened?", body)
        self.assertEqual(self.events(), [])
        self.c.post("/practice/grade", data={"item_id": item["id"], "picked": wrong, "node": "MS-014",
                                             "context": "practice", "rating": "1",
                                             "reason_key": "should_be_right",
                                             "reason_text": "I think my answer should be right"})
        ev = self.events()[-1]
        self.assertEqual((ev["result"], ev["rating"]), ("wrong", 1))
        reasons = store.all_miss_reasons(self.db)
        self.assertEqual(reasons[-1]["reason_key"], "should_be_right")

    def test_a_drag_and_drop_question_is_graded_by_the_app(self):
        store.set_review(self.db, "MS015-LABEL-01", "approved")
        body = self.c.post("/practice/answer", data={
            "item_id": "MS015-LABEL-01", "node": "MS-015,", "context": "practice",
            "pick": ["nominative · subject", "accusative · direct object", "verb"]}).data.decode()
        self.assertNotIn('class="grade g', body)
        ev = self.events()[-1]
        self.assertEqual((ev["result"], ev["rating"]), ("right", None))
        self.assertEqual(self.c.post("/practice/grade", data={"item_id": "MS015-LABEL-01",
                                                               "rating": "4"}).status_code, 400)

    def test_a_self_check_grade_is_its_result(self):
        sc = [i for i in self.items.values() if i.get("format") == "self-check"][0]
        store.set_review(self.db, sc["id"], "approved")
        self.c.post("/practice/grade", data={"item_id": sc["id"], "typed": "my answer",
                                             "context": "practice", "rating": "2"})
        ev = self.events()[-1]
        self.assertEqual((ev["result"], ev["rating"], ev["response"]), ("close", 2, "my answer"))

    def test_progress_shows_a_strength_bar(self):
        item = self.choice_item()
        self.c.post("/practice/grade", data={"item_id": item["id"], "picked": item["answer"],
                                             "node": "MS-014", "context": "practice", "rating": "3"})
        body = self.c.get("/drill/progress").data.decode()
        self.assertIn('class="sbar"', body)
        self.assertIn("3 days", body)
        home = self.c.get("/").data.decode()
        self.assertIn("due today", home)


class TestTheColumn(unittest.TestCase):
    def test_an_old_database_gets_the_rating_column(self):
        path = os.path.join(tempfile.mkdtemp(), "old.sqlite")
        import sqlite3
        raw = sqlite3.connect(path)
        raw.execute("CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,"
                    " timestamp REAL NOT NULL, item_id TEXT NOT NULL, spec_node_id TEXT, response TEXT,"
                    " result TEXT NOT NULL, latency_ms INTEGER, context TEXT DEFAULT 'practice',"
                    " version TEXT DEFAULT 'v1')")
        raw.execute("INSERT INTO events (student_id, timestamp, item_id, result) VALUES ('403217', 1.0, 'x', 'right')")
        raw.commit(); raw.close()
        db = store.connect(path)
        store.init_db(db)
        self.assertIn("rating", db.table_columns("events"))
        self.assertIsNone(store.events_for_student(db, "403217")[0]["rating"])

    def test_stronger_counts_what_was_remembered(self):
        now = time.time()
        evs = [{"item_id": "a", "timestamp": now - 30, "result": "right", "rating": 3},
               {"item_id": "b", "timestamp": now - 20, "result": "wrong", "rating": 1},
               {"item_id": "c", "timestamp": now - 10, "result": "wrong", "rating": 2}]
        self.assertEqual(stats.session_stats(evs, now=now)["stronger"], 2)


if __name__ == "__main__":
    unittest.main()
