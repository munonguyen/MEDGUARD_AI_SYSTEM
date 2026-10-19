from datetime import datetime, timedelta, timezone
import json, sqlite3
import pytest
from app.services.knowledge_pool import KnowledgePool
from app.services.knowledge_retriever import KnowledgeRetriever

CONTENT='Tài liệu thử nghiệm về tình huống mới chưa có trong bộ chủ đề; cần kiểm định độc lập trước khi sử dụng.'


def stage(pool):
    return pool.stage(title='Tình huống zyxnovel', content=CONTENT+' zyxnovel',
                      source_url='https://www.nhs.uk/symptoms/headaches/', domain='clinical', actor='admin-test')


def review(pool, identifier):
    digest=next(d['digest'] for d in pool.inventory()['documents'] if d['id']==identifier)
    return dict(approval_id='SYNTHETIC-UNIT-TEST', reviewer_id='test-reviewer', source_verified=True,
                clinical_approved=True, content_sha256=digest,
                reviewed_at=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),
                expires_at=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat())


def test_pending_candidates_do_not_become_runtime_evidence(tmp_path,monkeypatch):
    path=tmp_path/'pool.sqlite3';monkeypatch.setenv('MEDGUARD_KNOWLEDGE_POOL_DATABASE',str(path))
    pool=KnowledgePool(path);identifier=stage(pool)
    retriever=KnowledgeRetriever()
    assert not retriever.retrieve('zyxnovel',intent='triage')
    pool.approve(identifier,review=review(pool,identifier),actor='admin-test')
    rows=retriever.retrieve('zyxnovel',intent='triage')
    assert rows[0].chunk_id==identifier
    assert rows[0].source_url=='https://www.nhs.uk/symptoms/headaches/'
    assert not retriever.retrieve('zyxnovel',intent='safety')
    pool.revoke(identifier,actor='admin-test')
    assert not retriever.retrieve('zyxnovel',intent='triage')


@pytest.mark.parametrize('field,value', [('content_sha256','0'*64),('source_verified',False),('clinical_approved',False),('reviewer_id','')])
def test_invalid_approvals_are_rejected(tmp_path,field,value):
    pool=KnowledgePool(tmp_path/'pool.sqlite3');identifier=stage(pool)
    data=review(pool,identifier);data[field]=value
    with pytest.raises(ValueError):pool.approve(identifier,review=data,actor='admin-test')
    assert not pool.approved('clinical')


@pytest.mark.parametrize('value', ['true', 'false', 1, 0])
def test_review_flags_require_explicit_booleans(value):
    from app.api.knowledge_pool import Review
    from pydantic import ValidationError
    data = dict(approval_id='TEST', reviewer_id='reviewer', source_verified=value,
                clinical_approved=True, content_sha256='0'*64,
                reviewed_at=datetime.now(timezone.utc).isoformat(),
                expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())
    with pytest.raises(ValidationError):
        Review(**data)


def test_tampered_or_expired_documents_are_not_retrieved(tmp_path):
    pool=KnowledgePool(tmp_path/'pool.sqlite3');identifier=stage(pool)
    pool.approve(identifier,review=review(pool,identifier),actor='admin-test')
    with pool.db() as db:db.execute('UPDATE documents SET content=? WHERE id=?',('Altered after approval',identifier))
    assert not pool.approved('clinical')
    with pool.db() as db:db.execute('UPDATE documents SET content=?,expires=0 WHERE id=?',(CONTENT+' zyxnovel',identifier))
    assert not pool.approved('clinical')


def test_source_allowlist_and_deduplication(tmp_path):
    pool=KnowledgePool(tmp_path/'pool.sqlite3')
    assert stage(pool)==stage(pool)
    with pytest.raises(ValueError):pool.stage(title='Bad',content=CONTENT,source_url='https://nhs.uk.attacker.test/a',domain='clinical',actor='test')
    assert len(pool.inventory()['documents'])==1


def test_gap_capture_is_keyed_deduplicated_and_contains_no_patient_text(tmp_path):
    pool=KnowledgePool(tmp_path/'pool.sqlite3')
    for _ in range(2):pool.capture_gap(question='Tôi Nguyễn Văn PatientSecret 0912345678 đang đau',domain='clinical',intent='triage',reason='no_local_evidence')
    inventory=pool.inventory()
    assert inventory['gaps'][0]['occurrences']==2
    dump=json.dumps(inventory,ensure_ascii=False)
    assert 'PatientSecret' not in dump and '0912345678' not in dump
    assert 'Nguyễn' not in dump
    assert tmp_path.joinpath('pool.sqlite3').stat().st_mode & 0o777 == 0o600


def test_patient_and_anonymous_cannot_access_admin_pool(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    monkeypatch.setenv('MEDGUARD_AUTH_DATABASE',str(tmp_path/'accounts.sqlite3'))
    monkeypatch.setenv('MEDGUARD_KNOWLEDGE_POOL_DATABASE',str(tmp_path/'pool.sqlite3'))
    with TestClient(create_app()) as client:
        assert client.get('/v1/knowledge-pool').status_code==401
        data={'email':'pool-test@example.com','password':'pool test password 123!','consent':True}
        assert client.post('/v1/auth/register',json=data).status_code==201
        login=client.post('/v1/auth/login',json={k:v for k,v in data.items() if k!='consent'}).json()
        assert client.get('/v1/knowledge-pool').status_code==403
        with client.app.state.accounts.db() as db:db.execute("UPDATE users SET role='admin'")
        assert client.get('/v1/knowledge-pool').status_code==200
        doc={'title':'Candidate','content':CONTENT,'source_url':'https://www.nhs.uk/symptoms/headaches/','domain':'clinical'}
        assert client.post('/v1/knowledge-pool/candidates',json=doc).status_code==403
        assert client.post('/v1/knowledge-pool/candidates',json=doc,headers={'X-CSRF-Token':login['csrf_token']}).status_code==201


def test_pool_storage_failure_does_not_break_answer_retrieval(tmp_path,monkeypatch):
    monkeypatch.setenv('MEDGUARD_KNOWLEDGE_POOL_DATABASE',str(tmp_path))
    rows=KnowledgeRetriever().retrieve('warfarin ibuprofen',intent='safety')
    assert rows


def test_verified_source_capture_stays_pending_and_never_copies_model_answer(tmp_path,monkeypatch):
    from app.services.knowledge_pool import get_knowledge_pool,stage_verified_public_evidence
    from app.services.trusted_evidence import RuntimeEvidence
    monkeypatch.setenv('MEDGUARD_KNOWLEDGE_POOL_DATABASE',str(tmp_path/'pool.sqlite3'))
    evidence=RuntimeEvidence(requested_url='https://www.nhs.uk/symptoms/headaches/',url='https://www.nhs.uk/symptoms/headaches/',content=CONTENT,content_type='text/html')
    stage_verified_public_evidence([evidence],'clinical')
    pool=get_knowledge_pool()
    assert pool.inventory()['documents'][0]['state']=='pending_review'
    assert not pool.approved('clinical')
