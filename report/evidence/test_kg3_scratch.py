import re
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
user = os.getenv('NEO4J_USER', 'neo4j')
pwd = os.getenv('NEO4J_PASSWORD', 'password123')

driver = GraphDatabase.driver(uri, auth=(user, pwd))

def run_cypher(cypher, **params):
    records, _, _ = driver.execute_query(cypher, params)
    return [r.data() for r in records]

SUBSTANCES = ["Heroine", "Cocaine", "Methamphetamine", "Amphetamine", "MDMA", "XLR-11", "Ketamine",
              "cần sa", "thuốc phiện", "côca"]
GENERIC_NAMES = ['ma túy', 'chất ma túy', 'ma túy tổng hợp', 'ma túy đá', 'tiền chất',
                 'chất gây nghiện', 'chất hướng thần']

def find_substances(text: str) -> list[str]:
    lowered = text.lower()
    return [name for name in SUBSTANCES if name.lower() in lowered]

def seed_facts(question: str, doc_ids: list[str], limit: int = 60):
    seeds = run_cypher(
        """
        MATCH (n)
        WHERE n.doc_id IN $doc_ids
           OR (n.name IS :: STRING AND size(n.name) >= 3 AND NOT toLower(n.name) IN $generic_names AND toLower($q) CONTAINS toLower(n.name))
           OR any(a IN coalesce(n.aliases, []) WHERE size(a) >= 3 AND NOT toLower(a) IN $generic_names AND toLower($q) CONTAINS toLower(a))
        RETURN elementId(n) AS id
        """,
        q=question, doc_ids=doc_ids, generic_names=GENERIC_NAMES
    )
    seed_ids = [row["id"] for row in seeds]
    edges = run_cypher(
        """
        MATCH (s)-[r]-(m)
        WHERE elementId(s) IN $ids
        WITH DISTINCT r LIMIT $limit
        WITH startNode(r) AS a, r, endNode(r) AS b
        RETURN labels(a)[0] AS a_label, coalesce(a.name, a.id) AS a_name, type(r) AS rel,
               properties(r) AS props, labels(b)[0] AS b_label, coalesce(b.name, b.id) AS b_name
        """,
        ids=seed_ids, limit=limit,
    )
    facts = []
    for e in edges:
        props = ", ".join(f"{k}: {v}" for k, v in e["props"].items() if v)
        facts.append(f"({e['a_label']}: {e['a_name']}) -[{e['rel']}{' {' + props + '}' if props else ''}]-> "
                     f"({e['b_label']}: {e['b_name']})")
    return seed_ids, facts

def test_context(question: str, doc_ids: list[str], max_facts: int = 60):
    if max_facts <= 0:
        return []

    bucket_clauses = []
    bucket_person_case = []
    bucket_cases = []
    bucket_seeds = []
    bucket_aggregation = []

    is_max_asked = bool(re.search(r"tối đa|cao nhất|khung cao", question, re.IGNORECASE))
    is_aggregation = bool(re.search(r"những vụ|các vụ|vụ việc nào|vụ án nào|danh sách vụ", question, re.IGNORECASE))
    q_substances = find_substances(question)

    # Aggregation branch
    if is_aggregation and q_substances:
        rows = run_cypher(
            """
            MATCH (k:Case)-[r:INVOLVES]->(s:Substance)
            WHERE toLower(s.name) IN [sub IN $substances | toLower(sub)]
            OPTIONAL MATCH (p:Person)-[pin:INVOLVED_IN]->(k)
            WITH k, r, s, collect(DISTINCT p.name + CASE WHEN pin.role IS NOT NULL AND pin.role <> '' THEN ' (' + pin.role + ')' ELSE '' END) AS people
            RETURN k.name AS name, k.summary AS summary, k.doc_id AS doc_id, r.amount AS amount, s.name AS substance, people
            ORDER BY k.doc_id, k.name
            """,
            substances=q_substances
        )
        for r in rows:
            p_str = f" [Người liên quan: {', '.join(r['people'])}]" if r['people'] else ""
            amt_str = f", khối lượng: {r['amount']}" if r['amount'] else ""
            bucket_aggregation.append(f"Vụ việc '{r['name']}' (doc_id: {r['doc_id']}): {r['summary']} [Chất: {r['substance']}{amt_str}]{p_str}")

    # Person-Case facts: prioritize persons whose name appears in question
    seed_ids, seed_fact_list = seed_facts(question, doc_ids, limit=30)
    for sf in seed_fact_list:
        if "INVOLVED_IN" in sf and ("sentence" in sf or "charge" in sf):
            # Prioritize target person mentioned in question
            if any(w in question for w in re.findall(r"Person:\s*([^)]+)", sf)):
                bucket_person_case.insert(0, sf)
            else:
                bucket_person_case.append(sf)
        else:
            bucket_seeds.append(sf)

    # Reached cases
    case_rows = run_cypher(
        """
        MATCH (k:Case)
        WHERE elementId(k) IN $ids OR EXISTS { MATCH (s)--(k) WHERE elementId(s) IN $ids }
        RETURN DISTINCT elementId(k) AS id, k.name AS name, k.summary AS summary
        """,
        ids=seed_ids,
    )
    case_ids = [row["id"] for row in case_rows]
    for row in case_rows:
        name, summary = row.get("name"), row.get("summary")
        if name and summary:
            bucket_cases.append(f"Vụ việc '{name}': {summary}")

    # Follow case charges to clauses
    if case_ids:
        clause_rows = run_cypher(
            """
            MATCH (k:Case)-[:CHARGED_WITH]->(:Crime)<-[:DEFINES]-(a:Article)-[:HAS_CLAUSE]->(cl:Clause)
            WHERE elementId(k) IN $case_ids
              AND (
                cl.number = 1
                OR EXISTS { MATCH (k)-[:INVOLVES]->(sub:Substance)<-[:MENTIONS]-(cl) }
                OR ($is_max = true AND (
                    cl.text CONTAINS 'tử hình'
                    OR cl.text CONTAINS 'chung thân'
                    OR ((cl.penalty CONTAINS 'tù' OR cl.penalty CONTAINS 'tử hình' OR cl.penalty CONTAINS 'chung thân')
                        AND NOT EXISTS {
                            MATCH (a)-[:HAS_CLAUSE]->(cl2:Clause)
                            WHERE (cl2.penalty CONTAINS 'tù' OR cl2.penalty CONTAINS 'tử hình' OR cl2.penalty CONTAINS 'chung thân')
                              AND cl2.number > cl.number
                        })
                ))
              )
            RETURN DISTINCT a.id AS article_id, a.title AS title, cl.number AS number, cl.text AS text
            ORDER BY a.id, cl.number
            """,
            case_ids=case_ids, is_max=is_max_asked
        )
        for row in clause_rows:
            bucket_clauses.append(f"[{row['article_id']} - {row['title']}] khoản {row['number']}: {row['text']}")

    # Direct articles from question or doc_ids
    target_law = None
    ql = question.lower()
    if "pcmt" in ql or "phòng, chống ma túy" in ql or "phòng chống ma túy" in ql:
        target_law = "Luật PCMT"
    elif "blhs" in ql or "hình sự" in ql or "bộ luật hình sự" in ql:
        target_law = "BLHS"

    article_matches = re.findall(r"[Đđ]iều\s*(\d+)", question)
    law_doc_ids = [d for d in doc_ids if d.startswith("pcmt-") or d.startswith("blhs-")]

    # Match target articles
    matched_articles = []
    if article_matches:
        for num in article_matches:
            arts = run_cypher(
                """
                MATCH (a:Article)
                WHERE a.id CONTAINS ('Điều ' + $num + ' ') OR a.id = ('Điều ' + $num)
                   OR a.id CONTAINS ('Điều ' + $num + '.')
                RETURN a.id AS id, a.title AS title, a.law AS law, a.doc_id AS doc_id
                """,
                num=num
            )
            for a in arts:
                if target_law and a["law"] != target_law and target_law not in a["id"]:
                    continue
                matched_articles.append(a)
    elif law_doc_ids:
        arts = run_cypher(
            """
            MATCH (a:Article)
            WHERE a.doc_id IN $law_docs
            RETURN a.id AS id, a.title AS title, a.law AS law, a.doc_id AS doc_id
            """,
            law_docs=law_doc_ids
        )
        matched_articles.extend(arts)

    # Keywords from question for PCMT definition lookup
    pcmt_keywords = [w for w in ["tiền chất", "chất ma túy", "chất gây nghiện", "chất hướng thần", "cây có chứa chất ma túy", "phòng, chống ma túy", "tệ nạn ma túy", "cai nghiện"] if w in ql]

    for art in matched_articles:
        art_id = art["id"]
        is_pcmt = art.get("law") == "Luật PCMT" or "PCMT" in art_id
        if is_pcmt:
            clauses = run_cypher(
                """
                MATCH (a:Article {id: $art_id})-[:HAS_CLAUSE]->(cl:Clause)
                WHERE cl.number = 1
                   OR any(k IN $keywords WHERE toLower(cl.text) CONTAINS k)
                RETURN DISTINCT a.id AS article_id, a.title AS title, cl.number AS number, cl.text AS text
                ORDER BY cl.number
                """,
                art_id=art_id, keywords=pcmt_keywords
            )
        else:
            clauses = run_cypher(
                """
                MATCH (a:Article {id: $art_id})-[:HAS_CLAUSE]->(cl:Clause)
                WHERE cl.number = 1
                   OR any(s IN $substances WHERE EXISTS { MATCH (cl)-[:MENTIONS]->(:Substance {name: s}) })
                   OR ($is_max = true AND (
                       cl.text CONTAINS 'tử hình'
                       OR cl.text CONTAINS 'chung thân'
                       OR ((cl.penalty CONTAINS 'tù' OR cl.penalty CONTAINS 'tử hình' OR cl.penalty CONTAINS 'chung thân')
                           AND NOT EXISTS {
                               MATCH (a)-[:HAS_CLAUSE]->(cl2:Clause)
                               WHERE (cl2.penalty CONTAINS 'tù' OR cl2.penalty CONTAINS 'tử hình' OR cl2.penalty CONTAINS 'chung thân')
                                 AND cl2.number > cl.number
                           })
                   ))
                RETURN DISTINCT a.id AS article_id, a.title AS title, cl.number AS number, cl.text AS text
                ORDER BY cl.number
                """,
                art_id=art_id, substances=q_substances, is_max=is_max_asked
            )
        for row in clauses:
            bucket_clauses.append(f"[{row['article_id']} - {row['title']}] khoản {row['number']}: {row['text']}")

    # Bucket ordering
    if is_aggregation:
        all_ordered = bucket_aggregation + bucket_clauses + bucket_person_case + bucket_cases + bucket_seeds
    else:
        all_ordered = bucket_clauses + bucket_person_case + bucket_cases + bucket_seeds

    seen = set()
    facts = []
    for f in all_ordered:
        if f and f not in seen:
            seen.add(f)
            facts.append(f)

    return facts[:max_facts]

# Now run verification tests
print("--- TEST S2.1: Q1 with PCMT ---")
f1 = test_context("Điều 2 Luật PCMT quy định tiền chất là gì?", [])
print(f"Facts count: {len(f1)}")
for f in f1[:5]:
    print("  *", f[:120])
has_tien_chat = any("tiền chất" in f.lower() and "khoản 4" in f.lower() for f in f1)
print(f"Has tiền chất khoản 4: {has_tien_chat}")

print("\n--- TEST S2.2: Q1 with doc_ids=['pcmt-dieu-2'] no unrelated cases ---")
f2 = test_context("Theo Luật Phòng, chống ma túy 2021, tiền chất là gì?", ["pcmt-dieu-2"])
print(f"Facts count: {len(f2)}")
for f in f2[:5]:
    print("  *", f[:120])
has_unrelated_cases = any("Vụ việc" in f for f in f2)
print(f"Has unrelated cases: {has_unrelated_cases} (Expect False)")

print("\n--- TEST S2.3: Q6 Aggregation for MDMA ---")
f6 = test_context("Những vụ việc nào trong tin tức có liên quan đến ma túy MDMA?", [])
print(f"Facts count: {len(f6)}")
for f in f6:
    print("  *", f)
cases_in_f6 = [f for f in f6 if f.startswith("Vụ việc")]
print(f"Found {len(cases_in_f6)} cases for MDMA")

print("\n--- TEST S2.4: Q3 with max_facts=5 ---")
f3 = test_context("Lê Minh Thành bị tuyên bao nhiêu tháng tù, về tội gì, và tội đó được quy định tại điều nào của Bộ luật Hình sự với khung hình phạt cơ bản bao nhiêu?", ["news-100260918080821054"], max_facts=5)
print(f"Facts count: {len(f3)}")
for f in f3:
    print("  *", f[:120])
has_251 = any("251" in f for f in f3)
has_sentence = any("36 tháng" in f for f in f3)
print(f"Has Điều 251: {has_251}, Has 36 tháng: {has_sentence}")

print("\n--- TEST S2.5: Q4 max frame ---")
f4 = test_context("Giang hồ 'Hoàng Nato' bị bắt về hành vi gì, và hành vi đó có thể bị phạt tù tối đa bao nhiêu theo Bộ luật Hình sự?", [])
print(f"Facts count: {len(f4)}")
for f in f4:
    print("  *", f[:120])
has_255_max = any("255" in f and ("chung thân" in f or "khoản 4" in f) for f in f4)
print(f"Has Điều 255 max clause: {has_255_max}")

driver.close()
