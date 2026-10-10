"""Coverage for ``app/scheduled.py`` background job wiring and runners (MID-676).

The scheduler module sits outside the FastAPI request cycle and was previously
uncovered (0%). These tests exercise the job registration and each runner's
success and failure paths without a live database or network by monkeypatching
the async session factory and the pipeline entry points.
"""

from unittest.mock import MagicMock

import pytest

import app.scheduled as scheduled


class _FakeSession:
    """Minimal async-context-manager stand-in for ``AsyncSessionLocal()``."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


@pytest.fixture
def fake_session_factory(monkeypatch):
    def _factory():
        return _FakeSession()

    monkeypatch.setattr(scheduled, "AsyncSessionLocal", _factory)
    return _factory


class TestScheduleJobs:
    """``schedule_jobs`` registers the full set of recurring jobs."""

    def test_registers_all_expected_jobs(self):
        scheduler = MagicMock()
        scheduled.schedule_jobs(scheduler)

        assert scheduler.add_job.call_count == 5
        job_ids = {call.kwargs["id"] for call in scheduler.add_job.call_args_list}
        assert job_ids == {
            "daily_expiration_scan",
            "daily_alert_delivery",
            "daily_osha_sync",
            "daily_state_credential_sync",
            "daily_data_quality_checks",
        }

    def test_uses_cron_triggers(self):
        from apscheduler.triggers.cron import CronTrigger

        scheduler = MagicMock()
        scheduled.schedule_jobs(scheduler)

        for call in scheduler.add_job.call_args_list:
            assert isinstance(call.args[1], CronTrigger)


class TestDailyScanRunner:
    async def test_success_runs_scan_inside_session(self, monkeypatch, fake_session_factory):
        seen = {}

        async def fake_scan(db):
            seen["db"] = db
            return {
                "alerts_created": 1,
                "certifications_expired": 2,
                "warnings_30": 3,
                "warnings_14": 4,
                "warnings_7": 5,
            }

        monkeypatch.setattr(scheduled, "scan_expirations", fake_scan)
        await scheduled._run_daily_scan()
        assert isinstance(seen["db"], _FakeSession)

    async def test_swallows_scan_failure(self, monkeypatch, fake_session_factory):
        async def boom(db):
            raise RuntimeError("db down")

        monkeypatch.setattr(scheduled, "scan_expirations", boom)
        # Must not raise: the runner logs and continues.
        await scheduled._run_daily_scan()


class TestDailyDeliveryRunner:
    async def test_success_runs_delivery_inside_session(self, monkeypatch, fake_session_factory):
        seen = {}

        async def fake_deliver(db):
            seen["db"] = db
            return {
                "total_processed": 1,
                "sent_email": 1,
                "sent_sms": 0,
                "failed": 0,
            }

        monkeypatch.setattr(scheduled, "deliver_pending_alerts", fake_deliver)
        await scheduled._run_daily_delivery()
        assert isinstance(seen["db"], _FakeSession)

    async def test_swallows_delivery_failure(self, monkeypatch, fake_session_factory):
        async def boom(db):
            raise RuntimeError("smtp down")

        monkeypatch.setattr(scheduled, "deliver_pending_alerts", boom)
        await scheduled._run_daily_delivery()


class TestOshaSyncRunner:
    async def test_success(self, monkeypatch, fake_session_factory):
        import app.services.external_compliance_pipeline as pipeline

        async def fake_run(db, triggered_by):
            assert triggered_by == "schedule"
            return MagicMock(
                status="completed",
                records_inserted=3,
                records_updated=2,
                records_failed=0,
            )

        monkeypatch.setattr(pipeline, "run_osha_sync", fake_run)
        await scheduled._run_osha_sync()

    async def test_swallows_failure(self, monkeypatch, fake_session_factory):
        import app.services.external_compliance_pipeline as pipeline

        async def boom(db, triggered_by):
            raise RuntimeError("osha api down")

        monkeypatch.setattr(pipeline, "run_osha_sync", boom)
        await scheduled._run_osha_sync()


class TestStateCredentialSyncRunner:
    async def test_success_syncs_configured_and_supported_states(
        self, monkeypatch, fake_session_factory
    ):
        import app.services.external_compliance_pipeline as pipeline
        import app.services.state_scrapers.factory as factory

        monkeypatch.setenv("STATE_SYNC_STATES", "CA,TX")
        monkeypatch.setattr(factory, "list_supported_states", lambda: ["CA", "NY"])

        synced = []

        async def fake_run(db, state_code, triggered_by):
            synced.append((state_code, triggered_by))
            return MagicMock(
                status="completed",
                records_inserted=1,
                records_updated=0,
                records_failed=0,
            )

        monkeypatch.setattr(pipeline, "run_state_credential_sync", fake_run)
        await scheduled._run_state_credential_sync()

        # env states + scraper states, de-duplicated, order preserved.
        assert [s for s, _ in synced] == ["CA", "TX", "NY"]
        assert all(triggered == "schedule" for _, triggered in synced)

    async def test_one_state_failure_does_not_stop_others(
        self, monkeypatch, fake_session_factory
    ):
        import app.services.external_compliance_pipeline as pipeline
        import app.services.state_scrapers.factory as factory

        monkeypatch.setenv("STATE_SYNC_STATES", "CA,TX")
        monkeypatch.setattr(factory, "list_supported_states", lambda: [])

        synced = []

        async def flaky_run(db, state_code, triggered_by):
            if state_code == "CA":
                raise RuntimeError("CA scraper down")
            synced.append(state_code)
            return MagicMock(
                status="completed",
                records_inserted=0,
                records_updated=0,
                records_failed=0,
            )

        monkeypatch.setattr(pipeline, "run_state_credential_sync", flaky_run)
        await scheduled._run_state_credential_sync()
        assert synced == ["TX"]

    async def test_swallows_orchestration_failure(self, monkeypatch, fake_session_factory):
        import app.services.state_scrapers.factory as factory

        def boom():
            raise RuntimeError("factory misconfigured")

        monkeypatch.setattr(factory, "list_supported_states", boom)
        await scheduled._run_state_credential_sync()


class TestDataQualityChecksRunner:
    async def test_success_runs_both_suites(self, monkeypatch, fake_session_factory):
        import app.services.external_compliance_pipeline as pipeline
        import app.services.data_quality_monitoring as monitoring

        async def fake_validate(db):
            return {
                "unmatched_osha_violations": 1,
                "unmatched_state_credentials": 2,
                "stale_runs_cleaned": 3,
                "stale_running_jobs": 4,
                "failed_jobs_last_7d": 5,
            }

        async def fake_monitor(db):
            return {"alerts_triggered": [{"id": 1}, {"id": 2}]}

        monkeypatch.setattr(pipeline, "validate_pipeline_health", fake_validate)
        monkeypatch.setattr(monitoring, "run_data_quality_health_check", fake_monitor)
        await scheduled._run_data_quality_checks()

    async def test_swallows_failure(self, monkeypatch, fake_session_factory):
        import app.services.external_compliance_pipeline as pipeline

        async def boom(db):
            raise RuntimeError("checks failed")

        monkeypatch.setattr(pipeline, "validate_pipeline_health", boom)
        await scheduled._run_data_quality_checks()
