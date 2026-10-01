# V27.5 engineering evaluation

Baseline: `74315b926986cbbcb723be10f4280a7d60a14a5a`. Integrated with the concurrent V27.5 target `501eed3a631b1f7e83475d846b2cdd0140c497bd`.

The patch preserves approved safety actions and warnings through fallback composition, sanitization and frontend rendering. Grounding quotes only declarative current-turn clauses, retaining numeric measurements and excluding requests to delay assessment or start medication. The quality gate rejects partial 200-question reports and empty replies. OCR tests now supply complete valid PNG fixtures.

| Check | Result |
| --- | --- |
| Backend suite | 878 passed after reconciling the concurrent V27.5 implementation |
| Frontend response-authority contract / production build | PASS |
| Python compilation / frozen V10 provenance | PASS |
| 40-case medical response gate | PASS; zero critical failures and zero subthreshold cases |
| 200-turn conversation benchmark | 99.47/100; zero critical failures, zero below 70, zero card-state failures |
| Exact duplicate replies | 3%, compared with 9% on baseline |
| Exact duplicates within a conversation | Zero |
| Patient language, relevance/memory and output hygiene gate | Zero violations |

`200_QUESTIONS_ANSWERS.md` contains only the 200 questions and answers. `BENCHMARK_SUMMARY.json` records the measured engineering results. Duplication is measured over complete replies; grounding increases specificity and does not demonstrate new clinical reasoning or superiority over another product.

The live Gemini marker probe passed Writer 5/5 and Reviewer 5/5 with no retries after pacing; this does not validate clinical output.

These conversation evaluations use the development runtime with unavailable live providers and contextual deterministic fallback. Provider test doubles and offline scenarios do not establish live-model quality. Independent clinical validation, approved knowledge, actual OCR engines and image evaluation, production database/queue/object storage, credentials, consent enforcement and external operational evidence remain release dependencies. Passing these checks does not authorize production clinical use.
