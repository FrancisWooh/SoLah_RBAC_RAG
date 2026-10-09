# Incident Response Runbook

- Document ID: E02
- Department: Engineering
- Owner: Siti Rahmat, Head of Site Reliability
- Version: v2.1
- Effective Date: 2026-05-01
- Classification: Internal
- Compartments: none

## 1. Purpose

This runbook defines how Engineering and Security detect, classify, manage and learn from production incidents affecting Aspire services. It supports our MAS Technology Risk Management obligations. The on-call engineer is accountable for starting the process; the Incident Commander owns it from declaration to resolution.

## 2. Severity levels

| Severity | Definition | Acknowledge | Update cadence |
|---|---|---|---|
| SEV1 | Critical: widespread payment, card authorisation or login failure, confirmed data breach, or major regulatory impact | 15 minutes, 24x7 | Status page every 30 minutes |
| SEV2 | Major degradation of a core function for a subset of customers, no workaround | 30 minutes, 24x7 | Every 60 minutes |
| SEV3 | Minor feature impaired, workaround available | 4 business hours | Daily |
| SEV4 | Cosmetic issue or internal tooling, no customer impact | Next business day | On resolution |

When in doubt, declare the higher severity and downgrade later.

## 3. Roles

- Incident Commander (IC): runs the response, assigns tasks, decides on rollbacks and severity changes. Does not debug.
- Communications Lead: owns status page, customer support briefings and internal updates; coordinates with Corporate Communications for SEV1.
- Scribe: keeps a timestamped log in SGT in the incident channel and doc.
- Subject Matter Experts (SMEs): investigate and fix, reporting to the IC.
- Compliance liaison: joins for any SEV1 or any incident with data or regulatory aspects.

## 4. Declaring an incident

- Page on-call via the paging tool; acknowledge within the SLA above.
- Create the Aspire Hub incident channel named `#inc-YYYYMMDD-n`, where n is the sequence of incidents that day, for example `#inc-20260814-1`.
- Post the template: severity, impact, start time (SGT), IC, Comms Lead, Scribe.
- Start a video bridge and link it in the channel topic.

## 5. Response workflow

- Stabilise first: prefer rollback, feature flag off or failover over forward fixes.
- Hypotheses and actions are logged by the Scribe with timestamps.
- The IC polls SMEs every 15 minutes during SEV1 and 30 minutes during SEV2.
- Any change in production during an incident requires IC approval verbally recorded in the channel.
- Resolution is declared when customer impact has ended and monitoring is stable for 30 minutes.

## 6. Communication

For SEV1, the first status page post goes out within 20 minutes of declaration and updates follow every 30 minutes until resolution, even when the update is 'no change'. Customer Support receives a briefing note within 30 minutes. Internal executive notification goes to the CTO and COO within 30 minutes of SEV1 declaration. External wording on cause is approved by Legal and Compliance before publication.

## 7. Regulatory notification

Compliance determines whether an incident is a relevant incident under MAS notices. For a major technology incident, notification to MAS must be made within 1 hour of the incident being classified as such, using the MAS reporting channel. The Compliance liaison files the notice and logs the reference number in the incident doc. A root cause and impact report follows to MAS within 14 days. Where personal data is affected, the PDPA breach process applies in parallel: PDPC must be notified within 3 calendar days of assessing a breach as notifiable.

## 8. Post-incident

- A blameless postmortem is published within 5 business days for SEV1 and SEV2.
- The postmortem includes timeline in SGT, impact, root cause, what went well, what went poorly, and action items with owners and due dates.
- Action items are tracked in the engineering backlog with the label `postmortem`; overdue items are reviewed monthly by the VP Engineering.
- SEV3 incidents need a short written summary within 10 business days.

## 9. Drills

Run one SEV1 game day per quarter. On-call engineers must complete the IC training course within 90 days of joining the rotation.
