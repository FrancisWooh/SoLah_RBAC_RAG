# Fraud Rules Playbook

- Document ID: R03
- Department: Risk & Credit
- Owner: Daniel Koh, Head of Fraud Strategy
- Version: v1.0
- Effective Date: 2026-07-01
- Classification: Internal
- Compartments: none

## 1. Purpose

This playbook lists the active real-time fraud rules running in the Aspire Core decision engine for corporate card and account transactions, the thresholds that trigger each action, and the analyst handling process. Rules are owned by the Fraud Strategy team and reviewed monthly.

## 2. Rule Catalogue

| Rule ID | Name | Trigger | Action |
|---|---|---|---|
| FR-101 | Card velocity (count) | More than 5 card-present authorisations in 10 minutes on one card | Decline 6th, create alert |
| FR-102 | Card velocity (value) | Cumulative authorisations above SGD 15,000 within 1 hour on one card | Step-up and queue for review |
| FR-103 | Merchant velocity | Same card, same merchant, 4 or more attempts in 5 minutes | Soft decline, alert |
| FR-110 | Device mismatch | Online transaction from a device never seen on the account, with billing country mismatch | 3DS step-up challenge |
| FR-111 | New device plus high value | New device and amount above SGD 3,000 | 3DS step-up plus push notification to admin user |
| FR-120 | Geo impossibility | Two transactions more than 800 km apart within 60 minutes | Decline second, alert |
| FR-130 | High-risk MCC | MCC 7995 (gambling), 6051 (quasi-cash), 4829 (money transfer) above SGD 1,000 | Queue for review |
| FR-140 | Card testing | 10 or more declined attempts below SGD 5 in 15 minutes | Auto-block card |
| FR-150 | Transfer to new payee | PayNow or FAST transfer above SGD 20,000 to a payee added in the last 24 hours | Hold and callback |
| FR-160 | Account takeover signals | Password reset followed by limit change or new payee within 30 minutes | Lock session, alert security_engineer |

## 3. Auto-Block Thresholds

Each transaction receives a fraud score from 0 to 1000. The engine acts on the score as follows:

- 0-399: approve.
- 400-649: approve with monitoring; no customer impact.
- 650-849: 3DS step-up for online payments, or manual review queue for card-present and transfers.
- 850 and above: auto-decline and temporary card block; customer is contacted by card_ops through Aspire Hub / SupportDesk within 15 minutes during business hours (9:00-18:00 SGT), otherwise by SMS and in-app message.

Any card that triggers FR-140 or accumulates three auto-declines in 24 hours is blocked automatically and requires verified customer contact to unblock.

## 4. Step-Up Authentication

3DS step-up uses 3DS 2.x risk-based authentication with in-app approval as the preferred method and SMS OTP as fallback. A step-up that is not completed within 5 minutes is treated as a decline. Three failed challenges within 30 minutes block online use of the card for 24 hours.

## 5. Analyst Review SLA

- Queue alerts (score 650-849) must be reviewed within 30 minutes of creation during business hours.
- High-priority alerts (FR-150, FR-160 and any value above SGD 20,000) are reviewed within 15 minutes.
- Out-of-hours alerts are picked up by the on-call risk_analyst by 09:30 SGT next business day unless the value exceeds SGD 50,000, in which case the on-call analyst responds within 30 minutes.
- Analysts record the outcome (Confirmed fraud, Genuine, Inconclusive) in SupportDesk with a reason code.

## 6. Performance Targets

| Metric | Target |
|---|---|
| False-positive rate (genuine declined or held / total alerts) | below 8% |
| Fraud detection rate by value | at least 85% |
| Alert backlog older than SLA | below 2% |
| Fraud basis points of card volume | below 6 bps |

Rules whose false-positive rate exceeds 8% for two consecutive weeks are put into shadow mode and retuned by Fraud Strategy within 10 business days.

## 7. Change Control

New rules start in shadow mode for 14 days. Promotion to live requires sign-off from the Head of Fraud Strategy and a card_ops representative. Emergency rules for active attacks may go live immediately with retrospective approval within 2 business days. Confirmed fraud involving possible money laundering is passed to the MLRO under the AML procedures.
