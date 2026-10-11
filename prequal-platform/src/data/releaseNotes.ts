/**
 * Static release notes for the in-app "What's New" surface (MID-669).
 *
 * This module is the app's bundled source of truth for v1 (no backend). It is
 * kept in sync with `prequal-platform/CHANGELOG.md` (Keep a Changelog), which
 * is the human-facing record maintained by the release process.
 *
 * Newest release first. Every entry uses the Keep a Changelog category names.
 */
export type ReleaseCategory = 'Added' | 'Changed' | 'Fixed' | 'Security';

export interface ReleaseChange {
  category: ReleaseCategory;
  items: string[];
}

export interface ReleaseNote {
  version: string;
  date: string;
  title: string;
  summary?: string;
  changes: ReleaseChange[];
}

export const RELEASE_NOTES: ReleaseNote[] = [
  {
    version: '1.1.0',
    date: '2026-10-11',
    title: 'Feedback, support, and a clearer app',
    summary: 'The pilot now has a direct line to us, plus calmer empty states.',
    changes: [
      {
        category: 'Added',
        items: [
          'In-app feedback: rate a page and tell us what to improve without leaving it.',
          'A Support page with the fastest way to reach us and what to expect.',
          "This What's New surface, so you can see what changed since your last visit.",
        ],
      },
      {
        category: 'Changed',
        items: [
          'Analytics and compliance dashboards now show a clear "no access / no data" state instead of a blank or broken-looking screen when your team has no data.',
          'Admin-only analytics panels are hidden for everyone else, so the page stays focused on what you can act on.',
        ],
      },
      {
        category: 'Fixed',
        items: [
          'The backend test suite now runs against PostgreSQL in CI, catching database-specific issues before they reach you.',
        ],
      },
    ],
  },
  {
    version: '1.0.0',
    date: '2026-10-01',
    title: 'Pilot launch',
    summary: 'Subcontractor compliance, out of the spreadsheet and into one place.',
    changes: [
      {
        category: 'Added',
        items: [
          'Track subcontractors, certifications, and violations for every team.',
          'See certification expirations and get alerted before they lapse.',
          'Upload credential documents against a subcontractor.',
          'Compliance dashboards for a quick, honest read on where you stand.',
        ],
      },
      {
        category: 'Security',
        items: [
          'Org/team data isolation enforced on every read.',
          'Multi-factor authentication available for your account.',
        ],
      },
    ],
  },
];

/** The newest release version, or an empty string when there are no notes. */
export const getLatestVersion = (notes: ReleaseNote[] = RELEASE_NOTES): string =>
  notes.length > 0 ? notes[0].version : '';
