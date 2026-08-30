"""Tests for the shared answer-checking module.

Covers the cases named in the build spec, plus the edges most likely to bite:
short-answer closeness, the leading-article rule, and the macron_matters
exception in both directions.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from answercheck import check, clean  # noqa: E402


class TestRequiredCases(unittest.TestCase):
    """The exact cases the spec names."""

    def test_capitalization(self):
        self.assertEqual(check("Puella", ["puella"]), "right")

    def test_leading_dash(self):
        self.assertEqual(check("-mus", ["mus"]), "right")
        self.assertEqual(check("mus", ["-mus"]), "right")

    def test_macron_stripped_by_default(self):
        self.assertEqual(check("laudamus", ["laudāmus"]), "right")
        self.assertEqual(check("laudāmus", ["laudamus"]), "right")

    def test_close_not_wrong(self):
        self.assertEqual(check("puela", ["puella"]), "close")

    def test_macron_matters_rejects_missing_macron(self):
        self.assertEqual(check("regina", ["rēgīna"], macron_matters=True), "wrong")

    def test_leading_the(self):
        self.assertEqual(check("the farmer", ["farmer"]), "right")
        self.assertEqual(check("farmer", ["the farmer"]), "right")


class TestCleaning(unittest.TestCase):
    def test_clean_lowercases(self):
        self.assertEqual(clean("PUELLA"), "puella")

    def test_clean_strips_punctuation(self):
        self.assertEqual(clean("i.e."), "ie")
        self.assertEqual(clean("puella!"), "puella")

    def test_clean_collapses_spaces(self):
        self.assertEqual(clean("out of   many,  one"), "out of many one")

    def test_clean_leading_a(self):
        self.assertEqual(clean("a gift"), "gift")

    def test_clean_leading_the(self):
        self.assertEqual(clean("The Sailor"), "sailor")

    def test_clean_leading_dash(self):
        self.assertEqual(clean("-tis"), "tis")

    def test_clean_macron_default(self):
        self.assertEqual(clean("rēgīna"), "regina")

    def test_clean_macron_kept_when_matters(self):
        self.assertEqual(clean("rēgīna", macron_matters=True), "rēgīna")

    def test_clean_combining_macron(self):
        # a + combining macron (U+0304) should also normalise to plain a.
        self.assertEqual(clean("āra"), "ara")


class TestResults(unittest.TestCase):
    def test_exact_among_many(self):
        self.assertEqual(check("nauta", ["nauta", "sailor"]), "right")

    def test_multiple_accepted_english(self):
        self.assertEqual(check("watch", ["look at", "watch", "look"]), "right")

    def test_wrong_is_wrong(self):
        self.assertEqual(check("dominus", ["puella"]), "wrong")

    def test_close_distance_two(self):
        # two edits away -> close
        self.assertEqual(check("laudms", ["laudamus"]), "close")  # missing a, u? distance 2

    def test_far_is_wrong(self):
        self.assertEqual(check("xyz", ["laudamus"]), "wrong")

    def test_empty_is_wrong_not_close(self):
        self.assertEqual(check("", ["o"]), "wrong")
        self.assertEqual(check("   ", ["est"]), "wrong")

    def test_macron_matters_accepts_correct_macron(self):
        self.assertEqual(check("rēgīna", ["rēgīna"], macron_matters=True), "right")

    def test_macron_matters_still_strips_case_and_punct(self):
        self.assertEqual(check("Rēgīna!", ["rēgīna"], macron_matters=True), "right")

    def test_short_answers_demand_exactness(self):
        # CLOSE is length-scaled. On a short answer a one-edit difference is a
        # different answer, not a slip: "q" is not a typo of "w", and es/est is
        # a real form confusion the what-went-wrong menu exists to count.
        self.assertEqual(check("es", ["est"]), "wrong")     # 3 chars: exact only
        self.assertEqual(check("q", ["w"]), "wrong")        # 1 char: exact only
        self.assertEqual(check("nt", ["mus"]), "wrong")

    def test_typos_on_real_words_are_still_close(self):
        self.assertEqual(check("puela", ["puella"]), "close")      # 6 chars, 1 edit
        self.assertEqual(check("agricol", ["agricola"]), "close")  # 8 chars, 1 edit
        self.assertEqual(check("laudms", ["laudamus"]), "close")   # 8 chars, 2 edits

    def test_string_accepted_arg(self):
        # accepted may be a bare string, not only a list.
        self.assertEqual(check("puella", "puella"), "right")


if __name__ == "__main__":
    unittest.main(verbosity=2)
