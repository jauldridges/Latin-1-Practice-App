"""Tests for the decision log: append, undo, and what counts as hard to call.

The load-bearing distinction here is between a mis-tap and a change of mind.
Approve → undo → approve is one verdict recorded twice; approve → reject →
approve is a question that fought back. Only the second should ever reach the
flagged queue, or the flag is noise.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import store  # noqa: E402

S = "sess-1"


def item(iid, node="MS-001"):
    return {"id": iid, "node": node, "assess": "recognise", "tier": 1, "format": "choice"}


class Base(unittest.TestCase):
    def setUp(self):
        self.conn = store.connect(os.path.join(tempfile.mkdtemp(), "t.sqlite"))
        store.init_db(self.conn)
        store.import_items(self.conn, [item("Q1"), item("Q2")], {}, "test")


class TestAppend(Base):
    def test_a_decision_is_appended_not_overwritten(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q1", "rejected", reason="wrong answer", session_id=S)
        log = store.decisions_for(self.conn, "Q1")
        self.assertEqual([d["status"] for d in log], ["approved", "rejected"])

    def test_the_latest_decision_is_what_counts(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q1", "rejected", session_id=S)
        self.assertEqual(store.get_item(self.conn, "Q1")["review_status"], "rejected")
        self.assertEqual(store.approved_payloads(self.conn), [])

    def test_a_skip_is_logged_too(self):
        store.skip_item(self.conn, "Q1", session_id=S)
        self.assertEqual([d["status"] for d in store.decisions_for(self.conn, "Q1")],
                         ["skipped"])


class TestVerdictPath(Base):
    def test_repeats_collapse(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        self.assertEqual(store.verdict_path(self.conn, "Q1"), ["approved"])

    def test_skips_and_undos_are_not_verdicts(self):
        store.skip_item(self.conn, "Q1", session_id=S)
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.undo_last(self.conn, S)
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        self.assertEqual(store.verdict_path(self.conn, "Q1"), ["approved"])


class TestHardToCall(Base):
    def test_one_change_of_mind_is_not_flagged(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q1", "rejected", session_id=S)
        self.assertEqual(store.get_item(self.conn, "Q1")["flagged"], 0)

    def test_changing_back_is_flagged(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q1", "rejected", session_id=S)
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        it = store.get_item(self.conn, "Q1")
        self.assertEqual(it["flagged"], 1)
        self.assertIn("hard-to-call", [f["check"] for f in it["flags"]])

    def test_a_mistap_corrected_by_undo_is_not_flagged(self):
        # The whole reason undo writes 'undone' instead of a fresh verdict.
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.undo_last(self.conn, S)
        store.set_review(self.conn, "Q1", "rejected", session_id=S)
        store.undo_last(self.conn, S)
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        self.assertEqual(store.get_item(self.conn, "Q1")["flagged"], 0)

    def test_the_flag_is_not_added_twice(self):
        for status in ("approved", "rejected", "approved", "rejected", "approved"):
            store.set_review(self.conn, "Q1", status, session_id=S)
        flags = store.get_item(self.conn, "Q1")["flags"]
        self.assertEqual(sum(1 for f in flags if f["check"] == "hard-to-call"), 1)

    def test_they_are_listed(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q1", "rejected", session_id=S)
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q2", "approved", session_id=S)
        listed = store.hard_to_call(self.conn)
        self.assertEqual([d["item_id"] for d in listed], ["Q1"])


class TestUndo(Base):
    def test_undo_reopens_the_question(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        d = store.undo_last(self.conn, S)
        self.assertEqual(d["status"], "approved")
        self.assertEqual(store.get_item(self.conn, "Q1")["review_status"], "unreviewed")

    def test_undo_keeps_the_retracted_decision_in_the_record(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.undo_last(self.conn, S)
        self.assertEqual([d["status"] for d in store.decisions_for(self.conn, "Q1")],
                         ["approved", "undone"])

    def test_undo_works_the_same_after_a_rejection(self):
        store.set_review(self.conn, "Q1", "rejected", reason="duplicate", session_id=S)
        d = store.undo_last(self.conn, S)
        self.assertEqual(d["status"], "rejected")
        self.assertEqual(store.get_item(self.conn, "Q1")["review_status"], "unreviewed")

    def test_undoing_a_skip_brings_it_forward_again(self):
        store.skip_item(self.conn, "Q1", session_id=S)
        self.assertEqual(store.get_item(self.conn, "Q1")["skips"], 1)
        store.undo_last(self.conn, S)
        self.assertEqual(store.get_item(self.conn, "Q1")["skips"], 0)

    def test_undo_twice_steps_back_twice(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q2", "rejected", session_id=S)
        self.assertEqual(store.undo_last(self.conn, S)["item_id"], "Q2")
        self.assertEqual(store.undo_last(self.conn, S)["item_id"], "Q1")
        self.assertIsNone(store.undo_last(self.conn, S))

    def test_undo_is_scoped_to_the_sitting(self):
        store.set_review(self.conn, "Q1", "approved", session_id="other")
        self.assertIsNone(store.undo_last(self.conn, S))


class TestSessionHistory(Base):
    def test_most_recent_first(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.set_review(self.conn, "Q2", "rejected", reason="duplicate", session_id=S)
        hist = store.session_decisions(self.conn, S)
        self.assertEqual([h["item_id"] for h in hist], ["Q2", "Q1"])
        self.assertEqual(hist[0]["reason"], "duplicate")

    def test_it_carries_the_question_for_display(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        h = store.session_decisions(self.conn, S)[0]
        self.assertEqual(h["node_id"], "MS-001")
        self.assertIn("id", h["payload"])

    def test_an_undone_decision_stays_listed_but_marked(self):
        store.set_review(self.conn, "Q1", "approved", session_id=S)
        store.undo_last(self.conn, S)
        hist = store.session_decisions(self.conn, S)
        self.assertEqual(len(hist), 1)
        self.assertTrue(hist[0]["undone"])

    def test_other_sittings_do_not_appear(self):
        store.set_review(self.conn, "Q1", "approved", session_id="other")
        self.assertEqual(store.session_decisions(self.conn, S), [])


if __name__ == "__main__":
    unittest.main()


class TestRoutes(unittest.TestCase):
    """The four review changes, through the HTTP layer."""

    def setUp(self):
        for k in ("LATIN_TEACHER_PASSWORD", "LATIN_CLASS_CODE", "LATIN_PUBLIC"):
            os.environ.pop(k, None)
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.client = server.app.test_client()
        self.db = store.connect(self.db_path)
        store.init_db(self.db)
        store.import_items(self.db, [item("Q1"), item("Q2", "MS-002")], {}, "test")

    def tearDown(self):
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def decide(self, iid, action, **extra):
        data = {"item_id": iid, "action": action, "queue": "all", "node_id": "MS-001"}
        data.update(extra)
        return self.client.post("/review/action", data=data)

    def test_the_undo_strip_appears_only_after_a_decision(self):
        self.assertNotIn('class="lastaction"', self.client.get("/review/all").data.decode())
        self.decide("Q1", "approve")
        self.assertIn('class="lastaction"', self.client.get("/review/all").data.decode())

    def test_undo_reopens_that_question(self):
        self.decide("Q1", "approve")
        r = self.client.post("/review/undo", data={"queue": "all"})
        self.assertIn("/review/item/Q1", r.headers["Location"])
        body = self.client.get(r.headers["Location"]).data.decode()
        self.assertIn("Decide it again", body)
        self.assertIn("form-approve", body)          # the decision is open

    def test_undo_after_a_rejection_behaves_identically(self):
        self.decide("Q1", "reject", reason="duplicate")
        r = self.client.post("/review/undo", data={"queue": "all"})
        self.assertIn("/review/item/Q1", r.headers["Location"])
        self.assertEqual(store.get_item(self.db, "Q1")["review_status"], "unreviewed")

    def test_edit_instead_is_offered_after_a_rejection_only(self):
        self.decide("Q1", "approve")
        self.assertNotIn("Edit instead", self.client.get("/review/all").data.decode())
        self.decide("Q2", "reject")
        self.assertIn("Edit instead", self.client.get("/review/all").data.decode())

    def test_edit_instead_cancels_the_rejection(self):
        self.decide("Q1", "reject")
        r = self.client.get("/review/edit/Q1?queue=all&node_id=MS-001&from_reject=1")
        self.assertEqual(r.status_code, 302)
        body = self.client.get(r.headers["Location"]).data.decode()
        self.assertIn("rejection has been cancelled", body)
        self.assertEqual(store.get_item(self.db, "Q1")["review_status"], "unreviewed")

    def test_rejection_itself_is_still_one_tap(self):
        # The escape hatch comes after, not before: no confirmation screen.
        r = self.decide("Q1", "reject")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/review/all", r.headers["Location"])

    def test_history_lists_decisions_newest_first_and_links_to_them(self):
        self.decide("Q1", "approve")
        self.decide("Q2", "reject", reason="duplicate")
        body = self.client.get("/review/history").data.decode()
        self.assertLess(body.index("Q2"), body.index("Q1"))
        self.assertIn("/review/item/Q2", body)
        self.assertIn("duplicate", body)

    def test_history_survives_a_resume(self):
        # Same client keeps the cookie, which is what a resumed sitting is.
        self.decide("Q1", "approve")
        self.assertIn("/review/item/Q1", self.client.get("/review/history").data.decode())

    def test_a_new_sitting_starts_a_fresh_history(self):
        self.decide("Q1", "approve")
        other = self.server.app.test_client()
        self.assertNotIn("/review/item/Q1", other.get("/review/history").data.decode())

    def test_hard_to_call_gets_its_own_list_and_a_link(self):
        for status in ("approve", "reject", "approve"):
            self.decide("Q1", status)
        self.assertIn("Changed your mind more than once (1)",
                      self.client.get("/review").data.decode())
        self.assertIn("Q1", self.client.get("/review/hard").data.decode())

    def test_the_last_decision_of_a_sitting_is_still_undoable(self):
        # The done screen used to drop the strip, which made the final
        # decision — the tired one — the only one you could not take back.
        self.decide("Q1", "approve")
        self.decide("Q2", "reject")
        body = self.client.get("/review/all").data.decode()
        self.assertIn("Every question is decided", body)
        self.assertIn('class="lastaction"', body)
        self.assertIn("Edit instead", body)
