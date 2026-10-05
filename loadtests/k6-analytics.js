// k6 load test for staging Analytics endpoints (MID-625)
// Baseline benchmark for Analytics Service (MID-588) / Analytics Dashboard (MID-592).
//
// Usage:
//   k6 run -e BASE_URL=https://staging.prequal.yourcompany.com loadtests/k6-analytics.js
//
// Thresholds reflect the CloudWatch alarms in terraform (p95 > 2s, 5xx rate).

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'https://staging.prequal.yourcompany.com';

export const options = {
  scenarios: {
    baseline: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 20 },
        { duration: '3m', target: 20 },
        { duration: '1m', target: 50 },
        { duration: '3m', target: 50 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<2000'],
  },
};

const ENDPOINTS = [
  '/analytics/health',
  '/api/v1/analytics/dashboard/summary',
  '/api/v1/analytics/compliance/trends',
];

export default function () {
  for (const path of ENDPOINTS) {
    const res = http.get(`${BASE_URL}${path}`, {
      tags: { name: path },
    });
    check(res, {
      [`${path} status 2xx`]: (r) => res.status >= 200 && res.status < 300,
    });
    sleep(1);
  }
}
