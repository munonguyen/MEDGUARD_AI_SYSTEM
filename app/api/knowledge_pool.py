"""Administrative review of public, non-patient knowledge documents."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.core.accounts import check_origin, reject
from app.services.knowledge_pool import get_knowledge_pool

router = APIRouter(prefix='/v1/knowledge-pool', tags=['Knowledge governance'])


def admin(request: Request):
    user = request.app.state.accounts.authenticate(request)
    if user['role'] != 'admin':
        reject('permission_denied', 403)
    if request.method not in {'GET', 'HEAD'}:
        check_origin(request)
    return user


class Candidate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=180)
    content: str = Field(min_length=40, max_length=12000)
    source_url: str = Field(max_length=2000)
    domain: str


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approval_id: str = Field(min_length=1, max_length=128)
    reviewer_id: str = Field(min_length=1, max_length=128)
    source_verified: StrictBool
    clinical_approved: StrictBool
    content_sha256: str = Field(min_length=64, max_length=64)
    reviewed_at: str = Field(max_length=40)
    expires_at: str = Field(max_length=40)


@router.get('')
def inventory(user=Depends(admin)):
    return get_knowledge_pool().inventory()


@router.post('/candidates', status_code=201)
def stage(data: Candidate, user=Depends(admin)):
    try:
        identifier = get_knowledge_pool().stage(**data.model_dump(), actor=user['user_id'])
        return {'document_id': identifier, 'status': 'pending_review'}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.post('/{document_id}/approve')
def approve(document_id: str, data: Review, user=Depends(admin)):
    try:
        get_knowledge_pool().approve(document_id, review=data.model_dump(), actor=user['user_id'])
        return {'document_id': document_id, 'status': 'approved'}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.post('/{document_id}/revoke')
def revoke(document_id: str, user=Depends(admin)):
    try:
        get_knowledge_pool().revoke(document_id, actor=user['user_id'])
        return {'document_id': document_id, 'status': 'revoked'}
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
