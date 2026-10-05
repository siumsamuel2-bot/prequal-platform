import { analyticsTracker } from '../api/client';

export type ExportRow = Record<string, string | number | boolean | null | undefined>;

const escapeCsvCell = (value: string | number | boolean | null | undefined): string => {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (/[",\r\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
};

/**
 * Serializes rows to CSV and triggers a browser download.
 * Used by every analytics dashboard for CSV exports (MID-592).
 */
export function exportRowsToCsv(
  reportType: string,
  filename: string,
  headers: string[],
  rows: ExportRow[],
): void {
  const lines = [
    headers.map(escapeCsvCell).join(','),
    ...rows.map((row) => headers.map((header) => escapeCsvCell(row[header])).join(',')),
  ];
  const blob = new Blob([`\ufeff${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
  analyticsTracker.trackReportExport(reportType, 'csv');
}

/**
 * Prints the analytics dashboards to PDF via the browser print dialog.
 * Print styles (src/components/analytics/AnalyticsPages.css) hide chrome and
 * expand charts so the printed page is a clean report.
 */
export function exportPageToPdf(reportType: string): void {
  window.print();
  analyticsTracker.trackReportExport(reportType, 'pdf');
}
