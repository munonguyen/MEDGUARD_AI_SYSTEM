"""Tenant-scoped durable chat history without clinical content in audit metadata."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.core.database import DatabaseManager, db_manager
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationSummary,
    GroundedAnswer,
    StoredChatMessage,
)
from app.services.patient_response_surface import canonical_patient_response_text


class ChatHistoryStore:
    def __init__(self, database: DatabaseManager = db_manager) -> None:
        self.database = database
        self._lock = RLock()

    def append_exchange(self, tenant_id: str, payload: ChatRequest, response: ChatResponse) -> None:
        now = datetime.now(timezone.utc).isoformat()
        latest = (
            payload.original_latest_content
            if payload.original_latest_content is not None
            else payload.messages[-1].content
        ).strip()
        title = " ".join(latest.split())[:80] or "Cuộc trò chuyện mới"
        patient_ref = payload.context.patient_ref or response.extracted.get("patient_ref")
        assistant_content = canonical_patient_response_text(
            answer=response.answer,
            verification_status=response.verification_status,
            fallback_text=response.reply,
        )
        with self._lock, self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                INSERT INTO chat_conversations (
                    tenant_id, conversation_id, title, patient_ref, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, conversation_id) DO UPDATE SET
                    patient_ref = COALESCE(excluded.patient_ref, chat_conversations.patient_ref),
                    updated_at = excluded.updated_at
                """,
                (tenant_id, payload.conversation_id, title, patient_ref, now, now),
            )
            session.execute(
                """
                INSERT INTO chat_messages (
                    message_id, request_id, tenant_id, conversation_id, role, content,
                    intent, status, result_json, answer_json, created_at
                ) VALUES (?, ?, ?, ?, 'user', ?, NULL, NULL, NULL, NULL, ?)
                """,
                (str(uuid4()), response.request_id, tenant_id, payload.conversation_id, latest, now),
            )
            session.execute(
                """
                INSERT INTO chat_messages (
                    message_id, request_id, tenant_id, conversation_id, role, content,
                    intent, status, result_json, answer_json, answer_origin,
                    verification_status, knowledge_approval, created_at
                ) VALUES (?, ?, ?, ?, 'assistant', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    response.request_id,
                    tenant_id,
                    payload.conversation_id,
                    assistant_content,
                    response.intent,
                    response.status,
                    json.dumps(response.result, ensure_ascii=False) if response.result is not None else None,
                    json.dumps(response.answer.model_dump(mode="json"), ensure_ascii=False) if response.answer else None,
                    response.answer_origin,
                    response.verification_status,
                    response.knowledge_approval,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list(self, tenant_id: str, limit: int = 50) -> list[ConversationSummary]:
        with self._lock, self.database.tenant_context(tenant_id) as session:
            rows = session.execute(
                """
                SELECT c.conversation_id, c.title, c.patient_ref,
                       c.created_at, c.updated_at, COUNT(m.message_id) AS message_count
                FROM chat_conversations c
                LEFT JOIN chat_messages m
                  ON m.tenant_id = c.tenant_id
                 AND m.conversation_id = c.conversation_id
                WHERE c.tenant_id = ?
                GROUP BY c.conversation_id, c.title, c.patient_ref, c.created_at, c.updated_at
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            )
        return [ConversationSummary.model_validate(row) for row in rows]

    def get(self, tenant_id: str, conversation_id: str) -> ConversationHistoryResponse | None:
        with self._lock, self.database.tenant_context(tenant_id) as session:
            conversations = session.execute(
                """
                SELECT c.conversation_id, c.title, c.patient_ref,
                       c.created_at, c.updated_at, COUNT(m.message_id) AS message_count
                FROM chat_conversations c
                LEFT JOIN chat_messages m
                  ON m.tenant_id = c.tenant_id
                 AND m.conversation_id = c.conversation_id
                WHERE c.tenant_id = ? AND c.conversation_id = ?
                GROUP BY c.conversation_id, c.title, c.patient_ref, c.created_at, c.updated_at
                """,
                (tenant_id, conversation_id),
            )
            if not conversations:
                return None
            rows = session.execute(
                """
                SELECT message_id, request_id, role, content, intent, status, result_json, answer_json,
                       answer_origin, verification_status, knowledge_approval, created_at
                FROM chat_messages
                WHERE tenant_id = ? AND conversation_id = ?
                ORDER BY created_at ASC
                """,
                (tenant_id, conversation_id),
            )
        messages = []
        for row in rows:
            raw_result = row.pop("result_json")
            raw_answer = row.pop("answer_json")
            row["result"] = raw_result if isinstance(raw_result, dict) else json.loads(raw_result) if raw_result else None
            row["answer"] = raw_answer if isinstance(raw_answer, dict) else json.loads(raw_answer) if raw_answer else None
            messages.append(StoredChatMessage.model_validate(row))
        return ConversationHistoryResponse(
            conversation=ConversationSummary.model_validate(conversations[0]),
            messages=messages,
        )

    def update_verification(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        *,
        verification_status: str,
        answer_origin: str,
    ) -> None:
        with self._lock, self.database.tenant_context(tenant_id) as session:
            session.execute(
                """
                UPDATE chat_messages
                SET verification_status = ?, answer_origin = ?
                WHERE tenant_id = ? AND conversation_id = ? AND request_id = ?
                  AND role = 'assistant'
                """,
                (
                    verification_status,
                    answer_origin,
                    tenant_id,
                    conversation_id,
                    request_id,
                ),
            )

    def update_answer_and_verification(
        self,
        tenant_id: str,
        conversation_id: str,
        request_id: str,
        *,
        answer: GroundedAnswer,
        verification_status: str,
        answer_origin: str,
    ) -> None:
        """Atomically promote a verified background answer in chat history.

        When the background gateway promotes an answer to ``verified``, content
        is promoted to the same canonical narrative the frontend displays.  The
        previous content is retained as the fallback for non-verified states.
        """
        with self._lock, self.database.tenant_context(tenant_id) as session:
            existing = session.execute(
                """
                SELECT content
                FROM chat_messages
                WHERE tenant_id = ? AND conversation_id = ? AND request_id = ?
                  AND role = 'assistant'
                LIMIT 1
                """,
                (tenant_id, conversation_id, request_id),
            )
            fallback_text = str(existing[0].get("content") or "") if existing else ""
            assistant_content = canonical_patient_response_text(
                answer=answer,
                verification_status=verification_status,
                fallback_text=fallback_text,
            )
            session.execute(
                """
                UPDATE chat_messages
                SET content = ?, answer_json = ?, verification_status = ?, answer_origin = ?
                WHERE tenant_id = ? AND conversation_id = ? AND request_id = ?
                  AND role = 'assistant'
                """,
                (
                    assistant_content,
                    json.dumps(answer.model_dump(mode="json"), ensure_ascii=False),
                    verification_status,
                    answer_origin,
                    tenant_id,
                    conversation_id,
                    request_id,
                ),
            )

    def delete(self, tenant_id: str, conversation_id: str) -> bool:
        with self._lock, self.database.tenant_context(tenant_id) as session:
            existing = session.execute(
                "SELECT conversation_id FROM chat_conversations WHERE tenant_id = ? AND conversation_id = ?",
                (tenant_id, conversation_id),
            )
            if not existing:
                return False
            session.execute(
                "DELETE FROM chat_conversations WHERE tenant_id = ? AND conversation_id = ?",
                (tenant_id, conversation_id),
            )
        return True


chat_history_store = ChatHistoryStore()
