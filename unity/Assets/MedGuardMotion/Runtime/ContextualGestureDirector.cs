using System;
using System.Collections.Generic;
using UnityEngine;

namespace MedGuard.Motion
{
    [Serializable]
    public sealed class GestureBinding
    {
        public GestureDefinition definition;
        public string animatorState; // Explicit full path, e.g. Gestures.ExplainOpenPalm.
    }

    // Animator owns gesture bones; rig constraints own their final corrections.
    // This controller writes layer weights/state only, never bone transforms.
    public sealed class ContextualGestureDirector : MonoBehaviour
    {
        public Animator animator;
        public int gestureLayer = 1;
        public GestureBinding[] bindings = new GestureBinding[0];
        [Range(.1f, .5f)] public float blendSeconds = .2f;
        private readonly Dictionary<string, float> lastPlayed = new Dictionary<string, float>();
        private readonly CueBuffer cues = new CueBuffer();
        private MotionContext context;
        private string previousId;
        private float weight, weightVelocity;
        private double endsAt;
        private GestureDefinition currentGesture;
        private bool active;

        public bool BeginTurn(int generation, string speechId, MotionContext verifiedContext)
        {
            if (!cues.BeginGeneration(generation, speechId)) return false;
            context = verifiedContext; active = false; return true;
        }
        public void SetContext(MotionContext value) { context = value; }
        public bool Enqueue(GestureCue cue, double contentNow) => cues.TryEnqueue(cue, contentNow);
        public void Cancel()
        { cues.Cancel(); active = false; context = null; }
        // Call with the actual audio content clock. Paused/loading audio cannot
        // advance cues. No RMS threshold or OnAudioPlaying creates a hand action.
        public void TickAudio(double contentSeconds, bool advancing)
        {
            if (!advancing || context == null || context.state != ConversationState.Speaking)
            { active = false; return; }
            if (active && contentSeconds >= endsAt) active = false;
            while (cues.TryTakeDue(contentSeconds, out var cue))
            {
                if (active || contentSeconds - cue.prepareAt > .1) continue;
                foreach (var binding in bindings)
                {
                    var g = binding.definition;
                    if (g == null || g.gestureId != cue.gestureId || g.gestureId == previousId ||
                        !MotionPolicy.Allows(context, g, out _) || animator == null ||
                        gestureLayer < 1 || gestureLayer >= animator.layerCount ||
                        string.IsNullOrEmpty(binding.animatorState)) continue;
                    // Only play a cue whose authored markers match its timing.
                    if (Math.Abs((cue.strokeAt - cue.prepareAt) - (g.stroke - g.prepare)) > .03 ||
                        Math.Abs((cue.releaseAt - cue.prepareAt) - (g.release - g.prepare)) > .03 ||
                        Math.Abs((cue.endAt - cue.prepareAt) - (g.end - g.prepare)) > .03) continue;
                    if (lastPlayed.TryGetValue(g.gestureId, out var last) && Time.unscaledTime - last < g.cooldownSeconds) continue;
                    int state = Animator.StringToHash(binding.animatorState);
                    if (!animator.HasState(gestureLayer, state)) continue;
                    animator.CrossFadeInFixedTime(state, blendSeconds, gestureLayer, g.prepare);
                    lastPlayed[g.gestureId] = Time.unscaledTime; previousId = g.gestureId;
                    endsAt = cue.endAt; currentGesture = g; active = true; break;
                }
            }
        }
        private void Update()
        {
            if (active && !MotionPolicy.Allows(context, currentGesture, out _)) active = false;
            weight = Mathf.SmoothDamp(weight, active ? 1 : 0, ref weightVelocity, blendSeconds,
                                     Mathf.Infinity, Time.unscaledDeltaTime);
            if (animator != null && gestureLayer > 0 && gestureLayer < animator.layerCount)
                animator.SetLayerWeight(gestureLayer, weight);
        }
        private void OnDisable() { Cancel(); }
    }
}
