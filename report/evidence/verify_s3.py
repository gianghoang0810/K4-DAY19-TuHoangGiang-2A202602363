import os
import sys
import unittest
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
load_dotenv()

from src import graph, Document, EmbeddingStore

def verify_all():
    print("=== S3 VERIFICATION SUITE ===")

    # 1. link_entity checks
    print("\n--- 1. Testing link_entity edge cases ---")
    assert graph.link_entity("", ["tội mua bán"]) is None, "Empty name should return None"
    assert graph.link_entity("tội mua bán", []) is None, "Empty known should return None"
    assert graph.link_entity(None, ["tội mua bán"]) is None, "None name should return None"
    # Custom normalizer
    custom_norm = lambda s: s.strip().upper()
    known = ["FOO", "BAR"]
    assert graph.link_entity("foo", known, normalize=custom_norm) == "FOO", "Custom normalizer failed"
    print("[PASS] link_entity handles empty name, empty known, and custom normalizer.")

    # 2. KG-4 checks
    print("\n--- 2. Testing GraphRAGAgent deduplication and components ---")
    store = EmbeddingStore("test_s3_store")
    store.add_documents([
        Document("doc1#0", "Nội dung đoạn 1", {"doc_id": "news-dup"}),
        Document("doc1#1", "Nội dung đoạn 2", {"doc_id": "news-dup"}),
    ])
    captured = {}
    class MockGraph:
        def context(self, q, doc_ids):
            captured['doc_ids'] = doc_ids
            return ["Dữ kiện graph số 1"]

    mock_g = MockGraph()
    agent = graph.GraphRAGAgent(store=store, graph=mock_g, llm_fn=lambda p: p)
    res_prompt = agent.answer("Câu hỏi test?", top_k=2)
    assert captured['doc_ids'] == ["news-dup"], f"Doc IDs should be deduplicated: {captured['doc_ids']}"
    assert "Dữ kiện graph số 1" in res_prompt, "Prompt must contain graph facts"
    assert "Nội dung đoạn 1" in res_prompt, "Prompt must contain chunk 1"
    assert "Câu hỏi test?" in res_prompt, "Prompt must contain question"
    print("[PASS] GraphRAGAgent deduplicates doc_ids and properly formats prompt.")

    # 3. Neo4j connectivity & read-only safety
    print("\n--- 3. Testing Neo4j queries and read-only safety ---")
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    pwd = os.getenv('NEO4J_PASSWORD', 'password123')
    g = graph.Neo4jGraph(uri, user, pwd)

    nodes_before = g.stats()["nodes"]
    rels_before = g.stats()["relationships"]

    # Empty retrieval
    empty_f1 = g.context("", [])
    assert empty_f1 == [] or isinstance(empty_f1, list), "Empty retrieval should return list"
    empty_f2 = g.context("câu hỏi kỳ lạ hoàn toàn không có gì trong graph xyz123?", [])
    assert isinstance(empty_f2, list), "Unmatched retrieval should return list"
    assert g.context("Bất kỳ câu hỏi nào", [], max_facts=0) == [], "max_facts=0 must return []"
    print("[PASS] Empty / unknown retrieval returns list without error, max_facts=0 returns [].")

    # S2.1 check
    print("\n--- 4. Testing S2.1: Luật PCMT retrieval ---")
    f_pcmt = g.context("Điều 2 Luật PCMT quy định tiền chất là gì?", [])
    has_pcmt_clause4 = any("tiền chất" in f.lower() and "khoản 4" in f.lower() for f in f_pcmt)
    assert has_pcmt_clause4, f"Failed to retrieve Điều 2 Luật PCMT khoản 4: {f_pcmt}"
    print("[PASS] S2.1: Điều 2 Luật PCMT khoản 4 retrieved correctly without BLHS assumption.")

    # S2.2 check
    print("\n--- 5. Testing S2.2: Generic name 'ma túy' does not expand graph ---")
    f_q1 = g.context("Theo Luật Phòng, chống ma túy 2021, tiền chất là gì?", ["pcmt-dieu-2"])
    has_unrelated_case = any("Vụ việc" in f for f in f_q1)
    assert not has_unrelated_case, f"Q1 must not expand to unrelated cases via 'ma túy': {f_q1}"
    print("[PASS] S2.2: Generic name 'ma túy' does not trigger unrelated Case expansion.")

    # S2.3 check
    print("\n--- 6. Testing S2.3: MDMA Aggregation ---")
    direct_cases = g.run("MATCH (k:Case)-[:INVOLVES]->(s:Substance {name: 'MDMA'}) RETURN k.name AS name, k.doc_id AS doc_id ORDER BY k.doc_id, k.name")
    f_agg = g.context("Những vụ việc nào trong tin tức có liên quan đến ma túy MDMA?", [])
    for dc in direct_cases:
        matched = any(dc['doc_id'] in f or dc['name'] in f for f in f_agg)
        assert matched, f"Aggregation missed case {dc['name']} ({dc['doc_id']})"
    print(f"[PASS] S2.3: Aggregation correctly retrieved all {len(direct_cases)} Cases involving MDMA.")

    # S2.4 check
    print("\n--- 7. Testing S2.4: Priority ranking with max_facts=5 ---")
    f_q3 = g.context("Lê Minh Thành bị tuyên bao nhiêu tháng tù, về tội gì, và tội đó được quy định tại điều nào của Bộ luật Hình sự với khung hình phạt cơ bản bao nhiêu?", ["news-100260918080821054"], max_facts=5)
    assert len(f_q3) <= 5, f"Exceeded max_facts: {len(f_q3)}"
    has_251_k1 = any("251" in f and "khoản 1" in f for f in f_q3)
    has_36m = any("36 tháng" in f for f in f_q3)
    assert has_251_k1, f"Q3 max_facts=5 missing Điều 251 khoản 1: {f_q3}"
    assert has_36m, f"Q3 max_facts=5 missing 36 tháng: {f_q3}"
    print("[PASS] S2.4: Q3 with max_facts=5 retains both Điều 251 khoản 1 and 36 tháng sentence.")

    # S2.5 check
    print("\n--- 8. Testing S2.5: Maximum frame for Q4 ---")
    f_q4 = g.context("Giang hồ 'Hoàng Nato' bị bắt về hành vi gì, và hành vi đó có thể bị phạt tù tối đa bao nhiêu theo Bộ luật Hình sự?", [])
    has_255_max = any("255" in f and ("chung thân" in f or "khoản 4" in f) for f in f_q4)
    assert has_255_max, f"Q4 missing Điều 255 max clause: {f_q4}"
    print("[PASS] S2.5: Q4 correctly retrieves Điều 255 maximum clause.")

    # Verify no nodes/edges were created or deleted by context queries
    nodes_after = g.stats()["nodes"]
    rels_after = g.stats()["relationships"]
    assert nodes_before == nodes_after, f"Node count changed! {nodes_before} -> {nodes_after}"
    assert rels_before == rels_after, f"Rel count changed! {rels_before} -> {rels_after}"
    print(f"[PASS] Read-only integrity verified: graph nodes ({nodes_after}) and relationships ({rels_after}) unchanged.")

    g.close()
    print("\n=== ALL S3 VERIFICATIONS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    verify_all()
