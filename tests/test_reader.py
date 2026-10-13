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
        self.assertEqual(len(CIN["questions"]), 17)

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
                         [["p1", "q2", "p2"], ["q4", "p3", "q5", "p4"], ["p5", "q6", "p6"],
                          ["q7", "p7", "q8", "q9", "p8", "q10", "p9"]])
        self.assertEqual([q["number"] for qs in by_para for q in qs], list(range(1, 18)))

    def test_grading(self):
        picks = {q["id"]: q["answer"] for q in CIN["questions"] if "answer" in q}
        picks["q2"] = "b"
        del picks["p2"]
        picks["p3"] = "The Aequi attack and the consuls can't win."
        g = readings.grade(CIN, picks)
        self.assertEqual((g["p1"], g["q2"], g["p2"], g["p3"], g["p6"]),
                         ("right", "wrong", "blank", "self", "blank"))

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
        self.assertLess(body.index('id="q-p1"'), body.index('id="s5"'))

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
        self.assertIn("1 of 17", page)            # latest answer to each question

    def test_every_question_has_its_own_check_button(self):
        self.publish()
        body = self.student.get("/read/cincinnatus").data.decode()
        self.assertEqual(body.count('class="minibtn rq-check"'), 17)
        self.assertNotIn("Check my answers", body)

    def test_without_javascript_a_check_button_checks_its_question(self):
        self.publish()
        body = self.student.post("/read/cincinnatus", data={"only": "q4", "q4": "b", "p1": "a"}).data.decode()
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
        self.assertEqual(words(qs["p1"]), "quod Rōmānī rēgem timent")
        self.assertEqual(words(qs["p3"]), "bellum magnum est Exercitus Rōmānus in perīculō est Cōnsulēs Aequōs nōn superant")

    def test_the_packet_questions_are_all_there_in_the_packets_words(self):
        asks = {q["id"]: q["ask"] for q in CIN["questions"]}
        self.assertEqual(asks["p1"], "Sentence 1: Why does Rome have no king?")
        self.assertEqual(asks["p6"], "Sentence 14: Find the vocative and one imperative. "
                                     "Then translate the messengers’ command.")
        self.assertEqual(sorted(k for k in asks if k.startswith("p")),
                         ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"])
        written = [q["id"] for q in CIN["questions"] if readings.is_open(q)]
        self.assertEqual(written, ["p3", "p6", "p7", "p8", "p9"])

    def test_a_written_answer_question_needs_a_model(self):
        r = readings.load_one(CIN["path"])
        del readings.question(r, "p3")["model"]
        self.assertTrue(any("model answer" in p for p in readings.problems(r)))

    def test_a_hint_that_isnt_in_the_story_is_caught(self):
        r = readings.load_one(CIN["path"])
        r["questions"][0]["hint"] = {1: "rēgem amant"}
        self.assertTrue(any("hint" in p for p in readings.problems(r)))

    def test_a_written_answer_shows_the_model_then_records_what_they_say(self):
        self.publish()
        r = self.student.post("/read/cincinnatus/check", data={"qid": "p6", "picked": ""})
        self.assertEqual(r.get_json(), {"result": "blank"})          # no model for a blank
        typed = "Cincinnāte is vocative, venī is a command: Cincinnatus, come! Save Rome!"
        r = self.student.post("/read/cincinnatus/check", data={"qid": "p6", "picked": typed})
        self.assertEqual(r.get_json()["result"], "self")
        self.assertIn("Cincinnatus, come! Save Rome!", r.get_json()["model"])
        self.assertEqual(store.events_for_student(self.db, "403217"), [])   # not yet
        r = self.student.post("/read/cincinnatus/report",
                              data={"qid": "p6", "reported": "partly", "typed": typed})
        self.assertEqual(r.get_json(), {"result": "close"})
        ev = store.events_for_student(self.db, "403217")[-1]
        self.assertEqual((ev["item_id"], ev["result"], ev["response"]),
                         ("read:cincinnatus:p6", "close", typed))
        page = self.teacher.get("/teacher/reader").data.decode()
        self.assertIn("Written answers", page)
        self.assertIn(typed, page)
        self.assertIn("partly", page)

    def test_a_report_must_be_about_a_written_question_with_an_answer(self):
        self.publish()
        for data in ({"qid": "p1", "reported": "had", "typed": "x"},       # multiple choice
                     {"qid": "p6", "reported": "great", "typed": "x"},     # not a choice
                     {"qid": "p6", "reported": "had", "typed": "  "}):     # nothing written
            self.assertEqual(self.student.post("/read/cincinnatus/report", data=data).status_code, 400)
        self.assertEqual(store.events_for_student(self.db, "403217"), [])

    def test_without_javascript_a_written_answer_still_works(self):
        self.publish()
        body = self.student.post("/read/cincinnatus", data={"only": "p6", "p6": "Come!"}).data.decode()
        self.assertIn("Compare yours with this answer:", body)
        self.assertIn('value="p6:had"', body)
        body = self.student.post("/read/cincinnatus", data={"report": "p6:had", "p6": "Come!"}).data.decode()
        self.assertIn("✓ You had it.", body)
        self.assertEqual(store.events_for_student(self.db, "403217")[-1]["result"], "right")

    def test_a_teacher_checking_records_nothing(self):
        r = self.teacher.post("/read/cincinnatus/check", data={"qid": "p1", "picked": "a"})
        self.assertEqual(r.get_json(), {"result": "right"})
        self.assertEqual(store.all_events(self.db), [])

    def test_unpublish(self):
        self.publish()
        self.teacher.post("/teacher/reader", data={"slug": "cincinnatus", "action": "withdraw"})
        self.assertEqual(self.student.get("/read/cincinnatus").status_code, 404)


if __name__ == "__main__":
    unittest.main()
