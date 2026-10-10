using System;

namespace MedGuard.Motion
{
    public enum ConversationState { Listening, Thinking, Speaking, Yielding, Interrupted, Recovering }
    public enum SpeechAct { None, AskClarification, AskQuestion, Empathize, Reassure, Explain, Emphasize, Enumerate, GuideSteps, Compare, Contrast, StateUncertainty, CorrectMisunderstanding, Caution, UrgentInstruction, ProhibitAction, FollowUp, Refer, ShowTarget, Thank, Close, Greet }
    public enum AlertLevel { Routine, Caution, Urgent }
    public enum PatientAffect { Neutral, Worried, Distressed, Relieved }
    public enum Posture { Any, Standing, Seated }
    public enum Polarity { Unknown, Present, Absent }
    public enum Temporality { Unknown, Current, Past, Future }
    public enum Modality { Unknown, Asserted, Hypothetical, Quoted, KnowledgeQuestion }
    public enum FaceStyle { NeutralWarm, Attentive, Concerned, CalmSerious }
    [Serializable]
    public sealed class SemanticFact
    {
        public string concept;
        public Polarity polarity;
        public Temporality temporality;
        public Modality modality;
        public string experiencer; // Must be resolved by the semantic producer.
    }
    // Populate only after transport authentication, schema checks and episode
    // revision checks. This is NOT a symptom classifier or clinical triage engine.
    [Serializable]
    public sealed class MotionContext
    {
        public string turnId, episodeId;
        public ConversationState state;
        public SpeechAct responseAct;
        public AlertLevel alert;
        public bool alertVerified;
        public PatientAffect affect;
        public float inputConfidence, responseConfidence, affectConfidence;
        public bool semanticFrameVerified;
        public bool reducedMotion;
        public Posture posture;
        public bool hasTarget, targetVisible, hasRequiredBones;
        public bool contactLocked, contactReleasePlanned;
        public SemanticFact[] facts;
    }
}
