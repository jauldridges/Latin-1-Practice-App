"""Tests for the drill's schedule (FSRS) and the solid/shaky/not-yet logic."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import drill  # noqa: E402

DAY = 86400.0


def ev(latin, ask, result, ts):
    return {"item_id": f"vocab:{latin}:{ask}", "result": result, "timestamp": ts}


class TestSchedule(unittest.TestCase):
    """The drill's schedule is FSRS (fsrs.py); these hold the drill's use of it."""

    def test_a_new_word_has_no_card(self):
        self.assertIsNone(drill.card_state([]))

    def test_right_pushes_the_next_review_out(self):
        t = 1_000_000.0
        once = drill.card_state([ev("aqua", "la_en", "right", t)])
        twice = drill.card_state([ev("aqua", "la_en", "right", t),
                                  ev("aqua", "la_en", "right", t + 3 * DAY)])
        self.assertGreater(once.due, t)
        self.assertGreater(twice.stability, once.stability)

    def test_a_miss_is_a_setback_not_a_reset(self):
        t = 1_000_000.0
        evs = [ev("aqua", "la_en", "right", t + d * DAY) for d in (0, 3, 10, 30)]
        strong = drill.card_state(evs)
        after = drill.card_state(evs + [ev("aqua", "la_en", "wrong", t + 70 * DAY)])
        self.assertLess(after.stability, strong.stability)
        self.assertGreater(after.stability, drill.card_state([ev("aqua", "la_en", "wrong", t)]).stability)

    def test_a_retyped_typo_is_not_a_review(self):
        t = 1_000_000.0
        a = drill.card_state([ev("aqua", "la_en", "right", t)])
        b = drill.card_state([ev("aqua", "la_en", "right", t), ev("aqua", "la_en", "close", t + 10)])
        self.assertEqual(a.stability, b.stability)

    def test_both_directions_are_one_word(self):
        t = 1_000_000.0
        card = drill.card_state([ev("aqua", "la_en", "right", t), ev("aqua", "en_la", "right", t + 3 * DAY)])
        self.assertEqual(card.reps, 2)

    def test_due_words_come_before_new_ones(self):
        words = [{"latin": "aqua", "en": ["water"], "week": "week_of_aug_31"},
                 {"latin": "terra", "en": ["land"], "week": "week_of_aug_31"},
                 {"latin": "via", "en": ["road"], "week": "week_of_aug_31"}]
        t = 1_000_000.0
        evs = [ev("terra", "la_en", "wrong", t),               # due again in 5 minutes
               ev("via", "la_en", "right", t + 1)]             # just answered
        card = drill.next_card(words, evs, week="week_of_aug_31", now=t + 600)
        self.assertEqual(card.latin, "terra")                  # not the new "aqua"

    def test_never_the_word_just_answered_while_another_is_left(self):
        words = [{"latin": "aqua", "en": ["water"], "week": "week_of_aug_31"},
                 {"latin": "terra", "en": ["land"], "week": "week_of_aug_31"}]
        t = 1_000_000.0
        evs = [ev("aqua", "la_en", "right", t), ev("terra", "la_en", "right", t + 1)]
        for _ in range(2):
            card = drill.next_card(words, evs, week="week_of_aug_31", now=t + 60)
            self.assertNotEqual(card.latin, evs[-1]["item_id"].split(":")[1])
            evs.append(ev(drill._key(card.latin), "la_en", "right", evs[-1]["timestamp"] + 1))


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
        self.assertEqual(drill.by_week(self.rows())[0]["label"], "Week of Monday August 24")

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


class TestDictionaryEntries(unittest.TestCase):
    """Every Latin prompt shows the forms the class has learned: a noun's
    nominative, genitive and gender; a verb's first person singular and
    infinitive; an adjective's nominative in every gender."""

    def setUp(self):
        import dataio
        self.words = dataio.load_drill_words()
        self.lists = dataio

    def test_every_noun_verb_and_adjective_has_its_entry(self):
        from answercheck import clean
        d = self.lists
        nouns = set(d._FIRST_DECL) | set(d._SECOND_US) | set(d._SECOND_ER) \
            | set(d._SECOND_NEUTER) | {"rex", "dux", "miles", "homo", "pater", "mater",
                                       "lex", "iuvenis", "senex", "nomen", "corpus",
                                       "tempus", "caput", "liberi"}
        verbs = set(d._FIRST_CONJ) | set(d._SECOND_CONJ) | {"sum", "possum", "do", "credo"}
        adjs = set(d._ADJ_US) | set(d._ADJ_ER) | {"omnis", "fortis", "nobilis"}
        seen = set()
        for w in self.words:
            k, e = clean(w["latin"]), w.get("entry", "")
            parts = [p.strip() for p in e.split(",")]
            if k in adjs:
                seen.add(k)
                self.assertTrue(len(parts) == 3 or (len(parts) == 2 and parts[1].endswith("e")), e)
                self.assertEqual(clean(parts[0]), k)
            elif k in nouns:
                seen.add(k)
                self.assertEqual(len(parts), 3, e)
                self.assertIn(parts[2], ("m.", "f.", "n.", "m. pl."), e)
                self.assertEqual(clean(parts[0]), k)
            elif k in verbs:
                seen.add(k)
                self.assertEqual(len(parts), 2, e)
                self.assertTrue(clean(parts[1]).endswith(("re", "se")), e)
                self.assertEqual(clean(parts[0]), k)
            else:
                self.assertNotIn("entry", w, w["latin"])   # et, non, the phrases
        self.assertGreater(len(seen), 100)

    def test_the_latin_prompt_is_the_entry_and_the_english_one_is_not(self):
        rex = drill.find_word(self.words, "rex")
        self.assertEqual(drill.card_for(rex, "la_en").prompt, "rēx, rēgis, m.")
        self.assertEqual(drill.card_for(rex, "en_la").prompt, "king")
        self.assertEqual(drill.accepted_for(rex, "en_la"), ["rēx"])    # still type just rēx
        et = drill.find_word(self.words, "et")
        self.assertEqual(drill.card_for(et, "la_en").prompt, "et")
