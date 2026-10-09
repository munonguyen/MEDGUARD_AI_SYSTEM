// MedGuard Gesture Planner v3.0
// Lập kế hoạch 4 pha (Preparation, Stroke, Hold, Retraction) và xử lý ngắt lời mượt mà
using System;
using UnityEngine;

namespace MedGuard.Doctor.Motion.Planning
{
    public enum GesturePhase
    {
        IdleRest,
        Preparation,
        Stroke,
        Hold,
        Retraction
    }

    public class DoctorGesturePlanner
    {
        public GesturePhase CurrentPhase { get; private set; } = GesturePhase.IdleRest;
        public float PhaseProgress { get; private set; }
        public float CurrentWeight { get; private set; }

        private float _prepTime = 0.4f;
        private float _strokeTime = 1.2f;
        private float _holdTime = 0.5f;
        private float _retractTime = 0.5f;
        private float _elapsedTime = 0f;

        public void StartGesture(float duration)
        {
            _elapsedTime = 0f;
            CurrentPhase = GesturePhase.Preparation;
            _prepTime = Mathf.Max(0.2f, duration * 0.15f);
            _strokeTime = Mathf.Max(0.4f, duration * 0.50f);
            _holdTime = Mathf.Max(0.2f, duration * 0.15f);
            _retractTime = Mathf.Max(0.2f, duration * 0.20f);
        }

        public void Update(float deltaTime)
        {
            if (CurrentPhase == GesturePhase.IdleRest)
            {
                CurrentWeight = 0f;
                return;
            }

            _elapsedTime += deltaTime;

            if (_elapsedTime < _prepTime)
            {
                CurrentPhase = GesturePhase.Preparation;
                PhaseProgress = _elapsedTime / _prepTime;
                CurrentWeight = Mathf.SmoothStep(0f, 1f, PhaseProgress);
            }
            else if (_elapsedTime < _prepTime + _strokeTime)
            {
                CurrentPhase = GesturePhase.Stroke;
                PhaseProgress = (_elapsedTime - _prepTime) / _strokeTime;
                CurrentWeight = 1f;
            }
            else if (_elapsedTime < _prepTime + _strokeTime + _holdTime)
            {
                CurrentPhase = GesturePhase.Hold;
                PhaseProgress = (_elapsedTime - _prepTime - _strokeTime) / _holdTime;
                CurrentWeight = 1f;
            }
            else if (_elapsedTime < _prepTime + _strokeTime + _holdTime + _retractTime)
            {
                CurrentPhase = GesturePhase.Retraction;
                PhaseProgress = (_elapsedTime - _prepTime - _strokeTime - _holdTime) / _retractTime;
                CurrentWeight = Mathf.SmoothStep(1f, 0f, PhaseProgress);
            }
            else
            {
                CurrentPhase = GesturePhase.IdleRest;
                CurrentWeight = 0f;
            }
        }

        public void ForceInterrupt(float settleDuration = 0.3f)
        {
            // Ngay lập tức chuyển sang Retraction nhanh để tránh khựng hình (Inertial settle)
            CurrentPhase = GesturePhase.Retraction;
            _retractTime = settleDuration;
            _elapsedTime = _prepTime + _strokeTime + _holdTime;
        }
    }
}
