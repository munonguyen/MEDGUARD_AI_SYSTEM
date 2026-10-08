# Doctor avatar refinement

Based on `e801e38` from `feature/v28-1-clinical-context-reasoning`.

## Appearance

Both doctor VRMs use a white coat, teal inner uniform and dark scrub trousers.
The female cardigan hem is extended, decorative lace is covered, original short
bottoms are replaced with trousers using the existing leg skinning, and the skin
atlas is brightened while preserving warm shading. The renderer adds folded
lapels, an AI staff badge and a stethoscope attached to the actual animated chest.
The original skeleton, face morph targets and source license metadata are retained.
These remain stylized VRM characters, rather than photorealistic human scans.

`frontend/scripts/refine_doctor_models.py` is the reproducible asset transform.
It requires Pillow and NumPy, appends binary data on aligned boundaries, compacts
unused buffers, and marks transformed assets to prevent cumulative edits.

## Motion

`doctorMotion.js` controls time-based quaternion damping for pose transitions,
subtle breathing, attentive head movement and intermittent explanatory gestures.
Utterance-aware plans alternate greeting, invitation, explanation, reassurance
and caution gestures involving shoulder, elbow, wrist, head and torso. A brief
written-reply acknowledgment works even when TTS is unavailable, with the mouth
closed. The settings panel includes an independent greeting gesture preview.
The speech envelope fades gestures in and out. Web Audio RMS drives the mouth and
closes it during pauses. This is audio-envelope animation, not phoneme alignment.
Reduced-motion preferences disable incidental body movement.

The built-in sample models have unstable legacy spring-bone colliders after
normalized-bone posing. Their authored hair shape is preserved with spring
simulation disabled; custom VRM uploads retain their spring-bone simulation.
Rapid model switches discard stale loads and dispose their resources.

## Voice

The primary 3D page requests `/v1/tts` via POST through the shared API client.
Text is sent in the body, and returned audio uses `Cache-Control: no-store`.

- Male: `vi-VN-NamMinhNeural`, rate `-8%`, pitch `-6Hz`.
- Female: `vi-VN-HoaiMyNeural`, rate `-7%`, pitch `-12Hz`.

`edge-tts==7.2.8` is included in application dependencies. Validated requests are
read in full, with a 4,000-character limit and 25-second synthesis deadline.
An unavailable provider leaves the written answer visible and shows a notice,
without silently substituting an operating-system voice. Stop, persona changes
and unmount cancel pending synthesis and dispose playback and analysis resources.
The legacy GET endpoint remains for compatibility with older views.

The settings dialog fetches `/v1/tts/profiles` and displays the running backend's
voice, rate and pitch for the selected doctor. “Nghe thử giọng bác sĩ” plays a
short sample through the same POST audio pipeline. Missing profile metadata
shows an update/backend warning and disables preview. The response revision is
`doctor-voices-20261008`; POST audio includes the revision and voice settings in
response headers. Restart the updated backend as well as the frontend. These
changes are on `feature/doctor-avatar-refinement`, not the default `develop`.
These are general Vietnamese neural voices with calmer tempo/pitch settings;
configuration alone does not establish a clinical or professional voice quality.

## Verification

- `python -m pytest app/tests/test_doctor_voice.py -q`
- `python -m pytest app/tests/test_ui_and_endpoints.py::test_dashboard_and_static_assets_serving -q`
- `npm --prefix frontend run test:doctor-motion`
- `CHROME_PATH=/path/to/chromium npm --prefix frontend run test:doctor-web`
- Optional live provider/browser: `CHROME_PATH=/path/to/chromium npm --prefix frontend run test:doctor-live` (free port 8466, Internet; uses backend-built page, synthetic greetings, no API/audio mocks).
- `npm --prefix frontend run build`

The browser test uses real VRMs and real Web Audio analysis with a deterministic
audio fixture. It checks both personas, silence, stop, pending-speech cancellation,
rapid switches, provider failure, viewport overflow and runtime errors. The latest live-provider probe synthesized both voices (32,256 bytes male and
30,960 bytes female) after loading the machine's trusted CA certificates alongside
certifi in the pinned edge-tts 7.2.8 transport context. Certificate and hostname
verification remain enabled and are regression-tested. This compatibility adapter
uses the pinned package's shared `_SSL_CTX`; review it when changing edge-tts.
The fixture does not verify provider availability or subjective voice quality.
A failed or blocked playback now leaves a persistent inline message and a
“Đọc lại” button; it never silently switches to an OS default voice.
The earlier advanced motion commits were not recovered: these are newly added
gesture plans, not a restoration of that entire prior implementation.
