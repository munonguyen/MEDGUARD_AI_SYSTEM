"""Unit Tests for Phase 4B: Hybrid Retrieval (BM25, Vector, Graph, Fusion, Reranker)."""

import pytest
from app.knowledge.ingestion.version_manager import VersionManager
from app.knowledge.retrieval.bm25_retriever import BM25Retriever
from app.knowledge.retrieval.vector_retriever import VectorRetriever
from app.knowledge.retrieval.graph_retriever import GraphRetriever
from app.knowledge.retrieval.fusion import reciprocal_rank_fusion
from app.knowledge.retrieval.reranker import MultiFactorClinicalReranker
from app.services.retrieval_planner import RetrievalPlanner
from app.services.context_budget_manager import ContextBudgetManager


def test_bm25_retriever_scores_exact_drug_and_codes():
    vm = VersionManager.create_default()
    snapshot = vm.get_snapshot()

    bm25 = BM25Retriever()
    bm25.index_snapshot(snapshot)

    results = bm25.search("Warfarin Ibuprofen xuất huyết", top_k=3)
    assert len(results) >= 1
    top_ev, score = results[0]
    assert "Warfarin" in top_ev.statement
    assert score > 0.0


def test_vector_retriever_matches_fuzzy_colloquial_symptoms():
    vm = VersionManager.create_default()
    snapshot = vm.get_snapshot()

    vec = VectorRetriever()
    vec.index_snapshot(snapshot)

    # Fuzzy patient phrasing for calf muscle fatigue
    results = vec.search("chân nó cứ ê ẩm mỏi mỏi sau khi chạy bộ", top_k=3)
    assert len(results) >= 1
    top_ev, score = results[0]
    assert top_ev.concept in ("muscle_strain_self_care", "dvt_unilateral_swelling")
    assert score > 0.0


def test_graph_retriever_extracts_hard_drug_interactions():
    vm = VersionManager.create_default()
    snapshot = vm.get_snapshot()

    gr = GraphRetriever()
    gr.set_snapshot(snapshot)

    results = gr.search("Uống thuốc chống đông warfarin chung với ibuprofen có sao không?", top_k=3)
    assert len(results) >= 1
    top_ev, score = results[0]
    assert top_ev.evidence_id == "EV_DRUG_WARFARIN_IBUPROFEN"
    assert score >= 0.85


def test_rrf_fusion_merges_multiple_retrieval_runs():
    vm = VersionManager.create_default()
    snapshot = vm.get_snapshot()

    bm25 = BM25Retriever()
    bm25.index_snapshot(snapshot)
    run1 = bm25.search("đau thắt ngực đè nặng lan tay trái khó thở 115", top_k=5)

    vec = VectorRetriever()
    vec.index_snapshot(snapshot)
    run2 = vec.search("đau thắt ngực đè nặng lan tay trái khó thở 115", top_k=5)

    fused = reciprocal_rank_fusion([run1, run2], k=60, top_n=5)
    assert len(fused) >= 1
    top_ev, fused_score = fused[0]
    assert top_ev.concept == "cardiac_emergency_acs"
    assert fused_score > 0.0


def test_multifactor_reranker_boosts_emergency_and_domestic_authority():
    vm = VersionManager.create_default()
    snapshot = vm.get_snapshot()

    bm25 = BM25Retriever()
    bm25.index_snapshot(snapshot)
    candidates = bm25.search("đau ngực cấp cứu", top_k=5)

    reranker = MultiFactorClinicalReranker()
    reranked = reranker.rerank(candidates, query="Bệnh nhân khó thở đau ngực cần cấp cứu 115")

    assert len(reranked) >= 1
    top_ev, score = reranked[0]
    assert top_ev.evidence_type == "emergency_protocol"
    assert score > 0.70


def test_retrieval_planner_selects_engines_adaptively():
    planner = RetrievalPlanner()

    # Drug interaction query -> activates Graph
    drug_plan = planner.plan("Warfarin uống chung với Gofen có bị loét dạ dày không?")
    assert drug_plan.use_graph is True
    assert "drug_monograph" in drug_plan.target_domains

    # Legal regulation query -> activates Legal, disables Graph
    legal_plan = planner.plan("Quy định của Bộ Y tế về điều kiện cấp chứng chỉ hành nghề khám chữa bệnh")
    assert legal_plan.use_legal is True
    assert legal_plan.use_graph is False


def test_context_budget_manager_allocates_dynamically():
    mgr = ContextBudgetManager()

    # Emergency budget prioritizes emergency tokens
    em_budget = mgr.allocate_budget(is_emergency=True, complexity_level="C4")
    assert em_budget.emergency_tokens >= 600
    assert em_budget.legal_tokens == 0

    # Drug heavy budget expands drug allocation
    drug_budget = mgr.allocate_budget(is_drug_heavy=True, complexity_level="C3")
    assert drug_budget.drug_tokens >= 1200
