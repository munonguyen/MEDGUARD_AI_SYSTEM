// MedGuard Doctor Motion Controller v3.0 (Unity C# Native)
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
