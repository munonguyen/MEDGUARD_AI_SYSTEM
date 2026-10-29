from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from app.core.observability import metrics
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


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class TokenBudget:
    max_input_tokens: int
    max_output_tokens: int


@dataclass(frozen=True)
class AdaptiveAgentRuntimeConfig:
    mode: str = "shadow"
    kev_base_url: str | None = None
    kev_model: str = "kev-latest"
    kev_timeout_seconds: float = 0.35
    kev_calibration_status: str = "unvalidated"
    kev_calibration_version: str | None = None
    fast_writer_model: str | None = None
    standard_writer_model: str | None = None
    deep_writer_model: str | None = None
    writer_fallback_models: tuple[str, ...] = ()
    verifier_fallback_models: tuple[str, ...] = ()
    fast_max_input_tokens: int = 7000
    fast_max_output_tokens: int = 900
    standard_max_input_tokens: int = 10000
    standard_max_output_tokens: int = 1400
    verifier_fast_max_output_tokens: int = 700
    verifier_standard_max_output_tokens: int = 900
    verifier_deep_max_output_tokens: int = 1200

    @classmethod
    def from_env(cls) -> "AdaptiveAgentRuntimeConfig":
        return cls(
            mode=(os.getenv("MEDGUARD_ADAPTIVE_ROUTING_MODE", "shadow") or "shadow").strip().lower(),
            kev_base_url=(os.getenv("MEDGUARD_KEV_URL") or None),
            kev_model=(os.getenv("MEDGUARD_KEV_MODEL", "kev-latest") or "kev-latest").strip(),
            kev_timeout_seconds=_float_env("MEDGUARD_KEV_TIMEOUT_SECONDS", 0.35),
            kev_calibration_status=(
                os.getenv("MEDGUARD_KEV_CALIBRATION_STATUS", "unvalidated") or "unvalidated"
            ).strip().lower(),
            kev_calibration_version=(os.getenv("MEDGUARD_KEV_CALIBRATION_VERSION") or None),
            fast_writer_model=(os.getenv("MEDGUARD_FAST_WRITER_MODEL") or None),
            standard_writer_model=(os.getenv("MEDGUARD_STANDARD_WRITER_MODEL") or None),
            deep_writer_model=(os.getenv("MEDGUARD_DEEP_WRITER_MODEL") or None),
            writer_fallback_models=_csv(os.getenv("MEDGUARD_WRITER_FALLBACK_MODELS")),
            verifier_fallback_models=_csv(os.getenv("MEDGUARD_VERIFIER_FALLBACK_MODELS")),
            fast_max_input_tokens=_int_env("MEDGUARD_FAST_MAX_INPUT_TOKENS", 7000),
            fast_max_output_tokens=_int_env("MEDGUARD_FAST_MAX_OUTPUT_TOKENS", 900),
            standard_max_input_tokens=_int_env("MEDGUARD_STANDARD_MAX_INPUT_TOKENS", 10000),
            standard_max_output_tokens=_int_env("MEDGUARD_STANDARD_MAX_OUTPUT_TOKENS", 1400),
            verifier_fast_max_output_tokens=_int_env("MEDGUARD_VERIFIER_FAST_MAX_OUTPUT_TOKENS", 700),
            verifier_standard_max_output_tokens=_int_env("MEDGUARD_VERIFIER_STANDARD_MAX_OUTPUT_TOKENS", 900),
            verifier_deep_max_output_tokens=_int_env("MEDGUARD_VERIFIER_DEEP_MAX_OUTPUT_TOKENS", 1200),
        )

    @property
    def effective_mode(self) -> str:
        requested = self.mode if self.mode in {"disabled", "shadow", "enforced"} else "shadow"
        if requested != "enforced":
            return requested
        # A real Kev endpoint may affect execution only after an explicitly
        # versioned calibration has been approved. Missing Kev still falls back
        # to the validated clinical result and therefore does not require this
        # approval marker.
        if self.kev_base_url and not self.kev_is_calibrated:
            return "shadow"
        return "enforced"

    @property
    def kev_is_calibrated(self) -> bool:
        return (
            self.kev_calibration_status == "validated"
            and bool((self.kev_calibration_version or "").strip())
        )


class AdaptiveAgentRuntime:
    """Resolve execution routing without owning the clinical decision.

    The clinical envelope is read-only. The runtime may choose an execution
    agent/model tier, token budget, or provider model ladder, but it never
    mutates ``clinical_result.urgency``. Model fallback is therefore orthogonal
    to clinical severity. A real Kev endpoint cannot enter enforced routing
    unless a versioned calibration has been explicitly marked validated.
    """

    def __init__(self, config: AdaptiveAgentRuntimeConfig | None = None) -> None:
        self.config = config or AdaptiveAgentRuntimeConfig.from_env()
        self.mode = self.config.effective_mode
        if self.config.mode == "enforced" and self.mode != "enforced":
            metrics.inc_counter(
                "medguard_kev_enforcement_guard_total",
                labels={"reason": "calibration_not_validated"},
            )
        self.kev = KevRouter(
            KevRouterConfig(
                base_url=self.config.kev_base_url,
                model=self.config.kev_model,
                timeout_seconds=self.config.kev_timeout_seconds,
                mode=self.mode,
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
            kev_mode=self.mode,
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

    def token_budget(
        self,
        *,
        route: AdaptiveRouteDecision | None,
        role: str,
        base_input_tokens: int,
        base_output_tokens: int,
    ) -> TokenBudget:
        # V15 must not change legacy/non-routed or pharmacology behavior merely
        # because adaptive execution exists. Only a concrete adaptive route is
        # allowed to tighten budgets.
        if route is None:
            return TokenBudget(
                max_input_tokens=max(1, base_input_tokens),
                max_output_tokens=max(1, base_output_tokens),
            )

        tier = route.model_tier
        input_limit = base_input_tokens
        output_limit = base_output_tokens

        if tier == ModelTier.FAST:
            input_limit = min(input_limit, self.config.fast_max_input_tokens)
            if role == "verifier":
                output_limit = min(output_limit, self.config.verifier_fast_max_output_tokens)
            else:
                output_limit = min(output_limit, self.config.fast_max_output_tokens)
        elif tier == ModelTier.STANDARD:
            input_limit = min(input_limit, self.config.standard_max_input_tokens)
            if role == "verifier":
                output_limit = min(output_limit, self.config.verifier_standard_max_output_tokens)
            else:
                output_limit = min(output_limit, self.config.standard_max_output_tokens)
        elif role == "verifier":
            output_limit = min(output_limit, self.config.verifier_deep_max_output_tokens)

        # Deep Writer keeps the caller's full budget. Emergency/uncertain routes
        # are deliberately DEEP, so cost optimization can never truncate the
        # highest-risk clinical path below its configured baseline.
        return TokenBudget(
            max_input_tokens=max(1, input_limit),
            max_output_tokens=max(1, output_limit),
        )

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
