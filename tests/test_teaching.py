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


class TestRewordingInTheApp(unittest.TestCase):
    """Teaching text can be reworded without leaving the app.

    The edit goes in the database, not into teaching.yaml. A hosted service's
    disk does not survive a redeploy, so writing the file would lose the
    teacher's words the next time the app was updated -- quietly, and in favour
    of wording they had already decided against.
    """

    NODE = "MS-018"

    def setUp(self):
        import tempfile
        for k in ("LATIN_TEACHER_PASSWORD", "LATIN_PUBLIC"):
            os.environ.pop(k, None)
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.client = server.app.test_client()
        self.db = store.connect(self.db_path)
        self.yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "teaching.yaml")
        with open(self.yaml_path, "rb") as fh:
            self.yaml_before = fh.read()

    def tearDown(self):
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def edit(self, **over):
        data = {"explain": "A reworded explanation for the first declension.",
                "examples": "puella — the girl\nsilva — the forest",
                "when_wrong": "Look at the ending before you decide the job."}
        data.update(over)
        return self.client.post("/teaching/%s/edit" % self.NODE, data=data)

    def test_the_file_is_never_written_to(self):
        self.edit()
        self.client.post("/teaching/%s/approve" % self.NODE, data={"action": "approve"})
        self.client.post("/teaching/approve-all")
        with open(self.yaml_path, "rb") as fh:
            self.assertEqual(fh.read(), self.yaml_before,
                             "the app wrote to teaching.yaml")

    def test_an_edit_becomes_the_wording_in_force(self):
        self.edit()
        entry = self.server.teaching_entry(self.db, self.NODE)
        self.assertIn("reworded explanation", entry["explain"])
        self.assertEqual(entry["examples"], ["puella — the girl", "silva — the forest"])

    def test_saving_an_edit_clears_the_approval(self):
        # The fingerprint covers exact words. New words are not signed off.
        self.client.post("/teaching/%s/approve" % self.NODE, data={"action": "approve"})
        self.assertIsNotNone(self.server.approved_teaching_for(self.db, self.NODE))
        self.edit()
        self.assertIsNone(self.server.approved_teaching_for(self.db, self.NODE),
                          "reworded text reached a student without being re-read")
        self.assertEqual(self.server.teaching_state(self.db, self.NODE), "draft")

    def test_approving_a_reworded_node_serves_the_reworded_words(self):
        self.edit()
        self.client.post("/teaching/%s/approve" % self.NODE, data={"action": "approve"})
        served = self.server.approved_teaching_for(self.db, self.NODE)
        self.assertIsNotNone(served)
        self.assertIn("reworded explanation", served["explain"])

    def test_reverting_restores_the_file_and_drops_the_approval(self):
        self.edit()
        self.client.post("/teaching/%s/approve" % self.NODE, data={"action": "approve"})
        self.client.post("/teaching/%s/edit" % self.NODE, data={"action": "revert"})
        entry = self.server.teaching_entry(self.db, self.NODE)
        self.assertNotIn("reworded explanation", entry["explain"])
        self.assertIsNone(self.server.approved_teaching_for(self.db, self.NODE))

    def test_it_refuses_to_empty_the_explanation(self):
        r = self.edit(explain="")
        self.assertEqual(r.status_code, 400)
        self.assertIsNone(store.teaching_override(self.db, self.NODE))

    def test_it_refuses_to_drop_every_example(self):
        self.assertEqual(self.edit(examples="   \n  ").status_code, 400)

    def test_it_keeps_the_explanation_phone_readable(self):
        # Same 120-word rule the drafted text is held to.
        self.assertEqual(self.edit(explain="word " * 200).status_code, 400)


class TestApprovingFromTheReviewScreen(TestRewordingInTheApp):
    def setUp(self):
        super(TestApprovingFromTheReviewScreen, self).setUp()
        import checks
        items = dataio.load_bank()
        flags, _ = checks.run_all(items, set(dataio.load_spec()),
                                  dataio.allowed_latin(dataio.load_exemplars()))
        store.import_items(self.db, items, flags, "test")

    def test_the_question_screen_carries_its_node_s_teaching_text(self):
        body = self.client.get("/review/node/%s" % self.NODE).data.decode()
        self.assertIn("Teaching text", body)
        self.assertIn("not yet approved", body)
        self.assertIn("Approve teaching text", body)
        self.assertIn("Edit teaching text", body)

    def test_approving_returns_to_the_question(self):
        # Reviewing is a flow; approving the explanation must not leave it.
        # `request.full_path` hands over a trailing "?" and Werkzeug normalises
        # it off the redirect, so compare the path rather than the exact string.
        back = "/review/node/%s?" % self.NODE
        r = self.client.post("/teaching/%s/approve" % self.NODE,
                             data={"action": "approve", "back": back})
        self.assertEqual(r.status_code, 302)
        landed = r.headers["Location"]
        self.assertIn("/review/node/%s" % self.NODE, landed)
        self.assertNotIn("/teaching", landed, "approving dropped out of the review flow")

    def test_an_approved_node_says_so_and_still_offers_an_edit(self):
        self.client.post("/teaching/%s/approve" % self.NODE, data={"action": "approve"})
        body = self.client.get("/review/node/%s" % self.NODE).data.decode()
        self.assertIn("Approved teaching text", body)
        self.assertIn("Edit teaching text", body)


class TestApproveAll(TestRewordingInTheApp):
    def test_it_approves_everything_waiting(self):
        import dataio
        self.client.post("/teaching/approve-all")
        approvals = store.teaching_approvals(self.db)
        self.assertEqual(len(approvals), len(self.server._TEACHING))
        for nid in self.server._TEACHING:
            self.assertEqual(self.server.teaching_state(self.db, nid), "approved")

    def test_it_signs_off_the_wording_in_force_not_the_file(self):
        self.edit()
        self.client.post("/teaching/approve-all")
        served = self.server.approved_teaching_for(self.db, self.NODE)
        self.assertIn("reworded explanation", served["explain"])

    def test_a_later_reword_still_needs_reading_again(self):
        self.client.post("/teaching/approve-all")
        self.edit()
        self.assertIsNone(self.server.approved_teaching_for(self.db, self.NODE))


class TestTheOverrideSurvivesABackup(unittest.TestCase):
    def test_backup_and_migrate_carry_the_table(self):
        # An edit that a backup does not carry is an edit the teacher loses.
        import backup, migrate
        self.assertIn("teaching_overrides", backup.TABLES)
        self.assertIn("teaching_overrides", migrate.TABLES)
