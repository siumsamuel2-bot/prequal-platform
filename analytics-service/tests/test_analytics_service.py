"""Integration tests for the analytics service boundaries (MID-588).

Covers:
- Service-to-service authentication (X-Service-Api-Key, fail-closed)
- Trusted user context propagation and org/team isolation
- Event ingestion (stream + direct-write fallback)
- Reporting and anomaly detection endpoints
- Backward-compatible API contract with the monolith
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import AnalyticsEvent
from app.services.ingestion import EventProducer, IngestionConsumer, RedisUnavailableError

SERVICE_KEY = "test-service-key"


class FakeRedis:
    """Minimal in-memory Redis stub implementing the stream operations used."""

    def __init__(self):
        self.streams = {}
        self.groups = {}
        self._pending = {}
        self._counter = 0

    def xadd(self, stream, fields):
        self._counter += 1
        entry_id = f"{self._counter}-1"
        self.streams.setdefault(stream, []).append((entry_id, dict(fields)))
        return entry_id

    def xgroup_create(self, stream, group, id="0", mkstream=False):
        if stream not in self.streams and not mkstream:
            raise Exception("ERR no such stream")
        key = (stream, group)
        if key in self.groups:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.groups[key] = id
        self._pending[key] = []

    def xreadgroup(self, group, consumer, streams, count=100, block=None):
        stream = list(streams.keys())[0]
        key = (stream, group)
        entries = self.streams.get(stream, [])
        delivered = self._counter
        last_delivered = int(self.groups[key].split("-")[0])
        new_entries = [e for e in entries if int(e[0].split("-")[0]) > last_delivered]
        if not new_entries:
            return []
        batch = new_entries[:count]
        self.groups[key] = batch[-1][0]
        return [(stream, batch)]

    def xack(self, stream, group, *entry_ids):
        return len(entry_ids)

    def xlen(self, stream):
        return len(self.streams.get(stream, []))

    def pipeline(self, transaction=False):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.ops = []

    def xadd(self, stream, fields):
        self.ops.append(("xadd", stream, fields))

    def execute(self):
        results = []
        for op, stream, fields in self.ops:
            results.append((self.client.xadd(stream, fields), None))
        self.ops = []
        return results


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    return TestClient(app)


@pytest.fixture(scope="function")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def service_headers(user_id=None, role="admin", org_id=None):
    headers = {"X-Service-Api-Key": SERVICE_KEY}
    if user_id:
        headers["X-User-Id"] = user_id
        headers["X-User-Role"] = role
    if org_id:
        headers["X-Organization-Id"] = org_id
    return headers


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "prequal-analytics-service"


# ---------------------------------------------------------------------------
# Service-to-service authentication
# ---------------------------------------------------------------------------

def test_endpoints_reject_missing_service_key(client):
    resp = client.get("/api/v1/analytics/events")
    assert resp.status_code == 401

    resp = client.post("/api/v1/analytics/events", json={"event_type": "page_view"})
    assert resp.status_code == 401


def test_endpoints_reject_invalid_service_key(client):
    resp = client.get("/api/v1/analytics/events", headers={"X-Service-Api-Key": "wrong-key"})
    assert resp.status_code == 401


def test_service_auth_fails_closed_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_API_KEY", None)
    resp = client.get("/api/v1/analytics/events", headers={"X-Service-Api-Key": SERVICE_KEY})
    assert resp.status_code == 401


def test_admin_endpoints_require_admin_role(client):
    resp = client.get("/api/v1/analytics/feature-adoption", headers=service_headers(user_id="u1", role="user", org_id="org-1"))
    assert resp.status_code == 403

    resp = client.get("/api/v1/analytics/feature-adoption", headers=service_headers(user_id="u1", role="admin"))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Event ingestion (direct-write fallback when Redis unavailable)
# ---------------------------------------------------------------------------

def test_create_event_direct_write(client, db):
    resp = client.post(
        "/api/v1/analytics/events",
        json={"event_type": "page_view", "metadata": {"page": "/dashboard"}},
        headers=service_headers(user_id="user-1", role="admin", org_id="org-1"),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["event_type"] == "page_view"
    assert body["organization_id"] == "org-1"
    assert body["metadata"] == {"page": "/dashboard"}
    assert body["id"] != "pending"

    events = db.query(AnalyticsEvent).all()
    assert len(events) == 1
    assert events[0].event_metadata == {"page": "/dashboard"}


def test_create_event_non_admin_pinned_to_own_org(client, db):
    resp = client.post(
        "/api/v1/analytics/events",
        json={"event_type": "page_view", "organization_id": "other-org"},
        headers=service_headers(user_id="user-2", role="user", org_id="org-2"),
    )
    assert resp.status_code == 201
    assert resp.json()["organization_id"] == "org-2"


def test_list_events_org_isolation(client):
    for org in ("org-a", "org-b"):
        client.post(
            "/api/v1/analytics/events",
            json={"event_type": "page_view"},
            headers=service_headers(user_id=f"user-{org}", role="admin", org_id=org),
        )

    resp = client.get("/api/v1/analytics/events", headers=service_headers(user_id="u", role="user", org_id="org-a"))
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["organization_id"] == "org-a"

    resp = client.get("/api/v1/analytics/events", headers=service_headers(user_id="u", role="admin"))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_ingest_batch_stream_fallback(client):
    resp = client.post(
        "/api/v1/analytics/ingestion/events",
        json={"events": [{"event_type": "feature_usage"}, {"event_type": "feedback_submitted"}]},
        headers=service_headers(user_id="u1", role="admin"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] in ("stream", "direct")
    if body["mode"] == "direct":
        assert len(body["event_ids"]) == 2


# ---------------------------------------------------------------------------
# Redis Streams ingestion
# ---------------------------------------------------------------------------

def test_event_producer_publishes_to_stream():
    fake = FakeRedis()
    producer = EventProducer(redis_client=fake)
    entry_id = producer.publish({"event_type": "page_view", "metadata": {"a": 1}})
    assert entry_id == "1-1"
    assert fake.xlen("analytics:events") == 1
    entry = fake.streams["analytics:events"][0]
    assert entry[1]["event_type"] == "page_view"
    assert json.loads(entry[1]["metadata"]) == {"a": 1}


def test_event_producer_raises_when_unavailable():
    class BrokenRedis:
        def xadd(self, *args, **kwargs):
            raise ConnectionError("connection refused")

    producer = EventProducer(redis_client=BrokenRedis())
    with pytest.raises(RedisUnavailableError):
        producer.publish({"event_type": "page_view"})


def test_consumer_drains_stream_into_database(db):
    fake = FakeRedis()
    producer = EventProducer(redis_client=fake)
    for i in range(3):
        producer.publish({"event_type": "cert_uploaded", "user_id": f"u{i}", "metadata": {"i": i}})

    consumer = IngestionConsumer(redis_client=fake)
    ingested = consumer.consume(max_count=10)
    assert ingested == 3

    events = db.query(AnalyticsEvent).filter(AnalyticsEvent.event_type == "cert_uploaded").all()
    assert len(events) == 3
    assert {e.user_id for e in events} == {"u0", "u1", "u2"}
    assert all(e.event_metadata == {"i": i} for i, e in enumerate(events))


# ---------------------------------------------------------------------------
# Reporting endpoints (backward-compatible contract)
# ---------------------------------------------------------------------------

def test_track_feature_and_feature_adoption(client):
    resp = client.post(
        "/api/v1/analytics/track-feature",
        json={"feature_name": "compliance_dashboard", "event_type": "view"},
        headers=service_headers(user_id="u1", role="admin", org_id="org-1"),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "tracked"

    resp = client.get("/api/v1/analytics/feature-adoption", headers=service_headers(user_id="u1", role="admin"))
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["feature_name"] == "compliance_dashboard" and r["event_count"] == 1 for r in rows)


def test_track_health_and_system_health(client):
    resp = client.post(
        "/api/v1/analytics/track-health",
        json={"service_name": "api", "metric_name": "error_count", "metric_value": 0.01, "metric_unit": "percent"},
        headers={"X-Service-Api-Key": SERVICE_KEY},
    )
    assert resp.status_code == 200

    resp = client.get("/api/v1/analytics/system-health", headers=service_headers(user_id="u1", role="admin"))
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["service_name"] == "api" and r["metric_name"] == "error_count" for r in rows)


def test_daily_active_users(client):
    client.post(
        "/api/v1/analytics/track-feature",
        json={"feature_name": "login", "event_type": "action"},
        headers=service_headers(user_id="u1", role="admin"),
    )
    resp = client.get("/api/v1/analytics/daily-active-users", headers=service_headers(user_id="u1", role="admin"))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_weekly_report(client):
    resp = client.get("/api/v1/analytics/weekly-report", headers=service_headers(user_id="u1", role="admin"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["period"] == "weekly"
    assert "feature_adoption" in body and "system_health" in body and "alerts" in body


def test_anomalies(client):
    resp = client.get("/api/v1/analytics/anomalies", headers=service_headers(user_id="u1", role="admin"))
    assert resp.status_code == 200
    body = resp.json()
    assert "anomalies" in body and "total" in body
    assert body["total"] >= 1


def test_pilot_engagement(client):
    client.post(
        "/api/v1/analytics/events",
        json={"event_type": "onboarding_completion"},
        headers=service_headers(user_id="u1", role="admin", org_id="org-1"),
    )
    resp = client.get("/api/v1/analytics/pilot-engagement", headers=service_headers(user_id="u1", role="admin"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_organizations_30d"] == 1
    assert body["onboarding_completion_rate"] > 0
    assert body["recently_active_orgs"][0]["organization_id"] == "org-1"


# ---------------------------------------------------------------------------
# Dashboard configurations
# ---------------------------------------------------------------------------

def test_dashboard_config_crud(client):
    resp = client.post(
        "/api/v1/analytics/dashboard-configs",
        params={"name": "compliance-overview"},
        json={"widgets": ["expirations", "violations"]},
        headers=service_headers(user_id="u1", role="admin", org_id="org-1"),
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["organization_id"] == "org-1"

    resp = client.get("/api/v1/analytics/dashboard-configs", headers=service_headers(user_id="u2", role="user", org_id="org-2"))
    assert resp.status_code == 200
    assert resp.json() == []
