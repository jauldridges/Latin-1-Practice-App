"""
One web app, two tools:
  /review  - teacher-facing review tool (Application 1)
  /drill   - student-facing vocabulary drill (Application 2)

Both share answercheck.py. Data lives in a local SQLite file (store.py). Run
locally, open on a phone over the LAN. No accounts, no hosting.

    python run.py           # http://0.0.0.0:5000

The drill routes are added in build step 4; this file grows, it does not fork.
"""

import io
import os
import time

import yaml
from flask import (Flask, g, redirect, render_template, request, Response,
                   url_for, abort)

import checks
import dataio
import drill
import practice
import store
from answercheck import check as check_answer

app = Flask(__name__)
DB_PATH = os.environ.get("LATIN_DB", store.DEFAULT_DB)

# Source data is read once at startup. It never changes under the app.
_SPEC = dataio.load_spec()
_EXEMPLARS = dataio.load_exemplars()
_VALID_NODES = set(_SPEC)
_ALLOWED_LATIN = dataio.allowed_latin(_EXEMPLARS)
_NODE_LABEL = {nid: n.get("label", "") for nid, n in _SPEC.items()}
_DRILL_WORDS = dataio.load_drill_words()


def get_db():
    if "db" not in g:
        g.db = store.connect(DB_PATH)
        store.init_db(g.db)
    return g.db


@app.teardown_appcontext
def _close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.template_filter("nodelabel")
def nodelabel(node_id):
    return _NODE_LABEL.get(node_id, "")


# ==========================================================================
# Landing
# ==========================================================================

@app.route("/")
def index():
    return render_template("index.html", counts=store.counts(get_db()))


# ==========================================================================
# Application 1 — the review tool
# ==========================================================================

def ensure_seeded(db):
    """On first use, import the generated bank automatically so the teacher
    lands straight in a working queue instead of an empty screen. Runs the
    mechanical checks exactly as a manual import would. No-op once seeded."""
    if store.counts(db)["total"] > 0:
        return None
    items = dataio.load_bank()
    flags_by_item, report = checks.run_all(items, _VALID_NODES, _ALLOWED_LATIN)
    store.import_items(db, items, flags_by_item, os.path.basename(dataio.BANK_FILE))
    return report


@app.route("/review")
def review_queue():
    db = get_db()
    ensure_seeded(db)
    nodes = store.node_queue_counts(db)
    node_rows = [{"node": n, "label": _NODE_LABEL.get(n, ""), "count": c} for n, c in nodes]
    return render_template("review_queue.html", nodes=node_rows,
                           counts=store.counts(db))


@app.route("/review/import", methods=["POST"])
def review_import():
    db = get_db()
    items = dataio.load_bank()
    flags_by_item, report = checks.run_all(items, _VALID_NODES, _ALLOWED_LATIN)
    stats = store.import_items(db, items, flags_by_item, os.path.basename(dataio.BANK_FILE))
    # Build a human import summary.
    summary = {
        "inserted": stats["inserted"], "updated": stats["updated"],
        "flagged": report["n_flagged"], "total": report["n_items"],
        "by_check": report["by_check"], "by_level": report["by_level"],
        "literal_check4": report["literal_check4_explain_items_with_a_noncausal_option"],
        "literal_check6a": report["literal_check6a_macron_items_without_macron_answers"],
    }
    return render_template("review_import.html", summary=summary, counts=store.counts(db))


@app.route("/review/node/<node_id>")
def review_node(node_id):
    db = get_db()
    item = store.next_unreviewed_in_node(db, node_id)
    if item is None:
        return render_template("review_done.html", where="node", node_id=node_id,
                               label=_NODE_LABEL.get(node_id, ""), counts=store.counts(db))
    remaining = dict(store.node_queue_counts(db)).get(node_id, 0)
    return render_template("review_item.html", item=item, queue="node",
                           node_id=node_id, remaining=remaining)


@app.route("/review/flagged")
def review_flagged():
    db = get_db()
    item = store.next_flagged(db)
    if item is None:
        return render_template("review_done.html", where="flagged",
                               counts=store.counts(db))
    remaining = store.counts(db)["flagged"]
    return render_template("review_item.html", item=item, queue="flagged",
                           node_id=item["node_id"], remaining=remaining)


@app.route("/review/action", methods=["POST"])
def review_action():
    db = get_db()
    item_id = request.form["item_id"]
    action = request.form["action"]
    queue = request.form.get("queue", "node")
    node_id = request.form.get("node_id", "")
    if action == "approve":
        store.set_review(db, item_id, "approved")
    elif action == "reject":
        reason = request.form.get("reason") or "rejected"
        store.set_review(db, item_id, "rejected", reason=reason)
    elif action == "skip":
        store.skip_item(db, item_id)
    else:
        abort(400)
    if queue == "flagged":
        return redirect(url_for("review_flagged"))
    return redirect(url_for("review_node", node_id=node_id))


@app.route("/review/edit/<item_id>", methods=["GET", "POST"])
def review_edit(item_id):
    db = get_db()
    item = store.get_item(db, item_id)
    if item is None:
        abort(404)
    queue = request.values.get("queue", "node")
    node_id = request.values.get("node_id", item["node_id"])
    if request.method == "POST":
        text = request.form["payload"]
        try:
            new_payload = yaml.safe_load(text)
            assert isinstance(new_payload, dict) and new_payload.get("id"), "must be a mapping with an id"
        except Exception as e:  # noqa: BLE001
            return render_template("review_edit.html", item=item, payload_text=text,
                                   error=str(e), queue=queue, node_id=node_id)
        store.set_review(db, item_id, "approved", new_payload=new_payload, edited=True)
        if queue == "flagged":
            return redirect(url_for("review_flagged"))
        return redirect(url_for("review_node", node_id=node_id))
    payload_text = yaml.safe_dump(item["payload"], allow_unicode=True, sort_keys=False)
    return render_template("review_edit.html", item=item, payload_text=payload_text,
                           error=None, queue=queue, node_id=node_id)


@app.route("/review/export")
def review_export():
    db = get_db()
    payloads = store.approved_payloads(db)
    doc = {"items": payloads}
    text = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    header = ("# Approved questions exported from the review tool\n"
              f"# {len(payloads)} items · {time.strftime('%Y-%m-%d %H:%M')}\n\n")
    return Response(header + text, mimetype="text/yaml",
                    headers={"Content-Disposition": "attachment; filename=latin1-items-approved.yaml"})


# ==========================================================================
# Application 2 — the vocabulary drill (build step 4, wired below)
# ==========================================================================

@app.route("/drill")
def drill_home():
    return render_template("drill_home.html", weeks=drill.WEEK_ORDER,
                           week_labels=drill.WEEK_LABELS)


@app.route("/drill/start", methods=["POST"])
def drill_start():
    student = (request.form.get("student") or "").strip()
    week = request.form.get("week", "current")
    direction = request.form.get("direction", "both")
    if not student:
        return redirect(url_for("drill_home"))
    return redirect(url_for("drill_session", student=student, week=week, direction=direction))


@app.route("/drill/session")
def drill_session():
    db = get_db()
    student = request.args["student"]
    week = request.args.get("week", "current")
    direction = request.args.get("direction", "both")
    events = store.events_for_student(db, student)
    card = drill.next_card(_DRILL_WORDS, events, week=week, direction=direction)
    if card is None:
        return render_template("drill_none.html", student=student, week=week)
    return render_template("drill_card.html", student=student, week=week,
                           direction=direction, card=card)


@app.route("/drill/answer", methods=["POST"])
def drill_answer():
    db = get_db()
    student = request.form["student"]
    week = request.form.get("week", "current")
    direction = request.form.get("direction", "both")
    latin = request.form["latin"]
    ask = request.form["ask"]                 # 'la_en' or 'en_la'
    response = request.form.get("response", "")
    latency_ms = request.form.get("latency_ms", type=int)
    word = drill.find_word(_DRILL_WORDS, latin)
    if word is None:
        abort(400)
    accepted = drill.accepted_for(word, ask)
    result = check_answer(response, accepted, macron_matters=False)
    item_id = drill.item_id_for(word, ask)
    store.record_event(db, student, item_id, drill.node_for(word), response, result,
                       latency_ms=latency_ms, context="practice", version="v1")
    if result == "close":
        # Close never counts against the student and never reveals the answer;
        # re-show the same card and let them retype. (The attempt is still
        # logged as a "close" event.)
        card = drill.card_for(word, ask)
        return render_template("drill_card.html", student=student, week=week,
                               direction=direction, card=card,
                               notice="So close — check your spelling and try again.")
    return render_template("drill_feedback.html", student=student, week=week,
                           direction=direction, word=word, ask=ask, response=response,
                           result=result, model=accepted[0])


# ==========================================================================
# Application 3 — grammar practice (serves APPROVED questions only)
# ==========================================================================

VALID_CONTEXTS = {"practice", "homework", "classwork", "quiz", "exam"}


def _taught_now():
    return practice.taught_nodes(_SPEC)


@app.route("/practice")
def practice_home():
    db = get_db()
    taught = _taught_now()
    approved = store.approved_items(db)
    ready = practice.practiceable(approved, taught)
    by_node = {}
    for it in ready:
        by_node.setdefault(it["node"], 0)
        by_node[it["node"]] += 1
    nodes = [{"node": n, "label": _NODE_LABEL.get(n, ""), "count": c}
             for n, c in sorted(by_node.items())]
    return render_template("practice_home.html", nodes=nodes,
                           n_ready=len(ready), n_approved=len(approved),
                           n_locked=len(approved) - len(ready))


@app.route("/practice/start", methods=["POST"])
def practice_start():
    student = (request.form.get("student") or "").strip()
    if not student:
        return redirect(url_for("practice_home"))
    node = request.form.get("node") or ""
    ctx = request.form.get("context", "practice")
    return redirect(url_for("practice_session", student=student, node=node, context=ctx))


@app.route("/practice/session")
def practice_session():
    db = get_db()
    student = request.args["student"]
    node = request.args.get("node") or None
    ctx = request.args.get("context", "practice")
    if ctx not in VALID_CONTEXTS:
        ctx = "practice"
    approved = store.approved_items(db)
    events = store.events_for_student(db, student)
    item = practice.select_question(approved, events,
                                    allowed_nodes=_taught_now(), node_id=node)
    if item is None:
        return render_template("practice_none.html", student=student, node=node,
                               n_approved=len(approved))
    return render_template("practice_question.html", student=student, item=item,
                           node=node, context=ctx, notice=None,
                           label=_NODE_LABEL.get(item["node"], ""))


@app.route("/practice/answer", methods=["POST"])
def practice_answer():
    db = get_db()
    student = request.form["student"]
    item_id = request.form["item_id"]
    node = request.form.get("node") or None
    ctx = request.form.get("context", "practice")
    if ctx not in VALID_CONTEXTS:
        ctx = "practice"
    latency = request.form.get("latency_ms", type=int)

    row = store.get_item(db, item_id)
    if row is None or row["review_status"] != "approved":
        abort(404)
    item = row["payload"]
    fmt = item.get("format")

    box_results = tag_results = None
    picked = typed = None

    if fmt == "choice":
        picked = request.form.get("picked")
        result = practice.grade_choice(item, picked)
    elif fmt == "boxes":
        responses = request.form.getlist("box")
        result, box_results = practice.grade_boxes(item, responses)
    elif fmt == "tag-then-translate":
        cases = request.form.getlist("case")
        jobs = request.form.getlist("job")
        result, tag_results = practice.grade_tags(item, cases, jobs)
    else:                                   # self-check
        typed = request.form.get("typed", "")
        result = "self"

    # CLOSE never counts against the student and never opens the menu:
    # re-show the question and let them retype. The attempt is still logged.
    if result == "close":
        store.record_event(db, student, item_id, item.get("node"),
                           practice.response_summary(item, box_results, picked, typed),
                           "close", latency_ms=latency, context=ctx, version="v1")
        return render_template("practice_question.html", student=student, item=item,
                               node=node, context=ctx,
                               label=_NODE_LABEL.get(item["node"], ""),
                               notice="So close — check your spelling and try again.")

    if result != "self":
        store.record_event(db, student, item_id, item.get("node"),
                           practice.response_summary(item, box_results, picked, typed),
                           result, latency_ms=latency, context=ctx, version="v1")

    return render_template("practice_feedback.html", student=student, item=item,
                           node=node, context=ctx, result=result,
                           box_results=box_results, tag_results=tag_results,
                           picked=picked, typed=typed,
                           menu=practice.menu_for(item) if result == "wrong" else None,
                           label=_NODE_LABEL.get(item["node"], ""))


@app.route("/practice/selfreport", methods=["POST"])
def practice_selfreport():
    """Self-check and the translation half of tag-then-translate: the student
    reports how they did. What they typed is stored next to what they claimed."""
    db = get_db()
    student = request.form["student"]
    item_id = request.form["item_id"]
    node = request.form.get("node") or None
    ctx = request.form.get("context", "practice")
    reported = request.form.get("reported", "")
    typed = request.form.get("typed", "")
    row = store.get_item(db, item_id)
    if row is None:
        abort(404)
    item = row["payload"]
    result = {"had": "right", "close": "close", "missed": "wrong"}.get(reported, "wrong")
    store.record_event(db, student, item_id, item.get("node"),
                       f"[self:{reported}] {typed}"[:200], result,
                       context=ctx, version="v1")
    if result == "wrong":
        return render_template("practice_feedback.html", student=student, item=item,
                               node=node, context=ctx, result="wrong",
                               box_results=None, tag_results=None, picked=None,
                               typed=typed, menu=practice.menu_for(item),
                               label=_NODE_LABEL.get(item["node"], ""), self_done=True)
    return redirect(url_for("practice_session", student=student, node=node or "", context=ctx))


@app.route("/practice/menu", methods=["POST"])
def practice_menu():
    """Record what the student said went wrong, tagged to the node that explains
    that mistake. Contesting a question returns it to the flagged queue — this
    is the live-fire path."""
    db = get_db()
    student = request.form["student"]
    item_id = request.form["item_id"]
    node = request.form.get("node") or None
    ctx = request.form.get("context", "practice")
    key = request.form.get("reason_key", "")
    text = request.form.get("reason_text", "")
    reason_node = request.form.get("reason_node") or None
    contested = (key == practice.CONTEST_KEY)

    row = store.get_item(db, item_id)
    item_node = row["node_id"] if row else None
    store.record_miss_reason(db, student, item_id, item_node, key, text,
                             reason_node, contested=contested)
    if contested:
        store.flag_item_live_fire(
            db, item_id, f"a student contested this question ({student})")
    return redirect(url_for("practice_session", student=student, node=node or "", context=ctx))


@app.route("/drill/progress")
def drill_progress():
    db = get_db()
    student = request.args["student"]
    events = store.events_for_student(db, student)
    rows = drill.progress_table(_DRILL_WORDS, events)
    summary = drill.progress_summary(rows)
    return render_template("drill_progress.html", student=student, rows=rows,
                           summary=summary, week_labels=drill.WEEK_LABELS)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
