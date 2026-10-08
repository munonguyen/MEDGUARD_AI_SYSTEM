# VRM motion and audio-viseme integration

The existing DoctorMotion controller now combines eight original VRMA torso/clavicle clips with authored hand paths, existing two-bone IK, fingers, breathing and gaze. Long spoken phrases perform one gesture and settle instead of looping a gesture every 5.3 seconds. The existing 24 semantic alternatives remain available.

## Ownership and playback

`doctorAnimationLayer.js` uses `@pixiv/three-vrm-animation` 3.5.5 (MIT) and Three.js AnimationMixer. It samples clips in media/gesture time, restores the procedural pose, then blends a bounded additive quaternion delta. Only spine, chest, upperChest and clavicles have tracks. The hands/arms and planted feet remain owned by DoctorMotion/IK. Eyes, face expressions and lip-sync have separate owners. VRM0 conversion is handled by the official clip adapter; VRM1 is tested too.

`gestureChoreography.js` defines reference-adult hand paths with preparation, stroke, hold and recovery. Range scales by the actual arm-chain length. The greeting stays in front of the upper chest with the elbow down. `frontend/scripts/build-doctor-vrma.mjs` reproducibly generates `frontend/public/animations/doctor-gestures.vrma`. These are original authored keyframes, **not motion capture**. They do not contain third-party model/motion assets.

## Lip-sync

HeadAudio is vendored under `frontend/public/vendor/headaudio/`, with its MIT license, source commit and local patches documented in NOTICE.md. HeadAudio uses MFCC features/Gaussian prototypes on an AudioWorklet. Local patches preserve viseme index 0 and clear classifier/filter/VAD state on interruption. Its prototype model was trained on English synthetic speech; Vietnamese accuracy has not been established.

`doctorLipSync.js` is the adapter. It maps detected visemes to model expressions, handles the five VRM vowel presets including `ou`, bounds their sum, closes the mouth during silence, and falls back to the existing spectrum mouth when detection is unavailable/stale. Worklet/model initialization happens in parallel with TTS. Playback never awaits it. It adds no LLM/TTS provider call. This does **not** mean zero processing latency: audio classification itself is causal and can trail audio; device/browser performance needs measurement.

The two shipped doctor rigs expose vowel presets and standard emotional expressions, not a complete set of consonant/brow/cheek morphs. Without those shapes, consonants are approximated; suppressing vowels on PP is not equivalent to a sculpted bilabial shape.

## Optional provider timing contract

TTS currently returns an audio Blob without alignment. The default path still estimates phrase boundaries by relative text length within that audio segment. When a provider supplies timings, both authenticated API and direct-fetch paths accept an optional `X-MedGuard-Speech-Timing` JSON header. Times are **seconds relative to the current audio segment**:

```json
{
  "phrases": [{"start": 0.0, "end": 2.6, "text": "Xin chào bạn."}],
  "visemes": [{"start": 0.1, "end": 0.2, "viseme": "PP"}, {"start": 0.2, "end": 0.4, "viseme": "aa"}]
}
```

Viseme IDs use the Oculus naming set, or VRM vowel IDs `aa`, `ih`, `oh`, `ou`; `E`, `I`, `O`, `U` are supported. If using Rhubarb mouth shapes, explicitly prefix IDs such as `rhubarb_E`; those are approximate shape mappings, not Oculus phoneme IDs. Invalid timings are ignored. Timeline silence returns a closed mouth rather than holding the last cue. Playback uses the actual media element currentTime, including pause/seek/rate changes. No timestamp generation or forced-alignment backend is claimed by this change.

## Validation

Run from `frontend/`:

```sh
npm ci
npm run build:doctor-vrma
npm run test:doctor-motion
npm run test:doctor-animation
npm run test:doctor-rigs
npm run test:doctor-latency
npm run build
```

The real-rig test parses the original model meshes/skeletons, omitting only textures for Node execution. It loads VRMA through the actual loader, exercises 24 alternatives on DoctorTuan, DoctorMai and VRM1_Sample, checks greeting geometry, finite/bounded joints and planted feet. It writes measurements to `.artifacts/open-motion/rig-report.json`.

The classifier test executes the bundled DSP and 39-prototype model with generated voiced/silent audio. It verifies delivery, pause detection, reset, and viseme index 0. It is **not a Vietnamese accuracy test**.

The implementation run passed unit, DSP, queue/cancellation, build and real-rig checks. In that Node run, P95 motion computation was about 0.24–0.40 ms for the two doctors; max arm step was about 0.0534 rad at 60 Hz. These exclude GPU rendering and AudioWorklet scheduling, and are not an iPhone FPS benchmark.

Browser visual/integration tests could not launch in the execution environment (Chromium socket/process restrictions). Run `npm run test:doctor-holistic` and `npm run test:doctor-web` on a machine with Chromium, then review the real Vietnamese doctor voices on desktop and iPhone. Do not treat the passing skeleton checks as a visual realism or end-to-end latency certification.
