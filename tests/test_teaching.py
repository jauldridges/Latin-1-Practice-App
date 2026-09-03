"""Tests for teaching text: coverage, and the approval gate.

The load-bearing property is that DRAFT text is invisible to students. Teaching
text is written or approved by the teacher; the app must never show wording
that has not been signed off, including wording edited after it was signed off.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dataio  # noqa: E402
import store   # noqa: E402


class TestCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = dataio.load_spec()
        cls.teaching = dataio.load_teaching()

    def test_every_unit_0_1_node_has_teaching_text(self):
        u01 = {k for k, v in self.spec.items() if v.get("unit") in (0, 1)}
        missing = sorted(u01 - set(self.teaching))
        self.assertEqual(missing, [], f"nodes with no teaching text: {missing}")

    def test_no_invented_node_ids(self):
        bogus = sorted(set(self.teaching) - set(self.spec))
        self.assertEqual(bogus, [])

    def test_every_entry_has_all_three_parts(self):
        for nid, e in self.teaching.items():
            self.assertTrue(str(e.get("explain", "")).strip(), f"{nid}: no explain")
            self.assertTrue(e.get("examples"), f"{nid}: no examples")
            self.assertTrue(str(e.get("when_wrong", "")).strip(), f"{nid}: no when_wrong")

    def test_labels_match_the_spec(self):
        for nid, e in self.teaching.items():
            self.assertEqual(e.get("label"), self.spec[nid]["label"], f"{nid}: label drift")

    def test_everything_ships_as_draft(self):
        # The file is a draft for approval. Nothing may be pre-approved in it.
        for nid, e in self.teaching.items():
            self.assertEqual(e.get("status"), "draft", f"{nid} is not marked draft")

    def test_explanations_stay_phone_readable(self):
        for nid, e in self.teaching.items():
            n = len(str(e["explain"]).split())
            self.assertLessEqual(n, 120, f"{nid}: explain is {n} words, too long for a phone")


class TestApprovalGate(unittest.TestCase):
    def setUp(self):
        self.db = store.connect(":memory:") if False else store.connect(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "_t.sqlite"))
        store.init_db(self.db)
        self.db.execute("DELETE FROM teaching_approvals")
        self.db.commit()
        self.entry = {"label": "x", "explain": "An explanation.",
                      "examples": ["one", "two"], "when_wrong": "A nudge."}

    def tearDown(self):
        self.db.close()
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_t.sqlite")
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(p + suffix):
                os.remove(p + suffix)

    def test_unapproved_node_has_no_approval(self):
        self.assertNotIn("MS-001", store.teaching_approvals(self.db))

    def test_approval_records_the_fingerprint(self):
        fp = dataio.teaching_fingerprint(self.entry)
        store.approve_teaching(self.db, "MS-001", fp)
        self.assertEqual(store.teaching_approvals(self.db)["MS-001"], fp)

    def test_editing_after_approval_breaks_the_match(self):
        fp = dataio.teaching_fingerprint(self.entry)
        store.approve_teaching(self.db, "MS-001", fp)
        edited = dict(self.entry, explain="Reworded by the teacher.")
        # The stored approval no longer matches the current text, so the app
        # treats the node as unapproved again.
        self.assertNotEqual(dataio.teaching_fingerprint(edited),
                            store.teaching_approvals(self.db)["MS-001"])

    def test_fingerprint_covers_examples_and_when_wrong_too(self):
        base = dataio.teaching_fingerprint(self.entry)
        self.assertNotEqual(dataio.teaching_fingerprint(dict(self.entry, examples=["one"])), base)
        self.assertNotEqual(dataio.teaching_fingerprint(dict(self.entry, when_wrong="Different.")), base)

    def test_withdrawing_approval(self):
        fp = dataio.teaching_fingerprint(self.entry)
        store.approve_teaching(self.db, "MS-001", fp)
        store.unapprove_teaching(self.db, "MS-001")
        self.assertNotIn("MS-001", store.teaching_approvals(self.db))

    def test_reapproval_updates_the_fingerprint(self):
        store.approve_teaching(self.db, "MS-001", dataio.teaching_fingerprint(self.entry))
        edited = dict(self.entry, explain="Reworded.")
        store.approve_teaching(self.db, "MS-001", dataio.teaching_fingerprint(edited))
        self.assertEqual(store.teaching_approvals(self.db)["MS-001"],
                         dataio.teaching_fingerprint(edited))


if __name__ == "__main__":
    unittest.main(verbosity=2)
