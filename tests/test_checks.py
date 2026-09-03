"""Tests for the mechanical checks.

The load-bearing test is that the four *error-level* checks raise ZERO flags on
the 75 known-good exemplars (the spec's own correctness bar). The two heuristic
checks (4 and 6a) are allowed a small, named set of explainable flags.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dataio          # noqa: E402
import checks          # noqa: E402


class TestAgainstExemplars(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = dataio.load_spec()
        cls.ex = dataio.load_exemplars()
        cls.items = cls.ex["items"]
        cls.allowed = dataio.allowed_latin(cls.ex)
        cls.flags, cls.report = checks.run_all(cls.items, set(cls.spec), cls.allowed)

    def test_no_error_level_flags_on_exemplars(self):
        errors = {iid: [f for f in fs if f.level == "error"]
                  for iid, fs in self.flags.items()}
        errors = {k: v for k, v in errors.items() if v}
        self.assertEqual(errors, {},
                         f"error-level checks fired on known-good exemplars: {errors}")

    def test_heuristic_flags_are_the_known_one(self):
        heur = sorted(iid for iid, fs in self.flags.items()
                      if any(f.level == "heuristic" for f in fs))
        # Only EX-RECOG-003 survives: macron_matters true with no macron
        # anywhere in the item. The check is right to notice it; the exemplar's
        # flag is decorative. Every error-level check is clean (tested above).
        self.assertEqual(heur, ["EX-RECOG-003"])

    def test_all_exemplar_nodes_exist(self):
        # a direct expression of check 5 over the exemplars
        for it in self.items:
            self.assertIn(it["node"], self.spec)


class TestSyntheticItems(unittest.TestCase):
    """Each error-level check fires on a deliberately broken item."""

    def setUp(self):
        self.nodes = {"MS-026", "MS-027", "MS-001"}
        self.allowed = {"bellum", "bella", "puella"}

    def test_duplicate_options(self):
        it = {"id": "x", "node": "MS-026", "assess": "parse",
              "options": {"a": "dōna", "b": "dōna", "c": "dōnum", "d": "dōnōs"},
              "answer": "a"}
        fs = checks.check_duplicate_options(it)
        self.assertTrue(any(f.check == "duplicate_options" for f in fs))

    def test_recall_with_options(self):
        it = {"id": "x", "node": "MS-001", "assess": "recall",
              "format": "choice", "options": {"a": "j", "b": "w"}, "answer": "a"}
        self.assertTrue(checks.check_recall_has_options(it))

    def test_node_missing(self):
        it = {"id": "x", "node": "MS-999", "assess": "parse",
              "what_went_wrong": [{"text": "t", "node": "ZZ-1"}]}
        fs = checks.check_nodes_exist(it, self.nodes)
        self.assertEqual(len(fs), 2)

    def test_box_too_long(self):
        it = {"id": "x", "node": "MS-001", "assess": "translate", "format": "boxes",
              "boxes": [{"label": "L", "answer": ["one two three four five"]}]}
        self.assertTrue(checks.check_box_length(it))

    def test_macron_only_distinction_flagged(self):
        # correct differs from a wrong option only by a macron, macron_matters unset
        it = {"id": "x", "node": "MS-001", "assess": "recognize", "format": "choice",
              "macron_matters": False,
              "options": {"a": "līber", "b": "liber"}, "answer": "a"}
        fs = checks.check_macron(it)
        self.assertTrue(any(f.check == "macron_flag" for f in fs))

    def test_duplicate_questions(self):
        items = [
            {"id": "a", "node": "MS-001", "stem": "Same stem here."},
            {"id": "b", "node": "MS-001", "stem": "same stem here"},
            {"id": "c", "node": "MS-001", "stem": "Different."},
        ]
        dupes = checks.find_duplicate_questions(items)
        self.assertIn("b", dupes)
        self.assertNotIn("a", dupes)
        self.assertNotIn("c", dupes)

    def test_vocabulary_flags_macron_word_off_list(self):
        it = {"id": "x", "node": "MS-001", "assess": "translate",
              "stem": "Translate rōsa into English."}   # rōsa: not in Unit 0-1
        fs = checks.check_vocabulary(it, self.allowed)
        self.assertTrue(any(f.check == "vocabulary" for f in fs))

    def test_vocabulary_allows_inflected_form(self):
        it = {"id": "x", "node": "MS-027", "assess": "parse",
              "stem": "Parse bella.", "options": {"a": "bella"}}
        fs = checks.check_vocabulary(it, self.allowed)
        self.assertEqual(fs, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestEndingsAreNotWords(unittest.TestCase):
    """From Unit 2 on, items discuss endings constantly. An ending written the
    way a grammar book writes it must not read as unknown vocabulary."""

    def item(self, stem):
        return {"id": "X-01", "node": "MS-054", "assess": "explain", "tier": 2,
                "format": "choice", "stem": stem,
                "options": {"a": "yes", "b": "no"}, "answer": "a"}

    def test_a_hyphenated_ending_is_exempt(self):
        flags = checks.check_vocabulary(self.item('The ending is "-ārum" here.'), set())
        self.assertEqual(flags, [])

    def test_the_same_letters_as_a_bare_word_still_flag(self):
        flags = checks.check_vocabulary(self.item('The word ārum appears.'), set())
        self.assertEqual(len(flags), 1)

    def test_an_ending_in_an_option_is_exempt_too(self):
        it = self.item("Which ending is the genitive plural?")
        it["options"] = {"a": "-ārum", "b": "-ōrum"}
        self.assertEqual(checks.check_vocabulary(it, set()), [])

    def test_a_real_unglossed_word_is_still_caught(self):
        flags = checks.check_vocabulary(self.item("The noun rēgīna is here."), set())
        self.assertEqual(len(flags), 1)
