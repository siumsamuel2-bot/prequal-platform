"""Burst load test for API rate limiting and DDoS protection (MID-593).

Sends a burst of concurrent requests at a target endpoint and validates that
rate limiting engages (HTTP 429) and that the documented headers are present.

Usage:
    python scripts/load_test_rate_limit.py \
        --url http://localhost:8000/api/analytics/summary \
        --requests 300 --concurrency 50

Exit code is 0 when the protection behaves as expected, 1 otherwise.
"""

import argparse
import asyncio
import sys
from collections import Counter

import httpx


async def _hit(client: httpx.AsyncClient, url: str, headers: dict, results: list) -> None:
    try:
        response = await client.get(url, headers=headers)
        results.append(
            {
                "status": response.status_code,
                "limit": response.headers.get("X-RateLimit-Limit"),
                "remaining": response.headers.get("X-RateLimit-Remaining"),
                "retry_after": response.headers.get("Retry-After"),
            }
        )
    except httpx.HTTPError as exc:
        results.append({"status": "error", "error": str(exc)})


async def run(url: str, total: int, concurrency: int, headers: dict) -> list:
    results: list = []
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def worker():
            async with semaphore:
                await _hit(client, url, headers, results)

        await asyncio.gather(*(worker() for _ in range(total)))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Target endpoint URL")
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--token", default=None, help="Optional bearer token")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}

    results = asyncio.run(run(args.url, args.requests, args.concurrency, headers))

    statuses = Counter(r["status"] for r in results)
    limit_headers = sum(1 for r in results if r.get("limit"))
    retry_headers = sum(1 for r in results if r.get("retry_after"))

    print(f"Requests:      {args.requests} (concurrency={args.concurrency})")
    print(f"Status counts: {dict(statuses)}")
    print(f"X-RateLimit-* present on: {limit_headers} responses")
    print(f"Retry-After present on:   {retry_headers} responses")

    blocked = statuses.get(429, 0)
    error = statuses.get("error", 0)
    ok = statuses.get(200, 0)

    if error:
        print("FAIL: transport errors occurred")
        return 1
    if blocked == 0 and ok == args.requests:
        print("FAIL: no requests were rate limited under burst load")
        return 1
    if blocked and retry_headers == 0:
        print("FAIL: 429 responses did not include Retry-After")
        return 1
    print("PASS: rate limiting engaged and headers were returned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
