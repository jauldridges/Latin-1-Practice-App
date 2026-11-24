"""DI mode: the first-declension strand."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json  # noqa: E402
import tempfile  # noqa: E402

import di  # noqa: E402
import di_run  # noqa: E402
import store  # noqa: E402

# Every translation the DI plan itself gives (sections 9 and 10).
PLAN_TRANSLATIONS = [
    ("Fēmina spectat.", "The woman watches."),
    ("Laudat agricola.", "The farmer praises."),
    ("Puella nautam vocat.", "The girl calls the sailor."),
    ("Puellam nauta vocat.", "The sailor calls the girl."),
    ("Agricola terram amat.", "The farmer loves the land."),
    ("Fēmina aquam portat.", "The woman carries the water."),
    ("Nauta puellās vocat.", "The sailor calls the girls."),
    ("Lūnam et stēllās nauta spectat.", "The sailor watches the moon and the stars."),
    ("Puellae nautam vocant.", "The girls call the sailor."),
    ("Puellās nautae vocant.", "The sailors call the girls."),
    ("Fēminās puellae laudant.", "The girls praise the women."),
    ("Nauta fēminās laudat.", "The sailor praises the women."),
    ("Fāmam agricola nōn amat.", "The farmer does not love fame."),
    ("Vītam fēminae laudant.", "The women praise life."),
    ("Fēminam nautae nōn laudant.", "The sailors do not praise the woman."),
    ("Nautās fēmina nōn vocat.", "The woman does not call the sailors."),
    ("Patriam nautae amant.", "The sailors love the homeland."),
    ("Fēmina fāmam nautārum laudat.", "The woman praises the fame of the sailors."),
    ("Agricolae aquam silvārum portant.", "The farmers carry the water of the forests."),
    ("Nauta vītam agricolārum laudat.", "The sailor praises the life of the farmers."),
    ("Puellae viās īnsulārum spectant.", "The girls watch the roads of the islands."),
    ("Terram fēminārum agricolae amant.", "The farmers love the land of the women."),
    ("Fēmina vītam puellae laudat.", "The woman praises the life of the girl."),
    ("Agricola fāmam nautae laudat.", "The farmer praises the fame of the sailor."),
    ("Nauta viam īnsulae spectat.", "The sailor watches the road of the island."),
    ("Silvam patriae agricola amat.", "The farmer loves the forest of the homeland."),
    ("Fēminae fāmam patriae laudant.", "The women praise the fame of the homeland."),
    ("Puella fāmam nautārum laudat.", "The girl praises the fame of the sailors."),
    ("Nauta puellīs fābulam nārrat.", "The sailor tells a story to the girls."),
    ("Fēmina agricolīs aquam portat.", "The woman carries water for the farmers."),
    ("Agricola fēminīs viam parat.", "The farmer prepares a road for the women."),
    ("Puellae nautīs fābulās nārrant.", "The girls tell stories to the sailors."),
    ("Fābulam nautīs fēmina nārrat.", "The woman tells a story to the sailors."),
    ("Fēmina agricolās vocat.", "The woman calls the farmers."),
    ("Nautae puellīs aquam portant.", "The sailors carry water for the girls."),
    ("Agricolae vītam nautae laudant.", "The farmers praise the life of the sailor."),
    ("Puellae fābulam nārrant.", "The girls tell a story."),
    ("Nauta puellae fābulam nārrat.", "The sailor tells a story to the girl."),
    ("Nauta fāmam puellae laudat.", "The sailor praises the fame of the girl."),
    ("Agricola fēminae aquam portat.", "The farmer carries water for the woman."),
    ("Agricolae aquam portant.", "The farmers carry the water."),
    ("Fēmina vītam agricolae laudat.", "The woman praises the life of the farmer."),
    ("Puella agricolae viam parat.", "The girl prepares a road for the farmer."),
    ("Fēmina nautae īnsulam servat.", "The woman saves the island for the sailor."),
    ("Nauta in īnsulā pugnat.", "The sailor fights on the island."),
    ("Puella cum fēminā aquam portat.", "The girl carries water with the woman."),
    ("Fēmina puellam vocat.", "The woman calls the girl."),
    ("Agricola ē silvā aquam portat.", "The farmer carries water out of the forest."),
    ("Fēminae in viā stēllās spectant.", "The women watch the stars in the street."),
    ("Puella ā portā nautam vocat.", "The girl calls the sailor from the gate."),
    ("Silva agricolam nōn servat.", "The forest does not save the farmer."),
    ("Fēmina in viā puellae fābulam nārrat.", "The woman tells a story to the girl in the street."),
    ("Cum nautā agricola pugnat.", "The farmer fights with the sailor."),
    ("Nauta cum puellīs pugnat.", "The sailor fights with the girls."),
    ("Fēmina ē silvīs aquam portat.", "The woman carries water out of the forests."),
    ("Nautae in īnsulīs lūnam spectant.", "The sailors watch the moon on the islands."),
    ("Puellae fēminīs viam parant.", "The girls prepare a road for the women."),
    ("Agricola in silvā pugnat.", "The farmer fights in the forest."),
    ("Puella cum fēminīs fābulās nārrat.", "The girl tells stories with the women."),
    ("Fēmina fāmam nautārum laudat.", "The woman praises the fame of the sailors."),
    ("Nautae fāmam patriae laudant.", "The sailors praise the fame of the homeland."),
    ("Fēmina agricolīs aquam portat.", "The woman carries water for the farmers."),
    ("Nauta in īnsulā lūnam et stēllās spectat.", "The sailor watches the moon and the stars on the island."),
    ("Puellae ē silvā aquam portant.", "The girls carry water out of the forest."),
    ("Nauta puellās vocat et puellīs fābulam nārrat.",
     "The sailor calls the girls and tells a story to the girls."),
    ("Fābula fāmam nautārum laudat.", "The story praises the fame of the sailors."),
    ("Puellae fābulam nautae amant.", "The girls love the story of the sailor."),
    ("Puellae cum nautā patriam servant.", "The girls save the homeland with the sailor."),
]

PLAN_PHRASES = [
    ("fāma nautārum", "the fame of the sailors"),
    ("vīta agricolārum", "the life of the farmers"),
    ("aqua silvārum", "the water of the forests"),
    ("patria puellārum", "the homeland of the girls"),
    ("viae īnsulārum", "the roads of the islands"),
    ("terra fēminārum", "the land of the women"),
    ("in silvā", "in the forest"),
    ("in īnsulā", "on the island"),
    ("cum puellā", "with the girl"),
    ("ē silvā", "out of the forest"),
    ("ā portā", "away from the gate"),
    ("in viā", "in the street"),
    ("in silvīs", "in the forests"),
]


class TestTheEngineReadsThePlan(unittest.TestCase):
    def test_every_translation_in_the_plan(self):
        wrong = [(la, di.translate(la), en) for la, en in PLAN_TRANSLATIONS if di.translate(la) != en]
        self.assertEqual(wrong, [])

    def test_every_phrase_in_the_plan(self):
        wrong = [(la, di.translate(la), en) for la, en in PLAN_PHRASES if di.translate(la) != en]
        self.assertEqual(wrong, [])

    def test_the_three_jobs_of_ae(self):
        self.assertEqual(di.job_of("**Puellae** aquam portant."), "subject")
        self.assertEqual(di.job_of("Fēmina vītam **puellae** laudat."), "poss")
        self.assertEqual(di.job_of("Nauta **puellae** fābulam nārrat."), "tofor")
        # two -ae words: the one with the verb is the subject, the other belongs to its noun
        self.assertEqual(di.job_of("Fēminae fāmam **patriae** laudant."), "poss")
        self.assertEqual(di.job_of("**Fēminae** fāmam patriae laudant."), "subject")
        self.assertEqual(di.job_of("Puellae **agricolae** viam parant."), "tofor")

    def test_the_two_jobs_of_is_and_a_versus_long_a(self):
        self.assertEqual(di.job_of("Nauta **puellīs** fābulam nārrat."), "tofor")
        self.assertEqual(di.job_of("Nauta cum **puellīs** pugnat."), "objprep")
        self.assertEqual(di.job_of("**Silva** agricolam nōn servat."), "subject")
        self.assertEqual(di.job_of("Agricola ē **silvā** aquam portat."), "objprep")

    def test_placement_answers(self):
        cases = [("**Puella** nautam vocat.", "subject"), ("Nauta **puellam** vocat.", "dobj"),
                 ("Nauta **puellās** vocat.", "dobj"), ("Fēmina fāmam **nautārum** laudat.", "poss"),
                 ("Fēmina vītam **puellae** laudat.", "poss"), ("**Puellae** fābulam nārrant.", "subject"),
                 ("Nauta **puellīs** fābulam nārrat.", "tofor"), ("Nauta **puellae** fābulam nārrat.", "tofor"),
                 ("Nauta in **īnsulā** pugnat.", "objprep"), ("Agricolae in **silvīs** pugnant.", "objprep")]
        self.assertEqual([(la, di.job_of(la)) for la, _ in cases], cases)


class TestThreeChoices(unittest.TestCase):
    def test_always_three_one_right_all_different(self):
        for la, en in PLAN_TRANSLATIONS:
            ch = di.choices(la, key=la)
            self.assertEqual(len(ch), 3, la)
            self.assertEqual(len({t for t, _ in ch}), 3, (la, ch))
            self.assertEqual([t for t, right in ch if right], [en], la)

    def test_one_swaps_subject_and_object(self):
        texts = {t for t, _ in di.choices("Puella nautam vocat.")}
        self.assertIn("The sailor calls the girl.", texts)

    def test_one_changes_the_job_of_a_dative_ae(self):
        texts = {t for t, _ in di.choices("Nauta puellae fābulam nārrat.", focus="ae")}
        self.assertIn("The sailor tells the story of the girl.", texts)

    def test_the_order_is_fixed_for_an_item(self):
        self.assertEqual(di.choices("Puella nautam vocat.", key="x"), di.choices("Puella nautam vocat.", key="x"))


class TestTypedAnswers(unittest.TestCase):
    def test_english(self):
        la = "Nauta puellīs fābulam nārrat."
        for typed in ("The sailor tells a story to the girls.", "the sailor tells the story to the girls",
                      "The sailor tells the girls a story", "sailor tells story for girls"):
            self.assertEqual(di.check_english(typed, la), "right", typed)
        self.assertEqual(di.check_english("The sailor tells a story to the girl.", la), "close")
        self.assertEqual(di.check_english("The girls tell a story to the sailor.", la), "wrong")
        self.assertEqual(di.check_english("", la), "wrong")
        self.assertEqual(di.check_english("The woman watches the land of the girls",
                                          "Fēmina terram puellārum spectat."), "right")
        self.assertEqual(di.check_english("The woman watches the girls' land",
                                          "Fēmina terram puellārum spectat."), "right")

    def test_endings_need_no_macrons(self):
        self.assertEqual(di.check_ending("am", "am"), "right")
        self.assertEqual(di.check_ending("-as", "ās"), "right")
        self.assertEqual(di.check_ending("arum", "ārum"), "right")
        self.assertEqual(di.check_ending("a", "am"), "wrong")


class TestCorrections(unittest.TestCase):
    def test_the_rule_line(self):
        self.assertEqual(di.rule_line("Puellam", "dobj"),
                         "*Puellam* ends in **-am**. -am marks the direct object.")
        self.assertIn("possession", di.rule_line("puellae", "poss"))


# --------------------------------------------------------------------------
# The runner
# --------------------------------------------------------------------------

def right_value(st):
    if st["kind"] in ("choice", "tap"):
        return st["answer"][0]
    if st["kind"] == "type":
        return di.translate(st["latin"]) if st["mode"] == "english" else st["answer"]
    return di_run.NEXT


def wrong_value(st):
    if st["kind"] == "choice":
        return next(o["v"] for o in st["options"] if o["v"] not in st["answer"])
    if st["kind"] == "tap":
        vals = [str(t["i"]) for t in st["tokens"]] + [x["v"] for x in st.get("extra") or []]
        return next(v for v in vals if v not in st["answer"])
    if st["kind"] == "type":
        return "zzzzzzzz"
    return di_run.NEXT


def run_through(state, miss=lambda e, st, k: False, limit=2000):
    """Answer every screen; miss where miss() says. Returns the events."""
    events = []
    for _ in range(limit):
        e, steps, k = di_run.current(state)
        if e is None:
            return events
        st = steps[k]
        v = wrong_value(st) if miss(e, st, k) else right_value(st)
        state, out = di_run.answer(state, v, 1500)
        if out.get("event"):
            events.append(out["event"])
    raise AssertionError("the lesson never ended")


class TestContent(unittest.TestCase):
    def test_no_content_problems(self):
        self.assertEqual(di_run.problems(), [])

    def test_thirteen_lessons_and_eighteen_placement_items(self):
        self.assertEqual([L["n"] for L in di_run.load()["lessons"]], list(range(13)))
        self.assertEqual(len(di_run.build_placement()), 18)

    def test_every_check_is_eight_items_seven_to_pass(self):
        for L in di_run.load()["lessons"]:
            want = (16, 14) if L["n"] == 12 else (8, 7)     # Lesson 12 checks the whole table
            for s in ("A", "B"):
                self.assertEqual((len(di_run.part_f(L, s)), di_run.pass_mark(L)), want, (L["n"], s))

    def test_a_verb_stem_keeps_its_vowel(self):
        # "port___" with -t / -nt would make "portt": the stem is porta-.
        import re
        seen = 0
        for ref in di_run.all_refs():
            for st in di_run.steps_for(ref):
                if st.get("prompt") == "Which verb ending?":
                    seen += 1
                    stem = re.sub("<[^>]+>", "", st["show"]["html"]).split("___")[0].split()[-1]
                    self.assertTrue(stem.endswith("a"), (ref, stem))
                    for end in ("t", "nt"):
                        self.assertEqual(di.word(stem + end)["kind"], "verb", (ref, stem + end))
        self.assertGreater(seen, 15)

    def test_endings_are_built_inside_a_sentence(self):
        # "of the gate - port___" on its own became a whole sentence, in English and Latin.
        seen = 0
        for ref in di_run.all_refs():
            raw, _ = di_run.resolve(ref)
            if isinstance(raw, str) and raw.split(" ", 1)[0] in ("F4", "F8E"):
                seen += 1
                st = di_run.steps_for(ref)[0]
                self.assertIn("<strong>", st["show"]["html"], ref)
                latin = st["show"]["html"].split('class="la">')[1]
                self.assertGreaterEqual(len(latin.split()), 3, ref)
        self.assertEqual(seen, 44)

    def test_one_or_more_is_asked_in_a_sentence_after_lesson_4(self):
        for ref in di_run.all_refs():
            raw, n = di_run.resolve(ref)
            if isinstance(raw, str) and raw.startswith("F3 ") and not ref.startswith("4/C/"):
                self.assertIn("**", raw, ref)

    def test_every_lesson_says_why(self):
        for L in di_run.load()["lessons"]:
            self.assertTrue(L.get("today"), L["n"])
            info = di_run.intro(di_run.new_state(L["n"], "full", "x", 1))
            self.assertTrue(all(p["why"] for p in info["parts"]), L["n"])
            self.assertNotIn("new ending", " ".join(p["why"] for p in info["parts"] if L["n"] in (0, 5, 12)).lower())

    def test_lesson_5_keeps_its_new_words_and_reviews_eight(self):
        for run in range(1, 6):
            st = di_run.new_state(5, "full", "x", run, missed_words={"stēlla"})
            words = [e["r"].split("/")[-1] for e in st["seq"] if e["p"] == "A"]
            self.assertEqual(len(words), 12)
            self.assertTrue({"patria", "fāma", "vīta", "nōn", "stēlla"} <= set(words))

    def test_lesson_12_is_shorter(self):
        st = di_run.new_state(12, "full", "x", 1)
        self.assertEqual(sum(1 for e in st["seq"] if e["p"] == "A"), 10)
        self.assertLess(len(st["seq"]), 85)

    def test_every_sound_is_on_the_recording_list(self):
        keys = {c["key"] for c in di_run.clips()}
        for ref in di_run.all_refs():
            for st in di_run.steps_for(ref):
                text = di_run._audio_of(st)
                if text:
                    self.assertIn(di_run.clip_key(text), keys, (ref, text))
        # every word a capped review might draw, too
        for w in di_run.words_taught(di_run.LAST):
            for st in di_run.steps_for("12/A/w/%s" % w):
                self.assertIn(di_run.clip_key(di_run._audio_of(st)), keys, w)
        self.assertEqual(len(keys), len(di_run.clips()))

    def test_no_screen_says_mastery(self):
        for ref in di_run.all_refs():
            self.assertNotIn("master", json.dumps(di_run.steps_for(ref)).lower(), ref)


class TestRunner(unittest.TestCase):
    def test_every_lesson_ends_ready_when_all_right(self):
        for n in range(13):
            state = di_run.new_state(n, "full", "403217", 1)
            run_through(state)
            self.assertTrue(state["done"]["ready"], n)
            self.assertEqual(state["done"]["set"], "A")

    def test_a_miss_brings_model_test_back_up_and_delayed(self):
        state = di_run.new_state(3, "full", "403217", 1)
        target = []

        def miss(e, st, k):
            if not target and e["p"] == "B" and st["kind"] in ("choice", "tap") and not e.get("f"):
                target.append(e["r"])
                return True
            return False
        events = run_through(state, miss)
        flags = [ev["flag"] for ev in events if ev["ref"] == target[0]]
        self.assertEqual(flags[0], "")
        self.assertIn("test", flags)
        self.assertIn("backup", flags)
        self.assertIn("delayed", flags)
        self.assertTrue(events[[ev["ref"] for ev in events].index(target[0])]["corrected"])
        # the delayed test comes 3-6 items after the missed one
        refs = [ev["ref"] + ev["flag"] for ev in events]
        i, j = refs.index(target[0] + "backup"), refs.index(target[0] + "delayed")
        self.assertTrue(3 <= j - i <= 6, j - i)
        self.assertTrue(state["done"]["ready"])

    def test_a_student_who_keeps_missing_still_reaches_the_check(self):
        state = di_run.new_state(7, "full", "403217", 1)
        run_through(state, miss=lambda e, st, k: e["p"] != "F")
        self.assertTrue(state["done"]["ready"])
        self.assertLess(len(json.dumps(state)), 60000)

    def test_two_misses_in_the_check_is_again(self):
        state = di_run.new_state(5, "full", "403217", 1)
        seen = []

        def miss(e, st, k):
            if e["p"] == "F" and e["r"] not in seen and len(seen) < 2:
                seen.append(e["r"])
                return True
            return False
        run_through(state, miss)
        self.assertFalse(state["done"]["ready"])
        self.assertEqual(state["done"]["score"], 6)

    def test_one_miss_in_the_check_is_still_ready(self):
        state = di_run.new_state(5, "full", "403217", 1)
        seen = []

        def miss(e, st, k):
            if e["p"] == "F" and not seen:
                seen.append(e["r"])
                return True
            return False
        run_through(state, miss)
        self.assertTrue(state["done"]["ready"])

    def test_again_reruns_examples_and_look_alikes_then_set_b(self):
        state = di_run.new_state(4, "again", "403217", 2, check_set="B")
        parts = []
        for e in state["seq"]:
            if e["p"] not in parts:
                parts.append(e["p"])
        self.assertEqual(parts, ["I", "B", "C", "F"])          # I: the "Today" screen
        self.assertTrue(all("/F/B/" in e["r"] for e in state["seq"] if e["p"] == "F"))

    def test_the_check_alone(self):
        state = di_run.new_state(6, "check", "403217", 1)
        self.assertEqual({e["p"] for e in state["seq"]}, {"I", "F"})

    def test_placement(self):
        state = di_run.new_state(0, "placement", "403217", 1)
        run_through(state)
        self.assertEqual(state["done"], {"kind": "placement", "lesson": 12})
        state = di_run.new_state(0, "placement", "403217", 1)
        run_through(state, miss=lambda e, st, k: e["r"] == "P/4")
        self.assertEqual(state["done"]["lesson"], 3)
        self.assertEqual(di_run.placement_lesson([0, 9]), 0)

    def test_slow_right_answer_comes_back_without_a_correction(self):
        state = di_run.new_state(1, "full", "403217", 1)
        for _ in range(200):
            e, steps, k = di_run.current(state)
            st = steps[k]
            if st["kind"] == "choice" and st.get("fmt") in di_run.ONE_TAP and len(steps) == 1 and e["p"] != "F":
                break
            di_run.answer(state, right_value(st), 1000)
        ref = e["r"]
        _, out = di_run.answer(state, right_value(st), 9000)
        self.assertTrue(out["event"]["slow"])
        self.assertFalse(out["event"].get("corrected"))
        later = [x for x in state["seq"][state["pos"]:] if x["r"] == ref]
        flags = [x.get("f") for x in later]
        self.assertIn("slow", flags)
        self.assertFalse({"test", "backup", "delayed"} & set(flags))

    def test_the_state_is_small(self):
        state = di_run.new_state(12, "full", "403217", 1)
        self.assertLess(len(json.dumps(state)), 6000)


class TestEngagement(unittest.TestCase):
    def test_a_right_answer_cheers_and_counts_the_streak(self):
        state = di_run.new_state(2, "full", "x", 1)
        streaks = []
        for _ in range(400):
            e, steps, k = di_run.current(state)
            if e is None or e["p"] == "F":
                break
            st = steps[k]
            state, out = di_run.answer(state, right_value(st), 1000)
            if st["kind"] in ("choice", "tap", "type"):
                self.assertIsNotNone(out["cheer"])
                if out["cheer"]["size"] == "item":
                    streaks.append(out["cheer"]["streak"])
        self.assertEqual(streaks, list(range(1, len(streaks) + 1)))
        self.assertEqual(state["best"], len(streaks))

    def test_a_miss_resets_the_streak_and_gets_no_cheer(self):
        state = di_run.new_state(2, "full", "x", 1)
        state["streak"] = state["best"] = 4
        while True:
            e, steps, k = di_run.current(state)
            if steps[k]["kind"] == "choice":
                break
            di_run.answer(state, di_run.NEXT)
        state, out = di_run.answer(state, wrong_value(steps[k]), 1000)
        self.assertIsNone(out["cheer"])
        self.assertEqual(state["streak"], 0)
        self.assertEqual(state["best"], 4)

    def test_the_check_gives_no_cheer(self):
        state = di_run.new_state(3, "check", "x", 1)
        di_run.answer(state, di_run.NEXT)                    # the Today screen
        e, steps, k = di_run.current(state)
        _, out = di_run.answer(state, right_value(steps[k]), 1000)
        self.assertIsNone(out["cheer"])

    def test_the_table_fills_in_lesson_by_lesson(self):
        pr = {"ready": {0, 1, 2, 3}, "placed": 0}
        t = di_run.table(pr)
        self.assertEqual(t["filled"], 3)
        rows = {r["job"]: r for r in t["rows"]}
        self.assertEqual((rows["Subject"]["sg"], rows["Direct object"]["pl"]), ("-a", "-ās"))
        self.assertIsNone(rows["Subject"]["pl"])
        t = di_run.table(pr, new=[4])
        self.assertTrue({r["job"]: r for r in t["rows"]}["Subject"]["pl_new"])
        # placed at Lesson 6: Lessons 0-5 count as known
        self.assertEqual(di_run.table({"ready": set(), "placed": 6})["filled"], 4)
        everything = di_run.table({"ready": set(range(13)), "placed": 0})
        self.assertEqual(everything["filled"], 10)
        self.assertEqual(sum(len(c) for c in di_run.LESSON_CELLS.values()), 10)

    def test_the_parts_bar(self):
        st = di_run.new_state(7, "full", "x", 1)
        self.assertEqual([b["state"] for b in di_run.parts_bar(st)], ["todo"] * 6)
        st["pos"] = next(i for i, e in enumerate(st["seq"]) if e["p"] == "C")
        bar = di_run.parts_bar(st)
        self.assertEqual([b["part"] for b in bar], ["A", "B", "C", "D", "E", "F"])
        self.assertEqual([b["state"] for b in bar], ["done", "done", "now", "todo", "todo", "todo"])


class TestProgress(unittest.TestCase):
    def ev(self, item, result, t=1):
        return {"item_id": item, "result": result, "context": "di", "student_id": "403217",
                "timestamp": t, "latency_ms": 0, "response": "{}"}

    def test_ready_opens_the_next_lesson(self):
        pr = di_run.progress([self.ev("di:placement", "L0"), self.ev("di:check:0", "ready")])
        self.assertEqual(pr["unlocked"], 1)
        self.assertEqual(pr["lessons"][0]["state"], "ready")
        self.assertEqual(pr["lessons"][1]["state"], "current")
        self.assertEqual(pr["lessons"][2]["state"], "locked")

    def test_placement_leaves_earlier_lessons_open(self):
        pr = di_run.progress([self.ev("di:placement", "L4")])
        self.assertEqual([l["state"] for l in pr["lessons"][:6]], ["open"] * 4 + ["current", "locked"])

    def test_two_agains_in_a_row_flags_the_student(self):
        evs = [self.ev("di:placement", "L0"), self.ev("di:check:0", "again"), self.ev("di:check:0", "again")]
        rep = di_run.report(evs, ["403217"])
        self.assertEqual(rep["students"][0]["flag"], [0])
        self.assertEqual(rep["students"][0]["current"], 0)
        evs.append(self.ev("di:check:0", "ready"))
        self.assertEqual(di_run.report(evs, ["403217"])["students"][0]["flag"], [])

    def test_missed_items_come_back(self):
        evs = [self.ev("di:3/B/test/1", "wrong"), self.ev("di:4/D/2/C/1", "wrong"),
               self.ev("di:check:3", "again")]
        self.assertEqual(di_run.missed_refs(evs), {"3/B/test/1", "2/C/1"})


class TestNotHomework(unittest.TestCase):
    def test_di_answers_are_left_out(self):
        import rush
        import teacher
        self.assertIn("di", teacher.NOT_HOMEWORK)
        self.assertIn('"di"', open(rush.__file__, encoding="utf-8").read())


# --------------------------------------------------------------------------
# The routes
# --------------------------------------------------------------------------

class TestRoutes(unittest.TestCase):
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

    def turn_on(self):
        r = self.teacher.post("/teacher/di", data={"on": "yes"})
        self.assertEqual(r.status_code, 302)

    def state(self):
        return store.get_setting(self.db, "di_run:403217")

    def test_hidden_until_the_teacher_turns_it_on(self):
        self.assertEqual(self.student.get("/di").status_code, 404)
        self.assertNotIn("/di\"", self.student.get("/").get_data(as_text=True))
        self.turn_on()
        self.assertEqual(self.student.get("/di").status_code, 200)
        self.assertIn("Steps", self.student.get("/").get_data(as_text=True))

    def test_the_teacher_can_try_it_while_it_is_off(self):
        self.teacher.post("/teacher/student-mode")
        r = self.teacher.get("/di")
        self.assertEqual(r.status_code, 200)
        self.assertIn("DI mode is off for students", r.get_data(as_text=True))

    def test_a_student_cannot_reach_the_teacher_pages(self):
        self.turn_on()
        for url in ("/teacher/di", "/teacher/di/lesson/3"):
            r = self.student.get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn("/login", r.headers["Location"])
        self.student.post("/teacher/di", data={"on": "no"})
        self.assertTrue(store.get_setting(self.db, "di_on"))

    def test_teacher_pages(self):
        self.turn_on()
        r = self.teacher.get("/teacher/di")
        self.assertEqual(r.status_code, 200)
        self.assertIn("403217", r.get_data(as_text=True))
        for n in range(13):
            r = self.teacher.get("/teacher/di/lesson/%d" % n)
            self.assertEqual(r.status_code, 200, n)
        self.assertEqual(self.teacher.get("/teacher/di/lesson/13").status_code, 404)

    def test_a_locked_lesson_cannot_be_started(self):
        self.turn_on()
        self.student.post("/di/skip-placement")
        self.student.post("/di/start", data={"n": "5"})
        self.assertIsNone(self.state())

    def answer_all(self, miss_check=0):
        missed = 0
        for _ in range(2000):
            st = self.state()
            e, steps, k = di_run.current(st)
            if e is None:
                return st
            s = steps[k]
            v = right_value(s)
            if e["p"] == "F" and missed < miss_check and s["kind"] in ("choice", "tap"):
                v = wrong_value(s)
                missed += 1
            r = self.student.post("/di/answer", data={"pos": st["pos"], "step": st["step"],
                                                      "v": v, "latency_ms": "1200"})
            self.assertEqual(r.status_code, 302)
        raise AssertionError("never ended")

    def test_a_whole_lesson_then_again_then_ready(self):
        self.turn_on()
        self.student.post("/di/skip-placement")
        self.student.post("/di/start", data={"n": "0"})
        page = self.student.get("/di/lesson").get_data(as_text=True)
        self.assertIn("Lesson 0", page)
        self.assertIn("Today, in order", page)
        self.assertIn("Why so many taps?", page)
        st = self.answer_all(miss_check=2)
        self.assertFalse(st["done"]["ready"])
        self.assertGreater(st["best"], 5)
        page = self.student.get("/di/lesson").get_data(as_text=True)
        self.assertIn("Again", page)
        for word in ("mastery", "score", "/8", "wrong"):
            self.assertNotIn(word, page.lower())
        self.student.post("/di/next")
        st = self.state()
        self.assertEqual(st["mode"], "again")
        self.assertEqual(st["set"], "B")
        st = self.answer_all()
        self.assertTrue(st["done"]["ready"])
        page = self.student.get("/di/lesson").get_data(as_text=True)
        self.assertIn("Ready", page)
        self.assertIn("data-confetti", page)
        self.student.post("/di/next")
        self.assertIsNone(self.state())
        page = self.student.get("/di").get_data(as_text=True)
        self.assertIn("Run it again", page)
        events = [e for e in store.events_for_student(self.db, "403217") if e["context"] == "di"]
        checks = [e["result"] for e in events if e["item_id"] == "di:check:0"]
        self.assertEqual(checks, ["again", "ready"])
        self.assertTrue(all(e["context"] == "di" for e in events))

    def test_a_right_answer_shows_a_cheer_once(self):
        self.turn_on()
        self.student.post("/di/skip-placement")
        self.student.post("/di/start", data={"n": "0"})
        st = self.state()
        self.student.post("/di/answer", data={"pos": st["pos"], "step": st["step"], "v": "next"})  # Today
        for _ in range(30):
            st = self.state()
            e, steps, k = di_run.current(st)
            if steps[k]["kind"] in ("choice", "tap"):
                break
            self.student.post("/di/answer", data={"pos": st["pos"], "step": st["step"], "v": "next"})
        self.student.post("/di/answer", data={"pos": st["pos"], "step": st["step"],
                                              "v": right_value(steps[k]), "latency_ms": "900"})
        self.assertIn('class="di-cheer', self.student.get("/di/lesson").get_data(as_text=True))
        self.assertNotIn('class="di-cheer', self.student.get("/di/lesson").get_data(as_text=True))

    def test_the_home_page_shows_the_table(self):
        self.turn_on()
        self.student.post("/di/skip-placement")
        page = self.student.get("/di").get_data(as_text=True)
        self.assertIn("Your table", page)
        self.assertIn("0 of 10 endings", page)

    WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 200

    def test_recording_page_is_the_teachers(self):
        r = self.student.get("/teacher/di/audio")
        self.assertIn("/login", r.headers.get("Location", ""))
        key = di_run.clips()[0]["key"]
        self.student.post("/teacher/di/audio/save?key=" + key, data=self.WAV)
        self.assertEqual(store.word_audio_versions(self.db), {})
        page = self.teacher.get("/teacher/di/audio").get_data(as_text=True)
        self.assertIn('<strong id="nrec">0</strong> of %d recorded' % len(di_run.clips()), page)

    def test_record_a_clip_and_students_hear_it(self):
        self.turn_on()
        self.student.post("/di/skip-placement")
        self.student.post("/di/start", data={"n": "1"})          # locked: nothing starts
        self.student.post("/di/start", data={"n": "0"})
        st = self.state()
        # walk to the first screen with audio
        for _ in range(60):
            e, steps, k = di_run.current(st)
            text = di_run._audio_of(steps[k]) if steps[k]["kind"] != "intro" else None
            if text:
                break
            self.student.post("/di/answer", data={"pos": st["pos"], "step": st["step"], "v": right_value(steps[k])})
            st = self.state()
        key = di_run.clip_key(text)
        self.assertIn(key, {c["key"] for c in di_run.clips()})
        self.assertNotIn("/audio/" + key, self.student.get("/di/lesson").get_data(as_text=True))
        r = self.teacher.post("/teacher/di/audio/save?key=" + key, data=self.WAV)
        self.assertEqual(r.status_code, 200)
        page = self.student.get("/di/lesson").get_data(as_text=True)
        self.assertIn("/audio/" + key, page)
        url = page.split('data-src="')[1].split('"')[0].replace("&amp;", "&")
        got = self.student.get(url)
        self.assertEqual((got.status_code, got.data[:4]), (200, b"RIFF"))
        # deleting it brings the computer voice back
        self.teacher.post("/teacher/di/audio/delete", data={"key": key})
        self.assertNotIn("/audio/" + key, self.student.get("/di/lesson").get_data(as_text=True))

    def test_only_real_clips_and_real_recordings_are_saved(self):
        key = di_run.clips()[5]["key"]
        self.assertEqual(self.teacher.post("/teacher/di/audio/save?key=di-nothing", data=self.WAV).status_code, 404)
        self.assertEqual(self.teacher.post("/teacher/di/audio/save?key=" + key, data=b"not a wav").status_code, 400)
        self.assertEqual(store.word_audio_versions(self.db), {})

    def test_recordings_of_old_text_can_be_cleared(self):
        store.save_word_audio(self.db, "di-0123456789abcdef0123", "audio/wav", self.WAV)
        key = di_run.clips()[3]["key"]
        store.save_word_audio(self.db, key, "audio/wav", self.WAV)
        store.save_word_audio(self.db, "puella", "audio/wav", self.WAV)          # a vocabulary word: kept
        page = self.teacher.get("/teacher/di/audio").get_data(as_text=True)
        self.assertIn("1 recording of sentences no lesson uses any more", page)
        self.teacher.post("/teacher/di/audio/clear-unused")
        self.assertEqual(set(store.word_audio_versions(self.db)), {key, "puella"})

    def test_a_stale_page_answers_nothing(self):
        self.turn_on()
        self.student.post("/di/skip-placement")
        self.student.post("/di/start", data={"n": "0"})
        before = self.state()
        self.student.post("/di/answer", data={"pos": before["pos"] + 3, "step": 0, "v": "next"})
        self.assertEqual(self.state()["pos"], before["pos"])

    def test_placement_through_the_app(self):
        self.turn_on()
        self.student.post("/di/start", data={"mode": "placement"})
        st = self.answer_all()
        self.assertEqual(st["done"]["lesson"], 12)
        self.student.post("/di/next")
        pr = di_run.progress(store.events_for_student(self.db, "403217"))
        self.assertEqual(pr["placed"], 12)
        # placement is taken once
        self.student.post("/di/start", data={"mode": "placement"})
        self.assertIsNone(self.state())

    def test_the_purge_forgets_runs(self):
        import backup
        self.turn_on()
        self.student.post("/di/skip-placement")
        self.student.post("/di/start", data={"n": "0"})
        self.assertIsNotNone(self.state())
        removed = backup.purge_students(self.db)
        self.assertEqual(removed.get("di_runs"), 1)
        self.assertIsNone(self.state())


if __name__ == "__main__":
    unittest.main()
