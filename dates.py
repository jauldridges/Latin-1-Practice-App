"""
How the app writes a date, everywhere a person reads one: "Friday October 30"
-- the day of the week, the month, the day (the teacher's rule, October 2026),
with ", 2026" added only where the year is needed. One place, so no screen
drifts back to "Fri 30 Oct" or "Oct 30".

Spreadsheet and backup files keep 2026-10-30: they are read by programs.
"""

import time


def _struct(when):
    """A time.struct_time from a timestamp, a "YYYY-MM-DD" string or a struct_time."""
    if isinstance(when, time.struct_time):
        return when
    if isinstance(when, (int, float)):
        return time.localtime(when)
    return time.strptime(str(when)[:10], "%Y-%m-%d")


def day(when, year=False):
    """"Friday October 30" (", 2026" too with year=True). Empty for nothing;
    anything that isn't a date comes back as written."""
    if when is None or when == "":
        return ""
    try:
        t = _struct(when)
    except ValueError:
        return str(when)
    out = "%s %s %d" % (time.strftime("%A", t), time.strftime("%B", t), t.tm_mday)
    return out + (", %d" % t.tm_year if year else "")


def day_time(when):
    """"Friday October 30, 3:15 pm"."""
    t = _struct(when)
    hour = t.tm_hour % 12 or 12
    return "%s, %d:%02d %s" % (day(t), hour, t.tm_min, "am" if t.tm_hour < 12 else "pm")


def weekday(when):
    """"Friday"."""
    return time.strftime("%A", _struct(when))


def span(first, last):
    """"Saturday October 24 – Friday October 30"."""
    return "%s – %s" % (day(first), day(last))
