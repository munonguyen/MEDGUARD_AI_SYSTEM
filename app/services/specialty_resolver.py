"""Clinical Specialty Resolver for MedGuard AI System.

Resolves clinical specialties accurately based on anatomical location, organ system,
and clinical presentation, eliminating dangerous specialty misrouting (e.g. routing
back pain to Neurology, toothache to Cardiology, or gym shoulder soreness to Cardiology).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.clinical_text import normalize_search_text

logger = logging.getLogger(__name__)


class SpecialtyResolver:
    """Medical specialty routing engine with strict organ-system discrimination."""

    @classmethod
    def resolve_specialty(
        cls,
        text: str,
        patient_context: dict[str, Any] | None = None,
    ) -> tuple[str, str, float]:
        """Resolves (specialty_code, specialty_label, confidence)."""
        norm = normalize_search_text(text)

        # Strip explicitly negated phrases to prevent false-triggering (e.g. "không đau ngực", "không khó thở")
        norm_clean = re.sub(
            r"\b(?:khong|chua|khong co|khong bi|chua tung|khong con)\s+(?:dau nguc|tuc nguc|kho tho|dau dau|nhuc dau|sot|sot cao|chay mau|kho tho du doi)\b",
            "",
            norm,
        )

        # -------------------------------------------------------------
        # 1. DENTISTRY (Răng Hàm Mặt)
        # -------------------------------------------------------------
        # Note: Avoid bare "rang" matching Vietnamese conjunction "rằng" ("nhận định rằng", "cho rằng")
        has_dental = bool(
            re.search(
                r"\b(?:nhuc rang|dau rang|sau rang|buot rang|e buot|nuou|loi|tuy rang|nho rang|rang khon|viem nuou|viem loi|viem tuy|ap xe rang|cung ham|nha khoa|ham rang|chan rang|chay mau chan rang|nieng rang|tram rang)\b",
                norm_clean,
            )
            or (
                re.search(r"\brang\b", norm_clean)
                and not re.search(r"\b(?:rang la|nhan dinh rang|cho rang|nghi rang|thay rang|biet rang|tin rang|noi rang)\b", norm_clean)
                and any(k in norm_clean for k in ("sau", "nho", "tram", "tay", "ham", "nuou", "loi", "tuy", "nieng", "kham rang", "nha si"))
            )
        )
        if has_dental and not any(k in norm_clean for k in ("nguc", "tim", "kho tho")):
            return ("DENTISTRY", "Răng Hàm Mặt", 0.98)

        # -------------------------------------------------------------
        # 2. NEUROLOGY (Thần kinh)
        # Covers both true emergency neurological signs and primary headache presentations
        # -------------------------------------------------------------
        has_true_neuro = bool(
            re.search(
                r"\b(?:meo mieng|meo mat|liet nua nguoi|yeu nua nguoi|noi ngong|u o khong noi|mat ngon ngu|dot quy|tai bien|co giat|dong kinh|dau dau set danh|dau dau du doi chua tung co|mat y thuc|hon me|dong tu gian|bi tieu kem te liet chi)\b",
                norm_clean,
            )
        )
        has_headache = bool(
            re.search(
                r"\b(?:dau dau|nhuc dau|dau nua dau|migraine|dau dau am i|dau dau vung tran|dau dau sau gay)\b",
                norm_clean,
            )
        )
        if has_true_neuro or has_headache:
            return ("NEUROLOGY", "Thần kinh", 0.98)

        # -------------------------------------------------------------
        # 3. MUSCULOSKELETAL & ORTHOPEDICS (Cơ xương khớp)
        # Covers muscle strains, gym soreness (DOMS), back pain, shoulder, neck, legs
        # -------------------------------------------------------------
        has_msk = bool(
            re.search(
                r"\b(?:dau co|moi co|cang co|e am co|nhuc co|co bap|bap tay|canh tay|khop vai|dau vai|moi vai|vai gay|co vai gay|co gay|dau lung|moi lung|that lung|cot song|khop goi|dau goi|bap chan|cang chan|co chan|ban chan|mat ca|dui|bong gan|trat khop|thoai hoa|viem gan|chuot rut|gian co|doms|sau gym|tap gym|tap ta|tap luyen|ngoi lau|ngoi may tinh|khieng vac|mang vac)\b",
                norm_clean,
            )
        )
        # Musculoskeletal chest wall pain (costochondritis, strain after workout)
        is_chest_wall_msk = bool(
            re.search(r"\b(?:co nguc|co lien suon|an vao dau nguc|sau tap ta|sau tap gym)\b", norm_clean)
            and not any(k in norm_clean for k in ("lan tay trai", "lan ham", "vat mo hoi", "va mo hoi", "ngat"))
        )

        if has_msk or is_chest_wall_msk:
            # Check if there is also genuine chest emergency
            has_cardiac_flags = bool(
                re.search(r"\b(?:lan tay trai|lan ham|lan lung|bop nghet|de nang|vat mo hoi|va mo hoi|kho tho du doi)\b", norm_clean)
            )
            if not has_cardiac_flags:
                return ("ORTHOPEDICS", "Cơ xương khớp", 0.96)

        # -------------------------------------------------------------
        # 4. CARDIOVASCULAR (Tim mạch)
        # -------------------------------------------------------------
        has_cardio = bool(
            re.search(
                r"\b(?:tuc nguc|dau nguc|nang nguc|dau that nguc|bop nghet nguc|dau vung tim|tim dap nhanh|danh trong nguc|hoi hop|loan nhip tim|mach nhanh|nhoi mau co tim|benh mach vanh|tang huyet ap|huyet ap cao)\b",
                norm_clean,
            )
        )
        if has_cardio:
            return ("CARDIOLOGY", "Tim mạch", 0.95)

        # -------------------------------------------------------------
        # 5. RESPIRATORY (Hô hấp)
        # -------------------------------------------------------------
        has_pulmo = bool(
            re.search(
                r"\b(?:kho tho|tho gap|tho doc|tho khok khe|tho rit|phoi|viem phoi|hen|suyen|viem phe quan|ho keo dai|ho ra mau|tran khi)\b",
                norm_clean,
            )
        )
        if has_pulmo:
            return ("PULMONOLOGY", "Hô hấp", 0.94)

        # -------------------------------------------------------------
        # 6. ENT (Tai Mũi Họng)
        # -------------------------------------------------------------
        has_ent = bool(
            re.search(
                r"\b(?:dau hong|viem hong|ngat mui|so mui|chay nuoc mui|viem xoang|u tai|dau tai|chay mu tai|viem amidan|khan tieng|mat tieng)\b",
                norm_clean,
            )
        )
        if has_ent:
            return ("ENT", "Tai Mũi Họng", 0.95)

        # -------------------------------------------------------------
        # 7. GASTROENTEROLOGY (Tiêu hóa)
        # -------------------------------------------------------------
        has_gastro = bool(
            re.search(
                r"\b(?:dau da day|trao nguoc|o chua|o nong|day bung|kho tieu|dau bung|tieu chay|tao bon|viem loet da day|non ra mau|di ngoai ra mau)\b",
                norm_clean,
            )
        )
        if has_gastro:
            return ("GASTROENTEROLOGY", "Tiêu hóa", 0.95)

        # -------------------------------------------------------------
        # 8. DERMATOLOGY (Da liễu)
        # -------------------------------------------------------------
        has_derm = bool(
            re.search(
                r"\b(?:ngua da|noi me day|phat ban|di ung da|man do|mun nhot|viem da|bong troc da|mun nuoc|zona)\b",
                norm_clean,
            )
        )
        if has_derm:
            return ("DERMATOLOGY", "Da liễu", 0.95)

        # -------------------------------------------------------------
        # 9. GENERAL / INTERNAL MEDICINE (Nội tổng quát)
        # -------------------------------------------------------------
        return ("GENERAL", "Nội tổng quát", 0.70)
