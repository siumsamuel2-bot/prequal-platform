"""Anomaly detection for usage analytics.

Detects unusual patterns in feature usage and system health metrics
that may indicate churn, system degradation, or other problems.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.models.models import FeatureUsageEvent, SystemHealthMetric
from app.services.ingestion import FEATURE_NAMES

logger = logging.getLogger(__name__)


@dataclass
class Anomaly:
    """Represents a detected anomaly in analytics data."""
    anomaly_type: str
    severity: str
    feature: Optional[str]
    message: str
    detected_at: datetime
    metric_value: Optional[float] = None
    expected_range: Optional[tuple] = None


class UsageAnomalyDetector:
    """Detects anomalies in feature usage data."""

    def __init__(self, db: Session):
        self.db = db

    def detect_zero_usage_features(self, days: int = 7) -> List[Anomaly]:
        """Find features with zero usage events."""
        anomalies = []
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = (
            self.db.query(FeatureUsageEvent.feature_name)
            .filter(FeatureUsageEvent.created_at >= cutoff)
            .distinct()
            .all()
        )
        active_features = {row.feature_name for row in rows}
        for feature in FEATURE_NAMES:
            if feature not in active_features:
                anomalies.append(Anomaly(
                    anomaly_type="zero_usage",
                    severity="warning",
                    feature=feature,
                    message=f"No usage events for {feature} in the last {days} days. Potential churn signal.",
                    detected_at=datetime.utcnow(),
                ))
        return anomalies

    def detect_usage_drops(self, days: int = 7, threshold: float = 0.5) -> List[Anomaly]:
        """Detect features with a significant usage drop compared to the previous period."""
        anomalies = []
        current_cutoff = datetime.utcnow() - timedelta(days=days)
        previous_cutoff = datetime.utcnow() - timedelta(days=days * 2)

        current_rows = (
            self.db.query(
                FeatureUsageEvent.feature_name,
                func.count(FeatureUsageEvent.id).label("count"),
            )
            .filter(FeatureUsageEvent.created_at >= current_cutoff)
            .group_by(FeatureUsageEvent.feature_name)
            .all()
        )
        previous_rows = (
            self.db.query(
                FeatureUsageEvent.feature_name,
                func.count(FeatureUsageEvent.id).label("count"),
            )
            .filter(
                FeatureUsageEvent.created_at >= previous_cutoff,
                FeatureUsageEvent.created_at < current_cutoff,
            )
            .group_by(FeatureUsageEvent.feature_name)
            .all()
        )

        current_counts = {row.feature_name: row.count for row in current_rows}
        previous_counts = {row.feature_name: row.count for row in previous_rows}

        for feature in set(current_counts) | set(previous_counts):
            current_count = current_counts.get(feature, 0)
            previous_count = previous_counts.get(feature, 0)
            if current_count < previous_count * threshold and previous_count > 10:
                anomalies.append(Anomaly(
                    anomaly_type="usage_drop",
                    severity="critical",
                    feature=feature,
                    message=f"Usage for {feature} dropped significantly: {current_count} vs {previous_count} previous period.",
                    detected_at=datetime.utcnow(),
                    metric_value=float(current_count),
                    expected_range=(previous_count * threshold, previous_count),
                ))
        return anomalies

    def detect_health_anomalies(self, hours: int = 1, error_rate_threshold: float = 0.05) -> List[Anomaly]:
        """Detect system health anomalies based on error rates."""
        anomalies = []
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        rows = (
            self.db.query(
                SystemHealthMetric.service_name,
                func.avg(SystemHealthMetric.metric_value).label("avg_value"),
            )
            .filter(
                SystemHealthMetric.recorded_at >= cutoff,
                SystemHealthMetric.metric_name == "error_count",
            )
            .group_by(SystemHealthMetric.service_name)
            .having(func.avg(SystemHealthMetric.metric_value) > error_rate_threshold)
            .all()
        )
        for row in rows:
            anomalies.append(Anomaly(
                anomaly_type="high_error_rate",
                severity="critical",
                feature=row.service_name,
                message=f"High error rate in {row.service_name}: avg={row.avg_value:.4f}.",
                detected_at=datetime.utcnow(),
                metric_value=row.avg_value,
            ))
        return anomalies

    def run_all_checks(self) -> List[Anomaly]:
        """Run all anomaly detection checks and return combined results."""
        anomalies = []
        anomalies.extend(self.detect_zero_usage_features())
        anomalies.extend(self.detect_usage_drops())
        anomalies.extend(self.detect_health_anomalies())
        return anomalies
