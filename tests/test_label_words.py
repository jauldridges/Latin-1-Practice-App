"""Label the words: tap a label from the bank, tap the box above its word."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import checks    # noqa: E402
import dataio    # noqa: E402
import practice  # noqa: E402
import quiz      # noqa: E402
import store     # noqa: E402

BANK = ["nominative · subject", "accusative · direct object", "vocative · direct address", "verb"]


def item(**kw):
    it = {"id": "T-LABEL-01", "node": "MS-015", "format": "label-words", "assess": "parse",
          "tier": 1, "stem": "Label each word.",
          "sentence": [{"latin": "Fēmina", "answer": "nominative · subject"},
                       {"latin": "et"},
                       {"latin": "aquam", "answer": ["accusative · direct object"]},
                       {"latin": "portat.", "answer": "verb"}],
          "bank": list(BANK)}
    it.update(kw)
    return it


class TestGrading(unittest.TestCase):
    def test_all_right(self):
        res, rows = practice.grade_labels(item(), ["nominative · subject",
                                                   "accusative · direct object", "verb"])
        self.assertEqual(res, "right")
        self.assertEqual([r["word"] for r in rows], ["Fēmina", "aquam", "portat."])

    def test_one_wrong_box_is_wrong_and_says_which(self):
        res, rows = practice.grade_labels(item(), ["accusative · direct object",
                                                   "accusative · direct object", "verb"])
        self.assertEqual(res, "wrong")
        self.assertEqual([r["result"] for r in rows], ["wrong", "right", "right"])

    def test_an_empty_box_is_wrong_not_an_error(self):
        res, rows = practice.grade_labels(item(), ["nominative · subject"])
        self.assertEqual(res, "wrong")
        self.assertEqual(rows[2]["picked"], "")

    def test_a_word_without_an_answer_gets_no_box(self):
        self.assertEqual(len(practice.label_targets(item())), 3)

    def test_what_is_stored(self):
        _, rows = practice.grade_labels(item(), ["nominative · subject", "", "verb"])
        self.assertEqual(practice.label_summary(rows),
                         "Fēmina=nominative · subject | aquam=(blank) | portat.=verb")


class TestTheRulesForABank(unittest.TestCase):
    def test_a_good_item_has_no_problems(self):
        self.assertEqual(practice.label_problems(item()), [])

    def test_the_answer_must_be_in_the_bank(self):
        bad = item(bank=["nominative · subject", "verb", "vocative · direct address"])
        self.assertTrue(any("not in the bank" in p for p in practice.label_problems(bad)))

    def test_there_must_be_a_label_that_is_not_an_answer(self):
        # Otherwise the last box can be filled by elimination.
        bad = item(bank=["nominative · subject", "accusative · direct object", "verb"])
        self.assertTrue(any("elimination" in p for p in practice.label_problems(bad)))

    def test_one_box_is_not_a_labelling_question(self):
        bad = item(sentence=[{"latin": "Fēmina", "answer": "nominative · subject"}, {"latin": "est"}])
        self.assertTrue(any("two words" in p for p in practice.label_problems(bad)))

    def test_the_import_checks_flag_it(self):
        bad = item(bank=["nominative · subject", "accusative · direct object", "verb"])
        flags = checks.check_label_words(bad)
        self.assertTrue(flags and flags[0].check == "label_words" and flags[0].level == "error")

    def test_every_label_question_in_the_bank_passes_every_check(self):
        items = dataio.load_bank()
        flags, _ = checks.run_all(items, set(dataio.load_spec()),
                                  dataio.allowed_latin(dataio.load_exemplars()))
        lw = [i["id"] for i in items if i.get("format") == "label-words"]
        self.assertGreaterEqual(len(lw), 18)
        self.assertEqual({i: flags[i] for i in lw if i in flags}, {})

    def test_verbs_are_just_verb(self):
        # The teacher's rule: "verb", unless the question is about the verb's form.
        for it in dataio.load_bank():
            if it.get("format") == "label-words":
                for b in it["bank"]:
                    self.assertFalse(b.startswith("verb ·"), (it["id"], b))

    def test_a_rewrite_is_not_a_duplicate_of_what_it_replaces(self):
        old = {"id": "OLD", "node": "MS-015", "stem": "Label each word. Fēmina et aquam portat."}
        new = item(id="NEW", replaces="OLD")
        self.assertEqual(checks.find_duplicate_questions([old, new]), {})


class TestHintsDontGiveItAway(unittest.TestCase):
    def test_an_example_using_the_same_sentence_is_held_back(self):
        kept = practice.hint_examples(["Fēmina et aquam portat — aquam is accusative.",
                                       "Puella rosam amat."], item())
        self.assertEqual(kept, ["Puella rosam amat."])


class TestQuizGrading(unittest.TestCase):
    def test_a_quiz_grades_it_the_same_way(self):
        it = item()
        out = quiz.grade_attempt({it["id"]: it}, [it["id"]],
                                 {it["id"]: {"pick": ["nominative · subject",
                                                      "accusative · direct object", "verb"],
                                             "typed": "The woman carries water."}})
        self.assertEqual(out[it["id"]]["result"], "right")
        self.assertTrue(quiz.answer_is_blank("label-words", {"pick": ["", ""], "typed": ""}))


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

    def approve(self, *ids):
        for i in ids:
            store.set_review(self.db, i, "approved")

    def served(self):
        return {p["id"] for p in store.approved_items(self.db)}


class TestReplacing(_App):
    def test_the_old_question_is_served_until_the_new_one_is_approved(self):
        self.approve("MS015-TRANS-01")
        self.assertIn("MS015-TRANS-01", self.served())
        self.approve("MS015-LABEL-01")
        self.assertIn("MS015-LABEL-01", self.served())
        self.assertNotIn("MS015-TRANS-01", self.served())

    def test_the_review_tool_shows_the_sentence_and_what_it_replaces(self):
        body = self.teacher.get("/review/item/MS015-LABEL-01").data.decode()
        self.assertIn("replaces", body)
        self.assertIn("MS015-TRANS-01", body)
        self.assertIn("lw-slot", body)
        self.assertIn("vocative", body)


class TestPracticingIt(_App):
    def setUp(self):
        _App.setUp(self)
        self.approve("MS015-LABEL-01")

    def ask(self):
        return self.student.get("/practice/session?node=MS-015,").data.decode()

    def answer(self, picks):
        return self.student.post("/practice/answer", data={
            "item_id": "MS015-LABEL-01", "node": "MS-015,", "context": "practice",
            "pick": picks, "typed": "The woman carries the water."}).data.decode()

    def test_the_question_shows_boxes_and_the_bank(self):
        body = self.ask()
        self.assertIn('name="item_id" value="MS015-LABEL-01"', body)
        self.assertEqual(body.count('class="lw-slot'), 3)
        self.assertEqual(body.count('class="lw-chip"'), 5)
        self.assertIn("labelwords.js", body)

    def test_a_right_answer(self):
        body = self.answer(["nominative · subject", "accusative · direct object", "verb"])
        self.assertIn("Right!", body)
        self.assertIn("The woman carries the water.", body)
        ev = store.events_for_student(self.db, "403217")[-1]
        self.assertEqual((ev["item_id"], ev["result"]), ("MS015-LABEL-01", "right"))
        self.assertIn("aquam=accusative · direct object", ev["response"])

    def test_a_wrong_answer_shows_the_fix_and_the_menu(self):
        body = self.answer(["accusative · direct object", "nominative · subject", "verb"])
        self.assertIn("Not quite.", body)
        self.assertIn("✓ nominative · subject", body)
        self.assertIn("What happened?", body)
        self.assertEqual(store.events_for_student(self.db, "403217")[-1]["result"], "wrong")


if __name__ == "__main__":
    unittest.main()
