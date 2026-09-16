"""Active Learning & Knowledge Capture Service for MedGuard AI.

Captures unmapped clinical queries and novel health cases processed via
the LiteLLM Gateway / Dual-Agent pipeline so they can be reviewed,
curated, and integrated into model training & fine-tuning datasets.
"""

from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from app.core.observability import metrics
from app.models.chat import GroundedAnswer
from app.services.audit import AuditEvent, audit_store

_DEFAULT_STORAGE_PATH = Path("datasets/active_learning/captured_cases.json")


@dataclass
class CapturedKnowledgeCase:
    case_id: str
    timestamp: str
    tenant_id: str
    conversation_id: str
    request_id: str
    user_query: str
    detected_intent: str
    suggested_intent: str
    suggested_domain: str
    answer_summary: str
    narrative: list[dict[str, Any]]
    verifier_status: str
    verifier_scores: dict[str, float]
    citations: list[str]
    clinical_review_status: str = "pending_review"
    training_eligible: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_training_case(self) -> dict[str, Any]:
        """Convert into DS-DUAL-AGENT-TRAINING case schema."""
        return {
            "case_id": f"DA-AL-{self.case_id[:8]}",
            "group": "WRITER_CLINICAL" if self.suggested_domain == "clinical" else "WRITER_PHARMA",
            "sub_category": "ACTIVE_LEARNING_CAPTURED",
            "input": self.user_query,
            "expected_intent": self.suggested_intent,
            "expected_urgency": "ROUTINE",
            "expected_domain": self.suggested_domain,
            "description": f"Ca thu nhận tự động: {self.user_query[:60]}...",
            "target_answer": self.answer_summary,
            "verified_by_agent": self.verifier_status == "verified",
        }


class ActiveLearningStore:
    def __init__(self, storage_path: Path = _DEFAULT_STORAGE_PATH) -> None:
        self.storage_path = storage_path
        self._lock = RLock()
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        with self._lock:
            if not self.storage_path.parent.exists():
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                initial_data = {
                    "_meta": {
                        "version": "1.0.0",
                        "description": "MedGuard Active Learning Buffer — Tri thức mới ghi nhận từ Gateway",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    "cases": [],
                }
                self.storage_path.write_text(
                    json.dumps(initial_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

    def capture_case(
        self,
        *,
        request_id: str,
        tenant_id: str,
        conversation_id: str,
        query: str,
        detected_intent: str,
        answer: GroundedAnswer,
        suggested_intent: str = "triage",
        suggested_domain: str = "clinical",
        metadata: dict[str, Any] | None = None,
    ) -> CapturedKnowledgeCase:
        trace = answer.agent_trace
        verifier_status = trace.status if trace else "deterministic"
        verifier_scores = {}
        citations = []
        if trace:
            if trace.verification:
                verifier_scores = {
                    "grounding": trace.verification.scores.grounding,
                    "safety": trace.verification.scores.safety,
                    "completeness": trace.verification.scores.completeness,
                    "citation_coverage": trace.verification.scores.citation_coverage,
                }
            citations = list(trace.verifier_citation_urls or [])

        narrative_blocks = [
            {"kind": b.kind, "text": b.text, "emphasis": b.emphasis}
            for b in answer.narrative
        ]

        case = CapturedKnowledgeCase(
            case_id=f"AL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            request_id=request_id,
            user_query=query,
            detected_intent=detected_intent,
            suggested_intent=suggested_intent,
            suggested_domain=suggested_domain,
            answer_summary=answer.summary,
            narrative=narrative_blocks,
            verifier_status=verifier_status,
            verifier_scores=verifier_scores,
            citations=citations,
            clinical_review_status="pending_review",
            # Captured clinical text is never admitted to training solely on
            # model or deterministic status. A designated reviewer must mark
            # both review approval and training eligibility explicitly.
            training_eligible=False,
            metadata=metadata or {},
        )

        with self._lock:
            self._ensure_storage_exists()
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            except Exception:
                data = {"_meta": {"version": "1.0.0"}, "cases": []}

            data["cases"].append(asdict(case))
            data["_meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
            data["_meta"]["total_captured"] = len(data["cases"])

            self.storage_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        # Audit event recording
        audit_store.append(
            AuditEvent(
                request_id=request_id,
                tenant_id=tenant_id,
                action="knowledge.captured",
                payload_type="active_learning_case",
                metadata={
                    "case_id": case.case_id,
                    # Audit metadata is operational telemetry, not a clinical
                    # content store. Keep raw text only in the access-controlled
                    # review buffer and use a stable digest in audit events.
                    "query_digest": sha256(query.encode("utf-8")).hexdigest()[:24],
                    "verifier_status": verifier_status,
                    "suggested_intent": suggested_intent,
                },
            )
        )

        metrics.inc_counter(
            "medguard_unmapped_knowledge_captured_total",
            labels={"intent": detected_intent, "status": verifier_status},
        )

        return case

    def list_cases(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            self._ensure_storage_exists()
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                return data.get("cases", [])[-limit:]
            except Exception:
                return []

    def export_to_training_dataset(
        self,
        output_path: Path | None = None,
        min_safety_score: float = 0.8,
    ) -> list[dict[str, Any]]:
        with self._lock:
            cases_raw = self.list_cases(limit=1000)
            eligible = []
            for c in cases_raw:
                if not c.get("training_eligible", False):
                    continue
                if c.get("clinical_review_status") != "approved":
                    continue
                safety = c.get("verifier_scores", {}).get("safety", 1.0)
                if safety >= min_safety_score:
                    obj = CapturedKnowledgeCase(**c)
                    eligible.append(obj.to_training_case())

            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "_meta": {
                        "version": "1.0.0",
                        "description": "Exported active learning dataset for model training",
                        "exported_at": datetime.now(timezone.utc).isoformat(),
                        "count": len(eligible),
                    },
                    "cases": eligible,
                }
                output_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            return eligible


active_learning_store = ActiveLearningStore()
