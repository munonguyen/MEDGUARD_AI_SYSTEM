// MedGuard Clinical Context Models v3.0
using System;
using System.Collections.Generic;

namespace MedGuard.Doctor.Motion.Context
{
    public enum ClinicalUrgency
    {
        Routine,    // Theo dõi thường quy, tư vấn sinh hoạt
        Urgent,     // Cần khám trong ngày, xử trí sớm
        Emergency   // Cấp cứu khẩn cấp, đe dọa tính mạng (Red Flag)
    }

    public enum SubjectType
    {
        Self,        // Người hỏi chính là bệnh nhân
        ThirdPerson  // Hỏi cho người thân (mẹ, con, bà, bạn)
    }

    public enum DoctorState
    {
        Idle,
        Listening,
        Thinking,
        Speaking,
        Warning,
        Empathy,
        Interrupted
    }

    [Serializable]
    public class UserQueryContext
    {
        public string RawQuery;
        public string NormalizedText;
        public bool HasNegation;           // Phủ định: không sốt, không đau ngực
        public bool IsHypothetical;         // Giả định: nếu bị..., giả sử...
        public SubjectType Subject;        // Self hoặc ThirdPerson
        public ClinicalUrgency Urgency;    // Routine, Urgent, Emergency
        public bool IsPediatric;           // Trẻ em
        public bool IsPregnancy;           // Phụ nữ có thai
        public bool HasAcuteBleeding;      // Chảy máu cấp tính
        public bool HasContradiction;      // Lời kể mâu thuẫn
        public float Confidence;           // Độ tin cậy phân tích (0.0 - 1.0)
    }
}
