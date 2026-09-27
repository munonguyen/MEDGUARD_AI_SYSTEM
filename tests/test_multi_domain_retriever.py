"""Unit tests for Multi-Domain Retriever and Evidence Packet Composer."""

import pytest
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.multi_domain_retriever import MultiDomainRetriever


def test_multi_domain_retriever_and_xml_packet_composition():
    query = (
        "bác ơi mấy hôm nay chân bên trái đoạn dưới đầu gối nó cứ căng căng sáng ngủ dậy thấy hơn "
        "nhưng đi lại thì vẫn được hôm kia có chạy bộ cũng hơi nhiều mà em thấy trên mạng nói cục máu đông "
        "nên hơi sợ không biết có nguy hiểm ko với em đang uống thuốc dị ứng cetri nữa"
    )

    intake = ClinicalIntakeCompiler.compile(query)
    packet = MultiDomainRetriever.retrieve_and_compose_packet(intake, max_evidence_budget=6)

    # 1. Check budget enforcement
    assert packet.total_chunks <= 6
    assert packet.total_chunks >= 1

    # 2. Check latency
    assert packet.retrieval_latency_ms < 500.0  # Runs in-memory, very fast

    # 3. Check XML packet tags
    xml = packet.xml_formatted_prompt
    assert "<clinical_case>" in xml
    assert "<patient_profile>" in xml
    assert "<patient_timeline>" in xml
    assert "<verified_evidence_packet>" in xml
    assert "<safety_constraints>" in xml
    assert "<task>" in xml

    # 4. Check that raw query and patient fears are appropriately encoded in XML
    assert "cục máu đông" in xml.lower() or "dvt" in xml.lower()
    assert "bắp chân trái" in xml or "left_calf" in xml
