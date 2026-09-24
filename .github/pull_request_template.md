## Summary

Describe the problem, the implemented change and the user-visible outcome.

## Scope

- [ ] Backend/API
- [ ] Clinical rules or knowledge
- [ ] LLM/VLM gateway or agent flow
- [ ] React UI
- [ ] Data, OCR or training
- [ ] Infrastructure or operations
- [ ] Documentation only

## Risk and safety

- [ ] Tenant isolation and authorization were considered.
- [ ] Protected health information is not exposed in logs, prompts or artifacts.
- [ ] Deterministic clinical rules remain authoritative.
- [ ] Failure, timeout and low-confidence paths fail closed.
- [ ] No secret, credential, local database or generated test artifact is committed.
- [ ] Clinical or knowledge changes include source and reviewer evidence, or are explicitly development-only.

## Validation

List the exact commands run and summarize results.

```text
.venv/bin/pytest -q
cd frontend && npm ci && npm run build
```

## Deployment

Describe migrations, configuration changes, rollout, rollback and monitoring impact. Write `None` when not applicable.
