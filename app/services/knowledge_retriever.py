"""Curated knowledge retriever for bounded medical RAG pipeline.

Indexes curated guidelines and clinical rules from app.knowledge:
- Drug-drug interactions (Dược thư Quốc gia / BYT 5948)
- Substance contraindications
- Allergy cross-reactivity matrices
- Red flag triage protocols (ESI / MTS / BYT)
- Vital sign monitoring rules
- Symptom clinical guidance
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import unicodedata
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Literal

from app.core.observability import metrics
from app.knowledge.loader import knowledge

_STOPWORDS = {
    "toi", "co", "the", "duoc", "khong", "voi", "khi", "dang", "uong",
    "bac", "si", "ke", "don", "cho", "la", "va", "o", "bi", "nay", "nao",
    "gi", "tu", "lai", "lam", "hay", "hoac", "de", "dieu", "tri", "nhung",
    "ma", "trong", "nguoi", "nha", "benh", "nhan", "tinh", "trang", "mot",
    "cac", "nhung", "den", "tai", "ve", "ra", "vao", "theo", "sau", "truoc", "di"
}

_BODY_REGION_TERMS: dict[str, tuple[str, ...]] = {
    "head": ("đầu", "sọ", "mặt", "head", "headache", "face"),
    "neck": ("cổ", "gáy", "neck"),
    "chest": ("ngực", "tim", "phổi", "chest", "heart", "lung"),
    "abdomen": ("bụng", "dạ dày", "ruột", "phân", "abdomen", "stomach", "bowel"),
    "upper_limb": ("cánh tay", "khuỷu tay", "cổ tay", "bàn tay", "ngón tay", "arm", "wrist", "hand"),
    "lower_limb": (
        "chân", "đùi", "đầu gối", "bắp chân", "cẳng chân", "cổ chân", "mắt cá chân", "bàn chân",
        "leg", "lower limb", "thigh", "knee", "calf", "ankle", "foot",
    ),
}


def _body_regions(text: str) -> set[str]:
    """Return explicit body regions without confusing e.g. ``chân`` with ``chấn``."""
    lowered = text.lower().replace("_", " ")
    regions: set[str] = set()
    for region, terms in _BODY_REGION_TERMS.items():
        if any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", lowered) for term in terms):
            regions.add(region)
    return regions


def _primary_body_regions(chunk: "RetrievedChunk") -> set[str]:
    """Infer a chunk's main region without treating cross-system safety-net text as its topic."""
    regions = _body_regions(chunk.title)
    if regions:
        return regions
    if chunk.section == "triage_emergency":
        return _body_regions(chunk.content.split("Khuyến cáo xử trí:", 1)[0])
    return set()


def _normalize(text: str) -> str:
    """Normalize text for token matching (strip diacritics and punctuation)."""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    without_marks = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", " ", without_marks)


def _tokenize(text: str, remove_stopwords: bool = True) -> set[str]:
    tokens = _normalize(text).split()
    if remove_stopwords:
        return {t for t in tokens if len(t) > 1 and t not in _STOPWORDS}
    return {t for t in tokens if len(t) > 1}


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    doc_name: str
    title: str
    section: str
    content: str
    source_reference: str
    source_url: str | None = None
    score: float = 0.0
    severity: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CLINICAL_DOCS = {"red_flag_protocols.json", "monitoring_rules.json", "crawled_clinical_guidelines.json"}
_PHARMA_DOCS = {
    "drug_interactions.json",
    "medication_incident_protocols.json",
    "contraindications.json",
    "allergy_cross_matrix.json",
    "atc_codes.json",
    "product_registry.json",
    "crawled_clinical_guidelines.json",
}


def resolve_domain(intent: str | None = None, query: str = "") -> Literal["clinical", "pharmacology"]:
    """Resolve whether an episode or question pertains to clinical/triage or pharmacology."""
    if intent in {"safety", "pharmacy", "authenticity"}:
        return "pharmacology"
    if intent in {"triage", "monitoring", "followup"}:
        return "clinical"

    # Analyze query keywords for pharmacology
    query_lower = query.lower()
    pharma_keywords = [
        "thuốc", "uống", "liều", "dược", "tác dụng phụ", "tương tác",
        "kháng sinh", "chống chỉ định", "paracetamol", "panadol", "aspirin",
        "ibuprofen", "amoxicillin", "kháng viêm", "viên", "mg", "ml",
        "uống cùng", "uống chung", "dị ứng thuốc"
    ]
    if any(k in query_lower for k in pharma_keywords):
        return "pharmacology"

    return "clinical"


class KnowledgeRetriever:
    """In-memory high-precision retriever over versioned clinical knowledge files."""

    def __init__(self) -> None:
        self._chunks: list[RetrievedChunk] = []
        self._chunk_regions: list[set[str]] = []
        self._token_index: dict[str, list[int]] = {}
        self._idf: dict[str, float] = {}
        self._intent_filters: dict[str, set[str]] = {
            "safety": {"medication_incident_protocols.json", "drug_interactions.json", "contraindications.json", "allergy_cross_matrix.json", "atc_codes.json", "crawled_clinical_guidelines.json"},
            "triage": {"red_flag_protocols.json", "crawled_clinical_guidelines.json"},
            "monitoring": {"monitoring_rules.json", "crawled_clinical_guidelines.json"},
            "authenticity": {"product_registry.json"},
        }
        self._build_index()

    def _build_index(self) -> None:
        chunks: list[RetrievedChunk] = []

        # 1. Drug interactions
        for item in knowledge.drug_interactions:
            pair = item.get("pair", [])
            pair_str = " - ".join(pair)
            cid = f"INT-{'-'.join(pair)}"
            content = (
                f"Tương tác thuốc giữa {pair[0]} và {pair[1]}. "
                f"Mức độ: {item.get('severity', 'MODERATE')}. "
                f"Cơ chế: {item.get('mechanism', 'Chưa rõ')}. "
                f"Hậu quả lâm sàng: {item.get('clinical_consequence', 'Nguy cơ tương tác thuốc')}. "
                f"Khuyến cáo xử trí: {item.get('action', 'Cần hội chẩn dược sĩ hoặc bác sĩ')}."
            )
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_name="drug_interactions.json",
                    title=f"Tương tác thuốc: {pair_str}",
                    section="drug_interaction",
                    content=content,
                    source_reference="Dược thư Quốc gia Việt Nam / Quyết định 5948/QĐ-BYT",
                    severity=item.get("severity"),
                )
            )

        # 2. Contraindications
        for ci in knowledge.contraindications:
            group = ci.get("medication_group", "")
            meds = ", ".join(ci.get("medications", []))
            conditions = ", ".join(ci.get("conditions", []))
            cid = f"CI-{ci.get('id', group)}"
            content = (
                f"Chống chỉ định nhóm thuốc {group} ({meds}): "
                f"Bệnh nền / tình trạng chống chỉ định: {conditions}. "
                f"Mức độ: {ci.get('severity', 'HIGH')} ({ci.get('tier', 'HARD_STOP')}). "
                f"Chi tiết: {ci.get('detail', '')}. "
                f"Khuyến cáo thay thế: {ci.get('recommendation', '')}."
            )
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_name="contraindications.json",
                    title=f"Chống chỉ định: {group} ({conditions})",
                    section="contraindication",
                    content=content,
                    source_reference="Dược thư Quốc gia Việt Nam / WHO Model Formulary",
                    severity=ci.get("severity"),
                )
            )

        # 3. Allergy groups
        for ag in knowledge.allergy_groups:
            name = ag.get("group_name", "")
            allergen = ag.get("primary_allergen", "")
            members = ", ".join(ag.get("cross_reactive_substances", []))
            partial = ", ".join(ag.get("partial_cross_reactive", []))
            cid = f"ALG-{ag.get('group_id', name)}"
            content = (
                f"Dị ứng nhóm thuốc {name} (dị nguyên chính: {allergen}). "
                f"Các hoạt chất dị ứng chéo mạnh: {members}. "
                f"Dị ứng chéo một phần: {partial}. "
                f"Ghi chú lâm sàng: {ag.get('cross_reactivity_note', '')}."
            )
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_name="allergy_cross_matrix.json",
                    title=f"Dị ứng nhóm: {name} ({allergen})",
                    section="allergy_cross_reactivity",
                    content=content,
                    source_reference="Dược thư Quốc gia Việt Nam / WHO ATC Cross-reactivity",
                    severity=ag.get("severity_if_confirmed"),
                )
            )

        # 4. Red flag protocols
        for rf in knowledge.red_flag_patterns:
            cat = rf.get("category", "")
            patterns = ", ".join(rf.get("patterns_vi", []))
            cid = f"RF-{rf.get('id', cat)}"
            content = (
                f"Dấu hiệu báo động đỏ cấp cứu {cat}: "
                f"Các triệu chứng nguy hiểm: {patterns}. "
                f"Phân loại ESI: Mức {rf.get('esi_level', 1)} - {rf.get('urgency', 'EMERGENCY')}. "
                f"Chuyên khoa tiếp nhận: {rf.get('specialty', {}).get('label', 'Cấp cứu')}. "
                f"Khuyến cáo xử trí: {rf.get('advice', 'Gọi 115 hoặc đến cơ sở cấp cứu ngay lập tức')}."
            )
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_name="red_flag_protocols.json",
                    title=f"Báo động đỏ cấp cứu: {cat}",
                    section="triage_emergency",
                    content=content,
                    source_reference="Hướng dẫn phân loại cấp cứu Bộ Y tế / Manchester Triage System",
                    severity=rf.get("urgency"),
                )
            )

        # 5. Symptom guidance
        for symp in knowledge.symptom_guidance:
            name = str(symp.get("symptom_vi") or symp.get("topic") or "general")
            cid = f"SYM-{symp.get('symptom_id') or symp.get('topic') or name}"
            keywords = ", ".join(str(value) for value in symp.get("keywords", []))
            red_flags = " ".join(
                str(value) for value in (symp.get("red_flags_vi") or symp.get("safety_net") or [])
            )
            self_care = " ".join(
                str(value) for value in (symp.get("self_care") or [symp.get("home_care_vi", "")])
            )
            content = (
                f"Hướng dẫn triệu chứng {name}. Từ khóa: {keywords}. "
                f"Mô tả: {symp.get('description_vi') or symp.get('summary', '')}. "
                f"Dấu hiệu nguy hiểm cần khám ngay: {red_flags}. "
                f"Chăm sóc ban đầu: {self_care}. Khuyến cáo: {symp.get('advice', '')}."
            )
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_name="red_flag_protocols.json",
                    title=f"Hướng dẫn triệu chứng: {name}",
                    section="symptom_guidance",
                    content=content,
                    source_reference="NICE Guidelines / Hướng dẫn chẩn đoán BYT",
                )
            )

        # 6. Monitoring rules
        for rule in knowledge.monitoring_rules:
            metric = rule.get("metric", "")
            cid = f"MON-{metric}"
            # Keep the actual thresholds and explanatory fields. These rules
            # do not contain a nested "thresholds" object; indexing an empty
            # default hid the evidence used by the monitoring runtime.
            content = (
                f"Quy tắc theo dõi sinh hiệu {metric}. "
                + json.dumps(rule, ensure_ascii=False, sort_keys=True)
            )
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_name="monitoring_rules.json",
                    title=f"Theo dõi sinh hiệu: {metric}",
                    section="vital_sign_rule",
                    content=content,
                    source_reference="Quy chuẩn theo dõi dấu hiệu sinh tồn lâm sàng",
                )
            )

        # Medication incidents were used by the safety engine but missing
        # from retrieval. Preserve approval status: local policy is evidence
        # provenance, never proof of independent clinical validation.
        incident_file = knowledge.files.get("medication_incident_protocols.json")
        incident_meta = incident_file.data.get("_meta", {}) if incident_file else {}
        for protocol in knowledge.reported_ingestion_protocols:
            chunks.append(RetrievedChunk(
                chunk_id=protocol["id"],
                doc_name="medication_incident_protocols.json",
                title="Sự cố dùng thuốc: " + protocol.get("ingredient", ""),
                section="medication_incident",
                content=json.dumps(protocol, ensure_ascii=False, sort_keys=True),
                source_reference=json.dumps(incident_meta, ensure_ascii=False, sort_keys=True),
                severity=protocol.get("risk"),
            ))

        # 7. Optional Crawled Clinical Guidelines (Crawl4AI & refined web sources)
        crawled_file = Path(__file__).resolve().parent.parent / "knowledge" / "crawled_clinical_guidelines.json"
        if crawled_file.exists():
            try:
                crawled_data = json.loads(crawled_file.read_text(encoding="utf-8"))
                for gl in crawled_data.get("guidelines", []):
                    cid = gl.get("guideline_id", "")
                    topic = gl.get("topic", "")
                    sec = gl.get("section", "")
                    content = gl.get("content", "")

                    # Map authoritative international topics to Vietnamese clinical aliases
                    vi_aliases = []
                    lower_text = (topic + " " + content).lower()
                    if "neck pain" in lower_text or "stiff neck" in lower_text:
                        vi_aliases.append("đau cổ vai gáy cứng cổ mỏi cổ thoái hóa đốt sống cổ chèn ép rễ thần kinh")
                    if "chest pain" in lower_text or "heart attack" in lower_text:
                        vi_aliases.append("đau ngực tức ngực nhồi máu cơ tim hội chứng vành cấp khó thở cấp cứu tim mạch")
                    if "headache" in lower_text or "migraine" in lower_text:
                        vi_aliases.append("đau đầu nhức đầu đau nửa đầu đau đầu căng cơ xuất huyết dưới nhện")
                    if "paracetamol" in lower_text:
                        vi_aliases.append("thuốc hạ sốt giảm đau paracetamol acetaminophen liều dùng quá liều tổn thương gan")
                    if "gord" in lower_text or "dyspepsia" in lower_text or "reflux" in lower_text:
                        vi_aliases.append("trào ngược dạ dày thực quản đau dạ dày viêm loét dạ dày ợ chua ợ nóng khó tiêu")

                    alias_str = " ".join(vi_aliases)
                    full_content = f"Hướng dẫn điều trị chuyên sâu {topic}. Phần {sec}: {content} Từ khóa lâm sàng: {alias_str}"
                    chunks.append(
                        RetrievedChunk(
                            chunk_id=cid,
                            doc_name="crawled_clinical_guidelines.json",
                            title=f"Hướng dẫn lâm sàng: {topic} ({sec})",
                            section=sec,
                            content=full_content,
                            source_reference=gl.get("source_authority", "Crawl4AI Web Guidelines"),
                            source_url=gl.get("source_uri"),
                        )
                    )
            except Exception:
                pass

        # 8. Product registry items
        for prod in knowledge.product_registry:
            code = prod.get("product_code", "")
            pname = prod.get("name", "")
            cid = f"PROD-{code}"
            content = (
                f"Thuốc biệt dược / sản phẩm: {pname} (Mã SP: {code}, GTIN: {prod.get('gtin', '')}). "
                f"Nhà sản xuất: {prod.get('manufacturer', '')}. Trạng thái lưu hành: {prod.get('status', 'active')}."
            )
            chunks.append(
                RetrievedChunk(
                    chunk_id=cid,
                    doc_name="product_registry.json",
                    title=f"Sản phẩm thuốc: {pname}",
                    section="product_authenticity",
                    content=content,
                    source_reference="Cơ sở dữ liệu đăng ký lưu hành thuốc MedGuard / Bộ Y tế",
                )
            )

        self._chunks = chunks
        self._chunk_regions = [_primary_body_regions(chunk) for chunk in chunks]

        # Build inverted index and compute IDF
        token_index: dict[str, list[int]] = {}
        total_docs = len(chunks)

        for idx, chunk in enumerate(chunks):
            # Index tokens with and without stopwords
            title_tokens = _tokenize(chunk.title, remove_stopwords=True)
            content_tokens = _tokenize(chunk.content, remove_stopwords=True)
            chunk_tokens = title_tokens | content_tokens
            for token in chunk_tokens:
                token_index.setdefault(token, []).append(idx)

        self._token_index = token_index

        # Calculate IDF for each token
        idf: dict[str, float] = {}
        for token, doc_indices in token_index.items():
            df = len(set(doc_indices))
            idf[token] = math.log((total_docs + 1.0) / (df + 0.5)) + 1.2
        self._idf = idf

    def retrieve(
        self,
        query: str,
        *,
        intent: str | None = None,
        domain: Literal["clinical", "pharmacology"] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Retrieve top-K most relevant chunks for query with optional intent and domain filtering."""
        start = perf_counter()
        effective_domain = domain or resolve_domain(intent, query)
        query_tokens = _tokenize(query, remove_stopwords=True)
        if not query_tokens:
            # Fallback to without removing stopwords if empty
            query_tokens = _tokenize(query, remove_stopwords=False)
        if not query_tokens:
            return []

        allowed_docs = self._intent_filters.get(intent) if intent else None
        domain_docs = _CLINICAL_DOCS if effective_domain == "clinical" else _PHARMA_DOCS

        scores: dict[int, float] = {}
        query_norm = _normalize(query)
        query_regions = _body_regions(query) if effective_domain == "clinical" else set()
        domain_boosted: set[int] = set()

        for token in query_tokens:
            matching_indices = self._token_index.get(token, [])
            token_idf = self._idf.get(token, 1.0)

            for idx in matching_indices:
                chunk = self._chunks[idx]
                if allowed_docs and chunk.doc_name not in allowed_docs:
                    continue

                chunk_regions = self._chunk_regions[idx]
                if query_regions and chunk_regions and query_regions.isdisjoint(chunk_regions):
                    continue

                chunk_title_norm = _normalize(chunk.title)
                chunk_content_norm = _normalize(chunk.content)

                score = scores.get(idx, 0.0)

                # Base match weighted by IDF
                score += 2.0 * token_idf

                # Domain specialization boost
                if chunk.doc_name in domain_docs and idx not in domain_boosted:
                    score += 5.0
                    domain_boosted.add(idx)

                # Title boost
                if token in chunk_title_norm:
                    score += 4.0 * token_idf

                # Exact phrase matching
                if query_norm in chunk_content_norm or query_norm in chunk_title_norm:
                    score += 10.0

                scores[idx] = score

        if query_regions:
            scores = {
                idx: score
                for idx, score in scores.items()
                if self._chunk_regions[idx] & query_regions
            }

        ranked_indices = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)[:top_k]

        results = [
            RetrievedChunk(
                chunk_id=self._chunks[i].chunk_id,
                doc_name=self._chunks[i].doc_name,
                title=self._chunks[i].title,
                section=self._chunks[i].section,
                content=self._chunks[i].content,
                source_reference=self._chunks[i].source_reference,
                source_url=self._chunks[i].source_url,
                score=round(scores[i], 3),
                severity=self._chunks[i].severity,
            )
            for i in ranked_indices
        ]

        duration = perf_counter() - start
        metrics.observe_histogram("medguard_rag_retrieval_latency_seconds", duration)
        metrics.observe_histogram("medguard_rag_retrieval_chunks_count", float(len(results)))

        return results


# Global singleton
knowledge_retriever = KnowledgeRetriever()
