# V12 Agent-First Clinical Response Architecture

## Goal

V12 changes ownership of patient-facing clinical prose without changing ownership of deterministic safety.

The deterministic stack remains authoritative for extracted facts, episode state, safety floors, red flags, tool results and minimum disposition. The agent stack becomes authoritative for the normal patient-facing explanation when the clinical gateway is configured and `MEDGUARD_AGENT_MODE=enforced`.

The professional doctor-response dataset is used only to derive communication principles (directness, misconception correction, mechanism explanation, actionability and question economy). It is not a clinical fact source and is never used as a keyword-to-template lookup table.

## Runtime flow

```text
User turn
  -> Intent + episode resolution
  -> Canonical clinical state / deterministic safety + tools
  -> ClinicalAgentContract
  -> Researcher / Clinical Writer
  -> Independent Reviewer (Jev role)
  -> at most one bounded revision
  -> deterministic non-authoring release gate
  -> patient UI

Failure / unavailable gateway
  -> existing deterministic safe fallback
```

## Invariants

1. The writer receives a structured clinical envelope, not legacy deterministic prose.
2. Locked emergency actions cannot be downgraded by the writer or reviewer.
3. The reviewer scores/rejects and requests revision; it does not author the response.
4. The final quality gate passes or rejects; it does not repair prose.
5. `shadow` mode preserves background-assessment semantics and never becomes the primary writer.
6. `enforced` mode is agent-first for answered `triage` and `safety` requests.
7. Tests default to disabled agent mode unless explicitly configured, keeping deterministic regression suites hermetic.
8. Development defaults to `enforced` unless `MEDGUARD_AGENT_MODE` is explicitly set; if providers are unavailable the safe deterministic fallback remains active.
9. Only one reviewer revision is allowed and all work remains bounded by the configured total timeout.

## Communication contract

The clinical writer must:

- address the patient's practical concern early;
- interrupt dangerous misconceptions before background explanation;
- distinguish clinical assessment from confirmed diagnosis;
- avoid inventing patient facts or rule antecedents;
- give situation-specific next actions;
- preserve locked safety actions;
- ask at most one high-information question for non-emergency cases;
- ask no blocking question before emergency action;
- avoid generic boilerplate such as a bare request for “more clinical assessment”.

## What V12 does not do

V12 does not let an LLM replace the Safety Kernel, execute operational tools, invent medication dosing, or override deterministic emergency floors. Operational commands remain tool/service-first; a future operational writer can render their results without changing tool authority.
