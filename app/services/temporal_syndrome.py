from __future__ import annotations

from dataclasses import dataclass

from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text


@dataclass(frozen=True)
class TemporalSyndromeAssessment:
    urgency: str = "ROUTINE"
    syndrome_id: str | None = None
    supporting_features: tuple[str, ...] = ()
    rationale: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "urgency": self.urgency,
            "syndrome_id": self.syndrome_id,
            "supporting_features": list(self.supporting_features),
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


def evaluate_temporal_syndrome(text: str) -> TemporalSyndromeAssessment:
    """Evaluate relational/temporal patterns that cannot be represented by a bag of words.

    The first governed pattern captures abdominal pain migration with supporting
    inflammatory/mechanical features.  It intentionally requires relations and
    multiple supporting features rather than a single location keyword.
    """
    norm = normalize_search_text(text)

    periumbilical = any(
        contains_affirmed_phrase(norm, marker)
        for marker in ("dau quanh ron", "quanh ron", "dau gan ron", "dau vung ron")
    )
    rlq = any(
        contains_affirmed_phrase(norm, marker)
        for marker in (
            "bung duoi ben phai",
            "dau bung duoi ben phai",
            "ho chau phai",
            "goc duoi ben phai bung",
        )
    )
    migration = any(marker in norm for marker in ("chuyen xuong", "chuyen sang", "di chuyen xuong", "lan xuong"))

    support: list[str] = []
    if any(marker in norm for marker in ("ho thi dau", "ho dau", "dau khi ho")):
        support.append("worse_with_cough")
    if any(marker in norm for marker in ("di lai thi dau", "dau khi di lai", "van dong dau", "cu dong dau")):
        support.append("worse_with_movement")
    if contains_affirmed_phrase(norm, "buon non") or contains_affirmed_phrase(norm, "non"):
        support.append("nausea_or_vomiting")
    if contains_affirmed_phrase(norm, "sot") or any(marker in norm for marker in ("on lanh", "lanh run")):
        support.append("fever_or_chills")

    if periumbilical and rlq and migration and len(support) >= 2:
        return TemporalSyndromeAssessment(
            urgency="URGENT",
            syndrome_id="MIGRATORY_RLQ_ABDOMINAL_PATTERN",
            supporting_features=tuple(["periumbilical_to_rlq_migration", *support]),
            rationale=(
                "Đau bụng có diễn tiến chuyển vị trí từ quanh rốn xuống bụng dưới phải kèm nhiều dấu hiệu hỗ trợ cần được đánh giá trực tiếp sớm trong ngày."
            ),
            confidence=0.95,
        )

    return TemporalSyndromeAssessment()
