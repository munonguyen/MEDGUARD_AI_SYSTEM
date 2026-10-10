using UnityEngine;

namespace MedGuard.Motion
{
    [CreateAssetMenu(menuName = "MedGuard/Motion/Gesture Definition")]
    public sealed class GestureDefinition : ScriptableObject
    {
        public string gestureId, family;
        public AnimationClip clip;
        public bool productionReady; // False until rig, motion and context review.
        public SpeechAct[] allowedActs;
        public Posture posture;
        public bool requiresTarget, requiresContact, requiresFingerBones;
        public bool permittedMirror;
        [Range(0, 1)] public float maxIntensity = .35f;
        [Min(0)] public float cooldownSeconds = 6;
        [Min(0)] public float prepare, stroke, release, end;
        public bool HasValidMarkers()
        {
            return !float.IsNaN(end) && !float.IsInfinity(end) &&
                   !float.IsNaN(prepare) && !float.IsInfinity(prepare) &&
                   !float.IsNaN(stroke) && !float.IsInfinity(stroke) &&
                   !float.IsNaN(release) && !float.IsInfinity(release) &&
                   prepare >= 0 && prepare <= stroke && stroke <= release && release < end &&
                   clip != null && end <= clip.length;
        }
    }
}
