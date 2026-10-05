"""Tests for analytics-service data quality monitoring (MID-626)."""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import (
    AnalyticsEvent,
    FeatureUsageEvent,
    DataQualityAlert,
    AnalyticsEventArchive,
)
from app.services import data_quality


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _mk_events(db, n, source="worker", org_id="org-1", user_id="u-1", days_old=0):
    for i in range(n):
        db.add(
            AnalyticsEvent(
                id=str(uuid.uuid4()),
                event_type="track",
                user_id=user_id,
                organization_id=org_id,
                source_service=source,
                created_at=datetime.utcnow() - timedelta(days=days_old),
            )
        )
    db.commit()


class TestFreshness:
    def test_no_events_all_breach(self, db_session):
        result = data_quality.check_freshness(db_session)
        assert result["total_breached"] == 0  # no sources yet
        assert result["sources"] == []

    def test_recent_event_not_breached(self, db_session):
        _mk_events(db_session, 3, days_old=0)
        result = data_quality.check_freshness(db_session)
        assert result["total_breached"] == 0
        assert result["sources"][0]["breached"] is False

    def test_stale_event_breaches(self, db_session):
        _mk_events(db_session, 2, days_old=5)
        result = data_quality.check_freshness(db_session)
        assert result["total_breached"] == 1
        assert result["sources"][0]["breached"] is True


class TestFieldQuality:
    def test_null_rates_detected(self, db_session):
        # 5 events: 2 missing org id -> 40% null rate (> 10% threshold)
        _mk_events(db_session, 3)
        for _ in range(2):
            db_session.add(
                AnalyticsEvent(
                    id=str(uuid.uuid4()),
                    event_type="track",
                    user_id=None,
                    organization_id=None,
                    source_service="worker",
                    created_at=datetime.utcnow(),
                )
            )
        db_session.commit()
        result = data_quality.check_field_quality(db_session)
        org_field = next(
            f for f in result["fields"]
            if f["table"] == "analytics_events" and f["column"] == "organization_id"
        )
        assert org_field["null_count"] == 2
        assert org_field["null_rate"] == 0.4
        assert any(a["alert_type"] == "high_null_rate" for a in result["alerts"])

    def test_healthy_data_no_alerts(self, db_session):
        _mk_events(db_session, 10)
        result = data_quality.check_field_quality(db_session)
        assert result["alerts"] == []


def _seed_feature_events(db, *, days=None, today_count=0, per_day=10):
    """Seed feature events: `today_count` at this exact moment, `per_day` at
    noon UTC for each day in `days` (days are day-offsets into the past)."""
    if days is None:
        days = range(1, 8)
    now = datetime.utcnow()
    for _ in range(today_count):
        db.add(
            FeatureUsageEvent(
                id=str(uuid.uuid4()),
                user_id="u-1",
                feature_name="login",
                event_type="action",
                created_at=now,
            )
        )
    for day_offset in days:
        anchor = datetime.combine(now.date() - timedelta(days=day_offset), datetime.min.time()) + timedelta(hours=12)
        for _ in range(per_day):
            db.add(
                FeatureUsageEvent(
                    id=str(uuid.uuid4()),
                    user_id="u-1",
                    feature_name="export_pdf" if day_offset % 2 else "login",
                    event_type="action",
                    created_at=anchor,
                )
            )
    db.commit()


class TestVolumeAnomalies:
    def test_volume_drop_detected(self, db_session):
        # 10 events/day for 7 past days, 0 today -> anomaly
        _seed_feature_events(db_session, days=range(1, 8), today_count=0, per_day=10)
        result = data_quality.check_volume_anomalies(db_session)
        assert result["anomalous"] is True
        assert "alert" in result

    def test_normal_volume_not_anomalous(self, db_session):
        # 10 events/day for 6 past days AND 10 today -> healthy
        _seed_feature_events(db_session, days=range(1, 7), today_count=10, per_day=10)
        result = data_quality.check_volume_anomalies(db_session)
        assert result["anomalous"] is False


class TestRunAndArchive:
    def test_run_check_persists_alerts(self, db_session):
        # seed stale + null-heavy data so alerts trigger
        _mk_events(db_session, 2, days_old=10)
        for _ in range(3):
            db_session.add(
                AnalyticsEvent(
                    id=str(uuid.uuid4()),
                    event_type="track",
                    user_id=None,
                    organization_id=None,
                    source_service="worker",
                    created_at=datetime.utcnow(),
                )
            )
        db_session.commit()
        result = data_quality.run_data_quality_check(db_session, persist=True)
        assert len(result["alerts"]) >= 1
        assert db_session.query(DataQualityAlert).count() >= 1

    def test_archive_is_insert_only(self, db_session):
        _mk_events(db_session, 2, days_old=200)
        before = db_session.query(AnalyticsEvent).count()
        res = data_quality.archive_old_analytics_events(db_session, retention_days=90)
        assert res["archived"] == 2
        # source rows untouched
        assert db_session.query(AnalyticsEvent).count() == before
        assert db_session.query(AnalyticsEventArchive).count() == 2

    def test_archive_idempotent(self, db_session):
        _mk_events(db_session, 3, days_old=200)
        data_quality.archive_old_analytics_events(db_session, retention_days=90)
        res = data_quality.archive_old_analytics_events(db_session, retention_days=90)
        assert res["archived"] == 0
        assert db_session.query(AnalyticsEventArchive).count() == 3
