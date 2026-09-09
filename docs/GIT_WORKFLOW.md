# Git Workflow

MedGuard uses a protected-main, integration-branch workflow. The repository keeps deployable history linear while allowing backend, AI, UI, validation and documentation changes to be reviewed independently.

## Long-lived branches

| Branch | Purpose | Direct push |
|---|---|---|
| `main` | Production and signed release history | Prohibited |
| `develop` | Integrated, tested candidate for the next release | Prohibited |

`main` must contain only reviewed release merges. `develop` is the default base for ordinary feature work. Neither branch is a personal workspace.

## Short-lived branches

| Pattern | Base | Merge target | Use |
|---|---|---|---|
| `feature/<scope>` | `develop` | `develop` | Product or architecture capability |
| `fix/<scope>` | `develop` | `develop` | Non-production bug fix |
| `test/<scope>` | `develop` | `develop` | Test, benchmark or evaluation evidence |
| `docs/<scope>` | `develop` | `develop` | Documentation and repository governance |
| `release/<version>` | `develop` | `main`, then `develop` | Release stabilization only |
| `hotfix/<scope>` | `main` | `main`, then `develop` | Urgent production correction |

Use lowercase kebab-case after the prefix. Delete a short-lived branch after merge.

## Commit policy

Use Conventional Commits:

```text
<type>(<optional-scope>): <imperative summary>
```

Accepted types are `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `build`, `ci`, `chore` and `revert`. Keep each commit reviewable and avoid combining unrelated backend, UI, data and infrastructure changes.

Examples:

```text
feat(ai): add verifier release gate
fix(triage): preserve negated red-flag context
test(ocr): add missing-image failure cases
docs: document production readiness gates
```

## Pull request flow

1. Update the base branch and create a correctly prefixed short-lived branch.
2. Commit one coherent concern at a time using Conventional Commits.
3. Push the branch and open a pull request against its intended base.
4. Complete the risk, privacy, clinical-safety and validation sections in the PR template.
5. Resolve all required checks and review comments.
6. Squash-merge ordinary short-lived branches. Preserve release and hotfix merge commits when they carry coordinated release history.
7. Delete the remote short-lived branch after merge.

Clinical behavior, safety rules, source authority, agent release gates, consent, tenant isolation and protected data handling require explicit review evidence. Model-generated output is never accepted as clinical validation by itself.

## Required checks

The `Repository CI` workflow must pass before merge:

- Python compile check and complete `pytest` regression suite.
- React dependency installation and production build.
- Git conflict resolution and an up-to-date PR branch.
- No committed secrets, local databases, logs, test artifacts or dependency directories.

For clinical, OCR, model or data changes, run the relevant repository benchmark and attach its artifact or summary to the PR. Production promotion additionally follows `docs/DEPLOYMENT_RUNBOOK.md` and the readiness gates in `docs/ARCHITECTURE_STATUS.md`.

## Branch protection

Configure GitHub protection for `main` and `develop` with these minimum settings:

- Require a pull request and at least one approving review.
- Dismiss stale approvals when new commits are pushed.
- Require the `Backend regression` and `Frontend build` checks.
- Require conversation resolution and prevent force pushes and deletion.
- Require linear history on `develop` and signed release tags on `main`.
- Restrict direct pushes to release automation or repository administrators for emergencies.

## Initial import stack

The first complete architecture is intentionally split into a cumulative review stack:

```text
main
  -> feature/backend-clinical-platform
  -> feature/llm-gateway-control-plane
  -> feature/react-chat-workspace
  -> test/continuous-validation
  -> docs/repository-governance
  -> develop
```

Review or merge the initial branches in that order. Subsequent feature branches should start directly from `develop` and target `develop` unless they are a release or hotfix.
