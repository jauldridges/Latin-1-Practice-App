"""
Who is allowed in.

This exists because of one sentence in the build spec — "no accounts or login
yet" — and one sentence from Jack: kids have to be able to do this at home,
even when he isn't there. Those are only in tension until the app leaves the
laptop. On a laptop on the school LAN, "no login" is fine. On the open
internet it would put ~88 minors' practice records and every teacher tool on a
public URL, so the moment the app is reachable from home it needs a door.

Two doors, deliberately different, because the two users are not alike:

  teacher   a real password. One person, one secret, and everything behind it
            — the dashboard, the review tool, quiz building — can change what
            students see or read every student's record.

  student   an ID number and a four-digit PIN they choose the first time.
            Not a password: fourteen-year-olds forgetting passwords at 9pm is
            the failure mode that kills home practice, and nothing behind this
            door is a grade. The PIN exists to stop one student practising as
            another. A forgotten one is cleared by the teacher — there is no
            email address in this system to send a reset to.

Both are cookies, so it is once per device per year, not once per session.

This module only ANSWERS "may they?"; server.py does the gating, in a single
before_request keyed on URL prefix. One mechanism, not two: a per-route
decorator fails by being forgotten on the route you add next month, and that
route is the leak.

LOCAL DEFAULT: with no password set and LATIN_PUBLIC unset, nothing is gated
and the laptop workflow is exactly as it was. Turning on LATIN_PUBLIC without
a password is refused at startup rather than served insecurely — a deployment
that silently forgot the password is the one outcome worth crashing over.
"""

import hmac
import os

from flask import session

TEACHER_KEY = "is_teacher"
STUDENT_KEY = "student_id"      # the signed-in student's ID, or absent


def teacher_password():
    return os.environ.get("LATIN_TEACHER_PASSWORD") or ""


def is_public():
    """True when the app is reachable from outside the LAN. Set by the deploy
    config; never guessed from the request, because a proxy can lie."""
    return os.environ.get("LATIN_PUBLIC", "").strip().lower() in ("1", "true", "yes")


def check_config():
    """Called at import. Returns a fatal message, or None."""
    if is_public() and not teacher_password():
        return ("LATIN_PUBLIC is set but LATIN_TEACHER_PASSWORD is empty. That "
                "would publish the teacher dashboard, the review tool and every "
                "student's practice record on a public URL. Set a password and "
                "restart.")
    return None


def teacher_gate_on():
    return bool(teacher_password())


def matches(given, expected):
    """Constant-time, so the password cannot be guessed a character at a time."""
    return bool(expected) and hmac.compare_digest(str(given or ""), str(expected))


def is_teacher():
    return (not teacher_gate_on()) or bool(session.get(TEACHER_KEY))


def student_ok():
    """A student is signed in on this device.

    Unlike the teacher gate there is no "off" switch. A shared class code used
    to serve this purpose and is gone: it let anyone who knew the code practise
    as any student, which is precisely what the PIN is for.
    """
    return bool(session.get(STUDENT_KEY))
