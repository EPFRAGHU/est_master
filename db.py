"""
Read-only link to the shared Neon Postgres database that both ecr-viewer's
and est_master's admin uploads write to. Every search/filter/detail/export
request queries this table directly (see search_establishments and friends
below) - est_master never loads the whole ~50k-row table into memory, which
is what was causing repeated out-of-memory restarts on Render's free tier.

If DATABASE_URL isn't set, every function below degrades to an empty/zero
result rather than raising, so the app stays up (just shows no data) instead
of crashing when the DB isn't configured.
"""
import os

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


# Reverse of ESTABLISHMENT_COLUMN_MAP: raw MIS header name -> db column name.
# app.py's DISPLAY_COLUMNS/FILTER_COLUMNS/etc. are all expressed in MIS
# names, but every SQL identifier has to be the actual db column - this is
# how callers translate a trusted MIS column name into one.
MIS_TO_DB_COLUMN = {mis: db_col for db_col, mis in ESTABLISHMENT_COLUMN_MAP.items()}


def _row_to_mis(row):
    """A DB row (db column names -> raw values) to the MIS-named,
    string-cleaned dict shape the rest of the app expects."""
    out = {}
    for db_col, val in row.items():
        mis = ESTABLISHMENT_COLUMN_MAP.get(db_col, db_col.upper())
        out[mis] = "" if val is None else str(val).strip()
    return out


def search_establishments(where_sql, params, order_by_sql, limit=None, offset=0):
    """Run a parameterized SELECT * against establishments and return rows
    as MIS-named dicts. where_sql/order_by_sql are built by the caller from
    a trusted column-name allowlist (FILTER_COLUMNS/ALL_TEXT_SEARCH_COLUMNS
    in app.py) - never from a raw user-supplied column name - so building
    them as f-strings is safe; only VALUES flow through bind parameters."""
    if engine is None:
        return []
    sql = f"SELECT * FROM establishments WHERE {where_sql} ORDER BY {order_by_sql}"
    if limit is not None:
        sql += " LIMIT :limit OFFSET :offset"
        params = {**params, "limit": limit, "offset": offset}
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [_row_to_mis(dict(r)) for r in rows]


def count_establishments(where_sql, params):
    if engine is None:
        return 0
    sql = f"SELECT COUNT(*) FROM establishments WHERE {where_sql}"
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar() or 0


def distinct_filter_values(db_col, where_sql, params):
    """Distinct non-blank values for one column, respecting the given WHERE
    (built by the caller from other active filters, for cascading dropdowns)."""
    if engine is None:
        return []
    sql = (
        f"SELECT DISTINCT {db_col} FROM establishments "
        f"WHERE ({where_sql}) AND {db_col} IS NOT NULL AND {db_col} != ''"
    )
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).scalars().all()
    return [v for v in rows if v]


def get_establishment(est_id):
    """One establishment by its EST_ID, as a MIS-named dict, or None."""
    if engine is None or not est_id:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM establishments WHERE est_id = :est_id"),
            {"est_id": est_id.strip().upper()},
        ).mappings().first()
    return _row_to_mis(dict(row)) if row else None


def total_establishment_count():
    if engine is None:
        return 0
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM establishments")).scalar() or 0


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
