// MedGuard Vietnamese Viseme Lip-Sync Driver v3.0
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
