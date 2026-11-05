"""Waiting for you: everything the teacher has yet to approve, on one page."""

import html
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dataio      # noqa: E402
import lessons     # noqa: E402
import magister    # noqa: E402
import store       # noqa: E402
import vocabhints  # noqa: E402


class TestWaitingForYou(unittest.TestCase):
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

    def tearDown(self):
        for k in ("LATIN_DB", "LATIN_TEACHER_PASSWORD"):
            os.environ.pop(k, None)
        sys.modules.pop("server", None)

    def page(self):
        return html.unescape(self.teacher.get("/teacher/approve").data.decode())

    def approve(self, **data):
        return self.teacher.post("/teacher/approve", data=data)

    def approvals(self):
        return store.teaching_approvals(self.db)

    def test_only_the_teacher_gets_in(self):
        student = self.server.app.test_client()
        student.post("/signin", data={"step": "id", "student_id": "403217", "next": "/"})
        student.post("/signin", data={"step": "pin", "student_id": "403217",
                                      "pin": "1234", "pin2": "1234", "next": "/"})
        for client in (student, self.server.app.test_client()):
            r = client.get("/teacher/approve")
            self.assertEqual(r.status_code, 302)
            self.assertIn("/login", r.headers["Location"])
            r = client.post("/teacher/approve", data={"scope": "everything"})
            self.assertEqual(r.status_code, 302)
        self.assertEqual(self.approvals(), {})

    def test_every_kind_that_waits_is_listed(self):
        body = self.page()
        for title in ("Lēgēs Magistrī, the laws", "Badge lessons", "Grammar questions",
                      "Teaching text", "Vocabulary hint sentences", "The Magister's other lines",
                      "Reader stories not published yet"):
            self.assertIn(title, body)
        # the thing itself is on the page, not just a link to it
        self.assertIn("rēx, rēgis, m.", body)                       # a hint, with its entry
        self.assertIn("Fābula dē Mariō", body)                      # a story
        self.assertIn("Approve everything on this page", body)
        # and the dashboard says how many
        home = self.teacher.get("/teacher").data.decode()
        self.assertIn("waiting for you", home)

    def test_approving_one_thing(self):
        law = next(l for l in magister.load() if l["category"] in magister.LEGES)
        self.approve(kind="laws", id=law["id"])
        self.assertEqual(self.approvals().get(magister.key(law["id"])), magister.fingerprint(law))
        hint = self.server.vocab_hint_entry(self.db, "rēx")
        self.approve(kind="hints", id="rēx")
        self.assertEqual(self.approvals().get(vocabhints.approval_key("rēx")), vocabhints.fingerprint(hint))
        self.approve(kind="lessons", id="how-to-study")
        self.assertEqual(self.approvals().get(lessons.key("how-to-study")),
                         lessons.fingerprint(self.server._LESSONS["how-to-study"]))

    def test_a_question_only_in_a_bank_file_is_imported_and_approved(self):
        bank = dataio.load_bank()
        flags, _ = self.server.checks.run_all(bank, self.server._VALID_NODES, self.server._ALLOWED_LATIN)
        clean = next(it for it in bank if not flags.get(it["id"]))
        self.assertIsNone(store.get_item(self.db, clean["id"]))
        self.assertIn(self.server.practice.question_text(clean)[:30], self.page())
        self.approve(kind="questions", id=clean["id"])
        self.assertEqual(store.get_item(self.db, clean["id"])["review_status"], "approved")

    def test_approve_all_in_one_group(self):
        r = self.approve(scope="all", kind="hints")
        self.assertIn("#hints", r.headers["Location"])
        words = self.server._DRILL_WORDS
        self.assertTrue(all(self.server.vocab_hint_state(self.db, w["latin"]) == "approved" for w in words))
        self.assertNotIn("Vocabulary hint sentences", self.page())
        self.assertIn("Teaching text", self.page())          # the other groups still wait

    def test_approve_everything_leaves_only_the_stories(self):
        self.approve(scope="everything")
        body = self.page()
        for title in ("Lēgēs Magistrī", "Badge lessons", "Teaching text",
                      "Vocabulary hint sentences", "The Magister's other lines"):
            self.assertNotIn(title, body)
        self.assertIn("Reader stories not published yet", body)
        self.assertEqual(self.server.published_readings(self.db), set())
        with self.server.app.test_request_context():
            self.assertEqual(self.server.approval_count(self.db), 0)
        # a question the automatic checks flagged is left for the Review tool
        flagged = self.db.execute("SELECT COUNT(*) AS n FROM items WHERE flagged=1 "
                                  "AND review_status='unreviewed'").fetchone()["n"]
        if flagged:
            self.assertIn("the Review tool", body)

    def test_a_story_is_published_one_at_a_time(self):
        self.approve(kind="stories", id="marius")
        self.assertEqual(self.server.published_readings(self.db), {"marius"})
        self.assertNotIn("Fābula dē Mariō", self.page())
        self.approve(scope="all", kind="stories")           # no group button for stories
        self.assertEqual(self.server.published_readings(self.db), {"marius"})

    def test_a_reworded_line_comes_back_marked(self):
        law = next(l for l in magister.load() if l["category"] in magister.LEGES)
        self.approve(kind="laws", id=law["id"])
        store.set_teaching_override(self.db, magister.key(law["id"]),
                                    {"category": law["category"], "text": "A new wording."})
        body = self.page()
        self.assertIn("A new wording.", body)
        self.assertIn("reworded since you approved it", body)

    # --- editing in place ------------------------------------------------

    def edit(self, **data):
        return self.teacher.post("/teacher/approve", data=dict(data, action="edit"))

    def test_every_editable_kind_has_an_edit_button(self):
        body = self.page()
        self.assertIn('<summary class="minibtn">Edit</summary>', body)
        self.assertIn('name="explain"', body)              # teaching text
        self.assertIn('name="option_a"', body)             # a multiple-choice question
        self.assertIn("full editor", body)
        self.assertIn("Lessons can't be edited in the app yet", body)

    def test_editing_a_law_saves_it_and_approves_it(self):
        law = next(l for l in magister.load() if l["category"] in magister.LEGES)
        r = self.edit(kind="laws", id=law["id"], text="Practice a little every day.")
        self.assertIn("edited=1", r.headers["Location"])
        line = {l["id"]: l for l in self.server.magister_lines(self.db)}[law["id"]]
        self.assertEqual((line["text"], line["state"]), ("Practice a little every day.", "approved"))

    def test_a_bad_edit_is_refused_and_says_why(self):
        law = next(l for l in magister.load() if l["category"] in magister.LEGES)
        r = self.edit(kind="laws", id=law["id"], text="   ")
        self.assertIn("error=", r.headers["Location"])
        self.assertNotIn(magister.key(law["id"]), self.approvals())
        body = html.unescape(self.teacher.get(r.headers["Location"]).data.decode())
        self.assertIn("not saved", body)
        self.assertIn("say something", body)
        self.assertIn("<details class=\"queue-edit\" open>", body)    # the drawer is still open

    def test_editing_a_hint_sentence(self):
        self.edit(kind="hints", id="rēx", latin="*Rēx* mīlitī pecūniam dat.",
                  en="The king gives money to the soldier.")
        self.assertEqual(self.server.vocab_hint_state(self.db, "rēx"), "approved")
        self.assertEqual(self.server.vocab_hint_entry(self.db, "rēx")["latin"], "*Rēx* mīlitī pecūniam dat.")
        r = self.edit(kind="hints", id="dux", latin="Mīles ducī pāret.", en="x")     # word not marked
        self.assertIn("error=", r.headers["Location"])

    def test_editing_teaching_text(self):
        nid = sorted(self.server._TEACHING)[0]
        self.edit(kind="teaching", id=nid, explain="Short and clear.", examples="one\ntwo",
                  when_wrong="Look again.")
        self.assertEqual(self.server.teaching_state(self.db, nid), "approved")
        self.assertEqual(self.server.teaching_entry(self.db, nid)["examples"], ["one", "two"])
        r = self.edit(kind="teaching", id=nid, explain="", examples="one", when_wrong="x")
        self.assertIn("error=", r.headers["Location"])

    def test_editing_a_multiple_choice_question_still_in_its_bank_file(self):
        it = next(i for i in dataio.load_bank() if i.get("format") == "choice"
                  and len(i.get("options") or {}) == 4)
        self.assertIsNone(store.get_item(self.db, it["id"]))
        keys = sorted(it["options"])
        data = {"option_" + k: "Choice %s" % k for k in keys}
        self.edit(kind="questions", id=it["id"], stem="A new question?", answer=keys[1], **data)
        row = store.get_item(self.db, it["id"])
        self.assertEqual(row["review_status"], "approved")
        self.assertEqual(row["payload"]["stem"], "A new question?")
        self.assertEqual(row["payload"]["answer"], keys[1])
        # two choices the same is refused
        data["option_" + keys[0]] = data["option_" + keys[1]]
        r = self.edit(kind="questions", id=it["id"], stem="Q?", answer=keys[0], **data)
        self.assertIn("error=", r.headers["Location"])

    def test_any_other_question_opens_the_full_editor_and_comes_back(self):
        it = next(i for i in dataio.load_bank() if i.get("format") != "choice")
        r = self.teacher.get("/teacher/approve/question/" + it["id"])
        self.assertIn("/review/edit/", r.headers["Location"])
        self.assertIn("queue=approve", r.headers["Location"])
        self.assertIsNotNone(store.get_item(self.db, it["id"]))          # brought in first
        import yaml
        payload = dict(it, stem="Edited in the full editor.")
        r = self.teacher.post("/review/edit/" + it["id"], data={
            "payload": yaml.safe_dump(payload, allow_unicode=True), "queue": "approve"})
        self.assertIn("/teacher/approve", r.headers["Location"])
        self.assertEqual(store.get_item(self.db, it["id"])["review_status"], "approved")


if __name__ == "__main__":
    unittest.main()
