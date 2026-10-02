"""Analytics event ingestion pipeline.

Two ingestion paths:
1. Redis Streams (default): events are published to a stream via XADD and a
   consumer group drains them into the analytics_events table, enabling
   decoupled, scalable ingestion and a background worker.
2. Direct write fallback: when Redis is unavailable, events are written
   synchronously to the database so ingestion never blocks callers.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.models import AnalyticsEvent, FeatureUsageEvent, SystemHealthMetric

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "login",
    "dashboard_view",
    "compliance_dashboard",
    "subcontractor_view",
    "certification_upload",
    "alert_config",
    "report_export",
    "invite_team",
    "settings_change",
]

SYSTEM_METRICS = [
    "api_request_count",
    "api_response_time_ms",
    "db_connection_count",
    "db_query_time_ms",
    "error_count",
    "active_users",
    "background_job_queue_depth",
]


class RedisUnavailableError(Exception):
    """Raised when the Redis stream cannot be reached."""


class EventProducer:
    """Publishes analytics events to the Redis stream."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    def _get_redis(self):
        if self._redis is None:
            import redis as redis_lib

            self._redis = redis_lib.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._redis

    def publish(self, event: Dict[str, Any]) -> str:
        """Publish an event to the stream. Returns the stream entry id."""
        payload = {k: json.dumps(v) if isinstance(v, (dict, list)) else (v if v is not None else "") for k, v in event.items()}
        try:
            entry_id = self._get_redis().xadd(settings.ANALYTICS_EVENTS_STREAM, payload)
            return str(entry_id)
        except Exception as exc:
            raise RedisUnavailableError(str(exc)) from exc

    def publish_many(self, events: List[Dict[str, Any]]) -> List[str]:
        """Publish a batch of events to the stream."""
        pipe = None
        try:
            client = self._get_redis()
            pipe = client.pipeline(transaction=False)
            ids = []
            for event in events:
                payload = {
                    k: json.dumps(v) if isinstance(v, (dict, list)) else (v if v is not None else "")
                    for k, v in event.items()
                }
                pipe.xadd(settings.ANALYTICS_EVENTS_STREAM, payload)
            for entry_id, _ in pipe.execute():
                ids.append(str(entry_id))
            return ids
        except Exception as exc:
            raise RedisUnavailableError(str(exc)) from exc


class IngestionConsumer:
    """Drains the analytics events stream into the database.

    Uses a consumer group so multiple workers can ingest in parallel without
    double-processing. Entries are acknowledged only after a successful write.
    """

    def __init__(self, redis_client=None, consumer_name: Optional[str] = None):
        self._redis = redis_client
        self.consumer_name = consumer_name or f"ingestor-{uuid.uuid4().hex[:8]}"

    def _get_redis(self):
        if self._redis is None:
            import redis as redis_lib

            self._redis = redis_lib.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._redis

    def _ensure_group(self, client) -> None:
        try:
            client.xgroup_create(settings.ANALYTICS_EVENTS_STREAM, settings.ANALYTICS_CONSUMER_GROUP, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def consume(self, max_count: int = 100) -> int:
        """Read up to max_count entries from the stream and persist them.

        Returns the number of events ingested.
        """
        client = self._get_redis()
        self._ensure_group(client)
        ingested = 0
        while ingested < max_count:
            result = client.xreadgroup(
                settings.ANALYTICS_CONSUMER_GROUP,
                self.consumer_name,
                {settings.ANALYTICS_EVENTS_STREAM: ">"},
                count=min(100, max_count - ingested),
                block=0 if ingested == 0 else 100,
            )
            if not result:
                break
            for _stream, entries in result:
                entry_ids = []
                rows = []
                for entry_id, fields in entries:
                    entry_ids.append(entry_id)
                    rows.append(self._to_row(fields))
                if rows:
                    self._persist(rows)
                client.xack(settings.ANALYTICS_EVENTS_STREAM, settings.ANALYTICS_CONSUMER_GROUP, *entry_ids)
                ingested += len(entry_ids)
        return ingested

    def _to_row(self, fields: Dict[str, str]) -> Dict[str, Any]:
        def _load(key: str) -> Any:
            raw = fields.get(key)
            if not raw:
                return None
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return raw

        return {
            "id": str(uuid.uuid4()),
            "event_type": fields.get("event_type", "unknown"),
            "user_id": fields.get("user_id") or None,
            "organization_id": fields.get("organization_id") or None,
            "event_metadata": _load("metadata"),
            "source_service": fields.get("source_service") or None,
        }

    def _persist(self, rows: List[Dict[str, Any]]) -> None:
        db = SessionLocal()
        try:
            db.add_all([AnalyticsEvent(**row) for row in rows])
            db.commit()
        finally:
            db.close()


class AnalyticsIngestionService:
    """Service for ingesting analytics data (direct-write fallback path)."""

    def __init__(self, db: Session, producer: Optional[EventProducer] = None):
        self.db = db
        self.producer = producer or EventProducer()

    def ingest_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ingest a single analytics event via the stream, falling back to a direct write."""
        event = {
            "event_type": event_type,
            "user_id": user_id or "",
            "organization_id": organization_id or "",
            "metadata": json.dumps(metadata) if metadata else "",
            "source_service": source_service or "",
        }
        try:
            entry_id = self.producer.publish(event)
            return {"mode": "stream", "stream_entry_id": entry_id, "event_id": None}
        except RedisUnavailableError:
            logger.warning("Redis stream unavailable; writing event directly to database")
            return {"mode": "direct", **self._direct_write_event(event_type, user_id, organization_id, metadata, source_service)}

    def ingest_event_batch(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ingest a batch of events via the stream, falling back to direct writes."""
        payload = [
            {
                "event_type": e.get("event_type", "unknown"),
                "user_id": e.get("user_id") or "",
                "organization_id": e.get("organization_id") or "",
                "metadata": json.dumps(e["metadata"]) if e.get("metadata") else "",
                "source_service": e.get("source_service") or "",
            }
            for e in events
        ]
        try:
            entry_ids = self.producer.publish_many(payload)
            return {"mode": "stream", "stream_entry_ids": entry_ids, "event_ids": []}
        except RedisUnavailableError:
            logger.warning("Redis stream unavailable; writing %d events directly to database", len(payload))
            ids = [self._direct_write_event(**event)["event_id"] for event in payload]
            return {"mode": "direct", "event_ids": ids}

    def _direct_write_event(
        self,
        event_type: str,
        user_id: Optional[str],
        organization_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
        source_service: Optional[str],
    ) -> Dict[str, Any]:
        row = AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            organization_id=organization_id,
            event_metadata=metadata,
            source_service=source_service,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return {"mode": "direct", "event_id": row.id}

    def track_feature_event(
        self,
        feature_name: str,
        event_type: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        row = FeatureUsageEvent(
            user_id=user_id,
            feature_name=feature_name,
            event_type=event_type,
            event_metadata=metadata,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info("Tracked feature event: %s %s (id=%s)", feature_name, event_type, row.id)
        return row.id

    def track_system_health_metric(
        self,
        service_name: str,
        metric_name: str,
        metric_value: float,
        metric_unit: Optional[str] = None,
    ) -> str:
        row = SystemHealthMetric(
            service_name=service_name,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info("Tracked health metric: %s %s=%.2f%s (id=%s)", service_name, metric_name, metric_value, metric_unit or "", row.id)
        return row.id
