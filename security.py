"""Small, dependency-free helpers for dashboard authentication."""
import hashlib, hmac, time

MAX_FAILS = 5
LOCK_SECONDS = 300

_fails = {}


def session_token(key, epoch=""):
    """Cookie value derived from the key AND a revocable epoch. The cookie never contains the key itself.

    Without the epoch, the token for a given key never changes, so a leaked cookie (from a log, a shared
    device, a backup) would grant access forever: the only way to kill it would be rotating the whole
    DASHBOARD_KEY, which also logs out the legitimate owner. Bumping the epoch (session_epoch_bump) revokes
    every issued cookie in one step while the key, and every other session started after the bump, stays valid.
    """
    return hmac.new(key.encode(), ("aiqx-dashboard-session-v1:" + str(epoch)).encode(), hashlib.sha256).hexdigest()


def check_credentials(key, supplied_key="", supplied_token="", epoch=""):
    """True if the plain key (query string / login form) or the session token (cookie, for this epoch) is valid."""
    if not key:
        return True
    if supplied_key and hmac.compare_digest(supplied_key.encode(), key.encode()):
        return True
    if supplied_token and hmac.compare_digest(supplied_token.encode(), session_token(key, epoch).encode()):
        return True
    return False


def is_locked(ip, now=None):
    now = time.time() if now is None else now
    entry = _fails.get(ip)
    if not entry:
        return False
    count, first = entry
    if now - first > LOCK_SECONDS:
        _fails.pop(ip, None)
        return False
    return count >= MAX_FAILS


def register_failure(ip, now=None):
    now = time.time() if now is None else now
    entry = _fails.get(ip)
    if not entry or now - entry[1] > LOCK_SECONDS:
        _fails[ip] = (1, now)
    else:
        _fails[ip] = (entry[0] + 1, entry[1])
    if len(_fails) > 5000:
        for stale in [k for k, v in _fails.items() if now - v[1] > LOCK_SECONDS]:
            _fails.pop(stale, None)


def client_ip(forwarded_for, peer, trusted_proxy=True):
    """Client address for rate limiting.

    Behind Railway's proxy the LAST X-Forwarded-For hop is the one the proxy itself appended, so it
    cannot be forged by the caller; the first hop can be set freely by an attacker to dodge the lockout.
    """
    if trusted_proxy and forwarded_for:
        hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return peer or "unknown"


def clear_failures(ip):
    _fails.pop(ip, None)


def authorize(key, supplied_key="", supplied_token="", ip="unknown", now=None, epoch=""):
    """Decide a request: "ok" | "locked" | "denied".

    A VALID session cookie is never blocked by a lockout: the lockout exists to stop key guessing, and letting
    it also reject the legitimate owner would let anyone behind the same proxy hop lock them out. A cookie from
    a revoked (bumped) epoch is simply not valid, so it falls through to the key check like any wrong cookie.
    """
    if not key:
        return "ok"
    if supplied_token and check_credentials(key, supplied_token=supplied_token, epoch=epoch):
        return "ok"
    if is_locked(ip, now):
        return "locked"
    if check_credentials(key, supplied_key=supplied_key):
        return "ok"
    if supplied_key:
        register_failure(ip, now)
    return "denied"


_hits = {}


def rate_limited(bucket, limit, window=60.0, now=None):
    """Sliding-window limiter. True when `bucket` already made `limit` calls in the last `window` seconds."""
    now = time.time() if now is None else now
    recent = [t for t in _hits.get(bucket, ()) if now - t < window]
    if len(recent) >= limit:
        _hits[bucket] = recent
        return True
    recent.append(now)
    _hits[bucket] = recent
    if len(_hits) > 5000:
        for stale in [k for k, v in _hits.items() if not v or now - v[-1] >= window]:
            _hits.pop(stale, None)
    return False


# Pro dashboard + login only talk to their own origin; no third-party scripts, fonts or frames.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def extra_headers(path, content_type=""):
    """Additional response headers: never cache private JSON/login, and lock HTML pages to their own origin."""
    headers = {}
    if path.startswith("/api/") or path in ("/login", "/health"):
        headers["Cache-Control"] = "no-store"
    if path != "/legacy" and "text/html" in (content_type or ""):      # the opt-in legacy page needs its CDNs
        headers["Content-Security-Policy"] = CSP
    return headers
