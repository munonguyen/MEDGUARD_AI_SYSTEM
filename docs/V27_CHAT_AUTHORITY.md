# V27 chat split

`app/services/chat_core.py` is the byte-for-byte V26/V27 routing core retained during the V27 authority migration.
`app/services/chat.py` is the thin policy facade that re-exports the historical API and overrides only `_response` so clinical `needs_information` stays on the same agent-first contract as answered clinical requests.

This split is intentionally narrow and reversible. Safety/routing behavior remains in `chat_core.py`; response-authority policy remains in `chat.py`.
