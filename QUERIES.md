# Seeing student work

There is no teacher dashboard, by design — for 88 students a direct query is
faster to read than a dashboard is to build. Everything below runs against the
one file the apps write to.

```bash
sqlite3 data/review.sqlite
```

Then paste a query. `.headers on` and `.mode column` once at the start makes the
output readable. `.quit` to leave.

Every query below has been run against a real database.

---

## Where the data lives

| Table | One row per | Use it for |
|-------|-------------|-----------|
| `events` | one attempt at one question | everything about practice and performance |
| `miss_reasons` | one what-went-wrong selection | *why* they missed, tagged to the node that explains it |
| `quiz_attempts` | one student's sitting of one quiz | quiz answers and results |
| `items` | one question | review state, flags |
| `teaching_approvals` | one approved node | which explanations are live |

`events` is append-only. Nothing is ever updated or deleted, so it is the
complete history and the source of every derived figure.

---

## Who has been practising

```sql
SELECT student_id,
       COUNT(*)                                            AS attempts,
       SUM(result='right')                                 AS right,
       ROUND(100.0*SUM(result='right')/COUNT(*))           AS pct,
       DATE(MAX(timestamp), 'unixepoch', 'localtime')      AS last_seen
FROM events
GROUP BY student_id
ORDER BY attempts DESC;
```

## Who has NOT practised this week

```sql
SELECT student_id, DATE(MAX(timestamp),'unixepoch','localtime') AS last_seen
FROM events
GROUP BY student_id
HAVING MAX(timestamp) < strftime('%s','now') - 7*86400;
```

## Which concepts the class is getting wrong

The one worth checking before you plan a lesson.

```sql
SELECT spec_node_id,
       COUNT(*)                                   AS attempts,
       SUM(result='wrong')                        AS missed,
       ROUND(100.0*SUM(result='wrong')/COUNT(*))  AS pct_wrong
FROM events
WHERE spec_node_id IS NOT NULL
GROUP BY spec_node_id
HAVING attempts >= 5
ORDER BY pct_wrong DESC
LIMIT 15;
```

## *Why* they are getting it wrong

This is the question the what-went-wrong menu exists to answer — "how many
students this week said they matched the ending instead of the gender."

```sql
SELECT reason_node, reason_text, COUNT(*) AS times
FROM miss_reasons
WHERE timestamp > strftime('%s','now') - 7*86400
GROUP BY reason_node, reason_text
ORDER BY times DESC
LIMIT 20;
```

## Questions students are contesting

Contested questions return to your flagged queue automatically; this shows the
pattern.

```sql
SELECT item_id, COUNT(*) AS contested_by
FROM miss_reasons
WHERE contested = 1
GROUP BY item_id
ORDER BY contested_by DESC;
```

## One student, everything

```sql
SELECT DATE(timestamp,'unixepoch','localtime') AS day,
       item_id, spec_node_id, response, result, context
FROM events
WHERE student_id = 'sam'          -- lower case; see the identity note
ORDER BY timestamp DESC
LIMIT 50;
```

## Practice versus proctored

Practice diagnoses; proctored certifies. Never mix them.

```sql
SELECT context,
       COUNT(*)                                   AS attempts,
       ROUND(100.0*SUM(result='right')/COUNT(*))  AS pct_right
FROM events
GROUP BY context;
```

## A quiz, student by student

```sql
SELECT student_id,
       DATETIME(submitted_at,'unixepoch','localtime') AS submitted
FROM quiz_attempts
WHERE quiz_id = 'PUT_QUIZ_ID_HERE' AND submitted_at IS NOT NULL
ORDER BY student_id;
```

(The per-question breakdown is easier to read on the quiz's own page in the app.)

## Everything out to a spreadsheet

```bash
sqlite3 -header -csv data/review.sqlite "SELECT * FROM events;" > events.csv
```

Opens in Excel or Google Sheets.

---

## Backing it up

**Do this weekly.** The whole year of student history is one file.

```bash
cp data/review.sqlite ~/Desktop/latin-backup-$(date +%Y-%m-%d).sqlite
```

Safe while the app is running (SQLite is in WAL mode), but stopping the app
first is safest.
