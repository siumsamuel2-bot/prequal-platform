#!/usr/bin/env python3
"""Generate Keep-a-Changelog release notes from merged GitHub PRs.

Collects merged PRs since the previous tag, groups them by label into
Keep-a-Changelog sections (Added / Changed / Fixed / Security), and either
prints the section or prepends it to a CHANGELOG.md.

Stdlib only (urllib) so it runs in CI and locally with no dependencies.

Usage (CI, inside the generate-changelog job on a v* tag):

    python3 scripts/release_notes.py \\
        --tag "$GITHUB_REF_NAME" --repo "$GITHUB_REPOSITORY" \\
        --prepend prequal-platform/CHANGELOG.md

Usage (local one-command regeneration):

    python3 scripts/release_notes.py --tag v1.2.0 \\
        --repo <owner>/<repo> --prepend prequal-platform/CHANGELOG.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request

# Label (lowercase) -> Keep-a-Changelog section. Anything unmatched -> Changed.
LABEL_SECTIONS = {
    "feature": "Added",
    "enhancement": "Added",
    "feat": "Added",
    "bug": "Fixed",
    "fix": "Fixed",
    "security": "Security",
}
SECTION_ORDER = ["Added", "Changed", "Fixed", "Security"]


def _request(url: str, token: str | None) -> list | dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def previous_tag(tag: str) -> str | None:
    """Return the tag immediately before ``tag`` (by tag date), or None."""
    try:
        out = subprocess.run(
            ["git", "tag", "--sort=-creatordate"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    if tag in out:
        idx = out.index(tag)
        if idx + 1 < len(out):
            return out[idx + 1]
    return None


def tag_date(tag: str) -> dt.datetime | None:
    """Commit date (UTC) the tag points at, from git; None if unavailable."""
    try:
        out = subprocess.run(
            ["git", "show", "-s", "--format=%cI", tag],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return dt.datetime.fromisoformat(out).astimezone(dt.timezone.utc)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def merged_prs(repo: str, since: dt.datetime, until: dt.datetime | None,
               token: str | None) -> list[dict]:
    """Merged PRs with since < merged_at <= until (until None = now)."""
    prs: list[dict] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{repo}/pulls"
            f"?state=closed&sort=updated&direction=desc&per_page=100&page={page}"
        )
        batch = _request(url, token)
        if not batch:
            break
        for pr in batch:
            merged = pr.get("merged_at")
            if not merged:
                continue
            merged_dt = dt.datetime.fromisoformat(
                merged.replace("Z", "+00:00"))
            if merged_dt <= since:
                return prs
            if until is None or merged_dt <= until:
                prs.append(pr)
        if len(batch) < 100:
            break
        page += 1
        if page > 30:  # safety valve
            break
    return prs


def section_for(pr: dict) -> str:
    for label in pr.get("labels", []):
        name = str(label.get("name", "")).strip().lower()
        if name in LABEL_SECTIONS:
            return LABEL_SECTIONS[name]
    return "Changed"


def render(tag: str, date: dt.datetime, prs: list[dict],
           prev: str | None, repo: str) -> str:
    grouped: dict[str, list[str]] = {}
    for pr in sorted(prs, key=lambda p: p.get("number") or 0):
        title = str(pr.get("title", "")).strip()
        grouped.setdefault(section_for(pr), []).append(
            f"- {title} (#{pr['number']})")

    lines = [f"## [{tag}] - {date.date().isoformat()}", ""]
    for section in SECTION_ORDER:
        if grouped.get(section):
            lines.append(f"### {section}")
            lines.extend(grouped[section])
            lines.append("")
    if prev and repo:
        lines.append(
            f"**Full changelog:** "
            f"https://github.com/{repo}/compare/{prev}...{tag}")
        lines.append("")
    return "\n".join(lines)


def prepend(changelog_path: str, block: str, tag: str) -> bool:
    """Insert ``block`` after the [Unreleased] section. Returns True if written."""
    with open(changelog_path, encoding="utf-8") as f:
        content = f.read()
    if f"[{tag}]" in content:
        print(f"release_notes: {changelog_path} already contains [{tag}]; "
              "nothing to do")
        return False
    lines = content.splitlines(keepends=True)
    insert_at = None
    if "## [Unreleased]" in content:
        start = next(i for i, l in enumerate(lines) if "## [Unreleased]" in l)
        insert_at = start + 1
        while insert_at < len(lines) and not lines[insert_at].startswith("## "):
            insert_at += 1
    else:
        for i, line in enumerate(lines):
            if line.startswith("## "):
                insert_at = i
                break
    block_lines = block.splitlines(keepends=True)
    if block_lines and not block_lines[-1].endswith("\n"):
        block_lines[-1] += "\n"
    out = "".join(lines[:insert_at] + ["\n"] + block_lines + lines[insert_at:]) \
        if insert_at is not None else content.rstrip("\n") + "\n\n" + block
    with open(changelog_path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="release tag, e.g. v1.2.0")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"),
                        help="owner/name (default $GITHUB_REPOSITORY)")
    parser.add_argument("--since", default=None,
                        help="ref or ISO date to collect PRs from "
                             "(default: the tag before --tag)")
    parser.add_argument("--prepend", default=None,
                        help="CHANGELOG.md path to prepend the section into")
    parser.add_argument("--token", default=None,
                        help="GitHub token (default $GITHUB_TOKEN)")
    args = parser.parse_args(argv)

    if not args.repo:
        parser.error("--repo is required (or set GITHUB_REPOSITORY)")
    token = args.token or os.environ.get("GITHUB_TOKEN")

    since_dt: dt.datetime | None = None
    if args.since:
        try:
            since_dt = dt.datetime.fromisoformat(
                args.since.replace("Z", "+00:00"))
        except ValueError:
            pass
        if since_dt is None:
            d = tag_date(args.since)
            if d is None:
                parser.error(f"--since {args.since!r} is not an ISO date "
                             "or a resolvable git tag")
            since_dt = d

    prev = previous_tag(args.tag)
    if since_dt is None:
        if prev:
            d = tag_date(prev)
            if d is None:
                parser.error(f"could not resolve date of previous tag {prev!r}; "
                             "pass --since explicitly")
            since_dt = d
        else:
            # No previous tag: take the last 30 days of merged PRs.
            since_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)

    until_dt = tag_date(args.tag)
    prs = merged_prs(args.repo, since_dt, until_dt, token)
    date = until_dt or dt.datetime.now(dt.timezone.utc)
    block = render(args.tag, date, prs, prev, args.repo)

    if args.prepend:
        changed = prepend(args.prepend, block, args.tag)
        print(f"release_notes: {len(prs)} merged PR(s) since "
              f"{prev or since_dt.date().isoformat()}; "
              f"{'wrote' if changed else 'skipped (already present)'} "
              f"[{args.tag}] in {args.prepend}")
    else:
        sys.stdout.write(block)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
