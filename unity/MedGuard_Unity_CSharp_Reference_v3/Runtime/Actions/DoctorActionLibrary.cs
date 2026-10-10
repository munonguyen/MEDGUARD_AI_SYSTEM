// MedGuard Action Library v3.0 (Đầy đủ 32 nhóm & 64 biến thể)
using System;
using System.Collections.Generic;
using MedGuard.Doctor.Motion.Context;
using UnityEngine;

namespace MedGuard.Doctor.Motion.Actions
{
    public class DoctorActionLibrary
    {
        private readonly Dictionary<string, DoctorActionDefinition> _actions = new Dictionary<string, DoctorActionDefinition>();

        public int TotalRegisteredVariants => _actions.Count;

        public DoctorActionLibrary()
        {
            RegisterAll64Variants();
        }

        public DoctorActionDefinition GetAction(string variantId)
        {
            if (_actions.TryGetValue(variantId, out var action))
                return action;

            return _actions.ContainsKey("LISTEN_NEUTRAL_STILL") ? _actions["LISTEN_NEUTRAL_STILL"] : null;
        }

        public bool ValidateAction(string variantId, UserQueryContext context, out string violationReason)
        {
            violationReason = string.Empty;

            // CẤM 1: Cấm cười cợt hoặc cử chỉ thư giãn khi ca cấp cứu (Emergency Red Flag)
            if (context.Urgency == ClinicalUrgency.Emergency)
            {
                if (variantId == "GREET_WARM_NOD" || variantId == "LIFESTYLE_OPEN_EXPANSIVE" || variantId == "LAB_NORMAL_REASSURE")
                {
                    violationReason = "VIOLATION: Cấm cử chỉ tươi vui/thư giãn trong tình huống cấp cứu đe dọa tính mạng.";
                    return false;
                }
            }

            // CẤM 2: Không kích hoạt cảnh báo đỏ hoảng hốt khi câu hỏi chỉ là giả định
            if (context.IsHypothetical)
            {
                if (variantId == "EMERGENCY_RAISE_PALM_HALT" || variantId == "CONVULSION_URGENT_CALM")
                {
                    violationReason = "VIOLATION: Không kích hoạt cử chỉ cấp cứu thực tế cho câu hỏi giả định lý thuyết.";
                    return false;
                }
            }

            // CẤM 3: Khi thông tin có phủ định loại trừ triệu chứng, không kích hoạt cảnh báo triệu chứng đó
            if (context.HasNegation && variantId == "EMERGENCY_SERIOUS_STILL")
            {
                violationReason = "VIOLATION: Bệnh nhân đã phủ định triệu chứng nguy hiểm, không kích hoạt báo động đỏ.";
                return false;
            }

            return true;
        }

        private void RegisterAll64Variants()
        {
            Register("GREET_WARM_NOD", "GRP_01_GREETING", "Chào ấm áp kèm cúi đầu nhẹ", 2.2f);
            Register("GREET_NEUTRAL_OPEN", "GRP_01_GREETING", "Chào trung tính mở lòng bàn tay", 1.8f);
            Register("LISTEN_LEAN_FORWARD", "GRP_02_ATTENTIVE_LISTENING", "Nghiêng người chú ý", 3.5f);
            Register("LISTEN_NEUTRAL_STILL", "GRP_02_ATTENTIVE_LISTENING", "Lắng nghe trung tính điềm đạm", 4.0f);
            Register("EMPATHY_HAND_CHEST", "GRP_03_EMPATHY_REASSURANCE", "Tay đặt ngực trên thấu cảm", 2.8f);
            Register("EMPATHY_OPEN_CALM", "GRP_03_EMPATHY_REASSURANCE", "Hai tay hạ thấp xoa dịu", 3.2f);
            Register("INQUIRE_OPEN_PALMS", "GRP_04_SYMPTOM_INQUIRY", "Mở tay hỏi chi tiết", 2.4f);
            Register("INQUIRE_CLARIFICATION", "GRP_04_SYMPTOM_INQUIRY", "Tay chỉ định làm rõ", 2.0f);
            Register("NEGATION_SUBTLE_NOD", "GRP_05_NEGATION_RECOGNITION", "Gật đầu xác nhận loại trừ", 1.6f);
            Register("NEGATION_NOTING_DOWN", "GRP_05_NEGATION_RECOGNITION", "Liếc mắt ghi nhận âm tính", 2.5f);
            Register("EMERGENCY_SERIOUS_STILL", "GRP_06_EMERGENCY_ALERT", "Nghiêm nghị bất động cảnh báo đỏ", 3.0f);
            Register("EMERGENCY_RAISE_PALM_HALT", "GRP_06_EMERGENCY_ALERT", "Nâng lòng bàn tay ngăn chặn", 2.2f);
            Register("URGENT_DIRECTIVE_HAND", "GRP_07_URGENT_REFERRAL", "Bàn tay chỉ dẫn phương hướng", 2.5f);
            Register("URGENT_FOCUSED_LEAN", "GRP_07_URGENT_REFERRAL", "Nghiêng người nhấn mạnh thời gian", 2.8f);
            Register("EXPLAIN_DUAL_HAND_LEVEL", "GRP_08_EXPLANATION_ANATOMICAL", "Hai tay nhịp nhàng phân tích", 3.6f);
            Register("EXPLAIN_PRECISION_PINCH", "GRP_08_EXPLANATION_ANATOMICAL", "Ngón tay chụm tinh tế", 2.4f);
            Register("MED_HAND_HOLD_IMAGINED", "GRP_09_MEDICATION_INSTRUCTION", "Bàn tay khum giữ hướng dẫn", 3.0f);
            Register("MED_COUNTING_SEQUENCE", "GRP_09_MEDICATION_INSTRUCTION", "Bàn tay đếm nhịp liều lượng", 3.5f);
            Register("LIFESTYLE_OPEN_EXPANSIVE", "GRP_10_LIFESTYLE_ADVICE", "Hai tay mở rộng thư thái", 3.0f);
            Register("LIFESTYLE_CALM_SETTLE", "GRP_10_LIFESTYLE_ADVICE", "Hạ tay nhẹ nhàng ổn định", 2.6f);
            Register("THINK_EYE_DEFLECT", "GRP_11_UNCERTAIN_THINKING", "Ánh mắt lệch góc suy ngẫm", 2.0f);
            Register("THINK_HAND_CHIN_NEAR", "GRP_11_UNCERTAIN_THINKING", "Tay gần cằm đắn đo", 2.5f);
            Register("DISCLAIM_PALMS_OUT_LOW", "GRP_12_DISCLAIMER_CLINICAL", "Hai lòng bàn tay mở thấp khuyến cáo", 2.8f);
            Register("DISCLAIM_HAND_TO_CHEST_FORMAL", "GRP_12_DISCLAIMER_CLINICAL", "Đặt tay trước ngực đoan trang", 2.4f);
            Register("HYPO_HEAD_TILT_ENGAGE", "GRP_13_HYPOTHETICAL_CLARIFY", "Nghiêng đầu giải thích giả định", 2.6f);
            Register("HYPO_GESTURE_WEIGHING", "GRP_13_HYPOTHETICAL_CLARIFY", "Hai tay như bàn cân so sánh", 3.2f);
            Register("THIRD_PERSON_RESPECTFUL_NOD", "GRP_14_THIRD_PERSON_ADDRESS", "Gật đầu lắng nghe về người thân", 2.5f);
            Register("THIRD_PERSON_GUIDE_PROMPT", "GRP_14_THIRD_PERSON_ADDRESS", "Mở tay hỏi tuổi và tiền sử người thân", 2.8f);
            Register("CONTRADICT_GENTLE_PAUSE", "GRP_15_CONTRADICTION_PROBE", "Dừng nhẹ tế nhị làm rõ", 2.2f);
            Register("CONTRADICT_PALM_ROTATION", "GRP_15_CONTRADICTION_PROBE", "Lật bàn tay đề nghị xác nhận", 2.5f);
            Register("CHRONIC_STEADY_WARMTH", "GRP_16_CHRONIC_MANAGEMENT", "Tư thế đĩnh đạc kiên trì", 3.2f);
            Register("CHRONIC_RHYTHM_COUNT", "GRP_16_CHRONIC_MANAGEMENT", "Nhịp tay nhắc đo chỉ số định kỳ", 2.8f);
            Register("PAIN_SYMPATHETIC_WINCE_MICRO", "GRP_17_PAIN_ASSESSMENT", "Vi thấu cảm cơn đau", 2.2f);
            Register("PAIN_SCALE_INDICATION", "GRP_17_PAIN_ASSESSMENT", "Bàn tay minh họa thang điểm đau", 3.0f);
            Register("HYGIENE_CLEAN_GESTURE", "GRP_18_PREVENTION_HYGIENE", "Cử chỉ gọn gàng vô khuẩn", 2.8f);
            Register("HYGIENE_STEP_DELINEATION", "GRP_18_PREVENTION_HYGIENE", "Phân định các bước sát khuẩn", 3.2f);
            Register("FOLLOWUP_CALENDAR_INDICATE", "GRP_19_FOLLOW_UP_SCHEDULING", "Bàn tay nghiêng nhắc hẹn lịch", 2.5f);
            Register("FOLLOWUP_REASSURING_WAVE_LOW", "GRP_19_FOLLOW_UP_SCHEDULING", "Tay nâng an tâm theo dõi", 2.4f);
            Register("ALLERGY_ALERT_STEADY", "GRP_20_ALLERGY_WARNING", "Tư thế cảnh báo phản vệ", 2.8f);
            Register("ALLERGY_EMERGENCY_STOP", "GRP_20_ALLERGY_WARNING", "Ra hiệu ngưng thuốc lập tức", 2.0f);
            Register("SPECIAL_GENTLE_LEAN", "GRP_21_SPECIAL_POPULATION", "Nghiêng người cẩn trọng", 3.0f);
            Register("SPECIAL_PROTECTIVE_HOLD", "GRP_21_SPECIAL_POPULATION", "Hai tay che chở bảo bọc", 2.8f);
            Register("DIET_SEPARATION_HANDS", "GRP_22_DIET_NUTRITION", "Hai tay phân tách kiêng - nên", 3.2f);
            Register("DIET_AFFIRMATIVE_PALM", "GRP_22_DIET_NUTRITION", "Lòng bàn tay nâng món tốt", 2.5f);
            Register("MENTAL_DEEP_BREATHE_SYNC", "GRP_23_MENTAL_HEALTH_SUPPORT", "Đồng bộ nhịp thở sâu", 4.0f);
            Register("MENTAL_OPEN_HEARING", "GRP_23_MENTAL_HEALTH_SUPPORT", "Tư thế mở lòng tĩnh lặng", 3.5f);
            Register("LAB_READING_ATTENTION", "GRP_24_LAB_TEST_EXPLANATION", "Đọc chỉ số rồi giải thích", 3.2f);
            Register("LAB_NORMAL_REASSURE", "GRP_24_LAB_TEST_EXPLANATION", "Tay hạ báo tin chỉ số tốt", 2.4f);
            Register("VACCINE_ARM_INDICATE_PROXIMAL", "GRP_25_VACCINATION_CONSULT", "Chỉ vùng cơ delta gián tiếp", 2.6f);
            Register("VACCINE_IMMUNITY_SHIELD", "GRP_25_VACCINATION_CONSULT", "Hai tay che chở miễn dịch", 3.0f);
            Register("INTERRUPT_SMOOTH_SETTLE", "GRP_26_INTERRUPTION_HANDOFF", "Hạ tay quán tính 0.3s ngậm miệng", 0.4f);
            Register("INTERRUPT_HEAD_RESET", "GRP_26_INTERRUPTION_HANDOFF", "Quay đầu chú ý lắng nghe lại", 0.5f);
            Register("AUDIO_LOSS_PUZZLED_NEUTRAL", "GRP_27_AUDIO_LOSS_HANDOFF", "Nghiêng đầu lắng nghe tín hiệu", 2.2f);
            Register("AUDIO_LOSS_REQUEST_REPEAT", "GRP_27_AUDIO_LOSS_HANDOFF", "Mở tay xin nhắc lại", 2.0f);
            Register("CONFIRM_FORWARD_NOD", "GRP_28_CONFIRMATION_CHECK", "Gật nhẹ hỏi đã nắm rõ chưa", 2.2f);
            Register("CONFIRM_PAUSE_WAIT", "GRP_28_CONFIRMATION_CHECK", "Giữ tĩnh chờ phản hồi", 1.8f);
            Register("CLOSE_FORMAL_BOW", "GRP_29_TERMINATION_CLOSING", "Cúi đầu chào trang trọng", 2.5f);
            Register("CLOSE_WARM_WISH", "GRP_29_TERMINATION_CLOSING", "Nâng tay chúc sức khỏe", 2.8f);
            Register("CONVULSION_URGENT_CALM", "GRP_30_HIGH_FEVER_CONVULSION", "Ra hiệu bình tĩnh dứt khoát", 2.8f);
            Register("CONVULSION_SIDE_POSITION", "GRP_30_HIGH_FEVER_CONVULSION", "Hai tay mô phỏng tư thế nằm nghiêng", 3.0f);
            Register("HEMOSTASIS_COMPRESS_GESTURE", "GRP_31_BLEEDING_HEMOSTASIS", "Mô phỏng ép chặt cầm máu tại chỗ", 3.0f);
            Register("HEMOSTASIS_ELEVATION_INDICATE", "GRP_31_BLEEDING_HEMOSTASIS", "Nhắc nhở ngồi thẳng đầu cao", 2.6f);
            Register("BURN_COOL_WATER_INDICATE", "GRP_32_BURN_TRAUMA_FIRST_AID", "Minh họa xả nước mát liên tục", 3.0f);
            Register("BURN_PROTECT_CLEAN", "GRP_32_BURN_TRAUMA_FIRST_AID", "Bàn tay khum che chở vô khuẩn", 3.2f);
        }

        private void Register(string id, string grp, string name, float duration)
        {
            _actions[id] = new DoctorActionDefinition
            {
                VariantId = id,
                GroupId = grp,
                ActionName = name,
                DurationSeconds = duration
            };
        }
    }
}
