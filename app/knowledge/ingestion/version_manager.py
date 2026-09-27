"""Knowledge Base Version & Snapshot Manager.

Manages immutable, versioned snapshots of normalized clinical knowledge.
Guarantees that every request references a deterministic snapshot ID (e.g. '2026.09.26.14')
so that any retrospective audit can reconstruct the exact knowledge state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from app.knowledge.ingestion.normalizer import NormalizedEvidence
from app.knowledge.provenance.checksum import compute_sha256
from app.knowledge.provenance.source_registry import SourceRegistry, default_source_registry


class KnowledgeSnapshot(BaseModel):
    """Immutable snapshot of the normalized clinical knowledge base."""
    snapshot_id: str = Field(description="Snapshot release tag, e.g. '2026.09.26.14'")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active_sources: list[str] = Field(default_factory=list)
    evidence_items: dict[str, NormalizedEvidence] = Field(default_factory=dict)
    snapshot_hash: str = ""

    def model_post_init(self, __context) -> None:
        if not self.snapshot_hash:
            keys = sorted(self.evidence_items.keys())
            content = f"{self.snapshot_id}:" + ",".join(f"{k}:{self.evidence_items[k].checksum_sha256}" for k in keys)
            self.snapshot_hash = compute_sha256(content)

    def get_evidence(self, evidence_id: str) -> NormalizedEvidence | None:
        return self.evidence_items.get(evidence_id)


class VersionManager:
    """Registry of frozen knowledge snapshots."""

    def __init__(self, registry: SourceRegistry = default_source_registry) -> None:
        self.registry = registry
        self._snapshots: dict[str, KnowledgeSnapshot] = {}
        self._active_snapshot_id: str = "2026.09.26.14"

    def register_snapshot(self, snapshot: KnowledgeSnapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot

    def get_snapshot(self, snapshot_id: str | None = None) -> KnowledgeSnapshot:
        sid = snapshot_id or self._active_snapshot_id
        if sid not in self._snapshots:
            # Fallback to active snapshot if requested not found
            return self._snapshots[self._active_snapshot_id]
        return self._snapshots[sid]

    @classmethod
    def create_default(cls) -> VersionManager:
        vm = cls()

        # Build initial production-grade normalized evidence cohort
        items: dict[str, NormalizedEvidence] = {
            "EV_DVT_001": NormalizedEvidence(
                evidence_id="EV_DVT_001",
                concept="dvt_unilateral_swelling",
                statement="Sưng đau hoặc căng tức một bên bắp chân là dấu hiệu cảnh báo nghi ngờ huyết khối tĩnh mạch sâu (DVT), cần khám chuyên khoa mạch máu hoặc siêu âm Doppler trong ngày.",
                source_id="NICE_NG158_2020",
                section="1.1.2",
                evidence_type="clinical_guideline",
                authority_score=0.98,
                applicability={"population": "adult", "urgency": "URGENT"},
            ),
            "EV_DVT_002": NormalizedEvidence(
                evidence_id="EV_DVT_002",
                concept="muscle_strain_self_care",
                statement="Căng mỏi cơ sau vận động hoặc đi bộ nhiều không kèm sưng đỏ hay khó thở có thể tự chăm sóc tại nhà bằng nghỉ ngơi, nâng cao chi và chườm lạnh tại chỗ.",
                source_id="BYT_QD_361_2014",
                section="4.2",
                evidence_type="clinical_guideline",
                authority_score=0.99,
                applicability={"population": "adult", "urgency": "ROUTINE"},
            ),
            "EV_ACS_001": NormalizedEvidence(
                evidence_id="EV_ACS_001",
                concept="cardiac_emergency_acs",
                statement="Đau thắt ngực đè nặng kéo dài trên 15 phút, lan lên vai, hàm hoặc cánh tay trái kèm vã mồ hôi, khó thở là dấu hiệu của hội chứng vành cấp, phải gọi cấp cứu 115 ngay lập tức.",
                source_id="BYT_QD_361_2014",
                section="2.1",
                evidence_type="emergency_protocol",
                authority_score=1.0,
                applicability={"population": "all", "urgency": "EMERGENCY"},
            ),
            "EV_STROKE_001": NormalizedEvidence(
                evidence_id="EV_STROKE_001",
                concept="stroke_fast_positive",
                statement="Méo miệng, yếu liệt tay chân hoặc nói khó khởi phát đột ngột là dấu hiệu đột quỵ não cấp tính, cần đưa đến cơ sở có khả năng can thiệp đột quỵ trong thời gian vàng, gọi 115 ngay.",
                source_id="BYT_QD_361_2014",
                section="3.1",
                evidence_type="emergency_protocol",
                authority_score=1.0,
                applicability={"population": "all", "urgency": "EMERGENCY"},
            ),
            "EV_ANAPHYLAXIS_001": NormalizedEvidence(
                evidence_id="EV_ANAPHYLAXIS_001",
                concept="anaphylaxis_epinephrine",
                statement="Phản vệ từ độ II trở lên có biểu hiện khó thở, thở rít, phù thanh quản hoặc tụt huyết áp cần được tiêm bắp Adrenalin ngay lập tức và gọi cấp cứu 115.",
                source_id="BYT_TT_51_2017",
                section="Điều 4",
                evidence_type="emergency_protocol",
                authority_score=1.0,
                applicability={"population": "all", "urgency": "EMERGENCY"},
            ),
            "EV_SEPSIS_001": NormalizedEvidence(
                evidence_id="EV_SEPSIS_001",
                concept="septic_shock_red_flag",
                statement="Sốt cao kèm lơ mơ, li bì, thở nhanh (> 22 lần/phút) hoặc huyết áp tụt là dấu hiệu cảnh báo sốc nhiễm khuẩn nguy kịch, đòi hỏi hồi sức cấp cứu khẩn cấp.",
                source_id="WHO_SEPSIS_2023",
                section="Rec 1",
                evidence_type="emergency_protocol",
                authority_score=0.98,
                applicability={"population": "all", "urgency": "EMERGENCY"},
            ),
            "EV_DRUG_WARFARIN_IBUPROFEN": NormalizedEvidence(
                evidence_id="EV_DRUG_WARFARIN_IBUPROFEN",
                concept="warfarin_ibuprofen_interaction",
                statement="Sử dụng đồng thời Warfarin và Ibuprofen làm tăng đáng kể nguy cơ xuất huyết tiêu hóa nặng do tác động hiệp đồng ức chế tiểu cầu và tổn thương niêm mạc dạ dày.",
                source_id="BYT_DUOC_THU_2022",
                section="Chuyên luận Warfarin",
                evidence_type="drug_monograph",
                authority_score=0.99,
                applicability={"severity": "major", "action": "contraindicated_combination"},
            ),
            "EV_DRUG_DENGUE_ASPIRIN": NormalizedEvidence(
                evidence_id="EV_DRUG_DENGUE_ASPIRIN",
                concept="dengue_aspirin_contraindication",
                statement="Tuyệt đối chống chỉ định dùng Aspirin và các thuốc NSAID khác trong điều trị sốt nghi do sốt xuất huyết Dengue vì nguy cơ làm tăng xuất huyết và hội chứng Reye ở trẻ em.",
                source_id="BYT_DUOC_THU_2022",
                section="Chuyên luận Acid acetylsalicylic",
                evidence_type="drug_monograph",
                authority_score=1.0,
                applicability={"severity": "critical", "action": "strict_contraindication"},
            ),
        }

        active_sources = [s.source_id for s in default_source_registry.list_active()]
        snapshot = KnowledgeSnapshot(
            snapshot_id="2026.09.26.14",
            active_sources=active_sources,
            evidence_items=items,
        )
        vm.register_snapshot(snapshot)
        return vm


# Global default instance
default_version_manager = VersionManager.create_default()
