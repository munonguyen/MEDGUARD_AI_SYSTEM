using System;
using UnityEngine;

namespace MedGuard.Motion
{
    public enum PlaybackState { Stopped, Scheduled, Playing, Paused, Ended, Cancelled }
    // Single fully loaded PCM-compatible clip, native prototype, pitch 1 only.
    // Streaming, Web, chunk offsets and audio-device resets need adapters.
    [RequireComponent(typeof(AudioSource))]
    public sealed class NativeSpeechClock : MonoBehaviour
    {
        private AudioSource source;
        private double startsAt;
        public double ContentSeconds { get; private set; }
        public PlaybackState State { get; private set; }
        public bool Advancing => State == PlaybackState.Playing && source != null && source.isPlaying;
        private void Awake() { source = GetComponent<AudioSource>(); }
        public void Schedule(AudioClip clip, double dspStart)
        {
            if (source == null || clip == null || clip.loadState != AudioDataLoadState.Loaded ||
                double.IsNaN(dspStart) || double.IsInfinity(dspStart) || dspStart <= AudioSettings.dspTime)
                throw new ArgumentException("Loaded audio and a future DSP start are required.");
            source.Stop(); source.clip = clip; source.pitch = 1; source.loop = false; source.playOnAwake = false;
            source.timeSamples = 0; startsAt = dspStart; ContentSeconds = 0; State = PlaybackState.Scheduled;
            source.PlayScheduled(dspStart);
        }
        private void Update()
        {
            if (source == null || source.clip == null) return;
            if (State == PlaybackState.Scheduled)
            {
                if (AudioSettings.dspTime < startsAt) return;
                if (source.isPlaying) State = PlaybackState.Playing;
                else if (AudioSettings.dspTime > startsAt + .25) State = PlaybackState.Cancelled;
                else return;
            }
            if (State == PlaybackState.Playing)
            {
                if (source.isPlaying) ContentSeconds = (double)source.timeSamples / source.clip.frequency;
                else { ContentSeconds = (double)source.clip.samples / source.clip.frequency; State = PlaybackState.Ended; }
            }
        }
        public void Pause()
        {
            if (State != PlaybackState.Playing) return;
            ContentSeconds = (double)source.timeSamples / source.clip.frequency;
            source.Pause(); State = PlaybackState.Paused;
        }
        public void Resume()
        {
            if (State != PlaybackState.Paused) return;
            source.UnPause(); State = PlaybackState.Playing;
        }
        public void Cancel()
        {
            if (source != null) source.Stop(); State = PlaybackState.Cancelled;
        }
        private void OnDisable() { Cancel(); }
    }
}
