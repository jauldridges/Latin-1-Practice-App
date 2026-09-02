"""Tests for student identity.

Identity is a number and only a number. These hold the two things that make
that safe: what counts as well-formed, and the fact that normalising a typed
number never changes which student it is.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import identity  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_trims_and_strips_separators(self):
        self.assertEqual(identity.normalize("  40-217 "), "40217")
        self.assertEqual(identity.normalize("40 217"), "40217")

    def test_leading_zeros_are_significant(self):
        # "04217" is somebody's actual ID and is not student 4217.
        self.assertEqual(identity.normalize("04217"), "04217")
        self.assertNotEqual(identity.normalize("04217"), identity.normalize("4217"))

    def test_empty(self):
        self.assertEqual(identity.normalize(None), "")
        self.assertEqual(identity.normalize("   "), "")


class TestValidity(unittest.TestCase):
    def test_a_plain_number_is_fine(self):
        self.assertTrue(identity.is_valid("40217"))
        self.assertTrue(identity.is_valid("0421"))

    def test_a_name_is_not_an_id(self):
        for bad in ("Sam", "Sam T.", "sam tucker", "", "   ", "sam217"):
            self.assertFalse(identity.is_valid(bad), bad)

    def test_too_short_and_too_long(self):
        self.assertFalse(identity.is_valid("123"))
        self.assertFalse(identity.is_valid("12345678901"))

    def test_the_pattern_is_configurable(self):
        old = os.environ.get("LATIN_ID_PATTERN")
        os.environ["LATIN_ID_PATTERN"] = r"^S[0-9]{3}$"
        try:
            self.assertTrue(identity.is_valid("S123"))
            self.assertFalse(identity.is_valid("40217"))
        finally:
            if old is None:
                os.environ.pop("LATIN_ID_PATTERN", None)
            else:
                os.environ["LATIN_ID_PATTERN"] = old


class TestDescribe(unittest.TestCase):
    def test_reads_as_a_sentence(self):
        self.assertEqual(identity.describe_pattern(), "a number, 4 to 10 digits")


if __name__ == "__main__":
    unittest.main()
