# API Design Standards

- Document ID: E01
- Department: Engineering
- Owner: Wei Jie Lee, Principal Engineer, Platform
- Version: v1.0
- Effective Date: 2026-03-01
- Classification: Public
- Compartments: none

## 1. Scope

These standards apply to every public and partner-facing REST API at Aspire, and by default to internal service APIs. The API Guild reviews new APIs in a design review before any code is merged to main. Exceptions require sign-off from the Principal Engineer, Platform.

## 2. Resource and naming rules

- Base path is versioned: `https://api.aspire.example/v1/...`.
- Resource names are plural nouns in kebab-case: `/v1/corporate-cards`, `/v1/payment-orders`.
- JSON fields use snake_case: `created_at`, `account_id`.
- Identifiers are prefixed strings, for example `acc_`, `card_`, `pay_`, and are opaque to clients.
- Timestamps are ISO 8601 in UTC (`2026-08-14T06:30:00Z`). Money is an object with `amount` in minor units (integer) and `currency` (ISO 4217).
- Use HTTP verbs correctly: GET read, POST create or action, PATCH partial update, DELETE remove. Actions that are not CRUD use a sub-resource, for example `POST /v1/corporate-cards/{id}/freeze`.

## 3. Versioning

Only the major version appears in the URL (`/v1`). Backwards-compatible changes (new optional fields, new endpoints) do not bump the version. Breaking changes require `/v2` and a deprecation period of at least 12 months for partner APIs and 6 months for internal APIs. Deprecated endpoints return the headers `Deprecation` and `Sunset`.

## 4. Authentication and authorization

All APIs use OAuth2 with the client-credentials grant for server-to-server calls. Access tokens are JWTs with a lifetime of 15 minutes. Scopes follow `resource:action`, for example `payments:write`. Clients must never send secrets in URLs.

```http
POST /oauth2/token HTTP/1.1
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=CLIENT_ID_PLACEHOLDER&client_secret=SECRET_PLACEHOLDER&scope=payments:write
```

## 5. Idempotency

Every POST that creates a payment or moves money must include an `Idempotency-Key` header (UUID v4). Requests without it receive `400` with the problem type `missing-idempotency-key`. Keys are retained for 24 hours; a replay with the same key and body returns the original response, while the same key with a different body returns `409`.

```http
POST /v1/payment-orders HTTP/1.1
Authorization: Bearer <token>
Idempotency-Key: 3f6c1f5e-9a1d-4b71-8a52-0c9f7d2e4a10
Content-Type: application/json

{"source_account_id": "acc_1042", "amount": {"amount": 125000, "currency": "SGD"}, "beneficiary_id": "ben_77"}
```

## 6. Error format

Errors follow RFC 7807 (`application/problem+json`). Every error includes `type`, `title`, `status`, `detail` and `trace_id`. Validation errors add an `errors` array.

```json
{
  "type": "https://api.aspire.example/problems/insufficient-funds",
  "title": "Insufficient funds",
  "status": 422,
  "detail": "Available balance is below the requested amount.",
  "trace_id": "b7e2c0d1f4a94c3e"
}
```

Never leak stack traces, SQL or internal hostnames. Use 4xx for client mistakes, 5xx for server faults only.

## 7. Pagination, filtering, sorting

List endpoints use cursor pagination. The default `limit` is 50 and the maximum is 200. Responses include `next_cursor`; a null value means the last page. Offset pagination is not allowed on datasets that can exceed 10,000 rows.

```json
{
  "data": [{"id": "pay_9001"}],
  "next_cursor": "eyJpZCI6InBheV85MDAxIn0",
  "has_more": true
}
```

Filters use query parameters (`status=settled&created_from=2026-08-01`). Sorting uses `sort=-created_at`.

## 8. Rate limiting

The default limit is 600 requests per minute per API key, enforced with a token bucket. Responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset`. When exceeded, return `429` with `Retry-After` in seconds. Higher limits for enterprise partners need approval from the API Guild and capacity review by SRE.

## 9. Webhooks

Webhook payloads are signed with HMAC-SHA256 in the `Aspire-Signature` header. Deliveries are retried with exponential backoff for up to 24 hours. Consumers must treat events as at-least-once and deduplicate by `event_id`.

## 10. Review checklist

- OpenAPI 3.1 spec committed alongside code and linted in CI.
- All POST money-movement endpoints enforce idempotency.
- Error responses conform to RFC 7807.
- Scopes defined and least-privilege applied.
- Contract tests and a p95 latency budget of 250 ms documented.
