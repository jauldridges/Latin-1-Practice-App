"""Grammar badges: the list, the forgetting timer, the homework rule, and a
badge check from the map to the result."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schooltime  # noqa: E402,F401
import badges      # noqa: E402
import checks      # noqa: E402
import dataio      # noqa: E402
import goals       # noqa: E402
import store       # noqa: E402

SPEC = dataio.load_spec()
ROWS, BADGES = badges.load()
BY_ID = {b["id"]: b for b in BADGES}
DAY = 86400


def noon(y, m, d):
    return time.mktime((y, m, d, 12, 0, 0, 0, 0, -1))


def mark(bid, ts, passed=True):
    return {"item_id": badges.item_id(bid), "timestamp": ts, "context": "badge",
            "result": "right" if passed else "wrong", "rating": 3 if passed else 1}


class TestTheList(unittest.TestCase):
    def test_every_unit_0_to_2_grammar_topic_is_in_exactly_one_badge(self):
        seen = [n for b in BADGES for n in b["nodes"]]
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual([n for n in seen if n not in SPEC], [])
        ms = [k for k, v in SPEC.items() if k.startswith("MS-") and v.get("unit") in (0, 1, 2)]
        self.assertEqual(sorted(set(ms) - set(seen)), [])

    def test_ids_rows_and_words(self):
        self.assertEqual(len({b["id"] for b in BADGES}), len(BADGES))
        rows = {r["id"] for r in ROWS}
        self.assertEqual([b["id"] for b in BADGES if b["row"] not in rows], [])
        words = " ".join(b["title"] + " " + b["about"] for b in BADGES).lower()
        self.assertNotIn("master", words)          # never "mastery" to a student
        self.assertNotIn("practi" + "se", words)            # American spelling

    def test_every_description_is_complete_sentences(self):
        for b in BADGES:
            self.assertTrue(b["about"].startswith("This badge covers "), b["id"])
            self.assertTrue(b["about"].endswith((".", ".”")), b["id"])
            self.assertGreater(len(b["about"].split()), 12, b["id"])

    def test_the_tree_runs_downhill(self):
        # Every line goes from a higher row to a lower one: no badge builds on
        # itself, even through others.
        lv = badges.levels(BADGES, SPEC)
        found = badges.foundations(BADGES, SPEC)
        for bid, pre in found.items():
            for p in pre:
                self.assertLess(lv[p], lv[bid], (p, bid))
        direct = badges.direct_foundations(BADGES, SPEC)
        self.assertEqual(direct["genitive"], ["second-declension"])    # no shortcut lines
        self.assertEqual([b for b in BADGES if lv[b["id"]] == 0 and b["id"] == "sounds"][0]["id"], "sounds")

    def test_the_arrows_come_from_the_spec(self):
        found = badges.foundations(BADGES, SPEC)
        self.assertIn("subjects-objects", found["second-declension"])
        self.assertIn("first-declension", found["genitive"])
        self.assertEqual(found["sounds"], [])

    def test_a_badge_appears_when_its_first_topic_is_taught(self):
        items = [{"id": "q-%s" % n, "node": n} for b in BADGES for n in b["nodes"]]
        oct27 = {b["id"] for b in badges.available(BADGES, SPEC, items, "2026-10-27")}
        self.assertIn("dative", oct27)
        self.assertNotIn("third-declension", oct27)          # taught Nov 2
        self.assertIn("third-declension",
                      {b["id"] for b in badges.available(BADGES, SPEC, items, "2026-11-02")})
        # no approved questions, no badge
        self.assertNotIn("dative", {b["id"] for b in badges.available(BADGES, SPEC, [], "2026-12-01")})


class TestTheTimer(unittest.TestCase):
    def test_earned_then_fading_then_refreshed(self):
        t = noon(2026, 10, 20)
        self.assertEqual(badges.status([], "genitive", t)["state"], "not yet")
        evs = [mark("genitive", t)]
        st = badges.status(evs, "genitive", t + 60)
        self.assertTrue(st["earned"] and st["up_to_date"])
        self.assertEqual(st["days_left"], 2)                 # a first pass holds ~3 days
        later = badges.status(evs, "genitive", t + 4 * DAY)
        self.assertTrue(later["due"])
        self.assertEqual(later["next"], "refresh")
        evs.append(mark("genitive", t + 4 * DAY))
        st = badges.status(evs, "genitive", t + 4 * DAY + 60)
        self.assertGreaterEqual(st["days_left"], 8)          # each refresh holds longer

    def test_a_failed_first_check_earns_nothing(self):
        t = noon(2026, 10, 20)
        st = badges.status([mark("genitive", t, passed=False)], "genitive", t + 60)
        self.assertEqual((st["earned"], st["next"]), (False, "earn"))

    def test_pass_marks(self):
        self.assertEqual(badges.needed("earn", 6), 5)
        self.assertEqual(badges.needed("earn", 3), 3)
        self.assertEqual(badges.needed("refresh", 3), 2)


class TestTheWeek(unittest.TestCase):
    start = goals.key_start("2026-10-31")                    # Sat 31 Oct
    end = goals.week_end(goals.key_start("2026-10-31"))

    def how(self, evs):
        return badges.done_for_week(evs, "genitive", self.start, self.end)[0]

    def test_up_to_date_at_the_deadline(self):
        self.assertEqual(self.how([mark("genitive", self.start + DAY)]), "on time")
        # earned long ago and refreshed, still holding on Friday night
        old = [mark("genitive", self.start - 30 * DAY), mark("genitive", self.start - 26 * DAY),
               mark("genitive", self.start - 2 * DAY)]
        self.assertEqual(self.how(old), "on time")

    def test_fading_by_friday_and_refreshed_later_is_late(self):
        evs = [mark("genitive", self.start - 2 * DAY)]       # due Mon
        self.assertIsNone(self.how(evs))
        evs.append(mark("genitive", self.end + DAY))
        self.assertEqual(self.how(evs), "late")

    def test_the_homework_week(self):
        rule = {"from": "2026-10-31", "required": lambda end: ["genitive", "dative"]}
        t = self.start + DAY
        vocab = [{"item_id": "vocab:w%d:la_en" % i, "timestamp": t + i, "result": "right",
                  "rating": 3, "context": "practice"} for i in range(50)]
        grammar = [{"item_id": "Q%d" % i, "spec_node_id": "MS-052", "timestamp": t + 100 + i,
                    "result": "right", "rating": 3, "context": "practice"} for i in range(60)]
        weeks = ["2026-10-24", "2026-10-31"]
        now = self.end + 3 * DAY

        def week(evs):
            rows = goals.homework_history(evs, None, weeks, now=now, badge_rule=rule)
            return rows[0], rows[1]

        before, w = week(vocab + grammar)
        self.assertIsNone(before["badges"])                  # before the switch: 50 + 50 cards
        self.assertEqual(w["targets"]["grammar"], 0)          # grammar cards don't fill a badge week
        self.assertEqual(w["status"], "not done")
        self.assertEqual(w["badges"]["missing"], ["genitive", "dative"])
        _, w = week(vocab + [mark("genitive", t + 500), mark("dative", t + 600)])
        self.assertEqual(w["status"], "on time")
        _, w = week(vocab + [mark("genitive", t + 500), mark("dative", self.end + DAY)])
        self.assertEqual(w["status"], "late")


class TestPicking(unittest.TestCase):
    def test_a_check_spreads_across_topics_and_rotates(self):
        items = [{"id": "%s-%d" % (n, i), "node": n} for n in ("MS-049", "MS-050") for i in range(4)]
        first = badges.pick(items, [], 6)
        self.assertEqual(sorted({it["node"] for it in first}), ["MS-049", "MS-050"])
        self.assertEqual(len(first), 6)
        seen = [{"item_id": it["id"], "timestamp": 1000 + i} for i, it in enumerate(first)]
        again = badges.pick(items, seen, 2)
        self.assertEqual({it["id"] for it in again} & {it["id"] for it in first}, set())


class TestTheNLEQuestion(unittest.TestCase):
    """Every badge check asks at least one past-NLE question when it has one."""
    ITEMS = ([{"id": "MS1-%d" % i, "node": "MS-001"} for i in range(5)]
             + [{"id": "MS2-%d" % i, "node": "MS-002"} for i in range(5)]
             + [{"id": "NLE-2019-latin1-0%d" % i, "node": "MS-002"} for i in (1, 2)])

    def test_one_is_always_asked(self):
        for n in (6, 3, 1):
            got = [it["id"] for it in badges.pick(self.ITEMS, [], n)]
            self.assertEqual(len(got), n)
            self.assertEqual(sum(i.startswith("NLE-") for i in got), 1, got)
        self.assertEqual(len({it["node"] for it in badges.pick(self.ITEMS, [], 6)}), 2)   # still spread

    def test_the_least_recently_met_one(self):
        events = [{"item_id": "NLE-2019-latin1-01", "timestamp": 100.0}]
        got = [it["id"] for it in badges.pick(self.ITEMS, events, 6)]
        self.assertIn("NLE-2019-latin1-02", got)

    def test_none_without_any(self):
        got = [it["id"] for it in badges.pick(self.ITEMS[:10], [], 6)]
        self.assertFalse(any(i.startswith("NLE-") for i in got))


class _App(unittest.TestCase):
    BADGE = "talking-to"

    def setUp(self):
        os.environ.pop("LATIN_PUBLIC", None)
        os.environ["LATIN_TEACHER_PASSWORD"] = "teacherpw"
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.db = store.connect(self.db_path)
        items = dataio.load_bank()
        flags, _ = checks.run_all(items, set(SPEC), dataio.allowed_latin(dataio.load_exemplars()))
        store.import_items(self.db, items, flags, "t")
        # The past-NLE questions arrive pre-approved (nle.py). Set aside here,
        # so this badge is the only one with questions.
        self.db.execute("UPDATE items SET review_status='rejected' WHERE item_id LIKE 'NLE-%'")
        self.db.commit()
        self.ids = [i["id"] for i in items if i["node"] in BY_ID[self.BADGE]["nodes"]]
        for iid in self.ids:
            store.set_review(self.db, iid, "approved")
        store.add_student(self.db, "403217", "Block 3")
        self.t = server.app.test_client()
        self.t.post("/login", data={"password": "teacherpw", "next": "/teacher"})
        self.c = server.app.test_client()
        self.c.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.c.post("/signin", data={"step": "pin", "student_id": "403217",
                                     "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def switch_on(self, week=None):
        week = week or goals.week_key(time.time())
        self.t.post("/teacher/deadlines", data={"form": "badges", "badges_from": week})

    def run_check(self, right):
        """Start a check and answer it: the first `right` questions right."""
        r = self.c.post("/badges/%s/start" % self.BADGE)
        self.assertIn("node=badge", r.headers["Location"])
        body = self.c.get(r.headers["Location"]).data.decode()
        self.assertIn('class="badgebar"', body)
        with self.c.session_transaction() as sess:
            run = sess["badge_run"]
        for i, iid in enumerate(run["items"]):
            ok = i < right
            store.record_event(self.db, "403217", iid, "MS-050", "x", "right" if ok else "wrong",
                               timestamp=run["t"] + 1 + i, rating=3 if ok else 1)
        r = self.c.get("/practice/session?node=badge:%s" % self.BADGE)
        self.assertIn("/badges/%s/done" % self.BADGE, r.headers["Location"])
        return run, self.c.get(r.headers["Location"]).data.decode()


class TestTheMap(_App):
    def test_off_until_the_teacher_switches_it_on(self):
        self.assertEqual(self.c.get("/practice").status_code, 200)       # the topic list
        self.assertIn("teacher preview", self.t.get("/badges").data.decode())
        self.switch_on()
        self.assertIn("/badges", self.c.get("/practice").headers["Location"])
        page = self.c.get("/badges").data.decode()
        self.assertIn("Talking to someone", page)
        self.assertIn("Start here", page)
        self.assertIn('data-parents="second-declension conjugations"', page)   # talking-to's lines
        self.assertIn('id="pop-talking-to"', page)
        self.assertIn("This badge covers talking straight to someone", page)
        # only one badge has approved questions here: the rest are greyed
        self.assertIn('class="node coming', page)
        self.assertIn("questions aren&#39;t ready yet", page.replace("'", "&#39;"))
        self.assertNotIn("master", page.lower())
        self.assertEqual(self.c.get("/practice?topics=1").status_code, 200)

    def test_earning_a_badge(self):
        self.switch_on()
        run, body = self.run_check(right=5)
        self.assertEqual(len(run["items"]), 6)
        self.assertIn("Badge earned", body)
        st = badges.status(store.events_for_student(self.db, "403217"), self.BADGE)
        self.assertTrue(st["earned"] and st["up_to_date"])
        page = self.c.get("/badges").data.decode()
        self.assertIn("holds 2 more days", page)
        self.assertIn("Check it again", page)
        self.assertIn('class="node earned', page)

    def test_not_yet(self):
        self.switch_on()
        _, body = self.run_check(right=4)
        self.assertIn("Not yet", body)
        self.assertIn("you need 5", body)
        self.assertFalse(badges.status(store.events_for_student(self.db, "403217"),
                                       self.BADGE)["earned"])

    def test_the_record_is_one_event_and_not_a_card(self):
        self.switch_on()
        self.run_check(right=6)
        evs = store.events_for_student(self.db, "403217")
        marks = [e for e in evs if badges.is_marker(e)]
        self.assertEqual([(m["context"], m["response"]) for m in marks], [("badge", "earn 6/6")])
        import teacher
        self.assertEqual(teacher.homework_counts(evs)["grammar"], 6)   # the questions, not the record

    def test_the_home_screen_and_the_dashboard(self):
        self.switch_on()
        home = self.c.get("/").data.decode()
        self.assertIn("Grammar badges", home)
        self.assertIn("0 of 1 up to date", home)          # one badge has approved questions
        self.assertIn("Talking to someone", home)
        self.run_check(right=6)
        home = self.c.get("/").data.decode()
        self.assertIn("✓ all 1 up to date", home)
        dash = self.t.get("/teacher").data.decode()
        self.assertIn("<th>Badges</th>", dash)
        page = self.t.get("/teacher/student/403217").data.decode()
        self.assertIn('id="badges"', page)
        self.assertIn("earn 6/6", page)

    def test_the_teacher_page(self):
        page = self.t.get("/teacher/badges").data.decode()
        self.assertIn("Where Latin comes from", page)
        self.assertIn("MS-049", page)
        self.assertIn("/login", self.c.get("/teacher/badges").headers["Location"])
        self.assertIn("Grammar badges", self.t.get("/teacher/deadlines").data.decode())

    def test_a_student_cannot_switch_badges_on(self):
        self.c.post("/teacher/deadlines", data={"form": "badges", "badges_from": "2026-10-31"})
        self.assertIsNone(store.get_setting(self.db, "badges"))


if __name__ == "__main__":
    unittest.main()
