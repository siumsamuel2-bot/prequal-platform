#!/usr/bin/env python3
"""Admin bulk-resolve for stranded Paperclip recovery actions.

The Paperclip control plane (npm package ``paperclipai``) exposes no
recovery-action API routes, and versions since 2026.403.0 no longer contain
the recovery/watchdog code that owned ``issue_recovery_actions``. Active
recovery actions whose source issues already reached a terminal state
(``done`` / ``cancelled``) are stale orphans: they can never be picked up by
an owner and keep review state permanently stranded.

This tool bulk-resolves them in ONE atomic SQL operation using the control
plane's own stale-sweep semantics (status/outcome = ``cancelled`` plus a
resolution note). Recovery actions linked to live issues (``todo``,
``in_progress``, ``in_review``) are never touched.

Run with:
    python resolve_stranded_recoveries.py              # dry-run (default)
    python resolve_stranded_recoveries.py --execute    # apply the bulk resolve

Environment:
    PAPERCLIP_DB_URL:      Control-plane PostgreSQL URL
                           (default: postgres://paperclip:paperclip@127.0.0.1:54329/paperclip)
    PAPERCLIP_COMPANY_ID:  Company scope for the bulk resolve (optional; all
                           companies are processed when unset)
"""
import argparse
import json
import logging
import os
from datetime import datetime, timezone

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = "postgres://paperclip:paperclip@127.0.0.1:54329/paperclip"

TERMINAL_ISSUE_STATUSES = ("done", "cancelled")

RESOLUTION_NOTE = (
    "Bulk-resolved by admin: recovery action became stale because the source "
    "issue reached a terminal state (done/cancelled)."
)

# One atomic operation: resolve every active recovery action whose source
# issue is in a terminal state. Live-source rows are structurally excluded.
BULK_RESOLVE_SQL = """
UPDATE issue_recovery_actions ra
SET status = 'cancelled',
    outcome = 'cancelled',
    resolution_note = %s,
    resolved_at = NOW(),
    updated_at = NOW()
WHERE ra.status = 'active'
  AND (%s::uuid IS NULL OR ra.company_id = %s::uuid)
  AND EXISTS (
    SELECT 1
    FROM issues i
    WHERE i.id = ra.source_issue_id
      AND i.status IN %s
  )
"""


def summarize_active(cur, company_id):
    """Breakdown of active recovery actions by kind, cause, and source issue status."""
    if company_id:
        cur.execute(
            """
            SELECT ra.kind, ra.cause, i.status, COUNT(*)
            FROM issue_recovery_actions ra
            LEFT JOIN issues i ON i.id = ra.source_issue_id
            WHERE ra.status = 'active'
              AND ra.company_id = %s
            GROUP BY ra.kind, ra.cause, i.status
            ORDER BY COUNT(*) DESC
            """,
            (company_id,),
        )
    else:
        cur.execute(
            """
            SELECT ra.kind, ra.cause, i.status, COUNT(*)
            FROM issue_recovery_actions ra
            LEFT JOIN issues i ON i.id = ra.source_issue_id
            WHERE ra.status = 'active'
            GROUP BY ra.kind, ra.cause, i.status
            ORDER BY COUNT(*) DESC
            """
        )
    rows = []
    for kind, cause, issue_status, count in cur.fetchall():
        rows.append({"kind": kind, "cause": cause, "source_issue_status": issue_status, "count": count})
    return rows


def resolve_stranded(db_url, company_id=None, execute=False):
    """Bulk-resolve stranded recovery actions. Returns a summary dict."""
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM issue_recovery_actions WHERE status = 'active'")
        active_total = cur.fetchone()[0]

        breakdown = summarize_active(cur, company_id)
        stale_total = sum(b["count"] for b in breakdown if b["source_issue_status"] in TERMINAL_ISSUE_STATUSES)
        live_total = sum(b["count"] for b in breakdown if b["source_issue_status"] not in TERMINAL_ISSUE_STATUSES)

        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execute": execute,
            "company_id": company_id,
            "active_total": active_total,
            "stale_resolvable": stale_total,
            "live_preserved": live_total,
            "breakdown": breakdown,
            "resolved": 0,
        }

        if not execute:
            logger.info("Dry run: %d stale recovery actions would be resolved, %d live preserved",
                        stale_total, live_total)
            return result

        cur.execute(
            BULK_RESOLVE_SQL,
            (RESOLUTION_NOTE, company_id, company_id, TERMINAL_ISSUE_STATUSES),
        )
        resolved = cur.rowcount
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM issue_recovery_actions WHERE status = 'active'")
        remaining_active = cur.fetchone()[0]

        result["resolved"] = resolved
        result["remaining_active"] = remaining_active
        logger.info("Bulk-resolved %d stranded recovery actions; %d active remain", resolved, remaining_active)
        return result
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Admin bulk-resolve for stranded recovery actions")
    parser.add_argument("--execute", action="store_true",
                        help="Apply the bulk resolve (default: dry-run)")
    parser.add_argument("--db-url", default=os.environ.get("PAPERCLIP_DB_URL", DEFAULT_DB_URL),
                        help="Control-plane PostgreSQL URL")
    parser.add_argument("--company-id", default=os.environ.get("PAPERCLIP_COMPANY_ID"),
                        help="Company scope (default: PAPERCLIP_COMPANY_ID or all companies)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    args = parser.parse_args()

    company_id = (args.company_id or "").strip() or None
    result = resolve_stranded(args.db_url, company_id=company_id, execute=args.execute)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    print("\n" + "=" * 60)
    print("STRANDED RECOVERY ACTIONS BULK-RESOLVE")
    print("=" * 60)
    print(f"Timestamp: {result['timestamp']}")
    print(f"Mode: {'EXECUTE' if result['execute'] else 'DRY-RUN'}")
    print(f"Company scope: {result['company_id'] or 'all'}")
    print(f"Active recovery actions: {result['active_total']}")
    print(f"Stale (resolvable): {result['stale_resolvable']}")
    print(f"Live (preserved): {result['live_preserved']}")
    if result["execute"]:
        print(f"Resolved: {result['resolved']}")
        print(f"Remaining active: {result.get('remaining_active')}")
    else:
        print("\nDry run only - re-run with --execute to apply.")

    print("\nBreakdown (kind | cause | source issue status | count):")
    for b in result["breakdown"]:
        print(f"  {b['kind']} | {b['cause']} | {b['source_issue_status']} | {b['count']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
