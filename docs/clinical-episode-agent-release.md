# Clinical episode and agent release correction

## Reproduction and causes

Reported sequence: chest pain with breathlessness → toothache → “Tôi đang đau ruột thừa có nên đi mổ sớm không”. The last question must never reuse dental guidance.

The episode router did not recognize `ruot thua` / `ho chau phai`, and its unknown-topic inquiry detector did not include `toi dang dau`. Consequently, dental history could remain in the text passed to symptom guidance. Separately, the agent patient context contained every earlier assistant answer even when clinical tools isolated the latest episode. Runtime defaults enabled enforced agents only in development, leaving production disabled unless explicitly overridden.

The reported appendix pain also had a ROUTINE safety floor. Regression tests reproduced that classification before the safety fix. The correction treats a current report as needing urgent in-person assessment, without treating the user's label as a confirmed diagnosis or surgical indication. Educational, negated and recovered-history statements do not activate this added detector. Existing stronger emergency detectors still take precedence.

A broader regression also exposed an existing accent-folding collision: “hơi đau đầu” was classified as the “hói đầu” hair/scalp episode. The routing correction preserves the headache episode when a subsequent turn reports sudden severe worsening.

Clinical reference: https://www.nhs.uk/conditions/appendicitis/ (reviewed during implementation). This is engineering evidence, not clinician approval of the complete knowledge registry.

## Release flow

1. Validate the current user turn and resolve the active complaint episode.
2. Run the deterministic safety/clinical tools; emergency action cannot depend on model availability.
3. Send the active user episode, patient background and structured clinical contract to Writer. Prior assistant prose and `last_result` cannot anchor a switched clinical topic.
4. Reviewer and the local quality/safety gates must pass before `gateway_verified` release. Existing evidence, citation and professional-response gates remain in place.
5. Configuration failure, capacity rejection, deadline, circuit opening, provider failure or quality rejection use explicitly unverified safety fallback. No fallback is promoted to verified by this change.

Default non-test runtime: `enforced`, coverage `all`, synchronous execution. Production readiness requires agents by default. Explicit operator overrides remain possible; production readiness reports them as unsuitable when enforced synchronous coverage is absent. Unit tests retain deterministic defaults.

For clinical answers the UI now displays the verification status without needing technical details to be expanded. Verified agent narrative does not get additional keyword-selected frontend follow-up suggestions.

## Proof of execution

`/v1/chat` now returns a small `agent_execution` summary alongside `verification_status`, `answer_origin` and `request_id`:

```json
{
  "requested": true,
  "writer": "not_run",
  "reviewer": "not_run",
  "reason": "configuration_incomplete"
}
```

`requested` means the orchestration path was selected, not that model calls completed. Stage statuses come from existing internal stage traces. A total deadline without a returned stage trace reports `unknown`, never invented success. Reason codes are bounded; raw provider errors, credentials, prompts and chain-of-thought are not exposed. Detailed fallback reasons remain in tenant-scoped audit metadata.

## Capacity and scaling

`MEDGUARD_AGENT_WORKERS` defaults to 8 and `MEDGUARD_AGENT_MAX_PENDING` to 16. The latter includes running and queued work per process. Admission rejects immediately at capacity and increments `medguard_agent_admission_rejected_total`; the answer remains explicitly unverified. A timed-out running task retains its permit until it actually completes. Cancelled pending tasks release permits. This prevents repeated timeout traffic from creating an unbounded executor queue.

This bound is per process, not a cluster-wide provider limit. Budget aggregate capacity as replicas × application processes × worker count; configure gateway/provider quotas and distributed ingress rate limits accordingly. Existing production readiness checks require durable database, queue and storage adapters, distributed rate limiting, knowledge approval and external clinical/load evidence. This change does not certify those dependencies or throughput. Running HTTP calls cannot be forcibly terminated by Python future cancellation; provider transport timeouts remain necessary.

## Validation and operational limitation

Regression tests cover the exact multi-turn sequence, active-episode agent input, urgent appendix floor, negation/hypothetical/history controls, chest-pain emergency fallback, capacity retention after caller cancellation, pending cancellation and recovery. Existing Writer/Reviewer tests use fake providers and are protocol/quality-gate tests, not live-model quality certification.

The development workspace has no configured gateway URL or virtual key. A real Writer→Reviewer run and production load test remain mandatory before claiming live agent verification or scalable clinical quality. Set `MEDGUARD_LLM_GATEWAY_URL`, `MEDGUARD_LLM_GATEWAY_API_KEY` and configured Writer/Reviewer aliases in the deployment secret/configuration system; require the gateway transport, model contract and response coverage checks in `/v1/health/readiness` to pass. Do not remove pending clinical-knowledge warnings to make readiness look healthy.

The first broad backend run reported 948 passed and 8 failed. All 8 failures reproduced against the prior commit. The headache episode failure was fixed here. The frozen-history check passed after fetching full git history. Six OCR tests still use truncated PNG headers as supposedly valid images; the installed Pillow rejects these before engine availability is checked. They are excluded explicitly from the follow-up broad run, not made green by weakening image validation. These pre-existing OCR test failures remain outside this correction.

Final follow-up broad run: **953 passed, 6 OCR tests explicitly deselected**. The final focused episode/admission regression file: **14 passed** (including the capacity-rejection API test added after broad collection). Vite production build and `git diff --check` passed. These counts are automated contract/safety tests, not evidence of a live model or production load test.
