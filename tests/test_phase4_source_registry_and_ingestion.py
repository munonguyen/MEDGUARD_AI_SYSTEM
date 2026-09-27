"""Unit Tests for Phase 4A: Source Registry, Checksum, and Ingestion Engine."""

import pytest
from app.knowledge.provenance.checksum import compute_sha256, verify_checksum
from app.knowledge.provenance.source_registry import SourceRegistry, SourceRecord
from app.knowledge.ingestion.normalizer import normalize_raw_item, NormalizedEvidence
from app.knowledge.ingestion.chunker import chunk_clinical_text
from app.knowledge.ingestion.version_manager import VersionManager, KnowledgeSnapshot


def test_checksum_deterministic_and_verifiable():
    data1 = {"b": 2, "a": 1}
    data2 = {"a": 1, "b": 2}
    # Deterministic dictionary sorting
    hash1 = compute_sha256(data1)
    hash2 = compute_sha256(data2)
    assert hash1 == hash2
    assert verify_checksum(data1, hash1) is True
    assert verify_checksum(data1, "invalid_hash") is False


def test_source_registry_lifecycle_and_active_filtering():
    registry = SourceRegistry.create_default()

    # Active BYT guideline
    byt_src = registry.get("BYT_QD_361_2014")
    assert byt_src is not None
    assert registry.is_active("BYT_QD_361_2014") is True
    assert byt_src.jurisdiction == "VN"

    # Superseded guideline
    old_src = registry.get("BYT_QD_OLD_2005")
    assert old_src is not None
    assert registry.is_active("BYT_QD_OLD_2005") is False

    active_sources = registry.list_active()
    active_ids = {s.source_id for s in active_sources}
    assert "BYT_QD_361_2014" in active_ids
    assert "BYT_QD_OLD_2005" not in active_ids


def test_normalizer_validates_active_source_and_assigns_authority():
    registry = SourceRegistry.create_default()

    raw_item = {
        "concept": "stroke_thrombolysis_window",
        "statement": "Bệnh nhân đột quỵ thiếu máu não cục bộ cấp cần được đánh giá tiêu sợi huyết trong 4.5 giờ đầu.",
        "section": "3.2",
    }

    norm_ev = normalize_raw_item(raw_item, "BYT_QD_361_2014", registry)
    assert norm_ev.concept == "stroke_thrombolysis_window"
    assert norm_ev.source_id == "BYT_QD_361_2014"
    assert norm_ev.authority_score >= 0.98
    assert norm_ev.checksum_sha256 != ""

    # Rejection of inactive / superseded source
    with pytest.raises(ValueError, match="inactive"):
        normalize_raw_item(raw_item, "BYT_QD_OLD_2005", registry)


def test_chunker_preserves_headers_and_concept_tags():
    text = (
        "## 1. Dấu hiệu cảnh báo cấp cứu\n"
        "Đau ngực dữ dội đè nặng trên 15 phút cần gọi cấp cứu 115 ngay.\n\n"
        "## 2. Hướng dẫn chống chỉ định\n"
        "Tuyệt đối chống chỉ định dùng Aspirin khi có nghi ngờ sốt xuất huyết."
    )

    chunks = chunk_clinical_text(text, source_id="TEST_GUIDELINE_001")
    assert len(chunks) == 2
    assert chunks[0].header == "Dấu hiệu cảnh báo cấp cứu"
    assert "emergency" in chunks[0].concept_tags
    assert chunks[1].header == "Hướng dẫn chống chỉ định"
    assert "contraindication" in chunks[1].concept_tags


def test_version_manager_freezes_deterministic_snapshot():
    vm = VersionManager.create_default()
    snapshot = vm.get_snapshot("2026.09.26.14")

    assert snapshot.snapshot_id == "2026.09.26.14"
    assert len(snapshot.evidence_items) >= 6
    assert snapshot.snapshot_hash != ""

    # Fetching normalized evidence from snapshot
    dvt_ev = snapshot.get_evidence("EV_DVT_001")
    assert dvt_ev is not None
    assert "huyết khối" in dvt_ev.statement
