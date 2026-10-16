"""Data for analysis: the zip of spreadsheets, split around an exam."""

import csv
import io
import os
import sys
import tempfile
import time
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schooltime  # noqa: E402,F401  -- school time, before any clock is read
import drill       # noqa: E402
import store       # noqa: E402

A, B = "403217", "512648"


def at(day, hh, mm=0, ss=0):
    y, m, d = (int(x) for x in day.split("-"))
    return time.mktime((y, m, d, hh, mm, ss, 0, 0, -1))


class TestAnalysisExport(unittest.TestCase):
    def setUp(self):
        os.environ.pop("LATIN_PUBLIC", None)
        os.environ["LATIN_TEACHER_PASSWORD"] = "teacherpw"
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        db = store.connect(self.db_path)
        store.add_student(db, A, "Block 3")
        store.add_student(db, B, "Block 5")

        def ev(ts, latin, result, rating=None, latency=4000, grade=2000, rush=None, who=A):
            store.record_event(db, who, "vocab:%s:la_en" % drill._key(latin), None, "MY SECRET TYPING",
                               result, latency_ms=latency, timestamp=ts, rating=rating,
                               grade_ms=grade, rush=rush)

        # A: a sitting of three a week before (the third after 10 idle minutes),
        # a second sitting 40 minutes later, one card the day before, one on exam
        # day, one after. amō is on the exam (taught the week of 7 Sep); aqua is not.
        ev(at("2026-10-01", 19, 0, 0), "amō", "right", 3)
        ev(at("2026-10-01", 19, 0, 30), "laudō", "wrong", 1)
        ev(at("2026-10-01", 19, 10, 30), "aqua", "right", 4)
        ev(at("2026-10-01", 19, 50, 30), "aqua", "wrong", 3, rush="graded_up")
        ev(at("2026-10-08", 21, 0, 0), "amō", "right", 3)
        ev(at("2026-10-09", 7, 0, 0), "amō", "right", 3)
        ev(at("2026-10-12", 16, 0, 0), "aqua", "right", 3)
        self.exam = store.save_assessment(db, "Unit 1 Test", "test", "2026-10-09", ["2026-09-07"])
        self.teacher = server.app.test_client()
        self.teacher.post("/login", data={"password": "teacherpw", "next": "/teacher"})
        self.server = server

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def download(self, **args):
        r = self.teacher.get("/teacher/analysis.zip", query_string=args)
        self.assertEqual(r.status_code, 200, r.headers.get("Location"))
        z = zipfile.ZipFile(io.BytesIO(r.data))
        self.zip = z
        return {n: list(csv.DictReader(io.StringIO(z.read(n).decode())))
                for n in z.namelist() if n.endswith(".csv")}

    def test_the_page_offers_the_test_and_the_zip_has_every_file(self):
        page = self.teacher.get("/teacher/analysis").data.decode()
        self.assertIn("Unit 1 Test", page)
        self.assertIn("selected", page)
        files = self.download(exam=self.exam)
        self.assertEqual(set(self.zip.namelist()), {
            "README.txt", "students.csv", "sittings.csv", "skills_by_student.csv",
            "answers.csv", "in_app_quizzes.csv", "skill_list.csv"})
        self.assertIn("Unit 1 Test", self.zip.read("README.txt").decode())
        self.assertEqual(len(files["answers.csv"]), 7)

    def test_only_id_numbers_and_never_what_they_typed(self):
        self.download(exam=self.exam)
        for n in self.zip.namelist():
            self.assertNotIn("MY SECRET TYPING", self.zip.read(n).decode())
        self.assertEqual({r["student_id"] for r in self.download()["students.csv"]}, {A, B})

    def test_sittings_and_estimated_time(self):
        sits = [s for s in self.download(exam=self.exam)["sittings.csv"] if s["student_id"] == A]
        self.assertEqual([s["cards"] for s in sits], ["3", "1", "1", "1", "1"])
        first = sits[0]
        self.assertEqual(first["span_minutes"], "10.5")
        # 6 s for the first card (its own timing), 30 s, then 10 minutes capped at 5
        self.assertEqual(first["est_minutes"], round((6 + 30 + 300) / 60.0, 1).__str__())
        self.assertEqual((first["days_before_exam"], first["phase"]), ("8", "before"))
        self.assertEqual(first["rushed_cards"], "0")
        self.assertEqual(sits[1]["rushed_cards"], "1")

    def test_before_the_exam_and_after(self):
        row = [r for r in self.download(exam=self.exam)["students.csv"] if r["student_id"] == A][0]
        self.assertEqual(row["cards"], "7")
        self.assertEqual(row["cards_before_exam"], "5")
        self.assertEqual(row["sittings_before_exam"], "3")
        self.assertEqual(row["days_practiced_before_exam"], "2")
        self.assertEqual(row["cards_day_before_exam"], "1")
        self.assertEqual(row["cards_exam_day"], "1")
        self.assertEqual(row["cards_after_exam"], "1")
        self.assertEqual(row["cards_last_7_days_before_exam"], "1")
        self.assertEqual(row["accuracy_before_exam_pct"], "60")
        self.assertEqual(row["rushed_cards"], "1")
        self.assertEqual(row["wrong_but_graded_good_pct"], "50")
        # amō and laudō are exam material; aqua is not
        self.assertEqual(row["exam_material_cards_before_exam"], "3")
        self.assertEqual(row["exam_words_practiced"], "2")
        b = [r for r in self.download(exam=self.exam)["students.csv"] if r["student_id"] == B][0]
        self.assertEqual((b["cards"], b["sittings"], b["cards_before_exam"]), ("0", "0", "0"))

    def test_skills_are_marked_on_the_exam_or_not(self):
        files = self.download(exam=self.exam)
        skills = {r["skill_id"]: r for r in files["skills_by_student.csv"] if r["student_id"] == A}
        self.assertEqual((skills["amo"]["on_exam"], skills["aqua"]["on_exam"]), ("yes", "no"))
        self.assertEqual((skills["amo"]["cards"], skills["amo"]["cards_before_exam"]), ("3", "2"))
        self.assertIn("love", skills["amo"]["skill_name"])
        listed = {r["skill_id"]: r for r in files["skill_list.csv"]}
        self.assertEqual(listed["porto"]["on_exam"], "yes")       # on the exam, never practiced
        answers = files["answers.csv"]
        self.assertEqual([a["phase"] for a in answers if a["student_id"] == A],
                         ["before"] * 5 + ["exam day", "after"])
        self.assertEqual(answers[0]["self_grade"], "good")
        self.assertEqual(answers[0]["direction"], "la_en")

    def test_a_typed_date_splits_without_marking_scope(self):
        files = self.download(exam="", date="2026-10-02")
        row = [r for r in files["students.csv"] if r["student_id"] == A][0]
        self.assertEqual(row["cards_before_exam"], "4")
        self.assertEqual(row["exam_topics"], "")
        self.assertEqual({r["on_exam"] for r in files["skill_list.csv"]}, {""})

    def test_no_exam_at_all(self):
        files = self.download(exam="")
        self.assertEqual({a["phase"] for a in files["answers.csv"]}, {""})

    def test_a_bad_date_is_sent_back(self):
        r = self.teacher.get("/teacher/analysis.zip", query_string={"exam": "", "date": "Oct 9"})
        self.assertIn("bad=date", r.headers["Location"])

    def test_one_block(self):
        files = self.download(exam=self.exam, section="Block 5")
        self.assertEqual([r["student_id"] for r in files["students.csv"]], [B])
        self.assertEqual(files["answers.csv"], [])

    def test_a_student_gets_nothing(self):
        student = self.server.app.test_client()
        r = student.get("/teacher/analysis.zip")
        self.assertIn("/login", r.headers["Location"])


if __name__ == "__main__":
    unittest.main()
