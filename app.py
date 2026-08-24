"""
EPFO Establishment Master Search - Web App
------------------------------------------
A Flask web application for browsing and searching the Establishment
Master data held in the shared Neon Postgres database (see db.py).

Run locally:
    pip install -r requirements.txt
    python app.py

Then open http://localhost:5000

Every search/filter/detail/export request queries the database directly -
nothing is preloaded or cached in memory. The home page shows no listing
until the user actually searches (types a query or picks a filter).
"""

import os
import io
import csv
import re

from flask import Flask, jsonify, request, render_template, send_file
from openpyxl import Workbook

from db import (
    get_ecr_history, get_overall_upload_status, MIS_TO_DB_COLUMN,
    search_establishments, count_establishments, distinct_filter_values,
    get_establishment, total_establishment_count,
)

APP_TITLE = "Establishment Master Search"
MAX_DISPLAY_ROWS = 5  # rows per page

DISPLAY_COLUMNS = [
    ("EST_ID", "Establishment ID"),
    ("EST_NAME", "Establishment Name"),
    ("INCROP_CITY", "City"),
    ("INCROP_DIST", "District"),
    ("INCROP_PIN", "PIN"),
    ("COVER_DATE", "Cover Date"),
    ("ACCTS", "Accounts"),
    ("UANS", "UAN"),
    ("DSC", "DSC"),
    ("ESN", "eSign"),
    ("F5A", "Form 5A"),
    ("ACC_GRP_ID", "Accounts Group"),
    ("ACC_TASK_ID", "Task ID"),
    ("EST_STATUS_NAME", "Status"),
    ("ACTIONABLE_STATUS_NAME", "Actionable Status"),
]

# Columns that hold numbers-as-strings - sort these numerically (1, 2, 10)
# instead of lexicographically (1, 10, 2).
NUMERIC_SORT_COLUMNS = {"ACCTS", "UANS"}

SEARCH_FIELD_OPTIONS = {
    "all": None,
    "est_id": ["EST_ID"],
    "est_name": ["EST_NAME"],
    "address": ["INCROP_ADDRESS1", "INCROP_ADDRESS2"],
    "city_dist_pin": ["INCROP_CITY", "INCROP_DIST", "INCROP_PIN"],
    "pan_cin": ["PAN", "EST_CIN"],
    "lin": ["LIN_CODE"],
}

ALL_TEXT_SEARCH_COLUMNS = [
    "EST_ID", "EST_NAME", "INCROP_ADDRESS1", "INCROP_ADDRESS2",
    "INCROP_CITY", "INCROP_DIST", "INCROP_PIN", "PAN", "EST_CIN", "LIN_CODE",
]

FILTER_COLUMNS = [
    ("Status", "EST_STATUS_NAME"),
    ("District", "INCROP_DIST"),
    ("Industry Group", "IND_GROUP_NAME"),
    ("Actionable Status", "ACTIONABLE_STATUS_NAME"),
    ("Establishment Type", "EST_TYPE_NAME"),
    ("Exemption Status", "EXEMPTION_STATUS_NAME"),
    ("Accounts Group", "ACC_GRP_ID"),
    ("Task ID", "ACC_TASK_ID"),
    ("DSC", "DSC"),
    ("eSign", "ESN"),
    ("Form 5A", "F5A"),
    ("Coverage Section", "COVER_SECTION_NAME"),
]

FIELD_LABELS = {
    "OFFICE_ID": "Office ID",
    "EST_ID": "Establishment ID",
    "LIN_CODE": "LIN Code",
    "EST_CIN": "CIN",
    "PAN": "PAN",
    "EST_NAME": "Establishment Name",
    "INCROP_ADDRESS1": "Address 1",
    "INCROP_ADDRESS2": "Address 2",
    "INCROP_CITY": "City",
    "INCROP_DIST": "District",
    "INCROP_PIN": "PIN Code",
    "COVER_DATE": "Coverage Date",
    "COVER_SECTION_NAME": "Coverage Section",
    "EXEMPTION_STATUS_NAME": "Exemption Status",
    "EST_STATUS_NAME": "Establishment Status",
    "EST_TYPE_NAME": "Establishment Type",
    "ACTIONABLE_STATUS_NAME": "Actionable Status",
    "CONT_RATE_NAME": "Contribution Rate",
    "ACC_YEAR_NAME": "Account Year",
    "IND_GROUP_NAME": "Industry Group",
    "IND_CODE_NAME": "Industry Code",
    "INS_GROUP_ID": "Inspection Group ID",
    "INS_TASK_ID": "Inspection Task ID",
    "ENF_GROUP_ID": "Enforcement Group ID",
    "ENF_TASK_ID": "Enforcement Task ID",
    "ACC_GRP_ID": "Accounts Group ID",
    "ACC_TASK_ID": "Accounts Task ID",
    "UANS": "No. of UANs",
    "DSC": "DSC Registered",
    "ESN": "eSign",
    "REGISTERED_ON_ER_PORTAL": "Registered on Employer Portal",
    "F5A": "Form 5A Filed",
    "ACCTS": "Accounts",
    "PRIMARY_EMAIL": "Primary Email",
    "AADHAAR_SEEDED": "Aadhaar Seeded",
    "AADHAAR_VERIFIED": "Aadhaar Verified",
    "BANK_SEEDED": "Bank Seeded",
    "PAN_SEEDED": "PAN Seeded",
    "MOBILE_SEEDED": "Mobile Seeded",
}

DETAIL_FIELD_ORDER = [
    "EST_ID", "EST_NAME", "LIN_CODE", "EST_CIN", "PAN",
    "INCROP_ADDRESS1", "INCROP_ADDRESS2", "INCROP_CITY", "INCROP_DIST", "INCROP_PIN",
    "COVER_DATE", "COVER_SECTION_NAME", "EST_STATUS_NAME", "ACTIONABLE_STATUS_NAME",
    "EXEMPTION_STATUS_NAME", "EST_TYPE_NAME", "CONT_RATE_NAME", "ACC_YEAR_NAME",
    "IND_GROUP_NAME", "IND_CODE_NAME", "OFFICE_ID",
    "INS_GROUP_ID", "INS_TASK_ID", "ENF_GROUP_ID", "ENF_TASK_ID", "ACC_GRP_ID", "ACC_TASK_ID",
    "UANS", "DSC", "ESN", "REGISTERED_ON_ER_PORTAL", "F5A", "ACCTS", "PRIMARY_EMAIL",
    "AADHAAR_SEEDED", "AADHAAR_VERIFIED", "BANK_SEEDED", "PAN_SEEDED", "MOBILE_SEEDED",
]

app = Flask(__name__)


def _build_where(args, exclude_col=None, include_query=True):
    """Build a parameterized SQL WHERE fragment from the request's active
    filter selections (+ free-text query, unless include_query=False).
    exclude_col skips that column's own filter - used when computing that
    column's cascading dropdown options from every *other* active filter.

    Column names are always taken from our own trusted FILTER_COLUMNS/
    ALL_TEXT_SEARCH_COLUMNS lists (never from a user-supplied column name),
    so building the SQL text with them is safe - only the filter/search
    *values* flow through bind parameters.

    Returns (where_sql, params, has_criteria) - has_criteria is False when
    nothing was actually selected/typed, so callers can skip hitting the DB
    entirely rather than running an unfiltered (all ~50k rows) query."""
    clauses = []
    params = {}
    has_criteria = False

    for _, col in FILTER_COLUMNS:
        if col == exclude_col:
            continue
        selected = args.get("f_" + col, "").strip()
        if selected and selected != "All":
            has_criteria = True
            db_col = MIS_TO_DB_COLUMN[col]
            key = f"filt_{db_col}"
            clauses.append(f"{db_col} = :{key}")
            params[key] = selected

    if include_query:
        query = args.get("q", "").strip()
        if query:
            has_criteria = True
            field = args.get("field", "all")
            cols = SEARCH_FIELD_OPTIONS.get(field)
            if cols is None:
                cols = ALL_TEXT_SEARCH_COLUMNS
            or_clauses = []
            for i, col in enumerate(cols):
                db_col = MIS_TO_DB_COLUMN[col]
                key = f"q{i}"
                or_clauses.append(f"{db_col} ILIKE :{key}")
                params[key] = f"%{query}%"
            clauses.append("(" + " OR ".join(or_clauses) + ")")

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    return where_sql, params, has_criteria


def _order_by_sql(args):
    sort_col = args.get("sort", "").strip()
    sort_dir = "DESC" if args.get("dir") == "desc" else "ASC"
    if sort_col and sort_col in MIS_TO_DB_COLUMN:
        db_col = MIS_TO_DB_COLUMN[sort_col]
        if sort_col in NUMERIC_SORT_COLUMNS:
            # Numeric-looking values sort as numbers; anything non-numeric
            # (blank, junk) falls back to NULL so it sorts last instead of
            # erroring the whole query out on a bad cast.
            return f"CASE WHEN {db_col} ~ '^-?\\d+(\\.\\d+)?$' THEN {db_col}::numeric END {sort_dir} NULLS LAST"
        return f"LOWER({db_col}) {sort_dir}"
    return "est_id ASC"


@app.route("/")
def index():
    status = get_overall_upload_status()
    header_info = None
    if status["last_updated"]:
        header_info = {
            "date": status["last_updated"].strftime("%d %b %Y"),
            "version": status["version"],
        }
    return render_template(
        "index.html",
        app_title=APP_TITLE,
        display_columns=DISPLAY_COLUMNS,
        filter_columns=FILTER_COLUMNS,
        total_records=total_establishment_count(),
        header_info=header_info,
    )


def _filter_option_sort_key(v):
    """Sort by the leading numeric code (e.g. "2-MANUFACTURING" before
    "10-FARMING") when present, falling back to plain text - a plain string
    sort puts "10-..." before "2-..." which reads wrong for coded values."""
    m = re.match(r"^-?\d+", v)
    if m:
        return (0, int(m.group()), v.lower())
    return (1, 0, v.lower())


@app.route("/api/filters")
def api_filters():
    """Return distinct values for each filter dropdown, cascaded: each
    column's options only reflect rows matching every *other* currently
    selected filter (e.g. picking Accounts Group 101 narrows Task ID to just
    101xx codes) - so selecting one filter never leaves another showing
    choices that would return zero results together. These are cheap
    DISTINCT queries regardless of table size, so (unlike search) they run
    even before the user has searched, letting the Filters panel populate
    immediately."""
    options = {}
    for _, col in FILTER_COLUMNS:
        where_sql, params, _ = _build_where(request.args, exclude_col=col, include_query=False)
        db_col = MIS_TO_DB_COLUMN[col]
        values = distinct_filter_values(db_col, where_sql, params)
        options[col] = sorted(values, key=_filter_option_sort_key)
    return jsonify(options)


@app.route("/api/search")
def api_search():
    """Search establishments directly in the database - nothing is
    preloaded. Returns an empty result without touching the DB at all when
    no query or filter is active, so the home page can show a "search to
    begin" prompt instead of ever listing the whole table."""
    where_sql, params, has_criteria = _build_where(request.args)
    if not has_criteria:
        return jsonify({"total": 0, "rows": [], "page": 1, "pages": 0})

    total = count_establishments(where_sql, params)

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    pages = max(1, (total + MAX_DISPLAY_ROWS - 1) // MAX_DISPLAY_ROWS)
    page = min(page, pages)
    offset = (page - 1) * MAX_DISPLAY_ROWS

    matched = search_establishments(where_sql, params, _order_by_sql(request.args), MAX_DISPLAY_ROWS, offset)
    rows = [
        {"est_id": r["EST_ID"], "values": [r.get(col, "") for col, _ in DISPLAY_COLUMNS]}
        for r in matched
    ]

    return jsonify({"total": total, "rows": rows, "page": page, "pages": pages})


@app.route("/api/detail/<est_id>")
def api_detail(est_id):
    row = get_establishment(est_id)
    if not row:
        return jsonify({"error": "Record not found"}), 404
    fields = []
    for col in DETAIL_FIELD_ORDER:
        if col not in row:
            continue
        fields.append({
            "label": FIELD_LABELS.get(col, col),
            "value": row[col] if row[col] != "" else "-",
        })
    return jsonify({"fields": fields})


@app.route("/api/ecr/<est_id>")
def api_ecr(est_id):
    return jsonify({"years": get_ecr_history(est_id)})


@app.route("/api/export")
def api_export():
    """Export matching results as CSV or Excel - same query as /api/search
    but without pagination. Skips the query (empty export) when no search
    criteria are active, matching the rest of the app."""
    where_sql, params, has_criteria = _build_where(request.args)
    fmt = request.args.get("format", "csv").lower()
    rows = search_establishments(where_sql, params, _order_by_sql(request.args)) if has_criteria else []
    columns = list(MIS_TO_DB_COLUMN.keys())

    if fmt == "xlsx":
        # openpyxl's write-only mode streams rows straight to the output zip
        # as they're appended, rather than building the whole workbook as
        # in-memory Python objects first.
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("Establishments")
        ws.append(columns)
        for row in rows:
            ws.append([row.get(c, "") for c in columns])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="establishment_results.xlsx",
        )

    text_buf = io.StringIO()
    writer = csv.writer(text_buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(c, "") for c in columns])
    data = io.BytesIO(text_buf.getvalue().encode("utf-8-sig"))
    return send_file(
        data,
        mimetype="text/csv",
        as_attachment=True,
        download_name="establishment_results.csv",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)