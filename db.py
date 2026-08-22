"""
Read-only link to the shared Neon Postgres database that ecr-viewer's
admin upload writes to. est_master doesn't own this data - it only reads
ecr_monthly (per-establishment ECR/employee/contribution history) so the
establishment detail pane can show it alongside the master-file fields.

If DATABASE_URL isn't set, get_ecr_history() just returns an empty list
(no ECR history section shown) rather than failing - local dev without a
DB configured still works for everything else in this app.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None

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
            month_cells.append({
                "month": MONTH_LABEL[m],
                "filed": cell is not None,
                "ecr_count": cell["ecr_count"] if cell else None,
                "employees": cell["employees"] if cell else None,
                "contribution": cell["contribution"] if cell else None,
            })
        result.append({"label": f"{dy}-{str(dy + 1)[-2:]}", "months": month_cells})
    return result
