"""
Move a laptop's SQLite database into the hosted Postgres, once.

    DATABASE_URL=postgresql://... python3 migrate.py data/review.sqlite

This is a one-way trip by design. After it runs, the hosted database is the
record and the local file is a historical copy — keep it somewhere safe for a
while, then delete it, because it is the last place old data can hide.

Two things it will not do:

  * it will not run twice into a database that already holds practice data,
    because the second run would double every event and silently corrupt every
    Leitner schedule. Pass --force if you genuinely mean to.
  * it will not carry names across. The purge runs on the source before
    anything is copied, so a row that was keyed on a name is deleted rather
    than migrated — see identity.py.
"""

import sys

import db as dbmod
import store

# Copied in this order so a row never arrives before the thing it refers to.
TABLES = ["items", "events", "miss_reasons", "teaching_approvals",
          "teaching_overrides", "quizzes", "quiz_attempts", "roster",
          "decisions"]

# Assigned by the database, not carried across.
SKIP_COLUMNS = {"events": {"id"}, "miss_reasons": {"id"}, "decisions": {"id"}}


def copy_table(src, dst, table):
    cols = sorted(dst.table_columns(table) & src.table_columns(table)
                  - SKIP_COLUMNS.get(table, set()))
    if not cols:
        return 0
    rows = src.execute("SELECT %s FROM %s" % (", ".join(cols), table)).fetchall()
    if not rows:
        return 0
    marks = ",".join("?" * len(cols))
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(cols), marks)
    for r in rows:
        dst.execute(sql, tuple(r[c] for c in cols))
    dst.commit()
    return len(rows)


def already_has_data(dst):
    for table in ("events", "decisions", "roster"):
        if dst.execute("SELECT COUNT(*) AS n FROM %s" % table).fetchone()["n"]:
            return table
    return None


def main(argv):
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    source = args[0]

    url = dbmod.database_url()
    if dbmod.dialect_for(url) != dbmod.POSTGRES:
        print("DATABASE_URL is not set to a Postgres URL — nothing to migrate into.")
        return 2

    src = dbmod.connect(sqlite_path=source, url="")
    dst = dbmod.connect(url=url)
    print("from: %s" % source)
    print("to:   %s" % dbmod.safe_target(url))

    store.init_db(dst)
    # The purge runs on the SOURCE first, so name-keyed rows are deleted rather
    # than copied into the database that was promised to hold none.
    report = store.purge_names(src)
    if any(report.get(k) for k in ("events", "miss_reasons", "quiz_attempts", "roster_rows")):
        print("purged from the source before copying: %r" % (report,))

    busy = already_has_data(dst)
    if busy and not force:
        print("\nREFUSING: the target already has rows in %s." % busy)
        print("Running twice would double every event and corrupt every")
        print("spaced-repetition schedule. Pass --force if you mean it.")
        return 1

    total = 0
    for table in TABLES:
        n = copy_table(src, dst, table)
        total += n
        print("  %-20s %6d" % (table, n))
    print("\ncopied %d rows." % total)
    print("The hosted database is the record now. Keep the local file somewhere")
    print("safe for a while, then delete it — it is the last place old data hides.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
