"""Create the demo department databases and register them as data sources.

One Postgres database per department; each has a `knowledge_records` table whose
rows carry their own access control (see requirement/db_source_demo.md):

  compartment IS NULL  -> normal record (role + clearance only)
  compartment = 'aml'  -> partitioned record (user must also hold the compartment)
  allowed_roles NULL   -> inherit the database's attach role (data_sources.permission_mapping)

Idempotent: drops and recreates the databases and the data_sources rows.
Usage: docker compose exec backend python seed_dept_databases.py
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from app.core.db import SessionLocal
from app.models.data_source import DataSource

HOST, PORT = "postgres", 5432
ADMIN = dict(host=HOST, port=PORT, user="rbac", password="rbac")
READER, READER_PW = "rag_reader", "rag_reader"

# (code, title, category, content, clearance, compartment, allowed_roles)
E = "employee"
HR = [
    ("HR-N01", "Internal Job Transfer Rules", "Mobility",
     "Employees may apply for an internal transfer after 12 months in their current role. The current manager must be notified at the same time as the application and cannot block a transfer, but may delay the start date by up to 60 days for handover. A transfer into a higher grade needs a fresh interview; a lateral move does not.",
     1, None, [E]),
    ("HR-N02", "Long-Service Award Scheme", "Recognition",
     "Milestone awards are given at 5, 10, 15 and 20 years of service: 500, 1,500, 3,000 and 6,000 respectively, plus extra leave of 1, 2, 3 and 5 days. Awards are paid in the month of the work anniversary. Career breaks longer than 6 months pause the service count.",
     2, None, None),
    ("HR-N03", "Staff Mortgage Interest Subsidy", "Benefits",
     "Confirmed employees with at least 3 years of service receive a 1.25 percentage point subsidy on the interest rate of a first home loan taken with the bank, applied to the first 400,000 of principal for up to 15 years. The subsidy ends on resignation and is reduced to 0.5 points on retirement.",
     2, None, None),
    ("HR-N04", "Overtime and Allowance Rules for Line Managers", "Compensation",
     "Overtime must be pre-approved by the line manager. Weekday overtime is compensated at 1.5x, rest-day work at 2.0x. Staff at Grade 8 and above are not eligible for overtime pay; they receive a flat meal allowance of 25 per late evening after 8pm.",
     2, None, ["hr_manager", "exec"]),
    ("HR-Z01", "Open Grievance Register (anonymised)", "Employee Relations",
     "Six grievances open at the end of Q3: three on workload allocation in Operations, two on shift scheduling in Customer Support, one on a manager's communication style in Technology. Average age of an open case is 26 days against a 30-day resolution target; case G-26-004 has exceeded it.",
     3, "hr", None),
    ("HR-Z02", "Succession Plan for Critical Roles", "Workforce Planning",
     "Twelve roles are designated critical. Ready-now successors exist for seven of them; the Head of Treasury, Head of Fraud and Chief Information Security Officer roles have no ready successor. Development plans for the nine identified high-potential staff are reviewed twice a year.",
     3, "hr", None),
    ("HR-Z03", "Whistleblowing Case Log", "Governance",
     "Four whistleblowing reports were received in FY2026, two via the external hotline and two directly to the Audit Committee chair. One concerned procurement irregularities and is under investigation by Internal Audit. Reporter identities are held only by the Audit Committee chair.",
     4, "board", ["exec"]),
    ("HR-Z04", "Key-Person Retention Awards", "Compensation",
     "Retention awards of 15-30% of base salary are offered to 14 staff in the digital banking and fraud analytics teams, vesting in two equal tranches at 12 and 24 months. Total commitment is 1.9 million. Awards lapse on resignation before the vesting date. Names are not to be circulated outside HR and Executive.",
     4, "hr", ["hr_manager", "exec"]),
]
FIN = [
    ("FIN-N01", "Petty Cash Handling", "Cash Management",
     "Each office keeps a petty cash float of 800 held in a locked safe by a named custodian. Single disbursements are limited to 100. The float is counted every Friday by someone other than the custodian and replenished when it falls below 200. Any shortage above 10 is reported to the Finance Controller the same day.",
     1, None, [E]),
    ("FIN-N02", "Cost Centre Allocation Rules", "Management Accounting",
     "Shared costs are allocated monthly: premises by floor area, IT services by user count, and HR services by headcount. Costs below 2,000 per month are not allocated and stay in the Shared Services cost centre. Cost centre owners may dispute an allocation within 5 working days of receiving the monthly report.",
     2, None, None),
    ("FIN-N03", "Withholding Tax on Vendor Payments", "Tax",
     "Payments to non-resident vendors are subject to withholding tax: 15% for royalties and interest, 17% for management fees, and 0% for goods. The rate may be reduced under a tax treaty if a valid residency certificate is on file before payment. Payables must not release the full amount until the tax clearance check is completed.",
     2, None, None),
    ("FIN-N04", "FX Hedging Desk Procedures", "Treasury",
     "Forward contracts are booked by the hedging desk only against documented exposures above 250,000 equivalent. Hedge ratio targets are 80% for exposures within 3 months and 50% for 3-12 months. Each contract needs a hedge-effectiveness memo within 5 working days of trade date.",
     2, None, None),
    ("FIN-Z01", "Interim Dividend Proposal", "Capital",
     "Management proposes an interim dividend of 0.11 per share, a 40% payout of first-half earnings, totalling 52 million. Capital adequacy remains above the board target of 15.5% after payment. The proposal goes to the board in the November meeting and is not to be disclosed before announcement.",
     3, "finance", None),
    ("FIN-Z02", "Transfer Pricing Study Summary", "Tax",
     "The FY2026 study concludes that intra-group service charges for technology and shared operations fall within the interquartile range, with a median mark-up of 7.2%. One adjustment is proposed: the regional HQ charge should rise from 5% to 6.5% to remain defensible. Estimated additional tax exposure if unchanged is 1.4 million.",
     3, "finance", None),
    ("FIN-Z03", "Acquisition Bridge Facility Covenants", "M&A",
     "The proposed 180 million bridge facility carries a maximum leverage covenant of 3.5x EBITDA, a minimum interest cover of 4.0x, and a 90-day mandatory refinancing trigger after closing. Margin is 210 basis points over base rate. A breach of the leverage covenant allows lenders to demand repayment.",
     3, "finance", ["finance_analyst", "proj_merger"]),
    ("FIN-Z04", "Board Share Buyback Authorisation", "Capital",
     "The board is asked to authorise a buyback of up to 2% of issued shares, capped at 75 million, to run for 12 months from January 2027. Purchases may not occur in the 30 days before results announcements. The programme is conditional on the capital adequacy ratio staying above 15%.",
     4, "board", ["exec"]),
]
RSK = [
    ("RSK-N01", "Collateral Valuation Haircuts", "Credit Policy",
     "Haircuts applied to collateral value: residential property 20%, commercial property 35%, listed shares 40%, fixed deposits 5%, vehicles 50%. Property valuations older than 12 months must be refreshed before a facility is renewed. Valuers must come from the approved panel of six firms.",
     2, None, None),
    ("RSK-N02", "Early Warning Indicators for Retail Accounts", "Monitoring",
     "An account is flagged for early review when two or more of these occur: salary credit stops for 2 consecutive months, utilisation of the revolving limit exceeds 90% for 3 months, minimum-payment-only behaviour for 4 cycles, or a new delinquency on an external credit report. Flagged accounts get a contact within 7 days.",
     2, None, ["risk_analyst", "customer_support"]),
    ("RSK-N03", "Merchant Blacklist Review Cycle", "Fraud",
     "Merchants with a chargeback ratio above 1.0% for two consecutive months are added to the blacklist review queue. The review team decides within 5 working days whether to suspend acceptance. Blacklist entries are reviewed every 90 days and removed only with the Head of Fraud's approval.",
     2, None, ["risk_analyst", "card_ops"]),
    ("RSK-N04", "Key Risk Indicator Thresholds", "Risk Governance",
     "Amber and red thresholds: 30-day delinquency 3.5% / 5.0%, fraud loss rate 6 / 9 basis points of card spend, system availability 99.7% / 99.3%, staff turnover in risk functions 12% / 18%. Any red indicator is escalated to the Chief Risk Officer within 2 working days.",
     3, None, ["risk_analyst", "exec"]),
    ("RSK-Z01", "Loan-to-Value Limits by Property Type", "Credit Policy",
     "Maximum loan-to-value: owner-occupied residential 75%, second property 60%, commercial shop-house 65%, industrial 55%. Exceptions up to 5 points need the Head of Credit and are capped at 3% of quarterly mortgage originations.",
     3, "credit", None),
    ("RSK-Z02", "Portfolio Stress Test Results", "Portfolio",
     "Under the severe scenario (unemployment up 4 points, property prices down 25%) cumulative 12-month credit losses reach 412 million, versus 168 million in the base case. The unsecured retail book accounts for 58% of the increase. Post-stress capital adequacy falls to 12.9%, above the 11% regulatory minimum.",
     3, "credit", None),
    ("RSK-Z03", "Restructured Loan Register (anonymised)", "Portfolio",
     "Twenty-three accounts totalling 96 million were restructured in Q3, 14 of them SME. Twelve are performing after the restructuring, seven are on probation and four have re-defaulted. The largest, a 18 million hospitality loan, received a 24-month moratorium on principal.",
     3, "credit", None),
    ("RSK-Z04", "Counterparty Limit Breach Waivers", "Governance",
     "Three temporary limit breaches were waived in Q3, the largest being 14% over the approved limit for a bank counterparty during a settlement delay, lasting 3 days. Waivers above 10% require the Chief Risk Officer and must be reported to the Risk Committee at its next meeting.",
     4, "credit", None),
]
CMP = [
    ("CMP-N01", "Whistleblowing Channels", "Ethics",
     "Concerns can be raised through the 24-hour external hotline, the whistleblowing mailbox, or directly with the Audit Committee chair. Reports can be anonymous. Retaliation against a reporter is a disciplinary offence and any suspected retaliation must be reported to Compliance within 1 working day.",
     1, None, [E]),
    ("CMP-N02", "Personal Account Dealing Rules", "Conduct",
     "Staff in treasury, research and investment advisory must pre-clear every personal securities trade and hold positions for at least 30 days. Pre-clearance is valid for 2 trading days. Quarterly holdings statements are due within 10 days of quarter end.",
     2, None, None),
    ("CMP-N03", "Correspondent Banking Due Diligence", "Third Parties",
     "New correspondent relationships need a questionnaire, a review of the respondent's own AML controls, and approval by the Head of Compliance. Shell banks are prohibited. Existing correspondents are re-reviewed every 18 months, or after any enforcement action against them.",
     2, None, ["compliance_officer", "legal_counsel", "risk_analyst"]),
    ("CMP-N04", "Insider List Maintenance", "Conduct",
     "A deal-specific insider list is opened when a project receives inside information, recording each person's name, access date and time. Persons are removed only after the information becomes public or the deal is abandoned. Lists are retained for 5 years.",
     2, None, None),
    ("CMP-Z01", "Wire Transfer Originator Information Rules", "AML",
     "Cross-border wires of 1,500 or more must carry full originator name, account number and address, and beneficiary name and account number. Incomplete messages are held for 1 working day for repair and rejected if still incomplete. Repeated incomplete messages from the same sender bank are reported to Compliance.",
     2, "aml", None),
    ("CMP-Z02", "Trade-Based Money Laundering Red Flags", "AML",
     "Red flags include invoices that differ significantly from market price (over 25%), repeated amendment of letters of credit, shipments routed through unrelated third countries, and payments from parties not named in the contract. Two or more flags require enhanced review by a senior trade finance officer.",
     3, "aml", None),
    ("CMP-Z03", "Cash-Intensive Business Review Programme", "AML",
     "Customers such as restaurants, money-changers and car dealers are reviewed every 6 months. Reviewers compare monthly cash deposits against declared turnover; a variance above 30% for 3 consecutive months leads to a referral to the MLRO. 41 customers are in the programme, 6 are currently under referral.",
     3, "aml", None),
    ("CMP-Z04", "Law Enforcement Request Log (anonymised)", "AML",
     "Nine production orders and information requests were received from authorities in the first three quarters, five of them in Q3. The average response time was 6 working days against a 10-day deadline. Request details and the existence of any request are restricted to the MLRO to avoid tipping-off.",
     3, "aml", ["mlro"]),
]
SUP = [
    ("SUP-N01", "ATM Cash-Out Limits and Troubleshooting", "ATM",
     "The default daily ATM withdrawal limit is 2,000 for debit cards and 1,000 for cash advance on credit cards. If cash is not dispensed but the account is debited, the customer should not retry; a case is logged and the amount is credited back within 3 working days after the ATM reconciliation.",
     1, None, [E]),
    ("SUP-N02", "Joint Account Operating Instructions", "Accounts",
     "Joint accounts operate on 'either to sign' or 'all to sign' mandates, chosen at opening. Changing the mandate needs all holders present or a signed instruction from each. When one holder dies, the account is frozen until the death certificate is verified and the survivor is confirmed, normally within 5 working days.",
     1, None, None),
    ("SUP-N03", "Overdraft Facility Customer FAQ", "Accounts",
     "Overdraft limits start at 1,000 and are set at up to 2 times monthly salary for salaried customers. Interest accrues daily on the amount used, and no interest is charged when the account is in credit. The facility is reviewed annually and can be withdrawn with 30 days' notice.",
     1, None, None),
    ("SUP-N04", "Fixed Deposit Early Withdrawal Rules", "Deposits",
     "A fixed deposit withdrawn before maturity earns interest at 50% of the contracted rate for the period held, and nothing if withdrawn within the first 14 days. Partial withdrawals are allowed in multiples of 1,000, provided the remaining balance meets the 5,000 minimum.",
     1, None, None),
    ("SUP-N05", "VIP Customer Handling", "Service",
     "Priority-banking customers are routed to the dedicated VIP desk with a 20-second answer target. Agents may offer a relationship manager call-back within 2 hours. Fee waivers up to 500 may be approved by the VIP desk lead.",
     2, None, ["customer_support", "account_manager"]),
    ("SUP-N06", "Scam Victim Call Script", "Fraud",
     "Verify identity with two factors, immediately block the card or session, and reassure the customer. Do not ask for full card number or PIN. Open a fraud case, advise the customer to file a police report, and transfer to the fraud desk for chargeback assessment.",
     2, None, ["customer_support", "risk_analyst"]),
]

DEPTS = [  # db, source name, attach role, rows
    ("hr_db", "HR Database", "hr_manager", HR),
    ("finance_db", "Finance Database", "finance_analyst", FIN),
    ("risk_credit_db", "Risk & Credit Database", "risk_analyst", RSK),
    ("compliance_db", "Compliance Database", "compliance_officer", CMP),
    ("support_db", "Customer Support Database", "customer_support", SUP),
]

DDL = """
CREATE TABLE knowledge_records (
    id                 SERIAL PRIMARY KEY,
    record_code        TEXT NOT NULL UNIQUE,
    title              TEXT NOT NULL,
    category           TEXT,
    content            TEXT NOT NULL,
    required_clearance INT  NOT NULL DEFAULT 1 CHECK (required_clearance BETWEEN 1 AND 4),
    compartment        TEXT,    -- NULL = normal record, otherwise a partition
    allowed_roles      TEXT[],  -- NULL = inherit the database's attach role
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def build_database(db: str, rows: list) -> None:
    conn = psycopg2.connect(dbname="postgres", **ADMIN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(db)))
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db)))
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (READER,))
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s").format(sql.Identifier(READER)), (READER_PW,))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db), sql.Identifier(READER)))
    conn.close()

    conn = psycopg2.connect(dbname=db, **ADMIN)
    with conn, conn.cursor() as cur:
        cur.execute(DDL)
        execute_values(
            cur,
            "INSERT INTO knowledge_records (record_code, title, category, content, required_clearance, compartment, allowed_roles) VALUES %s",
            rows,
        )
        cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(READER)))
    conn.close()


def register_sources() -> None:
    session = SessionLocal()
    try:
        session.query(DataSource).filter(DataSource.name.in_([d[1] for d in DEPTS])).delete(synchronize_session=False)
        for db, name, role, _ in DEPTS:
            session.add(DataSource(
                name=name, type="postgresql", sync_status="pending",
                connection_config=dict(host=HOST, port=PORT, dbname=db, user=READER, password=READER_PW,
                                       table="knowledge_records", id_column="record_code", title_column="title",
                                       content_columns=["content"], updated_at_column="updated_at"),
                permission_mapping=dict(attach_roles=[role], clearance_column="required_clearance",
                                        compartment_column="compartment", roles_column="allowed_roles",
                                        default_clearance=1),
            ))
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    for db, name, role, rows in DEPTS:
        build_database(db, rows)
        normal = sum(1 for r in rows if r[5] is None)
        print(f"{db:16} attach_role={role:20} {normal} normal + {len(rows) - normal} partitioned")
    register_sources()
    print("registered", len(DEPTS), "data sources")
