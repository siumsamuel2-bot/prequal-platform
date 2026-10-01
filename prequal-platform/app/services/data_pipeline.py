"""Data Pipeline module (legacy wrapper).

This module now re-exports the canonical implementation from
``external_compliance_pipeline`` to preserve backward compatibility.
All new code should import directly from ``external_compliance_pipeline``.
"""
from __future__ import annotations

from app.services.external_compliance_pipeline import (  # noqa: F401
    run_osha_sync,
    run_state_credential_sync,
    validate_pipeline_health,
    refresh_analytics_views,
    run_full_pipeline,
    record_pipeline_metric,
    get_pipeline_health_summary,
    MatchResult,
    PipelineRun,
    match_subcontractor,
    normalize_company_name,
    parse_date,
    parse_decimal,
    map_status,
)

__all__ = [
    "run_osha_sync",
    "run_state_credential_sync",
    "validate_pipeline_health",
    "refresh_analytics_views",
    "run_full_pipeline",
    "record_pipeline_metric",
    "get_pipeline_health_summary",
    "MatchResult",
    "PipelineRun",
    "match_subcontractor",
    "normalize_company_name",
    "parse_date",
    "parse_decimal",
    "map_status",
]
