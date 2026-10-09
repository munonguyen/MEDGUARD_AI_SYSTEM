using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace MedGuard.Motion
{
    [Serializable] internal sealed class TurnMessage { public string role, content; }
    [Serializable] internal sealed class VoicePreference { public string persona; }
    [Serializable] internal sealed class TurnRequest
    {
        public string conversation_id, locale = "vi-VN", intent_hint = "auto";
        public TurnMessage[] messages;
        public VoicePreference voice;
    }
#pragma warning disable CS0649
    [Serializable] internal sealed class TurnResponse
    {
        public string request_id, reply, spoken_reply, verification_status;
        public PreparedVoice prepared_speech;
    }
#pragma warning restore CS0649

    // Pure Unity/C# conversation adapter. A native host supplies short-lived
    // auth headers through Authorize; a WebGL host supplies its session/CSRF
    // integration. Never embed tenant API keys in the shipped Unity build.
    public sealed class DoctorConversationClient : MonoBehaviour
    {
        public UnityApprovedSpeechPlayer speech;
        public ContextualGestureDirector gestures;
        public ContextualFaceDriver expression;
        public TimedMouthDriver mouth;
        public string persona = "dr_tuan";
        public string conversationId;
        public Action<UnityWebRequest> Authorize;
        public event Action<string> TextReady, Failed;
        public event Action<ConversationState> StateChanged;
        private readonly List<TurnMessage> history = new List<TurnMessage>();
        private UnityWebRequest pending;
        private int generation;
        private MotionContext current;

        private void Awake()
        {
            if (string.IsNullOrEmpty(conversationId)) conversationId = Guid.NewGuid().ToString("N");
            if (speech != null)
            {
                speech.Started += OnStarted; speech.Completed += OnCompleted; speech.Failed += OnFailed;
            }
            ChangeState(ConversationState.Listening);
        }
        private void ChangeState(ConversationState state)
        {
            if (current == null) current = new MotionContext();
            current.state = state; gestures?.SetContext(current); expression?.SetContext(current); StateChanged?.Invoke(state);
        }
        public void Ask(string question)
        {
            if (speech == null || string.IsNullOrWhiteSpace(question) || question.Length > 4000)
            { Failed?.Invoke("invalid_turn"); return; }
            Interrupt();
            // Forget the previous turn's semantic/affect permissions.
            current = new MotionContext {turnId = generation.ToString(), state = ConversationState.Thinking};
            mouth?.BeginTurn(generation);
            ChangeState(ConversationState.Thinking);
            StartCoroutine(RequestTurn(question.Trim(), generation));
        }
        private IEnumerator RequestTurn(string question, int turn)
        {
            var messages = new List<TurnMessage>(history);
            messages.Add(new TurnMessage {role="user", content=question});
            var body = new TurnRequest {conversation_id=conversationId, messages=messages.ToArray(), voice=new VoicePreference {persona=persona}};
            var request = new UnityWebRequest(speech.apiRoot.TrimEnd('/') + "/v1/chat", "POST");
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(body)));
            request.downloadHandler = new DownloadHandlerBuffer(); request.timeout = 45;
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("Idempotency-Key", Guid.NewGuid().ToString("N"));
            bool authFailed = false;
            try { Authorize?.Invoke(request); }
            catch { authFailed = true; }
            if (authFailed) { request.Dispose(); OnFailed("chat_authentication_failed"); yield break; }
            pending = request;
            yield return request.SendWebRequest();
            if (turn != generation) yield break;
            TurnResponse response = null;
            if (request.result == UnityWebRequest.Result.Success)
            {
                try { response = JsonUtility.FromJson<TurnResponse>(request.downloadHandler.text); }
                catch { /* safe error below; do not read arbitrary error JSON */ }
            }
            pending = null; request.Dispose();
            if (response == null || string.IsNullOrWhiteSpace(response.spoken_reply))
            { OnFailed("chat_spoken_contract_unavailable"); yield break; }
            // The canonical text is generated only from the selected final answer,
            // including necessary safety/follow-up fields. No local truncation.
            TextReady?.Invoke(response.spoken_reply);
            history.Add(new TurnMessage {role="user",content=question});
            history.Add(new TurnMessage {role="assistant",content=response.spoken_reply.Substring(0, Math.Min(4000,response.spoken_reply.Length))});
            while (history.Count > 6) history.RemoveRange(0, 2);
            speech.Authorize = Authorize;
            speech.SpeakApproved(response.spoken_reply, persona, response.prepared_speech);
        }
        // Supply only a validated, current turn plan produced by a semantic
        // planner. The chat endpoint currently has NO motion-plan producer;
        // absent a plan, the avatar keeps attentive idle instead of inventing
        // gestures from symptom keywords or treating audio as semantic intent.
        public bool ApplyReviewedPlan(string turnId, MotionContext context, GestureCue[] cues)
        {
            if (context == null || turnId != generation.ToString() || context.turnId != turnId ||
                !context.semanticFrameVerified || gestures == null || cues == null) return false;
            context.state = current.state; current = context;
            if (!gestures.BeginTurn(generation, turnId, context)) return false;
            foreach (var cue in cues) gestures.Enqueue(cue, speech.ContentSeconds);
            expression?.SetContext(current); return true;
        }
        private void Update() { if (speech != null) gestures?.TickAudio(speech.ContentSeconds, speech.Advancing); }
        private void OnStarted() { ChangeState(ConversationState.Speaking); }
        private void OnCompleted() { gestures?.Cancel(); ChangeState(ConversationState.Listening); }
        private void OnFailed(string code) { gestures?.Cancel(); ChangeState(ConversationState.Recovering); Failed?.Invoke(code); }
        public void Interrupt()
        {
            generation++; StopAllCoroutines();
            if (pending != null) { pending.Abort(); pending.Dispose(); pending = null; }
            speech?.Cancel(); gestures?.Cancel(); mouth?.Cancel(); ChangeState(ConversationState.Interrupted);
        }
        private void OnDisable() { Interrupt(); }
        private void OnDestroy()
        {
            if (speech == null) return;
            speech.Started -= OnStarted; speech.Completed -= OnCompleted; speech.Failed -= OnFailed;
        }
    }
}
