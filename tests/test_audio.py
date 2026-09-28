"""Word audio: the teacher records each vocabulary word, students hear it."""

import io
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import store  # noqa: E402


def a_wav(n=2205):
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
    w.writeframes(b"\x10\x00" * n)
    w.close()
    return buf.getvalue()


class TestStore(unittest.TestCase):
    def test_round_trip_and_versions(self):
        db = store.connect(os.path.join(tempfile.mkdtemp(), "a.sqlite"))
        store.init_db(db)
        store.save_word_audio(db, "puella", "audio/wav", a_wav())
        self.assertEqual(store.get_word_audio(db, "puella"), ("audio/wav", a_wav()))
        self.assertIn("puella", store.word_audio_versions(db))
        store.delete_word_audio(db, "puella")
        self.assertIsNone(store.get_word_audio(db, "puella"))

    def test_it_travels_and_survives_the_year_end_purge(self):
        import backup, migrate
        self.assertIn("word_audio", backup.TABLES)
        self.assertIn("word_audio", migrate.TABLES)
        self.assertNotIn("word_audio", backup.STUDENT_TABLES)


class TestScreens(unittest.TestCase):
    def setUp(self):
        os.environ.pop("LATIN_PUBLIC", None)
        os.environ["LATIN_TEACHER_PASSWORD"] = "teacherpw"
        self.db_path = os.path.join(tempfile.mkdtemp(), "t.sqlite")
        os.environ["LATIN_DB"] = self.db_path
        sys.modules.pop("server", None)
        import server
        import drill
        server.app.config["TESTING"] = True
        self.server, self.drill = server, drill
        self.db = store.connect(self.db_path)
        store.add_student(self.db, "403217", "Block 3")
        self.teacher = server.app.test_client()
        self.teacher.post("/login", data={"password": "teacherpw", "next": "/teacher"})
        self.student = server.app.test_client()
        self.student.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.student.post("/signin", data={"step": "pin", "student_id": "403217",
                                           "pin": "1234", "pin2": "1234", "next": "/"})
        self.keys = sorted({drill._key(w["latin"]) for w in server._DRILL_WORDS})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def record(self, key, body=None):
        return self.teacher.post("/teacher/audio/save?key=" + key, data=body or a_wav(),
                                 content_type="audio/wav")

    def record_everything(self):
        for k in self.keys:
            self.assertEqual(self.record(k).status_code, 200)

    def test_the_teacher_page_lists_every_word(self):
        body = self.teacher.get("/teacher/audio").data.decode()
        self.assertIn("<strong id=\"nrec\">0</strong> of %d words recorded" % len(self.keys), body)
        self.assertIn("● Record", body)

    def test_a_recording_is_saved_and_a_student_can_hear_it(self):
        r = self.record("puella")
        self.assertEqual(r.status_code, 200)
        url = r.get_json()["url"]
        got = self.student.get(url)
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.mimetype, "audio/wav")
        self.assertEqual(got.data, a_wav())
        self.assertIn("immutable", got.headers["Cache-Control"])

    def test_re_recording_changes_the_url_so_phones_fetch_the_new_take(self):
        first = self.record("puella").get_json()["url"]
        import time
        time.sleep(1.1)
        second = self.record("puella", a_wav(4000)).get_json()["url"]
        self.assertNotEqual(first, second)

    def test_only_a_real_wav_for_a_real_word_is_kept(self):
        self.assertEqual(self.record("puella", b"<script>alert(1)</script>").status_code, 400)
        self.assertEqual(self.record("notaword").status_code, 404)
        self.assertEqual(self.record("puella", a_wav(800000)).status_code, 400)   # 1.6 MB
        self.assertEqual(store.word_audio_versions(self.db), {})

    def test_nobody_else_hears_it_or_records_it(self):
        self.record("puella")
        anon = self.server.app.test_client()
        r = anon.get("/audio/puella")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/signin", r.headers["Location"])
        r = self.student.post("/teacher/audio/save?key=puella", data=a_wav(), content_type="audio/wav")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])
        self.assertEqual(self.student.get("/teacher/audio").status_code, 302)

    def test_the_button_is_on_the_latin_card_and_never_on_the_english_one(self):
        self.record_everything()
        la = self.student.get("/drill/session?direction=la_en").data.decode()
        self.assertIn('class="say"', la)
        # English to Latin: the recording would be the answer.
        en = self.student.get("/drill/session?direction=en_la").data.decode()
        self.assertNotIn('class="say"', en)

    def test_the_button_is_on_the_answer_screen_and_progress(self):
        self.record_everything()
        en = self.student.get("/drill/session?direction=en_la").data.decode()
        latin = en.split('name="latin" value="')[1].split('"')[0]
        fb = self.student.post("/drill/answer", data={
            "direction": "en_la", "latin": latin, "ask": "en_la", "response": "zzz",
            "latency_ms": "900"}, follow_redirects=True).data.decode()
        self.assertIn('class="say"', fb)
        self.assertIn('class="say"', self.student.get("/drill/progress").data.decode())

    def test_no_recording_no_button(self):
        self.assertNotIn('class="say"', self.student.get("/drill/session?direction=la_en").data.decode())

    def test_delete(self):
        self.record("puella")
        self.teacher.post("/teacher/audio/delete", data={"key": "puella"})
        self.assertIsNone(store.get_word_audio(self.db, "puella"))


if __name__ == "__main__":
    unittest.main()
