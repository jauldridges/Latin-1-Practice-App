"""Tests for continuous review — one question after another, no trip home.

Three claims worth holding:
  * it walks the bank in TEACHING order, not alphabetical (the node ids sort
    CR before MS; the course does not),
  * skip advances instead of handing the same card back,
  * flagged items come last, and only then is it done.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import store  # noqa: E402


def item(iid, node, fmt="choice"):
    return {"id": iid, "node": node, "assess": "recognise", "tier": 1, "format": fmt}


class Base(unittest.TestCase):
    """Shared fixture. Subclasses are the test cases; this one holds none, so
    the suite is not run twice over."""

    def setUp(self):
        for k in ("LATIN_TEACHER_PASSWORD", "LATIN_CLASS_CODE", "LATIN_PUBLIC"):
            os.environ.pop(k, None)
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        self.server = server
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        self.db = store.connect(self.db_path)
        store.init_db(self.db)

    def tearDown(self):
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def load(self, items, flags=None):
        store.import_items(self.db, items, flags or {}, "test")

    def nxt(self, after=None):
        # No app context: picking the next item is plain SQL plus the spec's
        # node order, and binding g.db here would have the teardown close the
        # connection out from under the test.
        return self.server._next_continuous(self.db, after)


class TestOrder(Base):

    def test_teaching_order_not_alphabetical(self):
        # CR-001 sorts before MS-001 but is taught after it.
        self.load([item("Q-CR", "CR-001"), item("Q-MS", "MS-001")])
        self.assertEqual(self.nxt()["item_id"], "Q-MS")

    def test_walks_on_once_a_node_is_decided(self):
        self.load([item("Q-MS", "MS-001"), item("Q-CR", "CR-001")])
        store.set_review(self.db, "Q-MS", "approved")
        self.assertEqual(self.nxt()["item_id"], "Q-CR")

    def test_flagged_items_come_last(self):
        self.load([item("Q-FLAG", "MS-001"), item("Q-PLAIN", "MW-088")],
                  flags={"Q-FLAG": [{"check": "c", "level": "error", "detail": "d"}]})
        # MS-001 is taught first, but its only item is flagged, so the plain
        # one from the very last node is served ahead of it.
        self.assertEqual(self.nxt()["item_id"], "Q-PLAIN")
        store.set_review(self.db, "Q-PLAIN", "approved")
        self.assertEqual(self.nxt()["item_id"], "Q-FLAG")

    def test_nothing_left_is_none(self):
        self.load([item("Q1", "MS-001")])
        store.set_review(self.db, "Q1", "approved")
        self.assertIsNone(self.nxt())

    def test_skip_on_the_last_item_of_a_node_moves_on(self):
        # Without the exclusion this hands the same card straight back: it is
        # still the least-skipped unreviewed item in that node.
        self.load([item("Q-MS", "MS-001"), item("Q-CR", "CR-001")])
        self.assertEqual(self.nxt()["item_id"], "Q-MS")
        store.skip_item(self.db, "Q-MS")
        self.assertEqual(self.nxt(after="Q-MS")["item_id"], "Q-CR")

    def test_a_skipped_item_comes_back_later(self):
        self.load([item("Q-MS", "MS-001"), item("Q-CR", "CR-001")])
        store.skip_item(self.db, "Q-MS")
        store.set_review(self.db, "Q-CR", "approved")
        self.assertEqual(self.nxt()["item_id"], "Q-MS")   # deferred, not dropped


class TestRoutes(Base):
    def test_the_screen_renders_and_counts_the_whole_bank(self):
        self.load([item("Q-MS", "MS-001"), item("Q-CR", "CR-001")])
        body = self.client.get("/review/all").data.decode()
        self.assertIn("left in the whole bank", body)
        self.assertIn("MS-001", body)

    def test_approving_serves_the_next_one_without_going_home(self):
        self.load([item("Q-MS", "MS-001"), item("Q-CR", "CR-001")])
        r = self.client.post("/review/action", data={
            "item_id": "Q-MS", "action": "approve", "queue": "all", "node_id": "MS-001"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/review/all", r.headers["Location"])
        self.assertIn("CR-001", self.client.get(r.headers["Location"]).data.decode())

    def test_skip_carries_the_item_through_the_redirect(self):
        self.load([item("Q-MS", "MS-001"), item("Q-CR", "CR-001")])
        r = self.client.post("/review/action", data={
            "item_id": "Q-MS", "action": "skip", "queue": "all", "node_id": "MS-001"})
        self.assertIn("after=Q-MS", r.headers["Location"])
        self.assertIn("CR-001", self.client.get(r.headers["Location"]).data.decode())

    def test_the_done_screen_only_appears_at_the_very_end(self):
        self.load([item("Q1", "MS-001")])
        self.client.post("/review/action", data={
            "item_id": "Q1", "action": "approve", "queue": "all", "node_id": "MS-001"})
        self.assertIn("Every question is decided", self.client.get("/review/all").data.decode())

    def test_a_node_queue_offers_to_continue_rather_than_dead_ending(self):
        self.load([item("Q-MS", "MS-001"), item("Q-CR", "CR-001")])
        store.set_review(self.db, "Q-MS", "approved")
        body = self.client.get("/review/node/MS-001").data.decode()
        self.assertIn("Keep going", body)
        self.assertIn("/review/all", body)


if __name__ == "__main__":
    unittest.main()


class TestSkipDefers(Base):
    """A skip must survive more than one card.

    The bug this holds shut: with a single ordered pass, skipping an item in
    MS-003 served it straight back as soon as MS-004 emptied — one question of
    "later".
    """

    def test_a_skip_waits_for_the_whole_pass(self):
        self.load([item("Q-A", "MS-001"), item("Q-B", "MS-002"), item("Q-C", "MS-003")])
        store.skip_item(self.db, "Q-A")
        self.assertEqual(self.nxt(after="Q-A")["item_id"], "Q-B")
        store.set_review(self.db, "Q-B", "approved")
        # Q-A is in the earliest node, but it has been deferred: C first.
        self.assertEqual(self.nxt()["item_id"], "Q-C")
        store.set_review(self.db, "Q-C", "approved")
        self.assertEqual(self.nxt()["item_id"], "Q-A")

    def test_it_still_comes_back_before_the_flagged_queue(self):
        self.load([item("Q-A", "MS-001"), item("Q-F", "MS-002")],
                  flags={"Q-F": [{"check": "c", "level": "error", "detail": "d"}]})
        store.skip_item(self.db, "Q-A")
        self.assertEqual(self.nxt()["item_id"], "Q-A")
