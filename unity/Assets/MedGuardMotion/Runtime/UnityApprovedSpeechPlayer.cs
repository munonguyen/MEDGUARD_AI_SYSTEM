using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace MedGuard.Motion
{
    [Serializable] public sealed class PreparedVoice { public string ticket, text, persona; }
    [Serializable] internal sealed class SpeechBody { public string text, persona; }

    // Complete short MP3 segments with one-segment lookahead. This is NOT raw
    // PCM streaming. It avoids unsupported WebGL PCM callbacks and lets Unity
    // decode MP3; an MP3 byte stream must never be fed into a PCM ring buffer.
    [RequireComponent(typeof(AudioSource))]
    public sealed class UnityApprovedSpeechPlayer : MonoBehaviour
    {
        public string apiRoot = "http://127.0.0.1:8000";
        public Action<UnityWebRequest> Authorize;
        public event Action<string> Failed;
        public event Action Started, Completed;
        public double ContentSeconds { get; private set; }
        public bool Advancing => source != null && source.isPlaying && !AudioListener.pause;
        private AudioSource source;
        private int generation;
        private double offset;
        private readonly List<UnityWebRequest> requests = new List<UnityWebRequest>();
        private readonly List<AudioClip> clips = new List<AudioClip>();
        private sealed class Download { public AudioClip clip; public string error; public bool done; }

        private void Awake()
        {
            source = GetComponent<AudioSource>(); source.playOnAwake = false;
            source.loop = false; source.spatialBlend = 0; source.pitch = 1;
        }
        public void SpeakApproved(string canonicalText, string persona, PreparedVoice prepared = null)
        {
            Cancel();
            if (source == null) source = GetComponent<AudioSource>();
            if (source.mute || source.volume <= 0 || AudioListener.volume <= 0 || AudioListener.pause)
            { Failed?.Invoke("audio_output_muted"); return; }
            if (persona != "dr_tuan" && persona != "dr_mai") { Failed?.Invoke("invalid_persona"); return; }
            string[] parts = SpeechSegments.Split(canonicalText);
            if (parts.Length == 0) return;
            bool matches = prepared != null && prepared.persona == persona && prepared.text == parts[0] &&
                           System.Text.RegularExpressions.Regex.IsMatch(prepared.ticket ?? "", @"^[A-Za-z0-9_-]{32}$");
            StartCoroutine(Play(parts, persona, matches ? prepared.ticket : null, generation));
        }
        private IEnumerator Fetch(string text, string persona, string ticket, int current, Download download)
        {
            // Ticket failure falls back once to ordinary TTS. Never skip words.
            for (int attempt = 0; attempt < (ticket == null ? 1 : 2); attempt++)
            {
                string path = attempt == 0 && ticket != null ? "/v1/chat/speech/" + ticket : "/v1/tts";
                UnityWebRequest request = UnityWebRequestMultimedia.GetAudioClip(apiRoot.TrimEnd('/') + path, AudioType.MPEG);
                if (path == "/v1/tts")
                {
                    request.method = "POST";
                    request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(new SpeechBody {text=text, persona=persona})));
                    request.SetRequestHeader("Content-Type", "application/json");
                }
                request.timeout = 30;
                ((DownloadHandlerAudioClip)request.downloadHandler).streamAudio = false;
                bool authFailed = false;
                try { Authorize?.Invoke(request); }
                catch { authFailed = true; }
                if (authFailed) { request.Dispose(); download.error = "speech_authentication_failed"; download.done = true; yield break; }
                requests.Add(request);
                yield return request.SendWebRequest();
                if (current != generation) { requests.Remove(request); request.Dispose(); yield break; }
                bool ok = request.result == UnityWebRequest.Result.Success &&
                          (request.GetResponseHeader("Content-Type") ?? "").StartsWith("audio/", StringComparison.OrdinalIgnoreCase);
                if (ok)
                {
                    try { download.clip = DownloadHandlerAudioClip.GetContent(request); }
                    catch { download.error = "audio_decode_failed"; }
                    if (download.clip == null || download.clip.samples == 0 || download.clip.loadState != AudioDataLoadState.Loaded)
                    { if (download.clip != null) Destroy(download.clip); download.clip = null; download.error = "audio_decode_failed"; }
                    else { clips.Add(download.clip); download.error = null; }
                }
                else download.error = "speech_download_failed";
                bool retryTicket = ticket != null && attempt == 0 && request.responseCode == 404;
                requests.Remove(request); request.Dispose();
                if (download.error == null || !retryTicket) break;
            }
            download.done = true;
        }
        private IEnumerator Play(string[] parts, string persona, string ticket, int current)
        {
            var pending = new Download();
            StartCoroutine(Fetch(parts[0], persona, ticket, current, pending));
            for (int index = 0; index < parts.Length; index++)
            {
                var next = index + 1 < parts.Length ? new Download() : null;
                if (next != null) StartCoroutine(Fetch(parts[index + 1], persona, null, current, next));
                while (!pending.done && current == generation) yield return null;
                if (current != generation) yield break;
                if (pending.error != null) { Cancel(); Failed?.Invoke(pending.error); yield break; }
                source.clip = pending.clip; source.Play();
                if (index == 0) Started?.Invoke();
                float startedAt = Time.realtimeSinceStartup;
                while (current == generation && (source.isPlaying || AudioListener.pause || Time.realtimeSinceStartup - startedAt < .15f))
                {
                    if (source.isPlaying) ContentSeconds = offset + (double)source.timeSamples / source.clip.frequency;
                    yield return null;
                }
                if (current != generation) yield break;
                // If playback was blocked, do not silently declare success.
                if (ContentSeconds < offset + pending.clip.length - .25 && pending.clip.length > .3f)
                { Cancel(); Failed?.Invoke("audio_playback_interrupted"); yield break; }
                offset += (double)pending.clip.samples / pending.clip.frequency; ContentSeconds = offset;
                source.clip = null; clips.Remove(pending.clip); Destroy(pending.clip); pending = next;
            }
            Completed?.Invoke();
        }
        public void Cancel()
        {
            generation++; StopAllCoroutines();
            foreach (var request in requests) { request.Abort(); request.Dispose(); } requests.Clear();
            if (source != null) { source.Stop(); source.clip = null; }
            foreach (var clip in clips) if (clip != null) Destroy(clip); clips.Clear();
            offset = 0; ContentSeconds = 0;
        }
        private void OnDisable() { Cancel(); }
    }
}
