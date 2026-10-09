// MedGuard Anatomical IK Limiter v3.0
// Đảm bảo khuỷu tay dưới vai khi chào, kiểm soát góc xoay cổ tay an toàn
using UnityEngine;

namespace MedGuard.Doctor.Motion.IK
{
    public class DoctorIKLimiter
    {
        public static Vector3 ClampHandTarget(Vector3 handTarget, Vector3 shoulderPosition, float armLength, bool isGreeting)
        {
            Vector3 offset = handTarget - shoulderPosition;

            // Ràng buộc 1: Chiều dài không vượt quá cánh tay
            if (offset.magnitude > armLength * 0.95f)
            {
                offset = offset.normalized * (armLength * 0.95f);
            }

            // Ràng buộc 2: Khi chào, khuỷu tay và bàn tay không vượt quá tầm mắt/vai
            if (isGreeting && offset.y > 0.05f)
            {
                offset.y = 0.05f; // Ngang hoặc dưới vai
            }

            return shoulderPosition + offset;
        }
    }
}
