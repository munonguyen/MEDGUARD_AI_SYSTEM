namespace MedGuard.Motion
{
    // Deterministic hard-veto layer. A planner may score ONLY allowed candidates.
    // Cooldowns, seed choice, phase timing and pose-cost are planner responsibilities.
    public static class MotionPolicy
    {
        private static bool Quiet(string f) => f == "Rest" || f == "Attentive" || f == "Wait";
        private static bool FiniteConfidence(float f) => !float.IsNaN(f) && !float.IsInfinity(f) && f >= 0 && f <= 1;
        public static FaceStyle FaceFor(MotionContext c)
        {
            if (c == null) return FaceStyle.Attentive;
            if (c.alertVerified && c.alert == AlertLevel.Urgent) return FaceStyle.CalmSerious;
            if (c.semanticFrameVerified && FiniteConfidence(c.affectConfidence) && c.affectConfidence >= .75f &&
                (c.affect == PatientAffect.Worried || c.affect == PatientAffect.Distressed)) return FaceStyle.Concerned;
            return c.state == ConversationState.Listening ? FaceStyle.Attentive : FaceStyle.NeutralWarm;
        }
        public static bool Allows(MotionContext c, GestureDefinition g, out string reason)
        {
            reason = "allowed";
            if (c == null || g == null) { reason = "missing-context-or-asset"; return false; }
            if (!g.productionReady || g.clip == null || !g.HasValidMarkers()) { reason = "asset-not-reviewed"; return false; }
            if (g.posture != Posture.Any && g.posture != c.posture) { reason = "posture-mismatch"; return false; }
            if (g.requiresFingerBones && !c.hasRequiredBones) { reason = "missing-finger-capability"; return false; }
            if (g.requiresTarget && (!c.hasTarget || !c.targetVisible)) { reason = "missing-visible-target"; return false; }
            if (g.requiresContact && !c.contactLocked) { reason = "missing-contact"; return false; }
            if (c.contactLocked && !c.contactReleasePlanned && !g.requiresContact && !Quiet(g.family)) { reason = "release-contact-first"; return false; }
            if (c.state == ConversationState.Interrupted || c.state == ConversationState.Recovering)
            {
                bool recovery = g.family == "Interrupt" || g.family == "Recover" || Quiet(g.family);
                reason = recovery ? "allowed-recovery" : "cancelled-speech"; return recovery;
            }
            if (c.reducedMotion && !Quiet(g.family)) { reason = "reduced-motion"; return false; }
            if (c.state != ConversationState.Speaking)
            {
                bool allowed = Quiet(g.family) || (c.state == ConversationState.Thinking && g.family == "Thinking") ||
                               (c.state == ConversationState.Yielding && g.family == "TurnYield");
                reason = allowed ? "allowed-turn-state" : "not-doctor-speaking"; return allowed;
            }
            // A verified urgent episode survives uncertain input or semantics.
            if (c.alertVerified && c.alert == AlertLevel.Urgent)
            {
                bool urgent = g.family == "Urgent" || Quiet(g.family);
                reason = urgent ? "verified-urgent" : "urgent-veto"; return urgent;
            }
            if (!c.semanticFrameVerified || !FiniteConfidence(c.inputConfidence) || !FiniteConfidence(c.responseConfidence) ||
                c.inputConfidence < .75f || c.responseConfidence < .75f)
            {
                bool fallback = Quiet(g.family) || (c.semanticFrameVerified && c.responseAct == SpeechAct.AskClarification && g.family == "Clarify");
                reason = fallback ? "uncertain-fallback" : "uncertain-context"; return fallback;
            }
            if (g.family == "Urgent") { reason = "urgent-requires-verified-alert"; return false; }
            if (c.alertVerified && c.alert == AlertLevel.Caution &&
                (g.family == "Greeting" || g.family == "Thanks" || g.family == "Farewell")) { reason = "caution-veto-social-display"; return false; }
            if ((c.affect == PatientAffect.Worried || c.affect == PatientAffect.Distressed) &&
                (g.family == "Greeting" || g.family == "Thanks" || g.family == "Farewell")) { reason = "affect-veto-social-display"; return false; }
            if (Quiet(g.family)) return true;
            if (g.allowedActs != null)
                for (int i = 0; i < g.allowedActs.Length; i++)
                    if (g.allowedActs[i] == c.responseAct) return true;
            reason = "speech-act-mismatch"; return false;
        }
    }
}
