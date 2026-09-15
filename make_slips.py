"""
Print the ID numbers: slips to hand out, and the paper record to keep.

    python3 make_slips.py

Reads the ID numbers from out/student-ids.txt (whatever make_ids.py wrote) and
writes two files next to it:

    out/slips.html      one slip per student, to print and cut up
    out/id-record.html  the ID-to-name record, to print and fill in by hand

Open either in a browser and print it. Both live in out/, which is gitignored,
because a public list of every valid ID would leave only the PIN between a
stranger and a student's record.

WHY THE RECORD SHEET IS BLANK
The app holds an ID number and nothing else that identifies a person. That is
the commitment, and it means the link between a number and a child exists in
exactly one place: a piece of paper in your classroom. This generator therefore
prints the numbers and leaves the names to your handwriting. It never asks for
a name, never stores one, and there is no version of it that does.
"""

import os
import sys

import identity

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IDS = os.path.join(ROOT, "out", "student-ids.txt")
DEFAULT_URL = "magisters-practice-app.onrender.com"

# US Letter is the shorter page (279mm against A4's 297), so it sets the
# height budget: 259mm of printable area inside 10mm margins. Both sheets are
# laid out to use about 225mm of that. The slack is not waste — a printer's
# unprintable edge, a "Default" margin that is not 10mm, or a scale slightly
# off 100% will each eat several millimetres, and the symptom is the last row
# sliding onto a page of its own, which ruins a sheet meant to be cut up.
SLIP_COLUMNS = 3
PER_PAGE_SLIPS = 12       # 3 across, 4 down
SLIP_HEIGHT_MM = 55       # 4 rows = 220mm
PER_PAGE_ROWS = 22
ROW_HEIGHT_MM = 8         # 22 rows = 176mm
RECORD_FURNITURE_MM = 50  # heading, warning box, table head and footer

# Letter's printable height inside 10mm margins, and the budget we hold to.
# The gap between them is what absorbs a printer's unprintable edge or a
# "Default" margin that is not 10mm. Spend it and the last row of a sheet
# slides onto a page of its own, which is fatal for a sheet meant to be cut up.
LETTER_PRINTABLE_MM = 259
PAGE_BUDGET_MM = 235


def read_ids(path):
    """The numbers, in order, with anything that is not an ID handed back.

    `#` starts a comment and blank lines are skipped, matching the roster
    loader, so a file with notes in it still works.

    It also reads the dashboard's own CSV export (`/teacher/export.csv`),
    whose first column is the student id. That matters more than it looks:
    once the roster is loaded, the hosted class list is the authoritative
    copy of the numbers, and the file make_ids.py wrote is just the first
    draft of it. If that file is ever lost, the app can hand the list back.
    """
    good, bad = [], []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if "," in line:                       # a CSV row: id comes first
                line = line.split(",", 1)[0].strip()
            line = line.strip('"').strip("'").strip()
            if line.lower() == "student_id":      # the CSV's header row
                continue
            if identity.is_valid(line):
                good.append(identity.normalize(line))
            else:
                bad.append(line[:40])
    return good, bad


def site_url():
    """The address on the slips, taken from render.yaml so it cannot drift
    away from the service that actually answers."""
    try:
        import yaml
        with open(os.path.join(ROOT, "render.yaml"), encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        for svc in doc.get("services", []):
            if svc.get("type") == "web" and svc.get("name"):
                return "%s.onrender.com" % svc["name"]
    except Exception:
        pass
    return DEFAULT_URL


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


SLIP_CSS = """
@page { size: auto; margin: 10mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 0; color: #111; }
.sheet { display: grid; grid-template-columns: repeat(%(cols)d, 1fr); gap: 0; }
.slip { border: 1px dashed #999; padding: 6mm 5mm; height: %(slip_h)dmm;
        display: flex; flex-direction: column; justify-content: space-between;
        page-break-inside: avoid; break-inside: avoid; }
.title { font-size: 9pt; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: #444; }
.url { font-size: 10pt; font-weight: 600; margin-top: 1.5mm; word-break: break-all; }
.num-label { font-size: 8pt; color: #666; margin-top: 2mm; }
.num { font-size: 24pt; font-weight: 700; letter-spacing: .08em; font-variant-numeric: tabular-nums; }
.how { font-size: 8pt; line-height: 1.3; color: #333; }
.seq { font-size: 7pt; color: #aaa; text-align: right; }
@media screen { body { background: #f4f4f4; padding: 16px; } .sheet { background: #fff; } }
"""

SLIP = """      <div class="slip">
        <div>
          <div class="title">Latin I &middot; practice</div>
          <div class="url">%(url)s</div>
        </div>
        <div>
          <div class="num-label">Your number</div>
          <div class="num">%(sid)s</div>
        </div>
        <div>
          <div class="how">Type your number, then <b>choose a 4-digit PIN</b>.
          Use the same PIN every time. Forgotten it? Ask me &mdash; I can reset it.<br>
          Add the page to your home screen and it behaves like an app.</div>
          <div class="seq">#%(seq)d</div>
        </div>
      </div>
"""


def slips_html(ids, url):
    parts = ["<!doctype html><html><head><meta charset='utf-8'>",
             "<title>Latin I &mdash; student slips</title>",
             "<style>%s</style></head><body>"
             % (SLIP_CSS % {"slip_h": SLIP_HEIGHT_MM, "cols": SLIP_COLUMNS})]
    for start in range(0, len(ids), PER_PAGE_SLIPS):
        page = ids[start:start + PER_PAGE_SLIPS]
        parts.append("<div class='sheet' style='page-break-after:always'>")
        for offset, sid in enumerate(page):
            parts.append(SLIP % {"url": esc(url), "sid": esc(sid),
                                 "seq": start + offset + 1})
        # Keep the grid square on a short last page so slips stay a fixed size.
        for _ in range(len(page), PER_PAGE_SLIPS):
            parts.append("      <div class='slip' style='border-style:none'></div>\n")
        parts.append("</div>")
    parts.append("</body></html>")
    return "".join(parts)


RECORD_CSS = """
@page { size: auto; margin: 14mm; }
body { font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 0; color: #111; }
h1 { font-size: 13pt; margin: 0 0 2mm; }
.warn { border: 2px solid #111; padding: 2mm 3mm; font-size: 8.5pt; line-height: 1.3; margin: 0 0 3mm; }
table { border-collapse: collapse; width: 100%%; page-break-inside: auto; }
th, td { border: 1px solid #999; padding: 0; font-size: 10pt; }
th { background: #eee; font-size: 8pt; text-transform: uppercase; letter-spacing: .04em; padding: 2mm 2mm; text-align: left; }
td { height: %(row_h)dmm; padding: 0 2mm; }
td.num { font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: .06em; width: 26mm; }
td.seq { color: #888; font-size: 8pt; width: 10mm; text-align: right; }
.page { page-break-after: always; }
.foot { font-size: 8pt; color: #555; margin-top: 2mm; }
@media screen { body { background: #f4f4f4; padding: 16px; } .page { background: #fff; padding: 10mm; margin-bottom: 16px; } }
"""


def record_html(ids, url):
    parts = ["<!doctype html><html><head><meta charset='utf-8'>",
             "<title>Latin I &mdash; ID number record</title>",
             "<style>%s</style></head><body>"
             % (RECORD_CSS % {"row_h": ROW_HEIGHT_MM})]
    pages = [ids[i:i + PER_PAGE_ROWS] for i in range(0, len(ids), PER_PAGE_ROWS)]
    for pno, page in enumerate(pages, 1):
        parts.append("<div class='page'>")
        parts.append("<h1>Latin I &mdash; ID number record "
                     "<span style='font-weight:400;font-size:10pt;color:#666'>"
                     "(page %d of %d)</span></h1>" % (pno, len(pages)))
        parts.append(
            "<div class='warn'><b>Keep this paper in the classroom. "
            "Do not photograph it, email it, or type it into a computer.</b><br>"
            "The app stores a number and nothing else that identifies a student "
            "&mdash; no names, no emails. This sheet is the only thing that "
            "connects a number to a child, and that is the whole point. "
            "A number on its own tells a stranger nothing.</div>")
        parts.append("<table><tr><th></th><th>ID number</th>"
                     "<th>Student name</th><th>Block</th></tr>")
        for offset, sid in enumerate(page):
            seq = (pno - 1) * PER_PAGE_ROWS + offset + 1
            parts.append("<tr><td class='seq'>%d</td><td class='num'>%s</td>"
                         "<td></td><td></td></tr>" % (seq, esc(sid)))
        parts.append("</table>")
        parts.append("<div class='foot'>%s &middot; students sign in with this "
                     "number and a 4-digit PIN they choose. A forgotten PIN is "
                     "reset from Class list &mdash; you never need to know it."
                     "</div>" % esc(url))
        parts.append("</div>")
    parts.append("</body></html>")
    return "".join(parts)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    path = args[0] if args else DEFAULT_IDS
    url = DEFAULT_URL
    if "--url" in argv:
        url = argv[argv.index("--url") + 1]
    else:
        url = site_url()

    if not os.path.exists(path):
        print("No ID file at %s" % path)
        print()
        print("If numbers are ALREADY on the class list, do NOT run make_ids.py.")
        print("It would issue 120 different numbers and the slips would name")
        print("students the roster has never heard of. Instead, either:")
        print()
        print("  - point this at wherever the list actually is:")
        print("        python3 make_slips.py ~/Desktop/whatever-it-is.txt")
        print()
        print("  - or take the list back from the app, which is now the")
        print("    authoritative copy: Teacher dashboard -> Download this")
        print("    table as a spreadsheet, then")
        print("        python3 make_slips.py ~/Downloads/practice-YYYY-MM-DD.csv")
        print()
        print("Only if no roster exists anywhere is a fresh list right:")
        print("        mkdir -p out && python3 make_ids.py 120 > out/student-ids.txt")
        return 2

    ids, bad = read_ids(path)
    if bad:
        print("Skipped %d line(s) that are not ID numbers:" % len(bad))
        for b in bad[:5]:
            print("   %r" % b)
    if not ids:
        print("No usable ID numbers in %s" % path)
        return 2

    out_dir = os.path.dirname(os.path.abspath(path))
    slips_path = os.path.join(out_dir, "slips.html")
    record_path = os.path.join(out_dir, "id-record.html")
    with open(slips_path, "w", encoding="utf-8") as fh:
        fh.write(slips_html(ids, url))
    with open(record_path, "w", encoding="utf-8") as fh:
        fh.write(record_html(ids, url))

    print("%d ID numbers, address %s" % (len(ids), url))
    print()
    print("  slips to cut up : %s" % slips_path)
    print("  record to keep  : %s" % record_path)
    print()
    print("Open each in a browser and print. In the print dialog turn OFF")
    print("headers and footers, and set margins to Default.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
