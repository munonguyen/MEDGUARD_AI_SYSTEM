// MedGuard Layered Animator v3.0
// Quản lý các lớp hoạt ảnh: Layer 0 Base, Layer 1 UpperBody Gesture, Layer 2 Additive Breathing
using UnityEngine;

namespace MedGuard.Doctor.Motion.Animation
{
    public class DoctorLayeredAnimator
    {
        private readonly Animator _animator;
        private float _breathingPhase = 0f;
        private const float BreathingFrequency = 0.25f; // ~15 nhịp/phút
        private const float BreathingAmplitude = 0.015f; // 1.5cm độ nở ngực

        public DoctorLayeredAnimator(Animator animator)
        {
            _animator = animator;
        }

        public void UpdateBreathing(float deltaTime, Transform chestBone)
        {
            if (chestBone == null) return;

            _breathingPhase += 2f * Mathf.PI * BreathingFrequency * deltaTime;
            if (_breathingPhase > 2f * Mathf.PI) _breathingPhase -= 2f * Mathf.PI;

            float breathOffset = Mathf.Sin(_breathingPhase) * BreathingAmplitude;
            chestBone.localScale = Vector3.one + new Vector3(breathOffset, breathOffset * 0.5f, breathOffset);
        }

        public void SetLayerWeight(int layerIndex, float weight)
        {
            if (_animator != null && layerIndex < _animator.layerCount)
            {
                _animator.SetLayerWeight(layerIndex, Mathf.Clamp01(weight));
            }
        }
    }
}
