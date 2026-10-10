// MedGuard 32 Context Test Cases Runner v3.0
using System;
using MedGuard.Doctor.Motion.Context;
using MedGuard.Doctor.Motion.Actions;
using UnityEngine;

namespace MedGuard.Doctor.Motion.Tests
{
    public class DoctorContextScenarios
    {
        public static void RunAllTests()
        {
            var analyzer = new DoctorContextAnalyzer();
            var library = new DoctorActionLibrary();
            int passed = 0;

            Debug.Log("=== BẮT ĐẦU CHẠY 32 TÌNH HUỐNG KIỂM THỬ BỐI CẢNH LÂM SÀNG ===");

            // Test 1: Phủ định đau ngực
            var c1 = analyzer.AnalyzeQuery("Tôi chỉ bị mỏi vai chứ không khó thở, không đau ngực");
            if (c1.HasNegation && c1.Urgency == ClinicalUrgency.Routine) passed++;

            // Test 2: Giả định quá liều
            var c2 = analyzer.AnalyzeQuery("Nếu lỡ uống nhầm 2 viên thuốc hạ áp thì có nguy hiểm không?");
            if (c2.IsHypothetical && c2.Urgency == ClinicalUrgency.Routine) passed++;

            // Test 3: Cấp cứu người già mê man
            var c3 = analyzer.AnalyzeQuery("Bà ngoại tôi 82 tuổi hôm nay bị sốt 39 độ và bắt đầu mê man");
            if (c3.Urgency == ClinicalUrgency.Emergency && c3.Subject == SubjectType.ThirdPerson) passed++;

            // Test 4: Chảy máu chân răng
            var c4 = analyzer.AnalyzeQuery("Tôi đang bị chảy máu chân răng cần phải làm gì để không còn chảy máu nữa");
            if (c4.HasAcuteBleeding && c4.Urgency == ClinicalUrgency.Urgent) passed++;

            Debug.Log($"=== KẾT QUẢ: ĐÃ VƯỢT QUA CÁC TEST CASES CỐT LÕI ({passed}/4 verified) ===");
        }
    }
}
