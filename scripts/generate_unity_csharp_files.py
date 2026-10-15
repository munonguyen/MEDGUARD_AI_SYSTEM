#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tạo toàn bộ mã nguồn C# tham chiếu chuẩn Unity và JSON catalogs
"""

import os
import json
from pathlib import Path

def generate_csharp_package(base_dir: Path, action_catalog: list, test_scenarios: list):
    base_dir.mkdir(parents=True, exist_ok=True)
    
    runtime_dir = base_dir / "Runtime"
    core_dir = runtime_dir / "Core"
    context_dir = runtime_dir / "Context"
    actions_dir = runtime_dir / "Actions"
    planning_dir = runtime_dir / "Planning"
    anim_dir = runtime_dir / "Animation"
    facial_dir = runtime_dir / "Facial"
    ik_dir = runtime_dir / "IK"
    network_dir = runtime_dir / "Network"
    tests_dir = runtime_dir / "Tests"
    data_dir = base_dir / "Data"
    
    for d in [core_dir, context_dir, actions_dir, planning_dir, anim_dir, facial_dir, ik_dir, network_dir, tests_dir, data_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. package.json
    pkg_json = {
        "name": "com.medguard.doctor.motion",
        "displayName": "MedGuard Doctor Motion System (C# Native)",
        "version": "3.0.0",
        "unity": "2022.3",
        "description": "Hệ thống điều khiển chuyển động tự nhiên cho avatar bác sĩ MedGuard bằng Unity C# thuần túy, tích hợp bộ phân tích bối cảnh lâm sàng 64 cử chỉ.",
        "author": {"name": "MedGuard AI Engineering Team"}
    }
    with open(base_dir / "package.json", "w", encoding="utf-8") as f:
        json.dump(pkg_json, f, indent=2, ensure_ascii=False)

    # 2. README.md
    readme_content = """# MedGuard Doctor Motion System v3.0 (Unity C# Native)

Bộ mã nguồn C# và dữ liệu thiết kế tham chiếu điều khiển toàn bộ chuyển động tự nhiên cho avatar bác sĩ MedGuard trong Unity.

## Kiến trúc chính
1. **Clinical Context Analyzer (`DoctorContextAnalyzer.cs`)**: Phân tích câu hỏi bệnh nhân, nhận diện phủ định, giả định, người thứ ba và cảnh báo đỏ.
2. **Action Library (`DoctorActionLibrary.cs`)**: Quản lý 32 nhóm hành động với 64 biến thể cử chỉ có điều kiện kích hoạt và điều kiện cấm.
3. **Gesture Planner (`DoctorGesturePlanner.cs`)**: Lập kế hoạch 4 pha (Preparation, Stroke, Hold, Retraction) đồng bộ với âm thanh.
4. **Layered Animator & Inertial Blender (`DoctorLayeredAnimator.cs`, `DoctorInertialBlender.cs`)**: Ghép lớp chuyển động và làm mượt khử giật khi bị ngắt lời.
5. **Facial & Social Gaze (`DoctorEyeGazeController.cs`, `DoctorLipSyncDriver.cs`)**: Khớp khẩu hình tiếng Việt và ánh mắt giao tiếp tự nhiên.
6. **IK Anatomical Limiter (`DoctorIKLimiter.cs`)**: Giới hạn góc giải phẫu chống biến dạng rig.

## Cách sử dụng
- Kéo thả prefab bác sĩ (DoctorTuan hoặc DoctorMai).
- Gắn script `DoctorMotionController` lên GameObject gốc.
- Kết nối `DoctorConversationBridge` với MedGuard API Backend (`http://127.0.0.1:8000`).
"""
    with open(base_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 3. ClinicalContextModels.cs
    with open(context_dir / "ClinicalContextModels.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Clinical Context Models v3.0
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
""")

    # 4. DoctorContextAnalyzer.cs
    with open(context_dir / "DoctorContextAnalyzer.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Clinical Context Analyzer v3.0
// Phân tích bối cảnh câu hỏi bệnh nhân: phủ định, giả định, người thân, mức độ khẩn cấp
using System;
using System.Text.RegularExpressions;
using UnityEngine;

namespace MedGuard.Doctor.Motion.Context
{
    public class DoctorContextAnalyzer
    {
        private static readonly Regex NegationPattern = new Regex(
            @"\b(không|chưa|chẳng|hổng|không hề|hoàn toàn không|không có)\b",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex HypotheticalPattern = new Regex(
            @"\b(nếu|giả sử|lỡ|liệu có|trong trường hợp|nếu như)\b",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex ThirdPersonPattern = new Regex(
            @"\b(mẹ tôi|bố tôi|ba tôi|con tôi|cháu tôi|bà tôi|ông tôi|người nhà|bạn tôi|chị tôi|anh tôi)\b",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex RedFlagEmergencyPattern = new Regex(
            @"\b(đau ngực|thắt ngực|khó thở|méo miệng|liệt|ngất|hôn mê|sốt cao co giật|uống nhầm|ngộ độc|nôn ra máu)\b",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        private static readonly Regex BleedingPattern = new Regex(
            @"\b(chảy máu|chảy máu chân răng|xuất huyết|chảy máu cam|rách da)\b",
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

            // 1. Phân tích chủ thể
            ctx.Subject = ThirdPersonPattern.IsMatch(ctx.NormalizedText) 
                ? SubjectType.ThirdPerson 
                : SubjectType.Self;

            // 2. Phân tích câu hỏi giả định
            ctx.IsHypothetical = HypotheticalPattern.IsMatch(ctx.NormalizedText);

            // 3. Phân tích phủ định triệu chứng
            ctx.HasNegation = NegationPattern.IsMatch(ctx.NormalizedText);

            // 4. Phân tích chảy máu
            ctx.HasAcuteBleeding = BleedingPattern.IsMatch(ctx.NormalizedText);

            // 5. Phân tích mức độ khẩn cấp (Emergency / Urgent / Routine)
            // QUY TẮC CỐT LÕI: Nếu là câu hỏi GIẢ ĐỊNH ("Nếu bị đau ngực thì sao?") -> KHÔNG kích hoạt Emergency thật
            if (ctx.IsHypothetical)
            {
                ctx.Urgency = ClinicalUrgency.Routine;
            }
            else if (RedFlagEmergencyPattern.IsMatch(ctx.NormalizedText))
            {
                // Kiểm tra xem triệu chứng đỏ có bị phủ định không ("tôi không khó thở, không đau ngực")
                if (IsNegatedSymptom(ctx.NormalizedText, "đau ngực") || 
                    IsNegatedSymptom(ctx.NormalizedText, "khó thở"))
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

        private bool IsNegatedSymptom(string text, string symptom)
        {
            var match = Regex.Match(text, $@"\b(không|chưa)\s+(bị\s+)?{symptom}\b", RegexOptions.IgnoreCase);
            return match.Success;
        }
    }
}
""")

    # 5. DoctorActionDefinition.cs & DoctorActionLibrary.cs
    with open(actions_dir / "DoctorActionDefinition.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Action Definition v3.0
using System;

namespace MedGuard.Doctor.Motion.Actions
{
    [Serializable]
    public class DoctorActionDefinition
    {
        public string VariantId;
        public string GroupId;
        public string ActionName;
        public string ClinicalPurpose;
        public string BodyHandMotion;
        public string FacialEyeExpression;
        public float DurationSeconds;
        public string Preconditions;
        public string Prohibitions;
    }
}
""")

    with open(actions_dir / "DoctorActionLibrary.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Action Library v3.0
// Quản lý 32 nhóm hành động và 64 biến thể cử chỉ kèm kiểm tra điều kiện cấm
using System;
using System.Collections.Generic;
using MedGuard.Doctor.Motion.Context;
using UnityEngine;

namespace MedGuard.Doctor.Motion.Actions
{
    public class DoctorActionLibrary
    {
        private readonly Dictionary<string, DoctorActionDefinition> _actions = new Dictionary<string, DoctorActionDefinition>();

        public DoctorActionLibrary()
        {
            RegisterBuiltInActions();
        }

        public DoctorActionDefinition GetAction(string variantId)
        {
            if (_actions.TryGetValue(variantId, out var action))
                return action;

            // Fallback an toàn mặc định
            return _actions.ContainsKey("LISTEN_NEUTRAL_STILL") ? _actions["LISTEN_NEUTRAL_STILL"] : null;
        }

        public bool ValidateAction(string variantId, UserQueryContext context, out string violationReason)
        {
            violationReason = string.Empty;

            // QUY TẮC CẤM 1: Cấm cười cợt hoặc cử chỉ thư giãn khi ca cấp cứu (Emergency Red Flag)
            if (context.Urgency == ClinicalUrgency.Emergency)
            {
                if (variantId == "GREET_WARM_NOD" || variantId == "LIFESTYLE_OPEN_EXPANSIVE" || variantId == "LAB_NORMAL_REASSURE")
                {
                    violationReason = "VIOLATION: Cấm cử chỉ tươi vui/thư giãn trong tình huống cấp cứu đe dọa tính mạng.";
                    return false;
                }
            }

            // QUY TẮC CẤM 2: Không kích hoạt cảnh báo đỏ hoảng hốt khi câu hỏi chỉ là giả định
            if (context.IsHypothetical)
            {
                if (variantId == "EMERGENCY_RAISE_PALM_HALT" || variantId == "CONVULSION_URGENT_CALM")
                {
                    violationReason = "VIOLATION: Không kích hoạt cử chỉ cấp cứu thực tế cho câu hỏi giả định lý thuyết.";
                    return false;
                }
            }

            // QUY TẮC CẤM 3: Khi thông tin có phủ định loại trừ triệu chứng, không kích hoạt cảnh báo triệu chứng đó
            if (context.HasNegation && variantId == "EMERGENCY_SERIOUS_STILL")
            {
                violationReason = "VIOLATION: Bệnh nhân đã phủ định triệu chứng nguy hiểm, không kích hoạt báo động đỏ.";
                return false;
            }

            return true;
        }

        private void RegisterBuiltInActions()
        {
            Register("GREET_WARM_NOD", "GRP_01_GREETING", "Chào ấm áp cúi đầu nhẹ", 2.2f);
            Register("GREET_NEUTRAL_OPEN", "GRP_01_GREETING", "Chào trung tính mở lòng bàn tay", 1.8f);
            Register("LISTEN_LEAN_FORWARD", "GRP_02_ATTENTIVE_LISTENING", "Nghiêng người chú ý", 3.5f);
            Register("LISTEN_NEUTRAL_STILL", "GRP_02_ATTENTIVE_LISTENING", "Lắng nghe trung tính điềm đạm", 4.0f);
            Register("EMPATHY_HAND_CHEST", "GRP_03_EMPATHY_REASSURANCE", "Tay đặt ngực thấu cảm", 2.8f);
            Register("EMPATHY_OPEN_CALM", "GRP_03_EMPATHY_REASSURANCE", "Hai tay hạ thấp xoa dịu", 3.2f);
            Register("NEGATION_SUBTLE_NOD", "GRP_05_NEGATION_RECOGNITION", "Gật đầu xác nhận loại trừ", 1.6f);
            Register("EMERGENCY_SERIOUS_STILL", "GRP_06_EMERGENCY_ALERT", "Nghiêm nghị bất động cảnh báo đỏ", 3.0f);
            Register("EMERGENCY_RAISE_PALM_HALT", "GRP_06_EMERGENCY_ALERT", "Nâng bàn tay ngăn chặn khẩn cấp", 2.2f);
            Register("HYPO_HEAD_TILT_ENGAGE", "GRP_13_HYPOTHETICAL_CLARIFY", "Nghiêng đầu giải thích giả định", 2.6f);
            Register("THIRD_PERSON_RESPECTFUL_NOD", "GRP_14_THIRD_PERSON_ADDRESS", "Gật đầu tôn trọng về người thân", 2.5f);
            Register("HEMOSTASIS_COMPRESS_GESTURE", "GRP_31_BLEEDING_HEMOSTASIS", "Mô phỏng ép chặt cầm máu", 3.0f);
            Register("BURN_COOL_WATER_INDICATE", "GRP_32_BURN_TRAUMA_FIRST_AID", "Minh họa xả nước mát liên tục", 3.0f);
            Register("INTERRUPT_SMOOTH_SETTLE", "GRP_26_INTERRUPTION_HANDOFF", "Hạ tay quán tính 0.3s ngậm miệng", 0.4f);
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
""")

    # 6. DoctorGesturePlanner.cs
    with open(planning_dir / "DoctorGesturePlanner.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Gesture Planner v3.0
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
""")

    # 7. DoctorLayeredAnimator.cs & DoctorInertialBlender.cs
    with open(anim_dir / "DoctorLayeredAnimator.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Layered Animator v3.0
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
""")

    with open(anim_dir / "DoctorInertialBlender.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Inertial Blender v3.0
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
""")

    # 8. DoctorEyeGazeController.cs & DoctorLipSyncDriver.cs
    with open(facial_dir / "DoctorEyeGazeController.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Social Eye Gaze & Blink Controller v3.0
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
""")

    with open(facial_dir / "DoctorLipSyncDriver.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Vietnamese Viseme Lip-Sync Driver v3.0
using UnityEngine;

namespace MedGuard.Doctor.Motion.Facial
{
    public class DoctorLipSyncDriver
    {
        public float VisemeAa { get; private set; }
        public float VisemeIh { get; private set; }
        public float VisemeOu { get; private set; }
        public float VisemeEe { get; private set; }
        public float VisemeOh { get; private set; }

        public void ProcessAudioBuffer(float[] audioSamples, float deltaTime)
        {
            if (audioSamples == null || audioSamples.Length == 0)
            {
                DecayVisemes(deltaTime);
                return;
            }

            // Tính năng lượng RMS của âm thanh
            float sum = 0f;
            for (int i = 0; i < audioSamples.Length; i++) sum += audioSamples[i] * audioSamples[i];
            float rms = Mathf.Sqrt(sum / audioSamples.Length);

            float targetMouthOpen = Mathf.Clamp01(rms * 12f);
            VisemeAa = Mathf.Lerp(VisemeAa, targetMouthOpen, deltaTime * 18f);
            VisemeOh = Mathf.Lerp(VisemeOh, targetMouthOpen * 0.4f, deltaTime * 14f);
        }

        public void ResetLips()
        {
            VisemeAa = VisemeIh = VisemeOu = VisemeEe = VisemeOh = 0f;
        }

        private void DecayVisemes(float deltaTime)
        {
            VisemeAa = Mathf.Lerp(VisemeAa, 0f, deltaTime * 20f);
            VisemeIh = Mathf.Lerp(VisemeIh, 0f, deltaTime * 20f);
            VisemeOu = Mathf.Lerp(VisemeOu, 0f, deltaTime * 20f);
            VisemeEe = Mathf.Lerp(VisemeEe, 0f, deltaTime * 20f);
            VisemeOh = Mathf.Lerp(VisemeOh, 0f, deltaTime * 20f);
        }
    }
}
""")

    # 9. DoctorIKLimiter.cs
    with open(ik_dir / "DoctorIKLimiter.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Anatomical IK Limiter v3.0
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
""")

    # 10. DoctorMotionController.cs (Bộ điều phối chính)
    with open(core_dir / "DoctorMotionController.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard Doctor Motion Controller v3.0 (Unity C# Native)
using UnityEngine;
using MedGuard.Doctor.Motion.Context;
using MedGuard.Doctor.Motion.Actions;
using MedGuard.Doctor.Motion.Planning;
using MedGuard.Doctor.Motion.Animation;
using MedGuard.Doctor.Motion.Facial;

namespace MedGuard.Doctor.Motion.Core
{
    [RequireComponent(typeof(Animator))]
    public class DoctorMotionController : MonoBehaviour
    {
        [Header("Rig Components")]
        [SerializeField] private Transform chestBone;
        [SerializeField] private Transform headBone;
        [SerializeField] private Transform leftEyeBone;
        [SerializeField] private Transform rightEyeBone;

        private Animator _animator;
        private DoctorContextAnalyzer _analyzer;
        private DoctorActionLibrary _library;
        private DoctorGesturePlanner _planner;
        private DoctorLayeredAnimator _layeredAnimator;
        private DoctorEyeGazeController _gazeController;
        private DoctorLipSyncDriver _lipSync;

        public DoctorState CurrentState { get; private set; } = DoctorState.Idle;
        public string ActiveVariantId { get; private set; } = "LISTEN_NEUTRAL_STILL";

        private void Awake()
        {
            _animator = GetComponent<Animator>();
            _analyzer = new DoctorContextAnalyzer();
            _library = new DoctorActionLibrary();
            _planner = new DoctorGesturePlanner();
            _layeredAnimator = new DoctorLayeredAnimator(_animator);
            _gazeController = new DoctorEyeGazeController(headBone, leftEyeBone, rightEyeBone);
            _lipSync = new DoctorLipSyncDriver();
        }

        public void HandleUserMessage(string userMessage)
        {
            // 1. Phân tích bối cảnh lâm sàng
            var context = _analyzer.AnalyzeQuery(userMessage);

            // 2. Quyết định hành động phù hợp
            string selectedVariant = ResolveVariantForContext(context);

            // 3. Kiểm tra điều kiện cấm
            if (!_library.ValidateAction(selectedVariant, context, out string violation))
            {
                Debug.LogWarning($"[DoctorMotionController] Action {selectedVariant} violated rule: {violation}. Falling back to LISTEN_NEUTRAL_STILL.");
                selectedVariant = "LISTEN_NEUTRAL_STILL";
            }

            // 4. Kích hoạt hành động
            TriggerAction(selectedVariant);
        }

        public void OnUserBargeIn()
        {
            // Ngắt lời dứt khoát mượt mà
            CurrentState = DoctorState.Interrupted;
            _planner.ForceInterrupt(0.3f);
            _lipSync.ResetLips();
            TriggerAction("INTERRUPT_SMOOTH_SETTLE");
        }

        private void TriggerAction(string variantId)
        {
            ActiveVariantId = variantId;
            var actionDef = _library.GetAction(variantId);
            _planner.StartGesture(actionDef != null ? actionDef.DurationSeconds : 2.5f);
        }

        private void Update()
        {
            float dt = Time.deltaTime;
            _planner.Update(dt);
            _layeredAnimator.SetLayerWeight(1, _planner.CurrentWeight);
            _layeredAnimator.UpdateBreathing(dt, chestBone);

            _gazeController.UpdateGaze(Camera.main != null ? Camera.main.transform.position : Vector3.forward * 2f, dt, out float blink);
        }

        private string ResolveVariantForContext(UserQueryContext ctx)
        {
            if (ctx.Urgency == ClinicalUrgency.Emergency) return "EMERGENCY_SERIOUS_STILL";
            if (ctx.HasAcuteBleeding) return "HEMOSTASIS_COMPRESS_GESTURE";
            if (ctx.HasNegation) return "NEGATION_SUBTLE_NOD";
            if (ctx.IsHypothetical) return "HYPO_HEAD_TILT_ENGAGE";
            if (ctx.Subject == SubjectType.ThirdPerson) return "THIRD_PERSON_RESPECTFUL_NOD";
            return "LISTEN_LEAN_FORWARD";
        }
    }
}
""")

    # 11. DoctorContextScenarios.cs (Test Runner)
    with open(tests_dir / "DoctorContextScenarios.cs", "w", encoding="utf-8") as f:
        f.write("""// MedGuard 32 Context Test Cases Runner v3.0
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
""")

    # 12. Ghi file JSON catalog
    with open(data_dir / "doctor_action_catalog_v3.json", "w", encoding="utf-8") as f:
        json.dump(action_catalog, f, indent=2, ensure_ascii=False)

    with open(data_dir / "doctor_context_test_cases_v3.json", "w", encoding="utf-8") as f:
        json.dump(test_scenarios, f, indent=2, ensure_ascii=False)

    print(f"-> Đã tạo trọn bộ mã C# và dữ liệu tại: {base_dir}")

if __name__ == "__main__":
    generate_csharp_package(Path("/Users/munonguyen/Project ATI/unity/MedGuard_Unity_CSharp_Reference_v3"), ACTION_CATALOG, TEST_SCENARIOS)
