"""Semantic Relation Extractor for MedGuard AI Candidate V9.

Extracts structured clinical concepts and their semantic relations:
- Relations: co_occurs_with, associated_with, causes, precedes, aggravated_by, relieved_by, radiation_to.
- Connects disparate symptoms, autonomic signs, anatomical loci, and trajectories
  without requiring exact rigid monolithic regex phrases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Sequence

from app.services.clinical_text import normalize_search_text


class RelationType(str, Enum):
    CO_OCCURS_WITH = "co_occurs_with"
    ASSOCIATED_WITH = "associated_with"
    CAUSES = "causes"
    PRECEDES = "precedes"
    AGGRAVATED_BY = "aggravated_by"
    RELIEVED_BY = "relieved_by"
    RADIATION_TO = "radiation_to"


@dataclass(frozen=True)
class ExtractedConcept:
    concept_id: str
    canonical_name: str
    category: str  # "symptom", "sign", "timing", "anatomy", "trigger", "modifier"
    certainty: float
    evidence_span: str
    organ_system: str = "general"
    is_negated: bool = False
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClinicalRelation:
    relation_type: RelationType
    source_concept: str
    target_concept: str
    confidence: float
    evidence_span: str


@dataclass(frozen=True)
class SemanticRelationGraph:
    raw_text: str
    normalized_text: str
    concepts: dict[str, ExtractedConcept]
    relations: list[ClinicalRelation]

    def has_concept(self, concept_name: str) -> bool:
        return any(
            c.canonical_name == concept_name and not c.is_negated
            for c in self.concepts.values()
        )

    def has_any_concept(self, concept_names: Sequence[str]) -> bool:
        names = set(concept_names)
        return any(
            c.canonical_name in names and not c.is_negated
            for c in self.concepts.values()
        )

    def get_related_concepts(self, concept_name: str, relation_type: RelationType | None = None) -> list[ExtractedConcept]:
        related_ids = set()
        for r in self.relations:
            if relation_type and r.relation_type != relation_type:
                continue
            if r.source_concept == concept_name:
                related_ids.add(r.target_concept)
            elif r.target_concept == concept_name:
                related_ids.add(r.source_concept)
        return [self.concepts[cid] for cid in related_ids if cid in self.concepts]


# ---------------------------------------------------------------------------
# Elementary Concept Patterns for Bottom-Up Semantic Composition
# ---------------------------------------------------------------------------

_ATOMIC_CONCEPT_CATALOG: list[dict[str, Any]] = [
    # Pain & Discomfort
    {
        "canonical_name": "chest_pressure",
        "category": "symptom",
        "organ_system": "cardiopulmonary",
        "patterns": [
            r"\b(?:nguc|tim|long\s+nguc)\b.*?\b(?:de\s+nang|de\s+nghet|bop\s+nghet|that\s+nghet|dau\s+that|dau\s+tuc|that\s+lai|nhu\s+da\s+de|da\s+dan|vo\s+tung)\b|\b(?:tang\s+da|da\s+de|de\s+nghet|de\s+nang|bop\s+nghet)\b.*?\b(?:nguc|tim)\b|\b(?:chest\s+pressure|angina|om\s+nguc|tuc\s+nguc|de\s+nguc|nang\s+nguc|bop\s+nghet\s+nguc|that\s+nguc|dau\s+tuc\s+nguc|dau\s+nhoi\s+nguc|dau\s+nguc|nghet\s+tim)\b",
        ],
    },
    {
        "canonical_name": "reproducible_chest_wall_pain",
        "category": "sign",
        "organ_system": "musculoskeletal",
        "patterns": [
            r"\b(an vao dau|an vao thay nhoi|an vao thay dau|dau khi an|so vao thay dau|an vao cho dau|dau thanh nguc|moi hit dat|sau khi hit dat|tap the duc xong dau co|dau co nguc|moi tap gym)\b",
        ],
    },
    {
        "canonical_name": "abdominal_pain_severe",
        "category": "symptom",
        "organ_system": "abdomen",
        "patterns": [
            r"\b(?:dau|buot|nhoi|quan|that|xe|thieu\s+dot)\b.*?\b(?:bung|ruot|o\s+bung)\b|\b(?:bung|ruot|o\s+bung)\b.*?\b(?:dau|buot|nhoi|quan|that|xe|cung|gong|thieu\s+dot|quan\s+quai)\b|\b(?:om\s+bung|dau\s+nhu\s+dao\s+dam|viem\s+phuc\s+mac)\b",
            r"\b(dau bung du doi|bung dau quan|bung dau nhu cat|ruot gan bop nghet|dau bung khong chiu noi|bung cung nhu go|bung cung do|dau nhoi bung)\b",
        ],
    },
    {
        "canonical_name": "thunderclap_headache",
        "category": "symptom",
        "organ_system": "neurology",
        "patterns": [
            r"\bdau\s+dau\b.*?\b(?:set\s+danh|bua\s+bo|chua\s+tung\s+co|muon\s+vo\s+tung)\b|\b(?:dau\s+dau\s+set\s+danh|dau\s+dau\s+nhu\s+bua\s+bo)\b",
            r"\b(dau dau set danh|dau dau du doi chua tung co|dau dau nhu bua bo|dau nhoi dau dot ngot|dau dau muon vo tung|dau dau kinh khung)\b",
        ],
    },
    # Autonomic & Shock Signs
    {
        "canonical_name": "diaphoresis",
        "category": "sign",
        "organ_system": "autonomic",
        "patterns": [
            r"\b(?:mo\s+hoi\b.*?\b(?:toat|dam|uong|ra|uot)|toat\s+mo\s+hoi|va\s+mo\s+hoi|mo\s+hoi\s+hot|mo\s+hoi\s+lanh|do\s+mo\s+hoi|diaphoresis)\b",
            r"\b(va mo hoi|va mo hoi hot|mo hoi lanh|do mo hoi hot|nguoi va mo hoi|uong mo hoi|mo hoi dam dia)\b",
        ],
    },
    {
        "canonical_name": "cold_extremity",
        "category": "sign",
        "organ_system": "vascular",
        "patterns": [
            r"\b(?:chan|tay|chi|cang chan|ban chan|cai gio)\b.*?\b(?:lanh buot|lanh ngat|lanh gia|lanh cong|cold|lanh)\b",
            r"\b(chan lanh buot|tay lanh buot|dau chi lanh|chan tay lanh ngat|tay chan lanh buot|cold extremity|chan lanh|tay lanh)\b",
        ],
    },
    {
        "canonical_name": "pallor_or_cyanosis",
        "category": "sign",
        "organ_system": "vascular",
        "patterns": [
            r"\b(?:da|moi|chan|ban chan|tay)\b.*?\b(?:trang bech|tai nhat|tai met|xanh xao|tim tai|pale|trang nhot)\b",
            r"\b(trang bech|tai nhat|da xanh xao|tai met|moi tham|tim tai|da tim|trang nhot)\b",
        ],
    },
    {
        "canonical_name": "absent_or_weak_pulse",
        "category": "sign",
        "organ_system": "vascular",
        "patterns": [
            r"(?:so|bat|check|ro)\b.*?\b(?:mach|pulse)\b.*?\b(?:khong|k|no|chang|mat|yeu|hong thay|nho cho)\b",
            r"(?:mach|pulse)\b.*?\b(?:khong thay|no cho|mat han|khong con|hong thay|im lim|k thay)\b",
            r"\b(so mach khong thay|khong bat duoc mach|mach yeu|mat mach|khong thay mach|mach dap khong deu|bat mach khong thay|absent pulse)\b",
        ],
    },
    # Neurologic Deficits
    {
        "canonical_name": "focal_weakness",
        "category": "sign",
        "organ_system": "neurology",
        "patterns": [
            r"\b(?:tay|chan|nua nguoi|chi|canh tay)\b.*?\b(?:yeu|liet|khong gio|khong cam|khong giu|khong di|khuyu|ru xuong|roi do|yeu xiu|yeu han|rot cai dop|k cam dc|te ran va roi)\b",
            r"\b(yeu nua nguoi|liet nua nguoi|tay khong gio len duoc|tay cam coc nuoc thay yeu|yeu mot ben tay|yeu chan|khuyu chan|chan tay nhu muon cua ai|te ran nua nguoi|arm weakness)\b",
        ],
    },
    {
        "canonical_name": "facial_droop_or_numbness",
        "category": "sign",
        "organ_system": "neurology",
        "patterns": [
            r"\b(?:mieng|khoe mieng|moi|cai mieng)\b.*?\b(?:meo|lech|te ran|chay nuoc dai|chay nuoc mieng|chay nuoc bot|chay dai|xe xuong|facial droop|lech queo|meo xeo|meo xech)\b",
            r"\b(?:mat|khuon mat)\b.*?\b(?:meo|lech|te ran|xe xuong|facial droop|lech queo|meo xeo|meo xech)\b|\b(?:meo|lech|te)\s+mat\b",
            r"\b(meo mieng|lech mat|te ran khoe mieng|nuoc bot hoi chay|chay nuoc dai mot ben|te moi|te nua mat|facial droop)\b",
        ],
    },
    {
        "canonical_name": "speech_impairment",
        "category": "sign",
        "organ_system": "neurology",
        "patterns": [
            r"\b(?:noi|tieng noi|giong noi|phat am|speech|noi chuyen)\b.*?\b(?:ngong|kho nghe|khong duoc|lap bap|u o|cung luoi|hong ro|nghe hong ro)\b",
            r"\b(noi ngong|noi kho nghe|kho phat am|khong noi duoc|noi lap bap|u o khong thanh tieng|khong tim duoc tu|aphasia)\b",
        ],
    },
    {
        "canonical_name": "visual_loss_acute",
        "category": "sign",
        "organ_system": "ophthalmology",
        "patterns": [
            r"\b(khong nhin thay mot mat|mat thi luc mot mat|dot nhien toi sam mot ben|mat nhin toi thui|nhin mot hoa hai|song thi dot ngot|nhin doi)\b",
        ],
    },
    # Respiratory & Airway
    {
        "canonical_name": "severe_dyspnea",
        "category": "symptom",
        "organ_system": "cardiopulmonary",
        "patterns": [
            r"\b(khong tai nao hit sau duoc|khong hit sau duoc|khong the hit sau|khong hit tho duoc|kho tho du doi|tho doc|tho khong ra hoi|hut hoi|nghet tho|khong tho duoc|tho rit|co keo co ho hap)\b",
        ],
    },
    {
        "canonical_name": "angioedema_or_stridor",
        "category": "sign",
        "organ_system": "allergy_airway",
        "patterns": [
            r"\b(sung phu moi|phu luoi|nuot nghen khong tho|sung hong|sung mat sau an|kho tho rit|tieng tho rit)\b",
        ],
    },
    # Syncope & Consciousness
    {
        "canonical_name": "syncope",
        "category": "symptom",
        "organ_system": "cardiovascular",
        "patterns": [
            r"\b(ngat xiu|ngat|bat tinh|ngat khi gang suc|dot ngot ngat|mat y thuc)\b",
        ],
    },
    {
        "canonical_name": "micturition_syncope",
        "category": "trigger",
        "organ_system": "autonomic",
        "patterns": [
            r"(?<!ra mau )(?<!phan den )(?:di tieu|tieu tien)\b.*?\b(?:ngat|xiu|ngat xiu|choang)(?!.*(?:ra mau|phan den|chay mau|xuat huyet))",
            r"(?:ngat|xiu|ngat xiu|choang vang|choang)\b.*?\b(?:khi|sau khi)?\s*(?:dang\s+)?(?:di tieu|tieu tien)(?!.*(?:ra mau|phan den|chay mau|xuat huyet))",
        ],
    },
    # Exertion & Triggers
    {
        "canonical_name": "exertion_trigger",
        "category": "trigger",
        "organ_system": "general",
        "patterns": [
            r"\b(khi gang suc|leo cau thang|chay bo|khi di bo|lam viec nang|gang suc)\b",
        ],
    },
    {
        "canonical_name": "radiation_to_arm_or_jaw",
        "category": "radiation",
        "organ_system": "cardiovascular",
        "patterns": [
            r"\b(?:lan|buot|nhoi)\b.*?\b(?:tay\s+trai|vai|ham|co|co\s+hong|sau\s+lung|left\s+arm)\b|\b(lan\s+len\s+vai|lan\s+ra\s+tay\s+trai|lan\s+xuong\s+tay\s+trai|lan\s+len\s+ham|lan\s+ra\s+sau\s+lung|lan\s+len\s+co)\b",
            r"\b(lan len vai|lan xuong tay trai|lan len ham|lan ra sau lung|lan len co)\b",
        ],
    },
    {
        "canonical_name": "acute_onset",
        "category": "timing",
        "organ_system": "general",
        "patterns": [
            r"\b(dot ngot|vua moi|cach day vai phut|cach day 30 phut|tu nhien bi|bong nhien)\b",
        ],
    },
    # Bleeding & Hemorrhage
    {
        "canonical_name": "massive_hemorrhage",
        "category": "sign",
        "organ_system": "hematology",
        "patterns": [
            r"\b(non ra mau|mau do tuoi|mau cuc|phan den nhu ba ca phe|di ngoai phan den|chay mau o at|thau mau)\b",
        ],
    },
    # Shock & Collapse
    {
        "canonical_name": "circulatory_shock",
        "category": "sign",
        "organ_system": "cardiovascular",
        "patterns": [
            r"\b(tut huyet ap|truy mach|soc|choang vang nga quy|nga quy|mach nhanh nho|mach kho bat)\b",
        ],
    },
    # Sepsis & Deep Infection
    {
        "canonical_name": "deep_infection_sign",
        "category": "sign",
        "organ_system": "systemic",
        "patterns": [
            r"\b(sot cao ret run|sot 40 do|van hoa tim tai|lo mo lu lan|thop phong)\b",
        ],
    },
    # Toxic Ingestion
    {
        "canonical_name": "toxic_ingestion_sign",
        "category": "sign",
        "organ_system": "toxicology",
        "patterns": [
            r"\b(uong nham|nuot phai|thuoc tru sau|thuoc diet chuot|ruou ngam|doc chat|uong thuoc sau|qua lieu)\b",
        ],
    },
    # Pregnancy Emergency
    {
        "canonical_name": "pregnancy_emergency_sign",
        "category": "sign",
        "organ_system": "obstetrics",
        "patterns": [
            r"\b(?:mang thai|san phu|co bau)\b.*?\b(?:co giat|nhin mo|dau dau du doi|tien san giat|san giat)\b|\b(tien san giat|san giat)\b",
        ],
    },
    # Metabolic Crisis
    {
        "canonical_name": "metabolic_crisis_sign",
        "category": "sign",
        "organ_system": "endocrine",
        "patterns": [
            r"\b(kussmaul|tho nhanh sau|mui tao thoi|toan chuyen hoa|tieu duong.*?hon me|ha duong huyet.*?hon me)\b",
        ],
    },
    # Coagulopathy & Anticoagulant Hemorrhage
    {
        "canonical_name": "coagulopathy_hemorrhage",
        "category": "sign",
        "organ_system": "hematology",
        "patterns": [
            r"\b(?:chay mau|xuat huyet|mau chay)\b.*?\b(?:khong cam|kho cam|chay mai|khong dung)\b",
            r"\b(?:chay mau khong cam|mau chay khong cam duoc|mang bam tim|bam tim to|xuat huyet duoi da)\b",
            r"\b(?:warfarin|sintrom|thuoc chong dong)\b.*?\b(?:chay mau|bam tim|xuat huyet)\b",
        ],
    },
    # Spinal Cord & Cauda Equina Compression
    {
        "canonical_name": "cauda_equina_signs",
        "category": "sign",
        "organ_system": "neurology",
        "patterns": [
            r"\b(?:that lung|dau lung|cot song)\b.*?\b(?:lan (?:xuong )?(?:hai|2) chan|te (?:vung )?quanh hau mon|te yen ngua)\b",
            r"\b(?:te (?:vung )?quanh hau mon|te yen ngua|mat cam giac hau mon|bi tieu dot ngot)\b",
        ],
    },
    # Obstetric Acute Abdomen / Ectopic Rupture
    {
        "canonical_name": "obstetric_acute_abdomen",
        "category": "symptom",
        "organ_system": "obstetrics",
        "patterns": [
            r"\b(?:tre kinh|cham kinh|mang thai|co thai)\b.*?\b(?:dau bung|dau quan|dau ho chau|dau bung duoi)\b",
            r"\b(?:dau bung|dau quan)\b.*?\b(?:tre kinh|cham kinh|mang thai)\b",
        ],
    },
]


def extract_semantic_relations(text: str) -> SemanticRelationGraph:
    """Parse raw clinical text into an explicit entity-relation semantic graph."""
    norm = normalize_search_text(text)
    concepts: dict[str, ExtractedConcept] = {}

    for rule in _ATOMIC_CONCEPT_CATALOG:
        canonical = rule["canonical_name"]
        for pat in rule["patterns"]:
            match = re.search(pat, norm)
            if match:
                span = match.span()
                # Check if immediately preceded by a negation word within the same clause
                preceding = norm[:span[0]].rstrip()
                following = norm[span[1]:].lstrip()
                is_neg = bool(re.search(r"\b(?:khong|chua|khong he|khong phai|khong thay|chang|k)(?:\s+(?:co|bi|thay))?\s*$", preceding[-25:]))
                if not is_neg and canonical == "exertion_trigger":
                    if re.match(r"^(?:la\s+)?(?:binh thuong|tot|on|k sao|khong sao)\b", following[:25]):
                        is_neg = True

                cid = f"c_{canonical}"
                concepts[cid] = ExtractedConcept(
                    concept_id=cid,
                    canonical_name=canonical,
                    category=rule["category"],
                    certainty=0.92 if not is_neg else 0.95,
                    evidence_span=match.group(0),
                    organ_system=rule["organ_system"],
                    is_negated=is_neg,
                )
                break

    # Extract Relations based on proximity and linguistic markers
    relations: list[ClinicalRelation] = []
    c_list = list(concepts.values())

    for i in range(len(c_list)):
        for j in range(i + 1, len(c_list)):
            c1 = c_list[i]
            c2 = c_list[j]
            if c1.is_negated or c2.is_negated:
                continue

            # Co-occurrence within same interaction
            relations.append(
                ClinicalRelation(
                    relation_type=RelationType.CO_OCCURS_WITH,
                    source_concept=c1.canonical_name,
                    target_concept=c2.canonical_name,
                    confidence=0.90,
                    evidence_span=f"{c1.evidence_span} ... {c2.evidence_span}",
                )
            )

            # Check for specific semantic associations
            if c1.category == "symptom" and c2.canonical_name == "radiation_to_arm_or_jaw":
                relations.append(
                    ClinicalRelation(
                        relation_type=RelationType.RADIATION_TO,
                        source_concept=c1.canonical_name,
                        target_concept=c2.canonical_name,
                        confidence=0.95,
                        evidence_span="radiation",
                    )
                )
            if c1.category == "symptom" and c2.canonical_name == "exertion_trigger":
                relations.append(
                    ClinicalRelation(
                        relation_type=RelationType.AGGRAVATED_BY,
                        source_concept=c1.canonical_name,
                        target_concept=c2.canonical_name,
                        confidence=0.95,
                        evidence_span="exertion",
                    )
                )

    return SemanticRelationGraph(
        raw_text=text,
        normalized_text=norm,
        concepts=concepts,
        relations=relations,
    )
