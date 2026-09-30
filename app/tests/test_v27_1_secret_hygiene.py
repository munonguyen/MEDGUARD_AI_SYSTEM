from __future__ import annotations

import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SECRET_LIKE_GEMINI_KEY = re.compile(r"AQ\.[A-Za-z0-9_-]{20,}")
TEXT_SUFFIXES = {".py", ".sh", ".yaml", ".yml", ".json", ".toml", ".md", ".txt", ".example"}
SKIP_DIRS = {".git", ".venv", "node_modules", "dist", ".artifacts"}


def test_no_provider_key_is_embedded_in_tracked_source() -> None:
    offenders: list[str] = []
    for path in ROOT_DIR.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and not path.name.endswith(".example"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SECRET_LIKE_GEMINI_KEY.search(text) or "DEFAULT_KEY_B64" in text:
            offenders.append(str(path.relative_to(ROOT_DIR)))

    assert offenders == [], f"Provider credential material found in tracked source: {offenders}"


def test_gemini_setup_requires_runtime_secret() -> None:
    setup = (ROOT_DIR / "scripts/configure_gemini_free.sh").read_text(encoding="utf-8")
    quickstart = (ROOT_DIR / "quickstart.sh").read_text(encoding="utf-8")

    assert "GEMINI_API_KEY is required" in setup
    assert "DEFAULT_KEY_B64" not in setup
    assert "--default" not in setup
    assert "--default" not in quickstart
