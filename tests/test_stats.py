"""Tests for the progress figures shown while a student works."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stats  # noqa: E402

DAY = 86400.0


def ev(item, result, ts, node=None):
    return {"item_id": item, "result": result, "timestamp": ts, "spec_node_id": node}


class TestSession(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(stats.session_stats([])["studied"], 0)

    def test_counts_this_sitting(self):
        t = 1_000_000.0
        evs = [ev("a", "right", t), ev("b", "wrong", t + 60), ev("c", "close", t + 120)]
        s = stats.session_stats(evs)
        self.assertEqual((s["studied"], s["right"], s["wrong"], s["close"]), (3, 1, 1, 1))

    def test_a_long_gap_starts_a_new_sitting(self):
        t = 1_000_000.0
        evs = [ev("a", "right", t), ev("b", "right", t + 60),          # yesterday
               ev("c", "right", t + 5 * DAY), ev("d", "wrong", t + 5 * DAY + 30)]
        s = stats.session_stats(evs)
        self.assertEqual(s["studied"], 2)      # only today's two
        self.assertEqual(s["right"], 1)

    def test_gap_boundary_is_inclusive_of_close_attempts(self):
        t = 1_000_000.0
        evs = [ev("a", "right", t), ev("b", "right", t + stats.SESSION_GAP - 1)]
        self.assertEqual(stats.session_stats(evs)["studied"], 2)

    def test_events_out_of_order_are_handled(self):
        t = 1_000_000.0
        evs = [ev("b", "right", t + 60), ev("a", "right", t)]
        self.assertEqual(stats.session_stats(evs)["studied"], 2)


class TestReadiness(unittest.TestCase):
    def test_never_attempted(self):
        self.assertEqual(stats.readiness_from([]), "not yet")

    def test_attempted_but_never_right(self):
        self.assertEqual(stats.readiness_from([ev("a", "wrong", 100)]), "not yet")

    def test_one_right_is_shaky(self):
        self.assertEqual(stats.readiness_from([ev("a", "right", 100)]), "shaky")

    def test_cramming_is_not_solid(self):
        t = time.time()
        evs = [ev("a", "right", t + i * 60) for i in range(5)]     # one sitting
        self.assertEqual(stats.readiness_from(evs, now=t + 3600), "shaky")

    def test_retention_is_solid(self):
        t = 1_000_000.0
        evs = [ev("a", "right", t), ev("a", "right", t + DAY + 5), ev("a", "right", t + 8 * DAY)]
        self.assertEqual(stats.readiness_from(evs, now=t + 8 * DAY), "solid")

    def test_matches_the_drill_rule(self):
        import drill
        t = 1_000_000.0
        evs = [ev("a", "right", t), ev("a", "right", t + DAY + 5), ev("a", "right", t + 8 * DAY)]
        self.assertEqual(stats.readiness_from(evs, now=t + 8 * DAY),
                         drill.readiness(evs, now=t + 8 * DAY))


class TestAllTime(unittest.TestCase):
    def test_untouched_items_count_as_not_yet(self):
        t = 1_000_000.0
        evs = [ev("x", "right", t, node="MS-001")]
        out = stats.alltime_by_node(evs, universe={"MS-001", "MS-002", "MS-003"})
        self.assertEqual(out["shaky"], 1)
        self.assertEqual(out["not yet"], 2)      # never attempted
        self.assertEqual(out["total"], 3)

    def test_drill_groups_both_directions_of_a_word(self):
        t = 1_000_000.0
        evs = [ev("vocab:aqua:la_en", "right", t),
               ev("vocab:aqua:en_la", "right", t + DAY + 5),
               ev("vocab:aqua:la_en", "right", t + 8 * DAY)]
        out = stats.alltime_by_word(evs, universe={"aqua", "via"})
        self.assertEqual(out["solid"], 1)        # one word, not two entries
        self.assertEqual(out["not yet"], 1)

    def test_non_vocab_events_are_ignored_by_word_tally(self):
        evs = [ev("MS014-RECOG-01", "right", 100, node="MS-014")]
        out = stats.alltime_by_word(evs, universe={"aqua"})
        self.assertEqual(out["not yet"], 1)
        self.assertEqual(out["solid"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
