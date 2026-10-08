"""Process-local, bounded HTTP pool; never retain credentials or patient payloads."""
from contextlib import contextmanager
from http.cookiejar import CookieJar, DefaultCookiePolicy
from threading import Lock

import httpx

_lock = Lock()
_clients: dict[tuple[object, int], httpx.Client] = {}


class _NoCookies(DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        return False


@contextmanager
def provider_client(timeout_seconds: int):
    # Include the factory identity so injected test transports are isolated.
    key = (httpx.Client, timeout_seconds)
    with _lock:
        client = _clients.get(key)
        if client is None:
            client = httpx.Client(
                timeout=timeout_seconds,
                limits=httpx.Limits(max_connections=32, max_keepalive_connections=16, keepalive_expiry=30),
                cookies=CookieJar(policy=_NoCookies()),
            )
            _clients[key] = client
    # httpx.Client supports sharing between request threads. Headers stay on
    # each individual call; never mutate global authorization/default headers.
    yield client


def close_provider_clients() -> None:
    with _lock:
        clients = list(_clients.values())
        _clients.clear()
    for client in clients:
        client.close()
