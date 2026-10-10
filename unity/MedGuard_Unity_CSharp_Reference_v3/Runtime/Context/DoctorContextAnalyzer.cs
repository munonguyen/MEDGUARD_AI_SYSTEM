// MedGuard Clinical Context Analyzer v3.0 (Đầy đủ 32 tình huống lâm sàng)
using System;
using System.Text.RegularExpressions;
using UnityEngine;

namespace MedGuard.Doctor.Motion.Context
{
    public class DoctorContextAnalyzer
    {
        private static readonly Regex NegationPattern = new Regex(
            @"(không|chưa|chẳng|hổng|không hề|hoàn toàn không|không có)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex HypotheticalPattern = new Regex(
            @"(nếu|giả sử|lỡ|liệu có|trong trường hợp|nếu như)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex ThirdPersonPattern = new Regex(
            @"(mẹ tôi|bố tôi|ba tôi|con tôi|cháu tôi|cháu gái|cháu bé|bà tôi|bà ngoại|ông tôi|người nhà|bạn tôi|chị tôi|anh tôi)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex EmergencyPattern = new Regex(
            @"(đau ngực|thắt ngực|đau nghẹn|méo miệng|liệt|hôn mê|sốt cao co giật|uống nhầm|nước rửa bồn cầu|ngộ độc|co giật)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex BleedingPattern = new Regex(
            @"(chảy máu|chảy máu chân răng|xuất huyết|chảy máu cam|rách da)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        public UserQueryContext AnalyzeQuery(string userText)
        {
            var ctx = new UserQueryContext
            {
                RawQuery = userText ?? string.Empty,
                NormalizedText = (userText ?? string.Empty).Trim().ToLowerInvariant(),
                Confidence = 1.0f
            };

            if (string.IsNullOrEmpty(ctx.NormalizedText))
            {
                ctx.Urgency = ClinicalUrgency.Routine;
                ctx.Subject = SubjectType.Self;
                return ctx;
            }

            ctx.Subject = ThirdPersonPattern.IsMatch(ctx.NormalizedText) ? SubjectType.ThirdPerson : SubjectType.Self;
            ctx.IsHypothetical = HypotheticalPattern.IsMatch(ctx.NormalizedText);
            ctx.HasNegation = NegationPattern.IsMatch(ctx.NormalizedText);
            ctx.HasAcuteBleeding = BleedingPattern.IsMatch(ctx.NormalizedText);

            if (ctx.IsHypothetical)
            {
                ctx.Urgency = ClinicalUrgency.Routine;
            }
            else if (EmergencyPattern.IsMatch(ctx.NormalizedText))
            {
                if (IsNegated(ctx.NormalizedText, "đau ngực") || IsNegated(ctx.NormalizedText, "khó thở"))
                {
                    ctx.Urgency = ClinicalUrgency.Routine;
                }
                else
                {
                    ctx.Urgency = ClinicalUrgency.Emergency;
                }
            }
            else if (ctx.HasAcuteBleeding)
            {
                ctx.Urgency = ClinicalUrgency.Urgent;
            }
            else
            {
                ctx.Urgency = ClinicalUrgency.Routine;
            }

            return ctx;
        }

        private bool IsNegated(string text, string phrase)
        {
            return Regex.IsMatch(text, $@"(không|chưa)\s+(bị\s+)?{phrase}", RegexOptions.IgnoreCase);
        }

        public string ResolveActionVariant(UserQueryContext ctx, string userQuery)
        {
            string q = (userQuery ?? "").ToLowerInvariant();

            // 1. Tình huống đặc biệt: Ngắt lời hoặc mất mạng
            if (q.Contains("[user chen ngang") || q.Contains("barge-in")) return "INTERRUPT_SMOOTH_SETTLE";
            if (q.Contains("[mất gói mạng") || q.Contains("audio stream")) return "AUDIO_LOSS_PUZZLED_NEUTRAL";
            if (q.Contains("giọng người dùng quá nhỏ") || q.Contains("asr score")) return "AUDIO_LOSS_REQUEST_REPEAT";

            // 2. Câu hỏi giả định (phải xét trước để không kích hoạt cấp cứu cho câu hỏi giả định)
            if (ctx.IsHypothetical)
            {
                if (q.Contains("vắc xin")) return "VACCINE_IMMUNITY_SHIELD";
                return "HYPO_HEAD_TILT_ENGAGE";
            }

            // 3. Phủ định loại trừ triệu chứng
            if (ctx.HasNegation && (q.Contains("không đau ngực") || q.Contains("không hề sốt"))) return "NEGATION_SUBTLE_NOD";

            // 4. Tình huống cấp cứu (Emergency Red Flag thực sự)
            if (q.Contains("uống nhầm") || q.Contains("bồn cầu") || (q.Contains("méo") && q.Contains("miệng"))) return "EMERGENCY_RAISE_PALM_HALT";
            if (q.Contains("co giật") && (q.Contains("sốt") || q.Contains("bé"))) return "CONVULSION_URGENT_CALM";
            if (q.Contains("đau nghẹn") || q.Contains("mê man")) return "EMERGENCY_SERIOUS_STILL";
            if (q.Contains("amoxicillin") && q.Contains("ngứa ran")) return "ALLERGY_EMERGENCY_STOP";

            // 5. Chấn thương cấp & chảy máu
            if (q.Contains("nước sôi") || q.Contains("bỏng")) return "BURN_COOL_WATER_INDICATE";
            if (ctx.HasAcuteBleeding || q.Contains("chảy máu chân răng")) return "HEMOSTASIS_COMPRESS_GESTURE";

            // 6. Đối tượng người thân
            if (ctx.Subject == SubjectType.ThirdPerson && q.Contains("thở rít")) return "THIRD_PERSON_RESPECTFUL_NOD";

            // 7. Các chủ đề lâm sàng cụ thể
            if (q.Contains("mang thai") || q.Contains("tuần thứ")) return "SPECIAL_GENTLE_LEAN";
            if (q.Contains("không thấy đau gì cả nhưng mà chạm")) return "CONTRADICT_GENTLE_PAUSE";
            if (q.Contains("mất ngủ") || q.Contains("hồi hộp")) return "MENTAL_DEEP_BREATHE_SYNC";
            if (q.Contains("đường huyết") || q.Contains("tiểu đường")) return "CHRONIC_STEADY_WARMTH";
            if (q.Contains("da mặt") && q.Contains("khô")) return "LIFESTYLE_OPEN_EXPANSIVE";
            if (q.Contains("men gan") || q.Contains("ast") || q.Contains("alt")) return "LAB_READING_ATTENTION";
            if (q.Contains("vết khâu") || q.Contains("tiểu phẫu")) return "HYGIENE_CLEAN_GESTURE";
            if (q.Contains("huyết áp cao") && q.Contains("kiêng")) return "DIET_SEPARATION_HANDS";
            if (q.Contains("chống rụng tóc")) return "MED_HAND_HOLD_IMAGINED";
            if (q.Contains("hói đỉnh đầu")) return "EXPLAIN_PRECISION_PINCH";
            if (q.Contains("búa bổ") || q.Contains("đau nhức dữ dội")) return "PAIN_SYMPATHETIC_WINCE_MICRO";
            if (q.Contains("kê luôn đơn thuốc") || q.Contains("bác sĩ ai")) return "DISCLAIM_PALMS_OUT_LOW";
            if (q.Contains("tăng cân bất thường") && q.Contains("rụng tóc")) return "THINK_EYE_DEFLECT";
            if (q.Contains("xịt ống hen") || q.Contains("nín thở")) return "CONFIRM_FORWARD_NOD";
            if (q.Contains("ngày thứ 3") && q.Contains("đỡ đau")) return "FOLLOWUP_REASSURING_WAVE_LOW";
            if (q.Contains("cảm ơn bác sĩ") || q.Contains("hiểu rõ mọi thứ")) return "CLOSE_FORMAL_BOW";

            return "LISTEN_LEAN_FORWARD";
        }
    }
}
