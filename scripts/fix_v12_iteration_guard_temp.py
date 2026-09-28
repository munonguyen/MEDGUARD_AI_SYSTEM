from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/apply_agent_first_v12_temp.py"
text = path.read_text(encoding="utf-8")
needle = '''text = text.replace(
    '        default_factory=lambda: _env_int("MEDGUARD_AGENT_MAX_ITERATIONS", 0)\\n',
    '        default_factory=lambda: _env_int("MEDGUARD_AGENT_MAX_ITERATIONS", 1)\\n',
    1,
)
write(config, text)
'''
replacement = '''text = text.replace(
    '        default_factory=lambda: _env_int("MEDGUARD_AGENT_MAX_ITERATIONS", 0)\\n',
    '        default_factory=lambda: _env_int("MEDGUARD_AGENT_MAX_ITERATIONS", 1)\\n',
    1,
)
text = text.replace(
    ''' + '"""' + '''        if self.agent_max_iterations != 0:\\n            raise ValueError(\\n                "MEDGUARD_AGENT_MAX_ITERATIONS must be 0 to preserve the 10-second chat SLO"\\n            )\\n''' + '"""' + ''',
    ''' + '"""' + '''        if self.agent_max_iterations not in {0, 1}:\\n            raise ValueError(\\n                "MEDGUARD_AGENT_MAX_ITERATIONS must be 0 or 1; V12 permits one bounded reviewer revision within the total timeout"\\n            )\\n''' + '"""' + ''',
    1,
)
write(config, text)
'''
if needle not in text:
    raise SystemExit("config patch block not found")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
print("v12_iteration_guard=FIXED")
