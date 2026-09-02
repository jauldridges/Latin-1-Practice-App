"""
One storage module, two databases.

On a laptop this app is a single SQLite file, which is the right shape for it:
no server to install, no connection string, copy the file to back it up. Hosted
on Render it cannot be, because a web service's local disk does not survive a
redeploy — the year's practice history would vanish every time the app was
updated. So the hosted copy runs on Postgres.

Rather than an ORM, this is a thin dialect layer. The app's SQL is ordinary and
the differences that matter are few and boring, so they are handled here, in one
place, where they can be read:

    ?                     ->  %s
    INTEGER PRIMARY KEY AUTOINCREMENT  ->  BIGSERIAL PRIMARY KEY
    REAL                  ->  DOUBLE PRECISION   (Postgres REAL is 4 bytes and
                                                  loses precision on timestamps)
    IS NOT ?              ->  IS DISTINCT FROM %s
    MAX(a, b)             ->  GREATEST(a, b)     (two-argument scalar form)
    PRAGMA table_info     ->  information_schema
    executescript         ->  statements, one at a time

Which database is in use is decided by DATABASE_URL. Render sets it; a laptop
does not, and gets SQLite. Nothing about the connection is ever committed.
"""

import os
import re
import sqlite3

SQLITE, POSTGRES = "sqlite", "postgres"


def database_url():
    return os.environ.get("DATABASE_URL") or ""


def dialect_for(url):
    return POSTGRES if url.startswith(("postgres://", "postgresql://")) else SQLITE


# --------------------------------------------------------------------------
# Translation
# --------------------------------------------------------------------------

def _split_sql(sql):
    """Yield (is_code, text), where anything that is not code is left alone.

    Both quoted strings AND `--` comments are non-code. Comments matter as much
    as strings here: this schema's comments contain apostrophes and semicolons,
    and treating either as syntax splits statements in the wrong places or
    swallows half the file into a phantom string literal.
    """
    out, buf, i, n = [], [], 0, len(sql)

    def flush():
        if buf:
            out.append((True, "".join(buf)))
            del buf[:]

    while i < n:
        ch = sql[i]
        if ch == "'":
            flush()
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":   # '' is an escaped quote
                        j += 2
                        continue
                    break
                j += 1
            out.append((False, sql[i:j + 1]))
            i = j + 1
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            flush()
            j = sql.find("\n", i)
            j = n if j == -1 else j
            out.append((False, sql[i:j]))
            i = j
            continue
        buf.append(ch)
        i += 1
    flush()
    return out


_MAX2 = re.compile(r"\bMAX\s*\(([^(),]+),([^(),]+)\)", re.I)


def to_postgres(sql):
    """Rewrite this app's SQLite SQL for Postgres. Literals are left alone."""
    parts = []
    for is_code, text in _split_sql(sql):
        if not is_code:
            parts.append(text)
            continue
        text = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
                      "BIGSERIAL PRIMARY KEY", text, flags=re.I)
        text = re.sub(r"\bREAL\b", "DOUBLE PRECISION", text)
        text = _MAX2.sub(r"GREATEST(\1,\2)", text)
        text = re.sub(r"\bIS\s+NOT\s+\?", "IS DISTINCT FROM ?", text, flags=re.I)
        text = text.replace("%", "%%").replace("?", "%s")
        parts.append(text)
    return "".join(parts)


# --------------------------------------------------------------------------
# The connection
# --------------------------------------------------------------------------

class Conn(object):
    """A connection that speaks the app's SQL whichever database is underneath.

    Rows come back dict-like either way, so callers can keep doing row["x"]
    and dict(row) without caring.
    """

    def __init__(self, raw, dialect, target):
        self.raw = raw
        self.dialect = dialect
        self.target = target          # file path, or the URL with no password

    # -- the bits store.py uses -------------------------------------------
    def execute(self, sql, args=()):
        if self.dialect == POSTGRES:
            return self.raw.execute(to_postgres(sql), tuple(args))
        return self.raw.execute(sql, tuple(args))

    def executescript(self, script):
        if self.dialect == SQLITE:
            return self.raw.executescript(script)
        for statement in _statements(script):
            self.raw.execute(to_postgres(statement))
        self.raw.commit()

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()

    # -- the bits that genuinely differ -----------------------------------
    def table_columns(self, table):
        """Column names, or an empty set if the table does not exist."""
        if self.dialect == SQLITE:
            return {r["name"] for r in
                    self.raw.execute("PRAGMA table_info(%s)" % table).fetchall()}
        rows = self.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=?",
            (table,)).fetchall()
        return {r["column_name"] for r in rows}

    def reclaim_space(self, tables=()):
        """Actually remove deleted rows' bytes from storage.

        DELETE only marks space reusable; the text stays readable until
        something overwrites it. That is a correctness problem for the name
        purge, not a housekeeping one, so both dialects get a real rewrite.
        """
        if self.dialect == SQLITE:
            self.raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            level = self.raw.isolation_level
            self.raw.isolation_level = None       # VACUUM cannot run in a transaction
            try:
                self.raw.execute("VACUUM")
            finally:
                self.raw.isolation_level = level
            self.raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.raw.commit()
            return
        self.raw.commit()
        auto = self.raw.autocommit
        self.raw.autocommit = True
        try:
            for t in tables:
                self.raw.execute("VACUUM FULL %s" % t)
        finally:
            self.raw.autocommit = auto


def _statements(script):
    """Split a schema script into statements, ignoring semicolons in strings."""
    out, buf = [], []
    for is_code, text in _split_sql(script):
        if not is_code:
            buf.append(text)
            continue
        pieces = text.split(";")
        for piece in pieces[:-1]:
            buf.append(piece)
            # Keep the leading comments: Postgres is happy with them, and
            # dropping a statement because its BLOCK opens with a comment is
            # how every table after the first two once went missing.
            statement = "".join(buf).strip()
            if statement:
                out.append(statement)
            buf = []
        buf.append(pieces[-1])
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return [s for s in out if _has_sql(s)]


def _has_sql(statement):
    """True unless the statement is only comments and whitespace."""
    body = "\n".join(ln for ln in statement.splitlines()
                     if not ln.strip().startswith("--"))
    return bool(body.strip())


def safe_target(url):
    """The connection string with the password removed, for logs and screens."""
    return re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", url)


def connect(sqlite_path=None, url=None):
    """Open the database this deployment is configured for.

    DATABASE_URL wins when it is set, which is how Render points the app at
    Postgres without the repository knowing anything about it.
    """
    url = url if url is not None else database_url()
    if dialect_for(url) == POSTGRES:
        import psycopg                          # only needed when hosted
        from psycopg.rows import dict_row
        raw = psycopg.connect(url, row_factory=dict_row)
        return Conn(raw, POSTGRES, safe_target(url))
    path = sqlite_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA journal_mode=WAL")
    return Conn(raw, SQLITE, path)
