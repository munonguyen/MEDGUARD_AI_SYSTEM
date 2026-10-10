using System;
using MedGuard.Motion;
using UnityEngine;

public static class CoreChecks
{
    private static int checks;
    static void Check(bool condition) {if(!condition)throw new Exception("Core check failed at " + checks);checks++;}
    public static void Main()
    {
        string text="Bạn đo được 38.5 độ C. Nếu khó thở, cần hỗ trợ khẩn cấp.";
        Check(SpeechSegments.First(text)=="Bạn đo được 38.5 độ C.");
        Check(string.Join(" ",SpeechSegments.Split(text))==text);
        Check(string.Join("",SpeechSegments.Split(new string('a',1200)))==new string('a',1200));
        var context=new MotionContext {state=ConversationState.Listening,responseAct=SpeechAct.Explain,
            inputConfidence=.95f,responseConfidence=.95f,semanticFrameVerified=true,alertVerified=true};
        var g=new GestureDefinition {gestureId="explain",family="Explain",productionReady=true,clip=new AnimationClip(),
            allowedActs=new[]{SpeechAct.Explain},prepare=0,stroke=.3f,release=.6f,end=1};
        Check(!MotionPolicy.Allows(context,g,out _));
        context.state=ConversationState.Speaking; Check(MotionPolicy.Allows(context,g,out _));
        context.alert=AlertLevel.Urgent; context.inputConfidence=.1f; Check(!MotionPolicy.Allows(context,g,out _));
        g.family="Urgent"; Check(MotionPolicy.Allows(context,g,out _));
        context.alertVerified=false;Check(!MotionPolicy.Allows(context,g,out _));
        context.alert=AlertLevel.Routine;context.affect=PatientAffect.Worried;context.affectConfidence=.1f;
        Check(MotionPolicy.FaceFor(context)==FaceStyle.NeutralWarm);
        context.affectConfidence=.9f;Check(MotionPolicy.FaceFor(context)==FaceStyle.Concerned);
        var queue=new CueBuffer(2); Check(queue.BeginGeneration(1,"turn1"));
        var cue=new GestureCue {generationId=1,speechId="turn1",eventId="one",gestureId="explain",prepareAt=.1,strokeAt=.4,releaseAt=.7,endAt=1.1};
        Check(queue.TryEnqueue(cue,0));Check(!queue.TryEnqueue(cue,0));Check(!queue.TryTakeDue(.05,out _));
        Check(queue.TryTakeDue(.2,out _));queue.Cancel();Check(!queue.TryEnqueue(cue,.2));
        Check(queue.BeginGeneration(2,"turn2"));Check(!queue.TryEnqueue(cue,0));
        var trajectory=new QuinticTarget();var p0=new Vector3(.1f,.2f,.3f);var v0=new Vector3(.2f,-.1f,.08f);var a0=new Vector3(-.1f,.4f,.2f);
        var p1=new Vector3(.3f,-.1f,.2f);var v1=new Vector3(.1f,0,0);var a1=new Vector3(0,.1f,0);
        trajectory.Retarget(p0,v0,a0,p1,v1,a1,.6f);trajectory.Evaluate(0,out var p,out var v,out var a);
        Check(Vector3.Distance(p,p0)<1e-5);Check(Vector3.Distance(v,v0)<1e-5);Check(Vector3.Distance(a,a0)<1e-5);
        trajectory.Evaluate(.6f,out p,out v,out a);Check(Vector3.Distance(p,p1)<1e-4);Check(Vector3.Distance(v,v1)<1e-4);Check(Vector3.Distance(a,a1)<1e-3);
        Console.WriteLine(checks+" pure C# checks PASS (Unity signatures stubbed; no engine/rig/audio validation)");
    }
}
