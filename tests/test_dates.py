"""Dates are written "Friday October 30" everywhere a person reads one."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schooltime  # noqa: E402,F401
import dates       # noqa: E402
import drill       # noqa: E402
import goals       # noqa: E402


class TestDates(unittest.TestCase):
    def test_day_month_date(self):
        self.assertEqual(dates.day("2026-10-30"), "Friday October 30")
        self.assertEqual(dates.day("2026-10-30", year=True), "Friday October 30, 2026")
        noon = time.mktime((2026, 10, 30, 15, 5, 0, 0, 0, -1))
        self.assertEqual(dates.day(noon), "Friday October 30")
        self.assertEqual(dates.day_time(noon), "Friday October 30, 3:05 pm")
        self.assertEqual(dates.weekday(noon), "Friday")
        self.assertEqual(dates.day(""), "")
        self.assertEqual(dates.day("someday"), "someday")

    def test_everywhere_uses_it(self):
        self.assertEqual(goals.week_label("2026-10-29"), "Saturday October 24 – Friday October 30")
        self.assertEqual(drill.WEEK_LABELS["week_of_sep_8"], "Week of Monday September 7")
        self.assertEqual(goals.when_label("2026-12-18", now=time.mktime((2026, 10, 30, 12, 0, 0, 0, 0, -1))),
                         "Friday December 18")

    def test_no_old_style_dates_left_in_the_code(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for f in ("server.py", "goals.py", "drill.py", "teacher.py"):
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn('"%b', text, f)
            self.assertNotIn('"%a"', text, f)


if __name__ == "__main__":
    unittest.main()
