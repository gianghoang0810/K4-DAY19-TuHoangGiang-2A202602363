import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
load_dotenv()

from src.graph import Neo4jGraph

uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
user = os.getenv('NEO4J_USER', 'neo4j')
pwd = os.getenv('NEO4J_PASSWORD', 'password123')

g = Neo4jGraph(uri, user, pwd)

out_file = os.path.join(os.path.dirname(__file__), "s6_evidence.md")
lines = []

lines.append("# Bằng Chứng Lỗi và Dữ Liệu Thực Tế Trên Đồ Thị Cuối (S6)")
lines.append("")
lines.append("## 1. Thống kê Node và Relationship hiện tại")
stats = g.stats()
lines.append(f"- **Tổng số Node**: {stats['nodes']}")
lines.append(f"- **Tổng số Quan hệ**: {stats['relationships']}")
lines.append("")
lines.append("Chi tiết theo nhãn Node:")
for r in g.run("MATCH (n) RETURN labels(n)[0] AS lbl, count(n) AS cnt ORDER BY cnt DESC"):
    lines.append(f"- `{r['lbl']}`: {r['cnt']}")

lines.append("\nChi tiết theo loại Cạnh:")
for r in g.run("MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC"):
    lines.append(f"- `[:{r['rel']}]`: {r['cnt']}")

# Query 1: Case liên quan MDMA
lines.append("\n## 2. Truy vấn: Case liên quan MDMA")
lines.append("```cypher")
lines.append("MATCH (k:Case)-[r:INVOLVES]->(s:Substance {name:'MDMA'})")
lines.append("RETURN k.name, k.doc_id, r.amount")
lines.append("ORDER BY k.doc_id, k.name;")
lines.append("```")
lines.append("Kết quả thực tế:")
res1 = g.run("""
MATCH (k:Case)-[r:INVOLVES]->(s:Substance {name:'MDMA'})
RETURN k.name AS name, k.doc_id AS doc_id, r.amount AS amount
ORDER BY k.doc_id, k.name
""")
for r in res1:
    lines.append(f"- Case: `{r['name']}` | doc_id: `{r['doc_id']}` | amount: `{r['amount']}`")

# Query 2: Khác biệt cách viết tên chất
lines.append("\n## 3. Truy vấn: Trùng lặp biến thể cách viết tên chất (Case-insensitive)")
lines.append("```cypher")
lines.append("MATCH (s:Substance)")
lines.append("WITH toLower(s.name) AS normalized, collect(s.name) AS names")
lines.append("WHERE size(names) > 1")
lines.append("RETURN normalized, names;")
lines.append("```")
lines.append("Kết quả thực tế:")
res2 = g.run("""
MATCH (s:Substance)
WITH toLower(s.name) AS normalized, collect(s.name) AS names
WHERE size(names) > 1
RETURN normalized, names
""")
if res2:
    for r in res2:
        lines.append(f"- `{r['normalized']}`: {r['names']}")
else:
    lines.append("Không có substance nào bị trùng theo chữ hoa/thường.")

# Query 3: Một người tham gia nhiều Case
lines.append("\n## 4. Truy vấn: Một người tham gia nhiều Case")
lines.append("```cypher")
lines.append("MATCH (p:Person)-[:INVOLVED_IN]->(k:Case)")
lines.append("WITH p.name AS person,")
lines.append("     collect(DISTINCT {name:k.name, doc_id:k.doc_id}) AS cases")
lines.append("WHERE size(cases) > 1")
lines.append("RETURN person, cases;")
lines.append("```")
lines.append("Kết quả thực tế:")
res3 = g.run("""
MATCH (p:Person)-[:INVOLVED_IN]->(k:Case)
WITH p.name AS person,
     collect(DISTINCT {name:k.name, doc_id:k.doc_id}) AS cases
WHERE size(cases) > 1
RETURN person, cases
""")
for r in res3:
    lines.append(f"- Person `{r['person']}` ({len(r['cases'])} cases):")
    for c in r['cases']:
        lines.append(f"  * Case: `{c['name']}` (doc_id: `{c['doc_id']}`)")

# Query 4: Các khoản của Điều 250 đề cập MDMA
lines.append("\n## 5. Truy vấn: Các khoản của Điều 250 đề cập MDMA")
lines.append("```cypher")
lines.append("MATCH (a:Article {doc_id:'blhs-dieu-250'})")
lines.append("      -[:HAS_CLAUSE]->(cl:Clause)")
lines.append("      -[:MENTIONS]->(:Substance {name:'MDMA'})")
lines.append("RETURN cl.number, cl.penalty")
lines.append("ORDER BY cl.number;")
lines.append("```")
lines.append("Kết quả thực tế:")
res4 = g.run("""
MATCH (a:Article {doc_id:'blhs-dieu-250'})
      -[:HAS_CLAUSE]->(cl:Clause)
      -[:MENTIONS]->(:Substance {name:'MDMA'})
RETURN cl.number AS number, cl.penalty AS penalty
ORDER BY cl.number
""")
for r in res4:
    lines.append(f"- Khoản {r['number']}: `{r['penalty']}`")

# Query 5: Kiểm tra các Case không có CHARGED_WITH
lines.append("\n## 6. Truy vấn: Các Case không có liên kết CHARGED_WITH")
res5 = g.run("""
MATCH (k:Case)
WHERE NOT (k)-[:CHARGED_WITH]->(:Crime)
RETURN k.name AS name, k.doc_id AS doc_id, k.summary AS summary
""")
lines.append(f"Số lượng Case không có CHARGED_WITH: {len(res5)}")
for r in res5:
    lines.append(f"- Case `{r['name']}` (doc_id: `{r['doc_id']}`): {r['summary']}")

g.close()

with open(out_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print(f"Recorded S6 evidence successfully to {out_file}")
