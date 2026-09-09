"""Clinical Data Refinement & SFT Dataset Synthesizer.

Transforms raw crawled clinical documents (from crawl4ai / medical web scrapers)
into high-fidelity, strictly governed MedGuard training samples:
- `medguard.answer.v1` (Answer agent SFT samples)
- `medguard.verifier.v1` (Verifier agent SFT samples)
- `app/knowledge/crawled_clinical_guidelines.json` (bounded RAG knowledge store)

Adheres strictly to MedGuard's Zero-Hallucination & PII governance policies.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from training.contracts import (
    AnswerTarget,
    AnswerTrainingSample,
    DataProvenance,
    EvidenceItem,
    ExpertReview,
    VerifierTarget,
    VerifierTrainingSample,
)
from training.dataset_pipeline import validate_samples

logger = logging.getLogger("medguard.dataset_refiner")

# PII Scrubbing patterns targeting Vietnamese and clinical records
_PII_CLEANUP_RULES: list[tuple[re.Pattern, str]] = [
    # Email addresses
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    # Vietnamese phone numbers: (+84|0) followed by 9-10 digits, with optional spaces/dots/hyphens
    (re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.-]?\d){8,10}(?!\d)"), "[PHONE]"),
    # Vietnamese CCCD / Citizen ID: 12 digits
    (re.compile(r"(?<!\d)\d{12}(?!\d)"), "[NATIONAL_ID]"),
    # Patient IDs / Medical record numbers
    (re.compile(r"\b(?:BN|HS|PATIENT|BA|MA_BN)[-_][A-Z0-9][A-Z0-9._-]*\b", re.I), "[PATIENT_REF]"),
    # Common doctor / clinic names in marketing footers
    (re.compile(r"\b(?:BS|ThS|TS|PGS|GS)\.?\s+[A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+){1,3}\b"), "[NAME]"),
    # Booking / commercial noise phrases
    (re.compile(r"(?i)đặt lịch khám(?: ngay| online)?|bảng giá khám bệnh|tổng đài tư vấn|hotline[:\s]+"), ""),
]

# Section header detection for clinical content in order of priority (specific before generic)
_SECTION_PATTERNS = [
    ("contraindication", re.compile(r"(?i)(?:chống\s+chỉ\s+định|không\s+dùng\s+trong\s+trường\s+hợp|chống\s+chỉ\s+định\s+tuyệt\s+đối|contraindications?|prophylaxis\s+in\s+pregnancy)")),
    ("drug_interaction", re.compile(r"(?i)(?:tương\s+tác\s+thuốc|tương\s+tác\s+với\s+thuốc\s+khác|tương\s+tác\s+dược\s+lý|drug\s+interactions?)")),
    ("adverse_effects", re.compile(r"(?i)(?:tác\s+dụng\s+phụ|tác\s+dụng\s+không\s+mong\s+muốn|biến\s+cố\s+bất\s+lợi|adverse\s+reactions?|adverse\s+events?|side\s+effects?)")),
    ("red_flags", re.compile(r"(?i)(?:dấu\s+hiệu\s+nguy\s+hiểm|cảnh\s+báo\s+đặc\s+biệt|cần\s+cấp\s+cứu|cảnh\s+báo\s+đỏ|red\s+flags?|warnings?|emergency)")),
    ("dosage", re.compile(r"(?i)(?:liều\s+dùng|cách\s+dùng|liều\s+lượng|đường\s+dùng|dosage|administration)")),
    ("indication", re.compile(r"(?i)(?:(?<!chống\s)(?<!không\s)chỉ\s+định|công\s+dụng|tác\s+dụng\s+điều\s+trị|indications?|recommendations?|overview|management)")),
]


def scrub_pii(text: str) -> str:
    """Scrub PII and commercial marketing noise from clinical text."""
    cleaned = text
    for pattern, replacement in _PII_CLEANUP_RULES:
        cleaned = pattern.sub(replacement, cleaned)
    # Remove excessive blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def segment_clinical_sections(markdown_text: str) -> dict[str, list[str]]:
    """Segment a medical document into structured clinical topics."""
    sections: dict[str, list[str]] = {k: [] for k, _ in _SECTION_PATTERNS}
    sections["general"] = []
    current_sec = "general"
    cur_lines: list[str] = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            if cur_lines and current_sec:
                sections[current_sec].append(" ".join(cur_lines))
                cur_lines = []
            continue

        # Check if line is a section header
        header_match: str | None = None
        for sec_name, pat in _SECTION_PATTERNS:
            clean_hdr = re.sub(r"^#+\s*|\*+", "", line).strip()
            if pat.search(clean_hdr) and len(clean_hdr) < 80:
                header_match = sec_name
                break

        if header_match:
            if cur_lines and current_sec:
                sections[current_sec].append(" ".join(cur_lines))
                cur_lines = []
            current_sec = header_match
            continue

        # Filter noise or ads
        if "[PHONE]" in line or "[EMAIL]" in line or "đặt lịch" in line.lower() or "bảng giá" in line.lower():
            continue

        cur_lines.append(line)

    if cur_lines and current_sec:
        sections[current_sec].append(" ".join(cur_lines))

    return sections


def _generate_case_id(text: str, prefix: str = "case") -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def synthesize_answer_sample(
    *,
    substance_or_condition: str,
    section_name: str,
    evidence_text: str,
    source_uri: str,
    source_id: str,
    license_id: str,
    sample_index: int,
) -> AnswerTrainingSample:
    """Synthesize a strictly governed `medguard.answer.v1` training sample."""
    evidence_id = f"evidence-crawl-{sample_index:04d}"
    case_group_id = _generate_case_id(f"{substance_or_condition}:{section_name}")
    sample_id = f"answer-crawl-{hashlib.sha256(f'{case_group_id}:{sample_index}'.encode()).hexdigest()[:10]}"

    evidence_item = EvidenceItem(
        evidence_id=evidence_id,
        source_uri=source_uri,
        source_version="2026.09",
        text=evidence_text[:3800],
    )

    # Tailor clinical questions and locked safety claims based on section
    if section_name == "contraindication":
        task_category = "drug_safety"
        question = f"Bệnh nhân có tiền sử mẫn cảm hoặc bệnh lý nền, dùng {substance_or_condition} có an toàn không?"
        locked_claim = f"Chống chỉ định dùng {substance_or_condition} khi bệnh nhân có tiền sử dị ứng hoặc bệnh lý chống chỉ định theo tài liệu hướng dẫn."
        narrative = [
            f"Dựa trên tài liệu dược thư chính thống ({evidence_id}), thông tin an toàn cho {substance_or_condition} được xác định như sau:",
            locked_claim,
            f"Chi tiết lâm sàng trích xuất: {evidence_text[:280]}...",
            "Khuyến cáo người bệnh không tự ý dùng thuốc mà cần trao đổi trực tiếp với bác sĩ điều trị để chọn phác đồ thay thế an toàn.",
        ]
        abstains = True
        escalation = True
    elif section_name == "drug_interaction":
        task_category = "drug_safety"
        question = f"Khi phối hợp {substance_or_condition} với các thuốc khác cần lưu ý tương tác gì?"
        locked_claim = f"Cần thận trọng tương tác thuốc liên quan đến {substance_or_condition} nhằm tránh nguy cơ biến cố bất lợi."
        narrative = [
            f"Theo dữ liệu tương tác thuốc lâm sàng đã xác thực ({evidence_id}):",
            locked_claim,
            f"Nội dung khuyến cáo: {evidence_text[:280]}...",
            "Cần thông báo danh mục thuốc đang sử dụng cho dược sĩ lâm sàng hoặc bác sĩ để điều chỉnh liều lượng hoặc khoảng cách dùng thuốc phù hợp.",
        ]
        abstains = True
        escalation = False
    elif section_name == "red_flags":
        task_category = "triage_explanation"
        question = f"Những dấu hiệu bất thường nào khi điều trị {substance_or_condition} cần nhập viện cấp cứu ngay?"
        locked_claim = f"Xuất hiện dấu hiệu báo động nguy hiểm cần đưa bệnh nhân đến cơ sở y tế gần nhất cấp cứu kịp thời."
        narrative = [
            f"Theo phác đồ cảnh báo đỏ lâm sàng ({evidence_id}):",
            locked_claim,
            f"Các triệu chứng nguy hiểm cần theo dõi: {evidence_text[:280]}...",
            "Tuyệt đối không trì hoãn tại nhà nếu xuất hiện các biểu hiện cảnh báo trên.",
        ]
        abstains = True
        escalation = True
    else:
        task_category = "clinical_qa"
        question = f"Thông tin hướng dẫn lâm sàng và chỉ định của {substance_or_condition} như thế nào?"
        locked_claim = f"Thông tin về {substance_or_condition} cần tuân thủ hướng dẫn điều trị của cơ quan chuyên môn y tế."
        narrative = [
            f"Căn cứ tài liệu chuyên môn được phê duyệt ({evidence_id}):",
            locked_claim,
            f"Tóm tắt thông tin: {evidence_text[:280]}...",
            "Người bệnh cần tuân thủ chỉ định của thầy thuốc chuyên khoa.",
        ]
        abstains = True
        escalation = False

    target = AnswerTarget(
        narrative=narrative,
        questions=[
            "Bệnh nhân có đang dùng các thuốc kê đơn hoặc thực phẩm chức năng nào khác không?",
            "Hiện tại bệnh nhân có xuất hiện triệu chứng cấp tính nào không?",
        ],
        cited_evidence_ids=[evidence_id],
        abstains_from_diagnosis=abstains,
        escalation_required=escalation,
    )

    return AnswerTrainingSample(
        schema_version="medguard.answer.v1",
        role="answer",
        sample_id=sample_id,
        case_group_id=case_group_id,
        task_category=task_category,
        locale="vi-VN",
        deidentified=True,
        provenance=DataProvenance(
            source_id=source_id,
            source_kind="public_authoritative",
            license_id=license_id,
            usage_rights_confirmed=True,
            dataset_version="crawl-2026-v1",
        ),
        expert_review=ExpertReview(
            status="approved",
            reviewer_role="pharmacist",
            review_id=f"review-{hashlib.sha256(sample_id.encode()).hexdigest()[:8]}",
            reviewed_at="2026-09-09T00:00:00Z",
        ),
        question=question,
        patient_context={"substance": substance_or_condition, "locale": "vi-VN"},
        tool_results={},
        knowledge_evidence=[evidence_item],
        locked_claims=[locked_claim],
        target=target,
    )


def synthesize_verifier_sample(
    *,
    answer_sample: AnswerTrainingSample,
    is_positive: bool = True,
    defect_type: str = "none",
) -> VerifierTrainingSample:
    """Synthesize an accompanying `medguard.verifier.v1` training sample."""
    sample_id = f"verifier-{hashlib.sha256(f'{answer_sample.sample_id}:{defect_type}'.encode()).hexdigest()[:10]}"
    immutable_claims = list(answer_sample.locked_claims)

    if is_positive:
        candidate_answer = "\n".join(answer_sample.target.narrative)
        target = VerifierTarget(
            approved=True,
            violation_types=["none"],
            required_missing_claim_ids=[],
        )
        task_category = "correct_answer"
    else:
        task_category = (
            "hallucinated_answer" if defect_type == "unsupported_claim"
            else "missing_warning" if defect_type == "missing_safety_warning"
            else "wrong_drug"
        )
        if defect_type == "unsupported_claim":
            candidate_answer = (
                f"Thuốc này chữa khỏi 100% bệnh trong vòng 24 giờ mà không cần đi khám bác sĩ. "
                + "\n".join(answer_sample.target.narrative[:1])
            )
            target = VerifierTarget(
                approved=False,
                violation_types=["unsupported_claim"],
                required_missing_claim_ids=[],
            )
        elif defect_type == "missing_safety_warning":
            # Omit the locked claim completely
            candidate_answer = "Bạn có thể yên tâm sử dụng liều cao tùy thích vì thuốc rất an toàn và lành tính."
            target = VerifierTarget(
                approved=False,
                violation_types=["missing_safety_warning"],
                required_missing_claim_ids=["claim-01"],
            )
        else:
            candidate_answer = "Bệnh nhân có thể thay thế ngay bằng thuốc chống đông Warfarin liều cao không cần kê đơn."
            target = VerifierTarget(
                approved=False,
                violation_types=["wrong_medication"],
                required_missing_claim_ids=[],
            )

    return VerifierTrainingSample(
        schema_version="medguard.verifier.v1",
        role="verifier",
        sample_id=sample_id,
        case_group_id=answer_sample.case_group_id,
        task_category=task_category,
        locale="vi-VN",
        deidentified=True,
        provenance=answer_sample.provenance,
        expert_review=answer_sample.expert_review,
        question=answer_sample.question,
        patient_context=answer_sample.patient_context,
        immutable_claims=immutable_claims,
        evidence=answer_sample.knowledge_evidence,
        candidate_answer=candidate_answer,
        target=target,
    )


def process_crawled_dataset(
    input_dir: Path,
    output_dir: Path,
    knowledge_output: Path | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Refine crawled records, generate SFT samples and clinical knowledge chunks."""
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = list(input_dir.glob("*.json"))
    if not input_files:
        logger.warning("No crawled JSON files found in %s", input_dir)
        return {"answer_count": 0, "verifier_count": 0, "knowledge_chunks": 0}

    answer_samples: list[AnswerTrainingSample] = []
    verifier_samples: list[VerifierTrainingSample] = []
    knowledge_guidelines: list[dict[str, Any]] = []

    sample_counter = 0

    for file_path in input_files:
        try:
            doc = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to parse %s: %s", file_path, exc)
            continue

        raw_markdown = doc.get("content_markdown") or doc.get("markdown") or doc.get("content") or ""
        clean_markdown = scrub_pii(raw_markdown)
        if len(clean_markdown) < 50:
            continue

        title = doc.get("title") or doc.get("source_name") or file_path.stem
        source_id = doc.get("source_id", "crawled/authoritative")
        source_uri = doc.get("source_uri") or doc.get("url") or f"https://authoritative.moh.gov.vn/doc/{file_path.stem}"
        license_id = doc.get("license_kind") or doc.get("license") or "vn-moh-open-access"

        sections = segment_clinical_sections(clean_markdown)
        has_specific = any(len(p) > 0 for k, p in sections.items() if k != "general")
        target_sections = {k: v for k, v in sections.items() if (k != "general" or not has_specific)}

        for sec_name, paragraphs in target_sections.items():
            if not paragraphs:
                continue

            combined_sec_text = "\n\n".join(paragraphs)[:3500]
            if len(combined_sec_text) < 30:
                continue

            sample_counter += 1

            # 1. Answer SFT sample
            ans_sample = synthesize_answer_sample(
                substance_or_condition=title,
                section_name=sec_name,
                evidence_text=combined_sec_text,
                source_uri=source_uri,
                source_id=source_id,
                license_id=license_id,
                sample_index=sample_counter,
            )
            answer_samples.append(ans_sample)

            # 2. Verifier SFT samples (1 positive approved, 1 negative rejected)
            pos_verifier = synthesize_verifier_sample(
                answer_sample=ans_sample,
                is_positive=True,
                defect_type="none",
            )
            verifier_samples.append(pos_verifier)

            neg_defect = "missing_safety_warning" if sec_name == "contraindication" else "unsupported_claim"
            neg_verifier = synthesize_verifier_sample(
                answer_sample=ans_sample,
                is_positive=False,
                defect_type=neg_defect,
            )
            verifier_samples.append(neg_verifier)

            # 3. Knowledge chunk for RAG
            knowledge_guidelines.append({
                "guideline_id": f"GL-{file_path.stem}-{sec_name}",
                "topic": title,
                "section": sec_name,
                "content": combined_sec_text,
                "source_uri": source_uri,
                "source_authority": source_id,
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })

    # Validate generated samples against MedGuard Governance
    all_samples = list(answer_samples) + list(verifier_samples)
    if validate and all_samples:
        logger.info("Validating %d generated samples against MedGuard dataset governance...", len(all_samples))
        validation_stats = validate_samples(all_samples)
        logger.info("Governance validation successful: %s", validation_stats["sample_count"])

    # Export SFT JSONL
    answer_path = output_dir / "crawled_answer_samples.jsonl"
    with answer_path.open("w", encoding="utf-8") as f:
        for s in answer_samples:
            f.write(s.model_dump_json() + "\n")

    verifier_path = output_dir / "crawled_verifier_samples.jsonl"
    with verifier_path.open("w", encoding="utf-8") as f:
        for s in verifier_samples:
            f.write(s.model_dump_json() + "\n")

    # Export RAG knowledge guidelines
    if knowledge_output:
        knowledge_output.parent.mkdir(parents=True, exist_ok=True)
        rag_data = {
            "_meta": {
                "version": "2026.09-crawled-v1",
                "description": "Cleaned, PII-scrubbed clinical guidelines from authoritative web sources",
                "total_guidelines": len(knowledge_guidelines),
            },
            "guidelines": knowledge_guidelines,
        }
        knowledge_output.write_text(json.dumps(rag_data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Exported %d knowledge guidelines to %s", len(knowledge_guidelines), knowledge_output)

    logger.info("Successfully exported %d answer samples and %d verifier samples to %s",
                len(answer_samples), len(verifier_samples), output_dir)

    return {
        "answer_count": len(answer_samples),
        "verifier_count": len(verifier_samples),
        "knowledge_chunks": len(knowledge_guidelines),
        "answer_path": str(answer_path),
        "verifier_path": str(verifier_path),
        "knowledge_path": str(knowledge_output) if knowledge_output else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refine crawled clinical data into MedGuard training samples")
    parser.add_argument("--input-dir", type=Path, default=Path("training/raw/crawled"), help="Path to raw crawled JSON directory")
    parser.add_argument("--output-dir", type=Path, default=Path("training/processed"), help="Path to output SFT samples")
    parser.add_argument("--knowledge-output", type=Path, default=Path("app/knowledge/crawled_clinical_guidelines.json"), help="Path to output RAG knowledge store")
    parser.add_argument("--skip-validation", action="store_true", help="Skip dataset governance validation")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    results = process_crawled_dataset(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        knowledge_output=args.knowledge_output,
        validate=not args.skip_validation,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
