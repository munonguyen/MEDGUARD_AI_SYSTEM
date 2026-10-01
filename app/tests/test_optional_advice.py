import pytest
from app.models.chat import GroundedAnswer
from app.services.optional_advice import attach_optional_advice


def answer():
    return GroundedAnswer(title='Title',summary='Summary',decision_basis='versioned_rules',evidence_state='direct_rule_match', next_steps=['Mandatory'], safety_notes=['Safety'])


@pytest.mark.parametrize('urgency', ['EMERGENCY','URGENT','UNKNOWN','CRITICAL'])
def test_no_optional_advice_on_escalation(urgency):
    original = answer()
    result = attach_optional_advice(original, {'self_care':['Nghỉ ngơi ở nơi thoáng mát.']}, urgency)
    assert result.optional_advice == []
    assert result.next_steps == original.next_steps and result.safety_notes == original.safety_notes


def test_only_existing_bounded_routine_self_care_and_no_treatment():
    values = ['Nghỉ ngơi ở nơi thoáng mát.', 'Nghỉ ngơi ở nơi thoáng mát.', 'Uống thuốc 500mg.', 'Không tự dùng kháng sinh.', 'Đi khám bác sĩ ngay.']
    result = attach_optional_advice(answer(), {'self_care':values}, 'ROUTINE')
    assert result.optional_advice == [values[0]]
    assert attach_optional_advice(answer(), {'self_care':values, 'emergency_flag':True}, 'ROUTINE').optional_advice == []
