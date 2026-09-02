"""Tests for the door.

The claim being tested is narrow and important: with a password set, no
teacher URL serves anything to a stranger, and with a class code set, no
student URL does either. The last test is the one that matters most — it walks
every registered route rather than a hand-written list, because the way this
fails in practice is a route added later that nobody remembered to gate.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth  # noqa: E402
import store  # noqa: E402


class EnvMixin(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("LATIN_TEACHER_PASSWORD", "LATIN_PUBLIC")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def env(self, **kw):
        for k, v in kw.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestConfig(EnvMixin):
    def test_public_without_a_password_is_refused(self):
        # The one outcome worth crashing over: a deployment that would have
        # served 88 students' records to anyone with the URL.
        self.env(LATIN_PUBLIC="1", LATIN_TEACHER_PASSWORD=None)
        self.assertIsNotNone(auth.check_config())

    def test_public_with_a_password_is_fine(self):
        self.env(LATIN_PUBLIC="1", LATIN_TEACHER_PASSWORD="hunter2")
        self.assertIsNone(auth.check_config())

    def test_local_needs_nothing(self):
        self.env(LATIN_PUBLIC=None, LATIN_TEACHER_PASSWORD=None)
        self.assertIsNone(auth.check_config())

    def test_the_teacher_gate_is_off_until_a_password_is_set(self):
        self.env(LATIN_TEACHER_PASSWORD=None)
        self.assertFalse(auth.teacher_gate_on())


class TestMatches(EnvMixin):
    def test_right_password(self):
        self.assertTrue(auth.matches("hunter2", "hunter2"))

    def test_wrong_password(self):
        self.assertFalse(auth.matches("hunter3", "hunter2"))

    def test_an_empty_expected_secret_never_matches(self):
        # Otherwise an unset password would admit an empty form field.
        self.assertFalse(auth.matches("", ""))
        self.assertFalse(auth.matches(None, None))


def make_client(tmpdb, **env):
    """A fresh app bound to a throwaway DB, with the environment set first."""
    for k in ("LATIN_TEACHER_PASSWORD", "LATIN_CLASS_CODE", "LATIN_PUBLIC"):
        os.environ.pop(k, None)
    for k, v in env.items():
        os.environ[k] = v
    os.environ["LATIN_DB"] = tmpdb
    for mod in [m for m in list(sys.modules) if m in ("server",)]:
        del sys.modules[mod]
    import server
    server.app.config["TESTING"] = True
    return server, server.app.test_client()


class TestGate(EnvMixin):
    def setUp(self):
        EnvMixin.setUp(self)
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.sqlite")

    def tearDown(self):
        EnvMixin.tearDown(self)
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def test_the_teacher_side_is_open_when_no_password_is_set(self):
        _, c = make_client(self.db)
        self.assertEqual(c.get("/teacher").status_code, 200)

    def test_teacher_pages_redirect_to_login(self):
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        r = c.get("/teacher")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_the_right_password_gets_in_and_the_wrong_one_does_not(self):
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        self.assertEqual(c.post("/login", data={"password": "nope"}).status_code, 401)
        self.assertEqual(c.get("/teacher").status_code, 302)
        c.post("/login", data={"password": "hunter2"})
        self.assertEqual(c.get("/teacher").status_code, 200)

    def test_signing_out_closes_the_door_again(self):
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        c.post("/login", data={"password": "hunter2"})
        c.get("/logout")
        self.assertEqual(c.get("/teacher").status_code, 302)

    def test_the_student_side_always_needs_a_signed_in_student(self):
        # Unlike the teacher gate there is no "off" switch: a shared class code
        # let anyone who knew it practise as anyone, which is what PINs fix.
        _, c = make_client(self.db)
        r = c.get("/drill")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/signin", r.headers["Location"])

    def test_a_signed_in_student_does_not_open_the_teacher_side(self):
        # The whole point of two doors.
        server, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        conn = store.connect(self.db)
        store.add_student(conn, "403217", "Block 3")
        c.post("/signin", data={"step": "pin", "student_id": "403217",
                                "pin": "1234", "pin2": "1234"})
        self.assertEqual(c.get("/drill").status_code, 200)
        self.assertEqual(c.get("/teacher").status_code, 302)

    def test_the_landing_page_hides_teacher_tools_from_students(self):
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        body = c.get("/").data.decode()
        self.assertNotIn("/teacher", body)
        self.assertIn("/drill", body)

    def test_every_route_is_gated(self):
        """Walk the real URL map. A route added later is closed by default."""
        server, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        # /healthz is deliberately open — Render must reach it without a
        # password — and is safe because it returns the two bytes "ok" and
        # never any data. See test_the_health_check_says_nothing_else.
        allowed = {"/", "/login", "/logout", "/signin", "/signout", "/healthz",
                   "/static/<path:filename>"}
        leaked = []
        for rule in server.app.url_map.iter_rules():
            if str(rule) in allowed:
                continue
            if "GET" not in (rule.methods or ()):
                continue
            path = str(rule)
            for arg in rule.arguments:                 # any value will do; the
                path = path.replace("<%s>" % arg, "x")  # gate runs before the view
                path = path.replace("<path:%s>" % arg, "x")
                path = path.replace("<int:%s>" % arg, "1")
            if "<" in path:
                continue
            r = c.get(path)
            if r.status_code != 302 or ("/login" not in r.headers.get("Location", "")
                                        and "/signin" not in r.headers.get("Location", "")):
                leaked.append((path, r.status_code))
        self.assertEqual(leaked, [], "ungated routes: %r" % (leaked,))


if __name__ == "__main__":
    unittest.main()


class TestDeployment(EnvMixin):
    """The things Render needs, and the things a public URL needs."""

    def setUp(self):
        EnvMixin.setUp(self)
        import tempfile
        self.db = os.path.join(tempfile.mkdtemp(), "t.sqlite")

    def tearDown(self):
        EnvMixin.tearDown(self)
        os.environ.pop("LATIN_DB", None)
        sys.modules.pop("server", None)

    def test_the_health_check_is_open_and_touches_the_database(self):
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        r = c.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, b"ok\n")

    def test_the_health_check_says_nothing_else(self):
        # It is open by necessity, so it must leak nothing: no version, no
        # counts, no connection string.
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        self.assertEqual(c.get("/healthz").data, b"ok\n")

    def test_the_health_check_fails_when_the_database_is_gone(self):
        # A check that only proves Flask is running would keep a service alive
        # that cannot serve a single page.
        server, c = make_client(self.db)
        import store
        real = store.connect

        def broken(*a, **kw):
            raise RuntimeError("no database")
        store.connect = broken
        try:
            self.assertEqual(c.get("/healthz").status_code, 503)
        finally:
            store.connect = real

    def test_plain_http_is_redirected_once_deployed(self):
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2", LATIN_PUBLIC="1")
        r = c.get("/signin", headers={"X-Forwarded-Proto": "http"})
        self.assertEqual(r.status_code, 301)
        self.assertTrue(r.headers["Location"].startswith("https://"))

    def test_locally_there_is_no_https_to_redirect_to(self):
        _, c = make_client(self.db)
        self.assertEqual(c.get("/signin").status_code, 200)

    def test_hsts_only_when_public(self):
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2", LATIN_PUBLIC="1")
        self.assertIn("Strict-Transport-Security", c.get("/healthz").headers)
        _, c2 = make_client(self.db)
        self.assertNotIn("Strict-Transport-Security", c2.get("/healthz").headers)

    def test_the_usual_headers_are_set(self):
        _, c = make_client(self.db)
        h = c.get("/").headers
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["X-Frame-Options"], "DENY")

    def test_no_secret_reaches_a_page(self):
        _, c = make_client(self.db, LATIN_TEACHER_PASSWORD="hunter2")
        for path in ("/", "/login", "/signin", "/healthz"):
            self.assertNotIn(b"hunter2", c.get(path).data, path)
