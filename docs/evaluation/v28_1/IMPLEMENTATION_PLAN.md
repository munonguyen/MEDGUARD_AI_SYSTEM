# MedGuard V28.1 Clinical Context Reasoning Upgrade

## Goals

Move from keyword-triggered alerts to context-aware clinical reasoning.

## Safety objectives

- Detect emergency patterns using symptom + severity + duration + associated findings.
- Avoid false emergency escalation from negated symptoms.
- Separate current emergency from hypothetical safety questions.
- Prevent medication advice without sufficient context.

## Implementation phases

1. Clinical entity extraction with negation scope.
2. Domain routing (cardio, allergy, respiratory, neurological, musculoskeletal).
3. Risk calibration layer.
4. Medication safety guard.
5. Explanation alignment reviewer.
6. Regression benchmark expansion.

## Acceptance criteria

- No keyword-only emergency escalation.
- No unsupported diagnosis statements.
- No unsafe medication recommendation.
- Emergency and routine scenarios tested separately.
