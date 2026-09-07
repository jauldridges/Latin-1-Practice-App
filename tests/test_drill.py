"""Tests for the drill's box schedule and the solid/shaky/not-yet logic."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import drill  # noqa: E402

DAY = 86400.0


def ev(latin, ask, result, ts):
    return {"item_id": f"vocab:{latin}:{ask}", "result": result, "timestamp": ts}


class TestBox(unittest.TestCase):
    def test_new_word_box1_due_now(self):
        box, due = drill.box_and_due([])
        self.assertEqual(box, 1)
        self.assertEqual(due, 0.0)

    def test_right_moves_up(self):
        t = 1000.0
        evs = [ev("aqua", "la_en", "right", t), ev("aqua", "la_en", "right", t + 10)]
        box, due = drill.box_and_due(evs)
        self.assertEqual(box, 3)
        self.assertEqual(due, (t + 10) + drill._INTERVALS[3])

    def test_wrong_resets_to_box1(self):
        t = 1000.0
        evs = [ev("aqua", "la_en", "right", t), ev("aqua", "la_en", "wrong", t + 10)]
        box, _ = drill.box_and_due(evs)
        self.assertEqual(box, 1)

    def test_close_does_not_change_box(self):
        t = 1000.0
        evs = [ev("aqua", "la_en", "right", t), ev("aqua", "la_en", "close", t + 10)]
        box, _ = drill.box_and_due(evs)
        self.assertEqual(box, 2)

    def test_box_caps_at_5(self):
        evs = [ev("aqua", "la_en", "right", 100 + i) for i in range(9)]
        box, _ = drill.box_and_due(evs)
        self.assertEqual(box, 5)


class TestReadiness(unittest.TestCase):
    def test_no_events_not_yet(self):
        self.assertEqual(drill.readiness([]), "not yet")

    def test_attempts_but_no_right_not_yet(self):
        evs = [ev("aqua", "la_en", "wrong", 100), ev("aqua", "la_en", "close", 200)]
        self.assertEqual(drill.readiness(evs), "not yet")

    def test_one_right_is_shaky(self):
        evs = [ev("aqua", "la_en", "right", 100)]
        self.assertEqual(drill.readiness(evs), "shaky")

    def test_many_rights_same_day_not_solid(self):
        # three rights, but all within one sitting and no delayed success
        base = time.time()
        evs = [ev("aqua", "la_en", "right", base + i * 60) for i in range(3)]
        self.assertEqual(drill.readiness(evs, now=base + 3600), "shaky")

    def test_solid_requires_delayed_success(self):
        first = 1_000_000.0
        evs = [
            ev("aqua", "la_en", "right", first),                 # day 0
            ev("aqua", "la_en", "right", first + 1 * DAY + 5),   # day 1 (2nd sitting)
            ev("aqua", "la_en", "right", first + 8 * DAY),       # >1 week after first
        ]
        self.assertEqual(drill.readiness(evs, now=first + 8 * DAY + 10), "solid")

    def test_delayed_but_only_one_sitting_not_solid(self):
        first = 1_000_000.0
        # rights far apart in time but landing on effectively one calendar span
        evs = [ev("aqua", "la_en", "right", first),
               ev("aqua", "la_en", "right", first + 60)]
        self.assertEqual(drill.readiness(evs, now=first + 10 * DAY), "shaky")


class TestScopeAndAccept(unittest.TestCase):
    def setUp(self):
        self.words = [
            {"latin": "aqua", "en": ["water"], "week": "week_of_aug_31"},
            {"latin": "sum", "en": ["I am", "am"], "week": "week_of_sep_21"},
        ]

    def test_accepted_directions(self):
        w = self.words[0]
        self.assertEqual(drill.accepted_for(w, "la_en"), ["water"])
        self.assertEqual(drill.accepted_for(w, "en_la"), ["aqua"])

    def test_find_word_macron_insensitive(self):
        words = [{"latin": "rēgīna", "en": ["queen"], "week": "week_of_sep_21"}]
        self.assertIsNotNone(drill.find_word(words, "regina"))

    def test_next_card_prefers_new_word(self):
        card = drill.next_card(self.words, [], week="all")
        self.assertIsNotNone(card)
        self.assertIn(card.ask, ("la_en", "en_la"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestProgressByWeek(unittest.TestCase):
    """The progress table grouped by the week each word was introduced."""

    def rows(self):
        words = [{"latin": "aqua", "en": ["water"], "week": "week_of_aug_24"},
                 {"latin": "via", "en": ["road"], "week": "week_of_aug_24"},
                 {"latin": "puer", "en": ["boy"], "week": "week_of_sep_14"}]
        return drill.progress_table(words, [])

    def test_one_group_per_week(self):
        groups = drill.by_week(self.rows())
        self.assertEqual([g["week"] for g in groups],
                         ["week_of_aug_24", "week_of_sep_14"])

    def test_groups_run_in_teaching_order_not_alphabetical(self):
        # "week_of_aug_31" sorts before "week_of_sep_8" alphabetically and also
        # comes first in teaching; "week_of_sep_8" vs "week_of_sep_14" does not.
        words = [{"latin": "a", "en": ["a"], "week": "week_of_sep_14"},
                 {"latin": "b", "en": ["b"], "week": "week_of_sep_8"}]
        groups = drill.by_week(drill.progress_table(words, []))
        self.assertEqual([g["week"] for g in groups],
                         ["week_of_sep_8", "week_of_sep_14"])

    def test_each_group_counts_its_own_states(self):
        groups = drill.by_week(self.rows())
        self.assertEqual(groups[0]["total"], 2)
        self.assertEqual(groups[0]["counts"]["not yet"], 2)

    def test_groups_carry_a_human_label(self):
        self.assertEqual(drill.by_week(self.rows())[0]["label"], "Week of Aug 24")

    def test_an_unknown_week_still_gets_a_group(self):
        # A word must never vanish from a student's progress because its week
        # is not one the app knows about.
        words = [{"latin": "x", "en": ["x"], "week": "week_of_never"}]
        groups = drill.by_week(drill.progress_table(words, []))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["label"], "week_of_never")

    def test_every_word_appears_exactly_once_across_the_groups(self):
        import dataio
        rows = drill.progress_table(dataio.load_drill_words(), [])
        grouped = [r for g in drill.by_week(rows) for r in g["rows"]]
        self.assertEqual(len(grouped), len(rows))
        self.assertEqual({r.latin for r in grouped}, {r.latin for r in rows})

    def test_the_summary_carries_it(self):
        self.assertIn("by_week", drill.progress_summary(self.rows()))
