using UnityEngine;

namespace MedGuard.Motion
{
    // These are dedicated Animation Rigging CONTROL targets, never skeleton bones.
    // Run before Animator/RigBuilder evaluates the rig. Do not animate these same
    // controls in a clip. Calibrate the amplitudes for the imported model scale.
    [DefaultExecutionOrder(-100)]
    public sealed class AttentionRigDriver : MonoBehaviour
    {
        public Transform referenceFrame, listenerTarget, chestControl, eyeAimControl, headAimControl;
        [Range(0, .008f)] public float breathMeters = .0025f;
        [Range(.1f, .4f)] public float breathHz = .2f;
        [Range(0, .03f)] public float gazeMeters = .012f;
        public bool reducedMotion, contactLocked;
        private Vector3 chestRest, dart, eyePoint, headPoint;
        private float phase, nextDart;
        private bool initializedGaze;

        private void OnEnable()
        {
            if (chestControl != null) chestRest = chestControl.localPosition;
            phase = Random.Range(0, Mathf.PI * 2); nextDart = 0;
            initializedGaze = false;
        }
        private void Update()
        {
            float dt = Mathf.Min(Time.unscaledDeltaTime, .1f);
            phase = (phase + dt * 2 * Mathf.PI * breathHz) % (2 * Mathf.PI);
            // Contact-locked poses use their authored breathing instead.
            if (chestControl != null)
                chestControl.localPosition = chestRest + Vector3.up *
                    ((reducedMotion || contactLocked) ? 0 : Mathf.Sin(phase) * breathMeters);
            if (listenerTarget == null || referenceFrame == null) return;
            if (Time.unscaledTime >= nextDart)
            {
                Vector2 offset = reducedMotion ? Vector2.zero : Random.insideUnitCircle * gazeMeters;
                dart = referenceFrame.right * offset.x + referenceFrame.up * offset.y;
                nextDart = Time.unscaledTime + Random.Range(.7f, 1.8f);
            }
            Vector3 target = listenerTarget.position + (reducedMotion ? Vector3.zero : dart);
            if (!initializedGaze)
            { eyePoint = headPoint = target; initializedGaze = true; }
            eyePoint = Vector3.Lerp(eyePoint, target, 1 - Mathf.Exp(-dt / .045f));
            // The head follows less and later. Anatomical angular limits belong
            // to the configured aim constraints; this is not free bone rotation.
            headPoint = Vector3.Lerp(headPoint, listenerTarget.position + dart * .25f,
                                      1 - Mathf.Exp(-dt / .2f));
            if (eyeAimControl != null) eyeAimControl.position = eyePoint;
            if (headAimControl != null) headAimControl.position = headPoint;
        }
        private void OnDisable()
        { if (chestControl != null) chestControl.localPosition = chestRest; }
    }
}
