from scripts.benchmark_chat_hard import run_chat_hard_benchmark


def test_hard_user_chat_dataset_passes_every_development_invariant():
    report = run_chat_hard_benchmark()

    assert report["production_evaluable"] is False
    assert report["total"] == 21
    assert report["failed"] == 0
    assert report["gate_passed"] is True
