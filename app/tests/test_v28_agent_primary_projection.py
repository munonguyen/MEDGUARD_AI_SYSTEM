"""Presentation contract tests, not evidence of a live model/provider call."""
from scripts.audit_v28_output_quality import display_projection


def test_verified_agent_primary_excludes_legacy_template_from_display():
    body = {'intent': 'triage', 'verification_status': 'verified',
            'answer_origin': 'gateway_verified', 'result': {'urgency': 'ROUTINE'},
            'answer': {'title': 'Đánh giá', 'summary': 'LEGACY SUMMARY',
                       'next_steps': ['LEGACY ACTION'], 'clinical_hypotheses': ['LEGACY DIAGNOSIS'],
                       'narrative': [{'text': 'Agent đã phân tích bối cảnh và đưa ra hướng xử trí.'},
                                     {'text': 'Bạn cho mình biết thêm vị trí đau?'}]}}
    shown = display_projection(body)
    assert 'Agent đã phân tích' in shown['text']
    assert 'Bạn cho mình biết thêm vị trí đau?' in shown['text']
    assert 'LEGACY' not in shown['text']


def test_unavailable_agent_is_not_presented_as_verified():
    shown = display_projection({'intent': 'triage', 'verification_status': 'unavailable',
        'answer_origin': 'deterministic_fallback', 'answer': {'title': 'Dự phòng', 'summary': 'Thông tin giới hạn'}})
    assert 'Chưa hoàn tất thẩm định' in shown['text']
    assert 'hướng dẫn dự phòng' in shown['text']
