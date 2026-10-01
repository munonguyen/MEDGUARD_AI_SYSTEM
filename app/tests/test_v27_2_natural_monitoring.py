from app.services import chat


def _metrics(text: str) -> dict[str, float]:
    return {point.metric: float(point.value) for point in chat._extract_monitoring(text)}


def test_natural_spo2_sentence_is_parsed() -> None:
    values = _metrics("SpO2 của tôi lúc nghỉ là 95%.")
    assert values["spo2"] == 95.0


def test_natural_temperature_sentence_is_parsed() -> None:
    values = _metrics("Nhiệt độ của tôi là 38.1 độ C.")
    assert values["temperature_c"] == 38.1


def test_natural_resting_heart_rate_sentence_is_parsed() -> None:
    values = _metrics("Nhịp tim nghỉ của tôi khoảng 104 lần/phút.")
    assert values["heart_rate"] == 104.0


def test_natural_blood_pressure_sentence_preserves_both_values() -> None:
    values = _metrics("Huyết áp hiện tại của tôi là 150/95 mmHg.")
    assert values["systolic"] == 150.0
    assert values["diastolic"] == 95.0
