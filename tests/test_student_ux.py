"""What a student sees, checked from their side of the screen.

These came out of an audit done by driving the app as a student at phone and
Chromebook sizes. Two of the findings were bugs rather than looks, and they are
the reason this file exists.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import checks    # noqa: E402
import dataio    # noqa: E402
import practice  # noqa: E402
import store     # noqa: E402


class TestHintsDoNotGiveTheAnswerAway(unittest.TestCase):
    """The MS-014 hint said "Nauta puellam spectat -- nauta is nominative" on
    the question "In Nauta puellam spectat, which word is the subject?". The
    hint is taken BEFORE answering, so it may not repeat the question or print
    the answer. The explanation afterwards still shows everything."""

    def test_an_example_repeating_the_question_is_dropped(self):
        item = {"stem": "In Nauta puellam spectat, which word is the subject?",
                "format": "choice", "options": {"a": "Nauta", "b": "puellam"}, "answer": "a"}
        examples = ["Nauta puellam spectat — nauta is nominative.",
                    "First declension nominative singular ends in -a: puella, silva."]
        self.assertEqual(practice.hint_examples(examples, item), [examples[1]])

    def test_macrons_and_capitals_do_not_hide_a_repeat(self):
        item = {"stem": "In Femina aquam portat, which word is the object?", "format": "choice",
                "options": {"a": "aquam"}, "answer": "a"}
        self.assertEqual(practice.hint_examples(["Fēmina aquam portat — aquam is accusative."], item), [])

    def test_an_example_printing_the_answer_is_dropped(self):
        item = {"stem": "Which form of aqua is the object?", "format": "choice",
                "options": {"a": "aquam", "b": "aqua"}, "answer": "a"}
        self.assertEqual(practice.hint_examples(["puella → puellam; aqua → aquam."], item), [])

    def test_a_box_answer_counts_too(self):
        item = {"stem": "Write the accusative plural of island.", "format": "boxes",
                "boxes": [{"label": "x", "answer": ["insulas"]}]}
        self.assertEqual(practice.hint_examples(["insula → īnsulās"], item), [])

    def test_unrelated_examples_survive(self):
        item = {"stem": "Parse portam.", "format": "choice",
                "options": {"a": "accusative singular feminine"}, "answer": "a"}
        ex = ["Ending: stem + am.", "silva → silvam"]
        self.assertEqual(practice.hint_examples(ex, item), ex)

    def test_short_answers_do_not_wipe_out_everything(self):
        # A one- or two-letter answer ("a", "et") would match almost any example.
        item = {"stem": "Which ending?", "format": "boxes",
                "boxes": [{"label": "x", "answer": ["t"]}]}
        self.assertEqual(practice.hint_examples(["portat — he carries"], item),
                         ["portat — he carries"])


class _AsAStudent(unittest.TestCase):
    def setUp(self):
        os.environ.pop("LATIN_PUBLIC", None)
        os.environ["LATIN_TEACHER_PASSWORD"] = "teacherpw"
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.client = server.app.test_client()
        self.db = store.connect(self.db_path)
        self.items = dataio.load_bank()
        flags, _ = checks.run_all(self.items, set(dataio.load_spec()),
                                  dataio.allowed_latin(dataio.load_exemplars()))
        store.import_items(self.db, self.items, flags, "t")
        for it in self.items:
            if it.get("format") == "choice" and it.get("options"):
                store.set_review(self.db, it["id"], "approved")
        store.add_student(self.db, "403217", "Block 3")
        self.client.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.client.post("/signin", data={"step": "pin", "student_id": "403217",
                                          "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)


class TestFeedbackUsesTheLettersTheStudentSaw(_AsAStudent):
    """Options are shuffled per student, but the feedback printed the file's key.
    A student who saw the answer as "d" was told it was "a"."""

    def test_the_right_answer_carries_its_on_screen_letter(self):
        body = self.client.get("/practice/session?node=MS-014").data.decode()
        iid = body.split('name="item_id" value="')[1].split('"')[0]
        item = {i["id"]: i for i in self.items}[iid]
        shown = practice.display_options(item["options"], practice.option_seed("403217", iid))
        letter_of = {k: d for d, k, _ in shown}
        wrong = [k for k in item["options"] if k != item["answer"]][0]
        fb = self.client.post("/practice/answer", data={
            "item_id": iid, "picked": wrong, "node": "MS-014", "context": "practice"}).data.decode()
        self.assertIn('<span class="k">%s ✓</span>' % letter_of[item["answer"]], fb)
        self.assertIn('<span class="k">%s</span>' % letter_of[wrong], fb)
        if letter_of[item["answer"]] != item["answer"]:
            self.assertNotIn('<span class="k">%s ✓</span>' % item["answer"], fb)


class TestTheStudentScreens(_AsAStudent):
    def test_every_student_screen_has_the_three_tabs(self):
        for url in ("/", "/drill", "/practice", "/drill/progress"):
            body = self.client.get(url).data.decode()
            for tab in ("Vocabulary", "Grammar", "My progress"):
                self.assertIn(">%s</a>" % tab, body, "%s is missing the %s tab" % (url, tab))

    def test_the_header_shows_who_is_signed_in_and_a_way_out(self):
        body = self.client.get("/practice").data.decode()
        self.assertIn('class="sid">403217', body)
        self.assertIn("sign out", body)

    def test_no_spec_codes_on_a_question(self):
        # "MS-014" means nothing to a fourteen-year-old; the topic label stays.
        body = self.client.get("/practice/session?node=MS-014").data.decode()
        self.assertNotIn(">MS-014<", body)
        self.assertIn("Nominative case", body)

    def test_the_topic_list_has_no_codes_either(self):
        body = self.client.get("/practice").data.decode()
        self.assertNotIn(">MS-0", body)
        self.assertNotIn("MS-014 —", body)

    def test_no_teacher_language_on_the_practice_home(self):
        body = self.client.get("/practice").data.decode()
        self.assertNotIn("approved question(s) are waiting", body)
        self.assertNotIn("Open the review tool", body)

    def test_progress_folds_by_week_with_the_current_week_open(self):
        body = self.client.get("/drill/progress").data.decode()
        words, grammar = body.split('id="grammar"', 1)
        self.assertGreaterEqual(words.count('<details class="week"'), 6)
        self.assertEqual(words.count('<details class="week" open'), 1)
        self.assertLessEqual(grammar.count('<details class="week" open'), 1)
        self.assertNotIn("<th>Box</th>", body)


class TestGrammarOnTheProgressPage(_AsAStudent):
    """Grammar sits on the same page as the words, counted over the same topics
    the bar on every question counts."""

    def test_the_page_has_both_halves(self):
        body = self.client.get("/drill/progress").data.decode()
        self.assertIn('id="words"', body)
        self.assertIn('id="grammar"', body)
        self.assertIn("All topics so far", body)

    def test_every_topic_links_to_practice_on_just_that_topic(self):
        body = self.client.get("/drill/progress").data.decode().split('id="grammar"', 1)[1]
        self.assertIn("/practice/session?node=MS-014", body)
        self.assertIn("Nominative case", body)
        self.assertNotIn(">MS-014<", body)

    def test_it_agrees_with_the_bar_on_the_questions(self):
        import stats
        events = store.events_for_student(self.db, "403217")
        approved = store.approved_items(self.db)
        universe = {it["node"] for it in approved if it["node"] in self.server._taught_now()}
        groups = stats.grammar_progress(self.server._SPEC, universe, events)
        per_page = sum(g["total"] for g in groups)
        bar = stats.alltime_by_node(events, universe=universe)
        self.assertEqual(per_page, bar["total"])

    def test_a_right_answer_moves_a_topic_off_not_yet(self):
        import stats
        body = self.client.get("/practice/session?node=MS-014").data.decode()
        iid = body.split('name="item_id" value="')[1].split('"')[0]
        item = {i["id"]: i for i in self.items}[iid]
        self.client.post("/practice/answer", data={
            "item_id": iid, "picked": item["answer"], "node": "MS-014", "context": "practice"})
        events = store.events_for_student(self.db, "403217")
        rows = [r for g in stats.grammar_progress(self.server._SPEC, {"MS-014"}, events)
                for r in g["rows"]]
        self.assertEqual(rows[0]["state"], "shaky")   # right once is shaky, not solid


class TestTeacherScreensAreUntouched(_AsAStudent):
    def test_no_student_tabs_for_the_teacher(self):
        c = self.server.app.test_client()
        c.post("/login", data={"password": "teacherpw", "next": "/teacher"})
        body = c.get("/review").data.decode()
        self.assertNotIn('<nav class="tabs">', body)


if __name__ == "__main__":
    unittest.main()
