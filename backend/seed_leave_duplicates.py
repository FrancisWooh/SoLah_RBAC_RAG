"""Add HR leave-policy records to hr_db that overlap with data/hr/Leave_Policy_Admin_Guide.docx (H01),
to demo how RAG handles the same fact living in both a file and a database.

Default (matches the reference environment):
  HR-L01  annual leave entitlement (Chinese, same wording as the docx)
  HR-L02  sick leave quick reference (Chinese)

With --with-conflicts, also adds records that CONTRADICT the docx:
  HR-L03  annual leave carry-over (docx: 5 days by end of March; record: 10 days by end of June)
  HR-L04  paternity leave (docx: 2 weeks within 16 weeks; record: 3 weeks within 12 months)

Access control mirrors H01 (clearance 2, compartment 'hr', roles inherited from the HR database's
attach role), so the same users see both copies.

Only touches hr_db rows whose record_code starts with 'HR-L'; idempotent. Connects with the admin
credentials in DATABASE_URL (same server as the app database), so it works with a changed
POSTGRES_PASSWORD. Run seed_dept_databases.py first (it creates hr_db).

Usage:
  docker compose exec backend python seed_leave_duplicates.py                    add/refresh L01-L02
  docker compose exec backend python seed_leave_duplicates.py --with-conflicts   also add L03-L04
  docker compose exec backend python seed_leave_duplicates.py --remove           delete all HR-L* records
Add --sync to index immediately; otherwise the running backend picks the change up within
DB_SYNC_INTERVAL seconds (no second embedding model is loaded, which matters on small hosts).
"""

import sys

import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy.engine import make_url

from app.core.config import settings

_url = make_url(settings.database_url)
ADMIN = dict(host=_url.host or "postgres", port=_url.port or 5432, user=_url.username, password=_url.password, dbname="hr_db")

# (code, title, category, content, clearance, compartment, allowed_roles)
ROWS = [  # exactly what the reference (local) hr_db holds
    ('HR-L01', 'Annual Leave Entitlement', 'Leave',
     '年假政策规定：员工入职满1年后，每年享有18天带薪年假。工龄每满2年增加1天，累计上限为25天。例如，服务满3年的员工享有19天，服务满15年及以上的员工享有25天上限。入职不满1年的员工按月比例计算，每月1.5天，向下取整至半天。',
     2, 'hr', None),
    ('HR-L02', 'Sick Leave Quick Reference', 'Leave',
     '员工每年享有14天带薪门诊病假和60天带薪住院病假（含上述14天，即总计每年最多60天）。病假必须提供注册医生签发的医疗证明（MC）。连续病假2天及以上必须提交MC；单日病假如无MC，每年限5次，需向直属经理口头说明。员工应在当天上午10:00前通知直属经理。住院病假须附出院证明。试用期员工在第3个月起享有病假权益，前3个月按比例计算：第3个月5天门诊、15天住院。',
     2, 'hr', None),
]

# Optional: records that CONTRADICT the docx (carry-over 10 vs 5 days, paternity 3 vs 2 weeks) - see --with-conflicts
CONFLICT_ROWS = [
    ("HR-L03", "Annual Leave Carry-Over Rule", "Leave",
     "Up to 10 days of unused annual leave may be carried over to the next year and must be used by 30 June, after which they lapse. Carried-over leave is not paid out. Leave above 10 days is cleared on 31 December.",
     2, "hr", None),
    ("HR-L04", "Paternity Leave Entitlement", "Leave",
     "Fathers are entitled to 3 weeks of paid paternity leave, which must be taken within 12 months of the child's birth. Adoptive fathers receive the same entitlement.",
     2, "hr", None),
]


def main() -> None:
    remove = "--remove" in sys.argv
    rows = ROWS + (CONFLICT_ROWS if "--with-conflicts" in sys.argv else [])
    conn = psycopg2.connect(**ADMIN)
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge_records WHERE record_code LIKE 'HR-L%'")
        if not remove:
            execute_values(
                cur,
                "INSERT INTO knowledge_records (record_code, title, category, content, required_clearance, compartment, allowed_roles) VALUES %s",
                rows,
            )
        cur.execute("SELECT record_code FROM knowledge_records WHERE record_code LIKE 'HR-L%' ORDER BY 1")
        present = [r[0] for r in cur.fetchall()]
    conn.close()
    print("removed HR-L* records" if remove else f"hr_db now has HR-L* records: {', '.join(present)}")

    if "--sync" not in sys.argv:
        print("not indexed yet: the backend syncs data sources every DB_SYNC_INTERVAL seconds (default 30), or re-run with --sync")
        return

    from app.services.db_sync import run_db_sync  # loads the embedding model; skipped unless asked

    for name, r in run_db_sync().items():
        print(f"== {name}")
        for label, items in (("added", r.added), ("updated", r.updated), ("removed", r.removed),
                             ("skipped", r.skipped), ("errors", r.errors)):
            for i in items:
                print(f"  {label:8} {i}")


if __name__ == "__main__":
    main()
