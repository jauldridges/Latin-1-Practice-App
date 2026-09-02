"""Tests for the teacher dashboard's aggregation.

The load-bearing claim is the one about denominators: a student who did
nothing must appear in the table. Most of these tests exist to hold that.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import teacher  # noqa: E402

DAY = 86400.0
T = time.mktime((2026, 3, 10, 12, 0, 0, 0, 0, -1))   # a fixed Tuesday noon


def ev(student, item, result, ts, node=None):
    return {"student_id": student, "item_id": item, "result": result,
            "timestamp": ts, "spec_node_id": node}


def person(sid, section="Block 3"):
    # No name field: this system holds ID numbers only. See identity.py.
    return {"student_id": sid, "section": section}


class TestKind(unittest.TestCase):
    def test_vocab_ids_are_vocab(self):
        self.assertEqual(teacher.kind_of(ev("s", "vocab:puella:la_en", "right", T)), "vocab")

    def test_bank_ids_are_grammar(self):
        self.assertEqual(teacher.kind_of(ev("s", "RW008-RECALL-01", "right", T)), "grammar")


class TestAccuracy(unittest.TestCase):
    def test_close_counts_as_right(self):
        evs = [ev("s", "a", "right", T), ev("s", "b", "close", T), ev("s", "c", "wrong", T)]
        self.assertAlmostEqual(teacher.accuracy(evs), 2 / 3.0)

    def test_no_attempts_is_none_not_zero(self):
        # Zero would sort a student who has done nothing next to a student who
        # got everything wrong. They are not the same student.
        self.assertIsNone(teacher.accuracy([]))


class TestWindow(unittest.TestCase):
    def test_window_starts_at_midnight(self):
        since, until = teacher.window_bounds(days=1, now=T)
        self.assertLessEqual(since, T)
        self.assertEqual(time.strftime("%H:%M", time.localtime(since)), "00:00")

    def test_seven_days_includes_today(self):
        since, _ = teacher.window_bounds(days=7, now=T)
        self.assertAlmostEqual((T - since) / DAY, 0.5 + 6, places=1)

    def test_filters(self):
        evs = [ev("s", "a", "right", T - 30 * DAY), ev("s", "b", "right", T - DAY)]
        since, until = teacher.window_bounds(days=7, now=T)
        self.assertEqual(len(teacher.in_window(evs, since, until)), 1)


class TestActivity(unittest.TestCase):
    def test_counts_days_not_just_attempts(self):
        evs = [ev("s", "a", "right", T - DAY), ev("s", "b", "right", T - DAY + 60),
               ev("s", "c", "right", T)]
        act = teacher.activity(evs)
        self.assertEqual(act["attempts"], 3)
        self.assertEqual(act["days"], 2)

    def test_splits_vocab_from_grammar(self):
        evs = [ev("s", "vocab:puella:la_en", "right", T), ev("s", "RW008-01", "wrong", T)]
        act = teacher.activity(evs)
        self.assertEqual((act["vocab"], act["grammar"]), (1, 1))

    def test_ever_survives_the_window(self):
        # Windowing the table must not erase the fact that they used to work.
        evs = [ev("s", "a", "right", T - 60 * DAY)]
        since, until = teacher.window_bounds(days=7, now=T)
        act = teacher.activity(evs, since, until)
        self.assertEqual(act["attempts"], 0)
        self.assertEqual(act["ever_attempts"], 1)
        self.assertIsNotNone(act["ever_last_at"])


class TestHomeworkState(unittest.TestCase):
    def test_three_states(self):
        self.assertEqual(teacher.homework_state({"attempts": 0}), "none")
        self.assertEqual(teacher.homework_state({"attempts": 1}), "started")
        self.assertEqual(teacher.homework_state({"attempts": 25}), "done")

    def test_threshold_is_adjustable(self):
        self.assertEqual(teacher.homework_state({"attempts": 10}, done=10), "done")


class TestClassActivity(unittest.TestCase):
    def setUp(self):
        self.roster = [person("403217"), person("418206"), person("426913")]
        self.events = ([ev("403217", "vocab:puella:la_en", "right", T - i * 600)
                        for i in range(25)]
                       + [ev("418206", "vocab:aqua:la_en", "wrong", T - 3600)])

    def test_a_student_who_did_nothing_still_has_a_row(self):
        out = teacher.class_activity(self.roster, self.events)
        ids = {r["student_id"] for r in out["rows"]}
        self.assertIn("426913", ids)
        self.assertEqual(out["n_students"], 3)

    def test_states_are_counted(self):
        out = teacher.class_activity(self.roster, self.events)
        self.assertEqual((out["n_done"], out["n_started"], out["n_none"]), (1, 1, 1))

    def test_least_practice_sorts_first(self):
        out = teacher.class_activity(self.roster, self.events)
        self.assertEqual(out["rows"][0]["student_id"], "426913")
        self.assertEqual(out["rows"][-1]["student_id"], "403217")

    def test_an_off_roster_id_is_surfaced_not_dropped(self):
        # A mistyped digit looks perfectly well-formed, so this list is the
        # only place the typo becomes visible.
        evs = self.events + [ev("479518", "vocab:puella:la_en", "right", T)]
        out = teacher.class_activity(self.roster, evs)
        self.assertEqual(out["unrostered"], ["479518"])

    def test_window_is_applied(self):
        old = [ev("426913", "vocab:via:la_en", "right", T - 40 * DAY)]
        since, until = teacher.window_bounds(days=7, now=T)
        out = teacher.class_activity(self.roster, self.events + old, since, until)
        idle = [r for r in out["rows"] if r["student_id"] == "426913"][0]
        self.assertEqual(idle["state"], "none")


class TestDifficulty(unittest.TestCase):
    def test_weakest_first(self):
        evs = ([ev("a", "Q1", "wrong", T, node="N1") for _ in range(6)]
               + [ev("a", "Q2", "right", T, node="N2") for _ in range(6)])
        rows = teacher.difficulty(evs, teacher.node_key)
        self.assertEqual(rows[0]["key"], "N1")
        self.assertEqual(rows[0]["accuracy"], 0.0)

    def test_thin_rows_are_flagged_not_hidden(self):
        evs = [ev("a", "Q1", "wrong", T, node="N1")]
        rows = teacher.difficulty(evs, teacher.node_key, min_attempts=5)
        self.assertTrue(rows[0]["thin"])

    def test_untouched_universe_members_appear_last(self):
        evs = [ev("a", "Q1", "wrong", T, node="N1")]
        rows = teacher.difficulty(evs, teacher.node_key, universe={"N1", "N9"})
        self.assertEqual(rows[-1]["key"], "N9")
        self.assertIsNone(rows[-1]["accuracy"])

    def test_counts_distinct_students(self):
        evs = [ev("a", "Q1", "wrong", T, node="N1"), ev("b", "Q1", "wrong", T, node="N1")]
        rows = teacher.difficulty(evs, teacher.node_key)
        self.assertEqual(rows[0]["students"], 2)

    def test_word_key_ignores_direction(self):
        evs = [ev("a", "vocab:puella:la_en", "right", T),
               ev("a", "vocab:puella:en_la", "wrong", T)]
        rows = teacher.difficulty(evs, teacher.word_key)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["key"], "puella")

    def test_the_two_streams_do_not_mix(self):
        evs = [ev("a", "vocab:puella:la_en", "right", T),
               ev("a", "Q1", "wrong", T, node="N1")]
        self.assertEqual(len(teacher.difficulty(evs, teacher.node_key)), 1)
        self.assertEqual(len(teacher.difficulty(evs, teacher.word_key)), 1)


class TestMissReasons(unittest.TestCase):
    def rows(self):
        return [
            {"student_id": "a", "timestamp": T, "reason_node": "AGR", "reason_key": "k1",
             "reason_text": "I matched the ending", "contested": 0},
            {"student_id": "b", "timestamp": T, "reason_node": "AGR", "reason_key": "k1",
             "reason_text": "I matched the ending", "contested": 0},
            {"student_id": "a", "timestamp": T, "reason_node": "CASE", "reason_key": "k2",
             "reason_text": "I guessed", "contested": 1},
        ]

    def test_most_common_first(self):
        out = teacher.miss_reason_counts(self.rows())
        self.assertEqual(out[0]["reason_text"], "I matched the ending")
        self.assertEqual(out[0]["count"], 2)
        self.assertEqual(out[0]["students"], 2)

    def test_contested_is_carried(self):
        out = teacher.miss_reason_counts(self.rows())
        self.assertEqual(sum(r["contested"] for r in out), 1)

    def test_contested_items_listed(self):
        self.assertEqual(len(teacher.contested_items(self.rows())), 1)


if __name__ == "__main__":
    unittest.main()
