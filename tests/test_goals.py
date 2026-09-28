"""The homework week, the spacing reminder, and quizzes and tests students prepare for."""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import checks  # noqa: E402
import dataio  # noqa: E402
import goals   # noqa: E402
import store   # noqa: E402


def at(day, hour=15):
    """A timestamp on a September/October 2026 day. 28 Sep 2026 is a Monday."""
    month = 9 if day <= 30 else 10
    d = day if day <= 30 else day - 30
    return time.mktime(time.strptime("2026-%02d-%02d %02d:00" % (month, d, hour), "%Y-%m-%d %H:%M"))


def ev(day, item_id, result="right", context="practice", node=None, hour=15):
    return {"timestamp": at(day, hour), "item_id": item_id, "result": result,
            "context": context, "spec_node_id": node}


WED = at(30)


class TestTheWeek(unittest.TestCase):
    """Homework runs Saturday to Friday: the quiz is Friday, so the cards are due then."""

    def test_the_clock_is_the_schools(self):
        # Render runs in UTC, where Friday ends at 8pm in Massachusetts.
        self.assertEqual(os.environ.get("TZ"), os.environ.get("LATIN_TIMEZONE") or "America/New_York")

    def test_a_week_starts_on_saturday(self):
        self.assertEqual(time.strftime("%a %d", time.localtime(goals.week_start(WED))), "Sat 26")

    def test_friday_night_is_still_this_week(self):
        friday = at(32, 23)   # Fri 2 Oct, 11pm
        self.assertEqual(goals.week_key(friday), "2026-09-26")

    def test_saturday_starts_the_next_one(self):
        self.assertEqual(goals.week_key(at(33, 0)), "2026-10-03")

    def test_the_deadline_is_midnight_at_the_end_of_friday(self):
        end = goals.week_end(goals.week_start(WED))
        self.assertEqual(time.strftime("%a %d %H:%M", time.localtime(end)), "Sat 03 00:00")

    def test_daylight_saving_does_not_move_midnight(self):
        # Clocks go back on Sun 1 Nov 2026; a week is not 7 x 86400 seconds then.
        start = goals.key_start("2026-11-04")
        self.assertEqual(time.strftime("%a %d %b %H:%M", time.localtime(start)), "Sat 31 Oct 00:00")
        self.assertEqual(time.strftime("%a %d %b %H:%M", time.localtime(goals.week_end(start))),
                         "Sat 07 Nov 00:00")

    def test_labels(self):
        self.assertEqual(goals.week_label("2026-09-30"), "Sat 26 Sep – Fri 2 Oct")


class TestWeeklyProgress(unittest.TestCase):
    def test_vocab_and_grammar_are_counted_separately(self):
        p = goals.weekly_progress([ev(28, "vocab:aqua:la_en"), ev(28, "MS014-RECOG-01"),
                                   ev(29, "MS015-RECOG-01")], {"vocab": 50, "grammar": 50}, WED)
        self.assertEqual((p["vocab"], p["grammar"]), (1, 2))

    def test_a_retype_after_a_close_counts_once(self):
        # The same rule the stats bar uses, so the two numbers cannot drift.
        p = goals.weekly_progress([ev(28, "vocab:aqua:la_en", "close"),
                                   ev(28, "vocab:aqua:la_en", "right")], None, WED)
        self.assertEqual(p["vocab"], 1)

    def test_a_proctored_quiz_does_not_fill_the_homework_goal(self):
        p = goals.weekly_progress([ev(29, "MS014-RECOG-01", context="quiz"),
                                   ev(29, "MS014-RECOG-02", context="exam")], None, WED)
        self.assertEqual(p["grammar"], 0)

    def test_homework_and_classwork_count(self):
        p = goals.weekly_progress([ev(29, "MS014-RECOG-01", context="homework"),
                                   ev(29, "MS014-RECOG-02", context="classwork")], None, WED)
        self.assertEqual(p["grammar"], 2)

    def test_last_friday_does_not_count_and_saturday_does(self):
        self.assertEqual(goals.weekly_progress([ev(25, "vocab:aqua:la_en")], None, WED)["vocab"], 0)
        self.assertEqual(goals.weekly_progress([ev(26, "vocab:aqua:la_en")], None, WED)["vocab"], 1)

    def test_the_days_show_where_the_practice_fell(self):
        # Saturday first: S S M T W T F.
        p = goals.weekly_progress([ev(28, "vocab:aqua:la_en"), ev(30, "MS014-RECOG-01")], None, WED)
        self.assertEqual(p["days"], [False, False, True, False, True, False, False])
        self.assertEqual(p["today"], 4)
        self.assertEqual(goals.DAY_LETTERS, ["S", "S", "M", "T", "W", "T", "F"])

    def test_it_says_when_it_is_due(self):
        self.assertEqual(goals.weekly_progress([], None, WED)["due"], "due Friday")
        self.assertEqual(goals.weekly_progress([], None, at(32, 9))["due"], "due today")

    def test_meeting_the_goal(self):
        evs = [ev(28, "vocab:w%d:la_en" % i) for i in range(3)]
        p = goals.weekly_progress(evs, {"vocab": 3, "grammar": 5}, WED)
        self.assertTrue(p["met"]["vocab"])
        self.assertFalse(p["met"]["grammar"])
        self.assertFalse(p["done"])
        p = goals.weekly_progress(evs, {"vocab": 3, "grammar": 0}, WED)
        self.assertTrue(p["done"])

    def test_default_targets_are_the_teachers_fifty_and_fifty(self):
        self.assertEqual(goals.DEFAULT_TARGETS, {"vocab": 50, "grammar": 50})


SMALL = {"vocab": 2, "grammar": 1}     # a three-card week keeps these readable
WEEKS = ["2026-09-12", "2026-09-19", "2026-09-26"]
NOW = at(30, 20)                      # Wednesday evening of the third week


def vocab(day, n, hour=15, tag="w"):
    return [ev(day, "vocab:%s%d%d:la_en" % (tag, day, i), hour=hour) for i in range(n)]


def gram(day, n, hour=15, tag="q"):
    return [ev(day, "%s%d-%d" % (tag, day, i), hour=hour) for i in range(n)]


def hist(events, weeks=WEEKS, targets=SMALL, now=NOW):
    return {r["key"]: r for r in goals.homework_history(events, targets, weeks, now)}


class TestHomeworkHistory(unittest.TestCase):
    """On time by Friday is green; finished afterwards is yellow; never is red."""

    def test_done_by_friday_is_on_time(self):
        h = hist(vocab(14, 2) + gram(18, 1, hour=23))        # the last card at 11pm Friday
        self.assertEqual(h["2026-09-12"]["status"], "on time")

    def test_nothing_is_not_done_and_the_open_week_is_this_week(self):
        h = hist([])
        self.assertEqual(h["2026-09-19"]["status"], "not done")
        self.assertEqual(h["2026-09-26"]["status"], "this week")

    def test_a_missed_week_can_be_finished_late(self):
        evs = vocab(21, 1)                                    # week 2: one card of three
        evs += vocab(28, 2) + gram(28, 1)                     # week 3: its own homework...
        evs += vocab(29, 1, tag="x") + gram(29, 1, tag="x")   # ...and then extra
        h = hist(evs, weeks=WEEKS[1:])
        self.assertEqual(h["2026-09-26"]["status"], "on time")
        late = h["2026-09-19"]
        self.assertEqual(late["status"], "late")
        self.assertEqual(late["late"], {"vocab": 1, "grammar": 1})
        self.assertEqual(time.strftime("%d", time.localtime(late["done_at"])), "29")

    def test_this_weeks_homework_is_never_pulled_back_to_cover_an_old_week(self):
        # Doing exactly each week's homework keeps each week on time; the missed
        # week stays missed until extra is done. The other way round, one missed
        # week would make every week after it late, forever.
        h = hist(vocab(28, 2) + gram(28, 1))
        self.assertEqual(h["2026-09-26"]["status"], "on time")
        self.assertEqual(h["2026-09-19"]["status"], "not done")
        self.assertEqual(h["2026-09-19"]["total"], 0)

    def test_extra_goes_to_the_oldest_unfinished_week_first(self):
        h = hist(vocab(28, 2) + gram(28, 1) + vocab(29, 2, tag="x") + gram(29, 1, tag="x"))
        self.assertEqual(h["2026-09-12"]["status"], "late")
        self.assertEqual(h["2026-09-19"]["status"], "not done")

    def test_extra_vocabulary_does_not_pay_for_missing_grammar(self):
        h = hist(vocab(14, 2) + vocab(28, 2) + gram(28, 1) + vocab(29, 5, tag="x"))
        self.assertEqual(h["2026-09-12"]["status"], "not done")
        self.assertEqual(h["2026-09-12"]["counts"], {"vocab": 2, "grammar": 0})

    def test_a_week_before_friday_can_still_be_on_time(self):
        h = hist(vocab(30, 2) + gram(30, 1))
        self.assertEqual(h["2026-09-26"]["status"], "on time")

    def test_a_vacation_week_is_not_owed(self):
        weeks = goals.homework_weeks("2026-09-12", off=["2026-09-19"], now=NOW)
        self.assertEqual(weeks, ["2026-09-12", "2026-09-26"])
        # and cards done during it finish an earlier week
        h = hist(vocab(21, 2) + gram(21, 1), weeks=weeks)
        self.assertEqual(h["2026-09-12"]["status"], "late")
        self.assertNotIn("2026-09-19", h)

    def test_nothing_before_the_first_week_counts(self):
        h = hist(vocab(7, 2) + gram(7, 1), weeks=["2026-09-12"])
        self.assertEqual(h["2026-09-12"]["total"], 0)

    def test_a_quiz_is_not_homework(self):
        h = hist(vocab(14, 2) + [ev(15, "q1", context="quiz")])
        self.assertEqual(h["2026-09-12"]["status"], "not done")

    def test_any_date_names_its_week(self):
        self.assertEqual(goals.homework_weeks("2026-09-30", now=NOW), ["2026-09-26"])

    def test_all_time(self):
        evs = vocab(14, 2) + gram(18, 1) + vocab(28, 1) + [ev(29, "q1", context="quiz")]
        history = goals.homework_history(evs, SMALL, WEEKS, NOW)
        t = goals.all_time(evs, history)
        self.assertEqual((t["cards"], t["vocab"], t["grammar"], t["days"]), (4, 3, 1, 3))
        self.assertEqual((t["on_time"], t["late"], t["not_done"]), (1, 0, 1))


class TestSpacingFlag(unittest.TestCase):
    def test_never_practiced(self):
        self.assertEqual(goals.spacing_flag([], WED), "never")

    def test_two_days_off_is_fine(self):
        self.assertIsNone(goals.spacing_flag([ev(28, "vocab:aqua:la_en")], WED))

    def test_more_than_two_days_raises_it(self):
        self.assertEqual(goals.spacing_flag([ev(27, "vocab:aqua:la_en")], WED), "idle")
        self.assertEqual(goals.days_since_practice([ev(27, "vocab:aqua:la_en")], WED), 3)

    def test_a_quiz_is_not_practice(self):
        # Sitting a quiz yesterday does not mean you practiced.
        self.assertEqual(goals.spacing_flag([ev(29, "MS014-RECOG-01", context="quiz")], WED), "never")

    def test_calendar_days_not_hours(self):
        # 11pm Monday to 9am Wednesday is two days, however few hours it is.
        self.assertEqual(goals.days_since_practice([ev(28, "x", hour=23)], at(30, 9)), 2)


class TestWhenLabel(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(goals.when_label("2026-09-30", WED), "today")
        self.assertEqual(goals.when_label("2026-10-01", WED), "tomorrow")
        self.assertEqual(goals.when_label("2026-10-02", WED), "in 2 days")
        self.assertEqual(goals.when_label("2026-10-30", WED), "Fri 30 Oct")
        self.assertEqual(goals.when_label("2026-09-01", WED), "finished")


class TestScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = dataio.load_spec()
        cls.words = [{"latin": "aqua", "en": ["water"], "week": "week_of_aug_31"},
                     {"latin": "dominus", "en": ["master"], "week": "week_of_sep_14"}]

    def test_weeks_bring_their_topics_and_words(self):
        a = {"weeks": ["2026-09-14"], "excluded_nodes": []}
        practiceable = {"MS-023", "MS-024", "MS-015"}
        nodes, words = goals.scope(a, self.spec, self.words, practiceable)
        self.assertIn("MS-023", nodes)
        self.assertNotIn("MS-015", nodes)            # taught in a different week
        self.assertEqual([w["latin"] for w in words], ["dominus"])

    def test_unticked_topics_are_left_out(self):
        a = {"weeks": ["2026-09-14"], "excluded_nodes": ["MS-024"]}
        nodes, _ = goals.scope(a, self.spec, self.words, {"MS-023", "MS-024"})
        self.assertEqual(nodes, ["MS-023"])

    def test_nothing_is_offered_that_cannot_be_practiced(self):
        a = {"weeks": ["2026-09-14"], "excluded_nodes": []}
        nodes, _ = goals.scope(a, self.spec, self.words, set())
        self.assertEqual(nodes, [])


class TestReadiness(unittest.TestCase):
    def test_right_last_time_follows_the_most_recent_try(self):
        spec = dataio.load_spec()
        events = [ev(28, "MS014-RECOG-01", "wrong", node="MS-014"),
                  ev(29, "MS014-RECOG-02", "right", node="MS-014"),
                  ev(29, "MS015-RECOG-01", "right", node="MS-015"),
                  ev(30, "MS015-RECOG-01", "wrong", node="MS-015")]
        r = goals.readiness(["MS-014", "MS-015", "MS-018"], [], events, spec, now=WED)
        by = {row["node"]: row for row in r["topics"]}
        self.assertTrue(by["MS-014"]["right_last"])
        self.assertFalse(by["MS-015"]["right_last"])
        self.assertFalse(by["MS-018"]["tried"])
        self.assertEqual(r["topic_totals"]["right_last"], 1)
        self.assertEqual(r["topic_totals"]["total"], 3)

    def test_solid_shaky_not_yet_are_unchanged(self):
        # Right three times in three days is still shaky: solid needs a week.
        spec = dataio.load_spec()
        events = [ev(d, "MS014-RECOG-01", node="MS-014") for d in (28, 29, 30)]
        r = goals.readiness(["MS-014"], [], events, spec, now=WED)
        self.assertEqual(r["topics"][0]["state"], "shaky")
        self.assertTrue(r["topics"][0]["right_last"])


class _App(unittest.TestCase):
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
        self.items = dataio.load_bank()
        flags, _ = checks.run_all(self.items, set(dataio.load_spec()),
                                  dataio.allowed_latin(dataio.load_exemplars()))
        store.import_items(self.db, self.items, flags, "t")
        for it in self.items:
            if it.get("format") == "choice" and it.get("options"):
                store.set_review(self.db, it["id"], "approved")
        store.add_student(self.db, "403217", "Block 3")
        self.teacher = server.app.test_client()
        self.teacher.post("/login", data={"password": "teacherpw", "next": "/teacher"})
        self.student = server.app.test_client()
        self.student.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.student.post("/signin", data={"step": "pin", "student_id": "403217",
                                           "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def add_quiz(self, weeks, due=None, title="Quiz: nominative and accusative"):
        due = due or time.strftime("%Y-%m-%d", time.localtime(time.time() + 4 * 86400))
        r = self.teacher.post("/teacher/deadlines/edit", data={
            "title": title, "kind": "quiz", "due_date": due, "week": weeks})
        self.assertEqual(r.status_code, 302)
        return r.headers["Location"].split("id=")[1].split("&")[0]


class TestTeacherScreens(_App):
    def test_a_student_cannot_reach_them(self):
        for url in ("/teacher/deadlines", "/teacher/deadlines/edit"):
            r = self.student.get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn("/login", r.headers["Location"])

    def test_setting_the_goal(self):
        self.teacher.post("/teacher/deadlines", data={"vocab": "40", "grammar": "60"})
        self.assertEqual(store.get_setting(self.db, "weekly_goal"), {"vocab": 40, "grammar": 60})
        self.assertIn("of 60", self.student.get("/").data.decode())

    def test_a_bad_goal_is_refused(self):
        body = self.teacher.post("/teacher/deadlines", data={"vocab": "lots", "grammar": "5"}).data.decode()
        self.assertIn("not saved", body)
        self.assertIsNone(store.get_setting(self.db, "weekly_goal"))

    def test_a_new_week_brings_grammar_and_leaves_other_strands_unticked(self):
        # Two weeks of class is ~50 topics across every strand; a quiz on the
        # nominative is not testing the Norman Conquest.
        aid = self.add_quiz(["2026-09-07", "2026-09-14"])
        a = store.get_assessment(self.db, aid)
        self.assertTrue(a["excluded_nodes"])
        self.assertTrue(all(not n.startswith("MS-") for n in a["excluded_nodes"]))
        page = self.student.get("/due/%s" % aid).data.decode()
        self.assertIn("Nominative case", page)
        self.assertNotIn("The insula", page)          # Roman world, taught that week
        self.assertNotIn("Norman Conquest", page)     # modern world, taught that week

    def test_ticking_a_topic_in_or_out_sticks(self):
        aid = self.add_quiz(["2026-09-07"])
        self.teacher.post("/teacher/deadlines/edit", data={
            "id": aid, "title": "Quiz", "kind": "quiz",
            "due_date": store.get_assessment(self.db, aid)["due_date"],
            "week": ["2026-09-07"], "topics_shown": "1",
            "listed": ["MS-014", "MS-015", "CR-002"], "node": ["MS-015", "CR-002"]})
        a = store.get_assessment(self.db, aid)
        self.assertIn("MS-014", a["excluded_nodes"])
        self.assertNotIn("CR-002", a["excluded_nodes"])
        self.assertNotIn("MS-015", a["excluded_nodes"])

    def test_it_insists_on_a_title_a_date_and_a_week(self):
        for data in ({"title": "", "due_date": "2026-10-02", "week": ["2026-09-07"]},
                     {"title": "Q", "due_date": "", "week": ["2026-09-07"]},
                     {"title": "Q", "due_date": "2026-10-02"}):
            data["kind"] = "quiz"
            body = self.teacher.post("/teacher/deadlines/edit", data=data).data.decode()
            self.assertIn("not saved", body)
        self.assertEqual(store.list_assessments(self.db), [])

    def test_delete(self):
        aid = self.add_quiz(["2026-09-07"])
        self.teacher.post("/teacher/deadlines/edit", data={"id": aid, "action": "delete"})
        self.assertIsNone(store.get_assessment(self.db, aid))


class TestHomeworkScreens(_App):
    def practice(self, n_vocab, n_gram, ts=None):
        ts = ts or time.time()
        for i in range(n_vocab):
            store.record_event(self.db, "403217", "vocab:w%d:la_en" % i, None, "x", "right",
                               timestamp=ts - 1000 + i)
        for i in range(n_gram):
            store.record_event(self.db, "403217", "MS014-X-%d" % i, "MS-014", "x", "right",
                               timestamp=ts - 500 + i)

    def test_the_student_sees_their_weeks_and_all_time(self):
        self.practice(3, 2)
        body = self.student.get("/homework").data.decode()
        self.assertIn("5<span> cards all time", body)
        self.assertIn("This week", body)
        self.assertIn("Saturday to Friday", body)
        self.assertNotIn("mastery", body.lower())

    def test_it_needs_a_signed_in_student(self):
        r = self.server.app.test_client().get("/homework")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/signin", r.headers["Location"])

    def test_a_student_cannot_reach_the_gradebook(self):
        for url in ("/teacher/homework", "/teacher/homework.csv"):
            r = self.student.get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn("/login", r.headers["Location"])

    def test_the_teacher_grid_and_its_spreadsheet(self):
        self.practice(50, 50)
        body = self.teacher.get("/teacher/homework").data.decode()
        self.assertIn("403217", body)
        csv_text = self.teacher.get("/teacher/homework.csv").data.decode()
        self.assertTrue(csv_text.startswith("student_id,block,Sat "))
        self.assertIn("403217,Block 3,on time", csv_text)

    def test_did_it_means_the_weekly_goal(self):
        self.practice(49, 50)
        body = self.teacher.get("/teacher").data.decode()
        self.assertIn("This homework week (Sat–Fri)", body)
        self.assertIn('<span class="pill shaky">started</span>', body)
        self.practice(50, 50)
        self.assertIn('<span class="pill solid">done</span>', self.teacher.get("/teacher").data.decode())

    def test_setting_the_homework_weeks(self):
        self.teacher.post("/teacher/deadlines", data={
            "form": "homework", "from": "2026-09-16",
            "listed": ["2026-09-12", "2026-09-19"], "on": ["2026-09-12"]})
        self.assertEqual(store.get_setting(self.db, "homework"),
                         {"from": "2026-09-12", "off": ["2026-09-19"]})
        page = self.teacher.get("/teacher/deadlines").data.decode()
        self.assertIn("Sat 12 Sep – Fri 18 Sep", page)

    def test_the_home_screen_says_what_is_owed(self):
        self.teacher.post("/teacher/deadlines", data={
            "form": "homework", "from": time.strftime("%Y-%m-%d", time.localtime(time.time() - 14 * 86400))})
        body = self.student.get("/").data.decode()
        self.assertIn("This week's homework", body)
        self.assertIn("isn't finished: 0 of 100 cards", body)


class TestWhatAStudentSees(_App):
    def test_home_shows_the_goal_and_whats_coming(self):
        self.add_quiz(["2026-09-07"])
        body = self.student.get("/").data.decode()
        self.assertIn("This week", body)
        self.assertIn("0 of 50", body)
        self.assertIn("Coming up", body)
        self.assertIn("Quiz: nominative and accusative", body)
        self.assertIn("in 4 days", body)

    def test_a_finished_quiz_drops_off_the_home_screen(self):
        self.add_quiz(["2026-09-07"], due="2026-01-05", title="Old quiz")
        self.assertNotIn("Old quiz", self.student.get("/").data.decode())

    def test_a_new_student_is_nudged_to_start(self):
        self.assertIn("You haven't practiced yet", self.student.get("/").data.decode())

    def test_the_quiz_page(self):
        aid = self.add_quiz(["2026-09-07"])
        body = self.student.get("/due/%s" % aid).data.decode()
        self.assertIn("right on your last try", body)
        self.assertIn("Practice these topics", body)
        self.assertIn("Practice these words", body)
        self.assertNotIn("mastery", body.lower())

    def test_an_unknown_quiz_is_a_404(self):
        self.assertEqual(self.student.get("/due/nope").status_code, 404)

    def test_the_teacher_does_not_get_the_student_home(self):
        self.assertNotIn('class="goalcard"', self.teacher.get("/").data.decode())


class TestPracticingForAQuiz(_App):
    def test_topic_practice_stays_inside_the_quiz(self):
        topics = ["MS-014", "MS-015"]
        seen = set()
        for _ in range(6):
            body = self.student.get("/practice/session?node=" + ",".join(topics) + ",").data.decode()
            if 'name="item_id"' not in body:
                break
            iid = body.split('name="item_id" value="')[1].split('"')[0]
            item = {i["id"]: i for i in self.items}[iid]
            seen.add(item["node"])
            self.student.post("/practice/answer", data={
                "item_id": iid, "picked": item["answer"], "node": ",".join(topics) + ",",
                "context": "practice"})
        self.assertTrue(seen)
        self.assertTrue(seen <= set(topics), seen)

    def test_it_still_never_serves_ahead_of_the_lesson(self):
        # MS-052 is taught in October; asking for it by name must not bypass that.
        body = self.student.get("/practice/session?node=MS-052,").data.decode()
        self.assertNotIn('name="item_id"', body)

    def test_word_practice_stays_inside_the_quiz_weeks(self):
        import drill
        weeks = "week_of_aug_31,week_of_sep_14,"
        pool = drill._scope_words(self.server._DRILL_WORDS, weeks)
        self.assertEqual({w["week"] for w in pool}, {"week_of_aug_31", "week_of_sep_14"})
        allowed = {drill._key(w["latin"]) for w in pool}
        for _ in range(5):
            body = self.student.get("/drill/session?week=" + weeks + "&direction=la_en").data.decode()
            latin = body.split('name="latin" value="')[1].split('"')[0]
            self.assertIn(drill._key(latin), allowed)
            self.student.post("/drill/answer", data={
                "week": weeks, "direction": "la_en", "latin": latin, "ask": "la_en",
                "response": "zzz", "latency_ms": "1000"})
            self.assertIn('value="%s"' % weeks, self.student.get(
                "/drill/session?week=" + weeks + "&direction=la_en").data.decode())


class TestAmericanSpelling(unittest.TestCase):
    def test_practice_is_spelled_the_american_way(self):
        # The teacher's rule: "practice" for noun and verb, never the British -ise form.
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bad = []
        for folder, _, files in os.walk(root):
            if any(part in folder for part in (".git", "__pycache__", "data", "out")):
                continue
            for f in files:
                if f.endswith((".py", ".html", ".md", ".yaml", ".css")):
                    text = open(os.path.join(folder, f), encoding="utf-8").read()
                    if ("practi" + "s") in text.lower():
                        bad.append(f)
        self.assertEqual(bad, [])


class TestItTravels(unittest.TestCase):
    def test_backup_and_migration_carry_the_new_tables(self):
        import backup, migrate
        for t in ("settings", "assessments"):
            self.assertIn(t, backup.TABLES)
            self.assertIn(t, migrate.TABLES)
        self.assertNotIn("assessments", backup.STUDENT_TABLES)   # the year-end purge keeps them


if __name__ == "__main__":
    unittest.main()
