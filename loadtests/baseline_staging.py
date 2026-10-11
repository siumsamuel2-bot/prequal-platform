"""Baseline staging load harness for MID-625 (stdlib only, no k6/locust needed).

Respects the platform's rate-limit policies (see
app/middleware/rate_limit.py) and session-rotation auth (see
app/routers/auth.py get_current_user):

- One registered user per VU; register paced >= 4.5s apart (limit 20/min/IP).
- Login paced >= 8.5s apart (limit 10/min/IP), serialized globally.
- Every authenticated request rotates the session: the harness chains the
  X-New-Access-Token response header into the next request per VU. Tokens are
  never shared across VUs and requests within a VU are strictly sequential.
- Authenticated reads stay <= ~80 req/min per user (limit 200/min per user).
- Aggregate traffic stays <= ~650 req/min from the runner IP (DDoS sustained
  protection is 1000/min per IP); burst stays far below 100/s.
- /api/health is rate-limit exempt (EXEMPT_PATHS).

Profile (Render free tier sized - single small instance, so gentler than the
k6 ECS profile in k6-analytics.js):

    warm-up          : GET /health until 200 (cold-start tolerant)
    setup            : register + login 8 users
    phase 1 baseline : 3 VUs, 120s, think 1-2s
    phase 2 sustained: 8 VUs, 180s, think 1-2s
    phase 3 peak     : 8 VUs, 60s, think 0.5-1s

Usage:

    python loadtests/baseline_staging.py --base-url https://prequal-staging-api.onrender.com

Outputs per-endpoint percentiles and threshold verdicts
(p95 < 2000 ms, error rate < 1%) and writes loadtests/baseline_results_<ts>.csv.
"""

import argparse
import csv
import json
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict

DEFAULT_BASE = "https://prequal-staging-api.onrender.com"
PASSWORD = "Loadtest!12345"

# (vus, seconds, think_min, think_max, label)
PHASES = [
    (3, 120, 1.0, 2.0, "baseline"),
    (8, 180, 1.0, 2.0, "sustained"),
    (8, 60, 0.5, 1.0, "peak"),
]
NUM_USERS = 8
REGISTER_SPACING = 4.5   # limit: 20/min/IP
LOGIN_SPACING = 8.5      # limit: 10/min/IP

ENDPOINTS = [
    ("health", "/health", 1, False),              # root /health is in EXEMPT_PATHS
    ("summary", "/api/analytics/summary", 4, True),
    ("compliance", "/api/analytics/compliance/summary", 3, True),
]
WEIGHTED = [name for name, _, w, _ in ENDPOINTS for _ in range(w)]

REQUEST_TIMEOUT = 45

# Latest live token per user slot. Sessions rotate on every request
# (X-New-Access-Token); phase threads must resume from the newest token,
# never the original setup token, or the first request of each phase 401s.
user_tokens = {}
user_tokens_lock = threading.Lock()


class Paced:
    """Serialize mutating calls (register/login) with a minimum interval."""

    def __init__(self, min_interval):
        self.lock = threading.Lock()
        self.next_ok = 0.0
        self.min_interval = min_interval

    def wait(self):
        while True:
            with self.lock:
                now = time.monotonic()
                if now >= self.next_ok:
                    self.next_ok = time.monotonic() + self.min_interval
                    return
                delay = self.next_ok - now
            time.sleep(delay)


register_gate = Paced(REGISTER_SPACING)
login_gate = Paced(LOGIN_SPACING)

records = []
records_lock = threading.Lock()
relogin_lock = threading.Lock()
last_login = [0.0]


def http(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "mid625-baseline/1.0")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace"), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")[:500], (time.perf_counter() - t0) * 1000
    except Exception as e:
        return None, {}, f"{type(e).__name__}: {e}", (time.perf_counter() - t0) * 1000


def record(phase, name, status, ms):
    with records_lock:
        records.append((time.time(), phase, name, status, ms))


def warm_up(base):
    print("== warm-up (cold start tolerant) ==", flush=True)
    for attempt in range(6):
        status, _, _, ms = http("GET", base + "/health")
        record("warmup", "health", status, ms)
        print(f"  attempt {attempt + 1}: GET /health -> {status} ({ms:.0f} ms)", flush=True)
        if status == 200:
            return True
        time.sleep(10)
    return False


def setup_users(base, n):
    users = []
    stamp = str(int(time.time()))
    print(f"== setup: register {n} users ({REGISTER_SPACING}s spacing) ==", flush=True)
    for i in range(n):
        email = f"loadtest-{stamp}-{i}@example.com"
        register_gate.wait()
        status, _, _, ms = http("POST", base + "/api/auth/register",
                                {"email": email, "name": f"loadtest {i}", "password": PASSWORD})
        record("setup", "register", status, ms)
        print(f"  register {email} -> {status} ({ms:.0f} ms)", flush=True)
        users.append({"email": email, "slot": i})
    print(f"== setup: login {n} users ({LOGIN_SPACING}s spacing) ==", flush=True)
    for u in users:
        login_gate.wait()
        status, headers, body, ms = http("POST", base + "/api/auth/login",
                                         {"username": u["email"], "password": PASSWORD})
        record("setup", "login", status, ms)
        token = None
        if status == 200:
            try:
                token = json.loads(body).get("access_token")
            except Exception:
                pass
        if token:
            set_token(u["slot"], token)
        print(f"  login {u['email']} -> {status} token={'ok' if token else 'MISSING'} ({ms:.0f} ms)", flush=True)
    return [u for u in users if get_token(u["slot"])]


def pick_endpoint():
    return random.choice(WEIGHTED)


def header(headers, name):
    """Case-insensitive header lookup (uvicorn sends lowercase names)."""
    if not headers:
        return None
    lname = name.lower()
    for k, v in headers.items():
        if k.lower() == lname:
            return v
    return None


def set_token(user_slot, token):
    if token:
        with user_tokens_lock:
            user_tokens[user_slot] = token


def get_token(user_slot):
    with user_tokens_lock:
        return user_tokens.get(user_slot)


def vu_worker(base, user, user_slot, phase_label, seconds, think_min, think_max, stop_at):
    name_by_ep = {name: (path, needs_auth) for name, path, _, needs_auth in ENDPOINTS}
    email = user["email"]
    token = get_token(user_slot)
    while time.monotonic() < stop_at:
        ep = pick_endpoint()
        path, needs_auth = name_by_ep[ep]
        headers = {"Authorization": f"Bearer {token}"} if needs_auth and token else {}
        status, headers_out, _, ms = http("GET", base + path, headers=headers)
        record(phase_label, ep, status, ms)
        new_token = header(headers_out, "X-New-Access-Token")
        if new_token:
            token = new_token
            set_token(user_slot, token)
        if status == 401 and needs_auth:
            # session chain broken (e.g. rotation race): re-login, globally paced
            with relogin_lock:
                wait = last_login[0] + LOGIN_SPACING - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                status2, _, body2, _ = http("POST", base + "/api/auth/login",
                                            {"username": email, "password": PASSWORD})
                last_login[0] = time.monotonic()
                if status2 == 200:
                    try:
                        token = json.loads(body2).get("access_token") or token
                        set_token(user_slot, token)
                    except Exception:
                        pass
        elif status == 429:
            retry_after = header(headers_out, "Retry-After")
            try:
                time.sleep(min(float(retry_after), 10.0))
            except (TypeError, ValueError):
                time.sleep(5.0)
        time.sleep(random.uniform(think_min, think_max))


def pct(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(round((p / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[idx]


def summarize(phase_filter=None):
    per = defaultdict(list)
    per_err = defaultdict(int)
    errs = 0
    total = 0
    with records_lock:
        rows = list(records)
    for _, phase, name, status, ms in rows:
        if phase_filter and phase not in phase_filter:
            continue
        if name in ("register", "login", "health") and phase in ("warmup", "setup"):
            continue  # setup noise excluded from the load baseline
        total += 1
        per[name].append(ms)
        if status is None or status >= 400:
            errs += 1
            per_err[name] += 1
    lines = []
    agg = []
    for name in sorted(per):
        vals = sorted(per[name])
        agg.extend(vals)
        lines.append(
            f"  {name:<12} n={len(vals):<5} err={per_err.get(name, 0)}  p50={pct(vals, 50):7.0f}  p90={pct(vals, 90):7.0f}  p95={pct(vals, 95):7.0f}  p99={pct(vals, 99):7.0f}  max={vals[-1]:7.0f} ms"
        )
    err_rate = (errs / total * 100.0) if total else 0.0
    return total, errs, err_rate, sorted(agg), lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    random.seed(20261011)

    if not warm_up(base):
        print("FATAL: staging API never returned healthy /health", flush=True)
        sys.exit(2)

    users = setup_users(base, NUM_USERS)
    if not users:
        print("FATAL: no users logged in; cannot run authed load", flush=True)
        sys.exit(2)
    print(f"ready: {len(users)}/{NUM_USERS} users authenticated\n", flush=True)

    load_start = time.monotonic()
    for vus, seconds, tmin, tmax, label in PHASES:
        stop_at = time.monotonic() + seconds
        threads = []
        for i in range(vus):
            u = users[i]
            t = threading.Thread(target=vu_worker,
                                 args=(base, u, u["slot"], label, seconds, tmin, tmax, stop_at),
                                 daemon=True)
            threads.append(t)
        for t in threads:
            t.start()
        print(f"== phase '{label}': {vus} VUs for {seconds}s (think {tmin}-{tmax}s) ==", flush=True)
        for t in threads:
            t.join()
        total, errs, err_rate, agg, lines = summarize()
        dur = time.monotonic() - load_start
        print(f"  running totals: {total} reqs, {errs} errors ({err_rate:.2f}%), "
              f"{total / dur:.2f} req/s avg", flush=True)

    wall = time.monotonic() - load_start
    total, errs, err_rate, agg, lines = summarize()
    p50, p90, p95, p99 = pct(agg, 50), pct(agg, 90), pct(agg, 95), pct(agg, 99)

    print("\n================ BASELINE RESULTS (load phases only) ================", flush=True)
    print(f"base_url : {base}", flush=True)
    print(f"duration : {wall:.0f}s across {len(PHASES)} phases", flush=True)
    print(f"requests : {total}   errors: {errs}   error rate: {err_rate:.2f}%", flush=True)
    print(f"throughput: {total / wall:.2f} req/s ({total / wall * 60:.0f} req/min)", flush=True)
    print(f"latency  : p50={p50:.0f}  p90={p90:.0f}  p95={p95:.0f}  p99={p99:.0f}  max={agg[-1] if agg else 0:.0f} ms", flush=True)
    print("per-endpoint:", flush=True)
    for line in lines:
        print(line, flush=True)
    print(f"threshold p95 < 2000 ms   : {'PASS' if p95 < 2000 else 'FAIL'} ({p95:.0f} ms)", flush=True)
    print(f"threshold error rate < 1% : {'PASS' if err_rate < 1 else 'FAIL'} ({err_rate:.2f}%)", flush=True)

    out = f"loadtests/baseline_results_{int(time.time())}.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "phase", "endpoint", "status", "latency_ms"])
        with records_lock:
            for row in records:
                w.writerow(row)
    print(f"raw data  : {out}", flush=True)


if __name__ == "__main__":
    main()
