#!/usr/bin/env node
const http = require('http');
const fs = require('fs');

const API_URL = process.env.PAPERCLIP_API_URL || 'http://127.0.0.1:3100';
const API_KEY = process.env.PAPERCLIP_API_KEY || '';
const PAPERCLIP_RUN_ID = process.env.PAPERCLIP_RUN_ID || '';
const AGENT_ID = process.env.PAPERCLIP_AGENT_ID || '';
const COMPANY_ID = process.env.PAPERCLIP_COMPANY_ID || '';

function call(method, path, body, extraHeaders = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, API_URL);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      method: method,
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json'
      }
    };
    
    // Always include run ID on mutating calls if available
    if (PAPERCLIP_RUN_ID && (method !== 'GET')) {
      options.headers['X-Paperclip-Run-Id'] = PAPERCLIP_RUN_ID;
    }
    
    for (const [k, v] of Object.entries(extraHeaders)) {
      options.headers[k] = v;
    }

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(data) }); }
        catch (e) { resolve({ status: res.statusCode, body: data }); }
      });
    });

    req.on('error', (e) => reject(e));
    if (body && typeof body === 'object') {
      const json = JSON.stringify(body);
      options.headers['Content-Length'] = Buffer.byteLength(json);
      req.write(json);
    }
    req.end();
  });
}

async function main() {
  const command = process.argv[2];
  
  switch (command) {
    case 'inbox':
      const inbox = await call('GET', '/api/agents/me/inbox-lite');
      console.log(JSON.stringify(inbox.body, null, 2));
      break;
    case 'me':
      const me = await call('GET', '/api/agents/me');
      console.log(JSON.stringify(me.body, null, 2));
      break;
    case 'checkout':
      const issueId = process.argv[3];
      const checkout = await call('POST', `/api/issues/${issueId}/checkout`, {
        agentId: AGENT_ID,
        expectedStatuses: ['todo', 'backlog', 'blocked']
      });
      console.log(JSON.stringify(checkout, null, 2));
      break;
    case 'get-issue':
      const getIssueId = process.argv[3];
      const issue = await call('GET', `/api/issues/${getIssueId}`);
      console.log(JSON.stringify(issue.body, null, 2));
      break;
    case 'comments':
      const commentsIssueId = process.argv[3];
      const comments = await call('GET', `/api/issues/${commentsIssueId}/comments`);
      console.log(JSON.stringify(comments.body, null, 2));
      break;
    case 'context':
      const contextIssueId = process.argv[3];
      const context = await call('GET', `/api/issues/${contextIssueId}/heartbeat-context`);
      console.log(JSON.stringify(context.body, null, 2));
      break;
    case 'comment':
      const commentIssueId = process.argv[3];
      const text = process.argv[4] || '';
      const commentRes = await call('POST', `/api/issues/${commentIssueId}/comments`, { text });
      console.log(JSON.stringify(commentRes, null, 2));
      break;
    case 'patch':
      const patchIssueId = process.argv[3];
      const patchBody = JSON.parse(process.argv[4] || '{}');
      const patch = await call('PATCH', `/api/issues/${patchIssueId}`, patchBody);
      console.log(JSON.stringify(patch, null, 2));
      break;
    case 'full-inbox':
      const fullInbox = await call('GET', `/api/companies/${COMPANY_ID}/issues?assigneeAgentId=${AGENT_ID}&status=todo,in_progress,blocked`);
      console.log(JSON.stringify(fullInbox.body, null, 2));
      break;
    default:
      console.log('Usage: node papercli-api.js <command> [args...]');
      console.log('  me                - Get agent identity');
      console.log('  inbox             - Get inbox-lite assignments');
      console.log('  full-inbox        - Get full issue list');
      console.log('  checkout <id>     - Checkout an issue');
      console.log('  get-issue <id>    - Get an issue (with ancestors)');
      console.log('  comments <id>     - Get issue comments');
      console.log('  context <id>      - Get heartbeat context');
      console.log('  comment <id>     - Single comment (add)');
      console.log('  patch <id>        - PATCH an issue');
  }
}

main().catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});
