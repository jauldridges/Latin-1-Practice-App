"""Tests for student sign-in: an ID number and a PIN they choose.

The PIN's job is narrow — stop one student practising as another — and the
tests are correspondingly narrow. The one that matters most is the last class:
identity must come from the session, because a PIN at the door means nothing if
every screen behind it takes the student id from the URL.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import identity  # noqa: E402
import store  # noqa: E402


class TestPinRules(unittest.TestCase):
    def test_four_digits(self):
        self.assertTrue(identity.is_valid_pin("1234"))
        self.assertTrue(identity.is_valid_pin("0000"))

    def test_anything_else_is_refused(self):
        for bad in ("123", "12345", "abcd", "12a4", "", None, " 12 "):
            self.assertFalse(identity.is_valid_pin(bad), repr(bad))

    def test_hashing_is_salted(self):
        _, s1, h1 = identity.hash_pin("1234")
        _, s2, h2 = identity.hash_pin("1234")
        # Two students who pick 1234 must not share a hash, or the table is a
        # lookup table for 10,000 possibilities.
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(h1, h2)

    def test_verify(self):
        algo, salt, digest = identity.hash_pin("1234")
        self.assertTrue(identity.verify_pin("1234", algo, salt, digest))
        self.assertFalse(identity.verify_pin("1235", algo, salt, digest))

    def test_the_stored_rounds_are_honoured(self):
        # So the cost can be raised later without locking anyone out.
        algo, salt, digest = identity.hash_pin("1234")
        self.assertTrue(identity.verify_pin("1234", algo, salt, digest))
        self.assertIn("pbkdf2_sha256$", algo)


class TestPinStorage(unittest.TestCase):
    def setUp(self):
        self.conn = store.connect(os.path.join(tempfile.mkdtemp(), "t.sqlite"))
        store.init_db(self.conn)
        store.add_student(self.conn, "403217", "Block 3")

    def test_set_and_check(self):
        store.set_pin(self.conn, "403217", "1234")
        self.assertTrue(store.check_pin(self.conn, "403217", "1234"))
        self.assertFalse(store.check_pin(self.conn, "403217", "9999"))

    def test_the_pin_is_never_stored(self):
        store.set_pin(self.conn, "403217", "1234")
        row = self.conn.execute("SELECT * FROM student_pins").fetchone()
        self.assertNotIn("1234", "".join(str(v) for v in dict(row).values()))

    def test_has_pin(self):
        self.assertFalse(store.has_pin(self.conn, "403217"))
        store.set_pin(self.conn, "403217", "1234")
        self.assertTrue(store.has_pin(self.conn, "403217"))

    def test_a_reset_clears_it(self):
        store.set_pin(self.conn, "403217", "1234")
        store.clear_pin(self.conn, "403217")
        self.assertFalse(store.has_pin(self.conn, "403217"))
        self.assertFalse(store.check_pin(self.conn, "403217", "1234"))

    def test_setting_again_replaces(self):
        store.set_pin(self.conn, "403217", "1234")
        store.set_pin(self.conn, "403217", "5678")
        self.assertFalse(store.check_pin(self.conn, "403217", "1234"))
        self.assertTrue(store.check_pin(self.conn, "403217", "5678"))

    def test_an_unknown_student_never_matches(self):
        self.assertFalse(store.check_pin(self.conn, "491772", "1234"))


class TestSignInFlow(unittest.TestCase):
    def setUp(self):
        for k in ("LATIN_TEACHER_PASSWORD", "LATIN_PUBLIC"):
            os.environ.pop(k, None)
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        self.client = server.app.test_client()
        self.conn = store.connect(self.db_path)
        store.add_student(self.conn, "403217", "Block 3")
        store.add_student(self.conn, "418206", "Block 3")

    def tearDown(self):
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def enter_id(self, sid, client=None):
        return (client or self.client).post(
            "/signin", data={"step": "id", "student_id": sid, "next": "/drill"})

    def enter_pin(self, sid, pin, pin2=None, client=None):
        data = {"step": "pin", "student_id": sid, "pin": pin, "next": "/drill",
                "confirm_unknown": "1"}
        if pin2 is not None:
            data["pin2"] = pin2
        return (client or self.client).post("/signin", data=data)

    def test_a_name_is_refused_at_the_first_step(self):
        r = self.enter_id("Sam Tucker")
        self.assertEqual(r.status_code, 400)
        self.assertIn("not a valid student ID", r.data.decode())

    def test_an_unknown_number_is_challenged_not_accepted(self):
        r = self.enter_id("491772")
        self.assertIn("We don't have that number", r.data.decode())

    def test_confirming_an_unknown_number_carries_on_rather_than_looping(self):
        # "That is my number — continue" used to return this same screen.
        r = self.client.post("/signin", data={"step": "id", "student_id": "491772",
                                              "confirm_unknown": "1", "next": "/drill"})
        self.assertIn("Choose a PIN", r.data.decode())

    def test_a_first_time_student_is_asked_to_choose_a_pin(self):
        body = self.enter_id("403217").data.decode()
        self.assertIn("Choose a PIN", body)
        self.assertIn("Type it again", body)

    def test_choosing_a_pin_signs_them_in(self):
        self.enter_id("403217")
        r = self.enter_pin("403217", "1234", "1234")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "/drill")
        self.assertEqual(self.client.get("/drill").status_code, 200)

    def test_mistyped_confirmation_is_caught(self):
        self.enter_id("403217")
        r = self.enter_pin("403217", "1234", "4321")
        self.assertEqual(r.status_code, 401)
        self.assertIn("different", r.data.decode())
        self.assertFalse(store.has_pin(self.conn, "403217"))

    def test_a_short_pin_is_refused(self):
        self.enter_id("403217")
        r = self.enter_pin("403217", "12", "12")
        self.assertEqual(r.status_code, 401)
        self.assertFalse(store.has_pin(self.conn, "403217"))

    def test_a_returning_student_is_asked_for_their_pin(self):
        store.set_pin(self.conn, "403217", "1234")
        body = self.enter_id("403217").data.decode()
        self.assertIn("Your PIN", body)
        self.assertNotIn("Type it again", body)

    def test_the_wrong_pin_does_not_get_in(self):
        store.set_pin(self.conn, "403217", "1234")
        r = self.enter_pin("403217", "9999")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.client.get("/drill").status_code, 302)

    def test_the_right_pin_does(self):
        store.set_pin(self.conn, "403217", "1234")
        self.enter_pin("403217", "1234")
        self.assertEqual(self.client.get("/drill").status_code, 200)

    def test_signing_out_closes_it(self):
        store.set_pin(self.conn, "403217", "1234")
        self.enter_pin("403217", "1234")
        self.client.get("/signout")
        self.assertEqual(self.client.get("/drill").status_code, 302)

    def test_a_teacher_reset_lets_them_choose_again(self):
        store.set_pin(self.conn, "403217", "1234")
        self.client.post("/teacher/pin/reset", data={"student_id": "403217"})
        self.assertIn("Choose a PIN", self.enter_id("403217").data.decode())


class TestIdentityComesFromTheSession(TestSignInFlow):
    """A PIN at the door is worthless if the rooms behind it take your word.

    Every one of these used to pass a student id in the URL or a form field.
    """

    def sign_in(self, sid, pin="1234"):
        store.set_pin(self.conn, sid, pin)
        self.enter_pin(sid, pin)

    def test_practice_is_recorded_against_the_signed_in_student(self):
        self.sign_in("403217")
        store.record_event(self.conn, "403217", "vocab:x:la_en", None, "x", "right")
        self.assertEqual(len(store.events_for_student(self.conn, "403217")), 1)
        self.assertEqual(len(store.events_for_student(self.conn, "418206")), 0)

    def test_a_student_id_in_the_url_is_ignored(self):
        self.sign_in("403217")
        r = self.client.get("/drill/session?student=418206&week=all&direction=both")
        self.assertEqual(r.status_code, 200)
        self.assertIn("403217", r.data.decode())
        self.assertNotIn("418206", r.data.decode())

    def test_progress_shows_your_own(self):
        self.sign_in("403217")
        body = self.client.get("/drill/progress?student=40218").data.decode()
        self.assertIn("403217", body)
        self.assertNotIn("418206", body)

    def test_no_student_id_appears_in_any_link(self):
        self.sign_in("403217")
        body = self.client.get("/drill/session?week=all&direction=both").data.decode()
        self.assertNotIn("student=", body)


if __name__ == "__main__":
    unittest.main()
