from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/apply_agent_first_v12_temp.py"
text = path.read_text(encoding="utf-8")
old = '        and settings.agent_mode in {"shadow", "enforced"}\\n'
new = '        and settings.agent_mode == "enforced"\\n'
if old not in text:
    raise SystemExit("V12 agent-first mode condition not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("v12_shadow_semantics=FIXED")
