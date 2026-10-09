using System;
using UnityEngine;

namespace MedGuard.Motion
{
    [Serializable] public struct MouthCue
    {
        public int generation, shape;
        public double start, end;
        public float weight;
    }
    // Authored viseme shapes indexed by timestamped provider/alignment cues.
    // Separate blendshape ownership from brows/cheeks/blinks. Spectrum and RMS
    // are NOT exact phonemes. Native RMS is an optional jaw-opening fallback.
    public sealed class TimedMouthDriver : MonoBehaviour
    {
        public UnityApprovedSpeechPlayer clock;
        public AudioSource source;
        public SkinnedMeshRenderer face;
        public string[] visemeShapes = new string[0];
        public string fallbackJawShape = "";
        public bool allowNativeRmsFallback;
        private readonly MouthCue[] cues = new MouthCue[256];
        private readonly float[] samples = new float[256];
        private int count, generation, jaw = -1;
        private int[] indices;
        private float[] weights;
        private float jawWeight;

        private void Awake()
        {
            indices = new int[visemeShapes.Length]; weights = new float[indices.Length];
            for (int i = 0; i < indices.Length; i++)
            {
                indices[i] = face == null || face.sharedMesh == null ? -1 : face.sharedMesh.GetBlendShapeIndex(visemeShapes[i]);
                for (int j = 0; j < i; j++) if (indices[i] == indices[j]) indices[i] = -1;
            }
            if (face != null && face.sharedMesh != null && !string.IsNullOrEmpty(fallbackJawShape))
                jaw = face.sharedMesh.GetBlendShapeIndex(fallbackJawShape);
            for (int i = 0; i < indices.Length; i++) if (indices[i] == jaw) jaw = -1;
        }
        public void BeginTurn(int nextGeneration)
        { generation = nextGeneration; count = 0; }
        public bool Enqueue(MouthCue cue)
        {
            double now = clock == null ? 0 : clock.ContentSeconds;
            if (cue.generation != generation || cue.shape < 0 || cue.shape >= visemeShapes.Length ||
                double.IsNaN(cue.start) || double.IsInfinity(cue.start) || double.IsNaN(cue.end) || double.IsInfinity(cue.end) ||
                float.IsNaN(cue.weight) || float.IsInfinity(cue.weight) || cue.weight < 0 || cue.weight > 1 ||
                cue.start < 0 || cue.end <= cue.start || cue.end <= now || cue.start - now > 10 || count == cues.Length) return false;
            int index = count;
            while (index > 0 && cues[index - 1].start > cue.start) { cues[index] = cues[index - 1]; index--; }
            cues[index] = cue; count++; return true;
        }
        private void LateUpdate()
        {
            if (face == null || clock == null || indices == null) return;
            double now = clock.ContentSeconds;
            while (count > 0 && cues[0].end <= now)
            { Array.Copy(cues, 1, cues, 0, --count); cues[count] = default; }
            bool aligned = count > 0;
            float total = 0;
            for (int i = 0; i < indices.Length; i++)
            {
                float target = 0;
                if (clock.Advancing)
                    for (int j = 0; j < count && cues[j].start <= now; j++)
                        if (cues[j].shape == i && cues[j].end > now) target = Mathf.Max(target, cues[j].weight);
                weights[i] = Mathf.Lerp(weights[i], target, 1 - Mathf.Exp(-Time.unscaledDeltaTime / .035f));
                total += weights[i];
            }
            for (int i = 0; i < indices.Length; i++)
                if (indices[i] >= 0) face.SetBlendShapeWeight(indices[i], 100 * weights[i] / Mathf.Max(1, total));
            float jawTarget = 0;
#if !UNITY_WEBGL || UNITY_EDITOR
            if (!aligned && allowNativeRmsFallback && clock.Advancing && source != null && jaw >= 0)
            {
                source.GetOutputData(samples, 0);
                float sum = 0; for (int i = 0; i < samples.Length; i++) sum += samples[i] * samples[i];
                float rms = Mathf.Sqrt(sum / samples.Length);
                jawTarget = Mathf.Clamp01((rms - .008f) / .08f) * 35;
            }
#endif
            jawWeight = Mathf.Lerp(jawWeight, jawTarget, 1 - Mathf.Exp(-Time.unscaledDeltaTime / .06f));
            if (jaw >= 0) face.SetBlendShapeWeight(jaw, jawWeight);
        }
        public void Cancel() { generation++; count = 0; }
        private void OnDisable()
        {
            Cancel();
            if (face == null) return;
            if (indices != null) for (int i = 0; i < indices.Length; i++)
                if (indices[i] >= 0) face.SetBlendShapeWeight(indices[i], 0);
            if (jaw >= 0) face.SetBlendShapeWeight(jaw, 0);
            if (weights != null) Array.Clear(weights, 0, weights.Length); jawWeight = 0;
        }
    }
}
