from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
_AGENT_ENV_KEYS = (
    "MEDGUARD_AGENT_MODE",
    "MEDGUARD_AGENT_COVERAGE_SCOPE",
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
            (
                "from app.core.config import Settings; "
                "s=Settings(); "
                "print(s.environment, s.agent_mode, s.agent_coverage_scope, "
                "s.agent_sync_enabled, s.agent_max_iterations)"
            ),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


def test_development_defaults_to_enforced_single_path_when_not_overridden():
    assert _probe({"MEDGUARD_ENVIRONMENT": "development"}) == (
        "development enforced all True 1"
    )


def test_production_defaults_to_enforced_single_path():
    assert _probe({"MEDGUARD_ENVIRONMENT": "production"}) == (
        "production enforced all True 1"
    )


def test_explicit_agent_mode_and_execution_override_still_wins():
    assert _probe(
        {
            "MEDGUARD_ENVIRONMENT": "development",
            "MEDGUARD_AGENT_MODE": "shadow",
            "MEDGUARD_AGENT_COVERAGE_SCOPE": "clinical",
            "MEDGUARD_AGENT_SYNC_ENABLED": "false",
            "MEDGUARD_AGENT_MAX_ITERATIONS": "0",
        }
    ) == "development shadow clinical False 0"
