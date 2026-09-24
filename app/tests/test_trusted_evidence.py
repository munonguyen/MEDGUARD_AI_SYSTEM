from app.services.trusted_evidence import _VisibleTextParser, trusted_medical_url


def test_runtime_evidence_allowlist_rejects_spoofing_and_non_https():
    assert trusted_medical_url("https://www.who.int/news-room/fact-sheets")
    assert trusted_medical_url("https://www.nice.org.uk/guidance/cg150")
    assert not trusted_medical_url("http://www.who.int/news-room/fact-sheets")
    assert not trusted_medical_url("https://who.int.attacker.example/guidance")
    assert not trusted_medical_url("https://user@who.int/guidance")


def test_runtime_evidence_parser_ignores_active_content():
    parser = _VisibleTextParser()
    parser.feed(
        "<html><body><h1>Clinical guidance</h1>"
        "<script>stealPatientData()</script><p>Seek urgent care.</p></body></html>"
    )

    assert "Clinical guidance" in parser.parts
    assert "Seek urgent care." in parser.parts
    assert all("stealPatientData" not in part for part in parser.parts)
