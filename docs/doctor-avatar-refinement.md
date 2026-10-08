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


## Response latency (2026-10-08)

The companion waits for the final `/v1/chat` response before starting clinical
speech. Safety routing, Reviewer, grounding and clinical authority are unchanged.
The UI no longer discards content after 52 words; full returned warnings remain
visible and are read. The first sentence is synthesized separately; one following
chunk is prepared ahead, with a maximum of two pending preparations. Later short
sentences are grouped up to 360 characters. Both personas keep their existing
voice/rate/pitch. Each chunk still uses complete MP3 playback, compatible with the
existing HTML audio pipeline; this is sentence pipelining, not raw MP3 streaming.
Sentence boundaries may introduce pauses, and first audio still depends on TTS
provider/network latency. No claim of a guaranteed sub-second response is made.

Stop, mute during speech, persona change, new question and unmount invalidate old
turns and abort chat/TTS fetches. `/v1/tts` cancels its synthesis task when the
browser disconnects. An already running synchronous upstream chat/model call may
continue until its existing deadline; browser cancellation does not terminate
that thread. API deadlines now cover response bodies and combine correctly with
external cancellation. Superseded responses cannot update conversation history.
No provider key, TLS verification or login protection is relaxed.

AI adapters reuse a process-local HTTP pool (32 connections, 16 keepalive,
30-second keepalive expiry per configured timeout), closed at application shutdown.
Authorization stays on individual calls and provider cookies are rejected. No
patient answer or audio cache is introduced. HTTP clients are thread-safe, but
this change does not parallelize a writer with its dependent Reviewer.

Latency observations contain numbers and fixed persona/stage labels only:
- Browser `medguard:companion-latency` events: `safe_text` elapsed time and
  `first_audio` TTS/total elapsed time. No transcript, patient ID or content.
- Backend `medguard_tts_first_chunk_ms` and `medguard_tts_complete_ms` aggregate
  count/sum metrics. Current metrics do not store samples or report percentiles.

Additional checks:
- `npm --prefix frontend run test:doctor-latency`
- `python -m pytest app/tests/test_provider_transport.py app/tests/test_doctor_voice.py -q`
- `test:doctor-web` holds the next TTS response back and verifies first audio
  plays first, while the entire warning is subsequently read, for both doctors.
- `test:doctor-live` reports actual first-audio latency for synthetic samples.

Deployment: checkout `feature/doctor-avatar-refinement`, pull, restart backend
with `python3 scripts/start_with_doctor_voice.py`, then open
`http://localhost:8000/?view=companion`. Built frontend assets are committed;
when developing instead, run `npm --prefix frontend ci` and
`npm --prefix frontend run dev` alongside the backend.


## MacBook chat configuration and conversation repair

`doctor-chat-20261008` exposes non-secret config state at
`/v1/companion/status`. The page shows a rule-based/fallback notice instead of
pretending that a missing, timed-out or rejected AI response is a generated one.
Actual dialogue requires a reachable LiteLLM gateway with working upstream
provider credentials; the voice service alone does not provide AI reasoning.

1. Use Python 3.10+ and run `python3 scripts/start_with_doctor_voice.py --check`.
2. If an existing gateway is ready, run
   `python3 scripts/configure_doctor_chat.py --gateway-url http://127.0.0.1:4000/v1`.
   Enter a **gateway** virtual/master key in Terminal (hidden input). Do not enter
   the Gemini/OpenAI upstream key here. Use `--api-style responses` for a gateway
   configured for that API rather than Chat Completions.
3. The wizard requires all six `medguard-*` aliases and sends six small synthetic
   non-clinical probes through Writer/Reviewer aliases. It does not claim clinical
   validation. A failing check does not write a new configuration. `.env.doctor`
   is private (0600), excluded from Git, and leaves `.env`/login/TLS settings intact.
   Use `--force` only when intentionally replacing an existing doctor profile.
4. Restart with `python3 scripts/start_with_doctor_voice.py`; the launcher loads
   `.env.doctor` using Uvicorn's dotenv support. Explicit shell environment values
   take priority. Open `http://localhost:8000/?view=companion` and check the AI
   mode/revision in Settings. Existing `.env` setups remain supported.

If no gateway exists, use the existing Docker Desktop gateway deployment in
`infrastructure/litellm/docker-compose.yml` with its local `.env` and your own
provider key/master key/database credentials. Model names must be valid for your
provider account; aliases are logical application names, not model downloads.
The local YAML template now reads `LITELLM_MASTER_KEY` from the environment.
No provider key is distributed with Git. This code was tested on Linux with
Chromium, not on physical macOS/Safari; browser autoplay still requires an initial
click (try Settings → voice preview, or Read again).

The positive goals “muốn sống khỏe” and “muốn sống lâu” no longer match the
self-harm regex. Genuine desire to die, not wanting to live, lethal-dose queries
and the existing dual medical/crisis handling remain regression-tested. User
questions are sent unchanged; avatar tone instructions no longer contaminate
clinical intent extraction. The companion reads the returned action steps,
safety notes and follow-up questions, not only the summary. In background mode
it polls the exact request ID for a verified promoted answer, with cancellation
on new questions, stop, persona changes or unmount. It never speaks a draft.

Desktop layout has separate left avatar/right response regions. Mobile stacks
the response below the avatar. The full response scrolls in its own panel so
text does not cover the model. Browser tests assert non-overlapping bounds.

Additional regression commands:
- `python -m pytest app/tests/test_companion_configuration.py app/tests/test_ood_and_crisis.py app/tests/test_dual_agent_scenarios.py -q`
- `npm --prefix frontend run test:doctor-latency`

The audio context and a reusable media element are primed in the submit/click
handler, before network awaits. Silent priming uses a blob URL permitted by the
existing CSP; no security policy is loosened. Successive sentence clips reuse
one media source/context, disconnected between clips and closed on unmount.
The doctor browser regression now uses ordinary autoplay policy, not an autoplay
bypass launch flag. Physical Safari/macOS still needs device validation.
