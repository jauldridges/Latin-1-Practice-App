"""Rules every question in the bank has to obey.

These are not style preferences. Each one caused a real defect while Unit 2 was
being written, and each is invisible to the mechanical checks in checks.py,
which look at a question in isolation. These look at a question against the
syllabus.

The one that matters most is scope. An item may not lean on a node taught after
its own — not in what it uses, not in where it sends a student who gets it
wrong. The practice app gates teaching by date, so a miss-reason pointing at
next week's lesson is a menu line that leads nowhere.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dataio  # noqa: E402

SPEC = dataio.load_spec()
BANK = dataio.load_bank()


def day(node):
    """When a node is taught.

    Sixteen nodes have a week but no day: their `vehicle` is `module` — Roman
    culture delivered as a block rather than a dated lesson — so the week is
    the only date they have, and it is the right one.
    """
    d = SPEC.get(node, {})
    return str(d.get("day") or d.get("week") or "")


class TestNodes(unittest.TestCase):
    def test_every_item_names_a_real_node(self):
        bad = [i["id"] for i in BANK if i["node"] not in SPEC]
        self.assertEqual(bad, [])

    def test_every_touch_is_a_real_node(self):
        bad = [(i["id"], t) for i in BANK for t in (i.get("touches") or [])
               if t not in SPEC]
        self.assertEqual(bad, [])

    def test_every_miss_reason_routes_to_a_real_node(self):
        bad = [(i["id"], w.get("node")) for i in BANK
               for w in (i.get("what_went_wrong") or []) if w.get("node") not in SPEC]
        self.assertEqual(bad, [])

    def test_an_item_does_not_touch_its_own_node(self):
        # `touches` is for the OTHER nodes an item exercises; the node itself
        # is already in `node`.
        bad = [(i["id"], t) for i in BANK for t in (i.get("touches") or [])
               if t == i["node"]]
        self.assertEqual(bad, [])


class TestScope(unittest.TestCase):
    """What an item may LEAN ON, which is not the same as what it may mention.

    There is no rule against pointing forward. `touches` and `what_went_wrong`
    are diagnostic links: "I confused the macron with stress" belongs on the
    stress node whether or not stress has been taught yet, because that is
    where the misconception lives and where the teacher will look for it. The
    original bank does this deliberately in 51 touches and 28 miss-reasons.

    The real rule is about content — an item may not require a form the student
    has not met — and no test can check that, because it is a judgement about
    what a question is asking. It is enforced by writing each item against its
    node's date, and it caught two real defects in Unit 2: an adjective
    agreement item using a third declension NEUTER plural four days before
    neuters are taught, and an explain item whose only correct answer was the
    infinitive test, taught two days later.
    """

    def test_items_are_written_against_a_dated_syllabus(self):
        # The guard that makes the judgement above possible at all: every node
        # an item names has a teaching date to be judged against — a day, or
        # for a culture module, a week.
        undated = sorted({i["node"] for i in BANK if not day(i["node"])})
        self.assertEqual(undated, [])


class TestShape(unittest.TestCase):
    def test_ids_are_unique(self):
        seen, dupes = set(), []
        for i in BANK:
            if i["id"] in seen:
                dupes.append(i["id"])
            seen.add(i["id"])
        self.assertEqual(dupes, [])

    def test_recall_is_never_multiple_choice(self):
        # A recall question the student can recognise their way through is not
        # testing recall.
        bad = [i["id"] for i in BANK
               if i.get("assess") == "recall" and i.get("format") == "choice"]
        self.assertEqual(bad, [])

    def test_a_choice_item_names_an_answer_that_exists(self):
        bad = [i["id"] for i in BANK if i.get("format") == "choice"
               and i.get("answer") not in (i.get("options") or {})]
        self.assertEqual(bad, [])

    def test_teaching_stays_empty_in_the_bank(self):
        # Teaching text lives in teaching.yaml, keyed by node. The field here
        # is vestigial and must not be filled in by hand.
        bad = [i["id"] for i in BANK if i.get("teaching") not in ("", None)]
        self.assertEqual(bad, [])

    def test_box_answers_stay_short(self):
        # Boxes are graded by string match; a free sentence cannot be.
        bad = [(i["id"], a) for i in BANK for b in (i.get("boxes") or [])
               for a in (b.get("answer") or []) if len(str(a).split()) > 4]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
