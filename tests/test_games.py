"""Games: links to the teacher's games on the student home screen."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import store  # noqa: E402

TITLE = "Condenda Roma: Help Romulus Build Rome"
URL = "https://jauldridges.github.io/build-rome-game/latin.html"


class TestGames(unittest.TestCase):
    def setUp(self):
        os.environ.pop("LATIN_PUBLIC", None)
        os.environ["LATIN_TEACHER_PASSWORD"] = "teacherpw"
        self.dir = tempfile.mkdtemp()
        os.environ["LATIN_DB"] = os.path.join(self.dir, "t.sqlite")
        sys.modules.pop("server", None)
        import server
        server.app.config["TESTING"] = True
        self.server = server
        store.add_student(store.connect(os.environ["LATIN_DB"]), "403217", "Block 3")
        self.student = server.app.test_client()
        self.student.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        self.student.post("/signin", data={"step": "pin", "student_id": "403217",
                                           "pin": "1234", "pin2": "1234", "next": "/"})

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def test_the_first_game_is_on_the_student_home_screen(self):
        body = self.student.get("/").data.decode()
        self.assertIn("<h2>Games</h2>", body)
        self.assertIn('<a href="%s" target="_blank" rel="noopener">%s</a>' % (URL, TITLE), body)

    def test_only_titled_https_links_get_through(self):
        path = os.path.join(self.dir, "games.yaml")
        with open(path, "w") as f:
            f.write('games:\n'
                    '  - {title: "Good", url: "https://example.org/g.html"}\n'
                    '  - {title: "Plain http", url: "http://example.org/g.html"}\n'
                    '  - {title: "Script", url: "javascript:alert(1)"}\n'
                    '  - {url: "https://example.org/untitled.html"}\n')
        self.assertEqual([g["title"] for g in self.server.load_games(path)], ["Good"])

    def test_no_file_means_no_section(self):
        self.assertEqual(self.server.load_games(os.path.join(self.dir, "missing.yaml")), [])


if __name__ == "__main__":
    unittest.main()
