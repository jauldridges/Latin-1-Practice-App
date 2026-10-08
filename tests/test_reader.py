"""The Reader: a class passage, every word tappable, questions after."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import goals     # noqa: E402
import readings  # noqa: E402
import store     # noqa: E402
import teacher   # noqa: E402

ALL = readings.load_all()
CIN = ALL["cincinnatus"]


class TestThePassages(unittest.TestCase):
    def test_every_passage_is_well_formed(self):
        # Sentences in order, each in a paragraph, every word glossed, every
        # gloss used, every question's answer among its options.
        self.assertTrue(ALL)
        for slug, r in ALL.items():
            self.assertEqual(readings.problems(r), [], slug)

    def test_cincinnatus_is_the_whole_story(self):
        self.assertEqual(len(CIN["sentences"]), 20)
        self.assertEqual(CIN["title"], "Fābula dē Cincinnātō")
        self.assertEqual(len(CIN["questions"]), 10)

    def test_a_phrase_is_one_tap(self):
        words = [p for p in CIN["by_n"][7]["pieces"] if p["kind"] == "word"]
        self.assertIn(("in perīculō", "in danger"), [(p["text"], p["gloss"]) for p in words])

    def test_the_packets_underlined_words_are_underlined(self):
        p = {x["text"]: x for x in CIN["by_n"][1]["pieces"] if x["kind"] == "word"}
        self.assertTrue(p["rēgem"]["new"])
        self.assertEqual((p["rēgem"]["gloss"], p["rēgem"]["note"]),
                         ("king", "Direct Object, accusative"))
        self.assertFalse(p["habet"]["new"])

    def test_the_same_form_can_mean_different_jobs_in_different_sentences(self):
        # Rōmānī is a subject in 17 and someone spoken to in 16.
        def note(n):
            return [p["note"] for p in CIN["by_n"][n]["pieces"] if p["text"] == "Rōmānī"][0]
        self.assertEqual(note(16), "Vocative")
        self.assertEqual(note(17), "Subject, nominative")

    def test_a_missing_gloss_is_caught(self):
        r = readings.load_one(CIN["path"])
        del r["by_n"][5]["words"]["bellum"]
        r["by_n"][5]["pieces"] = readings.pieces(r["by_n"][5])
        self.assertTrue(any("'bellum' has no gloss" in p for p in readings.problems(r)))

    def test_questions_sit_with_the_paragraph_they_ask_about(self):
        by_para = readings.questions_by_paragraph(CIN)
        self.assertEqual([[q["id"] for q in qs] for qs in by_para],
                         [["q1", "q2", "q3"], ["q4", "q5"], ["q6"], ["q7", "q8", "q9", "q10"]])
        self.assertEqual([q["number"] for qs in by_para for q in qs], list(range(1, 11)))

    def test_grading(self):
        picks = {q["id"]: q["answer"] for q in CIN["questions"]}
        picks["q2"] = "b"
        del picks["q3"]
        g = readings.grade(CIN, picks)
        self.assertEqual((g["q1"], g["q2"], g["q3"]), ("right", "wrong", "blank"))

    def test_reading_is_not_homework(self):
        ev = {"item_id": "read:cincinnatus:q1", "context": "reading", "timestamp": 1.0,
              "result": "right", "student_id": "s"}
        self.assertEqual(teacher.homework_counts([ev]), {"vocab": 0, "grammar": 0})
        self.assertEqual(goals.spacing_flag([ev]), "never")


class TestScreens(unittest.TestCase):
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

    def publish(self):
        self.teacher.post("/teacher/reader", data={"slug": "cincinnatus", "action": "publish"})

    def test_students_cannot_see_it_until_it_is_published(self):
        self.assertEqual(self.student.get("/read/cincinnatus").status_code, 404)
        self.assertNotIn("Cincinnātō", self.student.get("/read").data.decode())
        self.publish()
        self.assertEqual(self.student.get("/read/cincinnatus").status_code, 200)
        self.assertIn("Cincinnātō", self.student.get("/read").data.decode())

    def test_the_teacher_can_preview_before_publishing(self):
        body = self.teacher.get("/read/cincinnatus").data.decode()
        self.assertIn("Teacher preview", body)
        self.assertIn("not published", body)

    def test_nobody_else_gets_in(self):
        r = self.server.app.test_client().get("/read/cincinnatus")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/signin", r.headers["Location"])
        r = self.student.get("/teacher/reader")
        self.assertIn("/login", r.headers["Location"])

    def test_every_word_is_a_button_with_its_gloss(self):
        self.publish()
        body = self.student.get("/read/cincinnatus").data.decode()
        self.assertIn('class="rw new" data-gloss="king" data-note="Direct Object, accusative">rēgem</button>', body)
        self.assertIn('data-gloss="in danger" data-note="">in perīculō</button>', body)
        self.assertIn('id="s20"', body)
        self.assertNotIn('data-gloss=""', body)
        self.assertIn('id="glosspop"', body)

    def test_each_question_comes_right_after_its_paragraph(self):
        # So a student answers while reading: question 4 (about sentence 6)
        # comes after the second paragraph and before the third.
        self.publish()
        body = self.student.get("/read/cincinnatus").data.decode()
        self.assertLess(body.index('id="s10"'), body.index('id="q-q4"'))
        self.assertLess(body.index('id="q-q4"'), body.index('id="s11"'))
        self.assertLess(body.index('id="q-q1"'), body.index('id="s5"'))

    def test_checking_one_question_in_place(self):
        self.publish()
        r = self.student.post("/read/cincinnatus/check", data={"qid": "q4", "picked": "b"})
        self.assertEqual(r.get_json(), {"result": "wrong"})
        r = self.student.post("/read/cincinnatus/check", data={"qid": "q4", "picked": "a"})
        self.assertEqual(r.get_json(), {"result": "right"})
        self.assertEqual(self.student.post("/read/cincinnatus/check",
                                           data={"qid": "q4", "picked": ""}).get_json(),
                         {"result": "blank"})
        self.assertEqual(self.student.post("/read/cincinnatus/check",
                                           data={"qid": "nope", "picked": "a"}).status_code, 404)
        evs = store.events_for_student(self.db, "403217")
        self.assertEqual([(e["result"], e["context"], e["spec_node_id"]) for e in evs],
                         [("wrong", "reading", "CR-009"), ("right", "reading", "CR-009")])
        page = self.teacher.get("/teacher/reader").data.decode()
        self.assertIn("403217", page)
        self.assertIn("1 of 10", page)            # latest answer to each question

    def test_every_question_has_its_own_check_button(self):
        self.publish()
        body = self.student.get("/read/cincinnatus").data.decode()
        self.assertEqual(body.count('class="minibtn rq-check"'), 10)
        self.assertNotIn("Check my answers", body)

    def test_without_javascript_a_check_button_checks_its_question(self):
        self.publish()
        body = self.student.post("/read/cincinnatus", data={"only": "q4", "q4": "b", "q1": "a"}).data.decode()
        self.assertIn("Not quite.", body)
        self.assertIn('data-hint="w6-0 w6-3 w6-6 w6-8"', body)     # Aequī, populus Italicus, Rōmānōs, oppugnant
        self.assertEqual(len(store.events_for_student(self.db, "403217")), 1)

    def test_the_hint_lights_up_the_latin_that_answers_it(self):
        def words(q):
            out = []
            for wid in readings.hint_targets(CIN, q):
                n, i = wid[1:].split("-")
                out.append(CIN["by_n"][int(n)]["pieces"][int(i)]["text"])
            return " ".join(out)
        qs = {q["id"]: q for q in CIN["questions"]}
        self.assertEqual(words(qs["q1"]), "quod Rōmānī rēgem timent")
        self.assertEqual(words(qs["q5"]), "Cōnsulēs Aequōs nōn superant Senātus dictātōrem nōminat")

    def test_a_hint_that_isnt_in_the_story_is_caught(self):
        r = readings.load_one(CIN["path"])
        r["questions"][0]["hint"] = {1: "rēgem amant"}
        self.assertTrue(any("hint" in p for p in readings.problems(r)))

    def test_a_teacher_checking_records_nothing(self):
        r = self.teacher.post("/read/cincinnatus/check", data={"qid": "q1", "picked": "a"})
        self.assertEqual(r.get_json(), {"result": "right"})
        self.assertEqual(store.all_events(self.db), [])

    def test_unpublish(self):
        self.publish()
        self.teacher.post("/teacher/reader", data={"slug": "cincinnatus", "action": "withdraw"})
        self.assertEqual(self.student.get("/read/cincinnatus").status_code, 404)


if __name__ == "__main__":
    unittest.main()
