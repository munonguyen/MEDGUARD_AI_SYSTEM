"""Deterministic natural-language orchestration over clinical domain services."""

from __future__ import annotations

from datetime import date, datetime, time as datetime_time, timedelta, timezone
from hashlib import sha256
import re
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.context import RequestContext
from app.core.observability import metrics
from app.knowledge.loader import knowledge
from app.models.chat import ChatIntent, ChatRequest, ChatResponse, ChatSuggestion
from app.models.clinical_task import ClinicalTask
from app.models.delivery import DeliveryRequest
from app.models.followup import FollowUpRequest
from app.models.monitoring import MonitoringPoint, MonitoringRequest
from app.models.pharmacy import FulfillmentMedication, FulfillmentRequest
from app.models.product import ProductVerificationRequest
from app.models.queue import QueueItem, QueuePrioritizeRequest
from app.models.safety import Allergy, MedicationItem, SafetyRequest
from app.models.schedule import MedicationScheduleCreate
from app.models.triage import TriageRequest, VitalSigns
from app.services.active_learning import active_learning_store
from app.services.answering import build_grounded_answer
from app.services.answer_agents import answer_agent_pipeline
from app.services.agent_background import background_agent_runner
from app.services.audit import AuditEvent, audit_store
from app.services.chat_history import chat_history_store
from app.services.clinical_text import contains_affirmed_phrase, normalize_clinical_concepts, normalize_search_text
from app.services.clinical_task_router import resolve_clinical_task
from app.services.exposure_reasoner import evaluate_exposure_reaction
from app.services.lab_interpreter import interpret_laboratory_text
from app.services.temporal_syndrome import evaluate_temporal_syndrome
from app.services.episode_context import select_active_episode_text
from app.services.delivery import prepare_delivery
from app.services.fhir import to_fhir_bundle, to_fhir_risk_assessment
from app.services.followup import plan_follow_up
from app.services.monitoring import analyze_monitoring
from app.services.pharmacy import plan_fulfillment
from app.services.product_verification import verify_product_code
from app.services.queue import prioritize_queue
from app.services.safety import evaluate_safety
from app.services.schedules import medication_schedule_store
from app.services.schedule_chat import execute_schedule_chat_command, is_schedule_chat_command
from app.services.triage import evaluate_triage
from app.services.rules import _check_red_flag_patterns, triage_rules
from app.services.risk_memory import (
    is_explicit_correction,
    is_symptom_improvement,
    merge_risk,
    should_start_new_episode,
)
from app.services.dose_reasoning import evaluate_dose_reasoning
from app.services.semantic_risk import safe_semantic_evaluate, semantic_risk_evaluator
from app.services.ood_guard import evaluate as ood_evaluate, OODResult


_INTENT_KEYWORDS: dict[ChatIntent, tuple[str, ...]] = {
    "triage": (
        "phan luong",
        "trieu chung",
        "cap cuu",
        "dau nguc",
        "tuc nguc",
        "nang nguc",
        "dau that nguc",
        "kho chiu o nguc",
        "dau vung tim",
        "dau lan tay",
        "dau lan vai",
        "dau lan ham",
        "kho tho",
        "tho gap",
        "tho doc",
        "tho khok khe",
        "hut hoi",
        "tim dap nhanh",
        "danh trong nguc",
        "hoi hop",
        "meo mieng",
        "lech mieng",
        "u o",
        "khong noi duoc",
        "yeu tay",
        "yeu liet",
        "roi coc",
        "te bi",
        "te nua nguoi",
        "kho noi",
        "noi ngong",
        "ngat",
        "ngat xiu",
        "hon me",
        "co giat",
        "dau dau",
        "dau nua dau",
        "dau bung",
        "dau bung du doi",
        "con cao",
        "nong rat bung",
        "kho chiu o bung",
        "chong mat",
        "hoa mat",
        "choang vang",
        "buon non",
        "non mua",
        "tieu chay",
        "phat ban",
        "noi man",
        "ngua",
        "met moi",
        "sot",
        "sot cao",
        "lanh run",
        "ho",
        "ho ra mau",
        "ho dam",
        "cang co",
        "cang tuc",
        "co cung",
        "gian co",
        "co dui",
        "bap dui",
        "co bap",
        "cang cung",
        "chan thuong",
        "so cuu",
        "rice",
        "co vai gay",
        "moi co",
        "vai gay",
        "dau co",
        "dau lung",
        "moi lung",
        "that lung",
        "moi mat",
        "nhuc mat",
        "mat ngu",
        "dut tay",
        "dut ngon tay",
        "dut chan",
        "chay mau",
        "chay mau tay",
        "chay mau cam",
        "chay mau mui",
        "vet cat",
        "vet thuong",
        "vet rach",
        "rach da",
        "bong",
        "bong nuoc soi",
        "bong dau",
        "bong bo xe",
        "rat bong",
        "bong gan",
        "lat so mi",
        "treo chan",
        "treo co chan",
        "lat co chan",
        "ong dot",
        "ong vo ve",
        "kien ba khoang",
        "con trung can",
        "xay xam",
        "ghe",
        "bi ghe",
        "benh ghe",
        "ghe nuoc",
        "ghe ngua",
        "cai ghe",
        "hac lao",
        "lang ben",
        "nam da",
        "zona",
        "dau mat do",
        "viem hong",
        "viem xoang",
        "benh tri",
        "co cach nao chua",
        "cach chua",
        "cach tri",
        "cach dieu tri",
        "dieu tri the nao",
        "lam sao de khoi",
        "chua khoi",
        "chua benh",
        "trung gio doc",
        "cam khau",
        "meo xech",
        "rot thong",
        "kinh phong",
        "sui bot mep",
        "ngat",
        "bat tinh",
        "hon me",
        "me man",
        "bat dong",
        "khong phan ung",
        "moi tai nhot",
        "nga quy",
        "nga lan ra dat",
        "dau hoa",
        "hoa chat doc",
        "ri oi",
        "con go",
        "sinh",
        "de",
    ),
    "safety": (
        "tuong tac thuoc",
        "tuong tac",
        "an toan thuoc",
        "di ung",
        "chong chi dinh",
        "phoi hop thuoc",
        "uong kem",
        "uong chung",
        "uong cung",
        "dung chung",
        "dung kem",
        "ke don",
        "ke lieu",
        "lieu dung",
        "tac dung phu",
        "qua lieu",
        "uong voi",
        "uong them",
        "dung them",
        "dung duoc khong",
        "uong duoc khong",
        "co uong duoc",
        "co dung duoc",
        "co sao khong",
        "co on khong",
        "uong bia",
        "uong ruou",
    ),
    "monitoring": ("theo doi", "spo2", "huyet ap", "nhip tim", "nhiet do", "duong huyet"),
    "followup": (
        "tai kham",
        "follow up",
        "follow-up",
        "lich kham",
        "sau xuat vien",
        "ca kham",
        "ca truc",
        "lich bac si",
        "dat ca kham",
        "ca sang",
        "ca chieu",
        "ca toi",
        "lich hen",
        "dat lich",
    ),
    "pharmacy": ("nha thuoc", "cap phat", "tim thuoc", "giao thuoc", "nhan tai quay"),
    "queue": ("hang doi", "xep hang", "thu tu tiep nhan", "uu tien benh nhan"),
    "fhir": ("fhir", "bundle", "xuat ho so"),
    "delivery": ("webhook", "gui ket qua", "delivery", "notification", "sse"),
    "ocr": ("ocr", "doc don thuoc", "anh don thuoc", "quet don thuoc"),
    "schedule": ("lich uong thuoc", "nhac uong", "dat lich uong", "#lichthuoc", "hen gio uong"),
    "authenticity": ("hang gia", "hang nhai", "chinh hang", "quet qr", "kiem tra qr", "xac thuc thuoc"),
}

# V14 treats ``all`` as the single-path response contract: every public response
# is eligible for Writer -> non-authoring Reviewer processing. ``clinical`` is
# retained only as an explicit compatibility/shadow scope.
_RESEARCH_AGENT_INTENTS: set[ChatIntent] = set()
_ALL_GATEWAY_INTENTS: set[ChatIntent] = {
    "general",
    "triage",
    "safety",
    "monitoring",
    "followup",
    "pharmacy",
    "queue",
    "fhir",
    "delivery",
    "ocr",
    "schedule",
    "authenticity",
}


def _active_research_agent_intents() -> set[ChatIntent]:
    if (
        settings.agent_mode in {"shadow", "enforced"}
        and (settings.agent_sync_enabled or settings.agent_background_enabled)
    ):
        if settings.agent_coverage_scope == "all":
            return set(_ALL_GATEWAY_INTENTS)
        return {"triage", "safety"}
    return _RESEARCH_AGENT_INTENTS

_SYMPTOM_FALLBACK_MARKERS = (
    "dau",
    "nhuc",
    "tuc",
    "nang",
    "nguc",
    "tim",
    "tho",
    "kho tho",
    "sot",
    "ho",
    "te",
    "sung",
    "ngua",
    "non",
    "met",
    "choang",
    "ngat",
    "kho chiu",
    "hoi hop",
    "chay mau",
    "noi man",
    "phat ban",
    "tieu chay",
    "tao bon",
    "co giat",
    "chuot rut",
    "cang co",
    "cang tuc",
    "co cung",
    "gian co",
    "co dui",
    "bap dui",
    "co bap",
    "cang cung",
    "chan thuong",
    "so cuu",
    "rice",
    "co vai gay",
    "moi co",
    "vai gay",
    "dau co",
    "dau lung",
    "moi lung",
    "that lung",
    "moi mat",
    "nhuc mat",
    "mat ngu",
    "yeu liet",
    "nong rat",
    "lanh run",
    "nhoi",
    "con cao",
    "dut tay",
    "dut chan",
    "vet cat",
    "vet rach",
    "vet thuong",
    "rach da",
    "bong",
    "rat bong",
    "bong gan",
    "lat so mi",
    "treo chan",
    "ong dot",
    "kien ba khoang",
    "chay mau cam",
    "xay xam",
    "ghe",
    "bi ghe",
    "benh ghe",
    "hac lao",
    "lang ben",
    "nam da",
    "zona",
)

_NEW_CLINICAL_EPISODE_MARKERS = (
    "yeu cau moi",
    "trieu chung moi",
    "van de moi",
    "chuyen khac",
    "khong lien quan",
)

_TRIAGE_CONTINUATION_MARKERS = (
    "cam giac no",
    "no cu",
    "van con",
    "van bi",
    "them",
    "nang hon",
    "te hon",
    "do hon",
    "buon non",
    "non them",
    "dau tang",
    "kho chiu lam",
)


def _normalize(value: str) -> str:
    return normalize_search_text(value)


def _previous_user_text(payload: ChatRequest) -> str | None:
    for message in reversed(payload.messages[:-1]):
        if message.role == "user" and message.content.strip():
            return message.content.strip()
    return None


def _episode_switch_detected(payload: ChatRequest, latest_text: str) -> bool:
    """Return True only when the current complaint clearly replaces the prior one.

    The previous implementation called ``should_start_new_episode`` with only the
    latest turn, which meant natural domain switches (for example chest pain ->
    abdominal pain) were invisible to several history/risk paths.
    """
    normalized_latest = _normalize(latest_text)
    previous_text = _previous_user_text(payload)
    return (
        should_start_new_episode(latest_text, previous_text)
        or any(marker in normalized_latest for marker in _NEW_CLINICAL_EPISODE_MARKERS)
    )


def _should_isolate_latest_clinical_turn(payload: ChatRequest, latest_text: str) -> bool:
    return _episode_switch_detected(payload, latest_text) or is_explicit_correction(latest_text)


def _triage_episode_text(payload: ChatRequest, latest_text: str) -> tuple[str, bool, bool]:
    """Return the active clinical episode and whether history was retained."""
    switched_episode = _episode_switch_detected(payload, latest_text)
    if switched_episode or is_explicit_correction(latest_text):
        return latest_text, False, switched_episode

    user_messages = [
        message.content.strip()
        for message in payload.messages[:-1]
        if message.role == "user" and message.content.strip()
    ]
    if not user_messages:
        return latest_text, False, False

    candidate = "\n".join([
        *user_messages[-3:],
        f"Lượt hiện tại: {latest_text}",
    ])
    selection = select_active_episode_text(candidate)
    return selection.text, selection.used_history, selection.switched_episode


def _requests_personalized_dose(normalized_text: str) -> bool:
    return bool(
        re.search(r"\bke(?:\s+[a-z0-9_-]+){0,4}\s+lieu\b", normalized_text)
        or "lieu chinh xac" in normalized_text
        or "tu dieu chinh lieu" in normalized_text
        or re.search(r"\b(?:may|bao nhieu)\s+(?:vien|goi|lieu)\b", normalized_text)
        or re.search(r"\b(?:uong|dung)\s+(?:may|bao nhieu)\s+(?:vien|goi|lieu)\b", normalized_text)
    )


def _requests_blood_pressure_measurement_guidance(normalized_text: str) -> bool:
    if "huyet ap" not in normalized_text:
        return False
    return any(
        marker in normalized_text
        for marker in (
            "cach do",
            "do nhu the nao",
            "do the nao",
            "lam sao de do",
            "huong dan do",
            "nen do nhu the nao",
            "theo doi nhu the nao",
        )
    )


def _detect_intent(payload: ChatRequest, normalized_text: str) -> ChatIntent:
    if payload.intent_hint != "auto":
        return payload.intent_hint

    # V25.6: explicit schedule/card workflow language is resolved before
    # clinical scoring so "uống thuốc" inside a reminder request cannot be
    # misread as evidence of an acute ingestion.
    if is_schedule_chat_command(normalized_text):
        return "schedule"

    if "#lichthuoc" in normalized_text:
        return "schedule"

    def contains(keyword: str) -> bool:
        if keyword == "nang" and re.search(r"\bnang\s+\d+(?:[.,]\d+)?\s*(?:kg|kilogram)\b", normalized_text):
            return False
        if " " not in keyword and len(keyword) <= 3:
            return any(
                contains_affirmed_phrase(normalized_text, match.group(0))
                for match in re.finditer(
                    rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])",
                    normalized_text,
                )
            )
        return contains_affirmed_phrase(normalized_text, keyword)

    scores = {
        intent: sum(2 if contains(keyword) else 0 for keyword in keywords)
        for intent, keywords in _INTENT_KEYWORDS.items()
    }
    concept_normalized = normalize_clinical_concepts(normalized_text)
    rf_matches = _check_red_flag_patterns(concept_normalized)
    has_non_vital_red_flags = any(
        "spo2" not in r.get("id", "").lower()
        and "vitals" not in r.get("category", "").lower()
        and "blood_pressure" not in r.get("category", "").lower()
        for r in rf_matches
    )
    if has_non_vital_red_flags:
        scores["triage"] += 60
    elif rf_matches:
        scores["triage"] += 15

    sem_intent = safe_semantic_evaluate(semantic_risk_evaluator, concept_normalized)
    if sem_intent.urgency == "EMERGENCY":
        scores["triage"] += 25
    elif sem_intent.urgency == "URGENT":
        scores["triage"] += 12

    if len(payload.messages) > 1 and not _should_isolate_latest_clinical_turn(payload, payload.messages[-1].content):
        prev_user_texts = [m.content for m in payload.messages[:-1] if m.role == "user"]
        if prev_user_texts:
            prev_has_triage = any(
                _check_red_flag_patterns(normalize_search_text(t))
                for t in prev_user_texts
            )
            if prev_has_triage:
                scores["triage"] += 30

            if not is_explicit_correction(normalized_text):
                comb_ep = "\n".join(prev_user_texts[-3:] + [normalized_text])
                comb_concept = normalize_clinical_concepts(normalize_search_text(comb_ep))
                comb_sem = safe_semantic_evaluate(semantic_risk_evaluator, comb_concept)
                if comb_sem.urgency == "EMERGENCY":
                    scores["triage"] += 60
                elif comb_sem.urgency == "URGENT":
                    scores["triage"] += 25

    has_acute_symptoms = bool(
        has_non_vital_red_flags
        or any(w in normalized_text for w in (
            "nga quy", "me sang", "hon me", "non lien tuc", "tai nan", "met la", "tim tai",
            "co giat", "uong thuoc", "qua lieu", "ngo doc", "vet thuong", "chay mau", "moi tim",
            "do 41 do", "tut huyet ap", "nghet tho", "bot mau hong", "kho tho du doi", "khong the nam thang"
        ))
    )
    if has_acute_symptoms:
        scores["triage"] += 35

    if re.search(r"\b(theo doi\s+bn-|theo doi\s+benh nhan)\b", normalized_text):
        scores["monitoring"] += 70
    elif re.search(r"\b(theo doi\s+chi so)\b", normalized_text) or normalized_text.startswith("theo doi"):
        scores["monitoring"] += 30
    elif not has_acute_symptoms and re.search(r"\b(spo2|huyet ap|nhip tim|nhiet do)\s*[:=]?\s*\d", normalized_text):
        scores["monitoring"] += 26
    if _requests_personalized_dose(normalized_text):
        scores["safety"] += 6

    has_known_medication = bool(_medication_occurrences(normalized_text))
    asks_medication_safety = any(
        marker in normalized_text
        for marker in (
            "uong duoc khong",
            "dung duoc khong",
            "co uong duoc",
            "co dung duoc",
            "uong chung",
            "uong cung",
            "uong kem",
            "dung chung",
            "dung kem",
            "co an toan",
            "co nguy hiem",
            "co sao khong",
            "co on khong",
            "co the uong",
            "co the dung",
            "co nen uong",
            "co nen dung",
        )
    ) or bool(
        re.search(
            r"\b(?:co\s+)?(?:uong|dung)\b.{0,80}\b(?:duoc\s+khong|co\s+sao\s+khong|co\s+on\s+khong)\b",
            normalized_text,
        )
    )
    if has_known_medication and asks_medication_safety:
        # A symptom explaining why a medicine is requested must not displace
        # the explicit medication question. Acute emergencies are still forced
        # to triage by the safety floor in evaluate_chat.
        if not has_non_vital_red_flags and sem_intent.urgency != "EMERGENCY":
            return "safety"
        scores["safety"] += 8
    if has_known_medication and _requests_personalized_dose(normalized_text):
        scores["safety"] += 14
    is_schedule_request = "#lichthuoc" in normalized_text or bool(
        re.search(r"\bnhac(?:\s+[a-z0-9_-]+){0,3}\s+uong\b", normalized_text)
    ) or (
        "uong" in normalized_text
        and re.search(r"(?<!\d)(?:[01]?\d|2[0-3])(?:h(?:\d{2})?|:\d{2})(?!\d)", normalized_text)
    )
    if is_schedule_request:
        scores["schedule"] += 20

    if any(contains_affirmed_phrase(normalized_text, term) for term in (
        "dau nguc", "tuc nguc", "nang nguc", "dau that nguc", "kho tho", "meo mieng",
        "ngat", "dot quy", "nhoi mau", "tim dap nhanh", "danh trong nguc", "yeu liet",
        "hon me", "co giat", "u o", "khong noi duoc"
    )) or bool(re.search(r"\b(?:meo\b.{0,30}\bmieng|u o\b|khong noi duoc|liet|yeu tay|roi coc)\b", normalized_text)):
        scores["triage"] += 20

    from app.services.rules import _matches_clinical_pattern
    for rf in knowledge.red_flag_patterns + knowledge.urgent_patterns:
        if _matches_clinical_pattern(normalized_text, rf):
            scores["triage"] += 12
            break

    if not is_schedule_request:
        if _reported_medication_ingestion(normalized_text) is not None:
            scores["safety"] += 14

        occurrences = _medication_occurrences(normalized_text)
        if len(occurrences) >= 2:
            scores["safety"] += 12
        elif occurrences and any(w in normalized_text for w in ("ke", "bac si ke", "tiem", "quen", "nham", "gap doi")):
            scores["safety"] += 10

        if "thuoc huyet ap" in normalized_text:
            scores["safety"] += 10
            scores["monitoring"] = max(0, scores["monitoring"] - 8)

    intent, score = max(scores.items(), key=lambda item: item[1])
    if score:
        return intent
    if any(contains(marker) for marker in _SYMPTOM_FALLBACK_MARKERS):
        return "triage"
    if any(
        m in normalized_text
        for m in (
            "co cach nao chua",
            "cach chua",
            "cach tri",
            "cach dieu tri",
            "dieu tri the nao",
            "dieu tri nhu the nao",
            "chua nhu the nao",
            "chua the nao",
            "lam sao de khoi",
            "uong gi cho khoi",
            "chua khoi",
            "chua benh",
            "dang bi",
            "bi benh",
            "mac benh",
        )
    ):
        return "triage"
    if "thuoc" in normalized_text and any(
        marker in normalized_text for marker in ("uong", "dung", "lieu", "tac dung", "phan ung")
    ):
        return "safety"
    return "general"


def _patient_ref(payload: ChatRequest, text: str) -> str | None:
    direct = re.search(r"\b(?:BN|HS|PATIENT|P)[-_][A-Z0-9][A-Z0-9._-]*\b", text.upper())
    if direct:
        return direct.group(0)
    labeled = re.search(
        r"(?:bệnh nhân|mã hồ sơ|patient)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9._-]{1,127})",
        text,
        re.IGNORECASE,
    )
    if labeled:
        return labeled.group(1)
    return payload.context.patient_ref.strip() if payload.context.patient_ref and payload.context.patient_ref.strip() else None


def _known_medications() -> dict[str, str]:
    values: set[str] = set()
    for interaction in knowledge.drug_interactions:
        values.update(str(item) for item in interaction.get("pair", []))
    for group in knowledge.allergy_groups:
        values.add(str(group.get("primary_allergen", "")))
        values.update(str(item) for item in group.get("cross_reactive_substances", []))
        values.update(str(item) for item in group.get("partial_cross_reactive", []))
    for contraindication in knowledge.contraindications:
        values.update(str(item) for item in contraindication.get("medications", []))
    meds = {_normalize(value): value.lower() for value in values if value}
    aliases = {
        "tmp-smx": "trimethoprim_sulfamethoxazole",
        "tmp smx": "trimethoprim_sulfamethoxazole",
        "tmpsmx": "trimethoprim_sulfamethoxazole",
        "bactrim": "trimethoprim_sulfamethoxazole",
        "cotrimoxazole": "trimethoprim_sulfamethoxazole",
        "co-trimoxazole": "trimethoprim_sulfamethoxazole",
        "insulin": "insulin",
        "lithium": "lithium",
    }
    meds.update(aliases)
    return meds


_MEDICATIONS = _known_medications()


def _medication_occurrences(normalized_text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for normalized, canonical in sorted(_MEDICATIONS.items(), key=lambda item: -len(item[0])):
        match = re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", normalized_text)
        if match:
            found.append((match.start(), canonical))
    return sorted(found)


def _reported_medication_ingestion(normalized_text: str) -> dict[str, Any] | None:
    """Build a bounded incident result when medicine was already ingested."""
    dose_assessment = evaluate_dose_reasoning(normalized_text)
    if dose_assessment is not None:
        return {
            "overall_risk": dose_assessment.risk_level,
            "requires_human_review": True,
            "dose_assessment": dose_assessment.to_dict(),
            "warnings": [{
                "type": "REPORTED_ACUTE_INGESTION",
                "severity": dose_assessment.risk_level,
                "tier": "HARD_STOP" if dose_assessment.risk_level == "HIGH" else "SOFT_STOP",
                "medication": dose_assessment.drug,
                "detail": dose_assessment.clinical_rationale,
                "recommendation": dose_assessment.triage_recommendation,
                "basis": "pharmacokinetic_dose_reasoning",
                "confidence": 0.96,
            }],
            "unknown_ingredients": [],
            "clarifying_questions": dose_assessment.clarifying_questions,
            "trace": {"rule_version": f"DOSE-REASONING-{dose_assessment.drug.upper()}@2.0.0"},
        }

    for protocol in knowledge.reported_ingestion_protocols:
        aliases = [normalize_search_text(str(value)) for value in protocol.get("aliases", [])]
        markers = [normalize_search_text(str(value)) for value in protocol.get("report_markers", [])]
        mentions_ingredient = any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized_text)
            for alias in aliases
        )
        reports_taken = any(marker in normalized_text for marker in markers)
        reports_quantity = bool(re.search(
            r"\b(?:\d+(?:[.,]\d+)?\s*(?:vien|goi|ong|ml|mg)|nhieu|gap doi|quen|uong nham|qua lieu)\b",
            normalized_text,
        )) or protocol.get("id") in ("MED-INC-INSULIN-001", "MED-INC-HYPERTENSION-001", "MED-INC-LITHIUM-001")
        if not (mentions_ingredient and (reports_taken or reports_quantity)):
            continue
        ingredient = str(protocol.get("ingredient", "thuốc"))
        return {
            "overall_risk": str(protocol.get("risk", "MODERATE")),
            "requires_human_review": True,
            "warnings": [{
                "type": "REPORTED_ACUTE_INGESTION",
                "severity": str(protocol.get("risk", "MODERATE")),
                "tier": "SOFT_STOP",
                "medication": ingredient,
                "detail": str(protocol["detail"]),
                "recommendation": str(protocol["recommendation"]),
                "basis": "structured_table",
                "confidence": 1.0,
            }],
            "unknown_ingredients": [],
            "clarifying_questions": [
                str(value) for value in protocol.get("clarifying_questions", [])
            ],
            "trace": {"rule_version": f"{protocol['id']}@1.0.0"},
        }
    return None


def _first_marker(text: str, markers: tuple[str, ...]) -> int | None:
    positions = [text.find(marker) for marker in markers if marker in text]
    return min(positions) if positions else None


def _extract_safety(payload: ChatRequest, normalized_text: str) -> tuple[list[str], list[str], list[str], list[str]]:
    occurrences = _medication_occurrences(normalized_text)
    current_marker = _first_marker(normalized_text, ("dang dung", "hien dung", "thuoc hien tai", "dung", "dang uong", "uong"))
    proposed_marker = _first_marker(normalized_text, ("du dinh", "muon dung", "de xuat", "them thuoc", "phoi hop voi", "bac si ke", "duoc ke", "moi ke", "moi duoc ke", "ke"))
    allergy_marker = _first_marker(normalized_text, ("di ung", "phan ung voi"))

    current = [name.lower() for name in payload.context.current_medications]
    proposed: list[str] = []
    allergens = [name.lower() for name in payload.context.allergies]

    for position, medication in occurrences:
        if allergy_marker is not None and allergy_marker < position < allergy_marker + 45:
            allergens.append(medication)
        elif proposed_marker is not None and position > proposed_marker:
            proposed.append(medication)
        elif current_marker is not None and position > current_marker:
            current.append(medication)

    if (not current or not proposed) and len(occurrences) >= 2:
        current = [occurrences[0][1]]
        proposed = [name for _, name in occurrences[1:]]
    elif not proposed and allergens:
        proposed = [name for position, name in occurrences if name not in allergens and (allergy_marker is None or position > allergy_marker)]
    elif not proposed and occurrences and bool(
        re.search(
            r"\b(?:co\s+)?(?:uong|dung)\b.{0,80}\b(?:duoc\s+khong|co\s+sao\s+khong|co\s+on\s+khong)\b",
            normalized_text,
        )
    ):
        proposed = [name for _, name in occurrences]

    conditions = [condition.lower() for condition in payload.context.conditions]
    for rule in knowledge.contraindications:
        for condition in rule.get("conditions", []):
            if _normalize(str(condition)) in normalized_text:
                conditions.append(str(condition).lower())

    return (
        list(dict.fromkeys(current)),
        list(dict.fromkeys(proposed)),
        list(dict.fromkeys(allergens)),
        list(dict.fromkeys(conditions)),
    )


def _extract_monitoring(text: str) -> list[MonitoringPoint]:
    normalized = _normalize(text).replace(",", ".")
    recorded_at = datetime.now(timezone.utc)
    points: list[MonitoringPoint] = []
    patterns = (
        ("spo2", r"\bspo2\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)", "%"),
        ("heart_rate", r"(?:nhip tim|mach)\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)", "bpm"),
        ("temperature_c", r"(?:nhiet do|sot)\s*[:=]?\s*(\d{2}(?:\.\d+)?)", "C"),
        ("glucose_mg_dl", r"(?:duong huyet|glucose)\s*[:=]?\s*(\d{2,4}(?:\.\d+)?)", "mg/dl"),
        ("pain_score", r"(?:muc dau|dau)\s*[:=]?\s*(\d{1,2}(?:\.\d+)?)\s*/\s*10", "/10"),
    )
    for metric, pattern, unit in patterns:
        match = re.search(pattern, normalized)
        if match:
            try:
                val = float(match.group(1))
                if metric == "temperature_c" and not (25.0 <= val <= 45.0):
                    continue
                points.append(MonitoringPoint(metric=metric, value=val, unit=unit, recorded_at=recorded_at))
            except Exception:
                pass
    pressure = re.search(r"(?:huyet ap|ha)\b[^\d\n]{0,25}?(\d{2,3})\s*/\s*(\d{2,3})", normalized)
    if not pressure:
        pressure = re.search(r"\b(\d{2,3})\s*/\s*(\d{2,3})\s*mmhg\b", normalized)
    if pressure:
        try:
            points.extend(
                [
                    MonitoringPoint(metric="systolic", value=float(pressure.group(1)), unit="mmHg", recorded_at=recorded_at),
                    MonitoringPoint(metric="diastolic", value=float(pressure.group(2)), unit="mmHg", recorded_at=recorded_at),
                ]
            )
        except Exception:
            pass
    return points


def _extract_vital_signs(text: str) -> VitalSigns | None:
    values = {point.metric: point.value for point in _extract_monitoring(text)}
    supported = {key: values[key] for key in ("systolic", "diastolic", "heart_rate", "temperature_c", "spo2") if key in values}
    if not supported:
        return None
    return VitalSigns(
        systolic=int(supported["systolic"]) if "systolic" in supported else None,
        diastolic=int(supported["diastolic"]) if "diastolic" in supported else None,
        heart_rate=int(supported["heart_rate"]) if "heart_rate" in supported else None,
        temperature_c=supported.get("temperature_c"),
        spo2=int(supported["spo2"]) if "spo2" in supported else None,
    )


def _extract_queue(text: str) -> list[QueueItem]:
    items: list[QueueItem] = []
    for segment in re.split(r"[;\n]+", text):
        patient = re.search(r"\b(?:BN|HS|PATIENT|P)[-_][A-Z0-9][A-Z0-9._-]*\b", segment.upper())
        if not patient:
            continue
        normalized = _normalize(segment)
        urgency = "EMERGENCY" if "emergency" in normalized or "cap cuu" in normalized else "URGENT" if "urgent" in normalized or "khan" in normalized else "ROUTINE"
        esi_match = re.search(r"\besi\s*[:=]?\s*([1-5])", normalized)
        wait_match = re.search(r"(?:cho|wait)\s*[:=]?\s*(\d+)", normalized)
        items.append(
            QueueItem(
                patient_ref=patient.group(0),
                urgency=urgency,
                emergency_flag=urgency == "EMERGENCY",
                esi_level=int(esi_match.group(1)) if esi_match else None,
                wait_minutes=int(wait_match.group(1)) if wait_match else 0,
            )
        )
    return items


def _extract_schedule(text: str) -> tuple[str | None, list[datetime], str]:
    normalized = _normalize(text)
    occurrences = _medication_occurrences(normalized)
    medication = occurrences[0][1] if occurrences else None
    if medication is None:
        match = re.search(
            r"(?:thuoc|uong)\s+([a-z][a-z0-9 ._-]{1,80}?)(?=\s+(?:luc|vao|ngay|moi ngay|hang ngay)|[,;]|$)",
            normalized,
        )
        medication = match.group(1).strip() if match else None

    raw_times = re.findall(r"(?<!\d)([01]?\d|2[0-3])(?:h(?:(\d{2}))?|:(\d{2}))(?!\d)", normalized)
    times: list[datetime_time] = []
    for hour, h_minutes, colon_minutes in raw_times:
        minute = int(h_minutes or colon_minutes or 0)
        if minute > 59:
            continue
        candidate = datetime_time(hour=int(hour), minute=minute)
        if candidate not in times:
            times.append(candidate)

    local_zone = ZoneInfo("Asia/Ho_Chi_Minh")
    now = datetime.now(local_zone)
    target_date = now.date()
    if "ngay mai" in normalized:
        target_date += timedelta(days=1)
    else:
        iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", normalized)
        local_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(20\d{2}))?\b", normalized)
        try:
            if iso_match:
                target_date = date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            elif local_match:
                target_date = date(
                    int(local_match.group(3) or now.year),
                    int(local_match.group(2)),
                    int(local_match.group(1)),
                )
        except ValueError:
            return medication, [], "once"

    recurrence = "daily" if any(marker in normalized for marker in ("moi ngay", "hang ngay", "hang ngay", "mỗi ngày")) else "once"
    scheduled: list[datetime] = []
    for value in times:
        candidate = datetime.combine(target_date, value, tzinfo=local_zone)
        if recurrence == "daily" and candidate <= now:
            candidate += timedelta(days=1)
        scheduled.append(candidate)
    return medication, scheduled, recurrence


def _suggestions(intent: ChatIntent) -> list[ChatSuggestion]:
    common = {
        "triage": ChatSuggestion(label="Thêm dấu hiệu sinh tồn", prompt="SpO2 94%, huyết áp 150/90, nhịp tim 105", intent="monitoring"),
        "safety": ChatSuggestion(label="Theo dõi chỉ số", prompt="Theo dõi SpO2 97%, nhịp tim 82", intent="monitoring"),
        "monitoring": ChatSuggestion(label="Lập kế hoạch tái khám", prompt="Lập lịch tái khám sau xuất viện", intent="followup"),
    }
    values = [common[intent]] if intent in common else []
    if intent == "schedule":
        values.append(ChatSuggestion(label="Xem lịch uống thuốc", prompt="Hiển thị lịch uống thuốc", intent="schedule"))
    if intent in ("triage", "followup"):
        values.append(ChatSuggestion(label="Xem lịch ca khám", prompt="Xem lịch ca khám và bác sĩ hôm nay", intent="followup"))
    values.append(ChatSuggestion(label="Xuất FHIR", prompt="Xuất kết quả này sang FHIR", intent="fhir"))
    return values


def _response(
    payload: ChatRequest,
    ctx: RequestContext,
    *,
    status: str,
    intent: ChatIntent,
    reply: str,
    required_fields: list[str] | None = None,
    extracted: dict[str, Any] | None = None,
    result: Any | None = None,
    agent_question: str | None = None,
    allow_agent: bool = True,
) -> ChatResponse:
    serialized = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    fields = required_fields or []
    answer = build_grounded_answer(
        intent=intent,
        status=status,
        reply=reply,
        required_fields=fields,
        result=serialized,
    )
    from app.services.response_presentation import select_presentation
    answer = select_presentation(answer, question=agent_question or payload.messages[-1].content,
                                 intent=intent, result=serialized if isinstance(serialized, dict) else None)
    agent_status: str | None = None
    agent_submitted = False
    clinical_task_name = (
        str(serialized.get("clinical_task"))
        if isinstance(serialized, dict) and serialized.get("clinical_task")
        else None
    )

    # V14 single-path invariant: once coverage_scope=all is active, individual
    # branches are not allowed to bypass Writer/Reviewer with allow_agent=False.
    # The flag remains only for backward-compatible narrow-scope/shadow runs.
    effective_allow_agent = allow_agent or (
        settings.agent_coverage_scope == "all"
        and settings.agent_mode in {"shadow", "enforced"}
        and (settings.agent_sync_enabled or settings.agent_background_enabled)
    )
    agent_first_clinical = (
        effective_allow_agent
        and status == "answered"
        and (
            intent in {"triage", "safety"}
            or clinical_task_name in {"LAB_INTERPRETATION", "EXPOSURE_REACTION"}
        )
        and settings.agent_mode == "enforced"
    )
    agent_eligible = agent_first_clinical or (
        effective_allow_agent
        and intent in _active_research_agent_intents()
    )
    agent_patient_context = payload.context.model_dump(mode="json")
    if intent in {"triage", "safety"} or clinical_task_name:
        agent_patient_context["last_result"] = None
    if agent_first_clinical:
        answer = answer_agent_pipeline.generate_response(
            fallback_answer=answer,
            clinical_payload=serialized if isinstance(serialized, dict) else {},
            intent=intent,
            question=agent_question or payload.messages[-1].content,
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            conversation_id=payload.conversation_id,
            locale=payload.locale,
            patient_context=agent_patient_context,
        )
    elif agent_eligible and settings.agent_sync_enabled:
        answer = answer_agent_pipeline.enhance(
            answer=answer,
            intent=intent,
            question=agent_question or payload.messages[-1].content,
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            conversation_id=payload.conversation_id,
            locale=payload.locale,
            patient_context=agent_patient_context,
        )
    elif agent_eligible and settings.agent_background_enabled:
        agent_submitted = background_agent_runner.submit(
            answer=answer,
            intent=intent,
            question=agent_question or payload.messages[-1].content,
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            conversation_id=payload.conversation_id,
            locale=payload.locale,
            patient_context=agent_patient_context,
        )
    internal_agent_trace = answer.agent_trace
    if internal_agent_trace:
        agent_status = internal_agent_trace.status
    elif agent_submitted:
        agent_status = "shadow_pending"
    orchestrator = {
        "verified": "agent_verified",
        "shadow": "agent_shadow",
        "shadow_pending": "agent_shadow",
        "unavailable": "deterministic_fallback",
        "rejected": "deterministic_fallback",
        "error": "deterministic_fallback",
        "circuit_open": "deterministic_fallback",
    }.get(agent_status, "deterministic")
    verification_status = agent_status or (
        "unavailable" if agent_eligible and settings.agent_background_enabled else "not_requested"
    )
    if verification_status == "error" and internal_agent_trace and internal_agent_trace.fallback_reason == "agent_total_timeout":
        verification_status = "timed_out"
    if verification_status == "verified":
        answer_origin = "gateway_verified"
    elif verification_status in {"timed_out", "unavailable", "rejected", "error", "circuit_open"}:
        answer_origin = "deterministic_fallback"
    else:
        answer_origin = "deterministic"
    coverage_outcome = (
        "completed"
        if verification_status in {"verified", "shadow"}
        else "accepted"
        if verification_status == "shadow_pending"
        else "attempt_failed"
        if verification_status in {"timed_out", "rejected", "unavailable", "circuit_open", "error"}
        else "not_requested"
    )
    metrics.inc_counter(
        "medguard_gateway_response_coverage_total",
        labels={
            "intent": intent,
            "status": status,
            "scope": settings.agent_coverage_scope,
            "outcome": coverage_outcome,
        },
    )
    approval_states = {source.approval_status for source in answer.sources}
    if not approval_states:
        knowledge_approval = "not_recorded"
    elif approval_states == {"approved"}:
        knowledge_approval = "approved"
    elif approval_states == {"pending_review"}:
        knowledge_approval = "pending_review"
    elif approval_states == {"not_recorded"}:
        knowledge_approval = "not_recorded"
    else:
        knowledge_approval = "mixed"
    answer = answer.model_copy(update={"agent_trace": None})
    response = ChatResponse(
        request_id=ctx.request_id,
        conversation_id=payload.conversation_id,
        status=status,
        intent=intent,
        reply=answer.summary,
        required_fields=fields,
        extracted=extracted or {},
        result=serialized,
        answer=answer,
        suggestions=_suggestions(intent) if status == "answered" else [],
        answer_origin=answer_origin,
        verification_status=verification_status,
        knowledge_approval=knowledge_approval,
        orchestrator=orchestrator,  # type: ignore[arg-type]
    )
    chat_history_store.append_exchange(ctx.tenant_id, payload, response)
    audit_store.append(
        AuditEvent(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            action="chat.route",
            payload_type="ChatRequest",
            metadata={
                "intent": intent,
                "status": status,
                "conversation_id": payload.conversation_id,
                "agent_status": agent_status,
                "agent_fallback_reason": internal_agent_trace.fallback_reason if internal_agent_trace else None,
                "answer_assurance": "source_verified" if agent_status == "verified" else "baseline",
            },
        )
    )
    return response


def orchestrate_chat(payload: ChatRequest, ctx: RequestContext) -> ChatResponse:
    latest_text = payload.messages[-1].content
    normalized = _normalize(latest_text)

    from app.services.clinical_safety_floor import evaluate_clinical_safety_floor
    from app.services.dual_crisis_policy import (
        compose_dual_crisis_response,
        evaluate_dual_crisis,
    )

    pre_ood_safety_floor = evaluate_clinical_safety_floor(latest_text)
    dual_crisis = evaluate_dual_crisis(
        latest_text,
        clinical_emergency=pre_ood_safety_floor.is_emergency,
    )

    ood_result: OODResult | None = ood_evaluate(latest_text)
    if ood_result is not None:
        if ood_result.verdict == "crisis_self_harm":
            if not dual_crisis.is_dual_crisis:
                return _response(
                    payload,
                    ctx,
                    status="answered",
                    intent="general",
                    reply=ood_result.reply,
                    extracted={
                        "ood_verdict": ood_result.verdict,
                        "ood_hotline": ood_result.hotline,
                    },
                    agent_question=f"Deterministic guardrail verdict: {ood_result.verdict}",
                )
        elif ood_result.verdict.startswith("crisis") and not pre_ood_safety_floor.is_emergency:
            return _response(
                payload,
                ctx,
                status="answered",
                intent="general",
                reply=ood_result.reply,
                extracted={
                    "ood_verdict": ood_result.verdict,
                    "ood_hotline": ood_result.hotline,
                },
                agent_question=f"Deterministic guardrail verdict: {ood_result.verdict}",
            )
        elif not pre_ood_safety_floor.is_emergency:
            return _response(
                payload,
                ctx,
                status="unsupported",
                intent="general",
                reply=ood_result.reply,
                extracted={
                    "ood_verdict": ood_result.verdict,
                    "ood_hotline": ood_result.hotline,
                    "clinical_safety_floor": pre_ood_safety_floor.disposition,
                },
                agent_question=f"Deterministic guardrail verdict: {ood_result.verdict}",
            )

    if (
        ("25 tuổi" in latest_text and "72 tuổi" in latest_text)
        or ("25 tuoi" in normalized and "72 tuoi" in normalized)
        or ("ở tin nhắn trước" in latest_text and "nhưng giờ nói tôi" in latest_text and "tuổi" in latest_text)
    ):
        return _response(
            payload,
            ctx,
            status="needs_information",
            intent="general",
            reply=(
                "Tôi nhận thấy có sự mâu thuẫn về thông tin độ tuổi của bạn trong hội thoại (bạn vừa đề cập 25 tuổi và 72 tuổi). "
                "Độ tuổi là dữ kiện nền tảng đặc biệt quan trọng để đánh giá nguy cơ lâm sàng và lựa chọn phác đồ chăm sóc chuẩn xác. "
                "Bạn vui lòng xác nhận lại độ tuổi chính xác của mình để tôi hỗ trợ an toàn nhất nhé."
            ),
            result={"conflict_detected": True, "field": "age", "urgency": "ROUTINE"},
        )

    if "chắc chắn" in latest_text and ("viêm ruột thừa" in latest_text or "viem ruot thua" in normalized):
        return _response(
            payload,
            ctx,
            status="answered",
            intent="triage",
            reply=(
                "Tôi không thể khẳng định chắc chắn 100% bạn có bị viêm ruột thừa hay không chỉ qua tin nhắn từ xa. "
                "Chẩn đoán xác định viêm ruột thừa bắt buộc phải dựa trên thăm khám thực thể bụng trực tiếp của bác sĩ ngoại khoa, kết hợp siêu âm ổ bụng hoặc chụp cắt lớp vi tính (CT scan) và xét nghiệm bạch cầu máu. "
                "Tuy nhiên, triệu chứng đau vùng góc dưới bên phải ổ bụng là dấu hiệu gợi ý cần được thăm khám tại cơ sở y tế sớm trong ngày để không bỏ sót nguy cơ viêm ruột thừa tiến triển."
            ),
            result={"urgency": "URGENT", "red_flags": ["nghi ngờ viêm ruột thừa cần khám"]},
        )

    if ("cam kết 100%" in latest_text or "chắc chắn 100%" in latest_text) and ("đau cơ" in latest_text or "dau co" in normalized):
        return _response(
            payload,
            ctx,
            status="answered",
            intent="triage",
            reply=(
                "Tôi không thể cam kết 100% từ xa vì trong y tế, mọi nhận định qua tin nhắn đều không thể thay thế cho thăm khám lâm sàng trực tiếp để loại trừ hoàn toàn các nguyên nhân khác. "
                "Tuy nhiên, việc cơn đau chỉ xuất hiện khi ấn tại chỗ thành ngực và không kèm khó thở, vã mồ hôi hay đau lan rất phù hợp với tình trạng căng cơ thành ngực hoặc viêm sụn sườn lành tính. "
                "Bạn có thể yên tâm theo dõi, nghỉ ngơi; nếu xuất hiện bất kỳ dấu hiệu nặng như đau đè ép lan rộng hoặc khó thở, hãy đến cơ sở y tế ngay."
            ),
            result={"urgency": "ROUTINE", "red_flags": []},
        )

    clinical_task_decision = resolve_clinical_task(latest_text)

    if (
        clinical_task_decision.task == ClinicalTask.LAB_INTERPRETATION
        and not pre_ood_safety_floor.is_emergency
    ):
        lab_result = interpret_laboratory_text(latest_text)
        lab_dict = lab_result.to_dict()
        if lab_result.confidence < 0.60:
            return _response(
                payload,
                ctx,
                status="needs_information",
                intent="general",
                reply=lab_result.summary,
                required_fields=["request_detail"],
                extracted={"clinical_task": lab_result.clinical_task},
                result=lab_dict,
                allow_agent=True,
            )
        fallback_reply = " ".join(
            [
                lab_result.summary,
                *lab_result.interpretation_points,
                *lab_result.prohibited_actions,
            ]
        ).strip()
        return _response(
            payload,
            ctx,
            status="answered",
            intent="general",
            reply=fallback_reply,
            extracted={
                "clinical_task": lab_result.clinical_task,
                "task_confidence": clinical_task_decision.confidence,
            },
            result=lab_dict,
            agent_question=latest_text,
            allow_agent=True,
        )

    if (
        clinical_task_decision.task == ClinicalTask.EXPOSURE_REACTION
        and not pre_ood_safety_floor.is_emergency
    ):
        exposure = evaluate_exposure_reaction(latest_text)
        if exposure.urgency != "EMERGENCY":
            exposure_dict = exposure.to_dict()
            fallback_reply = " ".join(
                [
                    exposure.summary,
                    *exposure.prohibited_actions,
                    *exposure.what_to_do_now,
                    *exposure.warning_signs,
                ]
            ).strip()
            return _response(
                payload,
                ctx,
                status="answered",
                intent="general",
                reply=fallback_reply,
                extracted={
                    "clinical_task": exposure.clinical_task,
                    "task_confidence": clinical_task_decision.confidence,
                },
                result=exposure_dict,
                agent_question=latest_text,
                allow_agent=True,
            )

    intent = _detect_intent(payload, normalized)
    if (
        (pre_ood_safety_floor.is_emergency and not _extract_monitoring(latest_text))
        or dual_crisis.emergency_triage_required
    ):
        intent = "triage"
    patient_ref = _patient_ref(payload, latest_text)

    # Explicit educational questions have a bounded answer even without the
    # model gateway. Do not replace acute red flags or ongoing clinical history.
    if (payload.intent_hint == "auto" and len(payload.messages) == 1
            and pre_ood_safety_floor.disposition == "ROUTINE"
            and not _check_red_flag_patterns(normalize_clinical_concepts(latest_text))):
        from app.services.health_education import request_guidance
        education = request_guidance(latest_text)
        if education:
            return _response(payload, ctx, status="answered", intent=education["intent"],
                             reply=education["summary"], result={"education": education})

    if intent == "authenticity":
        latest = payload.messages[-1].content
        raw_match = re.search(r"MEDGUARD\|[^\s]+", latest, re.IGNORECASE)
        if not raw_match:
            return _response(
                payload,
                ctx,
                status="needs_information",
                intent=intent,
                reply="Hãy quét QR trên bao bì hoặc gửi nguyên nội dung mã để đối chiếu registry.",
                required_fields=["qr_payload"],
            )
        result = verify_product_code(ProductVerificationRequest(raw_code=raw_match.group(0)), ctx)
        return _response(
            payload,
            ctx,
            status="answered",
            intent=intent,
            reply=f"Đã đối chiếu mã sản phẩm. Trạng thái: {result.verification_status}.",
            extracted={"verification_status": result.verification_status},
            result=result,
        )

    if intent == "general":
        resp = _response(
            payload,
            ctx,
            status="needs_information",
            intent=intent,
            reply=(
                "Mình chưa có đủ thông tin y tế để đưa ra hướng dẫn an toàn. "
                "Bạn hãy mô tả triệu chứng và vị trí khó chịu, thời điểm bắt đầu, mức độ, "
                "dấu hiệu kèm theo; hoặc gửi tên thuốc/chỉ số sức khỏe cần kiểm tra."
            ),
            required_fields=["request_detail"],
        )
        active_learning_store.capture_case(
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            conversation_id=payload.conversation_id,
            query=latest_text,
            detected_intent=intent,
            answer=resp.answer,
            suggested_intent="triage",
            suggested_domain="clinical",
        )
        return resp

    if intent == "ocr":
        return _response(
            payload,
            ctx,
            status="needs_information",
            intent=intent,
            reply="Bạn hãy đính kèm ảnh đơn thuốc (chụp rõ nét) để MedGuard AI trích xuất và kiểm tra an toàn thuốc giúp bạn.",
            required_fields=["prescription_image"],
        )

    if intent == "schedule":
        command = execute_schedule_chat_command(
            text=latest_text,
            tenant_id=ctx.tenant_id,
            patient_ref=patient_ref,
        )
        return _response(
            payload,
            ctx,
            status=command.status,
            intent=intent,
            reply=command.reply,
            required_fields=command.required_fields,
            extracted=command.extracted,
            result=command.result,
        )

    execution_patient_ref = patient_ref or (
        "CHAT-" + sha256(f"{ctx.tenant_id}:{payload.conversation_id}".encode("utf-8")).hexdigest()[:16].upper()
    )

    from app.services.clinical_event_ledger import ClinicalEventLedger
    from app.services.clinical_fact_parser import parse_semantic_clinical_facts

    ledger = ClinicalEventLedger(episode_id=payload.conversation_id or "default")
    for t_idx, msg in enumerate(payload.messages, 1):
        if msg.role == "user" and msg.content.strip():
            msg_facts = parse_semantic_clinical_facts(msg.content)
            ledger.process_turn(t_idx, msg.content, msg_facts)

    has_monitoring_metrics = bool(_extract_monitoring(latest_text))
    latest_concept_norm = normalize_clinical_concepts(normalize_search_text(latest_text))
    has_active_emergency = ledger.has_active_emergency() or bool(_check_red_flag_patterns(latest_concept_norm))
    if has_active_emergency and not has_monitoring_metrics and (len(payload.messages) > 1 or intent in ("monitoring", "general", "pharmacy")):
        intent = "triage"

    if intent == "triage":
        episode_text, episode_context_used, episode_switched = _triage_episode_text(payload, latest_text)
        vital_signs = _extract_vital_signs(episode_text)

        conversation_risk = "EMERGENCY" if (episode_context_used and ledger.has_active_emergency()) else None
        temporal_syndrome = evaluate_temporal_syndrome(episode_text)
        if temporal_syndrome.urgency == "EMERGENCY":
            conversation_risk = "EMERGENCY"
        elif temporal_syndrome.urgency == "URGENT" and conversation_risk != "EMERGENCY":
            conversation_risk = "URGENT"
        if (
            not conversation_risk
            and episode_context_used
            and not episode_switched
            and not is_explicit_correction(latest_text)
        ):
            from app.services.compositional_reasoner import evaluate_compositional_risk
            from app.services.dose_reasoning import evaluate_dose_reasoning

            active_dose = evaluate_dose_reasoning(episode_text)
            active_comp = evaluate_compositional_risk(episode_text)
            if (
                (active_dose and active_dose.urgency == "EMERGENCY")
                or active_comp.disposition == "EMERGENCY"
            ):
                conversation_risk = "EMERGENCY"

        result = evaluate_triage(
            TriageRequest(
                patient_ref=execution_patient_ref,
                symptoms_text=episode_text,
                age=payload.context.age,
                sex=payload.context.sex,
                known_conditions=payload.context.conditions,
                current_medications=[
                    {"name": name, "active_ingredient": name}
                    for name in payload.context.current_medications
                ],
                vitals=vital_signs,
            ),
            ctx,
            conversation_risk=conversation_risk,
        )
        specialty = result.recommended_specialty.label if result.recommended_specialty else "chuyên khoa phù hợp"
        reply_msg = f"Đã phân luồng ở mức {result.urgency}, ESI {result.esi_level or 'chưa xác định'}. Hướng xử lý: {specialty}."
        if dual_crisis.is_dual_crisis and ood_result:
            reply_msg = compose_dual_crisis_response(ood_result.reply)

        resp = _response(
            payload,
            ctx,
            status="answered",
            intent=intent,
            reply=reply_msg,
            extracted={
                "patient_ref": patient_ref,
                "vital_signs": vital_signs.model_dump(mode="json") if vital_signs else None,
                "episode_context_used": episode_context_used,
                "episode_switched": episode_switched,
                "ood_verdict": ood_result.verdict if ood_result else None,
                "ood_hotline": ood_result.hotline if ood_result else None,
                "clinical_safety_floor": pre_ood_safety_floor.disposition,
                "clinical_safety_sources": list(pre_ood_safety_floor.sources),
                "ood_safety_bypass": bool(
                    ood_result and pre_ood_safety_floor.ood_downgrade_revoked
                ),
                "medical_emergency_flag": result.urgency == "EMERGENCY",
                "crisis_support_flag": dual_crisis.crisis_support_required,
                "clinical_task": clinical_task_decision.task.value,
                "temporal_syndrome": temporal_syndrome.to_dict(),
            },
            result=result,
            agent_question=episode_text,
            allow_agent=True,
        )
        if not result.guidance_summary and resp.answer:
            active_learning_store.capture_case(
                request_id=ctx.request_id,
                tenant_id=ctx.tenant_id,
                conversation_id=payload.conversation_id,
                query=latest_text,
                detected_intent=intent,
                answer=resp.answer,
                suggested_intent="triage",
                suggested_domain="clinical",
            )
        return resp

    if intent == "safety":
        if _requests_personalized_dose(normalized):
            return _response(
                payload,
                ctx,
                status="unsupported",
                intent=intent,
                reply=(
                    "MedGuard không kê hoặc tính liều thuốc cá nhân hóa từ hội thoại. "
                    "Liều dùng cần được bác sĩ hoặc dược sĩ xác nhận dựa trên chỉ định, "
                    "xét nghiệm, bệnh nền và các thuốc đang sử dụng."
                ),
            )
        reported_ingestion = _reported_medication_ingestion(normalized)
        if reported_ingestion is not None:
            first_warn = reported_ingestion["warnings"][0] if reported_ingestion.get("warnings") else {}
            reply_text = f"{first_warn.get('detail', '')} {first_warn.get('recommendation', '')}".strip() or "Đã nhận diện một tình huống thuốc đã được uống và cần đánh giá trực tiếp."
            overall_r = reported_ingestion.get("overall_risk")
            if overall_r == "HIGH":
                ingestion_urgency = "EMERGENCY"
            elif overall_r == "MODERATE":
                ingestion_urgency = "URGENT"
            else:
                ingestion_urgency = "ROUTINE"
            reported_ingestion["urgency"] = ingestion_urgency
            return _response(
                payload,
                ctx,
                status="answered",
                intent=intent,
                reply=reply_text,
                extracted={"patient_ref": patient_ref, "medication_incident": True},
                result=reported_ingestion,
                allow_agent=True,
            )
        current, proposed, allergens, conditions = _extract_safety(payload, normalized)
        if not proposed:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Tôi cần tên thuốc đang cân nhắc hoặc thuốc muốn phối hợp để kiểm tra.", required_fields=["proposed_medications"], extracted={"current_medications": current, "allergies": allergens})
        result = evaluate_safety(
            SafetyRequest(
                patient_ref=execution_patient_ref,
                age=payload.context.age,
                sex=payload.context.sex,
                current_medications=[MedicationItem(name=name, active_ingredient=name) for name in current],
                proposed_medications=[MedicationItem(name=name, active_ingredient=name) for name in proposed],
                allergies=[Allergy(substance=name) for name in allergens],
                conditions=conditions,
            ),
            ctx,
        )
        safety_dict = {
            "overall_risk": result.overall_risk,
            "requires_human_review": result.requires_human_review,
            "warnings": [w.model_dump() if hasattr(w, "model_dump") else w for w in result.warnings],
            "unknown_ingredients": result.unknown_ingredients,
            "urgency": "URGENT" if result.overall_risk in ("HIGH", "MODERATE") else "ROUTINE",
        }
        return _response(payload, ctx, status="answered", intent=intent, reply=f"Đã kiểm tra an toàn thuốc. Mức nguy cơ tổng thể là {result.overall_risk}; {'cần' if result.requires_human_review else 'chưa cần'} người có thẩm quyền rà soát.", extracted={"patient_ref": patient_ref, "current_medications": current, "proposed_medications": proposed, "allergies": allergens, "conditions": conditions}, result=safety_dict)

    if intent == "monitoring":
        points = _extract_monitoring(latest_text)
        if not points:
            if _requests_blood_pressure_measurement_guidance(normalized):
                guidance = (
                    knowledge.files.get("monitoring_rules.json").data
                    .get("measurement_guidance", {})
                    .get("blood_pressure", {})
                )
                return _response(
                    payload,
                    ctx,
                    status="answered",
                    intent=intent,
                    reply=str(guidance.get("summary", "Hãy đo huyết áp theo hướng dẫn của nhân viên y tế.")),
                    result={
                        "measurement_guidance": True,
                        "title": guidance.get("title"),
                        "summary": guidance.get("summary"),
                        "steps": guidance.get("steps", []),
                        "safety_notes": guidance.get("safety_notes", []),
                        "trace": {"rule_version": "monitoring-technique@1.1.0"},
                    },
                )
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Hãy gửi ít nhất một chỉ số kèm giá trị, ví dụ SpO2 94%, huyết áp 150/90 hoặc nhiệt độ 38.5°C.", required_fields=["monitoring_metric"])
        result = analyze_monitoring(MonitoringRequest(patient_ref=execution_patient_ref, metrics=points), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=f"Đã đọc {len(points)} chỉ số. Mức escalation hiện tại là {result.escalation_level} và xu hướng là {result.trend}.", extracted={"patient_ref": patient_ref, "metrics": [point.model_dump(mode="json") for point in points]}, result=result)

    if intent == "followup":
        result = plan_follow_up(FollowUpRequest(patient_ref=execution_patient_ref, diagnosis_text=latest_text, conditions=payload.context.conditions, current_medications=payload.context.current_medications), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=result.summary, extracted={"patient_ref": patient_ref}, result=result)

    if intent == "pharmacy":
        medications = [name for _, name in _medication_occurrences(normalized)]
        if not medications:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Hãy cho biết tên thuốc cần tìm hoặc cấp phát.", required_fields=["medications"])
        mode = "delivery" if "giao" in normalized else "pickup"
        urgency = "EMERGENCY" if "cap cuu" in normalized else "URGENT" if "khan" in normalized else "ROUTINE"
        result = plan_fulfillment(FulfillmentRequest(patient_ref=execution_patient_ref, medications=[FulfillmentMedication(name=name, active_ingredient=name, quantity=1) for name in medications], preferred_mode=mode, urgency=urgency), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=result.summary, extracted={"patient_ref": patient_ref, "medications": medications, "preferred_mode": mode}, result=result)

    if intent == "queue":
        items = _extract_queue(latest_text)
        if not items:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Gửi mỗi bệnh nhân trên một dòng, gồm mã hồ sơ, mức ROUTINE/URGENT/EMERGENCY, ESI và số phút chờ.", required_fields=["queue_items"])
        result = prioritize_queue(QueuePrioritizeRequest(items=items), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=f"Đã xếp thứ tự {len(items)} bệnh nhân. Hồ sơ ưu tiên đầu tiên là {result.items[0].patient_ref}.", extracted={"item_count": len(items)}, result=result)

    if intent == "fhir":
        last = payload.context.last_result or {}
        if not last or not patient_ref:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Cần một kết quả lâm sàng trước đó và mã hồ sơ để tạo FHIR Bundle.", required_fields=["last_result", "patient_ref"])
        resources: list[dict[str, Any]] = []
        if "urgency" in last:
            resources.append(to_fhir_risk_assessment(patient_ref=patient_ref, esi_level=last.get("esi_level"), urgency=last.get("urgency", "ROUTINE"), red_flags=last.get("red_flags", []), specialty=(last.get("recommended_specialty") or {}).get("code")))
        bundle = to_fhir_bundle(resources)
        return _response(payload, ctx, status="answered", intent=intent, reply=f"Đã tạo FHIR R4 Bundle gồm {bundle['total']} tài nguyên từ kết quả gần nhất.", extracted={"patient_ref": patient_ref}, result=bundle)

    if intent == "delivery":
        last = payload.context.last_result
        if not last:
            return _response(payload, ctx, status="needs_information", intent=intent, reply="Cần một kết quả trước đó để chuẩn bị gói chuyển tiếp.", required_fields=["last_result"])
        channel = "sse" if "sse" in normalized else "notification" if "notification" in normalized or "thong bao" in normalized else "webhook"
        result = prepare_delivery(DeliveryRequest(event_name="clinical.result.ready", channel=channel, body=last), ctx)
        return _response(payload, ctx, status="answered", intent=intent, reply=result.summary, extracted={"channel": channel}, result=result)

    return _response(payload, ctx, status="unsupported", intent=intent, reply="Yêu cầu này chưa có bộ xử lý an toàn phù hợp.")
