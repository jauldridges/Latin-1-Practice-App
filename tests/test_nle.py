"""Past National Latin Exams: the files, the bank, badge checks and Practice NLE."""

import os
import re
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schooltime  # noqa: E402,F401
import backup      # noqa: E402
import badges      # noqa: E402
import dataio      # noqa: E402
import nle         # noqa: E402
import practice    # noqa: E402
import store       # noqa: E402
import teacher     # noqa: E402

SPEC = dataio.load_spec()
EXAMS = nle.load()
ALL = [p for e in EXAMS for p in e["items"]]
LIVE = {p["id"] for p in ALL}
OCT29 = practice.taught_nodes(SPEC, "2026-10-29")


class TestTheFiles(unittest.TestCase):
    def test_every_exam_is_here_and_well_formed(self):
        self.assertEqual(len(EXAMS), 15)
        self.assertEqual(len(ALL), 592)
        self.assertEqual(len(LIVE), len(ALL))                     # ids unique
        self.assertEqual(nle.problems(EXAMS, SPEC), [])
        years = {e["year"] for e in EXAMS}
        self.assertTrue({2014, 2016, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026} <= years)
        for e in EXAMS:
            self.assertIn(len(e["items"]), (36, 40), e["id"])
            self.assertEqual([p["nle"]["n"] for p in e["items"]], list(range(1, len(e["items"]) + 1)))

    def test_every_question_has_four_options_and_a_topic(self):
        for p in ALL:
            self.assertEqual(sorted(p["options"]), ["a", "b", "c", "d"], p["id"])
            self.assertTrue(p["node"], p["id"])
            self.assertTrue(p["keep_order"])

    def test_a_few_answers_by_hand(self):
        get = {p["id"]: p for p in ALL}
        self.assertEqual(get["NLE-2014-latin1-12"]["answer"], "a")        # Mārcō: to Marcus
        self.assertEqual(get["NLE-2014-latin1-12"]["node"], "MS-057")
        self.assertEqual(get["NLE-2022-beginning-05"]["underline"], ["Siciliae"])
        self.assertEqual(get["NLE-2025-beginning-27"]["answer"], "b")     # aqueducts
        self.assertTrue(get["NLE-2025-beginning-27"]["exam_only"])        # needs its picture
        self.assertEqual(get["NLE-2019-latin1-35"]["passage"], "plague")

    def test_passages_have_their_lines(self):
        for e in EXAMS:
            for pid, pas in e["passages"].items():
                ns = [l["n"] for l in pas["lines"]]
                self.assertEqual(ns, list(range(ns[0], ns[-1] + 1)), (e["id"], pid))
                self.assertTrue(all(l["latin"].strip() for l in pas["lines"]), (e["id"], pid))
                qs = [p for p in e["items"] if p.get("passage") == pid]
                self.assertTrue(qs, (e["id"], pid))

    def test_words_a_student_reads(self):
        for f in os.listdir(nle.DIR):
            with open(os.path.join(nle.DIR, f), encoding="utf-8") as fh:
                text = fh.read().lower()
            self.assertNotIn("mastery", text)


class TestServing(unittest.TestCase):
    def test_label(self):
        e = next(e for e in EXAMS if e["id"] == "2019-latin1")
        self.assertEqual(e["items"][0]["nle"]["label"], "2019 National Latin Exam")

    def test_options_keep_their_printed_order(self):
        opts = {"a": "1", "b": "2", "c": "3", "d": "4"}
        self.assertEqual([k for _, k, _ in practice.display_options(opts, "s", keep_order=True)],
                         ["a", "b", "c", "d"])

    def test_underline_whole_words_only_and_escaped(self):
        self.assertEqual(nle.mark_up("Nōlīte intrāre in vīllam <b>", ["in"]),
                         "Nōlīte intrāre <u>in</u> vīllam &lt;b&gt;")
        self.assertEqual(nle.mark_up("neque A neque B", ["neque"]), "<u>neque</u> A <u>neque</u> B")

    def test_needs_hold_a_question_back(self):
        q = {"id": "x", "node": "MS-057", "needs": ["MS-064"]}
        self.assertFalse(practice.needs_met(q, OCT29))                     # third declension: Nov 3
        self.assertTrue(practice.needs_met(q, practice.taught_nodes(SPEC, "2026-11-04")))
        b = {"id": "dative", "nodes": ["MS-057"]}
        self.assertEqual(badges.pool(b, [q], OCT29), [])
        self.assertEqual(badges.pool(b, [q], practice.taught_nodes(SPEC, "2026-11-04")), [q])

    def test_covered(self):
        self.assertTrue(nle.covered({"node": "VOCAB"}, OCT29))
        self.assertTrue(nle.covered({"node": "MS-052"}, OCT29))
        self.assertFalse(nle.covered({"node": "MS-104"}, OCT29))           # perfect: January

    def test_mashup(self):
        a = nle.mashup(EXAMS, LIVE, OCT29, 20, "seed")
        self.assertEqual(len(a), 20)
        self.assertEqual(a, nle.mashup(EXAMS, LIVE, OCT29, 20, "seed"))   # same seed, same paper
        get = {p["id"]: p for p in ALL}
        self.assertTrue(all(nle.covered(get[i], OCT29) and not get[i].get("passage") for i in a))
        self.assertGreaterEqual(len({get[i]["nle"]["exam"] for i in a}), 4)   # a mix of years
        b = nle.mashup(EXAMS, LIVE, OCT29, 40, "seed")
        self.assertEqual(len(b), 40)
        self.assertTrue(get[b[-1]].get("passage"))                        # ends with the reading
        unseen = nle.mashup(EXAMS, LIVE, OCT29, 20, "seed", seen=set(a))
        self.assertFalse(set(a) & set(unseen))

    def test_awards(self):
        self.assertEqual(nle.score_award(37, 40)["name"], "Summa Cum Laude")
        self.assertEqual(nle.score_award(33, 40)["name"], "Maxima Cum Laude")
        self.assertEqual(nle.score_award(30, 40)["name"], "Magna Cum Laude")
        self.assertEqual(nle.score_award(27, 40)["name"], "Cum Laude")
        self.assertIsNone(nle.score_award(26, 40))
        self.assertIsNone(nle.score_award(20, 20))

    def test_look_back(self):
        self.assertEqual(nle.look_back({"stem": "According to lines 1-2, how many"}), (1, 2))
        self.assertEqual(nle.look_back({"stem": "In line 9, mihi is"}), (9, 9))
        self.assertIsNone(nle.look_back({"stem": "Who was Mars?"}))

    def test_not_homework(self):
        self.assertIn("nle", teacher.NOT_HOMEWORK)


class TestTheBank(unittest.TestCase):
    def setUp(self):
        self.db = store.connect(os.path.join(tempfile.mkdtemp(), "t.sqlite"))
        store.init_db(self.db)

    def status(self, iid):
        return self.db.execute("SELECT review_status FROM items WHERE item_id=?", (iid,)).fetchone()[0]

    def test_sync_pre_approves_once_and_keeps_the_teachers_decisions(self):
        got = nle.sync(self.db, EXAMS)
        self.assertEqual(got["inserted"], 592)
        self.assertEqual(self.status("NLE-2014-latin1-12"), "approved")
        self.assertEqual(nle.sync(self.db, EXAMS), {"inserted": 0, "updated": 0})   # nothing changed
        store.set_review(self.db, "NLE-2014-latin1-12", "rejected", reason="wrong key")
        edited = dict(store.get_item(self.db, "NLE-2014-latin1-13")["payload"], answer="d")
        store.set_review(self.db, "NLE-2014-latin1-13", "approved", new_payload=edited, edited=True)
        store.set_setting(self.db, nle.SETTING, "older")                          # a new deploy
        nle.sync(self.db, EXAMS)
        self.assertEqual(self.status("NLE-2014-latin1-12"), "rejected")
        self.assertEqual(store.get_item(self.db, "NLE-2014-latin1-13")["payload"]["answer"], "d")

    def test_passage_questions_stay_out_of_practice(self):
        nle.sync(self.db, EXAMS)
        served = {p["id"] for p in store.approved_items(self.db)}
        self.assertIn("NLE-2014-latin1-12", served)
        self.assertNotIn("NLE-2019-latin1-35", served)
        self.assertIn("NLE-2019-latin1-35",
                      {p["id"] for p in store.approved_items(self.db, include_exam_only=True)})

    def test_grammar_questions_join_the_badge_checks(self):
        nle.sync(self.db, EXAMS)
        _, bs = badges.load()
        gen = next(b for b in bs if b["id"] == "genitive")
        ids = [p["id"] for p in badges.pool(gen, store.approved_items(self.db), OCT29)]
        self.assertIn("NLE-2014-latin1-02", ids)                       # familiae nostrae
        self.assertNotIn("NLE-2021-beginning-06", ids)                 # senātōris: waits for 3rd decl.


class TestPracticeNLE(unittest.TestCase):
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
        for sid in ("403217", "403218"):
            store.add_student(self.db, sid, "Block 3")
        self.c = self.signin("403217")
        self.t = server.app.test_client()
        self.t.post("/login", data={"password": "teacherpw", "next": "/teacher"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def signin(self, sid):
        c = self.server.app.test_client()
        c.post("/signin", data={"step": "id", "student_id": sid, "next": "/"})
        c.post("/signin", data={"step": "pin", "student_id": sid, "pin": "1234", "pin2": "1234", "next": "/"})
        return c

    def start_exam(self, exam="2014-latin1", who=None):
        r = (who or self.c).post("/nle/start", data={"kind": "exam", "exam": exam})
        return r.headers["Location"].rsplit("/", 1)[-1]

    def test_the_home_page(self):
        page = self.c.get("/nle").data.decode()
        self.assertIn("Practice NLE", page)
        self.assertIn("Quick mash-up", page)
        self.assertIn("2026 Beginning Latin", page)
        self.assertIn(">NLE</a>", self.c.get("/").data.decode())             # the tab

    def test_sit_an_exam_and_see_the_score(self):
        sid = self.start_exam()
        page = self.c.get("/nle/s/%s?n=12" % sid).data.decode()
        self.assertIn("Question 12 of 40", page)
        self.assertIn("<u>Mārcō</u>", page)
        self.assertIn("A)</span>", page)
        # the reading: the passage comes with its question
        page = self.c.get("/nle/s/%s?n=31" % sid).data.decode()
        self.assertIn("CINCINNATUS", page)
        self.assertIn("Fuerat = He had been", page)
        # answer two: one right, one wrong
        self.c.post("/nle/s/%s/save" % sid, data={"item_id": "NLE-2014-latin1-12", "picked": "a", "pos": 12})
        self.c.post("/nle/s/%s/save" % sid, data={"item_id": "NLE-2014-latin1-02", "picked": "a", "pos": 2})
        self.assertIn("38 questions still blank", self.c.get("/nle/s/%s/finish" % sid).data.decode())
        r = self.c.post("/nle/s/%s/submit" % sid)
        self.assertIn("/results", r.headers["Location"])
        page = self.c.get("/nle/s/%s/results" % sid).data.decode()
        self.assertIn("1 <span>of 40</span>", page)
        self.assertIn("What to work on", page)
        self.assertIn("Genitive case", page)
        evs = [e for e in store.events_for_student(self.db, "403217") if e["context"] == "nle"]
        self.assertEqual(len(evs), 40)
        # finished: the questions can't be changed
        self.assertIn("/results", self.c.get("/nle/s/%s" % sid).headers["Location"])

    def test_starting_an_exam_under_way_carries_on(self):
        sid = self.start_exam()
        self.assertEqual(self.start_exam(), sid)
        page = self.c.get("/nle/s/%s?n=33" % sid).data.decode()
        self.assertIn('class="hi"', page)                                 # lines 2-4 lit up

    def test_only_the_student_who_started_it_can_open_it(self):
        sid = self.start_exam()
        other = self.signin("403218")
        self.assertEqual(other.get("/nle/s/%s" % sid).status_code, 404)
        self.assertEqual(other.post("/nle/s/%s/submit" % sid).status_code, 404)

    def test_a_mashup(self):
        r = self.c.post("/nle/start", data={"kind": "mashup", "size": "20"})
        sid = r.headers["Location"].rsplit("/", 1)[-1]
        self.assertIn("Question 1 of 20", self.c.get("/nle/s/%s" % sid).data.decode())
        self.assertIn("Carry on: Mash-up", self.c.get("/nle").data.decode())

    def test_a_miss_offers_the_lesson_and_the_lesson_leads_back(self):
        self.t.post("/teacher/lessons", data={"action": "approve_all"})
        sid = self.start_exam()
        self.c.post("/nle/s/%s/save" % sid, data={"item_id": "NLE-2014-latin1-02", "picked": "a", "pos": 2})
        self.c.post("/nle/s/%s/submit" % sid)
        page = self.c.get("/nle/s/%s/results" % sid).data.decode()
        m = re.search(r'href="(/badges/genitive/lesson\?back=[^"]+)"', page)
        self.assertIsNotNone(m)
        lesson = self.c.get(m.group(1).replace("&amp;", "&")).data.decode()
        self.assertIn("Back to your practice NLE", lesson)
        self.assertIn('href="/nle/s/%s/results' % sid, lesson)
        self.assertIn("Remember:", page)
        # only a practice NLE can be the way back
        lesson = self.c.get("/badges/genitive/lesson?back=https://evil.example/").data.decode()
        self.assertNotIn("evil.example", lesson)
        self.assertIn("Back to the map", lesson)

    def test_teacher_pages(self):
        page = self.t.get("/teacher/nle").data.decode()
        self.assertIn("592 questions from 15 past National Latin Exams", page)
        page = self.t.get("/teacher/nle/2014-latin1").data.decode()
        self.assertIn("CINCINNATUS", page)
        self.assertIn("✓", page)
        self.assertIn("/login", self.c.get("/teacher/nle").headers["Location"])

    def test_teacher_quiz_list_and_year_end(self):
        sid = self.start_exam()
        self.assertNotIn(sid, [q["quiz_id"] for q in store.list_quizzes(self.db)])
        self.assertIn(sid, [q["quiz_id"] for q in store.list_quizzes(self.db, include_nle=True)])
        removed = backup.purge_students(self.db)
        self.assertEqual(removed["practice_nles"], 1)
        self.assertIsNone(store.get_quiz(self.db, sid))

    def test_badge_question_says_where_it_came_from(self):
        self.t.post("/teacher/deadlines", data={"form": "badges",
                                                "badges_from": __import__("goals").week_key(time.time())})
        item = store.get_item(self.db, "NLE-2014-latin1-02")["payload"]
        with self.server.app.test_request_context():
            html = self.server.render_template(
                "practice_question.html", student="403217", item=item, node="MS-052",
                context="practice", notice=None, extra=False, label="Genitive", hint=None,
                introduced=None, nudge=None, stats=None, n_seen=0)
        self.assertIn("From the 2014 National Latin Exam", html)
        self.assertIn("<u>familiae nostrae</u>", html)


if __name__ == "__main__":
    unittest.main()
