"""
Rate limiting, DDoS protection, and dynamic limit configuration for the
Prequal Platform API.

RATE LIMIT POLICIES
===================

Default Limits (applied to every public endpoint unless a route rule or
decorator overrides them):

- Authenticated reads (GET/HEAD/OPTIONS): 200 requests/minute per user
- Authenticated writes (POST/PUT/PATCH/DELETE): 50 requests/minute per user
- Authenticated default (fallback): 100 requests/minute per user
- Unauthenticated default: 20 requests/minute per IP address
- Login / token endpoints (unauthenticated): 10 requests/minute per IP
- Registration (unauthenticated): 20 requests/minute per IP
- Unauthenticated reads: 30 requests/minute per IP

DDoS Protection:
- Burst protection: 100 requests/second
- Sustained protection: 1000 requests/minute
- Maximum request body size (default 10 MB) -> HTTP 413
- Maximum query string length / parameter count -> HTTP 400
- Maximum header count -> HTTP 400
- Maximum concurrent in-flight requests per IP -> HTTP 429
- Suspicious request pattern detection (path traversal, SQLi, XSS,
  null bytes, ...) -> HTTP 400 and violation accounting
- Automatic temporary IP bans after repeated violations (default 300s)

Response Headers:
- X-RateLimit-Limit: The maximum number of requests allowed in the window
- X-RateLimit-Remaining: The number of requests remaining
- X-RateLimit-Reset: Unix timestamp when the current window resets
- Retry-After: Seconds to wait before retrying (on 429 responses)

Rate Limit Key Strategy:
- For authenticated requests: rate limiting key = "user:{user_id}"
- For unauthenticated requests: rate limiting key = "ip:{client_ip}"

Metrics:
- rate_limit_hits_total: Counter for rate limit exceeded events
- rate_limit_blocked_ips: Gauge for currently blocked IP addresses
- ddos_violations_total: Counter for DDoS protection violations

Administration:
- Limits are dynamic. Admins can change tier values and add per-route rules
  at runtime via ``/api/admin/rate-limits/*`` (see app/routers/rate_limits.py)
  without redeploying code. Changes are kept in memory and persisted to
  Redis (preferred) or to the JSON file configured by
  ``RATE_LIMIT_CONFIG_FILE``.

Usage:
    from app.middleware.rate_limit import limiter, RateLimitTiers

    @router.post("/endpoint")
    @limiter.limit(RateLimitTiers.UNAUTHENTICATED_DEFAULT)
    async def endpoint(request: Request):
        ...

    To make a decorated limit dynamic (admin manageable) pass a callable::

    @limiter.limit(lambda: get_tier_limit("unauthenticated_login"))
    async def login(request: Request):
        ...
"""

import json
import logging
import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import unquote_plus

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


DEFAULT_TIERS: dict[str, str] = {
    "authenticated_default": "100/minute",
    "authenticated_read": "200/minute",
    "authenticated_write": "50/minute",
    "unauthenticated_default": "20/minute",
    "unauthenticated_login": "10/minute",
    "unauthenticated_register": "20/minute",
    "unauthenticated_read": "30/minute",
    "ddos_burst": "100/second",
    "ddos_sustained": "1000/minute",
}

READ_METHODS = {"GET", "HEAD", "OPTIONS"}

#: Paths that must never be rate limited (health checks / observability).
EXEMPT_PATHS = {
    "/health",
    "/health/live",
    "/health/ready",
    "/health/detailed",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}

#: Requests matching any of these patterns are rejected as suspicious.
SUSPICIOUS_PATTERN = re.compile(
    r"("
    r"\.\./|\.\.\\|%2e%2e|%252e"
    r"|/etc/passwd|/proc/self|win\.ini"
    r"|<script|javascript:|onerror\s*=|onload\s*="
    r"|union\s+select|select\s+.*\s+from|insert\s+into|drop\s+table"
    r"|\bor\s+1\s*=\s*1\b|\band\s+1\s*=\s*1\b|'\s*or\s*'1"
    r"|sleep\s*\(|benchmark\s*\(|information_schema|xp_cmdshell"
    r"|\x00|%00"
    r")",
    re.IGNORECASE,
)


def get_ip_address(request: Request) -> str:
    """Extract client IP address, considering X-Forwarded-For header."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _decode_unverified_jwt(token: str) -> Optional[dict]:
    try:
        import jwt

        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None


def rate_limit_key(request: Request) -> str:
    """Return a rate limiting key based on user authentication.

    Authenticated requests are limited per user; unauthenticated requests are
    limited per client IP address.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = _decode_unverified_jwt(auth_header[7:])
        if payload:
            user_id = payload.get("user_id")
            if user_id:
                return f"user:{user_id}"
    return f"ip:{get_ip_address(request)}"


def get_authenticated_user_id(request: Request) -> Optional[str]:
    """Extract the (unverified) user_id from the Authorization header JWT."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = _decode_unverified_jwt(auth_header[7:])
        if payload:
            return payload.get("user_id")
    return None


def _get_redis_url() -> Optional[str]:
    """Get Redis URL from environment variables (None when not configured)."""
    return os.getenv("REDIS_URL") or None


def _init_limiter() -> Limiter:
    """Initialize the slowapi limiter with Redis storage when available.

    Falls back to in-memory storage when Redis is not configured or not
    reachable. ``headers_enabled`` ensures X-RateLimit-* headers are emitted
    for decorated routes.
    """
    redis_url = _get_redis_url()
    if redis_url:
        try:
            from limits.storage import RedisStorage

            storage = RedisStorage(storage_uri=redis_url)
            storage.check()
            logger.info("Using Redis storage for rate limiting: %s", redis_url)
            return Limiter(
                key_func=rate_limit_key,
                default_limits=[],
                headers_enabled=True,
                storage_uri=redis_url,
                in_memory_fallback=list(DEFAULT_TIERS.values()),
                in_memory_fallback_enabled=True,
            )
        except Exception as exc:  # pragma: no cover - depends on environment
            logger.warning(
                "Redis unavailable for rate limiting (%s); using in-memory storage",
                exc,
            )
    return Limiter(
        key_func=rate_limit_key,
        default_limits=[],
        headers_enabled=True,
    )


limiter = _init_limiter()


class RateLimitTiers:
    """Named rate limit tiers (static defaults for backwards compatibility).

    Values are strings understood by slowapi/limits, e.g. ``"100/minute"``.
    Runtime-configurable values are read through :func:`get_tier_limit`.
    """

    AUTHENTICATED_DEFAULT = DEFAULT_TIERS["authenticated_default"]
    AUTHENTICATED_READ = DEFAULT_TIERS["authenticated_read"]
    AUTHENTICATED_WRITE = DEFAULT_TIERS["authenticated_write"]

    UNAUTHENTICATED_DEFAULT = DEFAULT_TIERS["unauthenticated_default"]
    UNAUTHENTICATED_LOGIN = DEFAULT_TIERS["unauthenticated_login"]
    UNAUTHENTICATED_REGISTER = DEFAULT_TIERS["unauthenticated_register"]
    UNAUTHENTICATED_READ = DEFAULT_TIERS["unauthenticated_read"]

    DDOS_PROTECTION_BURST = DEFAULT_TIERS["ddos_burst"]
    DDOS_PROTECTION_SUSTAINED = DEFAULT_TIERS["ddos_sustained"]


class RateLimitRule:
    """A per-route rate limit rule configurable at runtime."""

    def __init__(
        self,
        rule_id: str,
        path_prefix: str,
        methods: Optional[list[str]] = None,
        tier: str = "authenticated_write",
        applies_to: str = "any",
        enabled: bool = True,
        description: str = "",
    ) -> None:
        self.id = rule_id
        self.path_prefix = path_prefix
        self.methods = [m.upper() for m in methods] if methods else []
        self.tier = tier
        self.applies_to = applies_to  # "any" | "authenticated" | "unauthenticated"
        self.enabled = enabled
        self.description = description

    def matches(self, path: str, method: str, authenticated: bool) -> bool:
        if not self.enabled:
            return False
        if not path.startswith(self.path_prefix):
            return False
        if self.methods and method.upper() not in self.methods:
            return False
        if self.applies_to == "authenticated" and not authenticated:
            return False
        if self.applies_to == "unauthenticated" and authenticated:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path_prefix": self.path_prefix,
            "methods": self.methods,
            "tier": self.tier,
            "applies_to": self.applies_to,
            "enabled": self.enabled,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RateLimitRule":
        return cls(
            rule_id=data.get("id") or data.get("rule_id") or "rule",
            path_prefix=data.get("path_prefix", "/"),
            methods=data.get("methods") or [],
            tier=data.get("tier", "authenticated_write"),
            applies_to=data.get("applies_to", "any"),
            enabled=bool(data.get("enabled", True)),
            description=data.get("description", ""),
        )


class RateLimitConfigStore:
    """Runtime configuration for named tiers, route rules, and IP bans.

    The store is thread-safe. Persistence is best-effort: Redis (when
    configured) or a JSON file at ``RATE_LIMIT_CONFIG_FILE``. When neither is
    available the store works purely in memory.
    """

    REDIS_CONFIG_KEY = "prequal:rate_limit:config"

    def __init__(self, config_file: Optional[str] = None) -> None:
        self._lock = threading.RLock()
        self._tiers: dict[str, str] = dict(DEFAULT_TIERS)
        self._rules: dict[str, RateLimitRule] = {}
        self._blocked: dict[str, float] = {}
        self._config_file = config_file or os.getenv("RATE_LIMIT_CONFIG_FILE")
        self._redis = self._init_redis()
        self.load()

    # -- Redis helpers -------------------------------------------------
    def _init_redis(self):
        redis_url = _get_redis_url()
        if not redis_url:
            return None
        try:
            from limits.storage import RedisStorage

            storage = RedisStorage(storage_uri=redis_url)
            storage.check()
            return storage
        except Exception:
            return None

    def _redis_client(self):
        if self._redis is None:
            return None
        try:
            return self._redis.get_connection()
        except Exception:
            return None

    # -- Persistence ---------------------------------------------------
    def load(self) -> None:
        """Load persisted configuration, if any."""
        raw: Optional[str] = None
        client = self._redis_client()
        if client is not None:
            try:
                value = client.get(self.REDIS_CONFIG_KEY)
                if value:
                    raw = value.decode() if isinstance(value, bytes) else value
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.warning("Could not read rate limit config from Redis: %s", exc)
        if raw is None and self._config_file and os.path.exists(self._config_file):
            try:
                with open(self._config_file, "r", encoding="utf-8") as handle:
                    raw = handle.read()
            except OSError as exc:  # pragma: no cover - environment dependent
                logger.warning("Could not read rate limit config file: %s", exc)
        if not raw:
            return
        try:
            self._apply_payload(json.loads(raw))
        except (ValueError, TypeError) as exc:
            logger.warning("Ignoring invalid persisted rate limit config: %s", exc)

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        with self._lock:
            for name, limit in (payload.get("tiers") or {}).items():
                if isinstance(limit, str):
                    self._tiers[name] = limit
            self._rules = {}
            for rule_data in payload.get("rules") or []:
                rule = RateLimitRule.from_dict(rule_data)
                self._rules[rule.id] = rule

    def _serialize(self) -> str:
        with self._lock:
            return json.dumps(
                {
                    "tiers": dict(self._tiers),
                    "rules": [r.to_dict() for r in self._rules.values()],
                }
            )

    def persist(self) -> None:
        payload = self._serialize()
        client = self._redis_client()
        if client is not None:
            try:
                client.set(self.REDIS_CONFIG_KEY, payload)
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.warning("Could not persist rate limit config to Redis: %s", exc)
        if self._config_file:
            try:
                directory = os.path.dirname(os.path.abspath(self._config_file))
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with open(self._config_file, "w", encoding="utf-8") as handle:
                    handle.write(payload)
            except OSError as exc:  # pragma: no cover - environment dependent
                logger.warning("Could not persist rate limit config file: %s", exc)

    # -- Tiers ---------------------------------------------------------
    def get_tier(self, name: str) -> Optional[str]:
        with self._lock:
            return self._tiers.get(name)

    def set_tier(self, name: str, limit: str) -> str:
        _validate_limit_string(limit)
        with self._lock:
            self._tiers[name] = limit
        self.persist()
        return limit

    def list_tiers(self) -> dict[str, str]:
        with self._lock:
            return dict(self._tiers)

    def reset_tiers(self) -> dict[str, str]:
        with self._lock:
            self._tiers = dict(DEFAULT_TIERS)
        self.persist()
        return self.list_tiers()

    # -- Route rules ---------------------------------------------------
    def list_rules(self) -> list[dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._rules.values()]

    def upsert_rule(self, rule: RateLimitRule) -> dict[str, Any]:
        _validate_limit_string(self.get_tier(rule.tier) or "1/minute")
        with self._lock:
            self._rules[rule.id] = rule
        self.persist()
        return rule.to_dict()

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            removed = self._rules.pop(rule_id, None) is not None
        if removed:
            self.persist()
        return removed

    def get_rule(self, rule_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            rule = self._rules.get(rule_id)
            return rule.to_dict() if rule else None

    def resolve_limit(
        self, path: str, method: str, authenticated: bool
    ) -> tuple[str, str]:
        """Resolve the effective ``(limit_string, source)`` for a request.

        Route rules take precedence. Otherwise a default tier is selected by
        authentication status and HTTP method (reads are more generous than
        writes).
        """
        with self._lock:
            rules = list(self._rules.values())
        for rule in rules:
            if rule.matches(path, method, authenticated):
                limit = self.get_tier(rule.tier) or DEFAULT_TIERS.get(
                    rule.tier, DEFAULT_TIERS["authenticated_default"]
                )
                return limit, f"rule:{rule.id}"
        if authenticated:
            tier = "authenticated_read" if method.upper() in READ_METHODS else "authenticated_write"
            return self.get_tier(tier) or DEFAULT_TIERS[tier], tier
        if method.upper() in READ_METHODS:
            return (
                self.get_tier("unauthenticated_read")
                or DEFAULT_TIERS["unauthenticated_read"],
                "unauthenticated_read",
            )
        return (
            self.get_tier("unauthenticated_default")
            or DEFAULT_TIERS["unauthenticated_default"],
            "unauthenticated_default",
        )

    # -- IP bans -------------------------------------------------------
    def block_ip(self, ip: str, seconds: int) -> None:
        with self._lock:
            self._blocked[ip] = time.time() + seconds

    def unblock_ip(self, ip: str) -> bool:
        with self._lock:
            return self._blocked.pop(ip, None) is not None

    def is_blocked(self, ip: str) -> bool:
        with self._lock:
            expiry = self._blocked.get(ip)
            if expiry is None:
                return False
            if expiry <= time.time():
                self._blocked.pop(ip, None)
                return False
            return True

    def blocked_until(self, ip: str) -> Optional[float]:
        with self._lock:
            expiry = self._blocked.get(ip)
            if expiry is None or expiry <= time.time():
                self._blocked.pop(ip, None)
                return None
            return expiry

    def list_blocked(self) -> list[dict[str, Any]]:
        now = time.time()
        with self._lock:
            for ip in [ip for ip, exp in self._blocked.items() if exp <= now]:
                self._blocked.pop(ip, None)
            return [
                {"ip": ip, "expires_at": exp, "retry_after": int(exp - now)}
                for ip, exp in self._blocked.items()
            ]


def _validate_limit_string(limit: str) -> None:
    """Validate a ``"<amount>/<period>"`` rate limit string."""
    if not isinstance(limit, str) or not re.match(
        r"^\d+\s*/\s*(second|minute|hour|day)s?$", limit.strip(), re.IGNORECASE
    ):
        raise ValueError(
            f"Invalid rate limit {limit!r}; expected e.g. '100/minute' or '10/second'"
        )


rate_limit_config = RateLimitConfigStore()


def get_tier_limit(name: str) -> str:
    """Return the current (admin-configurable) value of a named tier."""
    value = rate_limit_config.get_tier(name)
    if value:
        return value
    return DEFAULT_TIERS.get(name, DEFAULT_TIERS["unauthenticated_default"])


def reset_rate_limit_config() -> None:
    """Reset tiers, rules, and bans (used by tests and admin reset)."""
    rate_limit_config.reset_tiers()
    for rule in rate_limit_config.list_rules():
        rate_limit_config.delete_rule(rule["id"])


class RateLimitMetrics:
    """Track rate limiting / DDoS metrics for monitoring and alerting."""

    _rate_limit_hits: dict[str, int] = defaultdict(int)
    _violations: dict[str, int] = defaultdict(int)
    _lock = threading.RLock()

    @classmethod
    def record_hit(cls, client_id: str, endpoint: str, limit: str) -> None:
        with cls._lock:
            key = f"{client_id}:{endpoint}"
            cls._rate_limit_hits[key] += 1
            total = cls._rate_limit_hits[key]
        logger.warning(
            "Rate limit exceeded - client=%s endpoint=%s limit=%s total_hits=%s",
            client_id,
            endpoint,
            limit,
            total,
        )
        cls._emit_prometheus_hit(endpoint)

    @classmethod
    def record_blocked(cls, client_id: str, endpoint: str, reason: str) -> None:
        logger.warning(
            "Rate limit blocked - client=%s endpoint=%s reason=%s",
            client_id,
            endpoint,
            reason,
        )
        cls._emit_prometheus_blocked_gauge()

    @classmethod
    def record_violation(cls, client_id: str, endpoint: str, reason: str) -> int:
        """Record a DDoS/suspicious-request violation and return the count."""
        with cls._lock:
            key = f"{client_id}:{endpoint}:{reason}"
            cls._violations[key] += 1
            count = cls._violations[key]
        logger.warning(
            "DDoS violation - client=%s endpoint=%s reason=%s count=%s",
            client_id,
            endpoint,
            reason,
            count,
        )
        cls._emit_prometheus_violation(reason)
        return count

    @classmethod
    def get_stats(cls) -> dict[str, Any]:
        with cls._lock:
            return {
                "total_hits": sum(cls._rate_limit_hits.values()),
                "unique_blocked": len(
                    {k.split(":", 1)[0] for k in cls._rate_limit_hits}
                ),
                "tracked_keys": len(cls._rate_limit_hits),
                "total_violations": sum(cls._violations.values()),
                "blocked_ips": len(rate_limit_config.list_blocked()),
            }

    @classmethod
    def is_ip_blocked(cls, client_id: str) -> bool:
        return rate_limit_config.is_blocked(client_id)

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._rate_limit_hits.clear()
            cls._violations.clear()

    # -- Prometheus integration (best effort) --------------------------
    @classmethod
    def _emit_prometheus_hit(cls, endpoint: str) -> None:
        try:
            from app.metrics import RATE_LIMIT_HITS

            RATE_LIMIT_HITS.labels(endpoint=endpoint).inc()
        except Exception:
            pass

    @classmethod
    def _emit_prometheus_violation(cls, reason: str) -> None:
        try:
            from app.metrics import DDOS_VIOLATIONS

            DDOS_VIOLATIONS.labels(reason=reason).inc()
        except Exception:
            pass

    @classmethod
    def _emit_prometheus_blocked_gauge(cls) -> None:
        try:
            from app.metrics import RATE_LIMIT_BLOCKED_IPS

            RATE_LIMIT_BLOCKED_IPS.set(len(rate_limit_config.list_blocked()))
        except Exception:
            pass


class RateLimitStorage:
    """Thin wrapper around a limits strategy with an in-memory fallback."""

    def __init__(self) -> None:
        self._strategy = self._build_strategy()

    @staticmethod
    def _build_strategy():
        from limits.strategies import MovingWindowRateLimiter
        from limits.storage import MemoryStorage

        redis_url = _get_redis_url()
        if redis_url:
            try:
                from limits.storage import RedisStorage

                storage = RedisStorage(storage_uri=redis_url)
                storage.check()
                return MovingWindowRateLimiter(storage)
            except Exception:
                pass
        return MovingWindowRateLimiter(MemoryStorage())

    def hit(self, item, key: str) -> bool:
        return self._strategy.hit(item, key)

    def window_stats(self, item, key: str):
        return self._strategy.get_window_stats(item, key)


_rate_storage = RateLimitStorage()


def _parse_limit(limit: str):
    from limits import parse

    return parse(limit)


def create_rate_limit_response(
    detail: str,
    retry_after: int = 60,
    limit: Optional[int] = None,
    remaining: int = 0,
    reset: Optional[int] = None,
) -> JSONResponse:
    """Create a standardized 429 response with X-RateLimit-* and Retry-After."""
    headers = {"Retry-After": str(retry_after)}
    if limit is not None:
        headers["X-RateLimit-Limit"] = str(limit)
        headers["X-RateLimit-Remaining"] = str(remaining)
        headers["X-RateLimit-Reset"] = str(reset if reset is not None else int(time.time()) + retry_after)
    return JSONResponse(status_code=429, content={"detail": detail}, headers=headers)


async def rate_limit_handler(request: Request, exc):
    """Exception handler for slowapi rate limit errors."""
    client_ip = get_ip_address(request)
    endpoint = request.url.path

    if not isinstance(exc, RateLimitExceeded):
        RateLimitMetrics.record_blocked(client_ip, endpoint, f"unexpected error: {type(exc).__name__}")
        return create_rate_limit_response("rate limit exceeded", 60)

    RateLimitMetrics.record_hit(client_ip, endpoint, str(getattr(exc, "detail", "")))

    retry_after = 60
    detail = getattr(exc, "detail", None)
    if detail:
        match = re.search(r"(\d+)\s*(second|minute|hour|day)", str(detail), re.IGNORECASE)
        if match:
            value, unit = int(match.group(1)), match.group(2).lower()
            retry_after = {
                "second": value,
                "minute": value * 60,
                "hour": value * 3600,
                "day": value * 86400,
            }[unit]

    return create_rate_limit_response(
        str(detail) if detail else "rate limit exceeded", retry_after
    )


def get_limiter() -> Limiter:
    """Get the shared Limiter instance."""
    return limiter


def _is_decorated_route(request: Request) -> bool:
    """Return True when a slowapi decorator already handles this route.

    This prevents double-counting: decorated routes enforce their own limits
    (and are dynamic via :func:`get_tier_limit`), while the middleware covers
    everything else.
    """
    try:
        from slowapi.middleware import _find_route_handler, _get_route_name

        handler = _find_route_handler(request.app.routes, request.scope)
        if handler is None:
            return False
        name = _get_route_name(handler)
        return name in limiter._route_limits or name in limiter._dynamic_route_limits
    except Exception:
        return False


class ConfigurableRateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce admin-configurable rate limits on all non-decorated routes."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in EXEMPT_PATHS or _is_decorated_route(request):
            return await call_next(request)

        if os.getenv("RATELIMIT_ENABLED", "true").lower() in ("0", "false", "no"):
            return await call_next(request)

        client_id = rate_limit_key(request)
        authenticated = client_id.startswith("user:")
        limit_str, source = rate_limit_config.resolve_limit(
            path, request.method, authenticated
        )

        try:
            item = _parse_limit(limit_str)
        except Exception:
            return await call_next(request)

        key = f"{source}:{client_id}"
        try:
            allowed = _rate_storage.hit(item, key)
            reset_time, remaining = _rate_storage.window_stats(item, key)
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Rate limit storage error (%s); allowing request", exc)
            return await call_next(request)

        reset_epoch = int(reset_time)
        retry_after = max(1, reset_epoch - int(time.time()))

        if not allowed:
            RateLimitMetrics.record_hit(client_id, path, limit_str)
            return create_rate_limit_response(
                f"Rate limit exceeded: {limit_str}",
                retry_after,
                limit=item.amount,
                remaining=0,
                reset=reset_epoch,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(item.amount)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_epoch)
        return response


class RateLimitAlertMiddleware(BaseHTTPMiddleware):
    """Backwards-compatible alias for the enforcement middleware.

    Kept so existing imports keep working; the actual enforcement lives in
    :class:`ConfigurableRateLimitMiddleware`.
    """

    async def dispatch(self, request: Request, call_next):
        client_ip = get_ip_address(request)
        blocked_until = rate_limit_config.blocked_until(client_ip)
        if blocked_until is not None:
            return create_rate_limit_response(
                "Too many requests. You have been temporarily blocked.",
                max(1, int(blocked_until - time.time())),
            )
        return await call_next(request)


def _register_violation(client_id: str, endpoint: str, reason: str) -> None:
    """Record a violation and temporarily ban repeat offenders."""
    threshold = int(os.getenv("DDOS_VIOLATION_THRESHOLD", "20"))
    ban_seconds = int(os.getenv("DDOS_BAN_SECONDS", "300"))
    count = RateLimitMetrics.record_violation(client_id, endpoint, reason)
    if count >= threshold and not rate_limit_config.is_blocked(client_id):
        rate_limit_config.block_ip(client_id, ban_seconds)
        RateLimitMetrics.record_blocked(client_id, endpoint, f"auto-ban after {count} violations")
        _emit_alert(client_id, endpoint, reason, count, ban_seconds)


def _emit_alert(client_id: str, endpoint: str, reason: str, count: int, ban_seconds: int) -> None:
    """Best-effort alerting hook (structured log + optional webhook)."""
    logger.error(
        "SECURITY ALERT: auto-banned %s after %s violations (%s) on %s for %ss",
        client_id,
        count,
        reason,
        endpoint,
        ban_seconds,
    )
    webhook = os.getenv("RATE_LIMIT_ALERT_WEBHOOK")
    if not webhook:
        return
    try:  # pragma: no cover - network dependent
        import httpx

        httpx.post(
            webhook,
            json={
                "event": "rate_limit_auto_ban",
                "client": client_id,
                "endpoint": endpoint,
                "reason": reason,
                "violation_count": count,
                "ban_seconds": ban_seconds,
            },
            timeout=3.0,
        )
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Failed to deliver rate limit alert webhook: %s", exc)


class DDoSProtectionMiddleware(BaseHTTPMiddleware):
    """Request-size limits, connection throttling, and pattern detection."""

    def __init__(self, app, **kwargs) -> None:
        super().__init__(app, **kwargs)
        self._active: dict[str, int] = defaultdict(int)
        self._active_lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in EXEMPT_PATHS:
            return await call_next(request)

        client_ip = get_ip_address(request)

        blocked_until = rate_limit_config.blocked_until(client_ip)
        if blocked_until is not None:
            return create_rate_limit_response(
                "Too many requests. You have been temporarily blocked.",
                max(1, int(blocked_until - time.time())),
            )

        rejection = self._screen_request(request, client_ip)
        if rejection is not None:
            return rejection

        max_concurrent = int(os.getenv("DDOS_MAX_CONCURRENT_PER_IP", "50"))
        with self._active_lock:
            self._active[client_ip] += 1
            active = self._active[client_ip]
        try:
            if active > max_concurrent:
                _register_violation(client_ip, path, "connection_throttle")
                return create_rate_limit_response(
                    "Too many concurrent requests from this client.", 1
                )
            return await call_next(request)
        finally:
            with self._active_lock:
                self._active[client_ip] -= 1
                if self._active[client_ip] <= 0:
                    self._active.pop(client_ip, None)

    def _screen_request(self, request: Request, client_ip: str) -> Optional[Response]:
        max_body = int(os.getenv("DDOS_MAX_BODY_BYTES", str(10 * 1024 * 1024)))
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > max_body:
                    _register_violation(client_ip, request.url.path, "request_too_large")
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request entity too large"},
                    )
            except ValueError:
                _register_violation(client_ip, request.url.path, "invalid_content_length")
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid Content-Length header"}
                )

        max_query = int(os.getenv("DDOS_MAX_QUERY_LENGTH", "2048"))
        max_params = int(os.getenv("DDOS_MAX_QUERY_PARAMS", "50"))
        max_headers = int(os.getenv("DDOS_MAX_HEADER_COUNT", "100"))

        raw_query = request.scope.get("query_string", b"")
        query = raw_query.decode("latin-1") if isinstance(raw_query, bytes) else str(raw_query)
        if len(query) > max_query:
            _register_violation(client_ip, request.url.path, "query_too_long")
            return JSONResponse(status_code=400, content={"detail": "Query string too long"})
        if query.count("&") + 1 > max_params and query:
            _register_violation(client_ip, request.url.path, "too_many_params")
            return JSONResponse(status_code=400, content={"detail": "Too many query parameters"})
        if len(request.headers) > max_headers:
            _register_violation(client_ip, request.url.path, "too_many_headers")
            return JSONResponse(status_code=400, content={"detail": "Too many headers"})

        user_agent = request.headers.get("user-agent", "")
        decoded_query = unquote_plus(query)
        haystack = f"{request.url.path}?{query} {decoded_query}"
        if "\x00" in haystack or SUSPICIOUS_PATTERN.search(haystack):
            _register_violation(client_ip, request.url.path, "suspicious_pattern")
            return JSONResponse(
                status_code=400, content={"detail": "Malformed or suspicious request"}
            )
        if len(user_agent) > 1024 or "\x00" in user_agent:
            _register_violation(client_ip, request.url.path, "invalid_user_agent")
            return JSONResponse(status_code=400, content={"detail": "Invalid User-Agent"})
        return None


def setup_rate_limiting(app) -> None:
    """Configure rate limiting and DDoS protection middleware on the app."""
    if getattr(app.state, "_rate_limit_setup_done", False):
        return
    app.state.limiter = limiter
    app.add_middleware(ConfigurableRateLimitMiddleware)
    app.add_middleware(DDoSProtectionMiddleware)
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.state._rate_limit_setup_done = True
    logger.info("Rate limiting and DDoS protection middleware configured")
