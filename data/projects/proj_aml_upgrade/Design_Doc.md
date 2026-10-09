# Design Doc: Real-Time Transaction Monitoring Engine

- Document ID: J05
- Department: Engineering
- Owner: Marcus Teo, Staff Engineer, Financial Crime Platform
- Version: v1.1
- Effective Date: 2026-09-25
- Classification: Internal
- Compartments: none

## 1. Context and goals

The legacy engine, Sentinel, runs batch scenarios overnight and cannot score transactions before they settle. We are replacing it with a real-time engine by 2027-03-31, also in response to findings in MAS discussions on monitoring coverage and alert backlog. This document covers architecture, migration, risks and test plan.

- Goal 1: score every transaction in real time with p99 latency under 300 ms end to end (p50 under 60 ms).
- Goal 2: reduce false-positive alert rate by 30% versus Sentinel through better segmentation and tuning.
- Goal 3: rule changes deployable within 1 business day without code release.
- Goal 4: full audit trail of rule version, inputs and decision for 5 years.
- Non-goals: replacing sanctions screening and KYC systems in this phase.

## 2. Architecture

```
Payments / Cards / Account services
        |  (events)
   [Kafka-compatible event bus: topic txn.v1, 24 partitions]
        |
   [Ingest and enrichment] -> feature store (customer profile, 30/90 day aggregates)
        |
   [Rule engine + scoring] -> decision API (sync hook for pre-authorisation)
        |
   [Alert writer] -> Case management (CaseFlow) -> Analysts
        |
   [Audit store: immutable, 5-year retention]
```

### 2.1 Streaming ingest

Transaction events from Payments, Cards and Account services are published to a Kafka-compatible event bus (topic `txn.v1`, 24 partitions keyed by customer_id, replication factor 3). Schema is Avro with a schema registry. Peak design load is 1,500 events per second, 3x the observed peak of about 500 per second, with a retention of 7 days for replay.

### 2.2 Enrichment and feature store

A stream processor enriches each event with customer risk rating, KYC attributes and rolling aggregates (7, 30 and 90 days) held in a low-latency key-value store (target read p99 under 10 ms). Aggregates are computed incrementally.

### 2.3 Rule engine

Rules are expressed in a declarative DSL with versioning in Git and deployed via a rules service after four-eyes approval from Compliance and Engineering. Scenario types: velocity, structuring, high-risk corridor, dormant account reactivation, rapid in-out movement, and behavioural anomaly scores from a gradient-boosted model. Each rule can run in shadow mode before activation.

### 2.4 Case management integration

Alerts are written to CaseFlow, our case management tool, through an alert API with idempotent keys. Alerts are grouped per customer per 24 hours to avoid duplicates. Case outcomes, including STR decisions, are fed back into the feature store for tuning. SLA: alert visible to analysts within 5 seconds of generation.

### 2.5 Latency budget

| Stage | p99 budget |
|---|---|
| Event ingest | 30 ms |
| Enrichment and features | 70 ms |
| Rule and model evaluation | 120 ms |
| Decision and alert write | 50 ms |
| Headroom | 30 ms |
| Total | 300 ms |

## 3. Availability and resilience

- Active-active across two availability zones; availability target 99.95%.
- The pre-authorisation hook fails open to a lightweight rule set with async scoring if the engine exceeds 300 ms, with each fail-open event logged and reviewed.
- Dead-letter queue for malformed events; replay supported from the bus.
- Disaster recovery RPO of 5 minutes and RTO of 30 minutes.

## 4. Migration plan from Sentinel

| Phase | Dates | Description | Exit criteria |
|---|---|---|---|
| 0. Foundations | 2026-10 to 2026-11 | Infrastructure, bus, schemas, CaseFlow integration | End-to-end pipeline in staging |
| 1. Rule translation | 2026-11 to 2026-12 | Translate 86 Sentinel scenarios to DSL; document gaps | 100% scenarios mapped and reviewed by Compliance |
| 2. Shadow run | 2027-01 to 2027-02 | New engine runs in parallel; compare alerts with Sentinel | At least 95% of Sentinel true positives reproduced; latency target met for 14 days |
| 3. Phased cutover | 2027-03 | Cutover by product: Account (week 1), Pay (week 2), Card (week 3) | No SEV1/SEV2 during each step; sign-off by MLRO |
| 4. Sentinel decommission | By 2027-03-31, archive until 2027-06 | Sentinel set to read-only, data archived with 5-year retention | Regulatory sign-off, archive verified |

Rollback: during phase 3, Sentinel batch remains runnable for each product for 30 days after cutover.

## 5. Risks

- MAS inspection in November 2026 coincides with phases 0 and 1; engineering capacity is shared with evidence requests.
- Rule translation may expose scenarios with ambiguous logic, causing delay.
- Alert volumes may spike at cutover, overwhelming 14 analysts; mitigation is a temporary surge pool of 4 contractors.
- Model explainability requirements from Compliance may limit use of advanced models.
- Dependency on the Vietnam launch for scale-out of the data model.

## 6. Test plan

- Unit and rule tests: each rule has at least 10 positive and 10 negative cases.
- Replay test: 12 months of anonymised historical transactions, comparing alerts with Sentinel.
- Load test: sustained 1,500 events per second for 2 hours; p99 under 300 ms.
- Chaos tests: node loss, partition rebalance, feature store outage.
- UAT: 6 analysts review 500 alerts for quality; sign-off from MLRO.
- Security: penetration test and access review before go-live.

## 7. Open questions

- Hosting of the feature store in Singapore only, or also in Vietnam after launch.
- Vendor versus in-house model for behavioural anomaly scoring decision by 2026-11-30.
