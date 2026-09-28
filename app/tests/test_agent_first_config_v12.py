from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
_AGENT_ENV_KEYS = (
    "MEDGUARD_AGENT_MODE",
    "MEDGUARD_AGENT_MAX_ITERATIONS",
    "MEDGUARD_AGENT_SYNC_ENABLED",
    "MEDGUARD_AGENT_BACKGROUND_ENABLED",
)


def _probe(extra_env: dict[str, str]) -> str:
    env = os.environ.copy()
    for key in _AGENT_ENV_KEYS:
        env.pop(key, None)
    env.update(extra_env)
    env.pop("PYTEST_CURRENT_TEST", None)
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.core.config import Settings; s=Settings(); print(s.environment, s.agent_mode, s.agent_max_iterations)",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


def test_development_defaults_to_enforced_agent_first_when_not_overridden():
    assert _probe({"MEDGUARD_ENVIRONMENT": "development"}) == "development enforced 1"


def test_explicit_agent_mode_override_still_wins():
    assert _probe(
        {
            "MEDGUARD_ENVIRONMENT": "development",
            "MEDGUARD_AGENT_MODE": "shadow",
            "MEDGUARD_AGENT_MAX_ITERATIONS": "0",
        }
    ) == "development shadow 0"
