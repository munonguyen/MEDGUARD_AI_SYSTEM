"""V25 bounded clinical explanation and next-question reasoning.

This module does not diagnose and cannot change the Safety Kernel disposition.
It converts the episode model into explanation hypotheses that are safe for the
Writer to communicate and selects one unanswered question with the highest
expected management value.
"""

from __future__ import annotations

import re

from app.models.clinical_episode import ClinicalEpisodeModel, DecisionUnknown
from app.models.clinical_reasoning import ClinicalReasoningFrame, MechanismHypothesis
from app.services.clinical_text import normalize_search_text


def _episode_text(episode: ClinicalEpisodeModel) -> str:
    evidence = " ".join(
        fact.evidence_span
        for fact in (*episode.confirmed_positive, *episode.confirmed_negative)
        if fact.evidence_span
    )
    return normalize_search_text(f"{episode.latest_user_message} {evidence}")


def _evidence_matching(episode: ClinicalEpisodeModel, pattern: str) -> tuple[str, ...]:
    regex = re.compile(pattern)
    values: list[str] = []
    for fact in (*episode.confirmed_positive, *episode.confirmed_negative):
        candidate = normalize_search_text(fact.evidence_span)
        if candidate and regex.search(candidate):
            values.append(fact.evidence_span)
    if regex.search(normalize_search_text(episode.latest_user_message)):
        values.append(episode.latest_user_message)
    return tuple(dict.fromkeys(value for value in values if value))[:4]


def _unresolved(episode: ClinicalEpisodeModel, *keys: str) -> tuple[str, ...]:
    wanted = set(keys)
    return tuple(item.key for item in episode.unknown_decision_relevant if item.key in wanted)


def _headache_mechanisms(episode: ClinicalEpisodeModel, text: str) -> list[MechanismHypothesis]:
    values: list[MechanismHypothesis] = []
    screen = bool(re.search(r"\b(man hinh|may tinh|laptop|dien thoai|nhin man hinh|hoc online)\b", text))
    prolonged = bool(re.search(r"\b(ca ngay|nhieu gio|\d+\s*(?:gio|tieng)|lau|lien tuc)\b", text))
    rest_improves = bool(re.search(r"\b(nghi.*(?:do|giam|bot)|do khi nghi|giam khi nghi)\b", text))
    frontal = bool(re.search(r"\b(tran|quanh mat|hoc mat|thai duong)\b", text))
    posture = bool(re.search(r"\b(ngoi|co vai|vai gay|cang co|moi co|tu the)\b", text))
    sleep = bool(re.search(r"\b(mat ngu|thieu ngu|ngu it|thuc khuya)\b", text))
    hydration = bool(re.search(r"\b(it nuoc|khong uong nuoc|mat nuoc|khat)\b", text))
    stress = bool(re.search(r"\b(cang thang|stress|ap luc)\b", text))

    if screen:
        evidence = [episode.latest_user_message]
        if frontal or rest_improves:
            evidence.extend(_evidence_matching(episode, r"\b(tran|quanh mat|hoc mat|nghi|do|giam|bot)\b"))
        values.append(
            MechanismHypothesis(
                hypothesis_id="visual_load_contribution",
                label="Quá tải thị giác có thể góp phần vào đau đầu",
                role="leading" if prolonged or frontal or rest_improves else "contributor",
                support_level="supported" if (prolonged and (frontal or rest_improves)) else "plausible",
                mechanism=(
                    "Nhìn gần và tập trung vào màn hình trong thời gian dài làm hệ điều tiết và hội tụ của mắt "
                    "hoạt động liên tục; sự mỏi thị giác này có thể góp phần tạo cảm giác nặng hoặc đau vùng trán/quanh mắt."
                ),
                evidence_for=tuple(dict.fromkeys(evidence))[:4],
                unresolved=_unresolved(episode, "visual_loss", "onset_speed"),
                patient_safe_statement=(
                    "Việc đau xuất hiện sau thời gian nhìn màn hình làm mỏi thị giác trở thành một khả năng hợp lý, "
                    "nhưng mối liên hệ thời gian này chưa đủ để khẳng định đó là nguyên nhân duy nhất."
                ),
            )
        )

    if screen or posture or prolonged:
        evidence = [episode.latest_user_message]
        values.append(
            MechanismHypothesis(
                hypothesis_id="postural_pericranial_tension",
                label="Căng cơ cổ–vai–vùng quanh sọ có thể cùng góp phần",
                role="leading" if posture else "contributor",
                support_level="supported" if posture else "plausible",
                mechanism=(
                    "Tư thế đầu–cổ ít thay đổi trong thời gian dài có thể làm các cơ cổ, vai và quanh sọ duy trì co căng, "
                    "từ đó góp phần tạo cảm giác đau hoặc nặng đầu."
                ),
                evidence_for=tuple(dict.fromkeys(evidence))[:4],
                unresolved=_unresolved(episode, "trajectory"),
                patient_safe_statement=(
                    "Căng cơ do tư thế kéo dài cũng có thể góp phần, đặc biệt nếu cơn đau thay đổi theo nghỉ ngơi hoặc tư thế."
                ),
            )
        )

    modifier_evidence: list[str] = []
    if sleep:
        modifier_evidence.append("thiếu ngủ/mất ngủ được người dùng mô tả")
    if hydration:
        modifier_evidence.append("dấu hiệu uống ít nước/mất nước được người dùng mô tả")
    if stress:
        modifier_evidence.append("căng thẳng được người dùng mô tả")
    if modifier_evidence:
        values.append(
            MechanismHypothesis(
                hypothesis_id="headache_threshold_modifiers",
                label="Các yếu tố làm hạ ngưỡng đau đầu",
                role="contributor",
                support_level="plausible",
                mechanism=(
                    "Thiếu ngủ, mất nước hoặc căng thẳng có thể làm hệ thần kinh nhạy hơn với kích thích và làm cơn đau đầu dễ xuất hiện hơn."
                ),
                evidence_for=tuple(modifier_evidence),
                patient_safe_statement="Những yếu tố sinh hoạt này có thể làm cơn đau dễ xuất hiện hơn nhưng không thay thế việc sàng lọc dấu hiệu cảnh báo.",
            )
        )

    dangerous_unknowns = _unresolved(
        episode,
        "onset_speed",
        "focal_neurologic_deficit",
        "fever_neck_stiffness",
        "head_trauma",
        "visual_loss",
    )
    if dangerous_unknowns:
        values.append(
            MechanismHypothesis(
                hypothesis_id="secondary_headache_safety_pathway",
                label="Nguyên nhân thứ phát nguy hiểm chưa được loại trừ hoàn toàn",
                role="must_not_miss_pathway",
                support_level="weak",
                mechanism=(
                    "Một số đặc điểm như khởi phát đột ngột, thiếu sót thần kinh, sốt/cứng gáy, chấn thương hoặc giảm thị lực "
                    "có thể thay đổi hoàn toàn mức xử trí; hiện các dữ kiện này chưa được xác nhận đầy đủ."
                ),
                unresolved=dangerous_unknowns,
                patient_safe_statement=(
                    "Hiện chưa có đủ dữ kiện để coi các nguyên nhân nguy hiểm là đã được loại trừ chỉ vì chúng chưa được nhắc tới."
                ),
            )
        )
    return values


def _cardiorespiratory_mechanisms(episode: ClinicalEpisodeModel, text: str) -> list[MechanismHypothesis]:
    values: list[MechanismHypothesis] = []
    reproducible = bool(re.search(r"\b(an vao.*dau|dau khi an|xoay nguoi.*dau|sau tap|tap gym|cang co nguc)\b", text))
    exertional = bool(re.search(r"\b(gang suc|di bo nhanh|leo cau thang|tap the duc).*\b(dau|tuc|nang|kho tho)\b", text))
    if reproducible:
        values.append(
            MechanismHypothesis(
                hypothesis_id="chest_wall_mechanical",
                label="Cơ thành ngực có thể góp phần vào cảm giác đau",
                role="leading",
                support_level="plausible",
                mechanism="Đau tăng khi ấn, vận động thân mình hoặc sau vận động cơ có thể phù hợp với kích thích cơ–xương thành ngực.",
                evidence_for=(episode.latest_user_message,),
                patient_safe_statement="Đặc điểm cơ học có thể làm nguyên nhân thành ngực hợp lý hơn, nhưng không tự loại trừ nguyên nhân tim–phổi nếu xuất hiện dấu hiệu cảnh báo khác.",
            )
        )
    if exertional:
        values.append(
            MechanismHypothesis(
                hypothesis_id="exertional_cardiorespiratory_pathway",
                label="Gắng sức làm tăng nhu cầu tim–phổi và có thể bộc lộ bệnh cảnh nguy cơ",
                role="must_not_miss_pathway",
                support_level="supported",
                mechanism="Khi gắng sức, nhu cầu oxy của cơ thể tăng; khó chịu ngực hoặc khó thở xuất hiện rõ theo gắng sức cần được đánh giá trong bối cảnh tim–phổi.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "radiation_autonomic", "dyspnea_syncope"),
                patient_safe_statement="Việc triệu chứng liên quan gắng sức làm ngưỡng cảnh giác tim–phổi cao hơn và cần xem cùng các dấu hiệu đi kèm.",
            )
        )
    return values


def _gastrointestinal_mechanisms(episode: ClinicalEpisodeModel, text: str) -> list[MechanismHypothesis]:
    values: list[MechanismHypothesis] = []
    migration = bool(re.search(r"\b(chuyen|di chuyen).*\b(bung|ron|ben phai|ben trai)\b", text))
    diarrhea_vomit = bool(re.search(r"\b(tieu chay|non|nôn)\b", text))
    if migration:
        values.append(
            MechanismHypothesis(
                hypothesis_id="abdominal_localization_change",
                label="Sự thay đổi vị trí đau có giá trị định hướng",
                role="leading",
                support_level="supported",
                mechanism="Đau nội tạng có thể khởi đầu lan tỏa rồi khu trú hơn khi cơ quan hoặc phúc mạc vùng đó bị kích thích nhiều hơn.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "peritoneal_signs"),
                patient_safe_statement="Việc đau chuyển vị trí là dữ kiện quan trọng và cần được xem cùng sốt, nôn và dấu hiệu bụng cứng/đau tăng khi cử động.",
            )
        )
    if diarrhea_vomit:
        values.append(
            MechanismHypothesis(
                hypothesis_id="fluid_loss_contribution",
                label="Mất dịch có thể góp phần gây mệt hoặc choáng",
                role="contributor",
                support_level="plausible",
                mechanism="Nôn hoặc tiêu chảy làm mất nước và điện giải; khi đủ nhiều có thể làm giảm thể tích tuần hoàn và gây khát, tim nhanh hoặc choáng khi đứng.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "bleeding_or_dehydration"),
                patient_safe_statement="Nếu nôn/tiêu chảy tiếp tục, dấu hiệu mất nước trở thành yếu tố quan trọng để quyết định cần đánh giá trực tiếp hay không.",
            )
        )
    return values


def _musculoskeletal_mechanisms(episode: ClinicalEpisodeModel, text: str) -> list[MechanismHypothesis]:
    values: list[MechanismHypothesis] = []
    prolonged_sitting = bool(re.search(r"\b(ngoi.*(?:nhieu gio|ca ngay|lau)|may tinh|van phong)\b", text))
    improves_movement = bool(re.search(r"\b(di lai.*(?:do|giam|de chiu)|dung day.*(?:do|giam|de chiu))\b", text))
    if prolonged_sitting or improves_movement:
        values.append(
            MechanismHypothesis(
                hypothesis_id="mechanical_postural_load",
                label="Tải cơ học và tư thế kéo dài có thể góp phần",
                role="leading",
                support_level="supported" if improves_movement else "plausible",
                mechanism="Giữ một tư thế lâu làm cơ cạnh cột sống và mô mềm chịu tải liên tục; thay đổi tư thế hoặc vận động nhẹ có thể giảm tải nếu cơ chế chủ yếu là cơ học.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "motor_sensory_deficit", "cauda_equina_features"),
                patient_safe_statement="Đặc điểm liên quan tư thế làm cơ chế cơ học hợp lý hơn, nhưng yếu chân, tê tăng hoặc rối loạn tiểu tiện sẽ làm thay đổi hoàn toàn mức xử trí.",
            )
        )
    return values


def _dermatology_mechanisms(episode: ClinicalEpisodeModel, text: str) -> list[MechanismHypothesis]:
    values: list[MechanismHypothesis] = []
    norm = normalize_search_text(text)

    # 1. Scratch-itch cycle / mechanical aggravation
    scratching = bool(re.search(r"\b(cang gai|gai|ngua rat|rat da|rat hon|ngua hon|tray xuoc)\b", norm))
    if scratching:
        values.append(
            MechanismHypothesis(
                hypothesis_id="itch_scratch_cycle_aggravation",
                label="Cào gãi kích thích vòng xoắn ngứa - gãi và tăng giải phóng histamin",
                role="leading",
                support_level="supported",
                mechanism="Cào gãi cơ học kích thích đầu tận cùng thần kinh cảm giác và tế bào mast giải phóng thêm histamin, làm phản ứng viêm bùng phát và gây cảm giác càng gãi càng rát ngứa.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "scratch_skin_damage", "airway_mucosal_involvement"),
                patient_safe_statement="Càng gãi càng ngứa rát là biểu hiện điển hình của vòng xoắn kích thích thần kinh - giải phóng histamin tại da; chườm mát và kiềm chế gãi là mấu chốt để cắt cơn ngứa.",
            )
        )

    # 2. Exposure reaction pathway
    exposure = bool(re.search(r"\b(sau khi|thuoc moi|mon la|my pham|hoa chat|con trung)\b", norm))
    if exposure:
        values.append(
            MechanismHypothesis(
                hypothesis_id="exposure_reaction_pathway",
                label="Phản ứng liên quan phơi nhiễm là một hướng cần xem xét",
                role="contributor" if scratching else "leading",
                support_level="plausible",
                mechanism="Một thuốc, thực phẩm, hóa chất hoặc tác nhân tiếp xúc mới có thể hoạt hóa phản ứng viêm/dị ứng và gây ban, ngứa hoặc phù.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "airway_mucosal_involvement", "new_exposure"),
                patient_safe_statement="Mối liên hệ thời gian với phơi nhiễm mới gợi ý một phản ứng liên quan, nhưng dấu hiệu đường thở mới là yếu tố quyết định mức khẩn cấp.",
            )
        )

    # 3. Acute erythema and pruritus / urticaria
    has_rash_pruritus = bool(re.search(r"\b(man ngua|ban do|noi man|phat ban|me day|di ung da)\b", norm))
    if has_rash_pruritus and not values:
        values.append(
            MechanismHypothesis(
                hypothesis_id="acute_erythema_pruritus_reaction",
                label="Phản ứng viêm mạch nông và kích thích thụ thể ngứa ở da",
                role="leading",
                support_level="plausible",
                mechanism="Các chất trung gian gây viêm (đặc biệt histamin) làm giãn mao mạch nông tại bì gây ban đỏ và kích thích đầu tận cùng thần kinh thụ cảm ngứa.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "airway_mucosal_involvement", "rash_distribution_spread"),
                patient_safe_statement="Ban đỏ kèm mẩn ngứa thường là biểu hiện của viêm da dị ứng hoặc kích ứng nông; cần loại trừ ngay dấu hiệu phù niêm mạc hoặc khó thở.",
            )
        )

    return values


def _question_score(domain: str | None, item: DecisionUnknown, latest_text: str = "") -> float:
    impact = {"critical": 40.0, "high": 25.0, "medium": 12.0, "low": 5.0}[item.impact]
    score = impact + 4.0 * len(item.changes)
    if "emergency_disposition" in item.changes:
        score += 12.0
    domain_priority: dict[str, dict[str, float]] = {
        "neurovestibular": {
            "onset_speed": 12.0,
            "focal_neurologic_deficit": 10.0,
            "fever_neck_stiffness": 8.0,
            "visual_loss": 6.0,
        },
        "cardiorespiratory": {
            "dyspnea_syncope": 12.0,
            "radiation_autonomic": 10.0,
            "exertional_relation": 8.0,
        },
        "gastrointestinal": {
            "peritoneal_signs": 12.0,
            "bleeding_or_dehydration": 10.0,
            "pain_location_migration": 7.0,
        },
        "musculoskeletal_spine": {
            "cauda_equina_features": 12.0,
            "motor_sensory_deficit": 10.0,
        },
        "dermatology": {
            "airway_mucosal_involvement": 14.0,
            "rash_distribution_spread": 10.0,
            "new_exposure": 8.0,
            "scratch_skin_damage": 7.0,
        },
        "dental": {
            "swelling_or_infection": 14.0,
            "trigger_sensitivity": 10.0,
            "prior_cavity_damage": 7.0,
        },
        "ophthalmology": {
            "visual_acuity_change": 14.0,
            "discharge_crusting": 10.0,
            "contagion_contact": 7.0,
        },
    }
    target_specs = domain_priority.get(domain or "", {})
    bonus = target_specs.get(item.key, 0.0)
    if item.key in target_specs:
        score += 25.0
    if domain == "dermatology" and item.key == "scratch_skin_damage":
        norm_latest = normalize_search_text(latest_text)
        if any(w in norm_latest for w in ("gai", "cang gai", "rat", "tray")):
            bonus += 5.0
    return score + bonus


def select_next_question(episode: ClinicalEpisodeModel, *, urgency: str) -> DecisionUnknown | None:
    if str(urgency).upper() == "EMERGENCY":
        return None
    if not episode.unknown_decision_relevant:
        return None
    latest_text = episode.latest_user_message or ""
    return max(
        episode.unknown_decision_relevant,
        key=lambda item: (_question_score(episode.chief_domain, item, latest_text), item.key),
    )


def _dental_mechanisms(episode: ClinicalEpisodeModel, text: str) -> list[MechanismHypothesis]:
    values: list[MechanismHypothesis] = []
    norm = normalize_search_text(text)

    infection_sign = bool(re.search(r"\b(sung|sung nuou|chay mu|sung ma|sung ham|kho ha mieng)\b", norm))
    if infection_sign:
        values.append(
            MechanismHypothesis(
                hypothesis_id="acute_odontogenic_infection_abscess",
                label="Nhiễm trùng khoang miệng hoặc áp xe quanh chóp răng",
                role="leading",
                support_level="supported",
                mechanism="Vi khuẩn xâm nhập từ buồng tủy hoặc túi nha chu lan qua chóp răng vào mô mềm quanh cuống, gây sưng phù nề nướu, chảy mủ và nguy cơ lan vào các khoang cân mạc mặt.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "swelling_or_infection"),
                patient_safe_statement="Sưng nề nướu hoặc chảy mủ là dấu hiệu nhiễm trùng quanh răng cần được nha sĩ dẫn lưu và kê thuốc kháng sinh đặc hiệu sớm.",
            )
        )

    values.append(
        MechanismHypothesis(
            hypothesis_id="dentine_hypersensitivity_or_pulp_irritation",
            label="Kích thích ngà răng hoặc buốt tủy do mòn men răng / sâu răng",
            role="contributor" if infection_sign else "leading",
            support_level="supported",
            mechanism="Lộ các ống ngà vi thể (do mòn men răng, tụt nướu) hoặc tổn thương sâu răng khiến kích thích nhiệt, chua ngọt truyền trực tiếp vào thụ thể tủy răng gây phản xạ buốt nhói.",
            evidence_for=(episode.latest_user_message,),
            unresolved=_unresolved(episode, "swelling_or_infection", "trigger_sensitivity"),
            patient_safe_statement="Cơn ê buốt răng thường do mòn men răng hoặc kích thích tủy răng khi tiếp xúc thức ăn đồ uống; cần tránh đồ quá nóng, lạnh và đi khám nha sĩ để hàn trám bảo vệ tủy.",
        )
    )
    return values


def _ophthalmology_mechanisms(episode: ClinicalEpisodeModel, text: str) -> list[MechanismHypothesis]:
    values: list[MechanismHypothesis] = []
    norm = normalize_search_text(text)

    vision_warning = bool(re.search(r"\b(nhin mo|giam thi luc|choi mat|so anh sang|nhuc sau mat|nhuc mat)\b", norm))
    if vision_warning:
        values.append(
            MechanismHypothesis(
                hypothesis_id="keratitis_or_intraocular_pressure_elevation",
                label="Tổn thương giác mạc hoặc tăng nhãn áp cấp",
                role="leading",
                support_level="supported",
                mechanism="Viêm loét giác mạc hoặc ứ trệ thủy dịch làm tăng nhãn áp gây kích thích dây thần kinh sinh ba, làm giảm thị lực và đau buốt sâu trong hốc mắt.",
                evidence_for=(episode.latest_user_message,),
                unresolved=_unresolved(episode, "visual_acuity_change"),
                patient_safe_statement="Đau mắt kèm nhìn mờ hoặc sợ ánh sáng là dấu hiệu cảnh báo tổn thương giác mạc; cần bác sĩ Mắt khám chuyên sâu ngay.",
            )
        )

    values.append(
        MechanismHypothesis(
            hypothesis_id="acute_infectious_conjunctivitis",
            label="Viêm kết mạc cấp (đau mắt đỏ) dịch tễ hoặc dị ứng",
            role="contributor" if vision_warning else "leading",
            support_level="supported",
            mechanism="Tác nhân virus (Adenovirus) hoặc vi khuẩn gây viêm sung huyết mạch máu kết mạc làm mắt đỏ rực, kích thích tiết dịch dử ghèn và cảm giác cộm xốn mi mắt.",
            evidence_for=(episode.latest_user_message,),
            unresolved=_unresolved(episode, "visual_acuity_change", "discharge_crusting"),
            patient_safe_statement="Đau mắt đỏ là bệnh viêm kết mạc cấp rất dễ lây lan; cần nhỏ nước muối sinh lý NaCl 0.9%, kiêng dụi mắt và giữ vệ sinh cá nhân sạch sẽ.",
        )
    )
    return values


def build_contextual_reasoning_frame(
    episode: ClinicalEpisodeModel,
    *,
    urgency: str = "ROUTINE",
) -> ClinicalReasoningFrame:
    text = _episode_text(episode)
    mechanisms: list[MechanismHypothesis] = []

    if episode.chief_domain == "neurovestibular" or "dau dau" in text:
        mechanisms.extend(_headache_mechanisms(episode, text))
    elif episode.chief_domain == "cardiorespiratory":
        mechanisms.extend(_cardiorespiratory_mechanisms(episode, text))
    elif episode.chief_domain == "gastrointestinal":
        mechanisms.extend(_gastrointestinal_mechanisms(episode, text))
    elif episode.chief_domain == "musculoskeletal_spine":
        mechanisms.extend(_musculoskeletal_mechanisms(episode, text))
    elif episode.chief_domain == "dermatology":
        mechanisms.extend(_dermatology_mechanisms(episode, text))
    elif episode.chief_domain == "dental":
        mechanisms.extend(_dental_mechanisms(episode, text))
    elif episode.chief_domain == "ophthalmology":
        mechanisms.extend(_ophthalmology_mechanisms(episode, text))

    question = select_next_question(episode, urgency=urgency)
    leading = tuple(
        item.hypothesis_id
        for item in mechanisms
        if item.role == "leading"
    )
    must_not_miss = tuple(
        unknown.key
        for unknown in episode.unknown_decision_relevant
        if unknown.impact == "critical"
    )
    return ClinicalReasoningFrame(
        mechanisms=tuple(mechanisms),
        leading_hypothesis_ids=leading,
        must_not_miss_unknowns=must_not_miss,
        next_best_question=question.question if question else None,
        next_question_key=question.key if question else None,
    )
