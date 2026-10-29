"""Non-secret configuration diagnostics; not a claim of upstream availability."""
from app.core.config import settings


def companion_status():
    key = settings.llm_gateway_api_key or ''
    configured = bool(settings.llm_gateway_url and key and not key.startswith(('replace-', '<')))
    return {
        'configured': configured,
        'mode': settings.agent_mode,
        'synchronous': settings.agent_sync_enabled,
        'background': settings.agent_background_enabled,
        'chat_timeout_ms': min(45000, max(15000, settings.agent_total_timeout_seconds * 1000 + 10000)),
        'background_wait_ms': min(300000, settings.agent_background_total_timeout_seconds * 1000 + 10000),
        'revision': 'doctor-chat-20261008',
        'message': ('Đã có cấu hình AI gateway. Khả năng trả lời phụ thuộc kết nối và bước kiểm tra nội dung.'
                    if configured else 'Chưa cấu hình AI gateway. Chạy python3 scripts/configure_doctor_chat.py trên máy chủ để cấu hình.'),
    }
