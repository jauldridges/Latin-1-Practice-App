"""
The school's clock.

"Today", "this week", "due Friday" and the dashboard's midnight all mean the
school's day, not the server's. Render runs in UTC, where Friday ends at 8pm in
Massachusetts -- so a student finishing homework on Friday evening would find it
counted late. Importing this module sets the process clock to the school's time
zone once, before anything asks what day it is.

Timestamps in the database are unaffected: they are seconds since 1970 and
mean the same instant everywhere. Only the reading of them into days changes.

LATIN_TIMEZONE overrides it (any IANA name, e.g. America/Chicago).
"""

import os
import time

SCHOOL_TZ = os.environ.get("LATIN_TIMEZONE") or "America/New_York"

os.environ["TZ"] = SCHOOL_TZ
if hasattr(time, "tzset"):      # not on Windows, where the laptop's own clock is used
    time.tzset()
