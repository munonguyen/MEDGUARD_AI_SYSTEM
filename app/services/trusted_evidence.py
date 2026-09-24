"""Bounded runtime fetcher for evidence selected by a grounded writer.

This is deliberately not a general-purpose crawler.  It only reads HTTPS
pages from MedGuard's clinical allow-list, caps redirects/bytes/time, strips
active content, and keeps a short in-memory cache.  Fetched text is ephemeral
review context; it is never promoted into the approved knowledge base without
the existing offline review workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from threading import RLock
from time import monotonic
from typing import Iterable
from urllib.parse import urlsplit

import httpx

from app.core.observability import metrics


TRUSTED_MEDICAL_DOMAINS = frozenset(
    {
        "who.int",
        "nice.org.uk",
        "nhs.uk",
        "fda.gov",
        "ema.europa.eu",
        "cdc.gov",
        "nih.gov",
        "ncbi.nlm.nih.gov",
        "moh.gov.vn",
        "kcb.vn",
        "dav.gov.vn",
    }
)


def trusted_medical_url(value: str) -> bool:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() != "https" or parsed.username or parsed.password:
        return False
    hostname = (parsed.hostname or "").lower().rstrip(".")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in TRUSTED_MEDICAL_DOMAINS
    )


class _VisibleTextParser(HTMLParser):
    _blocked_tags = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._blocked_tags:
            self._blocked_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._blocked_tags and self._blocked_depth:
            self._blocked_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._blocked_depth == 0:
            cleaned = " ".join(data.split())
            if cleaned:
                self.parts.append(cleaned)


@dataclass(frozen=True)
class RuntimeEvidence:
    requested_url: str
    url: str
    content: str
    content_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "requested_url": self.requested_url,
            "url": self.url,
            "content": self.content,
            "content_type": self.content_type,
        }


class TrustedEvidenceFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: float = 6.0,
        max_pages: int = 2,
        max_bytes: int = 256_000,
        max_text_chars: int = 6_000,
        cache_ttl_seconds: float = 600.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_pages = max_pages
        self.max_bytes = max_bytes
        self.max_text_chars = max_text_chars
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, RuntimeEvidence]] = {}
        self._lock = RLock()

    def _cached(self, url: str) -> RuntimeEvidence | None:
        with self._lock:
            cached = self._cache.get(url)
            if not cached:
                return None
            expires_at, evidence = cached
            if expires_at <= monotonic():
                self._cache.pop(url, None)
                return None
            return evidence

    def _store(self, requested_url: str, evidence: RuntimeEvidence) -> None:
        with self._lock:
            self._cache[requested_url] = (
                monotonic() + self.cache_ttl_seconds,
                evidence,
            )

    def _fetch_one(self, url: str) -> RuntimeEvidence | None:
        cached = self._cached(url)
        if cached:
            metrics.inc_counter("medguard_runtime_evidence_total", labels={"outcome": "cache_hit"})
            return cached
        if not trusted_medical_url(url):
            metrics.inc_counter("medguard_runtime_evidence_total", labels={"outcome": "blocked_domain"})
            return None

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                max_redirects=3,
                headers={
                    "User-Agent": "MedGuard-EvidenceVerifier/1.0 (+clinical-safety-review)",
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
                },
            ) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    final_url = str(response.url)
                    if not trusted_medical_url(final_url):
                        metrics.inc_counter(
                            "medguard_runtime_evidence_total",
                            labels={"outcome": "blocked_redirect"},
                        )
                        return None
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                        metrics.inc_counter(
                            "medguard_runtime_evidence_total",
                            labels={"outcome": "unsupported_content_type"},
                        )
                        return None
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > self.max_bytes:
                            break
                        chunks.append(chunk)
                    raw = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        except (httpx.HTTPError, ValueError):
            metrics.inc_counter("medguard_runtime_evidence_total", labels={"outcome": "fetch_error"})
            return None

        if content_type == "text/plain":
            text = " ".join(raw.split())
        else:
            parser = _VisibleTextParser()
            parser.feed(raw)
            text = " ".join(parser.parts)
        text = text[: self.max_text_chars].strip()
        if len(text) < 80:
            metrics.inc_counter("medguard_runtime_evidence_total", labels={"outcome": "empty"})
            return None
        evidence = RuntimeEvidence(
            requested_url=url,
            url=final_url,
            content=text,
            content_type=content_type,
        )
        self._store(url, evidence)
        metrics.inc_counter("medguard_runtime_evidence_total", labels={"outcome": "fetched"})
        return evidence

    def fetch(self, urls: Iterable[str]) -> list[RuntimeEvidence]:
        evidence: list[RuntimeEvidence] = []
        for url in dict.fromkeys(str(value).strip() for value in urls if value):
            if len(evidence) >= self.max_pages:
                break
            item = self._fetch_one(url)
            if item:
                evidence.append(item)
        return evidence


trusted_evidence_fetcher = TrustedEvidenceFetcher()
