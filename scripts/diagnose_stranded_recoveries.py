#!/usr/bin/env python3
"""Diagnose stranded assigned issue recoveries in Paperclip.

This script queries the Paperclip API to identify issues that may be stranded
(checked out by ghost agents that never completed) or have missing dispositions.

Run with:
    python diagnose_stranded_recoveries.py [--dry-run] [--api-url URL] [--api-key KEY]

Environment:
    PAPERCLIP_API_URL: Base URL for the Paperclip API (default: http://127.0.0.1:3100)
    PAPERCLIP_API_KEY: API key for authentication
"""
import argparse
import json
import logging
import os
import sys
import requests
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PaperclipApiClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        url = f"{self._base_url}{path}"
        resp = requests.get(url, headers=self._headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, data: dict) -> dict:
        url = f"{self._base_url}{path}"
        resp = requests.post(url, headers=self._headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()


def diagnose_stranded_issues(api_url: str, api_key: str, dry_run: bool = True) -> dict:
    """Diagnose issues with potential stranding or missing dispositions.

    Returns a summary of issues that may need manual resolution.
    """
    client = PaperclipApiClient(api_url, api_key)

    result = {
        "dry_run": dry_run,
        "timestamp": datetime.utcnow().isoformat(),
        "issues_needing_disposition": [],
        "issues_with_failed_recovery": [],
        "stranded_issues": [],
        "summary": {}
    }

    try:
        issues = client.get("/api/issues", params={"status": "blocked", "limit": 200})
    except Exception as exc:
        logger.error("Failed to fetch blocked issues: %s", exc)
        result["error"] = str(exc)
        return result

    blocked_issues = issues.get("items", [])
    logger.info("Found %d blocked issues", len(blocked_issues))

    for issue in blocked_issues:
        issue_id = issue.get("id")
        title = issue.get("title", "")
        assignee = issue.get("assignee", {})
        assignee_name = assignee.get("name", "unknown") if assignee else "unassigned"

        meta = issue.get("meta", {})

        if meta.get("recoveryFailure"):
            result["issues_with_failed_recovery"].append({
                "id": issue_id,
                "title": title[:80],
                "assignee": assignee_name,
                "failure_reason": meta.get("recoveryFailure")
            })

        if meta.get("strandedAssignedIssue"):
            result["stranded_issues"].append({
                "id": issue_id,
                "title": title[:80],
                "assignee": assignee_name
            })

        disposition = meta.get("disposition")
        if not disposition and "review" in title.lower():
            result["issues_needing_disposition"].append({
                "id": issue_id,
                "title": title[:80],
                "assignee": assignee_name,
                "suggested_resolution": "missing_disposition"
            })

    result["summary"] = {
        "total_blocked": len(blocked_issues),
        "needs_disposition": len(result["issues_needing_disposition"]),
        "has_failed_recovery": len(result["issues_with_failed_recovery"]),
        "stranded_count": len(result["stranded_issues"])
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose stranded assigned issue recoveries"
    )
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Only report findings without taking action (default: True)")
    parser.add_argument("--api-url", default=os.environ.get("PAPERCLIP_API_URL", "http://127.0.0.1:3100"),
                        help="Paperclip API URL")
    parser.add_argument("--api-key", default=os.environ.get("PAPERCLIP_API_KEY", ""),
                        help="Paperclip API key")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.api_key:
        logger.error("PAPERCLIP_API_KEY not set. Use --api-key or set PAPERCLIP_API_KEY env var.")
        sys.exit(1)

    logger.info("Starting stranded issue diagnosis...")
    result = diagnose_stranded_issues(args.api_url, args.api_key, dry_run=args.dry_run)

    print("\n" + "="*60)
    print("STRANDED ISSUE DIAGNOSIS REPORT")
    print("="*60)
    print(f"Timestamp: {result['timestamp']}")
    print(f"Dry run: {result['dry_run']}")

    if "error" in result:
        print(f"\nERROR: {result['error']}")
        sys.exit(1)

    summary = result["summary"]
    print(f"\nSummary:")
    print(f"  Total blocked issues: {summary.get('total_blocked', 0)}")
    print(f"  Needs disposition: {summary.get('needs_disposition', 0)}")
    print(f"  Failed recovery: {summary.get('has_failed_recovery', 0)}")
    print(f"  Stranded: {summary.get('stranded_count', 0)}")

    if result["issues_needing_disposition"]:
        print(f"\nIssues needing disposition ({len(result['issues_needing_disposition'])}):")
        for issue in result["issues_needing_disposition"][:10]:
            print(f"  - {issue['id']}: {issue['title']} (assignee: {issue['assignee']})")
        if len(result["issues_needing_disposition"]) > 10:
            print(f"  ... and {len(result['issues_needing_disposition']) - 10} more")

    if result["issues_with_failed_recovery"]:
        print(f"\nIssues with failed recovery ({len(result['issues_with_failed_recovery'])}):")
        for issue in result["issues_with_failed_recovery"][:10]:
            print(f"  - {issue['id']}: {issue['title']}")
            print(f"    Reason: {issue['failure_reason']}")
        if len(result["issues_with_failed_recovery"]) > 10:
            print(f"  ... and {len(result['issues_with_failed_recovery']) - 10} more")

    if result["stranded_issues"]:
        print(f"\nStranded issues ({len(result['stranded_issues'])}):")
        for issue in result["stranded_issues"][:10]:
            print(f"  - {issue['id']}: {issue['title']} (assignee: {issue['assignee']})")
        if len(result["stranded_issues"]) > 10:
            print(f"  ... and {len(result['stranded_issues']) - 10} more")

    print("\n" + "="*60)
    print("Resolution guide:")
    print("  1. missing_disposition: Record a valid issue disposition")
    print("  2. stranded_assigned_issue: Record an intentional manual resolution")
    print("="*60)

    logger.info("Diagnosis complete")


if __name__ == "__main__":
    main()