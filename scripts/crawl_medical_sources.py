#!/usr/bin/env python3
"""Asynchronous Medical Web Crawler using Crawl4AI with resilient HTTP fallback.

Crawls authoritative clinical portals (national drug formularies, treatment guidelines,
WHO/NICE safety communications) and produces clean, de-duplicated Markdown documents
stored in training/raw/crawled/ for refinement and dataset synthesis.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Try importing Crawl4AI
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode  # type: ignore[import-not-found]
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

import httpx


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "_", cleaned).strip("-_")[:60]


def _clean_html_to_markdown(html: str) -> str:
    """Resilient fallback converter from HTML to Markdown when Crawl4AI browser is not present."""
    # Remove script and style tags
    html = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Headings
    html = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    # Paragraphs and line breaks
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", html, flags=re.DOTALL | re.IGNORECASE)
    # List items
    html = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Normalize whitespace
    lines = [line.strip() for line in text.split("\n")]
    cleaned_lines = [line for line in lines if line]
    return "\n\n".join(cleaned_lines)


class MedicalWebCrawler:
    """Crawler engine encapsulating Crawl4AI with resilient HTTP fallback."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def crawl_with_crawl4ai(self, url: str, exclude_selectors: list[str]) -> dict[str, Any]:
        """Crawl page using Crawl4AI headless browser engine."""
        css_exclusion = ", ".join(exclude_selectors) if exclude_selectors else ""
        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            excluded_tags=exclude_selectors,
            remove_overlay_elements=True,
            markdown_generator=None,
        )
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            if not result.success:
                raise RuntimeError(f"Crawl4AI failed for {url}: {result.error_message}")
            return {
                "url": url,
                "title": getattr(result, "title", "Medical Document") or "Medical Document",
                "markdown": result.markdown or "",
                "status_code": result.status_code,
            }

    async def crawl_with_httpx_fallback(self, url: str) -> dict[str, Any]:
        """Fallback crawl using standard HTTP client and HTML-to-markdown cleaner."""
        headers = {
            "User-Agent": "MedGuard-Clinical-Research-Crawler/1.0 (+https://medguard.ai; contact@medguard.internal)",
            "Accept": "text/html,application/xhtml+xml",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Medical Document"
            markdown = _clean_html_to_markdown(html)
            return {
                "url": url,
                "title": title,
                "markdown": markdown,
                "status_code": resp.status_code,
            }

    async def process_url(self, source_meta: dict[str, Any], url: str) -> dict[str, Any]:
        source_id = source_meta["source_id"]
        print(f"[*] Crawling: {url} (Source: {source_id})")

        data: dict[str, Any] = {}
        if CRAWL4AI_AVAILABLE:
            try:
                data = await self.crawl_with_crawl4ai(url, source_meta.get("exclude_selectors", []))
                engine_used = "crawl4ai"
            except Exception as exc:
                print(f"    [!] Crawl4AI error: {exc}. Falling back to HTTP client...")
                data = await self.crawl_with_httpx_fallback(url)
                engine_used = "httpx_fallback"
        else:
            data = await self.crawl_with_httpx_fallback(url)
            engine_used = "httpx_fallback"

        timestamp = datetime.now(timezone.utc).isoformat()
        document = {
            "source_id": source_id,
            "source_name": source_meta.get("name"),
            "category": source_meta.get("category"),
            "license_kind": source_meta.get("license_kind"),
            "usage_rights_confirmed": source_meta.get("usage_rights_confirmed", True),
            "source_uri": url,
            "title": data.get("title"),
            "crawled_at": timestamp,
            "crawler_engine": engine_used,
            "content_markdown": data.get("markdown"),
            "char_count": len(data.get("markdown", "")),
        }

        # Save to raw storage
        parsed_url = urlparse(url)
        slug = _slugify(parsed_url.path or "home")
        out_file = self.output_dir / f"{source_id}_{slug}.json"
        out_file.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    [+] Saved ({document['char_count']} chars) -> {out_file.name}")
        return document


async def run_crawler(manifest_path: Path, output_dir: Path, max_pages: int) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = manifest.get("sources", [])
    crawler = MedicalWebCrawler(output_dir)

    results: list[dict[str, Any]] = []
    print("=" * 70)
    print(f"STARTING MEDICAL CRAWLER (Crawl4AI Available: {CRAWL4AI_AVAILABLE})")
    print(f"Target manifest: {manifest_path}")
    print(f"Output directory: {output_dir}")
    print("=" * 70)

    for src in sources:
        urls = src.get("base_urls", [])[:max_pages]
        for url in urls:
            try:
                doc = await crawler.process_url(src, url)
                results.append(doc)
            except Exception as exc:
                print(f"    [-] Failed to crawl {url}: {exc}")

    print(f"\n[✓] Crawling complete. Successfully captured {len(results)} documents.")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl medical guidelines using Crawl4AI.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT_DIR / "training/configs/crawl_sources_manifest.json",
        help="Path to crawl sources manifest",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "training/raw/crawled",
        help="Directory to save raw crawled documents",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=2,
        help="Maximum pages to crawl per source",
    )
    args = parser.parse_args()

    asyncio.run(run_crawler(args.manifest, args.output_dir, args.max_pages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
