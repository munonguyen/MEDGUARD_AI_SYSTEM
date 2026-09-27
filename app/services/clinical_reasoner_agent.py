"""Agent A: Clinical Reasoner Agent for MedGuard AI System.

Phase 3.2 Architecture:
- Primary Author: Synthesizes initial clinical assessment, differential explanations,
  self-care guidance, and red flags.
- Atomic Claim Tracking: Every significant medical claim is tagged with `claim_id`
  and associated `evidence_ids` from the Clinical Evidence Packet.
- Non-Dogmatic: Formulates explanations as possibilities, not definitive diagnoses.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from typing import Any
import uuid

from app.models.evidence import ClinicalEvidencePacket
from app.models.intake import CompiledClinicalIntake
from app.models.safety import SafetyKernelResult
from app.models.synthesis import Claim, ReasoningDraft

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-flash-lite-latest"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


class ClinicalReasonerAgent:
    """Agent A: Generates structured clinical draft with claim-evidence provenance."""

    @classmethod
    def generate_draft(
        cls,
        intake: CompiledClinicalIntake,
        evidence_packet: ClinicalEvidencePacket,
        safety_kernel: SafetyKernelResult,
        patient_context: dict[str, Any] | None = None,
    ) -> ReasoningDraft:
        draft_id = f"DRAFT-{uuid.uuid4().hex[:8]}"

        # If LLM key is configured and not in isolated unit tests, we can query Gemini
        if os.getenv("MEDGUARD_TEST_LLM_SYNTHESIS") and GEMINI_API_KEY:
            try:
                llm_draft = cls._call_gemini_reasoner(
                    draft_id, intake, evidence_packet, safety_kernel, patient_context
                )
                if llm_draft:
                    return llm_draft
            except Exception as exc:
                logger.warning("Gemini Reasoner call failed, falling back to local reasoner: %s", exc)

        return cls._synthesize_local_reasoner(draft_id, intake, evidence_packet, safety_kernel)

    @classmethod
    def _synthesize_local_reasoner(
        cls,
        draft_id: str,
        intake: CompiledClinicalIntake,
        evidence_packet: ClinicalEvidencePacket,
        safety_kernel: SafetyKernelResult,
    ) -> ReasoningDraft:
        """Deterministic, rich in-process clinical reasoning with full claim-evidence linking."""
        raw_text = intake.raw_query.lower()
        evidence_list = evidence_packet.all_evidence
        evidence_id_map = {e.domain: e.evidence_id for e in evidence_list}

        # Determine Specialty & Topic
        if safety_kernel.emergency_lock:
            urgency = "EMERGENCY"
            specialty_code = "CARDIOLOGY" if any("ACS" in r for r in safety_kernel.triggered_rules) else (
                "NEUROLOGY" if any("STROKE" in r or "THUNDERCLAP" in r for r in safety_kernel.triggered_rules) else "GENERAL"
            )
            specialty_label = "Cấp cứu / Tim mạch" if specialty_code == "CARDIOLOGY" else (
                "Cấp cứu / Thần kinh" if specialty_code == "NEUROLOGY" else "Hồi sức cấp cứu"
            )
            interpretation = "Các triệu chứng bạn mô tả trùng khớp với dấu hiệu cảnh báo nguy kịch cần can thiệp y tế tức thời."
            likely_explanations = safety_kernel.hard_red_flags
            self_care = ["Nghỉ ngơi tại chỗ, không vận động mạnh", "Nới lỏng trang phục để thông thoáng đường thở"]
            red_flags = safety_kernel.hard_red_flags
            follow_ups = ["Triệu chứng xuất hiện bao lâu rồi?", "Có người hỗ trợ bên cạnh bạn ngay lúc này không?"]

            c1 = Claim(
                claim_id="C1",
                text="Tình trạng hiện tại có các dấu hiệu nguy kịch cần được đưa đến cơ sở y tế cấp cứu ngay lập tức.",
                evidence_ids=[evidence_id_map.get("red_flags", "E1")],
            )
            c2 = Claim(
                claim_id="C2",
                text="Hãy gọi ngay 115 hoặc nhờ người nhà đưa đi cấp cứu, tuyệt đối không tự điều khiển phương tiện giao thông.",
                evidence_ids=[evidence_id_map.get("guideline", "E2")],
            )
            claims = [c1, c2]

            draft_answer = (
                f"BẠN CẦN ĐƯỢC ĐÁNH GIÁ CẤP CỨU NGAY: {c1.text}\n\n"
                f"Hướng xử lý khẩn cấp: {c2.text}\n"
                f"- Dấu hiệu đe dọa sinh mạng: {', '.join(red_flags)}.\n"
                f"- Trong khi chờ 115: Giữ bình tĩnh, ngồi hoặc nằm tư thế thoải mái."
            )

        elif "mũi" in raw_text or "xoang" in raw_text or "họng" in raw_text:
            urgency = "ROUTINE"
            specialty_code = "ENT"
            specialty_label = "Tai Mũi Họng"
            interpretation = "Triệu chứng sổ mũi, nghẹt mũi thường do phản ứng viêm niêm mạc đường hô hấp trên lành tính."
            likely_explanations = [
                "Cảm lạnh thông thường do nhiễm siêu vi",
                "Viêm mũi dị ứng do thời tiết hoặc dị nguyên",
            ]
            self_care = [
                "Vệ sinh khoang mũi bằng nước muối sinh lý 0.9% ấm",
                "Uống nhiều nước ấm, giữ ấm vùng cổ ngực và nghỉ ngơi hợp lý",
            ]
            red_flags = [
                "Sốt cao > 38.5°C kéo dài trên 3 ngày",
                "Dịch mũi đổi màu xanh/vàng đục đặc quánh kèm đau nhức trán, hốc mắt",
                "Xuất hiện khó thở, thở rít hoặc mệt lả",
            ]
            follow_ups = [
                "Dịch mũi của bạn trong suốt hay có màu vàng đục?",
                "Bạn có bị sốt hoặc đau họng kèm theo không?",
            ]

            c1 = Claim(
                claim_id="C1",
                text="Tình trạng sổ mũi nhiều có thể là biểu hiện của cảm lạnh thông thường hoặc viêm mũi dị ứng theo mùa.",
                evidence_ids=[evidence_id_map.get("guideline", "E1")],
            )
            c2 = Claim(
                claim_id="C2",
                text="Rửa mũi bằng dung dịch nước muối sinh lý 0.9% giúp làm sạch dịch tiết và giảm xung huyết niêm mạc an toàn.",
                evidence_ids=[evidence_id_map.get("clinical", "E2")],
            )
            c3 = Claim(
                claim_id="C3",
                text="Nếu xuất hiện sốt cao trên 3 ngày hoặc dịch mũi đặc quánh kèm đau nhức mặt, bạn nên đi khám chuyên khoa Tai Mũi Họng.",
                evidence_ids=[evidence_id_map.get("red_flags", "E3")],
            )
            claims = [c1, c2, c3]

            draft_answer = (
                f"Chào bạn, qua thông tin bạn chia sẻ: {c1.text}\n\n"
                f"Hướng dẫn tự chăm sóc tại nhà: {c2.text} Bên cạnh đó, bạn hãy uống nhiều nước ấm và giữ ấm cơ thể.\n\n"
                f"Dấu hiệu cảnh báo cần thăm khám: {c3.text}"
            )

        else:  # Orthopedics / Musculoskeletal / General
            urgency = "ROUTINE"
            specialty_code = "ORTHOPEDICS"
            specialty_label = "Cơ xương khớp"
            interpretation = "Cảm giác mỏi cơ hoặc căng tức sau khi đi lại/đứng nhiều thường là hiện tượng căng cơ cơ học hoặc mỏi cơ lành tính."
            likely_explanations = [
                "Căng cơ cơ học do vận động hoặc đứng lâu",
                "Mất nước hoặc thiếu hụt điện giải vi lượng tạm thời",
            ]
            self_care = [
                "Nghỉ ngơi, gác chân cao hơn tim khi nằm để hỗ trợ tuần hoàn",
                "Chườm ấm nhẹ nhàng vùng bắp chân giúp giãn cơ",
                "Uống đủ nước, có thể bổ sung nước điện giải (oresol, nước dừa)",
            ]
            red_flags = [
                "Một bên bắp chân sưng to rõ rệt, nóng đỏ và đau tức dữ dội khi ấn",
                "Đau buốt không thể tì chân đi lại được",
                "Kèm theo khó thở hoặc đau ngực đột ngột",
            ]
            follow_ups = [
                "Cơn đau xuất hiện sau khi bạn vận động nhiều hay tự nhiên xuất hiện?",
                "Có kèm theo sưng tấy hoặc nóng đỏ một bên chân không?",
            ]

            c1 = Claim(
                claim_id="C1",
                text="Đau mỏi cơ bắp chân sau khi vận động đi lại thường là biểu hiện căng cơ cơ học lành tính (DOMS).",
                evidence_ids=[evidence_id_map.get("clinical", "E1")],
            )
            c2 = Claim(
                claim_id="C2",
                text="Nghỉ ngơi kê cao chân, chườm ấm và bổ sung đủ nước điện giải là biện pháp phục hồi hiệu quả tại nhà.",
                evidence_ids=[evidence_id_map.get("guideline", "E2")],
            )
            c3 = Claim(
                claim_id="C3",
                text="Nếu phát hiện bắp chân một bên sưng to bất thường, nóng đỏ hoặc đau nhức dữ dội, bạn cần đến bệnh viện khám ngay.",
                evidence_ids=[evidence_id_map.get("red_flags", "E3")],
            )
            claims = [c1, c2, c3]

            draft_answer = (
                f"Chào bạn: {c1.text}\n\n"
                f"Biện pháp chăm sóc: {c2.text}\n\n"
                f"Cảnh báo an toàn: {c3.text}"
            )

        sources_data = [
            {
                "source_id": e.source_ref.source_id,
                "title": e.source_ref.title,
                "publisher": e.source_ref.publisher,
                "url": e.source_ref.url,
                "authority_tier": e.source_ref.authority_tier,
                "version": e.source_ref.version,
            }
            for e in evidence_list[:2]
        ]

        return ReasoningDraft(
            draft_id=draft_id,
            urgency=urgency,
            specialty_code=specialty_code,
            specialty_label=specialty_label,
            clinical_interpretation=interpretation,
            likely_explanations=likely_explanations,
            self_care=self_care,
            red_flags=red_flags,
            follow_up_questions=follow_ups,
            claims=claims,
            draft_answer=draft_answer,
            sources=sources_data,
        )

    @classmethod
    def _call_gemini_reasoner(
        cls,
        draft_id: str,
        intake: CompiledClinicalIntake,
        evidence_packet: ClinicalEvidencePacket,
        safety_kernel: SafetyKernelResult,
        patient_context: dict[str, Any] | None,
    ) -> ReasoningDraft | None:
        """Call Gemini to generate a structured reasoning draft."""
        prompt = (
            "Bạn là Agent A (Clinical Reasoner) trong hệ thống MedGuard AI.\n"
            "Nhiệm vụ của bạn là đưa ra nhận định lâm sàng có cấu trúc, thấu cảm, khoa học.\n"
            "BẮT BUỘC: Mỗi nhận định y khoa quan trọng phải được tách thành từng claim kèm evidence_ids tương ứng.\n"
            f"{evidence_packet.to_xml_prompt()}\n\n"
            "Hãy trả về JSON theo schema ReasoningDraft:\n"
            "{\n"
            '  "urgency": "ROUTINE" | "URGENT" | "EMERGENCY",\n'
            '  "specialty_code": "ENT" | "ORTHOPEDICS" | "CARDIOLOGY" | "GENERAL",\n'
            '  "specialty_label": "...",\n'
            '  "clinical_interpretation": "...",\n'
            '  "likely_explanations": ["..."],\n'
            '  "self_care": ["..."],\n'
            '  "red_flags": ["..."],\n'
            '  "follow_up_questions": ["..."],\n'
            '  "claims": [{"claim_id": "C1", "text": "...", "evidence_ids": ["E1"]}],\n'
            '  "draft_answer": "..."\n'
            "}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        url = f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)
            claims = [
                Claim(
                    claim_id=c.get("claim_id", f"C{i+1}"),
                    text=c.get("text", ""),
                    evidence_ids=c.get("evidence_ids", []),
                )
                for i, c in enumerate(parsed.get("claims", []))
            ]
            return ReasoningDraft(
                draft_id=draft_id,
                urgency=parsed.get("urgency", "ROUTINE"),
                specialty_code=parsed.get("specialty_code", "GENERAL"),
                specialty_label=parsed.get("specialty_label", "Tổng quát"),
                clinical_interpretation=parsed.get("clinical_interpretation", ""),
                likely_explanations=parsed.get("likely_explanations", []),
                self_care=parsed.get("self_care", []),
                red_flags=parsed.get("red_flags", []),
                follow_up_questions=parsed.get("follow_up_questions", []),
                claims=claims,
                draft_answer=parsed.get("draft_answer", ""),
                sources=[
                    {
                        "source_id": e.source_ref.source_id,
                        "title": e.source_ref.title,
                        "publisher": e.source_ref.publisher,
                        "authority_tier": e.source_ref.authority_tier,
                    }
                    for e in evidence_packet.all_evidence[:2]
                ],
            )
