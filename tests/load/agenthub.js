// AgentHub load test (k6).
//
//   AGENTHUB_URL=http://localhost:8080 AGENTHUB_EMAIL=... AGENTHUB_PASSWORD=... \
//     k6 run tests/load/agenthub.js
//
// Credentials come from the environment, never from arguments. CI creates a
// throwaway account with a random password for each run (see ci.yml, job
// "images").
//
// What it models: signed-in people browsing - the dashboard's reads, agent and
// execution lists, the marketplace, status - through the real edge (Caddy) to
// the API and PostgreSQL. Writes are kept to setup: the per-session write
// limit (WRITE_REQUESTS_PER_MINUTE) exists to stop exactly the kind of burst a
// load test would otherwise produce.
//
// What it does not model: runs executing (there is no worker in the CI stack,
// and runs are bounded by model and sandbox time, not by the API), SSE streams
// held open, or many distinct accounts. See docs/PERFORMANCE.md.

import http from 'k6/http';
import { check, fail, group, sleep } from 'k6';

const BASE = (__ENV.AGENTHUB_URL || 'http://localhost:8080').replace(/\/$/, '');
const API = `${BASE}/api/v1`;

export const options = {
  scenarios: {
    browse: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 25 },
        { duration: '2m', target: 25 },
        { duration: '15s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  // The budget a release must meet. CI fails the build when it does not.
  thresholds: {
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
    'http_req_duration{kind:read}': ['p(95)<500', 'p(99)<1500'],
    'http_req_duration{kind:health}': ['p(95)<200'],
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

const CAPABILITIES = [
  'web_access',
  'api_access',
  'file_access',
  'database_access',
  'tool_calling',
  'code_execution',
  'email_send',
];

function agentDraft(index) {
  return {
    name: `Load Test Agent ${index}`,
    description: 'Created by the k6 load test so lists have something to return.',
    category: 'research',
    tags: ['load-test'],
    version: '1.0.0',
    model: { provider: 'Model gateway', model: 'fast-small', temperature: 0.2, maxOutputTokens: 1024 },
    tools: [],
    permissions: CAPABILITIES.map((capability) => ({
      capability,
      level: 'denied',
      requiresApproval: false,
      scope: '',
    })),
    resourceLimits: { maxRuntimeSeconds: 60, maxMemoryMb: 256, maxTokensPerRun: 10000, maxToolCalls: 5 },
    securityPolicy: {
      sandbox: 'strict',
      networkEgress: 'none',
      allowedDomains: [],
      approvalRequiredFor: ['high', 'critical'],
      auditLogging: true,
    },
  };
}

export function setup() {
  const email = __ENV.AGENTHUB_EMAIL;
  const password = __ENV.AGENTHUB_PASSWORD;
  if (!email || !password) fail('AGENTHUB_EMAIL and AGENTHUB_PASSWORD must be set');

  const login = http.post(`${API}/auth/login`, JSON.stringify({ email, password }), {
    headers: { 'Content-Type': 'application/json' },
    tags: { kind: 'login' },
  });
  if (login.status !== 200) fail(`sign-in failed with ${login.status}`);

  const session = login.cookies.agenthub_session && login.cookies.agenthub_session[0].value;
  const csrf = login.cookies.agenthub_csrf && login.cookies.agenthub_csrf[0].value;
  if (!session || !csrf) fail('sign-in did not set the session and CSRF cookies');

  // Cookies are sent explicitly: the server marks them Secure, and the CI
  // stack is plain http on localhost.
  const auth = {
    Cookie: `agenthub_session=${session}; agenthub_csrf=${csrf}`,
    'X-CSRF-Token': csrf,
    'Content-Type': 'application/json',
  };
  for (let index = 1; index <= 10; index += 1) {
    const created = http.post(`${API}/agents`, JSON.stringify(agentDraft(index)), {
      headers: auth,
      tags: { kind: 'setup' },
    });
    // 409: an earlier run on the same database already created it.
    if (created.status !== 201 && created.status !== 409) {
      fail(`creating a test agent failed with ${created.status}: ${created.body}`);
    }
  }
  return { cookie: auth.Cookie };
}

export default function (data) {
  const read = { headers: { Cookie: data.cookie }, tags: { kind: 'read' } };

  group('health', () => {
    const response = http.get(`${API}/health`, { tags: { kind: 'health' } });
    check(response, { 'health is 200': (r) => r.status === 200 });
  });

  group('dashboard', () => {
    const responses = http.batch([
      ['GET', `${API}/auth/session`, null, read],
      ['GET', `${API}/agents?limit=50`, null, read],
      ['GET', `${API}/executions?limit=50`, null, read],
      ['GET', `${API}/system/status`, null, read],
      ['GET', `${API}/alerts?state=firing`, null, read],
    ]);
    for (const response of responses) {
      check(response, { 'dashboard read is 200': (r) => r.status === 200 });
    }
  });

  group('browse', () => {
    const responses = http.batch([
      ['GET', `${API}/agents?search=load&sort=name_asc`, null, read],
      ['GET', `${API}/marketplace`, null, read],
      ['GET', `${API}/security/overview`, null, read],
      ['GET', `${API}/analytics/summary?days=14`, null, read],
    ]);
    for (const response of responses) {
      check(response, { 'browse read is 200': (r) => r.status === 200 });
    }
  });

  // A person reads for a while between pages.
  sleep(1 + Math.random() * 2);
}
