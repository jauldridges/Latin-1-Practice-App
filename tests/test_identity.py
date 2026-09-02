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
        self.assertEqual(identity.normalize("  403-217 "), "403217")
        self.assertEqual(identity.normalize("403 217"), "403217")

    def test_leading_zeros_are_significant(self):
        # "04217" is somebody's actual ID and is not student 4217.
        self.assertEqual(identity.normalize("04217"), "04217")
        self.assertNotEqual(identity.normalize("04217"), identity.normalize("4217"))

    def test_empty(self):
        self.assertEqual(identity.normalize(None), "")
        self.assertEqual(identity.normalize("   "), "")


class TestValidity(unittest.TestCase):
    def test_a_six_digit_number_is_fine(self):
        self.assertTrue(identity.is_valid("403217"))
        self.assertTrue(identity.is_valid("999999"))

    def test_a_name_is_not_an_id(self):
        for bad in ("Sam", "Sam T.", "sam tucker", "", "   ", "sam217", "40321a"):
            self.assertFalse(identity.is_valid(bad), bad)

    def test_the_wrong_length_is_refused(self):
        # A dropped or doubled digit is caught here rather than becoming a
        # mystery "we don't have that number".
        self.assertFalse(identity.is_valid("40321"))
        self.assertFalse(identity.is_valid("4032177"))

    def test_a_leading_zero_is_refused(self):
        # No issued id has one, and a spreadsheet would eat it anyway.
        self.assertFalse(identity.is_valid("040321"))

    def test_the_pattern_is_configurable(self):
        old = os.environ.get("LATIN_ID_PATTERN")
        os.environ["LATIN_ID_PATTERN"] = r"^S[0-9]{3}$"
        try:
            self.assertTrue(identity.is_valid("S123"))
            self.assertFalse(identity.is_valid("403217"))
        finally:
            if old is None:
                os.environ.pop("LATIN_ID_PATTERN", None)
            else:
                os.environ["LATIN_ID_PATTERN"] = old


class TestDescribe(unittest.TestCase):
    def test_reads_as_a_sentence(self):
        self.assertEqual(identity.describe_pattern(), "a 6-digit number")


if __name__ == "__main__":
    unittest.main()
