"""Tests for grammar-practice selection and grading."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import practice  # noqa: E402


class TestTaughtNodes(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "MS-001": {"day": "2026-08-24"},
            "MS-014": {"day": "2026-09-09"},
            "RW-064": {"day": None, "week": "2026-10-05"},
            "XX-001": {},                       # neither: always available
        }

    def test_only_taught_by_date(self):
        got = practice.taught_nodes(self.spec, on_date="2026-08-30")
        self.assertIn("MS-001", got)
        self.assertNotIn("MS-014", got)         # taught Sep 9, not yet
        self.assertNotIn("RW-064", got)

    def test_module_node_uses_week(self):
        got = practice.taught_nodes(self.spec, on_date="2026-10-06")
        self.assertIn("RW-064", got)

    def test_undated_node_available(self):
        self.assertIn("XX-001", practice.taught_nodes(self.spec, on_date="2026-08-24"))


class TestChoice(unittest.TestCase):
    def test_right_and_wrong(self):
        item = {"options": {"a": "Nauta", "b": "puellam"}, "answer": "a"}
        self.assertEqual(practice.grade_choice(item, "a"), "right")
        self.assertEqual(practice.grade_choice(item, "b"), "wrong")


class TestBoxesOrdered(unittest.TestCase):
    def setUp(self):
        self.item = {
            "format": "boxes", "order_matters": True,
            "boxes": [
                {"label": "First", "answer": ["laudo"]},
                {"label": "Second", "answer": ["laudare"]},
            ],
        }

    def test_all_right(self):
        overall, res = practice.grade_boxes(self.item, ["laudō", "laudāre"])
        self.assertEqual(overall, "right")
        self.assertEqual([r.result for r in res], ["right", "right"])

    def test_partial_is_reported_per_box(self):
        overall, res = practice.grade_boxes(self.item, ["laudo", "wrongword"])
        self.assertEqual(overall, "wrong")
        self.assertEqual([r.result for r in res], ["right", "wrong"])

    def test_close_overall_when_only_typos(self):
        overall, res = practice.grade_boxes(self.item, ["laudo", "laudar"])
        self.assertEqual([r.result for r in res], ["right", "close"])
        self.assertEqual(overall, "close")


class TestBoxesUnordered(unittest.TestCase):
    """The three masculine first-declension nouns: order must not matter."""

    def setUp(self):
        self.item = {
            "format": "boxes", "order_matters": False,
            "boxes": [
                {"label": "Noun", "answer": ["nauta"]},
                {"label": "Noun", "answer": ["agricola"]},
                {"label": "Noun", "answer": ["poeta"]},
            ],
        }

    def test_any_order_all_right(self):
        overall, res = practice.grade_boxes(self.item, ["poeta", "nauta", "agricola"])
        self.assertEqual(overall, "right")
        self.assertTrue(all(r.result == "right" for r in res))

    def test_macrons_forgiven(self):
        overall, _ = practice.grade_boxes(self.item, ["poēta", "nauta", "agricola"])
        self.assertEqual(overall, "right")

    def test_two_of_three(self):
        overall, res = practice.grade_boxes(self.item, ["nauta", "agricola", "dominus"])
        self.assertEqual(overall, "wrong")
        self.assertEqual(sorted(r.result for r in res), ["right", "right", "wrong"])

    def test_exact_match_not_stolen_by_close(self):
        # "nauta" is exact for box 1. A response close to another box must not
        # consume box 1 first and push the exact answer to a wrong.
        overall, res = practice.grade_boxes(self.item, ["agricol", "nauta", "poeta"])
        results = sorted(r.result for r in res)
        self.assertEqual(results, ["close", "right", "right"])
        self.assertEqual(overall, "close")


class TestBoxesSpecialCases(unittest.TestCase):
    def test_answer_rule_box_is_self_checked(self):
        item = {"format": "boxes", "order_matters": True,
                "boxes": [
                    {"label": "Meaning", "answer": ["across"]},
                    {"label": "English word", "answer_rule": "any English word beginning with trans"},
                ]}
        overall, res = practice.grade_boxes(item, ["across", "transport"])
        self.assertEqual(res[1].result, "self")
        self.assertEqual(res[1].rule, "any English word beginning with trans")
        self.assertEqual(overall, "right")      # the rule box is left out

    def test_macron_matters_is_enforced(self):
        item = {"format": "boxes", "macron_matters": True, "order_matters": True,
                "boxes": [{"label": "Latin", "answer": ["rēgīna"]}]}
        overall, _ = practice.grade_boxes(item, ["regina"])
        self.assertEqual(overall, "wrong")

    def test_missing_response_is_wrong_not_crash(self):
        item = {"format": "boxes", "order_matters": True,
                "boxes": [{"label": "a", "answer": ["x"]}, {"label": "b", "answer": ["y"]}]}
        overall, res = practice.grade_boxes(item, ["x"])       # only one typed
        self.assertEqual(len(res), 2)
        self.assertEqual(overall, "wrong")


class TestTags(unittest.TestCase):
    def setUp(self):
        self.item = {"tag_boxes": [
            {"word": "Nauta", "case": ["nominative", "nom"], "job": ["subject"]},
            {"word": "puellam", "case": ["accusative", "acc"], "job": ["direct object", "object"]},
        ]}

    def test_all_right_with_abbreviations(self):
        overall, res = practice.grade_tags(self.item, ["nom", "acc"], ["subject", "object"])
        self.assertEqual(overall, "right")
        self.assertEqual(len(res), 2)

    def test_reversed_roles_caught(self):
        overall, res = practice.grade_tags(self.item, ["acc", "nom"], ["object", "subject"])
        self.assertEqual(overall, "wrong")
        self.assertEqual(res[0]["case_result"], "wrong")


class TestMenu(unittest.TestCase):
    def test_menu_has_item_reasons_plus_the_fixed_ones(self):
        item = {"what_went_wrong": [
            {"text": "I picked the first noun", "node": "MS-011"},
            {"text": "I picked the verb", "node": "MS-014"},
        ]}
        menu = practice.menu_for(item)
        self.assertEqual(len(menu), 4)
        self.assertEqual(menu[0]["node"], "MS-011")
        self.assertEqual([m["text"] for m in menu[-2:]],
                         ["I didn't know the word",
                          "I think my answer should be right"])

    def test_contest_key_is_last(self):
        menu = practice.menu_for({"what_went_wrong": []})
        self.assertEqual(menu[-1]["key"], practice.CONTEST_KEY)

    def test_empty_menu_still_offers_the_fixed_ones(self):
        self.assertEqual(len(practice.menu_for({})), 2)

    def test_i_dont_know_is_gone(self):
        """It was most of the answers, which is not a diagnosis.

        Every remaining choice is a claim about why you were wrong, so nothing
        here may read as "no idea" -- a student with no idea takes the quiet
        way past the menu instead, and is recorded as nothing.
        """
        item = {"what_went_wrong": [{"text": "I picked the verb", "node": "MS-014"}]}
        for m in practice.menu_for(item):
            self.assertNotEqual(m["key"], "dont_know")
            self.assertNotIn("don't know", m["text"].lower())

    def test_the_only_way_to_say_nothing_is_not_a_contest(self):
        # Removing the honest option must not push a stuck student onto the
        # contest path, which pulls a sound question out of circulation.
        keys = [m["key"] for m in practice.menu_for({})]
        self.assertEqual(keys, ["didnt_know_word", practice.CONTEST_KEY])


class TestThereIsAWayPastTheMenu(unittest.TestCase):
    """In practice the menu replaces the Next button, so it must not be a trap.

    In a quiz review it sits behind a fold and can simply be ignored, which is
    why only the practice screen needs this.
    """

    def test_the_practice_screen_offers_one(self):
        import os
        tpl = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "templates", "practice_feedback.html")
        with open(tpl, encoding="utf-8") as fh:
            body = fh.read()
        menu_block = body.split("{% elif menu %}")[1].split("{% else %}")[0]
        self.assertIn("practice_session", menu_block,
                      "the menu is mandatory with no way on: a student who "
                      "does not know must invent a reason or contest the item")
        self.assertIn("None of these", menu_block)

    def test_it_records_nothing(self):
        # A link, not a form: no reason_key, so no row in miss_reasons.
        import os
        tpl = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "templates", "practice_feedback.html")
        with open(tpl, encoding="utf-8") as fh:
            menu_block = fh.read().split("{% elif menu %}")[1].split("{% else %}")[0]
        after = menu_block.split("None of these")[0].rsplit("<a ", 1)[-1]
        self.assertNotIn("reason_key", after)


class TestSelection(unittest.TestCase):
    def setUp(self):
        self.items = [
            {"id": "A", "node": "MS-001"},
            {"id": "B", "node": "MS-001"},
            {"id": "C", "node": "MS-014"},
        ]

    def test_filters_to_taught_nodes(self):
        q = practice.select_question(self.items, [], allowed_nodes={"MS-014"})
        self.assertEqual(q["id"], "C")

    def test_unseen_before_seen(self):
        events = [{"item_id": "A", "result": "right", "timestamp": 100}]
        q = practice.select_question(self.items, events, allowed_nodes={"MS-001"})
        self.assertEqual(q["id"], "B")

    def test_none_when_nothing_available(self):
        self.assertIsNone(practice.select_question(self.items, [], allowed_nodes=set()))

    def test_node_filter(self):
        q = practice.select_question(self.items, [], node_id="MS-014")
        self.assertEqual(q["id"], "C")


if __name__ == "__main__":
    unittest.main(verbosity=2)
