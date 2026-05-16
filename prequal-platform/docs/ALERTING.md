# Prequal Alerting Data Model & API Documentation

## Overview

The alerting system monitors certification expiration dates and generates internal alert records at configurable warning intervals. This document describes the data model, API endpoints, and how the daily scan service works.

---

## Data Model

### `alert_notifications` Table

Stores individual alert records generated for expiring certifications.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | |
| certification_id | UUID | FK → certifications.id, CASCADE | Links to the expiring cert |
| alert_type | VARCHAR(50) | NOT NULL | e.g. `expiration_30d`, `expiration_14d`, `expiration_7d` |
| scheduled_for | TIMESTAMP WITH TZ | NOT NULL | Date the alert was generated |
| sent_at | TIMESTAMP WITH TZ | | Reserved for future external notification delivery |
| status | VARCHAR(50) | DEFAULT 'pending' | `pending`, `acknowledged`, `sent`, `failed` |
| acknowledged_at | TIMESTAMP WITH TZ | | When the alert was acknowledged |
| days_until_expiration | INTEGER | | Denormalized for quick querying |
| method | VARCHAR(50) | | `in_app` (no external delivery yet) |
| recipient | VARCHAR(255) | | Target recipient id/contact |
| subject | VARCHAR(255) | | Human-readable alert subject |
| body | TEXT | | Full alert message |
| retry_count | INTEGER | DEFAULT 0 | Delivery retry attempts |
| max_retries | INTEGER | DEFAULT 3 | Maximum retry attempts |
| error_message | TEXT | | Error on delivery failure |
| created_at | TIMESTAMP WITH TZ | DEFAULT CURRENT_TIMESTAMP | |
| updated_at | TIMESTAMP WITH TZ | DEFAULT CURRENT_TIMESTAMP | |

### `certifications` Table (related)

The alerting service scans `certifications.expiration_date` with `status = 'valid'`.

When a certification passes its expiration date, the service automatically sets `certifications.status = 'expired'`.

---

## Alert Lifecycle

1. **Scan** — Daily scan identifies certifications approaching expiration.
2. **Generate** — An `alert_notification` record is created for each cert in each warning window (30, 14, 7 days).
3. **Deduplication** — Only one alert per certification per window per day is generated.
4. **Acknowledge** — Users can mark an alert as `acknowledged` via the API.
5. **Archive/Expire** — Acknowledged alerts are retained for audit. Expired certs are flagged, not deleted.

---

## API Endpoints

### `GET /api/alerts`

List all alerts with filtering and pagination.

**Query Parameters:**
- `skip` (int, default 0) — pagination offset
- `limit` (int, default 100) — page size
- `status_filter` (enum: `pending`, `sent`, `failed`, `cancelled`, `acknowledged`)
- `alert_type` (string) — filter by alert type
- `days_until` (int) — filter by days_until_expiration

**Response:** List of `AlertNotificationResponse` objects.

### `GET /api/alerts/by-contractor/{contractor_id}`

Get alerts scoped to a specific subcontractor (contractor).

**Query Parameters:**
- `status_filter` (optional enum)
- `skip`, `limit` (pagination)

**Response:** Enriched alert list including `contractor_name` and `project_ids`.

### `GET /api/alerts/by-project/{project_id}`

Get alerts scoped to a specific project (active subcontractors on that project).

**Query Parameters:**
- `status_filter` (optional enum)
- `skip`, `limit` (pagination)

**Response:** Enriched alert list.

### `PATCH /api/alerts/{alert_id}/acknowledge`

Acknowledge an alert, setting status to `acknowledged` and `acknowledged_at` to current timestamp.

**Response:** `AlertNotificationResponse` with updated status.

### `POST /api/alerts/scan`

Trigger a manual expiration scan (admin/testing).

**Response:**
```json
{
  "message": "Expiration scan completed",
  "summary": {
    "alerts_created": 5,
    "certifications_expired": 2,
    "warnings_30": 2,
    "warnings_14": 1,
    "warnings_7": 0
  }
}
```

### `GET /api/alerts/summary`

Get summary counts for a time window (default 30 days).

**Query Parameters:**
- `days` (int, default 30) — lookback window

**Response:**
```json
{
  "pending_alerts": 12,
  "acknowledged_alerts": 5,
  "expired_certifications": 3,
  "lookback_days": 30
}
```

---

## Daily Scan Service

The scan is implemented in `app/services/alert_service.py` as an async function `scan_expirations(db)`.

### Algorithm

1. **Mark expired certifications:**
   - Find all certs where `expiration_date < today()` AND `status != 'expired'`
   - Set `status = 'expired'`

2. **Check warning windows (30, 14, 7 days):**
   - For each window, find certs where `expiration_date == today() + window` AND `status == 'valid'`
   - Deduplicate by cert_id, alert_type, and date to avoid duplicate alerts
   - Create `AlertNotification` records with `status='pending'` and `method='in_app'`

### Warning Windows

| Window | Alert Type | Description |
|--------|-----------|-------------|
| 30 days | `expiration_30d` | Month-before warning |
| 14 days | `expiration_14d` | Two-week warning |
| 7 days | `expiration_7d` | Final week warning |

### Deduplication

Before creating an alert, the service checks:
```
SELECT * FROM alert_notifications
WHERE certification_id = :cert_id
  AND alert_type = :alert_type
  AND DATE(scheduled_for) = CURRENT_DATE;
```

If a record exists, the alert is skipped for that day.

---

## Pydantic Schemas

### `AlertNotificationResponse`

Returns an alert with all metadata including:
- `id`, `certification_id`, `alert_type`
- `scheduled_for`, `sent_at`, `acknowledged_at`
- `status`, `method`, `recipient`, `subject`, `body`
- `retry_count`, `max_retries`, `error_message`
- `days_until_expiration`
- `created_at`, `updated_at`

### `AlertNotificationUpdate`

Fields allowed for update:
- `status`, `sent_at`, `error_message`, `acknowledged_at`

### `AlertNotificationCreate`

Used internally by the service, not directly by clients.

---

## Future Enhancements

- **External notification delivery** (email/SMS) — hooks ready in `method`/`sent_at`/`retry_count` columns
- **Configurable warning windows** via `alert_preferences.advance_notice_days`
- **Bulk acknowledge** endpoint for multi-alert management
- **Alert templates** for customizable messages per certification type
