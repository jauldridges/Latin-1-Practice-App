"""Tests for ID generation.

One property does the real work: no issued id is one typo away from another.
Without it, a mistyped digit can land on a classmate's number and a student
practises into someone else's record with nothing on screen to suggest
anything is wrong.
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import identity  # noqa: E402
import make_ids  # noqa: E402


class TestShape(unittest.TestCase):
    def setUp(self):
        self.ids = make_ids.generate(120, seed=1)

    def test_the_right_number(self):
        self.assertEqual(len(self.ids), 120)

    def test_all_unique(self):
        self.assertEqual(len(set(self.ids)), 120)

    def test_six_digits(self):
        for sid in self.ids:
            self.assertRegex(sid, r"^[0-9]{6}$")

    def test_never_a_leading_zero(self):
        # A spreadsheet will eat it, and 042173 would become a different student.
        for sid in self.ids:
            self.assertNotEqual(sid[0], "0", sid)

    def test_the_app_accepts_them(self):
        for sid in self.ids:
            self.assertTrue(identity.is_valid(sid), sid)

    def test_not_sequential(self):
        # Sequential ids let a student reach a classmate by adding one.
        ordered = sorted(int(s) for s in self.ids)
        gaps = [b - a for a, b in zip(ordered, ordered[1:])]
        self.assertGreater(min(gaps), 1)
        self.assertGreater(sum(gaps) / len(gaps), 1000)


class TestTypoDistance(unittest.TestCase):
    """The property the whole design exists for."""

    def test_no_id_is_one_wrong_digit_from_another(self):
        ids = make_ids.generate(150, seed=2)
        issued = set(ids)
        for sid in ids:
            for i, ch in enumerate(sid):
                for d in "0123456789":
                    if d == ch:
                        continue
                    typo = sid[:i] + d + sid[i + 1:]
                    self.assertNotIn(typo, issued,
                                     "%s -> %s is one digit away" % (sid, typo))

    def test_no_id_is_a_swap_away_from_another(self):
        ids = make_ids.generate(150, seed=3)
        issued = set(ids)
        for sid in ids:
            for i in range(len(sid) - 1):
                swapped = sid[:i] + sid[i + 1] + sid[i] + sid[i + 2:]
                if swapped != sid:
                    self.assertNotIn(swapped, issued,
                                     "%s -> %s is a swap away" % (sid, swapped))

    def test_the_neighbourhood_is_symmetric(self):
        # If a is one typo from b then b is one typo from a — which is why a
        # single blocked set is enough rather than checking both directions.
        a = "483920"
        for b in make_ids.typo_neighbours(a):
            self.assertIn(a, make_ids.typo_neighbours(b), b)

    def test_neighbours_never_include_a_leading_zero(self):
        for n in make_ids.typo_neighbours("183920"):
            self.assertNotEqual(n[0], "0")


class TestGeneratorItself(unittest.TestCase):
    def test_a_seed_makes_it_reproducible(self):
        self.assertEqual(make_ids.generate(30, seed=9), make_ids.generate(30, seed=9))

    def test_different_seeds_differ(self):
        self.assertNotEqual(make_ids.generate(30, seed=9), make_ids.generate(30, seed=10))

    def test_unseeded_runs_differ(self):
        self.assertNotEqual(make_ids.generate(30), make_ids.generate(30))

    def test_it_refuses_a_size_it_cannot_serve_well(self):
        with self.assertRaises(ValueError):
            make_ids.generate(50000)


if __name__ == "__main__":
    unittest.main()
