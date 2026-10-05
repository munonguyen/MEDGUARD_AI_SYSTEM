"""Versioned public knowledge candidates; no automatic clinical promotion.

Patient messages/answers are never stored as source documents. Gap telemetry
stores keyed fingerprints and bounded categories only. Approved documents are
immutable, expire, and can be revoked without rebuilding the RAG index.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import hmac, json, os, secrets, sqlite3, time
from pathlib import Path
from uuid import uuid4
from app.services.trusted_evidence import trusted_medical_url


def document_digest(title, content, source_url, domain):
    return sha256(json.dumps([title, content, source_url, domain], ensure_ascii=False).encode()).hexdigest()


class KnowledgePool:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        os.chmod(self.path, 0o600)
        with self.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
                source_url TEXT NOT NULL, domain TEXT NOT NULL, digest TEXT NOT NULL,
                state TEXT NOT NULL, created REAL NOT NULL, expires REAL,
                review TEXT, reviewer TEXT
              );
              CREATE TABLE IF NOT EXISTS gaps (
                fingerprint TEXT PRIMARY KEY, domain TEXT NOT NULL, intent TEXT NOT NULL,
                reason TEXT NOT NULL, occurrences INTEGER NOT NULL, first_seen REAL NOT NULL,
                last_seen REAL NOT NULL
              );
              CREATE TABLE IF NOT EXISTS pool_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL, action TEXT NOT NULL,
                actor TEXT NOT NULL, at REAL NOT NULL
              );
            ''')
            db.execute("INSERT OR IGNORE INTO pool_meta VALUES('gap_hmac_key',?)", (secrets.token_hex(32),))

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _event(db, document_id, action, actor):
        db.execute('INSERT INTO events VALUES(?,?,?,?,?)', (uuid4().hex, document_id, action, actor, time.time()))

    def stage(self, *, title, content, source_url, domain, actor):
        title, content, source_url = title.strip(), content.strip(), source_url.strip()
        if not (1 <= len(title) <= 180 and 40 <= len(content) <= 12000):
            raise ValueError('invalid_document_size')
        if domain not in {'clinical', 'pharmacology'} or not trusted_medical_url(source_url):
            raise ValueError('invalid_medical_source_or_domain')
        from urllib.parse import urlsplit
        source = urlsplit(source_url)
        if source.query or source.fragment:
            raise ValueError('canonical_public_source_required')
        digest = document_digest(title, content, source_url, domain)
        with self.db() as db:
            existing = db.execute('SELECT id FROM documents WHERE digest=?', (digest,)).fetchone()
            if existing:
                return existing['id']
            if db.execute('SELECT count(*) FROM documents').fetchone()[0] >= 2000:
                raise ValueError('knowledge_pool_capacity_reached')
            document_id = 'KP-' + uuid4().hex
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (document_id, title, content, source_url, domain, digest, 'pending_review', time.time(), None, None, None))
            self._event(db, document_id, 'staged', actor)
            return document_id

    def approve(self, document_id, *, review, actor):
        # Explicit review record binds to exact bytes and a finite review period.
        # An admin record is provenance; it cannot prove clinical credentials.
        required = ('approval_id', 'reviewer_id', 'source_verified', 'clinical_approved',
                    'content_sha256', 'reviewed_at', 'expires_at')
        if any(key not in review for key in required) or review['source_verified'] is not True or review['clinical_approved'] is not True:
            raise ValueError('independent_review_required')
        if not str(review['approval_id']).strip() or not str(review['reviewer_id']).strip():
            raise ValueError('review_identity_required')
        reviewed = datetime.fromisoformat(review['reviewed_at'])
        expires = datetime.fromisoformat(review['expires_at'])
        if reviewed.tzinfo is None or expires.tzinfo is None:
            raise ValueError('review_timezone_required')
        now = time.time()
        if reviewed.timestamp() > now or not now < expires.timestamp() <= now + 366 * 86400:
            raise ValueError('invalid_review_period')
        with self.db() as db:
            row = db.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
            if not row or row['state'] != 'pending_review':
                raise ValueError('pending_document_required')
            actual = document_digest(row['title'], row['content'], row['source_url'], row['domain'])
            if row['digest'] != actual or not hmac.compare_digest(actual, str(review['content_sha256'])):
                raise ValueError('review_content_mismatch')
            db.execute('UPDATE documents SET state=?,expires=?,review=?,reviewer=? WHERE id=?',
                       ('approved', expires.timestamp(), json.dumps(review, ensure_ascii=False), actor, document_id))
            self._event(db, document_id, 'approved', actor)

    def revoke(self, document_id, *, actor):
        with self.db() as db:
            if not db.execute('SELECT id FROM documents WHERE id=?', (document_id,)).fetchone():
                raise ValueError('document_not_found')
            db.execute("UPDATE documents SET state='revoked' WHERE id=?", (document_id,))
            self._event(db, document_id, 'revoked', actor)

    def approved(self, domain):
        with self.db() as db:
            rows = db.execute("SELECT * FROM documents WHERE state='approved' AND expires>? AND domain=? ORDER BY created DESC", (time.time(), domain)).fetchall()
        return [dict(row) for row in rows if row['digest'] == document_digest(row['title'], row['content'], row['source_url'], row['domain']) and trusted_medical_url(row['source_url'])]

    def capture_gap(self, *, question, domain, intent, reason):
        if domain not in {'clinical', 'pharmacology'} or intent not in {'triage', 'safety', 'general', 'pharmacy', 'monitoring', 'followup'} or reason not in {'no_local_evidence', 'no_matching_guidance', 'provider_unavailable'}:
            raise ValueError('invalid_gap_category')
        with self.db() as db:
            key = bytes.fromhex(db.execute("SELECT value FROM pool_meta WHERE key='gap_hmac_key'").fetchone()['value'])
            # Never persist the question, clinical details, answer or identity.
            fingerprint = hmac.new(key, (domain + '|' + intent + '|' + reason + '|' + ' '.join(question.lower().split())).encode(), 'sha256').hexdigest()
            now = time.time()
            db.execute('INSERT INTO gaps VALUES(?,?,?,?,1,?,?) ON CONFLICT(fingerprint) DO UPDATE SET occurrences=occurrences+1,last_seen=excluded.last_seen',
                       (fingerprint, domain, intent, reason, now, now))
            db.execute('DELETE FROM gaps WHERE fingerprint IN (SELECT fingerprint FROM gaps ORDER BY last_seen DESC LIMIT -1 OFFSET 10000)')

    def inventory(self):
        with self.db() as db:
            documents = [dict(row) for row in db.execute('SELECT id,title,source_url,domain,digest,state,created,expires,review FROM documents ORDER BY created DESC')]
            gaps = [dict(row) for row in db.execute('SELECT * FROM gaps ORDER BY last_seen DESC LIMIT 200')]
        return {'documents': documents, 'gaps': gaps, 'automatic_promotion': False, 'training_eligible': False}


@lru_cache(maxsize=4)
def _pool(path):
    return KnowledgePool(path)


def get_knowledge_pool():
    return _pool(os.getenv('MEDGUARD_KNOWLEDGE_POOL_DATABASE', '.runtime/knowledge_pool.sqlite3'))


def approved_pool_documents(domain):
    try:
        return get_knowledge_pool().approved(domain)
    except (OSError, sqlite3.Error):
        from app.core.observability import metrics
        metrics.inc_counter('medguard_knowledge_pool_read_failures_total', 1.0)
        return []


def capture_knowledge_gap(**kwargs):
    try:
        get_knowledge_pool().capture_gap(**kwargs)
    except (OSError, sqlite3.Error):
        from app.core.observability import metrics
        metrics.inc_counter('medguard_knowledge_pool_capture_failures_total', 1.0)


def stage_verified_public_evidence(evidences, domain):
    """Save fetched public source text, never model prose or user questions."""
    from urllib.parse import urlsplit
    for evidence in evidences[:2]:
        try:
            if not trusted_medical_url(evidence.url) or len(evidence.content.strip()) < 40:
                continue
            source = urlsplit(evidence.url)
            get_knowledge_pool().stage(
                title=(source.hostname + ' · ' + source.path)[:180],
                content=evidence.content[:12000], source_url=evidence.url,
                domain=domain, actor='verified_runtime_public_source',
            )
        except (OSError, sqlite3.Error, ValueError):
            from app.core.observability import metrics
            metrics.inc_counter('medguard_knowledge_pool_capture_failures_total', 1.0)
