# MedGuard — Unity/C# conversation and motion adapter

Status: importable C# source and authoring catalogue, **not a finished Unity project or tested scene**. The repository's web avatar is still Three.js. These scripts are independent; no Three.js process writes their bones. A Unity Editor, imported character, reviewed clips, Animator Controller and rig setup are required before switching the web avatar to a Unity build.

## Import and ownership

1. Copy `Assets/MedGuardMotion` into the Unity project's `Assets` folder. Keep `Validation` outside `Assets`: it contains signature stubs exclusively for a standalone compiler check.
2. Import the real character with the appropriate Humanoid/avatar configuration. Check fingers, eye bones, mesh scale and blendshape names. Install a Unity-compatible Animation Rigging package if using aim/IK constraints.
3. Animator owns the base pose and gesture clips. Add an upper-body gesture layer with an appropriate Avatar Mask. Do not add a second system that rotates the same bones in `LateUpdate`.
4. Animation Rigging constraints apply the final anatomical/contact correction. `AttentionRigDriver` writes dedicated chest/eye/head **control targets before evaluation**, not skeleton bones. Clips must not animate these procedural controls.
5. `ContextualFaceDriver` owns brows/cheeks/blinks. `TimedMouthDriver` owns mouth/visemes. These sets must be disjoint and clips must not animate them. Missing shapes are skipped, never mapped accidentally to index zero.
6. Attach `UnityApprovedSpeechPlayer` and an `AudioSource` to one object. Connect `DoctorConversationClient.speech`, face, mouth and gesture references. Ensure there is an enabled AudioListener and an audible output device. Speech is 2D, pitch 1; it does not depend on avatar-camera distance.
7. Supply ephemeral authentication/consent/session headers via the `Authorize` delegate; do not ship tenant secrets in a Unity build. A native application should obtain short-lived app credentials through its host. A WebGL build should use the existing account session plus its CSRF integration on the same origin. This host integration is required and is not included as a production identity flow here.

## Runtime components

| Component | Responsibility |
|---|---|
| `DoctorConversationClient` | Async chat coroutine, six history messages, interruption, canonical text and speech handoff |
| `UnityApprovedSpeechPlayer` | Approved MP3 segments, prepared-first-segment ticket, one-segment lookahead, abort and decode checks |
| `AttentionRigDriver` | Small chest motion, restrained eye darts, slower head follow; no automatic agreement nod |
| `ContextualFaceDriver` | Context-vetted facial style and non-periodic blink schedule |
| `ContextualGestureDirector` | Reviewed clip bindings, hard vetoes, cue timing, cooldown and suppression of immediate repetition |
| `TimedMouthDriver` | Timestamped viseme blending; optional native jaw envelope fallback |
| `MotionPolicy` | Conversation state, verified urgency, uncertainty, pose, contact and target vetoes |
| `CueBuffer` | Generation-bound bounded queue, duplicate rejection and cancellation |
| `QuinticTarget` | Position/velocity/acceleration-preserving target interpolation for IK authoring |

## Semantic plan and gesture assets

`Data/GestureCatalog.json` contains **32 families / 64 authoring recipes**. They are marked `DesignOnly`; there are no finished AnimationClips in this package. Do not set `productionReady` until an actual clip passes rig, context and motion review. Bind that clip to an explicit Animator state through `GestureBinding` and configure its prepare/stroke/release/end markers in seconds.

`ApplyReviewedPlan` accepts a validated current-turn `MotionContext` and timestamped `GestureCue` entries. `turnId` is the current client's generation string; each cue's `generationId` and `speechId` must match. The current `/v1/chat` endpoint does **not** produce this plan. Connect an independently validated planner before expecting contextual hand gestures. Without it, the adapter intentionally retains attentive idle. It never guesses urgency from the word “sốt”, forces reassuring motion from a worrying question, or raises a hand just because audio plays.

Cue times are offsets on the actual concatenated audio content clock. Waiting for a segment does not advance that clock. Do not fabricate timestamps from word count. If precise provider/forced-alignment timing is unavailable, use sparse coarse phrase gestures with reviewed timing, not a claimed word-perfect synchronizer. A cue received too late is skipped; interruptions clear old generations. On a pause/loading gap, an active gesture fades to rest rather than continuing as if speech were advancing. Full playable-layer time scrubbing and full-body inertialization are future scene-level work, not implemented by `SmoothDamp` here.

## Audio contract and platform limits

Chat POST includes `voice: {"persona":"dr_tuan"}` or `dr_mai`. The server returns `spoken_reply`, plus an optional `prepared_speech` ticket scoped to the authenticated tenant. The player uses that ticket only when persona and first text segment match exactly. Expired/missing tickets (404) fall back once to ordinary POST `/v1/tts`; provider errors stop with a safe code. They do not silently skip a sentence or retry for another full timeout.

Each audio segment is decoded as a complete MP3 using Unity's download handler. This is **segment prefetch, not PCM streaming**. Native platforms can later add a bounded PCM streaming adapter with sample rate/channel metadata, underrun handling and a consumed-sample clock. Unity Web does not support the same scriptable PCM callback workflow; do not present native PCM streaming as a C#-only WebGL solution. Browser autoplay still requires a user action and must be tested on Safari/iOS.

`TimedMouthDriver` accepts only finite, bounded current-generation cues for authored mouth shapes. The existing Edge TTS backend currently supplies no provider visemes, so precise alignment is not wired. The optional native RMS fallback produces only restrained jaw opening. It cannot distinguish Vietnamese phonemes. The WebGL build needs actual timed cues for this component; native `GetOutputData` is disabled there. Frequency peaks alone are not a phoneme recognizer.

## Naturalness rules

- Listening: attentive gaze, blinking, small breathing, hands at rest. A nod may acknowledge receipt only after an explicit acknowledgement decision; it must not imply medical agreement.
- Thinking: keep attention and a relaxed pose. Do not touch the chin or scratch the head for every delayed response.
- Explanation: one restrained open-palm arc can emphasize a chosen clause. Allow long spans without gestures.
- Reassurance: only for a justified reassuring act; never downgrade a verified urgent episode. No broad smile during distress.
- Urgent instruction: calm, clear, low-amplitude emphasis with immediate instruction. No theatrical alarm or greeting wave.
- Demonstration: point only at a real visible target. Body-site demonstration needs anatomy/side resolution and an authored pose; no random touching of the doctor's own head/chest.
- Comparison/counting: bilateral motion can be natural. A fixed “never move both hands at once” rule is incorrect. Asymmetry belongs in the authored phase timing and variant, not a universal artificial delay.
- Breathing: 0.2 Hz means 12 cycles/min; the sine phase uses `2πf`. Long text alone is not evidence of physiological stress.
- Reach/contact: preserve elbow bend and wrist posture; authored collision/contact constraints win over noise. No hand penetration, lateral 90° greeting or double ownership of an animated bone.

## Checks and release gate

`MEDGUARD_DOTNET_ROOT=<dotnet-sdk> python3 unity/Validation/check.py` compiles source against **signature stubs** and runs 24 pure C# policy/queue/interpolation/text checks. This does not execute Unity, its Animator, rig, mesh or audio system. The NUnit tests under `Assets/MedGuardMotion/Tests` require Unity Test Runner; they have not been run here.

Before activation, run a real Unity scene with both doctor models and reviewed clips. Record listening, ordinary explanation, uncertainty, negation, hypothetical symptoms, verified urgency, contact, target loss, interruption, voice failure and mute/unmute. Record the actual audio output as well as frames. Verify lips during speech/silence, neutral face recovery, no stuck hand, no old-turn audio/cues, no forearm/coat collision and no repeated gesture every sentence. No naturalness pass or Unity deployment is claimed by standalone compilation.

Primary references:

- https://docs.unity3d.com/6000.0/Documentation/Manual/webgl-audio.html
- https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Networking.UnityWebRequestMultimedia.GetAudioClip.html
- https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.4/manual/index.html
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-lower-speech-synthesis-latency
