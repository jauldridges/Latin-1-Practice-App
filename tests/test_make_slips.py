"""The printed sheets.

The load-bearing property is the same one the rest of the app enforces in the
database: a name must not get in. The record sheet exists precisely so the
name-to-number link lives on paper in a classroom, so the generator prints the
numbers and leaves the names to handwriting -- and refuses anything that is not
an ID number, rather than helpfully printing it.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import make_slips  # noqa: E402


def write(lines):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "student-ids.txt")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return p


class TestReadingTheFile(unittest.TestCase):
    def test_plain_ids(self):
        good, bad = make_slips.read_ids(write(["403217", "418206", "905117"]))
        self.assertEqual(good, ["403217", "418206", "905117"])
        self.assertEqual(bad, [])

    def test_comments_and_blank_lines_are_skipped(self):
        good, bad = make_slips.read_ids(
            write(["# Block 3", "403217", "", "418206  # moved", ""]))
        self.assertEqual(good, ["403217", "418206"])
        self.assertEqual(bad, [])

    def test_a_name_is_refused_not_printed(self):
        good, bad = make_slips.read_ids(write(["403217", "Sam Tucker", "418206"]))
        self.assertEqual(good, ["403217", "418206"])
        self.assertEqual(bad, ["Sam Tucker"])

    def test_a_malformed_number_is_refused(self):
        # Five digits, seven digits, and a leading zero are all not ID-shaped.
        good, bad = make_slips.read_ids(write(["40321", "4032170", "043217", "403217"]))
        self.assertEqual(good, ["403217"])
        self.assertEqual(len(bad), 3)


class TestTheDashboardCsv(unittest.TestCase):
    """Once the roster is loaded the hosted class list is the authoritative
    copy of the numbers, and the app can hand it back if the original file is
    lost. So the generator has to read what the dashboard exports."""

    CSV = ["student_id,block,state,attempts,days_practised",
           "403217,Block 3,started,4,2",
           "418206,,nothing,0,0",
           '"905117",Block 5,started,9,3']

    def test_it_reads_the_export(self):
        good, bad = make_slips.read_ids(write(self.CSV))
        self.assertEqual(good, ["403217", "418206", "905117"])
        self.assertEqual(bad, [])

    def test_the_header_row_is_not_an_id(self):
        good, bad = make_slips.read_ids(write(self.CSV))
        self.assertNotIn("student_id", good)
        self.assertEqual(bad, [], "the header row was reported as a bad id")

    def test_the_other_columns_are_ignored(self):
        html = make_slips.record_html(
            make_slips.read_ids(write(self.CSV))[0], "example.test")
        # Block and state belong to the teacher's handwriting, not the print.
        self.assertNotIn("started", html)
        self.assertNotIn("Block 3", html)

    def test_a_plain_list_still_works(self):
        good, bad = make_slips.read_ids(write(["403217", "418206"]))
        self.assertEqual(good, ["403217", "418206"])
        self.assertEqual(bad, [])


class TestNothingButNumbersIsPrinted(unittest.TestCase):
    IDS = ["403217", "418206", "905117"]

    def test_a_name_in_the_source_never_reaches_either_sheet(self):
        path = write(["403217", "Sam Tucker", "418206", "Priya R.", "905117"])
        good, _ = make_slips.read_ids(path)
        for html in (make_slips.slips_html(good, "example.test"),
                     make_slips.record_html(good, "example.test")):
            self.assertNotIn("Sam", html)
            self.assertNotIn("Tucker", html)
            self.assertNotIn("Priya", html)

    def test_every_id_appears_once_on_the_slips(self):
        html = make_slips.slips_html(self.IDS, "example.test")
        for sid in self.IDS:
            self.assertEqual(html.count(sid), 1, "%s is not on exactly one slip" % sid)

    def test_every_id_appears_once_on_the_record(self):
        html = make_slips.record_html(self.IDS, "example.test")
        for sid in self.IDS:
            self.assertEqual(html.count(sid), 1)

    def test_the_two_sheets_list_the_ids_in_the_same_order(self):
        # Slip #7 has to be row 7, or handing them out and ticking them off
        # drift apart.
        order = lambda html: [s for s in self.IDS if s in html]  # noqa: E731
        slips = make_slips.slips_html(self.IDS, "example.test")
        record = make_slips.record_html(self.IDS, "example.test")
        pos = lambda html: sorted(self.IDS, key=html.index)      # noqa: E731
        self.assertEqual(pos(slips), pos(record))

    def test_the_record_leaves_the_name_column_empty(self):
        html = make_slips.record_html(self.IDS, "example.test")
        self.assertIn("Student name", html)
        # One empty name cell and one empty block cell per student.
        self.assertGreaterEqual(html.count("<td></td><td></td>"), len(self.IDS))

    def test_the_record_says_to_keep_it_off_the_computer(self):
        html = make_slips.record_html(self.IDS, "example.test")
        self.assertIn("Keep this paper in the classroom", html)

    def test_the_slips_carry_the_address_and_the_pin_instruction(self):
        html = make_slips.slips_html(self.IDS, "example.test")
        self.assertEqual(html.count("example.test"), len(self.IDS))
        self.assertIn("4-digit PIN", html)

    def test_html_special_characters_cannot_break_out(self):
        html = make_slips.record_html(["403217"], "<script>x</script>")
        self.assertNotIn("<script>", html)


class TestItFitsOnAPage(unittest.TestCase):
    """The first print run had the last row of slips sliding onto a page of
    its own, which ruins a sheet you are going to cut up, and the record sheet
    took nine physical pages to print five logical ones while every page label
    said "of 5". Both were laid out to fill the paper exactly, leaving nothing
    for a printer's unprintable edge.

    These assert the height budget rather than the rendering, because the
    numbers below are what the rendering follows.
    """

    def test_the_slips_fit_with_room_to_spare(self):
        rows = make_slips.PER_PAGE_SLIPS / float(make_slips.SLIP_COLUMNS)
        used = rows * make_slips.SLIP_HEIGHT_MM
        self.assertLessEqual(
            used, make_slips.PAGE_BUDGET_MM,
            "%g rows of %dmm is %gmm, over the %dmm budget — the last row will "
            "print on a page of its own" % (rows, make_slips.SLIP_HEIGHT_MM, used,
                                            make_slips.PAGE_BUDGET_MM))

    def test_the_record_rows_fit_with_room_to_spare(self):
        used = (make_slips.PER_PAGE_ROWS * make_slips.ROW_HEIGHT_MM
                + make_slips.RECORD_FURNITURE_MM)
        self.assertLessEqual(
            used, make_slips.PAGE_BUDGET_MM,
            "%d rows of %dmm plus %dmm of furniture is %dmm, over the %dmm "
            "budget — each page will spill onto a second one and the "
            "'page N of M' labels will be wrong"
            % (make_slips.PER_PAGE_ROWS, make_slips.ROW_HEIGHT_MM,
               make_slips.RECORD_FURNITURE_MM, used, make_slips.PAGE_BUDGET_MM))

    def test_the_budget_leaves_a_real_margin_on_letter(self):
        # Letter is the shorter page, so it sets the limit for A4 too.
        self.assertLess(make_slips.PAGE_BUDGET_MM, make_slips.LETTER_PRINTABLE_MM)
        slack = make_slips.LETTER_PRINTABLE_MM - make_slips.PAGE_BUDGET_MM
        self.assertGreaterEqual(slack, 15, "under 15mm of slack is not slack")

    def test_the_constants_actually_drive_the_css(self):
        # Otherwise the budget above is a comment, not a constraint.
        slips = make_slips.slips_html(["403217"], "example.test")
        record = make_slips.record_html(["403217"], "example.test")
        self.assertIn("height: %dmm" % make_slips.SLIP_HEIGHT_MM, slips)
        self.assertIn("repeat(%d, 1fr)" % make_slips.SLIP_COLUMNS, slips)
        self.assertIn("height: %dmm" % make_slips.ROW_HEIGHT_MM, record)

    def test_the_page_labels_match_the_pages_produced(self):
        ids = ["%06d" % (100000 + i) for i in range(1, 60)]
        html = make_slips.record_html(ids, "example.test")
        import math
        expected = int(math.ceil(len(ids) / float(make_slips.PER_PAGE_ROWS)))
        self.assertEqual(html.count("page 1 of %d" % expected), 1)
        self.assertEqual(html.count("<table>"), expected)


class TestTheAddress(unittest.TestCase):
    def test_it_comes_from_render_yaml(self):
        # So the printed address cannot drift from the service that answers.
        self.assertEqual(make_slips.site_url(), "magisters-practice-app.onrender.com")


if __name__ == "__main__":
    unittest.main()
