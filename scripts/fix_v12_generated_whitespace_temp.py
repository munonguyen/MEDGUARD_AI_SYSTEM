from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = (
    "app/core/config.py",
    "app/services/clinical_agent_contract.py",
    "app/services/answer_agents.py",
    "app/services/agent_graph.py",
    "app/services/chat.py",
    "app/services/output_quality_verifier.py",
    "app/tests/test_agent_first_clinical_v12.py",
    "app/tests/test_output_quality_governance.py",
)
for rel in PATHS:
    path = ROOT / rel
    if not path.exists():
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")
print("v12_generated_whitespace=NORMALIZED")
