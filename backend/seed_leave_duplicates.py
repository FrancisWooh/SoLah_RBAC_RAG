"""Add HR leave-policy records to hr_db that overlap with data/hr/Leave_Policy_Admin_Guide.docx (H01),
to demo how RAG handles the same fact living in both a file and a database.

  HR-L01  exact copy        annual leave entitlement (same wording as the docx)
  HR-L02  paraphrase        sick leave (English rewording, same numbers)
  HR-L03  conflict          annual leave carry-over (docx: 5 days by end of March; record: 10 days by end of June)
  HR-L04  conflict          paternity leave (docx: 2 weeks within 16 weeks; record: 3 weeks within 12 months)

Access control mirrors H01 (clearance 2, compartment 'hr', roles inherited from the HR database's
attach role), so the same users see both copies.

Only touches hr_db rows whose record_code starts with 'HR-L'; idempotent.
Usage:
  docker compose exec backend python seed_leave_duplicates.py            add/refresh the records, then sync
  docker compose exec backend python seed_leave_duplicates.py --remove   delete them, then sync
"""

import sys

import psycopg2
from psycopg2.extras import execute_values

from app.services.db_sync import run_db_sync

ADMIN = dict(host="postgres", port=5432, user="rbac", password="rbac", dbname="hr_db")

# (code, title, category, content, clearance, compartment, allowed_roles)
ROWS = [
    ("HR-L01", "Annual Leave Entitlement", "Leave",
     "年假政策规定：员工入职满1年后，每年享有18天带薪年假。工龄每满2年增加1天，累计上限为25天。例如，服务满3年的员工享有19天，服务满15年及以上的员工享有25天上限。入职不满1年的员工按月比例计算，每月1.5天，向下取整至半天。",
     2, "hr", None),
    ("HR-L02", "Sick Leave Quick Reference", "Leave",
     "Staff get 14 days of paid outpatient sick leave a year, and up to 60 days of paid hospitalisation leave in total (the 14 outpatient days are counted inside the 60). A medical certificate from a registered doctor is needed for absences of 2 or more consecutive days; a single day without an MC is allowed twice a year after telling the line manager. Notify the manager before 10:00 on the day.",
     2, "hr", None),
    ("HR-L03", "Annual Leave Carry-Over Rule", "Leave",
     "Up to 10 days of unused annual leave may be carried over to the next year and must be used by 30 June, after which they lapse. Carried-over leave is not paid out. Leave above 10 days is cleared on 31 December.",
     2, "hr", None),
    ("HR-L04", "Paternity Leave Entitlement", "Leave",
     "Fathers are entitled to 3 weeks of paid paternity leave, which must be taken within 12 months of the child's birth. Adoptive fathers receive the same entitlement.",
     2, "hr", None),
]


def main() -> None:
    remove = "--remove" in sys.argv
    conn = psycopg2.connect(**ADMIN)
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge_records WHERE record_code LIKE 'HR-L%'")
        if not remove:
            execute_values(
                cur,
                "INSERT INTO knowledge_records (record_code, title, category, content, required_clearance, compartment, allowed_roles) VALUES %s",
                ROWS,
            )
    conn.close()
    print("removed HR-L* records" if remove else f"upserted {len(ROWS)} HR-L* records into hr_db")

    for name, r in run_db_sync().items():
        print(f"== {name}")
        for label, items in (("added", r.added), ("updated", r.updated), ("removed", r.removed),
                             ("skipped", r.skipped), ("errors", r.errors)):
            for i in items:
                print(f"  {label:8} {i}")


if __name__ == "__main__":
    main()
