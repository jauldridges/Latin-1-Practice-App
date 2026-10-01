"""Vocabulary hints: the word in an example sentence, never the answer."""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dataio      # noqa: E402
import store       # noqa: E402
import vocabhints  # noqa: E402
from answercheck import clean  # noqa: E402

WORDS = dataio.load_yaml(os.path.join(os.path.dirname(vocabhints.PATH), "vocab.yaml"))["words"]
EXAMPLES = vocabhints.load()


class TestTheSentences(unittest.TestCase):
    def test_every_drill_word_has_one(self):
        self.assertEqual({vocabhints.key(w["latin"]) for w in WORDS}, set(EXAMPLES))

    def test_every_one_marks_its_word_exactly_once(self):
        bad = {k: vocabhints.problems(e) for k, e in EXAMPLES.items() if vocabhints.problems(e)}
        self.assertEqual(bad, {})

    def test_latin_sentences_use_only_known_latin(self):
        allowed = dataio.allowed_latin(dataio.load_exemplars())
        unknown = set()
        for k, e in EXAMPLES.items():
            if not e["en"]:
                continue                       # an English sentence using a phrase
            for tok in re.findall(r"[A-Za-zāēīōūĀĒĪŌŪ]+", vocabhints.plain(e)):
                t = clean(tok)
                if t not in allowed and not (t.endswith("que") and t[:-3] in allowed):
                    unknown.add(tok)
        self.assertEqual(unknown, set())

    def test_a_blanked_sentence_does_not_show_the_word_elsewhere(self):
        # On an English -> Latin card the word is the answer.
        for k, e in EXAMPLES.items():
            rest = " ".join(t for t, marked in vocabhints.segments(e, blank=True) if not marked)
            stem = k[:4]
            self.assertFalse(any(clean(t).startswith(stem) for t in rest.split()
                                 if len(stem) >= 3), (k, rest))


class TestWhatACardShows(unittest.TestCase):
    def test_latin_to_english_bolds_the_word_and_hides_the_english(self):
        h = vocabhints.for_card(EXAMPLES["aqua"], "la_en")
        self.assertIn(("aquam", True), h["segments"])
        self.assertEqual(h["en"], "")

    def test_english_to_latin_blanks_the_word_and_gives_the_english(self):
        h = vocabhints.for_card(EXAMPLES["aqua"], "en_la")
        self.assertIn((vocabhints.BLANK, True), h["segments"])
        self.assertNotIn("aquam", " ".join(t for t, _ in h["segments"]))
        self.assertTrue(h["en"])

    def test_an_enclitic_blanks_only_itself(self):
        h = vocabhints.for_card(EXAMPLES[vocabhints.key("-que")], "en_la")
        self.assertEqual(h["segments"][0], ("Puer puella", False))


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

    def card(self, direction):
        body = self.student.get("/drill/session?direction=" + direction).data.decode()
        latin = body.split('name="latin" value="')[1].split('"')[0]
        return body, EXAMPLES[vocabhints.key(latin)]

    def test_nothing_shows_until_the_teacher_approves(self):
        body, _ = self.card("la_en")
        self.assertNotIn('class="vword"', body)

    def test_after_approving_all(self):
        self.teacher.post("/teacher/vocab-hints/approve-all")
        body, e = self.card("la_en")
        marked = [t for t, m in vocabhints.segments(e) if m][0]
        self.assertIn('<strong class="vword">%s</strong>' % marked, body)
        if e["en"]:
            self.assertNotIn(e["en"], body)            # the English is the answer here
        body, e = self.card("en_la")
        self.assertIn(vocabhints.BLANK, body)

    def test_the_answer_screen_shows_the_sentence_and_its_english(self):
        self.teacher.post("/teacher/vocab-hints/approve-all")
        self.student.post("/drill/answer", data={"direction": "la_en", "latin": "aqua",
                                                 "ask": "la_en", "response": "water",
                                                 "latency_ms": "800"})
        fb = self.student.post("/drill/answer", data={"direction": "la_en", "latin": "aqua",
                                                      "ask": "la_en", "response": "zzz",
                                                      "latency_ms": "800"}).data.decode()
        self.assertIn("In a sentence", fb)
        self.assertIn(EXAMPLES["aqua"]["en"], fb)

    def test_editing_saves_and_approves_and_a_bad_edit_is_refused(self):
        r = self.teacher.post("/teacher/vocab-hints/save", data={
            "word": "aqua", "action": "edit", "latin": "Aqua alta est.", "en": "The water is deep."})
        self.assertIn("error=", r.headers["Location"])
        self.teacher.post("/teacher/vocab-hints/save", data={
            "word": "aqua", "action": "edit", "latin": "*Aqua* alta est.", "en": "The water is deep."})
        self.assertEqual(self.server.vocab_hint_state(self.db, "aqua"), "approved")
        self.assertEqual(self.server.vocab_hint_entry(self.db, "aqua")["latin"], "*Aqua* alta est.")

    def test_a_reworded_sentence_needs_approving_again(self):
        self.teacher.post("/teacher/vocab-hints/save", data={"word": "aqua", "action": "approve"})
        self.assertEqual(self.server.vocab_hint_state(self.db, "aqua"), "approved")
        store.set_teaching_override(self.db, vocabhints.approval_key("aqua"),
                                    {"word": "aqua", "latin": "*Aqua* alta est.", "en": "x"})
        self.assertEqual(self.server.vocab_hint_state(self.db, "aqua"), "edited")

    def test_withdraw(self):
        self.teacher.post("/teacher/vocab-hints/save", data={"word": "aqua", "action": "approve"})
        self.teacher.post("/teacher/vocab-hints/save", data={"word": "aqua", "action": "withdraw"})
        self.assertEqual(self.server.vocab_hint_state(self.db, "aqua"), "draft")

    def test_the_teaching_text_page_is_unaffected(self):
        self.teacher.post("/teacher/vocab-hints/approve-all")
        self.assertNotIn("vocabhint:", self.teacher.get("/teaching").data.decode())

    def test_a_student_cannot_reach_the_teacher_page(self):
        r = self.student.get("/teacher/vocab-hints")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])


if __name__ == "__main__":
    unittest.main()
