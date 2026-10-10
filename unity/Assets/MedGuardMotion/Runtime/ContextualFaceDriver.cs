using System;
using UnityEngine;
using Random = UnityEngine.Random;

namespace MedGuard.Motion
{
    [Serializable]
    public sealed class FaceChannel
    {
        public string blendshape;
        [Range(0, 35)] public float neutralWarm, attentive, concerned, calmSerious;
    }

    // Owns brows/cheeks/blinks only. Animator clips and the viseme driver must
    // not write these channels. No symptom keyword forces an emotional face.
    public sealed class ContextualFaceDriver : MonoBehaviour
    {
        public SkinnedMeshRenderer face;
        public FaceChannel[] expressionChannels = new FaceChannel[0];
        public string leftBlink = "", rightBlink = "";
        private int[] indices;
        private float[] values;
        private int left = -1, right = -1;
        private float nextBlink, blinkStarted = -1;
        private FaceStyle style = FaceStyle.Attentive;

        public void SetContext(MotionContext context) { style = MotionPolicy.FaceFor(context); }
        private int Index(string name)
        { return face == null || face.sharedMesh == null || string.IsNullOrEmpty(name) ? -1 : face.sharedMesh.GetBlendShapeIndex(name); }
        private void OnEnable()
        {
            left = Index(leftBlink); right = Index(rightBlink);
            indices = new int[expressionChannels.Length]; values = new float[indices.Length];
            for (int i = 0; i < indices.Length; i++)
            {
                int index = Index(expressionChannels[i].blendshape);
                bool duplicate = index == left || index == right;
                for (int j = 0; j < i; j++) duplicate |= indices[j] == index;
                indices[i] = duplicate ? -1 : index;
                if (indices[i] >= 0) values[i] = face.GetBlendShapeWeight(indices[i]);
            }
            blinkStarted = -1; nextBlink = Time.unscaledTime + Random.Range(2.5f, 5.5f);
        }
        private void LateUpdate()
        {
            if (face == null || face.sharedMesh == null || indices == null) return;
            float smoothing = 1 - Mathf.Exp(-Time.unscaledDeltaTime / .22f);
            for (int i = 0; i < indices.Length; i++)
            {
                if (indices[i] < 0) continue;
                FaceChannel c = expressionChannels[i];
                float target = style == FaceStyle.Attentive ? c.attentive : style == FaceStyle.Concerned ? c.concerned :
                               style == FaceStyle.CalmSerious ? c.calmSerious : c.neutralWarm;
                values[i] = Mathf.Lerp(values[i], Mathf.Clamp(target, 0, 35), smoothing);
                face.SetBlendShapeWeight(indices[i], values[i]);
            }
            if (blinkStarted < 0 && Time.unscaledTime >= nextBlink) blinkStarted = Time.unscaledTime;
            float weight = 0;
            if (blinkStarted >= 0)
            {
                float elapsed = Time.unscaledTime - blinkStarted;
                // Fast closure, slower opening; no per-frame random probability.
                float u = elapsed < .065f ? elapsed / .065f : 1 - (elapsed - .065f) / .12f;
                u = Mathf.Clamp01(u); weight = 100 * u * u * (3 - 2 * u);
                if (elapsed >= .185f)
                { blinkStarted = -1; nextBlink = Time.unscaledTime + Random.Range(2.5f, 5.5f); }
            }
            if (left >= 0) face.SetBlendShapeWeight(left, weight);
            if (right >= 0 && right != left) face.SetBlendShapeWeight(right, weight);
        }
        private void OnDisable()
        {
            if (face == null) return;
            if (left >= 0) face.SetBlendShapeWeight(left, 0);
            if (right >= 0) face.SetBlendShapeWeight(right, 0);
        }
    }
}
