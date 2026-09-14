"""The correct answer must not always be the first thing on the screen.

Every choice item in the bank is written with its answer as option `a` -- that
is the authoring convention and it is a good one, because a reviewer reading
the YAML should see the answer without hunting. For a long time the templates
then rendered the options in exactly that order, which meant a student who
tapped the top option every time scored full marks on every multiple-choice
question in the course without reading any Latin, in practice and in a
proctored quiz alike.

Nothing caught it, because no individual question was wrong. These tests
encode the property that no single question can: what a student SEES.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dataio    # noqa: E402
import practice  # noqa: E402
import store     # noqa: E402

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

# Real ids, shaped the way make_ids.py issues them.
STUDENTS = ["403217", "418206", "905117", "271044", "660391"]


def choice_items():
    return [i for i in dataio.load_bank() if i.get("format") == "choice" and i.get("options")]


class TestDisplayOptions(unittest.TestCase):
    def setUp(self):
        self.opts = {"a": "the answer", "b": "wrong one", "c": "wrong two", "d": "wrong three"}
        self.seed = practice.option_seed("403217", "MS018-RECOG-01")

    def test_every_option_appears_exactly_once(self):
        shown = practice.display_options(self.opts, self.seed)
        self.assertEqual(sorted(k for _, k, _ in shown), sorted(self.opts))
        self.assertEqual(sorted(v for _, _, v in shown), sorted(self.opts.values()))

    def test_the_displayed_letters_run_in_order_down_the_page(self):
        shown = practice.display_options(self.opts, self.seed)
        self.assertEqual([d for d, _, _ in shown], ["a", "b", "c", "d"])

    def test_the_submit_key_still_matches_the_text_beside_it(self):
        for disp, key, text in practice.display_options(self.opts, self.seed):
            self.assertEqual(text, self.opts[key])

    def test_grading_is_untouched(self):
        # What the browser posts back is the item's own key, so the grader
        # never learns that anything moved.
        item = {"options": self.opts, "answer": "a"}
        for _, key, _ in practice.display_options(self.opts, self.seed):
            expected = "right" if key == "a" else "wrong"
            self.assertEqual(practice.grade_choice(item, key), expected)

    def test_the_same_student_sees_the_same_order_every_time(self):
        # A refresh must not reshuffle, and a quiz review days later must match
        # the paper they sat.
        first = practice.display_options(self.opts, self.seed)
        for _ in range(5):
            self.assertEqual(practice.display_options(self.opts, self.seed), first)

    def test_the_order_does_not_depend_on_which_option_is_correct(self):
        # The helper is never told the answer, so a future item whose answer is
        # not `a` shuffles exactly the same way.
        other = {"a": "the answer", "b": "wrong one", "c": "wrong two", "d": "wrong three"}
        self.assertEqual(practice.display_options(other, self.seed),
                         practice.display_options(self.opts, self.seed))

    def test_two_students_do_not_get_the_same_paper(self):
        items = choice_items()[:40]
        a = [practice.display_options(i["options"], practice.option_seed("403217", i["id"])) for i in items]
        b = [practice.display_options(i["options"], practice.option_seed("418206", i["id"])) for i in items]
        differ = sum(1 for x, y in zip(a, b) if x != y)
        self.assertGreater(differ, len(items) // 2,
                           "two students are seeing nearly the same option order")

    def test_one_student_gets_a_different_order_per_question(self):
        items = choice_items()[:40]
        orders = {tuple(k for _, k, _ in
                        practice.display_options(i["options"], practice.option_seed("403217", i["id"])))
                  for i in items}
        self.assertGreater(len(orders), 1,
                           "every question shuffles the same way, so position is still learnable")

    def test_missing_or_malformed_options_do_not_raise(self):
        self.assertEqual(practice.display_options(None, self.seed), [])
        self.assertEqual(practice.display_options({}, self.seed), [])
        self.assertEqual(practice.display_options(["a", "b"], self.seed), [])


class TestTappingTheTopOptionFails(unittest.TestCase):
    """The property the whole change exists for, measured on the real bank."""

    def test_always_picking_the_first_option_does_not_pass(self):
        items = choice_items()
        self.assertGreater(len(items), 100, "expected the real bank to be loaded")
        for sid in STUDENTS:
            first_is_right = 0
            for it in items:
                shown = practice.display_options(it["options"], practice.option_seed(sid, it["id"]))
                if shown[0][1] == it.get("answer"):
                    first_is_right += 1
            share = first_is_right / float(len(items))
            # Four options, so chance is about a quarter. The old behaviour was
            # 1.0 for every student; anything near that is the bug returning.
            self.assertLess(share, 0.45,
                            "student %s scores %.0f%% by tapping the top option" % (sid, share * 100))
            self.assertGreater(share, 0.05,
                               "student %s almost never sees the answer first, which is its own tell" % sid)

    def test_no_position_is_always_the_answer(self):
        items = choice_items()
        for sid in STUDENTS:
            for pos in range(4):
                hits = 0
                for it in items:
                    shown = practice.display_options(it["options"], practice.option_seed(sid, it["id"]))
                    if pos < len(shown) and shown[pos][1] == it.get("answer"):
                        hits += 1
                self.assertLess(hits / float(len(items)), 0.45,
                                "for %s, position %d is the answer too often" % (sid, pos + 1))


class TestStudentFacingTemplates(unittest.TestCase):
    """A regression here would be a new template, not a changed function."""

    STUDENT_FACING = ["practice_question.html", "quiz_take.html", "quiz_results.html"]

    def test_they_go_through_the_shuffle(self):
        for name in self.STUDENT_FACING:
            with open(os.path.join(TEMPLATES, name), encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("shown_options(", body, "%s renders options without the shuffle" % name)
            self.assertNotIn("options.items()", body,
                             "%s still iterates the options in file order" % name)

    def test_the_review_tool_still_shows_the_item_as_written(self):
        # Deliberately NOT shuffled: a teacher approving a question needs to see
        # it the way the YAML has it, answer first.
        with open(os.path.join(TEMPLATES, "review_item.html"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("options.items()", body)
        self.assertNotIn("shown_options(", body)


class TestThroughTheRunningApp(unittest.TestCase):
    def setUp(self):
        for k in ("LATIN_TEACHER_PASSWORD", "LATIN_PUBLIC"):
            os.environ.pop(k, None)
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.client = server.app.test_client()
        self.conn = store.connect(self.db_path)
        store.add_student(self.conn, "403217", "Block 3")

    def tearDown(self):
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def test_a_served_question_is_in_this_students_order(self):
        import checks
        spec = dataio.load_spec()
        items = dataio.load_bank()
        allowed = dataio.allowed_latin(dataio.load_exemplars())
        flags, _ = checks.run_all(items, set(spec), allowed)
        store.import_items(self.conn, items, flags, "test")
        # Approve only choice questions, so whatever selection serves first is
        # one. Selection is deterministic but which format comes up is not this
        # test's business.
        for it in items:
            if it.get("format") == "choice" and it.get("options"):
                store.set_review(self.conn, it["id"], "approved")

        self.client.post("/signin", data={"step": "id", "student_id": "403217", "next": "/practice"})
        self.client.post("/signin", data={"step": "pin", "student_id": "403217",
                                          "pin": "1234", "pin2": "1234", "next": "/practice"})
        r = self.client.get("/practice/session")
        self.assertEqual(r.status_code, 200)
        body = r.data.decode()

        served_id = body.split('name="item_id" value="')[1].split('"')[0]
        by_id = {i["id"]: i for i in items}
        item = by_id[served_id]
        self.assertEqual(item.get("format"), "choice",
                         "expected a choice question first; got %s (%s)"
                         % (item.get("format"), served_id))

        expected = [k for _, k, _ in
                    practice.display_options(item["options"], practice.option_seed("403217", item["id"]))]
        seen = [chunk.split('"')[0] for chunk in body.split('name="picked" value="')[1:]]
        self.assertEqual(seen, expected,
                         "the page did not use this student's option order")
        self.assertNotEqual(seen, sorted(item["options"]),
                            "the page served the options in file order, answer first")


if __name__ == "__main__":
    unittest.main()
