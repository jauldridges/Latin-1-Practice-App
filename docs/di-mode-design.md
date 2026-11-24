# DI Mode: Design Document

Latin I practice app · Libertas Academy · as built, Tuesday November 24, 2026

This is the plan "DI Mode: First Declension Strand, Lessons 0–12", rewritten to match what is now built
and running in the app, with every change since the first plan folded in. It is written to be dropped into a
new conversation to plan **the rest of DI mode as a standalone course**: the first declension is one strand, and
the next job is the scope and sequence it sits inside. Section 13 is the brief for that conversation.

Changes from the first plan are marked **Changed:** or **New:** where they appear.

---

## 1. What this mode is

DI mode is a second mode inside the practice app. Practice mode stays as it is: cards, solid / shaky / not yet,
nothing graded. DI mode **teaches**. It introduces each new ending, corrects every error the same way, and opens
the next lesson only after the student passes the current lesson's check.

DI mode grades nothing. It doesn't post to the gradebook, count toward homework, or use the word "mastery."
Students see two outcomes at a lesson check: **Ready** (the next lesson opens) or **Again** (the lesson reruns
with new items).

Students reach it from a tab called **Steps**. **New:** the teacher turns DI mode on and off for the whole class
(Teacher dashboard → DI mode); it starts off. The teacher can try every lesson as a student while it is off.

By the end of Lesson 12, students can name the job of every word in a simple sentence and read every
first-declension ending:

| | Singular | Plural |
|---|---|---|
| **Nominative** (subject) | -a | -ae |
| **Genitive** (possession: "of") | -ae | -ārum |
| **Dative** (to / for) | -ae | -īs |
| **Accusative** (direct object) | -am | -ās |
| **Ablative** (object of the preposition) | -ā | -īs |

The vocative is not part of this strand.

---

## 2. Order of the endings, and why

Unchanged from the first plan. Look-alike endings are kept apart until each is solid, then put side by side on
purpose.

| Lesson | New ending | Look-alike it is compared with |
|---|---|---|
| 0 | No Latin: verb, subject, direct object in English | subject vs direct object |
| 1 | -a (subject, nominative) | none |
| 2 | -am (direct object, accusative) | -a |
| 3 | -ās (direct object, plural) | -am |
| 4 | -ae (subject, plural) + verb -nt | -a, -ās |
| 5 | Firm-up: the four endings so far | all four |
| 6 | -ārum (possession, plural) | -ās |
| 7 | -ae (possession, singular) | -ae subject |
| 8 | -īs (to / for, plural) | -ās, -ārum |
| 9 | -ae (to / for, singular) | -ae subject, -ae possession |
| 10 | -ā (object of the preposition, singular) | -a subject |
| 11 | -īs (object of the preposition, plural) | -īs to / for |
| 12 | Whole table + reading | everything |

Each job is taught in English before any Latin ending is attached to it: verb, subject and direct object in
Lesson 0, possession in Lesson 6, to / for in Lesson 8, object of the preposition in Lesson 10. Unique endings
come first: -a, -am, -ās, -ārum. The three jobs of -ae arrive one at a time (Lessons 4, 7, 9), as do the two
jobs of -īs (Lessons 8, 11) and the -a / -ā pair (Lessons 1, 10).

---

## 3. How a lesson runs

About 15 minutes, in six parts, always in the same order. Lessons 6, 8 and 10 add a short Part B1, **The job in
English**, before the new ending.

| Part | Name | What happens |
|---|---|---|
| — | **Today** (**New**) | One screen: the lesson's reason in one sentence, each part with what it's for and how many screens, and why there are so many taps |
| A | Words | New and review vocabulary, meaning only |
| B1 | The job in English | Lessons 6, 8, 10 only: the new job taught with English sentences |
| B | New ending | Model → Echo → Test → Example sequence |
| C | Look-alikes | Sort the new ending against the one it is most often confused with |
| D | Review | Items from earlier lessons, mixed |
| E | Sentences | Step-by-step reading, then choose the translation |
| F | Lesson check | Fresh items, no help, decides Ready or Again |

**Part B sequence:** Model (one screen with audio: the ending, its job, one example) → Echo (audio plays a form,
the student taps the ending; new endings only) → Test (the Model's example, alone) → Example sequence (minimal
pairs, varied examples, at least one earlier item).

**Delayed tests.** Each lesson names one hardest item. It comes back 3–6 items later in Part E, and again in the
next lesson's Part D.

**The why, on screen (New).** The teacher found Lesson 12 a lot of clicking with no clear reason, so:

- The **Today** screen opens every run. Each lesson has a one-sentence reason (in Appendix C), e.g. Lesson 7:
  "-ae already marks a subject that is more than one. Today it gets a second job, possession, and the verb tells
  you which job it has." It ends: "Why so many taps? Each one is a decision you make every time you read Latin:
  find the verb, find the subject, read each ending's job, put it together. Doing them one at a time now is what
  makes reading fast later."
- Each part's reason shows in a box on its first screen, e.g. Part C: "Endings that look alike. This is where
  mistakes happen, so you practice telling them apart."
- Every question has one grey line above it saying why that step comes where it does, e.g. on "Tap the verb":
  "Start with the verb: -t means look for one subject, -nt more than one." (Before Lesson 4: "Start with the
  verb: it says what happens, and the subject has to fit it.")

**Length (Changed).** Lesson 5 and Lesson 12 reviewed every word so far in Part A (27 and 40 screens). They now
review 8 (Lesson 5, plus its 4 new words) and 10 (Lesson 12), the student's missed words first. Lesson 12 went
from 106 screens to 77; Lesson 5 from 82 to 67 (both counting the Today screen). Other lessons run 37–69 screens.

---

## 4. Answer formats

All answers are taps except the typed format, which appears only in lesson checks from Lesson 5 on.

| Code | Name | Screen | Student does |
|---|---|---|---|
| F1 | Meaning | Latin word | Taps 1 of 3 English meanings |
| F2 | Job | Sentence with one word highlighted | Taps the job button |
| F3 | How many | **Changed:** the word highlighted in a sentence | Taps **One** or **More than one** |
| F4 | Build | **Changed:** an English sentence with the target in bold, and the Latin sentence with the word's stem and a blank | Taps the ending |
| F5 | Verb match | Sentence with the verb's stem and a blank | Taps **-t** or **-nt** |
| F6 | Sentence steps | Full Latin sentence | Taps the verb, taps the subject, names the job of each other noun, then picks 1 of 3 translations |
| F7 | Echo | Audio only | Taps the ending heard |
| F8 | Type | Latin sentence, or (F8E) the F4 screen | Types the translation or the ending. Macrons not required |

**F4 in context (Changed).** The first plan's build items were a cue and a stem ("of the gate · port-"). Every
one is now a sentence, e.g. *The farmer watches the road **of the gate**.* / *Agricola viam port___ spectat.*
The app checks that each Latin sentence, filled in, translates to exactly its English. All 44 use only words the
lesson has taught (not *locus … est ignōtus*-style words outside the strand).

**F3 in context (Changed).** "One or more than one?" is asked about a word in a sentence, except Lesson 4's
look-alikes, where each is paired with picking the verb ending on the next screen.

**F5 (Changed).** A verb shown without its ending keeps its stem vowel: *porta___*, not *port___* (which made
"portt"). Every verb in the strand is first conjugation.

**F7 (unchanged).** Echo plays a single word; hearing an ending inside a whole sentence is much harder.

**Job buttons (F2, F6)** appear only from their lesson: Verb, Subject, Direct object (L0 in English; case name
from L1 / L2), Possession (L6), To / for (L8), Object of the preposition (L10). Lesson 0 also has **No direct
object**. **Ending buttons** (F4, F7) appear once taught: -a, -am, -ās, -ae, -ārum, -īs, -ā.

**Translation choices** are always three: correct; subject and object swapped (with *cum*, the subject and the
*cum* object; with a lone subject, "Someone ___ the X"); and one that changes one thing only (a dative -ae read as
possession, else the number of one word, else adding or dropping *nōn*). The order is fixed per item.

---

## 5. Correction (same every time)

On any wrong answer outside a check:

1. **Model.** The correct answer, one rule line, audio. No red X, no sound effect, no "wrong."
2. **Test.** The same item again, straight away.
3. **Back up.** The two items before it, plus the missed item.
4. **Delayed test.** The missed item returns 3–6 items later, and in the next lesson's Part D.

**Changed:** a miss on the back-up or delayed item gets the model and one test; a miss on the test itself gets the
model only and the lesson moves on (its delayed test is already queued). Without this, a student tapping at random
could make a lesson run forever.

**Slow answers.** A right answer slower than 6 seconds on a one-tap item (F1, F2, F3, F5, F7) gets no correction
and comes back later in the lesson. F6 and F8 have no time limit.

**Typed answers.** English is accepted with or without articles, "to / for" either way, possessives either way
("the girl's"), and is marked "Close: check your spelling" (try again) within two letters. Endings need no macrons.

---

## 6. Lesson check and moving on

- Part F has 8 fresh items, Set A. **7 of 8 right on the first try → Ready.** Lesson 12's check is 16 items, 14
  to pass.
- Below → **Again**: Part B's example sequence and Part C once more, then Set B (then A, alternating).
- Two Agains in a row on a lesson → the lesson stays open and the teacher view flags the student.
- No correction and no cheer during a check: it gives no help.
- **Placement**, offered once before Lesson 0 (or skipped), 18 items, no help. **Changed:** the first plan's rule
  stopped at item 14; item 15 (*cum fēminā*) sends a miss to Lesson 10 and item 16 (*fāmam patriae*) to Lesson 7.
  Skipped lessons stay open with "Take its check" or "Do the lesson."

---

## 7. Writing rules for items

Unchanged, and enforced by the engine (Appendix A):

1. One sensible reading.
2. Genitive -ae comes right after its noun, with *spectat, laudat, amat* (and *vocat*); dative -ae comes before
   the object, with *nārrat, parat, portat, servat*. -ārum also follows its noun.
3. Every sentence names its subject.
4. A plural -ae subject always has a verb in -nt; never two -ae words that could both be the subject.
5. Minimal pairs differ in one ending only.
6. From Lesson 2, at least one sentence in three puts the object first.
7. Earlier endings in every new set.
8. Macrons in print; audio for every Latin item; students never type macrons.

---

## 8. Words used

Unchanged. Nouns: aqua, terra, via, porta, īnsula, silva, puella, fēmina, nauta, agricola, patria, fāma, vīta,
lūna, stēlla, fābula. Verbs (3rd person, first conjugation): amat, laudat, portat, vocat, spectat, nārrat, parat,
servat, pugnat. Also in, cum, ē / ex, ā / ab, et, nōn.

| Lesson | New words |
|---|---|
| 1 | puella, fēmina, nauta, agricola, aqua · vocat, spectat, portat, amat, laudat |
| 2 | terra, silva, porta, via, īnsula |
| 3 | lūna, stēlla · et |
| 4 | the -nt forms of the five verbs |
| 5 | patria, fāma, vīta · nōn |
| 8 | fābula · nārrat, parat |
| 9 | servat |
| 10 | in, cum, ē / ex, ā / ab · pugnat |

---

## 9. Audio

**Changed:** the teacher records every clip (Teacher dashboard → DI mode → Record DI mode in your voice): 461 for
this strand — 374 sentences, 73 words, 13 model screens read whole, and the Lesson 12 reading — listed in the order
students meet them. A clip not yet recorded uses the browser's speech (an Italian voice for Latin, which cannot
tell -a from -ā). Editing a sentence's text asks for a new recording. Echo items have a text fallback for a device
with neither. A new strand adds its own clips to the same list.

---

## 10. Engagement (New)

Added after the first teacher run-through ("more engaging for kids"):

- **A cheer on every right answer** (outside checks): a green check that pops and fades in about a second, with a
  word ("Yes!", "Got it.", "Exactly." …). From three in a row it shows the streak ("4 in a row"); every fifth in a
  row adds a burst of confetti. A miss quietly resets the streak, with no message.
- **Parts bar.** The progress bar is split into the run's parts (A–F), each filling as the student goes and
  turning into a check when done, so a student sees "two parts left," not just a bar.
- **Your table.** The first-declension table (Section 1) is on the Steps page with every cell a "?" at first. Each
  Ready fills its lesson's cell (placement fills the ones it skipped); the Ready screen shows the new cell popping
  in, with confetti. "6 of 10 endings."
- **Longest streak** on the Ready and Again screens ("Your longest run of right answers this time: 9 in a row").
- Nothing moves for a student whose device asks for reduced motion. No sound effects (classrooms).

Not built, as options: DI lessons feeding the planned practice creature (owl / goose / wolf); a table for each
later strand (second declension, verb endings…) filling in the same way; a class-wide "endings unlocked" count on
the teacher's screen.

---

## 11. What the app records

Each answer is an event (context `di`, kept out of homework, rushing and every class figure): lesson and part,
item and format, first try or not, time, whether a correction ran, whether it was a delayed test or a slow
re-ask. Each check is a `di:check:<lesson>` event: Ready or Again, Set A or B, score. The placement is a
`di:placement` event with its lesson. A run in progress is saved on the server, so a student can stop and resume
on another device. The end-of-year purge removes all of it. As everywhere in the app, a student is an ID number
only.

---

## 12. Teacher view

Teacher dashboard → DI mode:

- **On / off switch** for the class, and a list of content problems if the lesson file has any.
- **By student:** current lesson (and where they placed), checks passed, Agains, a flag after two Agains in a row,
  minutes this week.
- **By lesson:** median time, Ready rate on the first check, most-missed item, and a warning when an example
  sequence runs below 70% first try ("too hard or too fast").
- **By item:** first-try rate across students; flagged below 50% ("rewrite it, or add steps before it") and above
  95% in Parts B and C ("teaches nothing new").
- **Read a lesson:** every screen of a lesson in order with its answer in bold, including the translations and
  wrong choices the app wrote.

---

## 13. Next: DI mode as a standalone course (the brief for this conversation)

The first declension is built and works as one **strand**. The goal now is a scope and sequence for DI mode as a
course a student could work through on their own, with the first declension in its place inside the larger
language. What the plan needs to settle:

1. **What "standalone" means here.** A complete Latin I a student could learn from DI mode alone, or a teaching
   track that runs beside class and the practice app (Appendix B is the class's real sequence and dates)? Can a
   student be ahead of class in DI mode, or does it unlock week by week?
2. **The strands, in order, with prerequisites.** Likely candidates: verbs first (person and number: -ō/-m, -s,
   -t, -mus, -tis, -nt; first and second conjugation; *sum*), second declension (and the neuter rule), adjective
   agreement, third declension, the ablative's uses, imperfect and future, the perfect system, pronouns, the
   passive, participles. The class already taught Units 1–3 out of this order (Appendix B): the first declension
   all at once with the second, verbs in week 2. DI's job-by-job order is different on purpose; the plan should
   say how the two fit.
3. **Interleaving across strands.** Does a later strand's Part D review earlier strands? Does Lesson 1 of the
   second declension put -us next to -a on purpose? When does a "whole system" lesson (like Lesson 12) come?
4. **Vocabulary.** DI uses a small closed word list per strand; class uses weekly lists (164 words through Week
   13). Does DI teach its own words, borrow the class's, or both?
5. **Placement.** One placement per strand, or one course-level placement that routes a student to a strand and
   lesson?
6. **Reading.** Each strand ends with a short reading. Is there a reading strand of its own (connected reading)
   that grows across the course?
7. **The NLE** (March 8–12, 2027): which strands must be done by then?
8. **Feasibility.** Appendix A says what is cheap to build (new lessons on the existing engine) and what needs
   engine work (new kinds of forms or sentences). The plan should mark each strand's new engine needs.

**What to produce:** a strand-by-strand map. For each strand: its lessons in order, each lesson's new form or job,
the look-alike it is compared with, its new words, which earlier strands it needs, which answer formats it uses,
and any new format or engine need. Then, one strand at a time, a lesson-by-lesson plan in the shape of Appendix C,
which can be brought back to the code session to build.

---

## Appendix A. How a strand is built in the app

So a plan stays buildable. Python / Flask, server-rendered pages, no build step, works on a school Chromebook.

- **One file per strand.** A strand is a YAML file of lessons (`di/first-declension.yaml`). Each screen is one
  line: a format code and the Latin (Appendix C shows them). Model screens are short text with audio.
- **The engine reads the Latin.** `di.py` knows a closed word list and the strand's rules. From a Latin sentence
  it works out each word's job, the English translation, the two wrong translation choices, and the one-line rule
  for each correction. A content check fails a lesson whose Latin doesn't parse, uses an untaught word, or (F4)
  doesn't say what its English says. This is why one item is one line, and why the teacher can read every screen
  before students see it.
- **Reused by every strand, no new work:** the lesson runner (parts, Today screen, why lines), the correction
  routine, slow re-asks, delayed tests, Ready / Again with two check sets, placement, the teacher view, the cheer,
  streaks and parts bar, recording, on / off.
- **Cheap:** new lessons and items using forms the engine already reads; new words of a kind it knows (another
  first-declension noun, another first-conjugation verb in the 3rd person).
- **Needs engine work first (then cheap again):**
  - a new declension's endings, especially ones shared between cases (second declension -ī, -ō, -um; third
    declension's unpredictable nominatives; neuters where nominative = accusative);
  - verbs in persons other than the 3rd, other conjugations, *sum*, other tenses (the parser assumes -t / -nt);
  - adjectives (agreement with a noun of another declension: *nauta bonus*);
  - new sentence shapes: two clauses beyond *et*, infinitives, relative clauses, the passive, participles;
  - a "Your table" for the new strand (cheap once its cells are named).
- **Current limits worth planning around:** answers are taps, plus typing only in checks; every new sentence is a
  new recording for the teacher (about 460 for this strand; the computer voice covers what isn't recorded yet); every sentence names its subject (no understood "he / she") — a verb strand would have to change that;
  each lesson is about 15 minutes and 40–80 screens.
- **Fixed commitments:** no names (a student is an ID number); never "mastery" (solid / shaky / not yet in
  practice mode; Ready / Again in DI); nothing graded.

## Appendix B. The class's grammar sequence this year

From `latin1-spec.yaml` (the course's source of truth): every morphosyntax topic, by the week it is taught. The NLE (Introduction to Latin / Latin I) is March 8–12, 2027.

**Unit 0 · week of Monday August 24, 2026**

- MS-001 Latin alphabet — letter inventory and differences from English
- MS-002 Consonants c and g are always hard
- MS-003 Consonantal v (= w) and consonantal i (= y)
- MS-004 Consonant clusters — qu, gn, ch, ph, th
- MS-005 Vowel sounds — long and short a, e, i, o, u
- MS-006 Macrons — notation and what they mark
- MS-007 Diphthongs — ae, oe, au, ei, eu, ui
- MS-008 Syllable division
- MS-009 Syllable weight — long by nature and long by position
- MS-010 Stress accent — the penult rule

**Unit 1 · week of Monday September 7, 2026**

- MS-011 Inflection — endings carry grammatical function
- MS-012 Latin word order signals emphasis, not grammatical role
- MS-013 The concept of case
- MS-014 Nominative case — subject function
- MS-015 Accusative case — direct object function
- MS-016 Noun dictionary entry — nominative, genitive, gender
- MS-017 Finding a noun stem from the genitive singular
- MS-018 First declension — nominative singular
- MS-019 First declension — accusative singular
- MS-020 First declension — nominative plural
- MS-021 First declension — accusative plural
- MS-022 First declension gender — default feminine, masculine exceptions
- MS-159 Latin has no articles — the translator supplies a, an, or the

**Unit 1 · week of Monday September 14, 2026**

- MS-023 Second declension masculine in -us — nominative and accusative singular
- MS-024 Second declension masculine in -us — nominative and accusative plural
- MS-025 Second declension nouns in -er — stem behavior (puer vs ager)
- MS-026 Second declension neuter — nominative and accusative singular
- MS-027 Second declension neuter — nominative and accusative plural
- MS-028 The neuter rule — nominative equals accusative, plural in -a
- MS-029 Ambiguity of syncretic forms — using context to resolve
- MS-030 Verb person and number — the concept
- MS-031 Personal endings, active — o/m, s, t, mus, tis, nt
- MS-032 Verb dictionary entry — first two principal parts
- MS-033 Present stem from the second principal part
- MS-034 Present active indicative — first conjugation
- MS-035 Present active indicative — second conjugation
- MS-036 Distinguishing first from second conjugation by infinitive
- MS-037 Subject-verb agreement in person and number
- MS-038 Latin verbs carry their own subject — pronoun not required
- MS-039 Three English translations of the Latin present

**Unit 1 · week of Monday September 21, 2026**

- MS-040 sum — present indicative
- MS-041 Predicate nominative with linking verbs
- MS-042 First/second declension adjectives — forms in -us, -a, -um
- MS-043 Adjective agreement — case
- MS-044 Adjective agreement — number
- MS-045 Adjective agreement — gender
- MS-046 Adjective agreement across declensions (nauta bonus)
- MS-076 The infinitive — the second principal part, and its "to ___" translation
- MS-156 Infinitive stem versus present stem — why -re comes off
- MS-157 Complementary infinitive with debeo — completing the meaning of a verb

**Unit 1 · week of Monday September 28, 2026**

- MS-047 Attributive versus predicate position
- MS-048 Substantive adjectives
- MS-049 Vocative case — form and use
- MS-050 Imperative — singular and plural, first and second conjugation
- MS-051 Coordinating conjunctions — et, sed, -que, aut

**Unit 2 · week of Monday October 12, 2026**

- MS-052 Genitive case — possession function
- MS-053 First declension — genitive singular and plural
- MS-054 Second declension — genitive singular and plural
- MS-056 Genitive singular and nominative plural are identical in first declension

**Unit 2 · week of Monday October 19, 2026**

- MS-055 Genitive of the whole (partitive)

**Unit 2 · week of Monday October 26, 2026**

- MS-057 Dative case — indirect object function
- MS-058 First declension — dative singular and plural
- MS-059 Second declension — dative singular and plural
- MS-060 Dative with special verbs (credo, noceo, pareo, persuadeo)
- MS-061 Dative of possession with sum

**Unit 2 · week of Monday November 2, 2026**

- MS-062 Third declension — the genitive singular reveals the stem
- MS-063 Third declension masculine/feminine — nominative singular is unpredictable
- MS-064 Third declension masculine/feminine — singular endings
- MS-065 Third declension masculine/feminine — plural endings
- MS-070 Gender of third declension nouns must be learned, not deduced
- MS-071 Adjective agreement with third declension nouns

**Unit 2 · week of Monday November 9, 2026**

- MS-066 Third declension neuter — singular and plural
- MS-067 i-stem nouns — identifying them
- MS-068 i-stem nouns — genitive plural in -ium
- MS-069 Third declension i-stem neuters — -i, -ia, -ium
- MS-072 Present active indicative — third conjugation
- MS-073 Present active indicative — third conjugation -io verbs
- MS-074 Present active indicative — fourth conjugation
- MS-075 Identifying conjugation from the infinitive — all four
- MS-077 Imperative — third and fourth conjugation, and the irregulars dic, duc, fac, fer
- MS-078 Negative commands with noli / nolite plus infinitive
- MS-158 Infinitive forms of the third and fourth conjugations

**Unit 3 · week of Monday November 16, 2026**

- MS-079 Ablative case — the concept of a catch-all adverbial case
- MS-080 First declension — ablative singular and plural
- MS-081 Second declension — ablative singular and plural
- MS-082 Third declension — ablative singular and plural
- MS-083 Prepositions taking the ablative — in, sub, cum, sine, de, ex, ab, pro
- MS-084 Prepositions taking the accusative — ad, in, per, trans, prope, post, inter
- MS-085 in with ablative versus in with accusative
- MS-088 Ablative of accompaniment with cum
- MS-089 Ablative of means or instrument — no preposition
- MS-090 Distinguishing means from accompaniment

**Unit 3 · week of Monday November 30, 2026**

- MS-086 Ablative of place where
- MS-087 Ablative of place from which

**Unit 3 · week of Monday December 7, 2026**

- MS-091 Ablative of manner
- MS-092 Ablative of time when
- MS-093 Ablative of time within which

**Unit 3 · week of Monday December 14, 2026**

- MS-094 Imperfect tense — meaning and aspect
- MS-095 Imperfect active indicative — the -ba- marker, first and second conjugation
- MS-096 Imperfect active indicative — third and fourth conjugation
- MS-097 Imperfect of sum
- MS-098 Future active indicative — the -bi- marker, first and second conjugation
- MS-099 Future active indicative — the -a-/-e- marker, third and fourth conjugation
- MS-100 Future of sum
- MS-101 Distinguishing present, imperfect, and future by marker

**Unit 4 · week of Monday January 4, 2027**

- MS-102 All four principal parts — what each one gives you
- MS-103 The perfect stem from the third principal part
- MS-108 Perfect stem patterns — reduplication, lengthening, -v-, -s-, unchanged

**Unit 4 · week of Monday January 11, 2027**

- MS-104 Perfect active endings — i, isti, it, imus, istis, erunt
- MS-105 Perfect active indicative — all conjugations
- MS-106 Perfect tense — meaning and aspect
- MS-107 Distinguishing perfect from imperfect in translation

**Unit 4 · week of Monday January 18, 2027**

- MS-109 Pluperfect active indicative
- MS-111 Perfect system of sum
- MS-112 possum — present, imperfect, future, perfect
- MS-113 Complementary infinitive with possum

**Unit 4 · week of Monday January 25, 2027**

- MS-110 Future perfect active indicative
- MS-114 Sequence of tenses in narrative — recognizing the timeline

**Unit 5 · week of Monday February 1, 2027**

- MS-115 Personal pronouns — ego, nos
- MS-116 Personal pronouns — tu, vos
- MS-117 Why Latin uses subject pronouns only for emphasis or contrast
- MS-118 is, ea, id — full declension
- MS-119 is, ea, id as third person pronoun
- MS-120 is, ea, id as demonstrative adjective
- MS-121 Pronoun-antecedent agreement in gender and number

**Unit 5 · week of Monday February 8, 2027**

- MS-122 hic, haec, hoc — forms and use
- MS-123 ille, illa, illud — forms and use
- MS-124 Distinguishing hic from ille — near versus far
- MS-125 Reflexive pronoun se and reflexive possessive suus

**Unit 5 · week of Monday February 22, 2027**

- MS-126 Relative pronoun qui, quae, quod — full declension
- MS-127 Relative clause — the antecedent
- MS-128 Relative pronoun takes gender and number from antecedent
- MS-129 Relative pronoun takes case from its function in its own clause
- MS-130 Interrogative quis, quid and interrogative adjective qui, quae, quod

**Unit 5 · week of Monday March 1, 2027**

- MS-131 Third declension adjectives — three, two, and one termination
- MS-132 Adverb formation from first/second and third declension adjectives

**Unit 6 · week of Monday March 15, 2027**

- MS-133 Voice — the concept of active versus passive
- MS-134 Passive personal endings — r, ris, tur, mur, mini, ntur
- MS-135 Present passive indicative — all conjugations
- MS-136 Imperfect passive indicative
- MS-137 Future passive indicative

**Unit 6 · week of Monday March 22, 2027**

- MS-138 The fourth principal part — the perfect passive participle
- MS-139 Perfect passive participle declines like a first/second declension adjective
- MS-140 Perfect passive indicative — participle plus present of sum

**Unit 6 · week of Monday March 29, 2027**

- MS-141 Pluperfect passive indicative
- MS-142 Future perfect passive indicative
- MS-143 Ablative of personal agent with a / ab
- MS-144 Distinguishing ablative of agent from ablative of means

**Unit 6 · week of Monday April 5, 2027**

- MS-145 Converting between active and passive expression

**Unit 7 · week of Monday April 12, 2027**

- MS-146 Participle — a verbal adjective
- MS-147 Present active participle — formation
- MS-148 Present active participle — declension (third declension pattern)
- MS-150 Participles agree with the noun they modify

**Unit 7 · week of Monday April 26, 2027**

- MS-149 Future active participle — formation and meaning
- MS-151 Relative time of participles — before, during, after the main verb
- MS-152 Translating participles as relative clauses
- MS-153 Participial phrases — recognizing the boundaries

**Unit 7 · week of Monday May 3, 2027**

- MS-154 Ablative absolute — recognition
- MS-155 Ablative absolute — translation strategies

## Appendix C. Every lesson as built

Copied from `di/first-declension.yaml`. Each line is one screen. Format codes are in section 4; **bold** marks the highlighted word; in F4 / F8E the English comes first, then the Latin with the blank, then the ending. The app works out every answer, translation and wrong choice from the Latin.

### Placement (18 items)

- `E2 **The sailor** watches the girl. | subject`
- `E2 The sailor watches **the girl**. | dobj`
- `F2 **Puella** nautam vocat.`
- `F2 Nauta **puellam** vocat.`
- `F2 Nauta **puellās** vocat.`
- `F3 Nauta **puellās** vocat.`
- `F5 Puellae aquam port__`
- `F6 Puellās nautae vocant.`
- `F2 Fēmina fāmam **nautārum** laudat.`
- `F2 Fēmina vītam **puellae** laudat.`
- `F2 **Puellae** fābulam nārrant.`
- `F2 Nauta **puellīs** fābulam nārrat.`
- `F2 Nauta **puellae** fābulam nārrat.`
- `F2 Nauta in **īnsulā** pugnat.`
- `F2 Agricolae in **silvīs** pugnant.`
- `F6 Fēmina agricolīs aquam portat.`
- `F6 Puella cum fēminā aquam portat.`
- `F6 Nautae fāmam patriae laudant.`

Missed item → first lesson (in order): 0, 0, 1, 2, 3, 3, 4, 4, 6, 7, 7, 8, 9, 10, 11, 11, 10, 7

### Lesson 0 · Jobs in a sentence (English only)

*Today screen:* Every word in a sentence has a job. Today you find the jobs in English, so you know what the Latin endings have to show.

**Part B · Three jobs**

*Model*

- *Model screen:* The **verb** is the action word. / *The girl **calls** the sailor.*
- *Model screen:* The **subject** is who or what does the verb. / Ask: who calls? *The girl.* / ***The girl** calls the sailor.*
- *Model screen:* The **direct object** is who or what receives the verb. / Ask: calls whom? *The sailor.* / *The girl calls **the sailor**.*

*Test*

- `E3 The girl / calls / the sailor`

*Example sequence*

- `E3 The girl / calls / the sailor`
- `E3 The sailor / calls / the girl`
- `NOTE Sentences 1 and 2 use the same words. In English, the order decides which word is the subject. Latin won't work that way.`
- `E3 The farmer / loves / the land`
- `E3 The woman / carries / the water`
- `E3 The sailors / watch / the stars`
- `E3 The girl / calls`
- `NOTE Some sentences have no direct object. *The girl calls* has a subject and a verb, and nothing receives the call.`
- `E3 The women / praise / the farmer`
- `E3 The farmer / praises / the women`
- `E3 The sailor / watches`
- `E3 The girls / love / the island`

**Part C · Look-alikes**

- `E2 **The farmer** watches the girl. | subject`
- `E2 The farmer watches **the girl**. | dobj`
- `E2 **She** calls him. | subject`
- `E2 She calls **him**. | dobj`
- `NOTE English changes some words when they become the direct object: *she → her, he → him, they → them.* Latin does this to every noun.`
- `E2 **The sailors** praise the women. | subject`
- `E2 The sailors praise **the women**. | dobj`

**Part E · Sentences**

- `E3 The woman / loves / the forest`
- `E3 The girls / carry / the water`
- `E3 The farmer / fights`
- `E3 The sailors / save / the homeland`

**Delayed test (hardest item):** `E3 The sailor / calls / the girl`

**Part F · Lesson check** (7 to pass)

*Set A*

- `ET [The sailor] [praises] [the farmer]. | The sailor | Tap the subject.`
- `ET [The woman] [watches] [the moon]. | the moon | Tap the direct object.`
- `ET [The girls] [call] [the women]. | call | Tap the verb.`
- `E2 **They** watch the stars. | subject | buttons: subject dobj`
- `E2 The farmer loves **her**. | dobj | buttons: subject dobj`
- `ET [The girl] [fights]. | none | Tap the direct object.`
- `ET [The women] [carry] [the water]. | The women | Tap the subject.`
- `ET [The sailor] [calls] [the girls]. | the girls | Tap the direct object.`

*Set B*

- `ET [The farmer] [praises] [the sailor]. | The farmer | Tap the subject.`
- `ET [The girl] [watches] [the stars]. | the stars | Tap the direct object.`
- `ET [The sailors] [call] [the farmers]. | call | Tap the verb.`
- `E2 **He** watches the moon. | subject | buttons: subject dobj`
- `E2 The woman loves **them**. | dobj | buttons: subject dobj`
- `ET [The sailor] [fights]. | none | Tap the direct object.`
- `ET [The girls] [carry] [the water]. | The girls | Tap the subject.`
- `ET [The woman] [calls] [the farmer]. | the farmer | Tap the direct object.`

### Lesson 1 · -a: the subject (nominative)

*Today screen:* In Latin, word order doesn't tell you who does what. The ending does. Today: -a marks the subject.

**Part A · Words** (new: puella, fēmina, nauta, agricola, aqua, vocat, spectat, portat, amat, laudat (twice))

**Part B · New ending**

*Model*

- *Model screen:* In English, word order shows which word is the subject. In Latin, the ending does. / **-a** marks the subject. The subject is in the **nominative** case. / *Puella vocat.* The girl calls.

*Echo*

- `F7 puella`
- `F7 fēmina`
- `F7 nauta`

*Test*

- `F6 Puella vocat.`

*Example sequence*

- `F6 Fēmina spectat.`
- `F6 Spectat fēmina.`
- `F6 Nauta laudat.`
- `NOTE *Nauta* and *agricola* name men. The ending is still -a. The ending shows the job in the sentence, not whether the person is a man or a woman.`
- `F6 Laudat agricola.`
- `F6 Agricola amat.`
- `F6 Portat puella.`
- `F6 Nauta vocat.`
- `F6 Amat fēmina.`

**Part C · Look-alikes**

- `F2 Vocat **puella**. | buttons: verb subject`
- `F2 **Nauta** spectat. | buttons: verb subject`
- `F2 Laudat **fēmina**. | buttons: verb subject`
- `F2 **Agricola** portat. | buttons: verb subject`
- `F2 Amat **nauta**. | buttons: verb subject`
- `F2 **Puella** laudat. | buttons: verb subject`

**Part D · Review**: 4 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Agricola spectat.`
- `F6 Vocat nauta.`
- `F6 Fēmina portat.`
- `F6 Laudat puella.`

**Delayed test (hardest item):** `F6 Laudat agricola.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F6 Nauta spectat.`
- `F6 Vocat fēmina.`
- `F1 agricola`
- `F1 portat`
- `F2 Laudat **puella**.`
- `F6 Puella amat.`
- `F1 aqua`
- `F6 Spectat agricola.`

*Set B*

- `F6 Fēmina vocat.`
- `F6 Laudat nauta.`
- `F1 fēmina`
- `F1 spectat`
- `F2 **Agricola** amat.`
- `F6 Portat puella.`
- `F1 nauta`
- `F6 Amat agricola.`

### Lesson 2 · -am: the direct object (accusative)

*Today screen:* *Puella nautam vocat* and *Nautam puella vocat* mean the same thing. -am is why: it marks the direct object, wherever it sits.

**Part A · Words** (new: terra, silva, porta, via, īnsula; review: puella, nauta, vocat, spectat)

**Part B · New ending**

*Model*

- *Model screen:* **-am** marks the direct object. The direct object is in the **accusative** case. / *Puella nautam vocat.* The girl calls the sailor.

*Echo*

- `F7 nautam`
- `F7 puella`
- `F7 terram`
- `F7 fēmina`

*Test*

- `F6 Puella nautam vocat.`

*Example sequence*

- `F6 Puella nautam vocat.`
- `F6 Puellam nauta vocat.`
- `F6 Fēmina agricolam spectat.`
- `F6 Fēminam agricola spectat.`
- `F6 Agricola terram amat.`
- `F6 Terram agricola amat.`
- `NOTE Sentences 5 and 6 mean the same thing. Moving a Latin word doesn't change the subject or the direct object. The endings decide.`
- `F6 Nautam puella laudat.`
- `F6 Fēmina aquam portat.`
- `F6 Īnsulam nauta amat.`
- `F6 Silvam agricola spectat.`
- `F6 Fēmina vocat.`

**Part C · Look-alikes**

- `F2 **Puella** nautam spectat. | buttons: subject dobj`
- `F2 Nauta **puellam** spectat. | buttons: subject dobj`
- `F2 **Terra** agricolam vocat. | buttons: subject dobj`
- `F2 Agricola **terram** amat. | buttons: subject dobj`
- `F2 Fēmina **nautam** vocat. | buttons: subject dobj`
- `F2 **Agricola** silvam spectat. | buttons: subject dobj`
- `F2 Puella **silvam** amat. | buttons: subject dobj`
- `F2 **Via** fēminam vocat. | buttons: subject dobj`
- `F2 **Īnsula** nautam vocat. | buttons: subject dobj`
- `F2 Nauta **portam** spectat. | buttons: subject dobj`

**Part D · Review**: 4 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Viam puella spectat.`
- `F6 Agricola nautam laudat.`
- `F6 Agricolam nauta laudat.`
- `F6 Portam fēmina spectat.`

**Delayed test (hardest item):** `F6 Puellam nauta vocat.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F6 Fēminam puella vocat.`
- `F6 Nauta silvam amat.`
- `F2 Agricola **terram** spectat.`
- `F2 **Fēmina** aquam portat.`
- `F6 Nautam agricola laudat.`
- `F1 īnsula`
- `F4 The sailor calls **the girl**. | Nauta puell___ vocat. | am`
- `F6 Puella viam spectat.`

*Set B*

- `F6 Agricolam fēmina vocat.`
- `F6 Puella īnsulam amat.`
- `F2 Nauta **portam** spectat.`
- `F2 **Agricola** aquam portat.`
- `F6 Puellam nauta laudat.`
- `F1 silva`
- `F4 The woman praises **the sailor**. | Fēmina naut___ laudat. | am`
- `F6 Fēmina terram spectat.`

### Lesson 3 · -ās: the direct object, plural (accusative plural)

*Today screen:* Today the direct object becomes more than one: -ās. One ending changes the English.

**Part A · Words** (new: lūna, stēlla, et; review: silva, via, īnsula, porta)

**Part B · New ending**

*Model*

- *Model screen:* **-ās** marks a plural direct object: more than one. / *Nauta puellās vocat.* The sailor calls the girls.

*Echo*

- `F7 puellās`
- `F7 puellam`
- `F7 stēllās`
- `F7 lūnam`

*Test*

- `F6 Nauta puellās vocat.`

*Example sequence*

- `F6N Nauta puellam vocat.`
- `F6N Nauta puellās vocat.`
- `F6N Fēmina stēllās spectat.`
- `F6N Fēmina stēllam spectat.`
- `F6N Agricola silvās spectat.`
- `F6N Lūnam et stēllās nauta spectat.`
- `F6N Īnsulās nauta amat.`
- `F6N Fēminās agricola laudat.`
- `F6N Puella portās spectat.`
- `F6 Agricolam fēmina vocat.`

**Part C · Look-alikes**

- `F3F2 Nauta **puellam** vocat.`
- `F3F2 Nauta **puellās** vocat.`
- `F3F2 Agricola **viās** spectat.`
- `F3F2 Puella **viam** amat.`
- `F3F2 Fēmina **stēllās** spectat.`
- `F3F2 Nauta **lūnam** spectat.`
- `F3F2 Agricola **īnsulās** amat.`
- `F3F2 Fēmina **terram** amat.`
- `F3F2 **Puella** stēllās spectat.`
- `F3F2 **Agricola** viās amat.`

**Part D · Review**: 6 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Agricola terrās amat.`
- `F6 Viās puella spectat.`
- `F6 Nauta lūnam et stēllās laudat.`
- `F6 Fēminās et puellās nauta vocat.`

**Delayed test (hardest item):** `F6 Lūnam et stēllās nauta spectat.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F6 Puella nautās vocat.`
- `F6 Silvās fēmina amat.`
- `F3 Fēmina **viās** amat.`
- `F3 Nauta **īnsulam** spectat.`
- `F2 Agricola **stēllās** spectat.`
- `F4 The farmer calls **the women**. | Agricola fēmin___ vocat. | ās`
- `F6 Nautam puella laudat.`
- `F6 Agricola lūnam et stēllās spectat.`

*Set B*

- `F6 Fēmina agricolās vocat.`
- `F6 Īnsulās puella amat.`
- `F3 Puella **portās** spectat.`
- `F3 Agricola **silvam** amat.`
- `F2 Nauta **terrās** spectat.`
- `F4 The sailor watches **the girls**. | Nauta puell___ spectat. | ās`
- `F6 Agricolam fēmina laudat.`
- `F6 Nauta stēllās et lūnam spectat.`

### Lesson 4 · -ae: the subject, plural, and verbs in -nt (nominative plural)

*Today screen:* -ae marks a subject that is more than one, and the verb changes to -nt to match. The verb is your check.

**Part A · Words** (new: vocant, spectant, portant, amant, laudant; review: vocat, spectat, portat, amat, laudat, lūna, stēlla)

- `EV The girl call__ | s`
- `EV The girls call__ | none`
- `EV The sailor watch__ | es`
- `EV The sailors watch__ | none`
- `NOTE In English the verb also changes when the subject is plural. Latin does the same with **-t** and **-nt**.`

**Part B · New ending**

*Model*

- *Model screen:* **-ae** marks a plural subject: more than one. Nominative plural. / When the subject is plural, the verb ends in **-nt**. The verb agrees with its subject. / *Puellae nautam vocant.* The girls call the sailor.

*Echo*

- `F7 puellae`
- `F7 puellās`
- `F7 nautae`
- `F7 fēmina`

*Test*

- `F6 Puellae nautam vocant.`

*Example sequence*

- `F6V Puella nautam vocat.`
- `F6V Puellae nautam vocant.`
- `F6V Fēminae aquam portant.`
- `F6V Agricolae terram amant.`
- `F6V Nautae stēllās spectant.`
- `F6V Puellae nautās vocant.`
- `F6V Puellās nautae vocant.`
- `F6V Fēminās puellae laudant.`
- `F6V Nauta fēminās laudat.`
- `F6 Silvās agricola spectat.`

**Part C · Look-alikes**

- `F2 **Puellae** nautam vocant. | buttons: subject dobj`
- `F2 Nauta **puellās** vocat. | buttons: subject dobj`
- `F2 **Nautae** stēllās spectant. | buttons: subject dobj`
- `F2 Puella **nautās** vocat. | buttons: subject dobj`
- `F2 Agricola **fēminās** laudat. | buttons: subject dobj`
- `F2 **Agricolae** terram amant. | buttons: subject dobj`
- `F2 Nauta **stēllās** spectat. | buttons: subject dobj`
- `F2 **Fēminae** aquam portant. | buttons: subject dobj`
- `F3 fēmina`
- `F5 Fēmina aquam port__`
- `F3 fēminae`
- `F5 Fēminae aquam port__`
- `F3 nauta`
- `F5 Nauta stēllās spect__`
- `F3 nautae`
- `F5 Nautae stēllās spect__`

**Part D · Review**: 6 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Agricolae silvās spectant.`
- `F6 Fēminam nautae laudant.`
- `F6 Nautam fēminae laudant.`
- `F6 Puellae lūnam et stēllās amant.`

**Delayed test (hardest item):** `F6 Puellās nautae vocant.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F6 Nautae puellam vocant.`
- `F6 Agricolās fēminae laudant.`
- `F5 Fēminae aquam port__`
- `F5 Puella terram am__`
- `F2 **Agricolae** īnsulam amant.`
- `F2 Nautae **fēminās** spectant.`
- `F6 Puellās agricola vocat.`
- `F4 **The sailors** love the island. | Naut___ īnsulam amant. | ae`

*Set B*

- `F6 Fēminae nautam vocant.`
- `F6 Puellās agricolae laudant.`
- `F5 Nautae stēllās spect__`
- `F5 Agricola silvam am__`
- `F2 **Puellae** viam spectant.`
- `F2 Fēminae **agricolās** vocant.`
- `F6 Nautās fēmina vocat.`
- `F4 **The farmers** carry the water. | Agricol___ aquam portant. | ae`

### Lesson 5 · Firm-up: the four endings (no new ending)

*Today screen:* No new ending today. You put -a, -am, -ās and -ae together until you can tell them apart fast.

**Part A · Words** (new: patria, fāma, vīta, nōn; review: every word so far, 8 of them, missed ones first)

**Part B · The table so far**

*Model*

- *Model screen:* (the ending table: nom acc)

*Echo*

- `F7 puellās`
- `F7 fēminae`
- `F7 nautam`
- `F7 agricola`
- `F7 terrās`
- `F7 silvae`
- `F7 īnsulam`
- `F7 via`

*Example sequence*

- `F4 **The girl** watches the stars. | Puell___ stēllās spectat. | a`
- `F4 The woman calls **the girls**. | Fēmina puell___ vocat. | ās`
- `F4 The farmers praise **the sailor**. | Agricolae naut___ laudant. | am`
- `F4 **The farmers** love the land. | Agricol___ terram amant. | ae`
- `F4 The sailor watches **the islands**. | Nauta īnsul___ spectat. | ās`
- `F4 **The woman** carries the water. | Fēmin___ aquam portat. | a`
- `F4 **The women** praise the homeland. | Fēmin___ patriam laudant. | ae`
- `F4 The farmer loves **the land**. | Agricola terr___ amat. | am`

**Part C · Look-alikes**

- `F2 **Puellae** viam spectant. | buttons: subject dobj`
- `F2 Silvās **agricola** amat. | buttons: subject dobj`
- `F2 Nauta **fēminās** vocat. | buttons: subject dobj`
- `F2 **Fēminam** nautae laudant. | buttons: subject dobj`
- `F2 Stēllās **puellae** spectant. | buttons: subject dobj`
- `F2 **Patriam** nauta amat. | buttons: subject dobj`
- `F2 Agricolae **terram** amant. | buttons: subject dobj`
- `F2 **Fēmina** lūnam spectat. | buttons: subject dobj`
- `F2 Viam **nautae** amant. | buttons: subject dobj`
- `F2 Puella **īnsulās** spectat. | buttons: subject dobj`
- `F2 **Agricolās** fēmina vocat. | buttons: subject dobj`
- `F2 Fāmam **nauta** nōn amat. | buttons: subject dobj`

**Part D · Review**: 8 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Agricolae silvās spectant.`
- `F6 Silvās agricolae spectant.`
- `F6 Patriam nautae amant.`
- `F6 Fāmam agricola nōn amat.`
- `F6 Vītam fēminae laudant.`
- `F6 Puella lūnam et stēllās amat.`
- `F6 Fēminam nautae nōn laudant.`
- `F6 Nautās fēmina nōn vocat.`

**Delayed test (hardest item):** `F6 Fēminam nautae nōn laudant.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F6 Fāmam nautae amant.`
- `F6 Agricola patriam laudat.`
- `F6 Puellās fēmina nōn vocat.`
- `F8 Nautae īnsulās spectant.`
- `F4 The girls watch **the forests**. | Puellae silv___ spectant. | ās`
- `F2 **Fēminae** vītam laudant.`
- `F8E The women call **the farmer**. | Fēminae agricol___ vocant. | am`
- `F6 Stēllās puella spectat.`

*Set B*

- `F6 Vītam agricolae amant.`
- `F6 Nauta patriam laudat.`
- `F6 Fēminās puella nōn vocat.`
- `F8 Agricolae silvās spectant.`
- `F4 The sailors love **the roads**. | Nautae vi___ amant. | ās`
- `F2 **Nautae** fāmam laudant.`
- `F8E The sailors praise **the girl**. | Nautae puell___ laudant. | am`
- `F6 Lūnam fēmina spectat.`

### Lesson 6 · -ārum: possession, plural (genitive plural)

*Today screen:* A new job: possession, “of the ___s.” -ārum is long and easy to spot, so it comes first.

**Part A · Words** (review: patria, fāma, vīta, silva, īnsula, via)

**Part B1 · The job in English**

- *Model screen:* **Possession** shows who or what something belongs to. / English shows it two ways: *the sailor's fame* · *the fame of the sailor*. / The owner is the word after **of**, or the word with **'s**.
- `ET [the girls'] [water] | the girls' | Tap the owner.`
- `ET [the life] of [the farmers] | the farmers | Tap the owner.`
- `ET [the woman's] [road] | the woman's | Tap the owner.`
- `ET [the fame] of [the sailors] | the sailors | Tap the owner.`
- `ET [the island's] [gate] | the island's | Tap the owner.`
- `ET [The farmer] [praises] [the fame] of [the women]. | the women | Tap the owner.`
- `E2 The sailors praise **the girl**. | dobj | buttons: subject dobj poss`
- `E2 The sailors praise the girl's **fame**. | dobj | buttons: subject dobj poss`
- `E2 The sailors praise the fame of **the girl**. | poss | buttons: subject dobj poss`

**Part B · New ending**

*Model*

- *Model screen:* **-ārum** shows possession: “of the ___s.” It belongs to the noun next to it. Possession is the **genitive** case. / *fāma nautārum* the fame of the sailors · the sailors' fame

*Echo*

- `F7 nautārum`
- `F7 nautās`
- `F7 silvārum`
- `F7 silvae`

*Test*

- `F1 fāma nautārum`

*Example sequence*

- `F1 vīta agricolārum`
- `F1 aqua silvārum`
- `F1 patria puellārum`
- `F1 viae īnsulārum`
- `F1 terra fēminārum`
- `F6 Fēmina fāmam nautārum laudat.`
- `F6 Fēmina nautās laudat.`
- `F6 Agricolae aquam silvārum portant.`
- `F6 Nauta vītam agricolārum laudat.`
- `F6 Puellae viās īnsulārum spectant.`
- `F6 Terram fēminārum agricolae amant.`
- `F6 Nautae stēllās spectant.`

**Part C · Look-alikes**

- `F2 Fēmina fāmam **nautārum** laudat. | buttons: dobj poss`
- `F2 Fēmina **nautās** laudat. | buttons: dobj poss`
- `F2 Agricola aquam **silvārum** portat. | buttons: dobj poss`
- `F2 Agricola **silvās** spectat. | buttons: dobj poss`
- `F2 Nauta **puellās** vocat. | buttons: dobj poss`
- `F2 Nauta viās **īnsulārum** amat. | buttons: dobj poss`
- `F2 Puella **fēminās** laudat. | buttons: dobj poss`
- `F2 Puella vītam **agricolārum** laudat. | buttons: dobj poss`

**Part D · Review**: 8 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Puella portam silvārum spectat.`
- `F6 Nautae patriam agricolārum servant. | gloss: servant = save`
- `F6 Fāmam puellārum fēmina laudat.`
- `F6 Agricola vītam nautārum nōn amat.`

**Delayed test (hardest item):** `F6 Terram fēminārum agricolae amant.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F6 Nauta fāmam fēminārum laudat.`
- `F6 Puellae aquam silvārum portant.`
- `F2 Agricola vītam **nautārum** laudat.`
- `F2 Agricola **nautās** laudat.`
- `F1 patria agricolārum`
- `F4 The woman praises the life **of the girls**. | Fēmina vītam puell___ laudat. | ārum`
- `F6 Viās īnsulārum nautae amant.`
- `F8 Fēmina terram puellārum spectat.`

*Set B*

- `F6 Fēmina fāmam agricolārum laudat.`
- `F6 Nautae aquam īnsulārum portant.`
- `F2 Puella vītam **fēminārum** laudat.`
- `F2 Puella **fēminās** laudat.`
- `F1 terra nautārum`
- `F4 The farmers carry the water **of the forests**. | Agricolae aquam silv___ portant. | ārum`
- `F6 Viās silvārum agricolae amant.`
- `F8 Nauta terram fēminārum spectat.`

### Lesson 7 · -ae: possession, singular (genitive singular)

*Today screen:* -ae already marks a subject that is more than one. Today it gets a second job, possession, and the verb tells you which job it has.

**Part A · Words** (review: fāma, vīta, patria, porta, via)

**Part B · New ending**

*Model*

- *Model screen:* **-ae** has a second job: possession for one, “of the ___.” Genitive singular. / Check the verb. / Verb ends in **-nt**, no other subject → **-ae** is the subject. / Verb ends in **-t** → **-ae** can't be the subject. It shows possession: “of the ___.” / *Fēmina vītam puellae laudat.* The woman praises the life of the girl.

*Test*

- `F2 Fēmina vītam **puellae** laudat.`

*Example sequence*

- `F2T **Puellae** aquam portant.`
- `F2T Fēmina vītam **puellae** laudat.`
- `F2T **Nautae** lūnam spectant.`
- `F2T Agricola fāmam **nautae** laudat.`
- `F2T Nauta viam **īnsulae** spectat.`
- `F2T Silvam **patriae** agricola amat.`
- `F2T **Fēminae** portam spectant.`
- `F2T Fēminae fāmam **patriae** laudant.`
- `NOTE Sentence 8 has two -ae words. *Fēminae* goes with *laudant*: the subject. *Patriae* sits right after *fāmam* and belongs to it: of the homeland.`
- `F6 Puella fāmam nautārum laudat.`

**Part C · Look-alikes**

- `F2F3 Fēmina vītam **puellae** laudat.`
- `F2F3 Fēmina vītam **puellārum** laudat.`
- `F2F3 Agricola fāmam **nautae** laudat.`
- `F2F3 Agricola fāmam **nautārum** laudat.`
- `F2F3 Nauta portam **silvae** spectat.`
- `F2F3 Nauta portam **silvārum** spectat.`

**Part D · Review**: 8 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Nauta portam silvae spectat.`
- `F6 Agricolae vītam fēminae laudant.`
- `F6 Puella stēllās patriae amat.`
- `F6 Fāmam agricolae fēmina nōn laudat.`

**Delayed test (hardest item):** `F6 Fēminae fāmam patriae laudant.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F2 **Nautae** terram amant.`
- `F2 Puella fāmam **nautae** laudat.`
- `F6 Agricola viam silvae spectat.`
- `F6 Fēminae vītam agricolae laudant.`
- `F2 Nauta vītam **puellārum** laudat.`
- `F3 Nauta fāmam **puellārum** laudat.`
- `F4 The sailor watches the road **of the island**. | Nauta viam īnsul___ spectat. | ae`
- `F8 Nautae portam īnsulae spectant.`

*Set B*

- `F2 **Puellae** terram amant.`
- `F2 Nauta fāmam **fēminae** laudat.`
- `F6 Fēmina viam īnsulae spectat.`
- `F6 Nautae vītam puellae laudant.`
- `F2 Agricola vītam **fēminārum** laudat.`
- `F3 Nauta vītam **fēminae** laudat.`
- `F4 The farmer praises the water **of the forest**. | Agricola aquam silv___ laudat. | ae`
- `F8 Agricolae portam silvae spectant.`

### Lesson 8 · -īs: to / for, plural (dative plural)

*Today screen:* A new job: to / for, the one who gets something. -īs marks it for more than one.

**Part A · Words** (new: fābula, nārrat, nārrant, parat, parant; review: portat, aqua, via)

**Part B1 · The job in English**

- *Model screen:* Some verbs have a direct object and also someone who **gets** it. / *The sailor tells a story **to the girls**.* The story is the direct object. The girls get it. / English can also drop the “to”: *The sailor tells **the girls** a story.* The girls still get the story. They are not the direct object.
- `ET [The woman] [carries] [water] for [the farmers]. | the farmers | Tap who gets it.`
- `ET [The farmer] [prepares] [a road] for [the women]. | the women | Tap who gets it.`
- `ET [The girl] [tells] [the sailors] [a story]. | the sailors | Tap who gets it.`
- `ET [The sailor] [tells] [a story] to [the women]. | the women | Tap who gets it.`
- `ET [The woman] [brings] [the farmers] [water]. | the farmers | Tap who gets it.`
- `E2 The sailor calls **the girls**. | dobj | buttons: dobj tofor`
- `E2 The sailor tells **the girls** a story. | tofor | buttons: dobj tofor`
- `E2 The sailor tells the girls **a story**. | dobj | buttons: dobj tofor`

**Part B · New ending**

*Model*

- *Model screen:* **-īs** means “to the ___s” or “for the ___s.” It names who gets the direct object. This is the **dative** case. / *Nauta puellīs fābulam nārrat.* The sailor tells a story to the girls.

*Echo*

- `F7 puellīs`
- `F7 puellās`
- `F7 nautīs`
- `F7 nautārum`

*Test*

- `F6 Nauta puellīs fābulam nārrat.`

*Example sequence*

- `F6 Nauta puellās vocat.`
- `F6 Nauta puellīs fābulam nārrat.`
- `F6 Fēmina agricolīs aquam portat.`
- `F6 Agricola fēminīs viam parat.`
- `F6 Puellae nautīs fābulās nārrant.`
- `F6 Fābulam nautīs fēmina nārrat.`
- `F6 Fēmina agricolās vocat.`
- `F6 Nautae puellīs aquam portant.`
- `F6 Agricolae vītam nautae laudant.`

**Part C · Look-alikes**

- `F2 Nauta **puellās** vocat. | buttons: dobj poss tofor`
- `F2 Nauta vītam **puellārum** laudat. | buttons: dobj poss tofor`
- `F2 Nauta **puellīs** fābulam nārrat. | buttons: dobj poss tofor`
- `F2 Fēmina **nautīs** aquam portat. | buttons: dobj poss tofor`
- `F2 Fēmina **nautās** vocat. | buttons: dobj poss tofor`
- `F2 Agricola fāmam **fēminārum** laudat. | buttons: dobj poss tofor`
- `F2 Puella **agricolīs** viam parat. | buttons: dobj poss tofor`
- `F2 Agricola **fēminās** spectat. | buttons: dobj poss tofor`

**Part D · Review**: 8 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Puella fēminīs fābulam nārrat.`
- `F6 Agricolae nautīs aquam parant.`
- `F6 Fābulās puellīs nauta nārrat.`
- `F6 Fēmina fābulās nautārum laudat.`

**Delayed test (hardest item):** `F6 Fābulam nautīs fēmina nārrat.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F6 Nauta fēminīs fābulam nārrat.`
- `F6 Puellae agricolīs aquam portant.`
- `F2 Fēmina **nautīs** viam parat.`
- `F2 Fēmina **nautās** vocat.`
- `F2 Fēmina fāmam **nautārum** laudat.`
- `F4 The woman prepares water **for the girls**. | Fēmina puell___ aquam parat. | īs`
- `F6 Fābulam puellīs agricola nārrat.`
- `F8 Nautae fēminīs aquam parant.`

*Set B*

- `F6 Agricola puellīs fābulam nārrat.`
- `F6 Fēminae nautīs aquam portant.`
- `F2 Puella **agricolīs** viam parat.`
- `F2 Puella **agricolās** vocat.`
- `F2 Puella fāmam **agricolārum** laudat.`
- `F4 The farmer tells a story **to the sailors**. | Agricola naut___ fābulam nārrat. | īs`
- `F6 Fābulam fēminīs nauta nārrat.`
- `F8 Puellae agricolīs aquam parant.`

### Lesson 9 · -ae: to / for, singular (dative singular)

*Today screen:* -ae gets a third job: to / for one person. Where it sits and the verb tell you which job it has.

**Part A · Words** (new: servat, servant; review: nārrat, parat, portat, fābula)

**Part B · New ending**

*Model*

- *Model screen:* **-ae** has a third job: “to the ___” or “for the ___” for one. Dative singular. / Three jobs for -ae. Check in this order: / 1. Verb ends in **-nt**, no other subject → **subject**. / 2. Right after another noun → **possession**. / 3. Before the direct object, with a verb like tells, carries, prepares → **to / for**. / *Nauta puellae fābulam nārrat.* The sailor tells a story to the girl.

*Test*

- `F2 Nauta **puellae** fābulam nārrat.`

*Example sequence*

- `F2T **Puellae** fābulam nārrant.`
- `F2T Nauta **puellae** fābulam nārrat.`
- `F2T Nauta fāmam **puellae** laudat.`
- `F2T Agricola **fēminae** aquam portat.`
- `F2T **Agricolae** aquam portant.`
- `F2T Fēmina vītam **agricolae** laudat.`
- `F2T Puella **agricolae** viam parat.`
- `F2T Fēmina **nautae** īnsulam servat.`
- `F6 Nauta puellīs fābulam nārrat.`

**Part C · Look-alikes**

- `F2 **Nautae** stēllās spectant. | buttons: subject poss tofor`
- `F2 Fēmina **nautae** fābulam nārrat. | buttons: subject poss tofor`
- `F2 Fēmina vītam **nautae** laudat. | buttons: subject poss tofor`
- `F2 **Fēminae** aquam parant. | buttons: subject poss tofor`
- `F2 Puella **fēminae** aquam parat. | buttons: subject poss tofor`
- `F2 Puella portam **silvae** spectat. | buttons: subject poss tofor`
- `F2 Agricola **puellae** viam parat. | buttons: subject poss tofor`
- `F2 **Puellae** viam parant. | buttons: subject poss tofor`
- `F2 Nauta silvam **patriae** amat. | buttons: subject poss tofor`
- `F2 Nauta **fēminae** fābulam nārrat. | buttons: subject poss tofor`
- `F2 **Agricolae** terram servant. | buttons: subject poss tofor`
- `F2 Agricola fāmam **īnsulae** laudat. | buttons: subject poss tofor`

**Part D · Review**: 8 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Puella nautae fābulam nārrat.`
- `F6 Agricolae fēminae viam parant.`
- `F6 Fēmina fāmam nautae laudat.`
- `F6 Fēmina nautīs fābulās nārrat.`

**Delayed test (hardest item):** `F6 Fēmina nautae īnsulam servat.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F2 Agricola **fēminae** fābulam nārrat.`
- `F2 Agricola vītam **fēminae** laudat.`
- `F2 **Fēminae** fābulam nārrant.`
- `F6 Nauta puellae aquam portat.`
- `F6 Puellae agricolae viam parant.`
- `F4 The girl carries water **for the woman**. | Puella fēmin___ aquam portat. | ae`
- `F6 Puella fāmam agricolae laudat.`
- `F8 Fēmina puellae fābulam nārrat.`

*Set B*

- `F2 Nauta **puellae** fābulam nārrat.`
- `F2 Nauta vītam **puellae** laudat.`
- `F2 **Puellae** fābulam nārrant.`
- `F6 Agricola fēminae aquam portat.`
- `F6 Nautae puellae viam parant.`
- `F4 The girl tells a story **to the sailor**. | Puella naut___ fābulam nārrat. | ae`
- `F6 Fēmina fāmam nautae laudat.`
- `F8 Puella fēminae fābulam nārrat.`

### Lesson 10 · -ā: object of the preposition, singular (ablative)

*Today screen:* After in, cum, ē / ex and ā / ab, one thing ends in -ā: a long ā, not the subject's -a.

**Part A · Words** (new: in, cum, ē, ex, ā, ab, pugnat, pugnant)

**Part B1 · The job in English**

- *Model screen:* A **preposition** is a small word like *in, with, out of, away from*. / The noun after it is the **object of the preposition**. / *in **the forest*** · *with **the woman*** · *out of **the forest***
- `ET [The sailor] [fights] on [the island]. | the island | Tap the object of the preposition.`
- `ET [The girl] [carries] [water] with [the woman]. | the woman | Tap the object of the preposition.`
- `ET [The farmer] [carries] [water] out of [the forest]. | the forest | Tap the object of the preposition.`
- `ET [The women] [watch] [the stars] in [the street]. | the street | Tap the object of the preposition.`
- `ET [The girl] [calls] [the sailor] from [the gate]. | the gate | Tap the object of the preposition.`
- `E2 **The forest** saves the farmer. | subject | buttons: subject dobj objprep`
- `E2 The farmer loves **the forest**. | dobj | buttons: subject dobj objprep`
- `E2 The farmer fights in **the forest**. | objprep | buttons: subject dobj objprep`

**Part B · New ending**

*Model*

- *Model screen:* After **in, cum, ē, ex, ā, ab**, the object of the preposition ends in **-ā**. This is the **ablative** case. / Read the noun with the preposition in front of it. / *in silvā* in the forest · *cum fēminā* with the woman · *ē silvā* out of the forest / **-ā** looks like **-a**. The word in front tells you which: a preposition means **-ā**.

*Echo*

- `F7 silvā`
- `F7 silva`
- `F7 fēminā`
- `F7 fēminam`

*Test*

- `F1 in silvā`

*Example sequence*

- `F1 in īnsulā`
- `F1 cum puellā`
- `F1 ē silvā`
- `F1 ā portā`
- `F1 in viā`
- `F6 Nauta in īnsulā pugnat.`
- `F6 Puella cum fēminā aquam portat.`
- `F6 Fēmina puellam vocat.`
- `F6 Agricola ē silvā aquam portat.`
- `F6 Fēminae in viā stēllās spectant.`
- `F6 Puella ā portā nautam vocat.`
- `F6 Silva agricolam nōn servat.`

**Part C · Look-alikes**

- `F2 **Silva** agricolam servat. | buttons: subject objprep`
- `F2 Agricola in **silvā** pugnat. | buttons: subject objprep`
- `F2 **Fēmina** aquam portat. | buttons: subject objprep`
- `F2 Puella cum **fēminā** aquam portat. | buttons: subject objprep`
- `F2 **Puella** nautam vocat. | buttons: subject objprep`
- `F2 Nauta cum **puellā** pugnat. | buttons: subject objprep`
- `F2 **Īnsula** nautam servat. | buttons: subject objprep`
- `F2 Nauta in **īnsulā** pugnat. | buttons: subject objprep`

**Part D · Review**: 8 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Nautae in īnsulā patriam servant.`
- `F6 Agricola cum puellā in silvā pugnat.`
- `F6 Fēmina in viā puellae fābulam nārrat.`
- `F6 Cum nautā agricola pugnat.`

**Delayed test (hardest item):** `F6 Puella ā portā nautam vocat.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F1 cum nautā`
- `F1 ē silvā`
- `F2 Puella in **īnsulā** pugnat.`
- `F2 **Puella** īnsulam amat.`
- `F6 Agricola cum fēminā aquam portat.`
- `F6 Nautae in viā lūnam spectant.`
- `F4 The sailor fights **in the forest**. | Nauta in silv___ pugnat. | ā`
- `F8 Puella ā portā agricolam vocat.`

*Set B*

- `F1 cum fēminā`
- `F1 ē viā`
- `F2 Nauta in **silvā** pugnat.`
- `F2 **Nauta** silvam amat.`
- `F6 Fēmina cum puellā aquam portat.`
- `F6 Agricolae in īnsulā stēllās spectant.`
- `F4 The farmers fight **on the island**. | Agricolae in īnsul___ pugnant. | ā`
- `F8 Nauta ā portā fēminam vocat.`

### Lesson 11 · -īs: object of the preposition, plural (ablative plural)

*Today screen:* After a preposition, more than one ends in -īs, the same ending as to / for. The preposition tells you which job it is.

**Part A · Words** (review: in, cum, ē, ex, ā, ab, nārrat, parat)

**Part B · New ending**

*Model*

- *Model screen:* After a preposition, a plural object of the preposition ends in **-īs**. Ablative plural. / *in silvīs* in the forests · *cum puellīs* with the girls / You already know **-īs** as “to / for.” / Preposition in front → **object of the preposition** (ablative). / No preposition → **to / for** (dative).

*Test*

- `F2 Agricolae in **silvīs** pugnant.`

*Example sequence*

- `F2T Nauta **puellīs** fābulam nārrat.`
- `F2T Nauta cum **puellīs** pugnat.`
- `F2T Fēmina **agricolīs** aquam portat.`
- `F2T Fēmina ē **silvīs** aquam portat.`
- `F2T Nautae in **īnsulīs** lūnam spectant.`
- `F2T Puellae **fēminīs** viam parant.`
- `F2T Agricola in **silvā** pugnat.`
- `F2T Puella cum **fēminīs** fābulās nārrat.`

**Part C · Look-alikes**

- `F2 Fēmina **puellīs** aquam portat. | buttons: tofor objprep`
- `F2 Fēmina cum **puellīs** aquam portat. | buttons: tofor objprep`
- `F2 Agricola **nautīs** fābulam nārrat. | buttons: tofor objprep`
- `F2 Agricola cum **nautīs** pugnat. | buttons: tofor objprep`
- `F2 Nautae in **īnsulīs** pugnant. | buttons: tofor objprep`
- `F2 Nauta **fēminīs** viam parat. | buttons: tofor objprep`
- `F2 Puella ē **silvīs** aquam portat. | buttons: tofor objprep`
- `F2 Puella **agricolīs** fābulam nārrat. | buttons: tofor objprep`
- `F2 Nauta in **īnsulā** pugnat. | buttons: subject tofor objprep`
- `F2 Agricola cum **fēminā** aquam portat. | buttons: subject tofor objprep`

**Part D · Review**: 8 items from earlier lessons: last lesson's delayed test and this student's misses first

**Part E · Sentences**

- `F6 Agricolae cum nautīs in silvīs pugnant.`
- `F6 Fēmina puellīs ē silvā aquam portat.`
- `F6 Nautae in viīs fēminīs fābulās nārrant.`
- `F6 Fēminae ab īnsulīs aquam portant.`

**Delayed test (hardest item):** `F6 Puella cum fēminīs fābulās nārrat.`

**Part F · Lesson check** (7 to pass)

*Set A*

- `F2 Fēmina **nautīs** fābulam nārrat.`
- `F2 Fēmina cum **nautīs** pugnat.`
- `F1 in silvīs`
- `F1 cum fēminīs`
- `F6 Agricola ē silvīs aquam portat.`
- `F6 Puellae agricolīs viam parant.`
- `F4 The woman fights **with the girls**. | Fēmina cum puell___ pugnat. | īs`
- `F8 Nautae in īnsulīs pugnant.`

*Set B*

- `F2 Nauta **fēminīs** fābulam nārrat.`
- `F2 Nauta cum **fēminīs** pugnat.`
- `F1 in īnsulīs`
- `F1 cum puellīs`
- `F6 Fēmina ē silvīs aquam portat.`
- `F6 Nautae fēminīs viam parant.`
- `F4 The sailor saves the homeland **with the farmers**. | Nauta cum agricol___ patriam servat. | īs`
- `F8 Agricolae in silvīs pugnant.`

### Lesson 12 · The whole table, and a reading (everything)

*Today screen:* Every ending together, the way a story uses them. Then you read one.

**Part A · Words** (review: every word so far, 10 of them, missed ones first)

**Part B · The whole table**

*Model*

- *Model screen:* (the ending table: nom gen dat acc abl)

*Example sequence*

- `F4 The sailor praises the fame **of the girls**. | Nauta fāmam puell___ laudat. | ārum`
- `F4 The girl fights **with the woman**. | Puella cum fēmin___ pugnat. | ā`
- `F4 **The sailors** watch the moon. | Naut___ lūnam spectant. | ae`
- `F4 The girl prepares water **for the farmer**. | Puella agricol___ aquam parat. | ae`
- `F4 The sailors love **the islands**. | Nautae īnsul___ amant. | ās`
- `F4 The farmers fight **in the forests**. | Agricolae in silv___ pugnant. | īs`
- `F4 The farmer watches the road **of the gate**. | Agricola viam port___ spectat. | ae`
- `F4 The women call **the girl**. | Fēminae puell___ vocant. | am`
- `F4 The sailor tells a story **to the women**. | Nauta fēmin___ fābulam nārrat. | īs`
- `F4 **The farmer** saves the homeland. | Agricol___ patriam servat. | a`

**Part C · Look-alikes**

- `F2 **Puella** nautam vocat.`
- `F2 Puella **nautam** vocat.`
- `F2 Nauta **puellam** spectat.`
- `F2 Nauta **puellās** spectat.`
- `F2 Agricola **fēminās** vocat.`
- `F2 **Fēminae** agricolam vocant.`
- `F2 Fēmina **nautās** laudat.`
- `F2 Fēmina fāmam **nautārum** laudat.`
- `F2 **Nautae** terram amant.`
- `F2 Agricola fāmam **nautae** laudat.`
- `F2 Agricola vītam **puellae** laudat.`
- `F2 Agricola **puellae** aquam portat.`
- `F2 Fēmina **agricolīs** fābulam nārrat.`
- `F2 Fēmina cum **agricolīs** pugnat.`
- `F2 **Silva** nautam servat.`
- `F2 Nauta in **silvā** pugnat.`

**Part D · Review**: the delayed-test item from every lesson, 1–11

**Part E · Sentences**

*Reading: Nauta et puellae*

> Nauta in īnsulā lūnam et stēllās spectat.  
> Puellae ē silvā aquam portant.  
> Nauta puellās vocat et puellīs fābulam nārrat.  
> Fābula fāmam nautārum laudat.  
> Puellae fābulam nautae amant.  
> Puellae cum nautā patriam servant.  

- `Q Where is the sailor? | on the island | in the forest | in the street`
- `Q Where do the girls carry the water from? | out of the forest | out of the island | away from the gate`
- `Q Who hears the story? | the girls | the sailor | the farmers`
- `Q Whose fame does the story praise? | the sailors' | the girls' | the homeland's`
- `Q Who saves the homeland? | the girls, with the sailor | the sailor, alone | the farmers, with the girls`

**Part F · Lesson check** (14 to pass)

*Set A*

- `F2 Fēmina vītam **puellārum** laudat.`
- `F2 **Nautae** terram servant.`
- `F2 Agricola **fēminae** fābulam nārrat.`
- `F2 Agricola fāmam **fēminae** laudat.`
- `F2 Puella in **silvā** pugnat.`
- `F2 Puella **agricolīs** aquam portat.`
- `F2 Puella cum **agricolīs** pugnat.`
- `F2 Nauta **stēllās** spectat.`
- `F6 Puellās nautae vocant.`
- `F6 Fēmina puellae fābulam nārrat.`
- `F6 Agricolae in īnsulīs patriam servant.`
- `F6 Nauta fāmam agricolae laudat.`
- `F4 The sailors watch the roads **of the islands**. | Nautae viās īnsul___ spectant. | ārum`
- `F4 The farmer fights **with the girl**. | Agricola cum puell___ pugnat. | ā`
- `F8 Fēminae nautīs aquam parant.`
- `F8 Agricola cum puellīs in viā pugnat.`

*Set B*

- `F2 Puella vītam **fēminārum** laudat.`
- `F2 **Agricolae** terram servant.`
- `F2 Nauta **puellae** fābulam nārrat.`
- `F2 Nauta fāmam **puellae** laudat.`
- `F2 Fēmina in **īnsulā** pugnat.`
- `F2 Fēmina **nautīs** aquam portat.`
- `F2 Fēmina cum **nautīs** pugnat.`
- `F2 Agricola **stēllās** spectat.`
- `F6 Fēminās agricolae vocant.`
- `F6 Puella fēminae fābulam nārrat.`
- `F6 Nautae in silvīs patriam servant.`
- `F6 Agricola fāmam nautae laudat.`
- `F4 The girl loves the water **of the forests**. | Puella aquam silv___ amat. | ārum`
- `F4 The sailor saves the homeland **with the woman**. | Nauta cum fēmin___ patriam servat. | ā`
- `F8 Puellae agricolīs aquam parant.`
- `F8 Nauta cum fēminīs in viā pugnat.`

