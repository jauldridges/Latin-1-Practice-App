"""The Magister: what he says, and that he says only what the teacher approved."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import magister  # noqa: E402
import store     # noqa: E402

LINES = magister.load()


class TestTheScript(unittest.TestCase):
    def test_every_kind_of_line_is_there(self):
        cats = {l["category"] for l in LINES}
        self.assertEqual(cats, {c for c, _ in magister.CATEGORIES})
        self.assertGreaterEqual(len(LINES), 50)

    def test_ids_are_unique_and_lines_fit_a_bubble(self):
        self.assertEqual(len({l["id"] for l in LINES}), len(LINES))
        self.assertEqual([l["id"] for l in LINES if magister.problems(l)], [])

    def test_he_never_says_mastery(self):
        # The teacher's rule for anything a student reads.
        self.assertEqual([l["id"] for l in LINES if "master" in l["text"].lower()], [])

    def test_each_student_hears_every_line_before_a_repeat(self):
        seen = [magister.rotate(LINES, "403217", n)["id"] for n in range(len(LINES))]
        self.assertEqual(len(set(seen)), len(LINES))
        self.assertEqual(magister.rotate(LINES, "403217", len(LINES)), magister.rotate(LINES, "403217", 0))


class TestScreens(unittest.TestCase):
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

    def save(self, **data):
        return self.teacher.post("/teacher/magister/save", data=data)

    def test_nothing_is_said_until_the_teacher_approves(self):
        self.assertNotIn('class="magister', self.student.get("/").data.decode())

    def test_an_approved_line_appears_on_the_home_screen(self):
        self.save(action="approve", id="latin-04")
        body = self.student.get("/").data.decode()
        self.assertIn('class="magister "', body)
        self.assertIn("Lībertās means freedom", body)

    def test_a_different_line_on_each_visit(self):
        for lid in ("latin-04", "latin-06", "science-01"):
            self.save(action="approve", id=lid)
        said = set()
        for _ in range(3):
            body = self.student.get("/").data.decode()
            said.add(body.split('<div class="mg-name">Magister</div><p>')[1].split("</p>")[0])
        self.assertEqual(len(said), 3)

    def test_he_is_the_drawing(self):
        self.save(action="approve", id="latin-04")
        body = self.student.get("/").data.decode()
        self.assertIn("static/magister.png", body)
        r = self.student.get("/static/magister.png")
        self.assertEqual((r.status_code, r.data[:8]), (200, b"\x89PNG\r\n\x1a\n"))
        r.close()

    def test_slow_down_lines_never_show_on_the_home_screen(self):
        self.save(action="approve", id="slowdown-03")
        self.assertNotIn("Even Caesar", self.student.get("/").data.decode())

    def test_editing_saves_and_approves_and_rewording_needs_approval_again(self):
        self.save(action="edit", id="latin-04", text="Lībertās — your school's name — means freedom.")
        lines = {l["id"]: l for l in self.server.magister_lines(self.db)}
        self.assertEqual(lines["latin-04"]["state"], "approved")
        store.set_teaching_override(self.db, magister.key("latin-04"),
                                    {"category": "latin", "text": "Something else."})
        lines = {l["id"]: l for l in self.server.magister_lines(self.db)}
        self.assertEqual(lines["latin-04"]["state"], "edited")

    def test_the_teacher_can_add_and_delete_their_own_lines(self):
        self.save(action="add", category="rules", text="Quiz on Friday: practice the genitive!")
        mine = [l for l in self.server.magister_lines(self.db) if l["custom"]]
        self.assertEqual((len(mine), mine[0]["state"]), (1, "approved"))
        self.assertIn("Quiz on Friday", self.student.get("/").data.decode())
        self.save(action="delete", id=mine[0]["id"])
        self.assertEqual([l for l in self.server.magister_lines(self.db) if l["custom"]], [])

    def test_an_empty_line_is_refused(self):
        r = self.save(action="add", category="rules", text="  ")
        self.assertIn("error=", r.headers["Location"])

    def test_approve_all(self):
        self.save(action="approve_all")
        self.assertTrue(all(l["state"] == "approved" for l in self.server.magister_lines(self.db)))

    def test_a_student_cannot_reach_the_page(self):
        self.assertIn("/login", self.student.get("/teacher/magister").headers["Location"])
        self.assertIn("/login", self.student.post("/teacher/magister/save",
                                                  data={"action": "approve_all"}).headers["Location"])

    def test_the_teaching_text_page_is_unaffected(self):
        self.save(action="approve_all")
        self.assertNotIn("magister:", self.teacher.get("/teaching").data.decode())


if __name__ == "__main__":
    unittest.main()
