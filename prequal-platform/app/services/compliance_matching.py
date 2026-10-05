"""Compliance Data Deduplication and Matching Validation

Provides utilities for fuzzy matching, duplicate detection, and
matching accuracy validation when integrating external compliance data
(OSHA violations, state credentials) with internal subcontractor records.

Owner: Data Engineer
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MatchValidationResult:
    """Result of a matching validation pass."""
    total_records: int = 0
    matched_records: int = 0
    unmatched_records: int = 0
    duplicate_records: int = 0
    match_by_ein: int = 0
    match_by_license: int = 0
    match_by_name: int = 0
    match_by_none: int = 0
    average_confidence: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)


@dataclass
class DuplicateCheckResult:
    """Result of a duplicate check on a single record."""
    is_duplicate: bool = False
    canonical_id: Optional[str] = None
    duplicate_of: Optional[List[str]] = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Fuzzy matching utilities
# ---------------------------------------------------------------------------

def jaro_winkler(s1: str, s2: str) -> float:
    """Compute Jaro-Winkler similarity between two strings (0.0 to 1.0)."""
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    # Jaro similarity
    len1, len2 = len(s1), len(s2)
    match_distance = (max(len1, len2) // 2) - 1

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)

        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (
        (matches / len1)
        + (matches / len2)
        + ((matches - transpositions / 2) / matches)
    ) / 3.0

    # Jaro-Winkler: boost for common prefix
    prefix = 0
    for i in range(min(len(s1), len(s2))):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    prefix = min(prefix, 4)

    return jaro + (0.1 * prefix * (1 - jaro))


def normalize_text(text: str) -> str:
    """Normalize text for comparison: uppercase, strip, collapse whitespace."""
    if not text:
        return ""
    return " ".join(text.upper().strip().split())


def normalize_ein(ein: str) -> str:
    """Normalize EIN to XX-XXXXXXX format, or return empty if invalid."""
    if not ein:
        return ""
    stripped = ein.strip().upper()
    cleaned = stripped.replace("-", "").replace(" ", "")
    if len(cleaned) == 9 and cleaned.isdigit():
        return f"{cleaned[:2]}-{cleaned[2:]}"
    return stripped


def normalize_license(license_number: str) -> str:
    """Normalize license number: uppercase, strip whitespace."""
    if not license_number:
        return ""
    return license_number.strip().upper()


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def is_potential_duplicate(
    rec1: Dict[str, Any],
    rec2: Dict[str, Any],
    *,
    name_threshold: float = 0.85,
    ein_exact: bool = True,
) -> DuplicateCheckResult:
    """Check if two external records are likely duplicates of the same violation/credential.

    Matches are based on:
    - Same OSHA violation ID / credential number (exact)
    - Same EIN + date + penalty (fuzzy)
    - Same company name + date + penalty (fuzzy)
    """
    # Exact match by external ID fields
    if rec1.get("osha_violation_id") and rec2.get("osha_violation_id"):
        if rec1["osha_violation_id"] == rec2["osha_violation_id"]:
            return DuplicateCheckResult(
                is_duplicate=True,
                canonical_id=rec1.get("id"),
                duplicate_of=[rec2.get("id", "")],
                reason="Same OSHA violation ID",
            )

    if rec1.get("credential_number") and rec2.get("credential_number"):
        if (
            rec1.get("credential_number") == rec2.get("credential_number")
            and rec1.get("state_code") == rec2.get("state_code")
        ):
            return DuplicateCheckResult(
                is_duplicate=True,
                canonical_id=rec1.get("id"),
                duplicate_of=[rec2.get("id", "")],
                reason="Same credential number and state",
            )

    # EIN + date + penalty match
    ein1 = normalize_ein(rec1.get("ein", ""))
    ein2 = normalize_ein(rec2.get("ein", ""))
    if ein_exact and ein1 and ein1 == ein2:
        date1 = parse_iso_date(rec1.get("issued_date"))
        date2 = parse_iso_date(rec2.get("issued_date"))
        if date1 and date2 and date1 == date2:
            return DuplicateCheckResult(
                is_duplicate=True,
                canonical_id=rec1.get("id"),
                duplicate_of=[rec2.get("id", "")],
                reason="Same EIN and issued date",
            )

    # Name + date fuzzy match
    name1 = normalize_text(rec1.get("company_name") or rec1.get("holder_name", ""))
    name2 = normalize_text(rec2.get("company_name") or rec2.get("holder_name", ""))
    if name1 and name2:
        name_sim = jaro_winkler(name1, name2)
        if name_sim >= name_threshold:
            date1 = parse_iso_date(rec1.get("issued_date"))
            date2 = parse_iso_date(rec2.get("issued_date"))
            if date1 and date2 and date1 == date2:
                return DuplicateCheckResult(
                    is_duplicate=True,
                    canonical_id=rec1.get("id"),
                    duplicate_of=[rec2.get("id", "")],
                    reason=f"Fuzzy name match ({name_sim:.2f}) and same date",
                )

    return DuplicateCheckResult(is_duplicate=False)


def find_duplicates(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Given a list of records, return (unique_records, duplicates).

    Each record must have an 'id' field for tracking.
    """
    unique: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []

    for i, rec in enumerate(records):
        is_dup = False
        for j in range(i):
            other = records[j]
            check = is_potential_duplicate(rec, other)
            if check.is_duplicate:
                rec["_duplicate_info"] = {
                    "duplicate_of": other.get("id"),
                    "reason": check.reason,
                }
                duplicates.append(rec)
                is_dup = True
                break
        if not is_dup:
            unique.append(rec)

    return unique, duplicates


# ---------------------------------------------------------------------------
# Matching accuracy validation
# ---------------------------------------------------------------------------

async def validate_matching_accuracy(
    db: AsyncSession,
    *,
    sample_size: int = 100,
) -> MatchValidationResult:
    """Validate the accuracy of subcontractor matching for recent external records.

    Returns a summary of match counts by method and confidence scores.
    """
    result = MatchValidationResult()

    # Count total OSHA violations with match info
    res = await db.execute(
        text(
            """SELECT
                COUNT(*) as total,
                COUNT(subcontractor_id) as matched,
                COUNT(*) - COUNT(subcontractor_id) as unmatched,
                COUNT(CASE WHEN is_duplicate = TRUE THEN 1 END) as duplicates,
                COUNT(CASE WHEN match_method = 'ein' THEN 1 END) as by_ein,
                COUNT(CASE WHEN match_method = 'license' THEN 1 END) as by_license,
                COUNT(CASE WHEN match_method = 'name' THEN 1 END) as by_name,
                COUNT(CASE WHEN match_method = 'none' OR match_method IS NULL THEN 1 END) as by_none,
                AVG(COALESCE(match_confidence, 0)) as avg_confidence
            FROM violations
            WHERE is_osha_violation = TRUE
            AND created_at > NOW() - INTERVAL '7 days'
            LIMIT :sample_size
            """
        ),
        {"sample_size": sample_size},
    )
    row = res.fetchone()
    if row:
        result.total_records = row[0] or 0
        result.matched_records = row[1] or 0
        result.unmatched_records = row[2] or 0
        result.duplicate_records = row[3] or 0
        result.match_by_ein = row[4] or 0
        result.match_by_license = row[5] or 0
        result.match_by_name = row[6] or 0
        result.match_by_none = row[7] or 0
        result.average_confidence = float(row[8] or 0.0)

    # Count state credential matches
    res2 = await db.execute(
        text(
            """SELECT
                COUNT(*) as total,
                COUNT(subcontractor_id) as matched,
                COUNT(*) - COUNT(subcontractor_id) as unmatched
            FROM state_credential_records
            WHERE created_at > NOW() - INTERVAL '7 days'
            LIMIT :sample_size
            """
        ),
        {"sample_size": sample_size},
    )
    row2 = res2.fetchone()
    if row2:
        # Aggregate into totals
        result.total_records += row2[0] or 0
        result.matched_records += row2[1] or 0
        result.unmatched_records += row2[2] or 0

    # Validate thresholds
    if result.total_records > 0:
        match_rate = result.matched_records / result.total_records
        if match_rate < 0.70:
            result.failure_reasons.append(
                f"Match rate {match_rate:.2%} below 70% threshold"
            )
        if result.duplicate_records > result.total_records * 0.05:
            result.failure_reasons.append(
                f"Duplicate rate {result.duplicate_records / result.total_records:.2%} above 5% threshold"
            )

    return result


async def validate_deduplication(
    db: AsyncSession,
    *,
    table: str = "violations",
    key_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Check for duplicate records in a given table."""
    if key_columns is None:
        key_columns = ["osha_violation_id"] if table == "violations" else ["state_code", "credential_number", "credential_type"]

    # Check for duplicates by key columns
    key_expr = ", ".join(key_columns)
    query = text(
        f"""SELECT {key_expr}, COUNT(*) as cnt
        FROM {table}
        WHERE {' AND '.join(f'{col} IS NOT NULL' for col in key_columns)}
        GROUP BY {key_expr}
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 100
        """
    )
    result = await db.execute(query)
    duplicates = result.fetchall()

    return {
        "table": table,
        "key_columns": key_columns,
        "duplicate_groups": len(duplicates),
        "total_duplicate_records": sum(r[-1] for r in duplicates) if duplicates else 0,
        "top_duplicates": [
            dict(zip(key_columns + ["count"], row)) for row in duplicates[:10]
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_iso_date(value: Any) -> Optional[date]:
    """Parse ISO date string to date object."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except (ValueError, TypeError):
        return None
