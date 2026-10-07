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
`doctor-voices-20261007`; POST audio includes the revision and voice settings in
response headers. Restart the updated backend as well as the frontend. These
changes are on `feature/doctor-avatar-refinement`, not the default `develop`.
These are general Vietnamese neural voices with calmer tempo/pitch settings;
configuration alone does not establish a clinical or professional voice quality.

## Verification

- `python -m pytest app/tests/test_doctor_voice.py -q`
- `python -m pytest app/tests/test_ui_and_endpoints.py::test_dashboard_and_static_assets_serving -q`
- `npm --prefix frontend run test:doctor-motion`
- `CHROME_PATH=/path/to/chromium npm --prefix frontend run test:doctor-web`
- `npm --prefix frontend run build`

The browser test uses real VRMs and real Web Audio analysis with a deterministic
audio fixture. It checks both personas, silence, stop, pending-speech cancellation,
rapid switches, provider failure, viewport overflow and runtime errors. The latest live-provider probe could not synthesize either voice because of a
TLS certificate validation error in the test environment. The fixture does not
verify provider availability or subjective voice quality.
