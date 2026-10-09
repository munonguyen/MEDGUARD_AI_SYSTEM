// MedGuard Inertial Blender v3.0
// Bộ lọc quán tính C2 khử hoàn toàn giật cục khi thay đổi cử chỉ hoặc bị ngắt lời
using UnityEngine;

namespace MedGuard.Doctor.Motion.Animation
{
    public class DoctorInertialBlender
    {
        private Vector3 _currentVelocity;
        private float _smoothTime = 0.25f;

        public Vector3 SmoothPosition(Vector3 current, Vector3 target, float deltaTime)
        {
            return Vector3.SmoothDamp(current, target, ref _currentVelocity, _smoothTime, Mathf.Infinity, deltaTime);
        }

        public Quaternion SmoothRotation(Quaternion current, Quaternion target, float maxDegreesPerSecond, float deltaTime)
        {
            return Quaternion.RotateTowards(current, target, maxDegreesPerSecond * deltaTime);
        }

        public void ResetVelocity()
        {
            _currentVelocity = Vector3.zero;
        }
    }
}
