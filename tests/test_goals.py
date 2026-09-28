"""The weekly goal, the spacing reminder, and quizzes and tests students prepare for."""

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
    def test_a_week_starts_on_monday(self):
        self.assertEqual(time.strftime("%a %d", time.localtime(goals.week_start(WED))), "Mon 28")

    def test_sunday_night_is_still_this_week(self):
        sunday = at(34, 22)   # Sun 4 Oct, 10pm
        self.assertEqual(time.strftime("%d", time.localtime(goals.week_start(sunday))), "28")


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

    def test_last_week_does_not_count(self):
        p = goals.weekly_progress([ev(27, "vocab:aqua:la_en")], None, WED)   # Sunday before
        self.assertEqual(p["vocab"], 0)

    def test_the_days_show_where_the_practice_fell(self):
        p = goals.weekly_progress([ev(28, "vocab:aqua:la_en"), ev(30, "MS014-RECOG-01")], None, WED)
        self.assertEqual(p["days"], [True, False, True, False, False, False, False])
        self.assertEqual(p["today"], 2)

    def test_meeting_the_goal(self):
        evs = [ev(28, "vocab:w%d:la_en" % i) for i in range(3)]
        p = goals.weekly_progress(evs, {"vocab": 3, "grammar": 5}, WED)
        self.assertTrue(p["met"]["vocab"])
        self.assertFalse(p["met"]["grammar"])

    def test_default_targets_are_the_teachers_fifty_and_fifty(self):
        self.assertEqual(goals.DEFAULT_TARGETS, {"vocab": 50, "grammar": 50})


class TestSpacingFlag(unittest.TestCase):
    def test_never_practised(self):
        self.assertEqual(goals.spacing_flag([], WED), "never")

    def test_two_days_off_is_fine(self):
        self.assertIsNone(goals.spacing_flag([ev(28, "vocab:aqua:la_en")], WED))

    def test_more_than_two_days_raises_it(self):
        self.assertEqual(goals.spacing_flag([ev(27, "vocab:aqua:la_en")], WED), "idle")
        self.assertEqual(goals.days_since_practice([ev(27, "vocab:aqua:la_en")], WED), 3)

    def test_a_quiz_is_not_practice(self):
        # Sitting a quiz yesterday does not mean you practised.
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

    def test_nothing_is_offered_that_cannot_be_practised(self):
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
        self.assertIn("You haven't practised yet", self.student.get("/").data.decode())

    def test_the_quiz_page(self):
        aid = self.add_quiz(["2026-09-07"])
        body = self.student.get("/due/%s" % aid).data.decode()
        self.assertIn("right on your last try", body)
        self.assertIn("Practise these topics", body)
        self.assertIn("Practise these words", body)
        self.assertNotIn("mastery", body.lower())

    def test_an_unknown_quiz_is_a_404(self):
        self.assertEqual(self.student.get("/due/nope").status_code, 404)

    def test_the_teacher_does_not_get_the_student_home(self):
        self.assertNotIn('class="goalcard"', self.teacher.get("/").data.decode())


class TestPractisingForAQuiz(_App):
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


class TestItTravels(unittest.TestCase):
    def test_backup_and_migration_carry_the_new_tables(self):
        import backup, migrate
        for t in ("settings", "assessments"):
            self.assertIn(t, backup.TABLES)
            self.assertIn(t, migrate.TABLES)
        self.assertNotIn("assessments", backup.STUDENT_TABLES)   # the year-end purge keeps them


if __name__ == "__main__":
    unittest.main()
