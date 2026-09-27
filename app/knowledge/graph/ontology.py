"""Clinical Ontology and Medical Knowledge Graph Engine.

Provides:
1. In-process Knowledge Graph traversal for hard clinical relations (drug interactions,
   contraindications, red-flag links, differential diagnoses).
2. Deep concept resolution mapping Vietnamese lay terms, teencode, and common typos
   to canonical clinical entities.
"""

from __future__ import annotations

import unicodedata
from pydantic import BaseModel
from app.knowledge.graph.entities import MedicalEntity
from app.knowledge.graph.relations import MedicalRelation


def _normalize_token(text: str) -> str:
    """Lowercases, strips accents, and cleans punctuation for robust matching."""
    text = text.lower().strip()
    text = text.replace("đ", "d").replace("Đ", "d")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())


class ConceptResolution(BaseModel):
    """Detailed resolution result distinguishing drug classes from specific active ingredients."""
    raw_text: str
    resolved_concept_id: str | None
    is_class: bool = False
    specific_drug_id: str | None = None
    clarification_required: bool = False
    confidence: float = 1.0


class ClinicalOntology:
    """In-process Knowledge Graph & Ontological Concept Resolver."""

    def __init__(self) -> None:
        self.entities: dict[str, MedicalEntity] = {}
        self.relations: list[MedicalRelation] = []
        self._alias_map: dict[str, str] = {}

    def add_entity(self, entity: MedicalEntity) -> None:
        self.entities[entity.entity_id] = entity
        self._alias_map[_normalize_token(entity.name)] = entity.entity_id
        for alias in entity.aliases:
            self._alias_map[_normalize_token(alias)] = entity.entity_id

    def add_relation(self, relation: MedicalRelation) -> None:
        self.relations.append(relation)

    def resolve_concept(self, text: str) -> str | None:
        """Resolves free-form text or alias to a canonical entity_id."""
        clean = _normalize_token(text)
        if clean in self._alias_map:
            return self._alias_map[clean]

        # Substring matching for phrases
        for alias, eid in self._alias_map.items():
            if len(alias) >= 4 and alias in clean:
                return eid
        return None

    def resolve_concept_details(self, text: str) -> ConceptResolution:
        """Resolves concept with awareness of drug classes vs specific active ingredients.

        Flags clarification_required when user mentions a broad drug class rather than a specific formulation.
        """
        eid = self.resolve_concept(text)
        if not eid:
            return ConceptResolution(raw_text=text, resolved_concept_id=None, confidence=0.0)

        ent = self.entities.get(eid)
        if ent and ent.entity_type == "DrugClass":
            return ConceptResolution(
                raw_text=text,
                resolved_concept_id=eid,
                is_class=True,
                specific_drug_id=None,
                clarification_required=True,
                confidence=0.95,
            )

        return ConceptResolution(
            raw_text=text,
            resolved_concept_id=eid,
            is_class=False,
            specific_drug_id=eid,
            clarification_required=False,
            confidence=0.98,
        )

    def resolve_all_concepts(self, text: str) -> list[str]:
        """Extracts all matched canonical concept IDs found in a user utterance."""
        clean = _normalize_token(text)
        matched: set[str] = set()
        for alias, eid in self._alias_map.items():
            if len(alias) >= 3 and alias in clean:
                matched.add(eid)
        return sorted(list(matched))

    def query_relations(
        self,
        subject_id: str | None = None,
        predicate: str | None = None,
        object_id: str | None = None,
    ) -> list[MedicalRelation]:
        """Queries graph edges matching subject, predicate, and/or object filters."""
        results: list[MedicalRelation] = []
        for rel in self.relations:
            if rel.status != "ACTIVE":
                continue
            if subject_id and rel.subject_id != subject_id:
                continue
            if predicate and rel.predicate != predicate:
                continue
            if object_id and rel.object_id != object_id:
                continue
            results.append(rel)
        return results

    def query_interactions(self, drug_a_name: str, drug_b_name: str) -> list[MedicalRelation]:
        """Queries for adverse interactions between two drugs or drug classes."""
        eid_a = self.resolve_concept(drug_a_name)
        eid_b = self.resolve_concept(drug_b_name)
        if not eid_a or not eid_b:
            return []

        # Check direct or parent class relations
        candidates_a = [eid_a]
        ent_a = self.entities.get(eid_a)
        if ent_a and ent_a.parent_class_id:
            candidates_a.append(ent_a.parent_class_id)

        candidates_b = [eid_b]
        ent_b = self.entities.get(eid_b)
        if ent_b and ent_b.parent_class_id:
            candidates_b.append(ent_b.parent_class_id)

        results: list[MedicalRelation] = []
        for a in candidates_a:
            for b in candidates_b:
                results.extend(self.query_relations(subject_id=a, predicate="interacts_with", object_id=b))
                results.extend(self.query_relations(subject_id=b, predicate="interacts_with", object_id=a))

        # Deduplicate
        seen = set()
        deduped = []
        for r in results:
            key = (r.subject_id, r.predicate, r.object_id)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped

    def query_contraindications(self, drug_name: str, condition_name: str) -> list[MedicalRelation]:
        """Queries for absolute or relative contraindications."""
        drug_id = self.resolve_concept(drug_name)
        cond_id = self.resolve_concept(condition_name)
        if not drug_id or not cond_id:
            return []

        candidates_drug = [drug_id]
        ent = self.entities.get(drug_id)
        if ent and ent.parent_class_id:
            candidates_drug.append(ent.parent_class_id)

        results: list[MedicalRelation] = []
        for d in candidates_drug:
            results.extend(self.query_relations(subject_id=d, predicate="contraindicated_in", object_id=cond_id))
        return results

    @classmethod
    def create_default(cls) -> ClinicalOntology:
        ont = cls()

        # -------------------------------------------------------------
        # 1. DRUG CLASSES & SPECIFIC ACTIVE INGREDIENTS
        # -------------------------------------------------------------
        # Class: Anticoagulants
        ont.add_entity(
            MedicalEntity(
                entity_id="drug_class.anticoagulant",
                name="Thuốc chống đông",
                entity_type="DrugClass",
                aliases=["thuoc chong dong", "thuốc kháng đông", "thuoc khang dong", "thuoc loang mau", "thuốc loãng máu"],
            )
        )
        # Specific: Warfarin
        ont.add_entity(
            MedicalEntity(
                entity_id="drug.warfarin",
                name="Warfarin",
                entity_type="Drug",
                parent_class_id="drug_class.anticoagulant",
                aliases=["warfarin", "coumadin"],
            )
        )
        # Specific: Acenocoumarol (Sintrom) - Correctly differentiated!
        ont.add_entity(
            MedicalEntity(
                entity_id="drug.acenocoumarol",
                name="Acenocoumarol",
                entity_type="Drug",
                parent_class_id="drug_class.anticoagulant",
                aliases=["sintrom", "acenocoumarol"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="drug.ibuprofen",
                name="Ibuprofen",
                entity_type="Drug",
                aliases=["ibu", "gofen", "thuoc giam dau khop", "nsaid"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="drug.aspirin",
                name="Aspirin",
                entity_type="Drug",
                aliases=["acid acetylsalicylic", "aspegic", "thuoc tim mach aspirin"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="drug.paracetamol",
                name="Paracetamol",
                entity_type="Drug",
                aliases=["para", "panadol", "efferalgan", "hapacol", "thuoc ha sot"],
            )
        )

        # -------------------------------------------------------------
        # 2. DISEASE & CONDITION ENTITIES
        # -------------------------------------------------------------
        ont.add_entity(
            MedicalEntity(
                entity_id="disease.dvt",
                name="Huyết khối tĩnh mạch sâu (DVT)",
                entity_type="Disease",
                aliases=["dvt", "huyet khoi tinh mach", "cuc mau dong tinh mach"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="disease.muscle_strain",
                name="Căng mỏi cơ",
                entity_type="Disease",
                aliases=["cang co", "moi co", "dau bap chan", "dau co bap chuoi"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="disease.dengue",
                name="Sốt xuất huyết Dengue",
                entity_type="Disease",
                aliases=["sot xuat huyet", "dengue", "sxk"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="disease.peptic_ulcer",
                name="Loét dạ dày tá tràng",
                entity_type="Disease",
                aliases=["loet da day", "dau da day", "xuat huyet tieu hoa"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="disease.acs",
                name="Hội chứng mạch vành cấp (ACS)",
                entity_type="Disease",
                aliases=["nhoi mau co tim", "con dau that nguc", "acs", "thieu mau co tim"],
            )
        )

        # -------------------------------------------------------------
        # 3. SYMPTOMS & RED FLAGS
        # -------------------------------------------------------------
        ont.add_entity(
            MedicalEntity(
                entity_id="symptom.calf_pain",
                name="Đau bắp chân",
                entity_type="Symptom",
                aliases=["dau chan", "moi bap chan", "cang bap chuoi"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="red_flag.unilateral_leg_edema",
                name="Sưng đau một bên bắp chân",
                entity_type="RedFlag",
                aliases=["sung mot ben chan", "phu bap chan mot ben", "sung lech chan"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="red_flag.thunderclap_headache",
                name="Đau đầu sét đánh",
                entity_type="RedFlag",
                aliases=["dau dau set danh", "dau nhu bua bo", "dau dau du doi dot ngot"],
            )
        )
        ont.add_entity(
            MedicalEntity(
                entity_id="red_flag.fast_positive",
                name="Dấu hiệu FAST đột quỵ",
                entity_type="RedFlag",
                aliases=["meo mieng", "yeu liet tay chan", "noi kho dot ngot"],
            )
        )

        # -------------------------------------------------------------
        # 4. GRAPH RELATIONS (WITH PROVENANCE)
        # -------------------------------------------------------------
        ont.add_relation(
            MedicalRelation(
                subject_id="drug.warfarin",
                predicate="interacts_with",
                object_id="drug.ibuprofen",
                severity="major",
                mechanism="Tăng nguy cơ xuất huyết tiêu hóa và biến chứng chảy máu nghiêm trọng do tác động hiệp đồng.",
                source_id="BYT_DUOC_THU_2022",
                version="3.0",
            )
        )
        ont.add_relation(
            MedicalRelation(
                subject_id="drug.acenocoumarol",
                predicate="interacts_with",
                object_id="drug.ibuprofen",
                severity="major",
                mechanism="Acenocoumarol (Sintrom) phối hợp với Ibuprofen làm tăng nguy cơ chảy máu đường tiêu hóa và kéo dài thời gian đông máu.",
                source_id="BYT_DUOC_THU_2022",
                version="3.0",
            )
        )
        ont.add_relation(
            MedicalRelation(
                subject_id="drug_class.anticoagulant",
                predicate="interacts_with",
                object_id="drug.ibuprofen",
                severity="major",
                mechanism="Nhóm thuốc chống đông nói chung khi phối hợp với NSAID (Ibuprofen) làm tăng đáng kể nguy cơ xuất huyết tiêu hóa.",
                source_id="BYT_DUOC_THU_2022",
                version="3.0",
            )
        )
        ont.add_relation(
            MedicalRelation(
                subject_id="drug.aspirin",
                predicate="contraindicated_in",
                object_id="disease.dengue",
                severity="critical",
                mechanism="Aspirin ức chế kết tập tiểu cầu không hồi phục, làm trầm trọng nguy cơ xuất huyết ồ ạt trong sốt xuất huyết.",
                source_id="BYT_DUOC_THU_2022",
                version="3.0",
            )
        )
        ont.add_relation(
            MedicalRelation(
                subject_id="drug.aspirin",
                predicate="contraindicated_in",
                object_id="disease.peptic_ulcer",
                severity="major",
                mechanism="Ức chế COX-1 làm giảm tổng hợp prostaglandin bảo vệ niêm mạc dạ dày, gây bùng phát loét và chảy máu.",
                source_id="BYT_DUOC_THU_2022",
                version="3.0",
            )
        )
        ont.add_relation(
            MedicalRelation(
                subject_id="disease.dvt",
                predicate="has_red_flag",
                object_id="red_flag.unilateral_leg_edema",
                severity="major",
                mechanism="Huyết khối làm tắc nghẽn lưu thông tĩnh mạch sâu gây sưng phù và ứ trệ tuần hoàn chi dưới một bên.",
                source_id="NICE_NG158_2020",
                version="1.2",
            )
        )
        ont.add_relation(
            MedicalRelation(
                subject_id="disease.dvt",
                predicate="differential_of",
                object_id="disease.muscle_strain",
                severity="moderate",
                mechanism="Căng mỏi cơ bắp chân là chẩn đoán phân biệt thông thường cần phân biệt với DVT thông qua dấu hiệu sưng một bên.",
                source_id="BYT_QD_361_2014",
                version="1.0",
            )
        )

        return ont


# Global default instance
default_ontology = ClinicalOntology.create_default()
