# V12 Agent-First Runtime Profile

V12 changes the normal answered clinical response path from deterministic-prose-first to agent-first generation.

## Important: old `.env` files can override V12

Configuration loaded from `.env` is explicit. If an existing development `.env` still contains:

```dotenv
MEDGUARD_AGENT_MODE=shadow
MEDGUARD_AGENT_BACKGROUND_ENABLED=true
MEDGUARD_AGENT_MAX_ITERATIONS=0
```

then MedGuard deliberately preserves the old shadow/background behavior. The patient will still receive the deterministic first response while the model reviews in the background.

For the V12 clinical response path, use the values in `.env.v12-agent-first.example`, in particular:

```dotenv
MEDGUARD_ENVIRONMENT=development
MEDGUARD_AGENT_MODE=enforced
MEDGUARD_AGENT_COVERAGE_SCOPE=clinical
MEDGUARD_AGENT_SYNC_ENABLED=false
MEDGUARD_AGENT_BACKGROUND_ENABLED=false
MEDGUARD_AGENT_MAX_ITERATIONS=1
MEDGUARD_LLM_GATEWAY_URL=http://127.0.0.1:4000/v1
MEDGUARD_LLM_GATEWAY_API_KEY=<litellm-virtual-key>
```

`agent_sync_enabled=false` is intentional for V12 clinical requests: answered `triage` and `safety` requests in `enforced` mode call the V12 `generate_response()` path directly. The old sync/background flags remain for compatibility with non-V12 enhancement paths.

## Expected request path

```text
user turn
  -> intent / episode / deterministic clinical safety
  -> ClinicalAgentContract
  -> Writer / Clinical Reasoner
  -> independent Reviewer
  -> at most one revision
  -> deterministic PASS/REJECT release gate
  -> patient UI
```

The deterministic stack continues to own minimum urgency, red flags, locked emergency actions and tool execution. The model cannot downgrade those constraints.

## Degraded behavior

If the LiteLLM gateway is unreachable, either role is not configured, a model times out, structured output fails, citations fail verification, or the final safety gate rejects the draft, MedGuard returns the existing deterministic safe fallback. This is intentional fail-safe behavior and should be visible in technical diagnostics as `answer_origin=deterministic_fallback` rather than being mistaken for a successful V12 model response.

## Local verification

1. Start the selected LiteLLM profile and verify both logical aliases.
2. Start MedGuard with `.env.v12-agent-first.example` values copied into the untracked `.env`.
3. Send a non-emergency clinical question such as `Tôi đang cảm thấy đau các khớp tay`.
4. Inspect the response metadata in technical mode:
   - `answer_origin` should be `gateway_verified` for an accepted V12 response.
   - `verification_status` should be `verified`.
   - `agent_trace` should show successful Writer and Reviewer stages internally.
5. If `answer_origin=deterministic_fallback`, inspect the gateway health and the internal fallback reason before evaluating prose quality.

Never judge whether V12 is active solely from how polished the text sounds.
