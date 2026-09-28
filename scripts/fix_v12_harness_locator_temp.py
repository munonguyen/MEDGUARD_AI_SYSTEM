from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/apply_agent_first_v12_temp.py"
text = path.read_text(encoding="utf-8")
old = '''replace_once(
    "app/services/agent_graph.py",
    ''' + "'''" + '''            "domain_claims": state.claims,\\n            "retrieved_contexts": rag_contexts,\\n''' + "'''" + ''',
    ''' + "'''" + '''            "domain_claims": state.claims,\\n            "clinical_envelope": state.tool_result,\\n            "retrieved_contexts": rag_contexts,\\n''' + "'''" + ''',
)
'''
new = '''graph_path = "app/services/agent_graph.py"
graph_text = read(graph_path)
graph_old = ''' + "'''" + '''            "domain_claims": state.claims,\\n            "retrieved_contexts": rag_contexts,\\n''' + "'''" + '''
if graph_text.count(graph_old) != 2:
    raise RuntimeError(f"agent_graph: expected two domain_claim blocks, found {graph_text.count(graph_old)}")
graph_text = graph_text.replace(
    graph_old,
    ''' + "'''" + '''            "domain_claims": state.claims,\\n            "clinical_envelope": state.tool_result,\\n            "retrieved_contexts": rag_contexts,\\n''' + "'''" + ''',
    1,
)
write(graph_path, graph_text)
'''
if old not in text:
    raise SystemExit("locator block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("v12_harness_locator=FIXED")
