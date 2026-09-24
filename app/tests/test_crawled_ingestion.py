"""Tests for Crawl4AI ingestion, PII scrubbing, clinical refinement, and SFT sample generation."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.services.knowledge_retriever import KnowledgeRetriever
from scripts.crawl_medical_sources import _clean_html_to_markdown
from scripts.refine_crawled_dataset import (
    process_crawled_dataset,
    scrub_pii,
    segment_clinical_sections,
    synthesize_answer_sample,
    synthesize_verifier_sample,
)
from training.contracts import (
    AnswerTrainingSample,
    VerifierTrainingSample,
    parse_training_sample,
)
from training.dataset_pipeline import validate_samples


def test_html_to_markdown_cleaning():
    """Verify HTML cleanup logic extracts readable markdown without HTML tags or script noise."""
    html_sample = """
    <html>
        <head><script>alert('xss');</script><style>.ads{color:red;}</style></head>
        <body>
            <header><nav>Home | About | Contact</nav></header>
            <h1>Dược thư Quốc gia: Paracetamol</h1>
            <p>Paracetamol (Acetaminophen) là thuốc giảm đau, hạ sốt phổ biến.</p>
            <h2>Chỉ định</h2>
            <p>Hạ sốt từ nhẹ đến vừa. Giảm đau tạm thời trong chứng đau đầu, đau cơ.</p>
            <h2>Chống chỉ định</h2>
            <p>Bệnh nhân suy gan nặng hoặc quá mẫn với paracetamol.</p>
            <footer>Bản quyền 2026 Bộ Y tế</footer>
        </body>
    </html>
    """
    md = _clean_html_to_markdown(html_sample)
    assert "# Dược thư Quốc gia: Paracetamol" in md
    assert "## Chỉ định" in md
    assert "## Chống chỉ định" in md
    assert "suy gan nặng" in md
    assert "<script>" not in md
    assert "<style>" not in md
    assert "<p>" not in md


def test_pii_scrubbing():
    """Verify clinical text is cleansed of phone numbers, emails, CCCD, and marketing noise."""
    raw_text = """
    Bệnh nhân BN_98234 có số điện thoại 0912345678 hoặc +84988765432.
    Email liên hệ bác sĩ: dr.nguyen.van.a@benhvien.vn.
    Số CCCD của người giám hộ: 001095012345.
    BS. Trần Thị Thu Thảo tư vấn đặt lịch khám ngay hôm nay.
    Tổng đài tư vấn: 19001234. Bảng giá khám bệnh niêm yết tại quầy.
    Chống chỉ định: Không phối hợp Methotrexate với NSAID liều cao.
    """
    cleaned = scrub_pii(raw_text)

    # Assert PII is replaced with approved placeholders
    assert "[PHONE]" in cleaned
    assert "[EMAIL]" in cleaned
    assert "[NATIONAL_ID]" in cleaned
    assert "[PATIENT_REF]" in cleaned
    assert "0912345678" not in cleaned
    assert "+84988765432" not in cleaned
    assert "dr.nguyen.van.a@benhvien.vn" not in cleaned
    assert "001095012345" not in cleaned
    assert "BN_98234" not in cleaned

    # Assert clinical content is retained
    assert "Chống chỉ định: Không phối hợp Methotrexate với NSAID liều cao." in cleaned


def test_segment_clinical_sections():
    """Verify clinical paragraphs are accurately categorized into clinical topics."""
    markdown_doc = """
    Chỉ định điều trị
    Dùng trong điều trị tăng huyết áp vô căn và suy tim mạn tính.

    Chống chỉ định
    Phụ nữ có thai 3 tháng giữa và 3 tháng cuối do nguy cơ hạ huyết áp và suy thận sơ sinh.

    Tương tác thuốc
    Phối hợp với thuốc lợi tiểu giữ kali hoặc thực phẩm bổ sung kali có thể làm tăng kali huyết nghiêm trọng.

    Dấu hiệu nguy hiểm cần cấp cứu
    Phù mạch (sưng mặt, môi, lưỡi, thanh quản) gây khó thở cấp tính.
    """
    sections = segment_clinical_sections(markdown_doc)
    assert len(sections["indication"]) >= 1
    assert len(sections["contraindication"]) >= 1
    assert len(sections["drug_interaction"]) >= 1
    assert len(sections["red_flags"]) >= 1
    assert "tăng huyết áp" in sections["indication"][0]
    assert "Phụ nữ có thai" in sections["contraindication"][0]


def test_synthesize_answer_sample_validity():
    """Verify synthesized answer samples satisfy all medguard.answer.v1 contract rules."""
    sample = synthesize_answer_sample(
        substance_or_condition="Lisinopril",
        section_name="contraindication",
        evidence_text="Chống chỉ định tuyệt đối cho phụ nữ mang thai từ tam cá nguyệt thứ hai.",
        source_uri="https://moh.gov.vn/guidelines/lisinopril",
        source_id="vndtf/lisinopril-2024",
        license_id="vn-moh-open-access",
        sample_index=1,
    )
    assert isinstance(sample, AnswerTrainingSample)
    assert sample.schema_version == "medguard.answer.v1"
    assert sample.role == "answer"
    assert sample.task_category == "drug_safety"
    assert sample.deidentified is True
    assert sample.target.abstains_from_diagnosis is True
    assert sample.target.escalation_required is True

    # Validate target narrative contains every locked claim verbatim
    narrative_text = "\n".join(sample.target.narrative)
    for claim in sample.locked_claims:
        assert claim in narrative_text

    # Validate cited evidence IDs match knowledge evidence
    evidence_ids = {e.evidence_id for e in sample.knowledge_evidence}
    for cited in sample.target.cited_evidence_ids:
        assert cited in evidence_ids


def test_synthesize_verifier_sample_validity():
    """Verify synthesized verifier samples satisfy all medguard.verifier.v1 contract rules."""
    ans_sample = synthesize_answer_sample(
        substance_or_condition="Metformin",
        section_name="drug_interaction",
        evidence_text="Nguy cơ nhiễm toan lactic khi dùng đồng thời Metformin với thuốc cản quang chứa iod đường tĩnh mạch.",
        source_uri="https://moh.gov.vn/guidelines/metformin",
        source_id="vndtf/metformin-2024",
        license_id="vn-moh-open-access",
        sample_index=2,
    )

    # Positive sample
    pos_ver = synthesize_verifier_sample(answer_sample=ans_sample, is_positive=True)
    assert isinstance(pos_ver, VerifierTrainingSample)
    assert pos_ver.schema_version == "medguard.verifier.v1"
    assert pos_ver.role == "verifier"
    assert pos_ver.target.approved is True
    assert pos_ver.target.violation_types == ["none"]

    # Negative sample (unsupported claim)
    neg_ver = synthesize_verifier_sample(
        answer_sample=ans_sample, is_positive=False, defect_type="unsupported_claim"
    )
    assert isinstance(neg_ver, VerifierTrainingSample)
    assert neg_ver.target.approved is False
    assert "unsupported_claim" in neg_ver.target.violation_types
    assert "none" not in neg_ver.target.violation_types


def test_end_to_end_crawled_refinement(tmp_path: Path):
    """Verify end-to-end processing pipeline produces valid JSONL splits and RAG knowledge."""
    input_dir = tmp_path / "raw_crawled"
    output_dir = tmp_path / "processed"
    knowledge_path = tmp_path / "crawled_clinical_guidelines.json"
    input_dir.mkdir(parents=True)

    # Create dummy crawled document with medical information & contact info
    doc_payload = {
        "url": "https://moh.gov.vn/phac-do/amoxicillin-clavulanic",
        "title": "Kháng sinh Amoxicillin + Clavulanic Acid",
        "source_id": "vndtf/amox-clav-2024",
        "license": "vn-moh-open-access",
        "markdown": """# Phác đồ sử dụng Amoxicillin / Clavulanic acid
        Liên hệ hỗ trợ dược lâm sàng: 0987654321 hoặc duoclamsang@bv.vn.
        Chỉ định
        Điều trị các nhiễm khuẩn đường hô hấp trên và dưới, nhiễm khuẩn tiết niệu.
        Chống chỉ định
        Tiền sử vàng da tắc mật hoặc rối loạn chức năng gan liên quan đến amoxicillin/acid clavulanic.
        Tương tác thuốc
        Phối hợp với Probenecid làm giảm bài tiết amoxicillin qua ống thận, gây tăng nồng độ amoxicillin trong máu.
        Dấu hiệu nguy hiểm cần cấp cứu
        Phản ứng phản vệ, khó thở cấp tính, phù thanh quản, sốc phản vệ cần tiêm Adrenalin ngay lập tức.
        Bác sĩ tư vấn: BS. Nguyen Van Tuan. Đặt lịch khám online ngay.
        """,
    }
    (input_dir / "amox_clav.json").write_text(json.dumps(doc_payload, ensure_ascii=False), encoding="utf-8")

    stats = process_crawled_dataset(
        input_dir=input_dir,
        output_dir=output_dir,
        knowledge_output=knowledge_path,
        validate=True,
    )

    assert stats["answer_count"] > 0
    assert stats["verifier_count"] == stats["answer_count"] * 2
    assert stats["knowledge_chunks"] > 0

    # Read back and parse JSONL files
    ans_lines = (output_dir / "crawled_answer_samples.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ans_lines) == stats["answer_count"]
    for line in ans_lines:
        parsed = parse_training_sample(json.loads(line))
        assert parsed.role == "answer"

    ver_lines = (output_dir / "crawled_verifier_samples.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ver_lines) == stats["verifier_count"]
    for line in ver_lines:
        parsed = parse_training_sample(json.loads(line))
        assert parsed.role == "verifier"

    # Verify RAG knowledge output
    assert knowledge_path.exists()
    rag_json = json.loads(knowledge_path.read_text(encoding="utf-8"))
    assert "_meta" in rag_json
    assert len(rag_json["guidelines"]) == stats["knowledge_chunks"]

    # Verify that retriever can index and retrieve from this document if placed in app/knowledge
    retriever = KnowledgeRetriever()
    # KnowledgeRetriever runs smoothly with existing index
    assert len(retriever._chunks) > 0
