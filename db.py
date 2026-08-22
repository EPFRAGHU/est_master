"""
Read-only link to the shared Neon Postgres database that both ecr-viewer's
and est_master's admin uploads write to. est_master reads the whole
establishments table at startup (establishments_to_dataframe) so its search
page shows the same synced data ecr-viewer has, and reads ecr_monthly
per-establishment so the detail pane can show ECR filing history alongside
the master-file fields.

If DATABASE_URL isn't set, establishments_to_dataframe() returns None (the
caller falls back to the local CSV) and get_ecr_history() returns an empty
list - local dev without a DB configured still works for everything else.
"""
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None

# Shared establishments table's db column -> the raw EPFO MIS header name
# est_master's app.py (DISPLAY_COLUMNS, FILTER_COLUMNS, FIELD_LABELS, etc.)
# expects. Keep in sync with ecr-viewer's db.py ESTABLISHMENT_COLUMNS and
# csv_upload.py MASTER_COLUMN_ALIASES - see
# docs/superpowers/specs/2026-08-22-shared-establishment-master-design.md
# (in the ecr-viewer repo).
ESTABLISHMENT_COLUMN_MAP = {
    "est_id": "EST_ID",
    "office_id": "OFFICE_ID",
    "est_name": "EST_NAME",
    "address1": "INCROP_ADDRESS1",
    "address2": "INCROP_ADDRESS2",
    "city": "INCROP_CITY",
    "district": "INCROP_DIST",
    "pin": "INCROP_PIN",
    "cover_date": "COVER_DATE",
    "industry": "IND_GROUP_NAME",
    "coverage_section": "COVER_SECTION_NAME",
    "email": "PRIMARY_EMAIL",
    "task_id": "ACC_TASK_ID",
    "dsc": "DSC",
    "esn": "ESN",
    "form_5a": "F5A",
    "lin_code": "LIN_CODE",
    "est_cin": "EST_CIN",
    "pan": "PAN",
    "exemption_status": "EXEMPTION_STATUS_NAME",
    "est_status": "EST_STATUS_NAME",
    "est_type": "EST_TYPE_NAME",
    "actionable_status": "ACTIONABLE_STATUS_NAME",
    "cont_rate": "CONT_RATE_NAME",
    "acc_year": "ACC_YEAR_NAME",
    "ind_code": "IND_CODE_NAME",
    "ins_group_id": "INS_GROUP_ID",
    "ins_task_id": "INS_TASK_ID",
    "enf_group_id": "ENF_GROUP_ID",
    "enf_task_id": "ENF_TASK_ID",
    "acc_grp_id": "ACC_GRP_ID",
    "uans": "UANS",
    "er_portal_registered": "REGISTERED_ON_ER_PORTAL",
    "accts": "ACCTS",
    "aadhaar_seeded": "AADHAAR_SEEDED",
    "aadhaar_verified": "AADHAAR_VERIFIED",
    "bank_seeded": "BANK_SEEDED",
    "pan_seeded": "PAN_SEEDED",
    "mobile_seeded": "MOBILE_SEEDED",
}


def establishments_to_dataframe():
    """Load the full shared establishments table, renamed to the raw MIS
    column names the rest of app.py expects. Returns None if no DB is
    configured (caller should fall back to the local CSV) or on any query
    error (e.g. table doesn't exist yet on a fresh DB)."""
    if engine is None:
        return None
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT * FROM establishments"), conn)
    except Exception:
        return None
    df = df.rename(columns=ESTABLISHMENT_COLUMN_MAP)
    df = df.fillna("")
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df


def get_overall_upload_status():
    """Latest admin-upload timestamp + total upload count from the shared
    upload_log table (populated by both ecr-viewer's and est_master's admin
    uploads) - same figure ecr-viewer shows in its own header, so both apps
    display the same 'data as of / version' line."""
    if engine is None:
        return {"last_updated": None, "version": 0}
    try:
        with engine.connect() as conn:
            last = conn.execute(text("SELECT MAX(uploaded_at) FROM upload_log")).scalar()
            count = conn.execute(text("SELECT COUNT(*) FROM upload_log")).scalar()
    except Exception:
        return {"last_updated": None, "version": 0}
    return {"last_updated": last, "version": count}


MONTH_LABEL = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# Apr - Mar, matching ecr-viewer's own financial-year layout.
DISPLAY_MONTHS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]


def _bucket_year(calendar_year, calendar_month):
    """A 'display year' Y runs Apr-Y to Mar-(Y+1) - same rule ecr-viewer
    uses, so both apps group the same calendar month into the same FY."""
    if calendar_month in (1, 2, 3):
        return calendar_year - 1
    return calendar_year


def get_ecr_history(est_id):
    """ECR history for one establishment, grouped into financial-year blocks
    (Apr-Mar, most recent first) - same shape as ecr-viewer's own
    /api/establishment/<est_id>. Returns [] if no DB is configured or
    nothing is found."""
    if engine is None or not est_id:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT year, month, ecr_count, employees, contribution "
                "FROM ecr_monthly WHERE est_id = :est_id"
            ),
            {"est_id": est_id.strip().upper()},
        ).mappings().all()

    years = {}
    for r in rows:
        dy = _bucket_year(r["year"], r["month"])
        years.setdefault(dy, {})[r["month"]] = {
            "ecr_count": r["ecr_count"],
            "employees": r["employees"],
            "contribution": float(r["contribution"]) if r["contribution"] is not None else None,
        }

    result = []
    for dy in sorted(years.keys(), reverse=True):
        months_data = years[dy]
        month_cells = []
        for m in DISPLAY_MONTHS:
            cell = months_data.get(m)
            calendar_year = dy + 1 if m in (1, 2, 3) else dy
            month_cells.append({
                "month": f"{MONTH_LABEL[m].upper()}-{calendar_year}",
                "filed": cell is not None,
                "ecr_count": cell["ecr_count"] if cell else None,
                "employees": cell["employees"] if cell else None,
                "contribution": cell["contribution"] if cell else None,
            })
        result.append({"label": f"{dy}-{str(dy + 1)[-2:]}", "months": month_cells})
    return result
