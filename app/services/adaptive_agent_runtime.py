from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from app.models.adaptive_routing import AdaptiveRouteDecision, ModelTier
from app.services.adaptive_dispatcher import resolve_adaptive_route
from app.services.kev_router import KevRouter, KevRouterConfig, build_compact_kev_state


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AdaptiveAgentRuntimeConfig:
    mode: str = "shadow"
    kev_base_url: str | None = None
    kev_model: str = "kev-latest"
    kev_timeout_seconds: float = 0.35
    fast_writer_model: str | None = None
    standard_writer_model: str | None = None
    deep_writer_model: str | None = None
    writer_fallback_models: tuple[str, ...] = ()
    verifier_fallback_models: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "AdaptiveAgentRuntimeConfig":
        return cls(
            mode=(os.getenv("MEDGUARD_ADAPTIVE_ROUTING_MODE", "shadow") or "shadow").strip().lower(),
            kev_base_url=(os.getenv("MEDGUARD_KEV_URL") or None),
            kev_model=(os.getenv("MEDGUARD_KEV_MODEL", "kev-latest") or "kev-latest").strip(),
            kev_timeout_seconds=_float_env("MEDGUARD_KEV_TIMEOUT_SECONDS", 0.35),
            fast_writer_model=(os.getenv("MEDGUARD_FAST_WRITER_MODEL") or None),
            standard_writer_model=(os.getenv("MEDGUARD_STANDARD_WRITER_MODEL") or None),
            deep_writer_model=(os.getenv("MEDGUARD_DEEP_WRITER_MODEL") or None),
            writer_fallback_models=_csv(os.getenv("MEDGUARD_WRITER_FALLBACK_MODELS")),
            verifier_fallback_models=_csv(os.getenv("MEDGUARD_VERIFIER_FALLBACK_MODELS")),
        )


class AdaptiveAgentRuntime:
    """Resolve execution routing without owning the clinical decision.

    The clinical envelope is read-only. The runtime may choose an execution
    agent/model tier or request a deeper uncertainty path, but it never mutates
    ``clinical_result.urgency``. Provider/model fallback is therefore orthogonal
    to clinical severity.
    """

    def __init__(self, config: AdaptiveAgentRuntimeConfig | None = None) -> None:
        self.config = config or AdaptiveAgentRuntimeConfig.from_env()
        self.kev = KevRouter(
            KevRouterConfig(
                base_url=self.config.kev_base_url,
                model=self.config.kev_model,
                timeout_seconds=self.config.kev_timeout_seconds,
                mode=self.config.mode,
            )
        )

    def resolve(
        self,
        *,
        envelope: dict[str, Any],
        patient_context: dict[str, Any] | None = None,
    ) -> AdaptiveRouteDecision | None:
        raw_result = envelope.get("clinical_result")
        if not isinstance(raw_result, dict):
            return None
        clinical_result = dict(raw_result)
        clinical_task = str(
            clinical_result.get("clinical_task")
            or envelope.get("clinical_task")
            or "general_medical"
        ).strip().lower()
        state = build_compact_kev_state(
            clinical_task=clinical_task,
            clinical_result=clinical_result,
            patient_context=patient_context,
        )
        kev = self.kev.evaluate(state, clinical_result)
        return resolve_adaptive_route(
            clinical_task=clinical_task,
            clinical_result=clinical_result,
            kev=kev,
            kev_mode=self.config.mode,
        )

    def writer_models(self, *, route: AdaptiveRouteDecision | None, default_model: str) -> tuple[str, ...]:
        primary = default_model
        if route is not None:
            if route.model_tier == ModelTier.FAST and self.config.fast_writer_model:
                primary = self.config.fast_writer_model
            elif route.model_tier == ModelTier.STANDARD and self.config.standard_writer_model:
                primary = self.config.standard_writer_model
            elif route.model_tier == ModelTier.DEEP and self.config.deep_writer_model:
                primary = self.config.deep_writer_model
        return self._dedupe((primary, default_model, *self.config.writer_fallback_models))

    def verifier_models(self, *, default_model: str) -> tuple[str, ...]:
        return self._dedupe((default_model, *self.config.verifier_fallback_models))

    @staticmethod
    def _dedupe(models: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for model in models:
            value = str(model).strip()
            if value and value not in seen:
                seen.add(value)
                ordered.append(value)
        return tuple(ordered)


adaptive_agent_runtime = AdaptiveAgentRuntime()
