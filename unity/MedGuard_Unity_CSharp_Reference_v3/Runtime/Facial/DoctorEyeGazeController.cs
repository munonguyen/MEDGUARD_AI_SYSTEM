// MedGuard Social Eye Gaze & Blink Controller v3.0
using System;
using UnityEngine;

namespace MedGuard.Doctor.Motion.Facial
{
    public class DoctorEyeGazeController
    {
        private readonly Transform _headBone;
        private readonly Transform _leftEye;
        private readonly Transform _rightEye;

        private float _blinkTimer;
        private float _nextBlinkInterval = 3.5f;
        private bool _isBlinking;
        private float _blinkProgress;

        public DoctorEyeGazeController(Transform head, Transform leftEye, Transform rightEye)
        {
            _headBone = head;
            _leftEye = leftEye;
            _rightEye = rightEye;
        }

        public void UpdateGaze(Vector3 patientHeadPosition, float deltaTime, out float blinkWeight)
        {
            blinkWeight = UpdateBlink(deltaTime);

            if (_headBone != null)
            {
                Vector3 direction = (patientHeadPosition - _headBone.position).normalized;
                Quaternion targetRot = Quaternion.LookRotation(direction, Vector3.up);
                _headBone.rotation = Quaternion.Slerp(_headBone.rotation, targetRot, deltaTime * 2.5f);
            }
        }

        private float UpdateBlink(float deltaTime)
        {
            _blinkTimer += deltaTime;
            if (!_isBlinking && _blinkTimer >= _nextBlinkInterval)
            {
                _isBlinking = true;
                _blinkProgress = 0f;
                _nextBlinkInterval = UnityEngine.Random.Range(2.5f, 5.0f);
            }

            if (_isBlinking)
            {
                _blinkProgress += deltaTime * 8f; // Thời gian nhắm-mở mắt ~120ms
                if (_blinkProgress >= 1f)
                {
                    _isBlinking = false;
                    _blinkTimer = 0f;
                    return 0f;
                }
                return Mathf.Sin(_blinkProgress * Mathf.PI);
            }

            return 0f;
        }
    }
}
