"""Student mode: the teacher uses the app exactly as a student does, and none
of it reaches the class's data."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import identity  # noqa: E402
import store     # noqa: E402

DEMO = store.DEMO_STUDENT


class TestStudentMode(unittest.TestCase):
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
        self.t = server.app.test_client()
        self.t.post("/login", data={"password": "teacherpw", "next": "/teacher"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def test_the_demo_id_can_never_be_a_real_student(self):
        self.assertFalse(identity.is_valid(DEMO))
        self.assertTrue(DEMO.isdigit())                     # so the name purge leaves it be

    def test_the_teacher_sees_what_a_student_sees(self):
        self.assertIn("Try it as a student", self.t.get("/").data.decode())
        r = self.t.post("/teacher/student-mode")
        self.assertEqual(r.headers["Location"], "/")
        home = self.t.get("/").data.decode()
        self.assertIn("Student mode.", home)
        self.assertIn("<h1>Salvē!</h1>", home)
        self.assertIn('<nav class="tabs">', home)
        self.assertNotIn("Teacher dashboard", home)
        self.assertIn("This week", home)
        self.assertEqual(self.t.get("/drill").status_code, 200)
        self.assertIn("Student mode.", self.t.get("/nle").data.decode())
        self.assertEqual(self.t.get("/teacher").status_code, 200)        # still the teacher

    def test_practice_in_student_mode_stays_out_of_class_data(self):
        self.t.post("/teacher/student-mode")
        store.record_event(self.db, DEMO, "vocab:aqua", None, "water", "right")
        store.record_event(self.db, "403217", "vocab:aqua", None, "water", "right")
        self.assertEqual({e["student_id"] for e in store.all_events(self.db)}, {"403217"})
        self.assertEqual(store.all_students(self.db), ["403217"])
        self.assertEqual(len(store.events_for_student(self.db, DEMO)), 1)   # but it is kept for the demo
        self.t.post("/teacher/student-mode/off")
        self.assertNotIn(DEMO, self.t.get("/teacher").data.decode())

    def test_back_to_teacher_view_and_start_over(self):
        self.t.post("/teacher/student-mode")
        store.record_event(self.db, DEMO, "vocab:aqua", None, "water", "right")
        r = self.t.post("/teacher/student-mode/reset")
        self.assertEqual(store.events_for_student(self.db, DEMO), [])
        self.assertEqual(r.headers["Location"], "/")
        r = self.t.post("/teacher/student-mode/off")
        self.assertIn("/teacher", r.headers["Location"])
        home = self.t.get("/").data.decode()
        self.assertNotIn("Student mode.", home)
        self.assertIn("Teacher dashboard", home)
        # the header's link does the same
        self.t.post("/teacher/student-mode")
        self.assertIn("/teacher", self.t.get("/signout").headers["Location"])
        self.assertNotIn("Student mode.", self.t.get("/").data.decode())

    def test_a_student_cannot_turn_it_on(self):
        c = self.server.app.test_client()
        c.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        c.post("/signin", data={"step": "pin", "student_id": "403217", "pin": "1234", "pin2": "1234", "next": "/"})
        self.assertIn("/login", c.post("/teacher/student-mode").headers["Location"])
        self.assertNotIn("Student mode.", c.get("/").data.decode())


if __name__ == "__main__":
    unittest.main()
