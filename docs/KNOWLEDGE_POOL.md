# Reviewed knowledge pool

The runtime pool supplements the existing retrieval index with public source
documents. It does not learn clinical facts from patient messages or model
answers. No candidate is promoted automatically.

## Lifecycle

1. An administrator stages a document, or the agent stages public source text
   fetched by the trusted evidence service after a verified response.
2. The document remains `pending_review` and cannot enter pool retrieval.
3. An administrator submits an independent review record bound to the exact
   document digest, with a named reviewer, explicit boolean source/clinical
   approvals, timezone-aware review date, and finite expiry.
4. Approved documents enter retrieval only for their clinical/pharmacology
   domain. Writer and Reviewer receive the retrieved context through the
   existing agent graph.
5. Expired, revoked, or content-modified records are excluded on each lookup.

An approval record records provenance; it does not independently verify the
reviewer's clinical credentials. Existing static knowledge retains its existing
governance rules. Pool approval is not production or clinical validation.

## Operation

Set `MEDGUARD_KNOWLEDGE_POOL_DATABASE` to a durable writable SQLite path.
The default is `.runtime/knowledge_pool.sqlite3`; database permissions are 0600.
Pool read/capture failures increment metrics and preserve fallback retrieval.

Authenticated administrators can use:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/knowledge-pool` | Candidate metadata and bounded gap telemetry |
| POST | `/v1/knowledge-pool/candidates` | Stage public source text |
| POST | `/v1/knowledge-pool/{document_id}/approve` | Submit exact-version review |
| POST | `/v1/knowledge-pool/{document_id}/revoke` | Remove a record from retrieval |

Mutations require the session CSRF token and permitted origin. Review payloads
contain `approval_id`, `reviewer_id`, `source_verified`, `clinical_approved`,
`content_sha256`, `reviewed_at`, and `expires_at`. Boolean flags must be JSON
booleans, not strings or integers. `content_sha256` is the inventory `digest`.

`python -m scripts.manage_knowledge_pool --seed-existing` stages existing
curated/public material without approving it. Repeated identical submissions
deduplicate. A changed document requires a new candidate and review.

Gap telemetry stores a database-keyed HMAC, domain, intent, reason, timestamps,
and occurrence count. It does not retain the patient's question. Counts identify
coverage gaps but cannot reconstruct the missing clinical topic. The pool is
not eligible for automatic training.

## Verification

Run `python -m pytest app/tests/test_knowledge_pool.py
app/tests/test_localized_headache_context.py -q` from the project environment.
Tests cover approval isolation, tampering, expiry, revocation, source allowlist,
privacy, authentication/CSRF, unavailable storage, anatomy, and topic switching.
An unknown complaint still enters the configured agent path; an unavailable or
disabled pipeline returns a valid fallback status instead of an API error.
These checks do not establish live-model response quality.
