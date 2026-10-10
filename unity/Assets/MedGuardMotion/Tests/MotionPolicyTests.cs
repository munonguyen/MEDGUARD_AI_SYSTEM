using NUnit.Framework;
using UnityEngine;
using MedGuard.Motion;

public sealed class MotionPolicyTests
{
    private GestureDefinition Definition(string family, SpeechAct act)
    {
        var g = ScriptableObject.CreateInstance<GestureDefinition>();
        g.family = family; g.gestureId = family; g.productionReady = true;
        g.clip = new AnimationClip();
        g.clip.SetCurve("", typeof(Transform), "localPosition.x", AnimationCurve.Linear(0,0,1,0));
        g.allowedActs = new[] { act }; g.prepare = 0; g.stroke = .3f; g.release = .5f; g.end = 1;
        return g;
    }
    private static MotionContext Context(SpeechAct act) => new MotionContext {
        state = ConversationState.Speaking, responseAct = act, alertVerified = true,
        inputConfidence = .95f, responseConfidence = .95f, semanticFrameVerified = true,
        posture = Posture.Standing
    };
    private static void Dispose(GestureDefinition g) { Object.DestroyImmediate(g.clip); Object.DestroyImmediate(g); }
    [Test] public void UrgentVetoSurvivesLowConfidence()
    {
        var c = Context(SpeechAct.Greet); c.alert = AlertLevel.Urgent; c.inputConfidence = .1f;
        var greet = Definition("Greeting", SpeechAct.Greet); var urgent = Definition("Urgent", SpeechAct.UrgentInstruction);
        try { Assert.IsFalse(MotionPolicy.Allows(c,greet,out _)); Assert.IsTrue(MotionPolicy.Allows(c,urgent,out _));
            Assert.AreEqual(FaceStyle.CalmSerious,MotionPolicy.FaceFor(c)); }
        finally { Dispose(greet); Dispose(urgent); }
    }
    [Test] public void ListeningCannotPlaySpeechGesture()
    {
        var c = Context(SpeechAct.Explain); c.state = ConversationState.Listening;
        var g = Definition("Explain", SpeechAct.Explain);
        try { Assert.IsFalse(MotionPolicy.Allows(c,g,out _)); } finally { Dispose(g); }
    }
    [Test] public void LowConfidenceAffectDoesNotForceConcernedFace()
    {
        var c = Context(SpeechAct.Explain); c.affect = PatientAffect.Worried; c.affectConfidence = .2f;
        Assert.AreEqual(FaceStyle.NeutralWarm,MotionPolicy.FaceFor(c));
        c.affectConfidence = .9f;
        Assert.AreEqual(FaceStyle.Concerned,MotionPolicy.FaceFor(c));
    }
    [Test] public void MissingTargetAndContactAreVetoes()
    {
        var c = Context(SpeechAct.ShowTarget); var g = Definition("ShowTarget",SpeechAct.ShowTarget); g.requiresTarget = true;
        try { Assert.IsFalse(MotionPolicy.Allows(c,g,out _)); c.hasTarget = c.targetVisible = true;
            Assert.IsTrue(MotionPolicy.Allows(c,g,out _)); c.contactLocked = true;
            Assert.IsFalse(MotionPolicy.Allows(c,g,out _)); } finally { Dispose(g); }
    }
    [Test] public void UnverifiedUrgentDoesNotCreateUrgentGesture()
    {
        var c = Context(SpeechAct.UrgentInstruction); c.alertVerified = false; c.alert = AlertLevel.Urgent;
        var g = Definition("Urgent",SpeechAct.UrgentInstruction);
        try { Assert.IsFalse(MotionPolicy.Allows(c,g,out _)); } finally { Dispose(g); }
    }
    [Test] public void CueCancelRejectsLateCallbackAndDeduplicates()
    {
        var b = new CueBuffer(2); Assert.IsTrue(b.BeginGeneration(1,"s1"));
        var cue = new GestureCue { generationId=1,speechId="s1",eventId="e1",gestureId="explain_one_arc",prepareAt=.1,strokeAt=.4,releaseAt=.6,endAt=1 };
        Assert.IsTrue(b.TryEnqueue(cue,0)); Assert.IsFalse(b.TryEnqueue(cue,0));
        Assert.IsTrue(b.TryTakeDue(.2,out _)); Assert.IsFalse(b.TryEnqueue(cue,.2));
        b.Cancel(); Assert.IsFalse(b.TryEnqueue(cue,.2)); Assert.IsTrue(b.BeginGeneration(2,"s2"));
        Assert.IsFalse(b.TryEnqueue(cue,.2)); Assert.AreEqual(0,b.Count);
    }
    [Test] public void QuinticRetargetPreservesBoundaryState()
    {
        var t = new QuinticTarget(); var p0=new Vector3(.1f,.2f,.3f);var v0=new Vector3(.2f,-.1f,.08f);var a0=new Vector3(-.1f,.4f,.2f);
        var p1=new Vector3(.3f,-.1f,.2f);var v1=new Vector3(.1f,0,0);var a1=new Vector3(0,.1f,0);
        t.Retarget(p0,v0,a0,p1,v1,a1,.6f);
        t.Evaluate(0,out var p,out var v,out var a);
        Assert.That(Vector3.Distance(p,p0),Is.LessThan(1e-5));Assert.That(Vector3.Distance(v,v0),Is.LessThan(1e-5));Assert.That(Vector3.Distance(a,a0),Is.LessThan(1e-5));
        t.Evaluate(.6f,out p,out v,out a);
        Assert.That(Vector3.Distance(p,p1),Is.LessThan(1e-4));Assert.That(Vector3.Distance(v,v1),Is.LessThan(1e-4));Assert.That(Vector3.Distance(a,a1),Is.LessThan(1e-3));
    }
}
