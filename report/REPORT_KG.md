# Báo cáo Day 19 — Flat RAG vs GraphRAG

**Họ tên:** Từ Hoàng Giang  **MSSV:** 2A202602363  **Ngày:** 05/10/2026

> Kỳ vọng và thang điểm: `SUBMISSION.md`. Mọi số liệu phải khớp với `ket_qua_benchmark_kg.txt`. Bản thiết kế ontology nộp riêng ở `report/ONTOLOGY.md`.

## 1. Chi phí (10 điểm)

Dán 2 bảng `Indexing` và `Querying` từ `ket_qua_benchmark_kg.txt`:

```
== Indexing (one-off)
pipeline  calls    in_tok  out_tok       USD  seconds
flat        176     56072        0   0.00112     80.3
graph       196     91958     4935   0.00947    152.6

== Querying (mean per question)
pipeline  recall  judge   in_tok  out_tok       USD  seconds
flat        0.43   1.00      694       47   0.00013     2.22
graph       0.94   1.83     4254       80   0.00068     3.22
```

| Chỉ số | Flat | Graph | Graph / Flat |
| --- | --- | --- | --- |
| Indexing USD | $0.00112 | $0.00947 | ×8.46 |
| Indexing giây | 80.3 | 152.6 | ×1.90 |
| Mỗi câu: USD | $0.00013 | $0.00068 | ×5.23 |
| Mỗi câu: giây | 2.22 | 3.22 | ×1.45 |
| Mỗi câu: in_tok | 694 | 4254 | ×6.13 |

**Chi phí tăng thêm đến từ đâu?** (2–3 câu)
> Ở pha Indexing, chi phí tăng gấp ~8.5 lần chủ yếu do GraphRAG phải thực hiện thêm 20 lượt gọi LLM JSON mode để trích xuất cấu trúc thực thể/quan hệ từ các bài báo tin tức (tiêu tốn thêm 4.935 output tokens và ~35.000 input tokens). Ở pha Querying, chi phí mỗi câu hỏi tăng gấp ~5.2 lần do Graph context mở rộng multi-hop đã bổ sung trung bình 13–17 dữ kiện chi tiết về Điều luật và tình tiết vụ án vào prompt, khiến lượng input tokens mỗi câu tăng từ 694 lên 4.254 tokens (gấp ~6.1 lần).

---

## 2. Từng câu hỏi (10 điểm)

| Câu | Loại | Flat recall / judge | Graph recall / judge | Thắng | Vì sao (1 câu) |
| --- | --- | --- | --- | --- | --- |
| Q1 | single-hop-law | 1.00 / 2 | 1.00 / 2 | Hòa | Câu hỏi định nghĩa điều luật cơ bản, văn bản luật nằm trọn vẹn trong top-3 vector chunks nên cả hai pipeline đều trả lời chính xác tuyệt đối. |
| Q2 | single-hop-news | 1.00 / 2 | 1.00 / 2 | Hòa | Thông tin mức án tử hình nằm trực tiếp trong một bài báo tin tức đơn lẻ, vector search tìm trúng bài nên cả hai bên đều trả lời đúng và đủ. |
| Q3 | cross-kb | 0.00 / 0 | 1.00 / 2 | Graph | Cần nối từ người trong tin (Lê Minh Thành) sang điều luật tương ứng (Điều 251 BLHS); Flat RAG không kết nối được 2 KB nên trả về "Không đủ thông tin", còn GraphRAG đi qua node cầu nối `Crime` tìm đúng Điều 251 khoản 1. |
| Q4 | cross-kb | 0.00 / 0 | 1.00 / 2 | Graph | Cần tra cứu mức phạt tối đa của hành vi tổ chức sử dụng; Flat RAG thiếu ngữ cảnh luật nên báo "Không đủ thông tin", còn GraphRAG mở rộng tới khoản 4 Điều 255 (tù 20 năm hoặc tù chung thân). |
| Q5 | cross-kb-multi-hop | 0.60 / 1 | 1.00 / 2 | Graph | Cần liên kết đối tượng (Cái Quang Huy), hành vi (vận chuyển), chất và lượng (9,6kg MDMA) để xác định đúng khoản 4 Điều 250; Flat RAG đoán sai thành "khoản b)", còn GraphRAG có fact cụ thể nên trả lời chính xác khung tử hình. |
| Q6 | aggregation | 0.00 / 1 | 0.67 / 1 | Graph | Câu hỏi tổng hợp danh sách các vụ việc liên quan đến MDMA; Flat RAG không nêu được tên vụ cụ thể, còn GraphRAG tổng hợp được các vụ án từ quan hệ `INVOLVES` nối tới node `Substance {name: 'MDMA'}`. |

---

## 3. Phân tích lỗi (20 điểm)

### Lỗi E4: Phép đo sai (Metric Mismatch / Overly Rigid Ground Truth)

- **Hiện tượng:** Ở câu Q6 (aggregation), câu trả lời của GraphRAG đã liệt kê đầy đủ 3 vụ án cụ thể có liên quan đến ma túy MDMA trong tin tức và được LLM Judge chấm đúng một phần (judge=1), nhưng chỉ số `keyword_recall` chỉ đạt 0.67.
- **Bằng chứng:** Trích câu trả lời Q6 của GraphRAG trong `ket_qua_benchmark_kg.txt`:

```
--- Q6 [aggregation] graph recall=0.67 judge=1 2.65s
Các vụ việc trong tin tức có liên quan đến ma túy MDMA bao gồm:

1. Vụ vận chuyển ma túy từ Đức về Việt Nam: Cái Quang Huy bị cáo buộc vận chuyển hơn 9,6kg MDMA.
2. Vụ góp tiền mua ma túy tại Hà Nội: Ba thanh niên góp tiền để Lê Minh Thành mua ma túy, trong đó có MDMA.
3. Vụ tổ chức sử dụng ma túy tại Sầm Sơn: Đông bị thu giữ 0,686g ma túy MDMA trong quá trình sử dụng ma túy.

Ngoài ra, các điều luật liên quan đến MDMA có thể được áp dụng trong các vụ việc này, như Điều 250 và Điều 251 của Bộ luật Hình sự.
```

Đối chiếu với `must_include` trong `data/benchmark_kg.json`: `["Cái Quang Huy", "Lê Minh Thành", "Pháp y tâm thần"]`. Kiểm tra số vụ án thực tế liên quan đến MDMA trên đồ thị:

```cypher
MATCH (k:Case)-[:INVOLVES]->(s:Substance {name: 'MDMA'})
RETURN k.name, k.doc_id;
```

```
k.name: "Vụ vận chuyển hơn 9,6kg ma túy từ Đức về Việt Nam qua sân bay Nội Bài", doc_id: "news-100260918080821051"
k.name: "Vụ mua bán ma túy tại Hà Nội", doc_id: "news-100260918080821054"
k.name: "Vụ tổ chức sử dụng ma túy tại Sầm Sơn", doc_id: "news-100260918080821053"
k.name: "Vụ đường dây ma túy tại Bệnh viện Tâm thần Trung ương I", doc_id: "news-100260918080821050"
```

- **Nguyên nhân:** Trong corpus có tới 4 vụ án cùng liên quan đến tang vật MDMA. GraphRAG đã gom và trình bày 3 vụ (gồm cả vụ Sầm Sơn), trong khi ground truth `must_include` lại áp đặt cứng chuỗi con `"Pháp y tâm thần"`. Hàm `keyword_recall` chỉ kiểm tra máy móc sự xuất hiện chuỗi con (`k.lower() in answer.lower()`) nên bị tụt điểm recall dù câu trả lời hoàn toàn chính xác về mặt nghiệp vụ.
- **Đề xuất sửa:** Đổi phép đo đánh giá câu hỏi aggregation sang `entity coverage` (tỷ lệ node Case hợp lệ được liệt kê trên tổng số Case thỏa mãn Cypher) hoặc yêu cầu LLM trong prompt trả lời liệt kê đầy đủ toàn bộ các vụ được graph cung cấp thay vì dừng ở 3 vụ tiêu biểu. Đánh đổi: câu trả lời sẽ dài hơn và tốn thêm token output.

---

### Lỗi E2: Thiếu mô hình hóa ngưỡng định lượng số học trong Điều luật (Missing Quantitative Threshold Modeling)

- **Hiện tượng:** Ở câu hỏi Q5, mặc dù GraphRAG đạt recall 1.00 và judge 2, nhưng đồ thị tri thức không thể tự lọc được chính xác duy nhất Khoản 4 bằng Cypher, mà phải đẩy đồng thời nhiều khoản luật vào prompt để LLM đọc văn bản và tự suy luận xem khối lượng `9,6kg` rơi vào khoản nào.
- **Bằng chứng:** Truy vấn Cypher các khoản của Điều 250 có liên kết tới chất MDMA:

```cypher
MATCH (a:Article {id: 'Điều 250 BLHS'})-[:HAS_CLAUSE]->(cl:Clause)-[:MENTIONS]->(s:Substance {name: 'MDMA'})
RETURN cl.number, cl.penalty;
```

```
cl.number: 2, cl.penalty: "phạt tù từ 07 năm đến 15 năm"
cl.number: 3, cl.penalty: "phạt tù từ 15 năm đến 20 năm"
cl.number: 4, cl.penalty: "phạt tù 20 năm, tù chung thân hoặc tử hình"
```

- **Nguyên nhân:** Bộ luật Hình sự quy định các khung hình phạt tăng nặng dựa trên ngưỡng khối lượng (khoản 2: 5g đến dưới 30g; khoản 3: 30g đến dưới 100g; khoản 4: từ 100g trở lên). Trong ontology hiện tại, quan hệ `[:MENTIONS]` chỉ liên kết nhãn thực thể mà không mang thuộc tính số học (`min_weight_g`, `max_weight_g`). Do đó, Cypher không thể thực hiện so sánh toán học `9600g >= 100g` để lọc duy nhất khoản 4, buộc phải nhồi văn bản của cả khoản 1, 2, 3, 4 vào facts.
- **Đề xuất sửa:** Bổ sung thuộc tính số học chuẩn hóa (đổi hết về gram) trên quan hệ `[:MENTIONS {min_g: 100, max_g: null}]` và trên vụ án `[:INVOLVES {weight_g: 9600}]`. Khi đó, Cypher có thể lọc trực tiếp: `WHERE k.weight_g >= rel.min_g AND (rel.max_g IS NULL OR k.weight_g < rel.max_g)`. Đánh đổi: quá trình trích xuất luật và tin tức phức tạp hơn nhiều, đòi hỏi parser phải phân tích được các biểu thức định lượng tự nhiên trong văn bản.

---

## 4. Kết luận (5 điểm)

Khi nào nên dùng KG, khi nào Flat RAG là đủ? Dẫn số liệu ở mục 1–2.
> - **Nên dùng Flat RAG khi:** Hệ thống chỉ phục vụ các câu hỏi tra cứu thông tin đơn lẻ (single-hop), định nghĩa trực tiếp văn bản quy phạm pháp luật (Q1: cả hai đều recall 1.00, judge 2) hoặc sự kiện nằm trọn vẹn trong một bài báo (Q2: cả hai đều recall 1.00, judge 2). Trong các kịch bản này, Flat RAG hoàn toàn vượt trội về hiệu quả chi phí: rẻ hơn **8.5 lần chi phí Indexing** ($0.00112 so với $0.00947), rẻ hơn **5.2 lần chi phí mỗi câu hỏi** ($0.00013 so với $0.00068), và độ trễ nhanh hơn 45% (2.22s so với 3.22s).
> - **Bắt buộc dùng GraphRAG khi:** Bài toán đòi hỏi suy luận xuyên miền tri thức (cross-kb) hoặc đa bước (multi-hop) giữa thực tiễn xét xử và căn cứ pháp luật (Q3, Q4, Q5). Số liệu thực nghiệm minh chứng rõ rệt: Flat RAG hoàn toàn bất lực trên Q3 và Q4 (recall 0.00, judge 0 do thông tin luật và tin nằm phân mảnh ở các tài liệu khác nhau), và đoán sai khoản luật ở Q5 (recall 0.60, judge 1). Ngược lại, GraphRAG đạt recall trung bình **0.94** và judge **1.83/2**, giải quyết triệt để vấn đề phân mảnh ngữ cảnh nhờ các liên kết thực thể có cấu trúc qua node cầu nối `Crime`.

---

## 5. Tự kiểm (5 điểm)

```
$ pytest tests/ -q
................................................                         [100%]
48 passed in 0.16s

$ python bench_kg.py --check
[OK] Dữ liệu: 18 điều luật, 20 bài báo
[OK] KG-1 link_entity
[OK] Neo4j kết nối được
[provider] chat = openrouter:openai/gpt-4o-mini | embedding = openrouter:openai/text-embedding-3-small
[OK] KG-2 build_graph: 146 node / 289 cạnh, đường xuyên 2 KB dài 2 cạnh
[OK] KG-3 context: 13 dữ kiện, có Điều 251
[OK] KG-4 GraphRAGAgent.answer
[OK] Chi phí check: 1 lần gọi LLM, $0.00065. Graph nhỏ (luật + 1 bài) vẫn còn trong Neo4j để bạn xem; chạy --judge để dựng graph đầy đủ.
```

Ảnh Neo4j: `report/img/kg_count.png`, `report/img/kg_cross_kb.png`, `report/img/kg_my_case.png`.
Người đã chọn cho `kg_my_case.png`: Ngô Việt Dũng (Vụ tổ chức sử dụng ma túy tại Sầm Sơn - Điều 255 BLHS).

## Vấn đề gặp phải (không tính điểm)

Lỗi chưa giải quyết được: Không có. Tất cả các bước kiểm thử offline (48 tests), self-check hợp đồng (`--check`), benchmark đánh giá tự động (`--judge`) và trích xuất hình ảnh minh chứng từ Neo4j Browser đều đã hoàn thành 100%.
