"""Ensure the audit cannot improve scores by replacing real output/evidence."""
import json

from scripts.audit_v28_output_quality import display_projection, summarize, render_report


def test_display_projection_preserves_ui_limits_and_keeps_hidden_narrative_separate():
    body = {"answer": {"title": "Title", "summary": "Actual displayed summary",
        "key_points": [str(i) for i in range(8)],
        "questions": ["Q1?", "Q2?", "Q3?"], "display_questions": ["Selected?"],
        "narrative": [{"text": "A nicer hidden answer"}, {"text": "Bạn cho mình biết thêm: legacy question"}]},
        "reply": "Reply fallback"}
    shown = display_projection(body)
    assert "Actual displayed summary" in shown["text"]
    assert "A nicer hidden answer" not in shown["text"]
    assert shown["narrative"] == ["A nicer hidden answer"]
    assert shown["questions"] == ["Selected?"]
    assert shown["sections"]["Dữ kiện chính"] == ["0", "1", "2", "3", "4"]


def test_strict_failure_cannot_be_compensated_by_high_average():
    report = summarize([{"case_id": "x", "strict_failures": ["URGENCY_MISMATCH:ROUTINE->EMERGENCY"],
        "rubric": {"total_score": 14}}])
    assert report["rubric_average"] == 14
    assert report["software_output_gate"] == "FAIL"
    assert report["superiority_proven"] is False
    assert report["push_recommended"] is False
    assert report["external_paired_benchmark"] == "NOT_RUN"


def test_empty_audit_is_not_a_pass():
    assert summarize([])["software_output_gate"] == "FAIL"


def test_html_escapes_original_answer_and_preserves_downloadable_json():
    raw = {"answer": {"summary": "</script><script>alert(1)</script>"}}
    result = {"case_id": "x", "question": "<question>", "expected": {}, "http_status": 200,
        "latency_ms": 1, "strict_failures": ["MISSING_ACTION"], "raw_response": raw,
        "display": {"text": raw["answer"]["summary"], "narrative": []}}
    report = {"generated_at": "test", "provenance": {"commit": "abc"}, "references": [],
        "summary": summarize([result]), "results": [result]}
    page = render_report(report)
    assert "</script><script>alert(1)</script>" not in page
    embedded = page.split('<script type="application/json" id="report-data">')[1].split('</script>')[0]
    assert json.loads(embedded)["results"][0]["raw_response"] == raw
