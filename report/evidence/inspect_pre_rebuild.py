from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
user = os.getenv('NEO4J_USER', 'neo4j')
pwd = os.getenv('NEO4J_PASSWORD', 'password123')

driver = GraphDatabase.driver(uri, auth=(user, pwd))
s = driver.session()

print('=== Node Counts by Label ===')
for r in s.run("MATCH (n) RETURN labels(n)[0] AS lbl, count(n) AS cnt ORDER BY cnt DESC"):
    print(r.data())

output_path = os.path.join(os.path.dirname(__file__), 's1_pre_rebuild_notes.md')

lines = []
lines.append('# Snapshot Lịch Sử Trước Khi Rebuild (Commit 92c57d8)')
lines.append('')
lines.append('- Thời điểm kiểm tra: 2026-10-05')
lines.append('- Neo4j URI: bolt://localhost:7687')
lines.append('')
lines.append('## 1. Thống kê Node theo Label')
for r in s.run("MATCH (n) RETURN labels(n)[0] AS lbl, count(n) AS cnt ORDER BY cnt DESC"):
    lines.append(f"- **{r['lbl']}**: {r['cnt']}")

total_n = s.run('MATCH (n) RETURN count(n) AS c').single()['c']
total_r = s.run('MATCH ()-[r]->() RETURN count(r) AS c').single()['c']
lines.append(f"\n**Tổng cộng**: {total_n} nodes, {total_r} relationships.")

lines.append('\n## 2. Các Case liên quan MDMA hiện tại (k:Case)-[:INVOLVES]->(s:Substance)')
for r in s.run("MATCH (k:Case)-[r:INVOLVES]->(sub:Substance) WHERE toLower(sub.name) = 'mdma' RETURN k.name AS case_name, k.doc_id AS doc_id, sub.name AS sub_name, r.amount AS amount"):
    lines.append(f"- Case: `{r['case_name']}` | doc_id: `{r['doc_id']}` | substance: `{r['sub_name']}` | amount: `{r['amount']}`")

lines.append('\n## 3. Trùng lặp tên Substance (khác chữ hoa/thường)')
for r in s.run("MATCH (sub:Substance) WITH toLower(sub.name) AS norm, collect(sub.name) AS names WHERE size(names) > 1 RETURN norm, names"):
    lines.append(f"- Normalized: `{r['norm']}` -> Variants: {r['names']}")

lines.append('\n## 4. Thực thể Người liên quan Cái Quang Huy')
for r in s.run("MATCH (p:Person)-[:INVOLVED_IN]->(k:Case) WHERE p.name CONTAINS 'Huy' RETURN p.name AS person, k.name AS case_name, k.doc_id AS doc_id"):
    lines.append(f"- Person: `{r['person']}` | Case: `{r['case_name']}` | doc_id: `{r['doc_id']}`")

lines.append('\n## 5. Các Khoản của Điều 250 đề cập MDMA')
for r in s.run("MATCH (a:Article {doc_id: 'blhs-dieu-250'})-[:HAS_CLAUSE]->(cl:Clause)-[:MENTIONS]->(sub:Substance) WHERE toLower(sub.name) = 'mdma' RETURN cl.number AS num, cl.penalty AS pen ORDER BY cl.number"):
    lines.append(f"- Khoản {r['num']}: penalty = `{r['pen']}`")

lines.append('\n## 6. Các vấn đề cần xác minh trên đồ thị cuối (R5, R8)')
lines.append('1. **Ba doc_id không tồn tại trong phần E4 của REPORT_KG.md**: Các doc_id `news-100260918080821051`, `news-100260918080821053`, `news-100260918080821050` trong báo cáo cũ không có trong thư mục `data/drug_news/`. Báo cáo mới phải dùng doc_id thật.')
lines.append('2. **Query E2**: Cần kiểm tra xem Clause 1 của Điều 250 có liên kết MENTIONS MDMA không hay chỉ các khoản 2, 3, 4.')
lines.append('3. **Case Cái Quang Huy**: Tên vụ án trích xuất từ tin tức có thể bị biến thể giữa các lần gọi LLM.')
lines.append('4. **Substance trùng khác chữ hoa/thường**: Kiểm tra có xuất hiện cả `MDMA` và `mdma` hoặc `Ma túy` và `ma túy`.')
lines.append('5. **Q6 nhập nhằng giữa sự kiện Sầm Sơn và tang vật thu tại viện**: Cần đối chiếu chính xác các Case được link tới MDMA.')

driver.close()

with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print('Wrote notes successfully to', output_path)

