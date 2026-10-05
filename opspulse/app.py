"""Flask web interface for OpsPulse; calculations live in src modules."""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
from flask import Flask, make_response, render_template_string, request, send_file, session
from markupsafe import Markup

from src.cleaning import clean_tasks
from src.kpis import calculate_kpis
from src.report import create_pdf
from src.summary import generate_summary


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(tempfile.gettempdir()) / "opspulse_flask_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or uuid.uuid4().hex
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpsPulse | Weekly operations</title>
  <style>
    :root{--ink:#152b35;--muted:#647780;--accent:#146c78;--line:#dce5e8;--paper:#f4f7f8;--white:#fff;--warn:#fff3df}
    *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    header{background:#102f39;color:#fff;padding:27px max(22px,calc((100vw - 1440px)/2));}header h1{margin:0;font-size:28px}header p{margin:3px 0 0;color:#d1e1e4}
    .layout{max-width:1480px;margin:22px auto;padding:0 22px;display:grid;grid-template-columns:280px minmax(0,1fr);gap:22px}
    aside,.panel,.metric{background:var(--white);border:1px solid var(--line);border-radius:12px}aside{padding:20px;height:max-content;position:sticky;top:18px}aside h2{font-size:17px;margin:0 0 12px}
    label{display:block;font-weight:650;font-size:13px;margin:14px 0 5px}input,select,button{font:inherit}input[type=file],input[type=date],select{width:100%;border:1px solid #cbd7db;border-radius:7px;padding:9px;background:#fff;color:var(--ink)}select[multiple]{height:88px}small,.muted{color:var(--muted)}small{font-size:12px}
    button,.button{background:var(--accent);border:0;border-radius:7px;color:#fff;padding:10px 13px;font-weight:650;cursor:pointer;text-decoration:none;display:inline-block}button:hover,.button:hover{background:#0e5660}.secondary{background:#eaf1f2;color:var(--ink)}.secondary:hover{background:#dce8ea}
    .actions{display:grid;gap:8px;margin-top:16px}.notice{padding:10px 12px;border-radius:8px;background:var(--warn);font-size:12px;margin-top:15px}
    main{min-width:0}.topline{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:1px 0 16px}.topline h2{font-size:20px;margin:0}.source{font-size:13px;color:var(--muted)}
    .metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.metric{padding:15px}.metric .label{font-size:12px;color:var(--muted);font-weight:650}.metric .value{font-size:26px;font-weight:750;margin-top:5px}.metric .delta{font-size:12px;color:var(--muted);margin-top:3px}
    nav{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 15px}nav a{padding:8px 11px;background:#e8eff1;border-radius:7px;color:var(--ink);text-decoration:none;font-size:13px;font-weight:650}
    .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.panel{padding:18px;margin-bottom:14px;min-width:0}.panel h3{margin:0 0 10px;font-size:17px}.chart{overflow-x:auto}.chart iframe{max-width:100%}
    .table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:8px 9px;text-align:left;white-space:nowrap}th{background:#f3f7f8;color:#435b64;font-size:12px}
    ul.summary{padding-left:20px;margin:4px 0}ul.summary li{margin:8px 0}.empty{color:var(--muted);padding:16px;background:#f6f9fa;border-radius:8px}.flash{padding:12px;background:#fde8e7;border-radius:8px;margin:0 0 14px;color:#7c2722}
    footer{font-size:12px;color:var(--muted);padding:12px 0 30px}.inline{display:flex;gap:8px}.inline>*{flex:1}
    @media(max-width:960px){.layout{grid-template-columns:1fr}aside{position:static}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:560px){.grid{grid-template-columns:1fr}.layout{padding:0 12px;margin:12px auto}.metrics{gap:8px}.metric{padding:11px}.metric .value{font-size:22px}header{padding:22px 16px}}
  </style>
</head>
<body>
<header><h1>OpsPulse</h1><p>A clear weekly view of delivery, workload, and data quality.</p></header>
<div class="layout">
  <aside>
    <h2>Task data &amp; filters</h2>
    <form method="post" enctype="multipart/form-data">
      <input type="hidden" name="dataset_id" value="{{ dataset_id }}">
      <label for="task_file">Upload CSV or Excel</label>
      <input id="task_file" type="file" name="task_file" accept=".csv,.xlsx,.xls">
      <small>Up to 16 MB. The included sample is synthetic.</small>
      <label for="as_of">Report as of</label>
      <input id="as_of" type="date" name="as_of" value="{{ as_of }}">
      <div class="inline">
        <div><label for="created_from">Created from</label><input id="created_from" type="date" name="created_from" value="{{ created_from }}"></div>
        <div><label for="created_to">Created to</label><input id="created_to" type="date" name="created_to" value="{{ created_to }}"></div>
      </div>
      <label for="teams">Team</label><select id="teams" name="teams" multiple>{% for item in all_teams %}<option value="{{ item }}" {% if item in selected_teams %}selected{% endif %}>{{ item }}</option>{% endfor %}</select>
      <label for="owners">Owner</label><select id="owners" name="owners" multiple>{% for item in all_owners %}<option value="{{ item }}" {% if item in selected_owners %}selected{% endif %}>{{ item }}</option>{% endfor %}</select>
      <label for="priorities">Priority</label><select id="priorities" name="priorities" multiple>{% for item in all_priorities %}<option value="{{ item }}" {% if item in selected_priorities %}selected{% endif %}>{{ item }}</option>{% endfor %}</select>
      <div class="actions">
        <button name="action" value="apply">Apply filters / upload</button>
        <button class="secondary" name="action" value="use_sample">Use sample data</button>
      </div>
      <div class="notice">For this public demo, use synthetic or non-confidential task data. Uploaded files are kept temporarily on the server to support filtering and are not saved to the project.</div>
      <div class="actions">
        <button class="secondary" name="action" value="download_csv">Download cleaned CSV</button>
        <button name="action" value="download_pdf">Download one-page PDF</button>
      </div>
    </form>
  </aside>
  <main>
    {% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}
    <div class="topline"><h2>Operations overview</h2><span class="source">{{ data_source }} · {{ quality.rows_out|int }} cleaned rows</span></div>
    <section class="metrics">
      {% for m in metrics %}<div class="metric"><div class="label">{{ m.label }}</div><div class="value">{{ m.value }}</div><div class="delta">{{ m.delta }}</div></div>{% endfor %}
    </section>
    <nav><a href="#overview">Overview</a><a href="#quality">Data quality</a><a href="#workload">Workload</a><a href="#weekly">Weekly report</a></nav>
    <section id="overview" class="grid">
      <div class="panel"><h3>Throughput by week</h3>{% if throughput_chart %}<div class="chart">{{ throughput_chart|safe }}</div>{% else %}<div class="empty">No weekly throughput data in this selection.</div>{% endif %}</div>
      <div class="panel"><h3>On-time rate by priority</h3>{% if priority_chart %}<div class="chart">{{ priority_chart|safe }}</div>{% else %}<div class="empty">No tasks with usable priority deadline data.</div>{% endif %}</div>
      <div class="panel"><h3>Overdue backlog by owner</h3>{% if overdue_chart %}<div class="chart">{{ overdue_chart|safe }}</div>{% else %}<div class="empty">No overdue tasks in this selection.</div>{% endif %}</div>
      <div class="panel"><h3>At a glance</h3><p>Overdue backlog is measured as of <strong>{{ as_of }}</strong>: tasks created by then, due before then, and not yet completed at that date.</p><p class="muted">All records in the included sample are synthetic.</p></div>
    </section>
    <section id="quality" class="panel"><h3>Data quality</h3><p>{{ quality.rows_in|int }} rows in · {{ quality.rows_out|int }} rows out · {{ quality.duplicates_removed|int }} exact duplicates removed · score {{ '%.1f'|format(quality.data_quality_score) }}%</p><h4>Change log</h4><ul>{% for change in quality.change_log %}<li>{{ change }}</li>{% else %}<li>No changes recorded.</li>{% endfor %}</ul><div class="table-wrap">{{ issue_table }}</div></section>
    <section id="workload" class="panel"><h3>Open workload by owner</h3><p class="muted">Overloaded means more than 1.5× the average number of open tasks per owner.</p>{% if workload_table %}<div class="table-wrap">{{ workload_table }}</div>{% else %}<div class="empty">No open tasks in this selection.</div>{% endif %}</section>
    <section id="weekly" class="panel"><h3>Weekly report</h3><ul class="summary">{% for item in summary %}<li>{{ item }}</li>{% endfor %}</ul><h4>Weekly KPI table</h4>{% if weekly_table %}<div class="table-wrap">{{ weekly_table }}</div>{% else %}<div class="empty">No weekly data in this selection.</div>{% endif %}</section>
    <footer>OpsPulse is a portfolio demo. Upload only synthetic or non-confidential data.</footer>
  </main>
</div>
</body></html>"""


def _sample_data():
    return pd.read_csv(BASE_DIR / "data" / "sample_tasks.csv"), "Synthetic sample data"


def _current_data():
    token = session.get("dataset_id")
    extension = session.get("dataset_ext")
    if not token:
        return _sample_data()
    path = UPLOAD_DIR / f"{token}{extension or '.csv'}"
    if not path.is_file():
        session.pop("dataset_id", None)
        return _sample_data()
    try:
        if path.suffix == ".xlsx":
            return pd.read_excel(path), "Uploaded task file"
        if path.suffix == ".xls":
            return pd.read_excel(path), "Uploaded task file"
        return pd.read_csv(path), "Uploaded task file"
    except (ValueError, ImportError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError(f"Could not read the saved upload: {exc}") from exc


def _save_upload(upload):
    name = (upload.filename or "").lower()
    extension = Path(name).suffix
    if extension not in {".csv", ".xlsx", ".xls"}:
        raise ValueError("Choose a CSV or Excel file (.csv, .xlsx, or .xls).")
    payload = upload.read()
    if not payload:
        raise ValueError("The selected file is empty.")
    token = uuid.uuid4().hex
    (UPLOAD_DIR / f"{token}{extension}").write_bytes(payload)
    old_token, old_extension = session.get("dataset_id"), session.get("dataset_ext")
    session["dataset_id"] = token
    session["dataset_ext"] = extension
    if old_token and old_extension:
        (UPLOAD_DIR / f"{old_token}{old_extension}").unlink(missing_ok=True)
    cutoff = pd.Timestamp.now().timestamp() - 24 * 60 * 60
    for old_file in UPLOAD_DIR.iterdir():
        if old_file.is_file() and old_file.stat().st_mtime < cutoff:
            old_file.unlink(missing_ok=True)
    return extension


def _metric(label, value, delta, kind="number"):
    if value is None or pd.isna(value):
        shown = "N/A"
    elif kind == "rate":
        shown = f"{value:.0%}"
    elif kind == "days":
        shown = f"{value:.1f} d"
    else:
        shown = f"{value:,.0f}"
    if delta is None or pd.isna(delta):
        change = "No reliable complete-week comparison"
    elif kind == "rate":
        change = f"{delta * 100:+.1f} pts vs. previous complete week"
    elif kind == "days":
        change = f"{delta:+.1f} d vs. previous complete week"
    else:
        change = f"{delta:+.1f} vs. previous complete week"
    return {"label": label, "value": shown, "delta": change}


def _table(frame, *, rates=()):
    if frame is None or frame.empty:
        return ""
    display = frame.copy()
    for column in rates:
        if column in display:
            display[column] = display[column].map(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
    for column in display.columns:
        if pd.api.types.is_datetime64_any_dtype(display[column]):
            display[column] = display[column].dt.strftime("%Y-%m-%d")
    display = display.astype(object).where(pd.notna(display), "N/A")
    return Markup(display.to_html(index=False, escape=True, border=0, classes="data-table"))


def _chart(fig, include_js=False):
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if include_js else False, config={"responsive": True, "displayModeBar": False})


def _render_dashboard(raw, source, messages=None, reset_filters=False):
    cleaned, quality = clean_tasks(raw)
    done_dates = cleaned.loc[cleaned["Status"].eq("Done"), "Completed Date"].dropna()
    default_as_of = done_dates.max().date() if len(done_dates) else date.today()
    dates = cleaned["Created Date"].dropna()
    default_from = dates.min().date().isoformat() if len(dates) else ""
    default_to = dates.max().date().isoformat() if len(dates) else ""

    as_of = (None if reset_filters else request.form.get("as_of")) or default_as_of.isoformat()
    created_from = default_from if reset_filters else request.form.get("created_from", default_from)
    created_to = default_to if reset_filters else request.form.get("created_to", default_to)
    all_teams = sorted(cleaned["Team"].dropna().astype(str).unique().tolist())
    all_owners = sorted(cleaned["Owner"].dropna().astype(str).unique().tolist())
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    all_priorities = sorted(cleaned["Priority"].dropna().astype(str).unique().tolist(), key=lambda p: (priority_order.get(p, 3), p))

    if request.method == "POST" and not reset_filters:
        selected_teams = request.form.getlist("teams")
        selected_owners = request.form.getlist("owners")
        selected_priorities = request.form.getlist("priorities")
    else:
        selected_teams, selected_owners, selected_priorities = all_teams, all_owners, all_priorities

    filtered = cleaned.copy()
    if created_from:
        filtered = filtered[filtered["Created Date"].ge(pd.Timestamp(created_from))]
    if created_to:
        filtered = filtered[filtered["Created Date"].le(pd.Timestamp(created_to))]
    filtered = filtered[
        filtered["Team"].astype(str).isin(selected_teams)
        & filtered["Owner"].astype(str).isin(selected_owners)
        & filtered["Priority"].astype(str).isin(selected_priorities)
    ]

    kpis = calculate_kpis(filtered, as_of_date=as_of)
    summary = generate_summary(kpis)
    overall = kpis["overall"]
    metrics = [
        _metric("On-time", overall.get("on_time_rate"), kpis["wow"].get("on_time_rate"), "rate"),
        _metric("Cycle time", overall.get("average_cycle_days"), kpis["wow"].get("average_cycle_days"), "days"),
        _metric("Throughput", overall.get("throughput"), kpis["wow"].get("throughput")),
        _metric("Overdue backlog", overall.get("overdue_backlog"), kpis["wow"].get("overdue_backlog")),
    ]

    priority_chart = None
    if len(kpis["priority"]):
        fig = px.bar(kpis["priority"], x="Priority", y="on_time_rate", color_discrete_sequence=["#146C78"])
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300, yaxis_tickformat=".0%", yaxis_title="On-time rate", xaxis_title="")
        priority_chart = _chart(fig, include_js=not len(kpis["weekly"]))
    throughput_chart = None
    if len(kpis["weekly"]):
        fig = px.line(kpis["weekly"], x="Week", y="throughput", markers=True, color_discrete_sequence=["#146C78"])
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300, xaxis_title="", yaxis_title="Completed tasks")
        throughput_chart = _chart(fig, include_js=True)
    overdue_chart = None
    overdue = kpis["overdue_by_owner"]
    if len(overdue):
        chart_data = overdue.rename("Overdue tasks").reset_index()
        chart_data.columns = ["Owner", "Overdue tasks"]
        fig = px.bar(chart_data, x="Owner", y="Overdue tasks", color_discrete_sequence=["#146C78"])
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300, xaxis_title="", yaxis_title="Tasks")
        overdue_chart = _chart(fig, include_js=not (throughput_chart or priority_chart))

    weekly_display = kpis["weekly"].copy()
    for column in ("on_time_rate", "rework_rate"):
        if column in weekly_display:
            weekly_display[column] = weekly_display[column].map(lambda value: f"{value:.1%}" if pd.notna(value) else "N/A")
    for column in ("on_time_rate_wow", "rework_rate_wow"):
        if column in weekly_display:
            weekly_display[column] = weekly_display[column].map(lambda value: f"{value * 100:+.1f} pts" if pd.notna(value) else "N/A")
    issue_frame = pd.DataFrame({"Issue": list(quality["issue_counts"]), "Flagged rows": list(quality["issue_counts"].values())})
    dataset_id = session.get("dataset_id", "")
    return render_template_string(
        PAGE,
        data_source=source,
        quality=quality,
        as_of=as_of,
        created_from=created_from,
        created_to=created_to,
        all_teams=all_teams,
        all_owners=all_owners,
        all_priorities=all_priorities,
        selected_teams=selected_teams,
        selected_owners=selected_owners,
        selected_priorities=selected_priorities,
        dataset_id=dataset_id,
        metrics=metrics,
        summary=summary,
        throughput_chart=throughput_chart,
        priority_chart=priority_chart,
        overdue_chart=overdue_chart,
        issue_table=_table(issue_frame),
        workload_table=_table(kpis["workload"]),
        weekly_table=_table(weekly_display, rates=()),
        messages=messages or [],
    )


@app.route("/", methods=["GET", "POST"])
def dashboard():
    messages = []
    reset_filters = False
    action = request.form.get("action", "") if request.method == "POST" else ""
    if action == "use_sample":
        token = session.pop("dataset_id", None)
        extension = session.pop("dataset_ext", None)
        if token and extension:
            (UPLOAD_DIR / f"{token}{extension}").unlink(missing_ok=True)
        raw, source = _sample_data()
        return _render_dashboard(raw, source, messages, reset_filters=True)

    upload = request.files.get("task_file") if request.method == "POST" else None
    try:
        if upload and upload.filename:
            extension = _save_upload(upload)
            raw, source = _current_data()
            messages.append("File uploaded and cleaned. Review the filters and report below.")
            reset_filters = True
        else:
            raw, source = _current_data()
            reset_filters = False
    except (ValueError, ImportError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        messages.append(f"Could not load this file: {exc}")
        raw, source = _sample_data()
        session.pop("dataset_id", None)
        session.pop("dataset_ext", None)
        return _render_dashboard(raw, source, messages, reset_filters=True)

    try:
        if action == "download_pdf":
            cleaned, quality = clean_tasks(raw)
            # Apply the same active form selections as the dashboard render.
            as_of = request.form.get("as_of") or None
            from_date, to_date = request.form.get("created_from"), request.form.get("created_to")
            if from_date:
                cleaned = cleaned[cleaned["Created Date"].ge(pd.Timestamp(from_date))]
            if to_date:
                cleaned = cleaned[cleaned["Created Date"].le(pd.Timestamp(to_date))]
            for field, column in (("teams", "Team"), ("owners", "Owner"), ("priorities", "Priority")):
                selected = request.form.getlist(field)
                cleaned = cleaned[cleaned[column].astype(str).isin(selected)]
            kpis = calculate_kpis(cleaned, as_of_date=as_of)
            pdf = create_pdf(kpis, generate_summary(kpis), quality)
            return send_file(BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name="opspulse_weekly_report.pdf")
        if action == "download_csv":
            cleaned, _ = clean_tasks(raw)
            output = BytesIO(cleaned.to_csv(index=False).encode("utf-8"))
            return send_file(output, mimetype="text/csv", as_attachment=True, download_name="opspulse_cleaned.csv")
    except (ValueError, ImportError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        messages.append(f"Could not create the download: {exc}")

    return _render_dashboard(raw, source, messages, reset_filters=reset_filters)


@app.errorhandler(413)
def upload_too_large(_error):
    return make_response("Upload is too large. Choose a file under 16 MB.", 413)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
