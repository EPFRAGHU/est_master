"""
EPFO Establishment Master Search - Web App
------------------------------------------
A Flask web application for browsing and searching the Establishment
Master download (the CSV exported from the EPFO portal).

Run locally:
    pip install -r requirements.txt
    python app.py

Then open http://localhost:5000

Expects a CSV file named "establishment_master.csv" in the same folder.
"""

import os
import io
import csv

import pandas as pd
from flask import Flask, jsonify, request, render_template, send_file

APP_TITLE = "Establishment Master Search"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "establishment_master.csv")
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


def load_master_csv(path):
    """Load the establishment master CSV as strings, tidy whitespace."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    df = df.fillna("")
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df


# Load data once at startup
if os.path.exists(DATA_FILE):
    DF = load_master_csv(DATA_FILE)
    # Ensure expected columns exist
    for col, _ in DISPLAY_COLUMNS:
        if col not in DF.columns:
            DF[col] = ""
    for col in ALL_TEXT_SEARCH_COLUMNS:
        if col not in DF.columns:
            DF[col] = ""
    for _, col in FILTER_COLUMNS:
        if col not in DF.columns:
            DF[col] = ""
else:
    DF = pd.DataFrame()


def apply_search(args):
    """Apply filters + free-text search from request args. Returns filtered DataFrame."""
    if DF.empty:
        return DF

    result = DF

    # Dropdown filters
    for _, col in FILTER_COLUMNS:
        selected = args.get("f_" + col, "").strip()
        if selected and selected != "All":
            result = result[result[col] == selected]

    # Free-text search
    query = args.get("q", "").strip().lower()
    if query:
        field = args.get("field", "all")
        cols = SEARCH_FIELD_OPTIONS.get(field)
        if cols is None:
            cols = ALL_TEXT_SEARCH_COLUMNS
        mask = None
        for col in cols:
            col_mask = result[col].str.lower().str.contains(query, na=False, regex=False)
            mask = col_mask if mask is None else (mask | col_mask)
        result = result[mask]

    # Sorting
    sort_col = args.get("sort", "").strip()
    if sort_col and sort_col in result.columns:
        ascending = args.get("dir", "asc") != "desc"
        result = result.sort_values(
            by=sort_col, ascending=ascending,
            key=lambda s: s.str.lower() if s.dtype == object else s,
        )

    return result


@app.route("/")
def index():
    return render_template(
        "index.html",
        app_title=APP_TITLE,
        display_columns=DISPLAY_COLUMNS,
        filter_columns=FILTER_COLUMNS,
        total_records=len(DF),
    )


@app.route("/api/filters")
def api_filters():
    """Return distinct values for each filter dropdown."""
    options = {}
    if not DF.empty:
        for _, col in FILTER_COLUMNS:
            options[col] = sorted(v for v in DF[col].unique() if v)
    return jsonify(options)


@app.route("/api/search")
def api_search():
    if DF.empty:
        return jsonify({"total": 0, "rows": [], "page": 1, "pages": 0})

    result = apply_search(request.args)
    total = len(result)

    # Pagination
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    pages = max(1, (total + MAX_DISPLAY_ROWS - 1) // MAX_DISPLAY_ROWS)
    page = min(page, pages)
    start = (page - 1) * MAX_DISPLAY_ROWS
    page_df = result.iloc[start:start + MAX_DISPLAY_ROWS]

    rows = []
    for idx, row in page_df.iterrows():
        rows.append({
            "idx": int(idx),
            "values": [row.get(col, "") for col, _ in DISPLAY_COLUMNS],
        })

    return jsonify({"total": total, "rows": rows, "page": page, "pages": pages})


@app.route("/api/detail/<int:idx>")
def api_detail(idx):
    if DF.empty or idx not in DF.index:
        return jsonify({"error": "Record not found"}), 404
    row = DF.loc[idx]
    fields = []
    for col in DETAIL_FIELD_ORDER:
        if col not in row:
            continue
        fields.append({
            "label": FIELD_LABELS.get(col, col),
            "value": row[col] if row[col] != "" else "-",
        })
    return jsonify({"fields": fields})


@app.route("/api/export")
def api_export():
    """Export current filtered results as CSV or Excel."""
    result = apply_search(request.args)
    fmt = request.args.get("format", "csv").lower()

    if fmt == "xlsx":
        buf = io.BytesIO()
        result.to_excel(buf, index=False)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="establishment_results.xlsx",
        )

    buf = io.StringIO()
    result.to_csv(buf, index=False, quoting=csv.QUOTE_MINIMAL)
    data = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    return send_file(
        data,
        mimetype="text/csv",
        as_attachment=True,
        download_name="establishment_results.csv",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)