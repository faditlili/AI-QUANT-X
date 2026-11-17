"""Small, dependency-free helpers for dashboard authentication."""
import hashlib, hmac, time

MAX_FAILS = 5
LOCK_SECONDS = 300

_fails = {}


def session_token(key):
    """Cookie value derived from the key. The cookie never contains the key itself."""
    return hmac.new(key.encode(), b"aiqx-dashboard-session-v1", hashlib.sha256).hexdigest()


def check_credentials(key, supplied_key="", supplied_token=""):
    """True if the plain key (query string / login form) or the session token (cookie) is valid."""
    if not key:
        return True
    if supplied_key and hmac.compare_digest(supplied_key.encode(), key.encode()):
        return True
    if supplied_token and hmac.compare_digest(supplied_token.encode(), session_token(key).encode()):
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
