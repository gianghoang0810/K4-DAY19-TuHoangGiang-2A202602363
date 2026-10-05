# Báo cáo Day 19 — Flat RAG vs GraphRAG

**Họ tên:** Từ Hoàng Giang  **MSSV:** 2A202602363  **Ngày:** 05/10/2026

> Kỳ vọng và thang điểm: `SUBMISSION.md`. Mọi số liệu khớp 100% với `ket_qua_benchmark_kg.txt`. Bản thiết kế ontology nộp riêng ở `report/ONTOLOGY.md`.

## 1. Chi phí (10 điểm)

Dán 2 bảng `Indexing` và `Querying` từ `ket_qua_benchmark_kg.txt`:

```
== Indexing (one-off)
pipeline  calls    in_tok  out_tok       USD  seconds
flat        176     56072        0   0.00112    108.9
graph       196     91958     4635   0.00929    234.2

== Querying (mean per question)
pipeline  recall  judge   in_tok  out_tok       USD  seconds
flat        0.43   1.00      694       47   0.00013     2.94
graph       1.00   1.83     3927       87   0.00063     4.33
```

| Chỉ số | Flat | Graph | Graph / Flat |
| --- | --- | --- | --- |
| Indexing USD | $0.00112 | $0.00929 | ×8.30 |
| Indexing giây | 108.9 | 234.2 | ×2.15 |
| Mỗi câu: USD | $0.00013 | $0.00063 | ×4.85 |
| Mỗi câu: giây | 2.94 | 4.33 | ×1.47 |
| Mỗi câu: in_tok | 694 | 3927 | ×5.66 |

**Chi phí tăng thêm đến từ đâu?** (2–3 câu)
> Ở pha Indexing, chi phí tăng gấp ~8.3 lần chủ yếu do GraphRAG phải thực hiện thêm 20 lượt gọi LLM JSON mode để trích xuất cấu trúc thực thể và quan hệ từ các bài báo tin tức (tiêu tốn thêm 4.635 output tokens và ~35.886 input tokens). Ở pha Querying, chi phí mỗi câu hỏi tăng gấp ~4.85 lần do Graph context mở rộng đa bước đã bổ sung các dữ kiện có cấu trúc về Điều/Khoản luật, tang vật và mức án vào prompt, khiến lượng input tokens mỗi câu tăng từ 694 lên 3.927 tokens (gấp ~5.66 lần). Chi phí pipeline trong bảng phản ánh chi phí token trực tiếp được ghi nhận bởi script (chi phí judge được đo tách biệt trong quá trình đánh giá).

---

## 2. Từng câu hỏi (10 điểm)

| Câu | Loại | Flat recall / judge | Graph recall / judge | Thắng | Vì sao (1 câu) |
| --- | --- | --- | --- | --- | --- |
| Q1 | single-hop-law | 1.00 / 2 | 1.00 / 2 | Hòa | Câu hỏi định nghĩa tiền chất trong Luật PCMT 2021; cả hai pipeline đều tìm đúng định nghĩa tại Khoản 4 Điều 2 và trả lời chính xác, đủ ý. |
| Q2 | single-hop-news | 1.00 / 2 | 1.00 / 2 | Hòa | Thông tin mức án tử hình nằm trọn vẹn trong một bài báo tin tức đơn lẻ; vector search lấy đúng chunk giúp cả hai bên trả lời đúng đối tượng Tuấn và Tâm. |
| Q3 | cross-kb | 0.00 / 0 | 1.00 / 2 | Graph | Cần kết nối từ nhân vật trong tin tức (Lê Minh Thành) sang điều luật tương ứng (Điều 251 BLHS); Flat RAG trả về "Không đủ thông tin", còn GraphRAG đi qua node cầu nối `Crime` tìm đúng tội danh và Khoản 1 với khung cơ bản 2–7 năm tù. |
| Q4 | cross-kb | 0.00 / 0 | 1.00 / 2 | Graph | Cần tra cứu mức phạt tối đa của hành vi tổ chức sử dụng trái phép chất ma túy; Flat RAG thiếu ngữ cảnh luật nên báo "Không đủ thông tin", còn GraphRAG truy xuất chính xác Khoản 4 Điều 255 BLHS (tù 20 năm hoặc tù chung thân). |
| Q5 | cross-kb-multi-hop | 0.60 / 1 | 1.00 / 2 | Graph | Cần xâu chuỗi đối tượng (Cái Quang Huy), hành vi (vận chuyển), tang vật (hơn 9,6kg MDMA) để xác định đúng Khoản 4 Điều 250; Flat RAG đoán sai thành "khoản b)", trong khi GraphRAG cung cấp facts đầy đủ giúp chỉ rõ Khoản 4 và khung phạt từ 20 năm, chung thân hoặc tử hình. |
| Q6 | aggregation | 0.00 / 1 | 1.00 / 1 | Graph | Câu hỏi tổng hợp danh sách các vụ việc liên quan đến MDMA; Flat RAG không nêu được tên vụ cụ thể, còn GraphRAG truy xuất đầy đủ 4 Case có cạnh `[:INVOLVES]` tới MDMA, bao phủ trọn vẹn cả 3 từ khóa chuẩn của ground truth ("Cái Quang Huy", "Lê Minh Thành", "Pháp y tâm thần"). |

---

## 3. Phân tích lỗi (20 điểm)

Dưới đây là hai nhóm lỗi được thu thập và chứng minh bằng truy vấn Cypher và dữ liệu thực tế trên đồ thị tri thức cuối cùng:

### Lỗi E3: Trùng lặp thực thể và phân mảnh vụ án (Entity Duplication & Case Fragmentation)

- **Hiện tượng 1: Trùng lặp biến thể tên chất do phân biệt chữ hoa/thường (`Substance Case-sensitivity`)**
  - **Query kiểm chứng trên đồ thị cuối:**
    ```cypher
    MATCH (s:Substance)
    WITH toLower(s.name) AS normalized, collect(s.name) AS names
    WHERE size(names) > 1
    RETURN normalized, names;
    ```
  - **Output thực tế:**
    ```
    - ketamine: ['Ketamine', 'ketamine']
    - cần sa: ['Cần sa', 'cần sa']
    - methamphetamine: ['methamphetamine', 'Methamphetamine']
    ```
  - **Nguyên nhân:** Quá trình nạp luật dùng danh sách chuẩn viết hoa (`SUBSTANCES = ["Ketamine", "Methamphetamine", ...]`), trong khi prompt trích xuất tin tức từ LLM trả về các từ viết thường trong tiếng Việt. Vì câu lệnh `MERGE (sub:Substance {name: s.name})` trong Neo4j phân biệt hoa/thường, đồ thị đã tạo ra hai node tách rời cho cùng một chất.
  - **Đề xuất sửa & Đánh đổi:** Chuẩn hóa tên chất về chữ hoa đầu từ (`s.name.capitalize()`) hoặc chuyển về chữ thường trước khi `MERGE`. Đánh đổi: Phải xử lý ngoại lệ cho các tên viết tắt quốc tế (như `MDMA`, `XLR-11`) để tránh bị đổi thành `Mdma`.

- **Hiện tượng 2: Phân mảnh vụ án giữa nhiều bài báo (`Case Fragmentation`)**
  - **Query kiểm chứng trên đồ thị cuối:**
    ```cypher
    MATCH (p:Person {name: 'Dương Minh Tuấn'})-[:INVOLVED_IN]->(k:Case)
    RETURN k.name AS case_name, k.doc_id AS doc_id;
    ```
  - **Output thực tế:**
    ```
    - Case: 'Vụ bắt giang hồ 'Hoàng Nato' và 126 người liên quan 8 đường dây ma túy' (doc_id: 'news-100260920221957595')
    - Case: 'Vụ bắt giữ TikToker Phannhibeauty và giang hồ 'Hoàng Nato'' (doc_id: 'news-100260922111804786')
    - Case: 'Vụ sử dụng ma túy etomidate của Hoàng Nato và Phan Kim Nhi' (doc_id: 'news-100260924095400982')
    - Case: 'Vụ bắt 'Hoàng Nato' và triệt phá 8 đường dây ma túy' (doc_id: 'news-100260925144412498')
    ```
  - **Nguyên nhân:** Khóa định danh của `Case` là thuộc tính `name` được LLM sinh ra độc lập theo từng bài báo. Khi một vụ án lớn được báo chí theo dõi và đưa tin liên tục qua nhiều ngày, mỗi bài báo sinh ra một node `Case` riêng rẽ thay vì hợp nhất vào một vụ việc duy nhất.
  - **Đề xuất sửa & Đánh đổi:** Cần bổ sung thuật toán gom cụm / liên kết thực thể (Cross-document Entity Resolution) dựa trên trùng khớp đối tượng chính (`Dương Minh Tuấn`), mốc thời gian và địa bàn. Đánh đổi: Tăng thêm chi phí tính toán và độ trễ khi nạp dữ liệu.

---

### Lỗi E2 / Hạn chế thiết kế: Thiếu mô hình hóa ngưỡng định lượng số học trong Điều luật (Missing Quantitative Threshold Modeling)

- **Hiện tượng:** Ở câu hỏi Q5, mặc dù GraphRAG đạt recall 1.00 và judge 2, nhưng đồ thị tri thức không thể tự động lọc duy nhất Khoản 4 bằng Cypher, mà phải chuyển đồng thời cả 4 khoản luật vào prompt để LLM tự đọc hiểu và tính toán xem khối lượng `9,6kg` rơi vào khoản nào.
- **Bằng chứng thực tế:** Truy vấn Cypher kiểm tra các khoản của Điều 250 có liên kết tới chất MDMA trên đồ thị cuối:
  ```cypher
  MATCH (a:Article {doc_id:'blhs-dieu-250'})
        -[:HAS_CLAUSE]->(cl:Clause)
        -[:MENTIONS]->(:Substance {name:'MDMA'})
  RETURN cl.number, cl.penalty
  ORDER BY cl.number;
  ```
- **Output thực tế:**
  ```
  - Khoản 1: phạt tù từ 02 năm đến 07 năm
  - Khoản 2: phạt tù từ 07 năm đến 15 năm
  - Khoản 3: phạt tù từ 15 năm đến 20 năm
  - Khoản 4: phạt tù 20 năm, tù chung thân hoặc tử hình
  ```
  *(Lưu ý đối chiếu: Báo cáo ban đầu từng chép thiếu Khoản 1. Kết quả thực nghiệm khẳng định cả 4 khoản của Điều 250 đều có quan hệ `[:MENTIONS]` tới MDMA).*
- **Nguyên nhân:** Trong ontology, quan hệ `[:MENTIONS]` chỉ liên kết nhãn văn bản thuần túy giữa Khoản luật và Chất ma túy, không chứa thuộc tính định lượng số học (`min_weight_g`, `max_weight_g`). Tương tự, quan hệ `[:INVOLVES]` trên vụ án chỉ lưu chuỗi tự nhiên `amount: "9.6kg"`. Do đó, Cypher không thể thực thi so sánh toán học `9600g >= 100g` để tự loại bỏ các khoản 1, 2, 3.
- **Đề xuất sửa & Đánh đổi:** Bổ sung thuộc tính số học đã quy đổi về gram trên quan hệ: `[:MENTIONS {min_g: 100}]` và `[:INVOLVES {amount_g: 9600}]`. Khi đó Cypher có thể lọc trực tiếp khoản áp dụng chính xác. Đánh đổi: Quá trình parser luật và trích xuất tin tức phải nhận diện được biểu thức định lượng phức tạp, tốn thêm token và dễ gặp lỗi parsing khi vụ án có nhiều loại chất ma túy khác nhau.

---

### Phân tích cải tiến Q6 (Truy xuất Aggregation và đối chiếu bài báo nguồn)

- **Trước cải tiến:** Hàm `seed_facts()` cũ tìm kiếm chuỗi con chứa từ khóa "ma túy" trong câu hỏi, dẫn đến việc kích hoạt mở rộng toàn bộ đồ thị do node `Substance {name: 'ma túy'}` liên kết với hầu hết các vụ án. Hậu quả là facts bị tràn bởi các dữ kiện không liên quan, khiến GraphRAG chỉ đạt recall 0.67 và bỏ sót hai vụ việc quan trọng. Đồng thời, báo cáo ban đầu từng trích dẫn 3 `doc_id` không tồn tại trong thư mục dữ liệu (`news-100260918080821051`, `news-100260918080821053`, `news-100260918080821050`).
- **Sau cải tiến (S2):**
  1. Loại bỏ các tên chung ("ma túy", "chất ma túy") khỏi danh sách mở rộng tự do trong `seed_facts`.
  2. Bổ sung nhánh truy vấn aggregation chuyên biệt: tìm trực tiếp các Case có quan hệ `(k:Case)-[:INVOLVES]->(:Substance {name: 'MDMA'})` kèm người liên quan và tóm tắt vụ việc.
  3. Kiểm chứng trên đồ thị cuối cùng, 4 vụ việc thực tế liên quan đến MDMA tương ứng với 4 `doc_id` có thật 100% trong `data/drug_news/`:
     - `Vụ vận chuyển ma túy từ Đức về Việt Nam` (`news-100260917203001265`): Cái Quang Huy (bị cáo), thu giữ hơn 9,6kg MDMA.
     - `Vụ góp tiền mua ma túy tại Hà Nội` (`news-100260918080821054`): Lê Minh Thành (bị cáo), thu giữ 5 viên MDMA.
     - `Vụ án tại Viện Pháp y tâm thần Trung ương` (`news-100260924105118645`): Nguyễn Thị Mai Anh, Lê Văn Đông liên quan đến hành vi tổ chức, sử dụng MDMA trong phòng bệnh.
     - `Vụ tổ chức sử dụng ma túy tại Sầm Sơn` (`news-100260930085028036`): Lê Văn Đông trốn viện và sử dụng 0,686g MDMA cùng Ngô Việt Dũng và người khác.
  4. **Đối chiếu sâu với bài báo nguồn — Sự nhập nhằng giữa sự kiện và nguồn gốc tang vật:**
     - Khi đọc kỹ bài báo gốc `news-100260930085028036.md`, bài viết tường thuật phiên tòa xét xử vụ án Viện Pháp y tâm thần Trung ương, trong đó làm rõ việc Lê Văn Đông trốn viện ra Sầm Sơn "bay lắc" (sử dụng "nước vui" và cần sa). Tuy nhiên, tại các đoạn 70–74, bài báo nêu rõ: tang vật **`0,686g ma túy MDMA` thực tế được phát hiện khi khám xét buồng chữa bệnh của Đông tại Viện Pháp y tâm thần Trung ương**, chứ không phải thu tại bãi biển Sầm Sơn.
     - Do LLM trích xuất độc lập theo từng bài báo mà không có liên kết hồ sơ thực tế, thực thể `Case` mang tên `Vụ tổ chức sử dụng ma túy tại Sầm Sơn` đã bị gán luôn tang vật `0,686g MDMA`. Trong khi đó, bài báo trước (`news-100260924105118645.md`) lại sinh ra một node `Case` riêng là `Vụ án tại Viện Pháp y tâm thần Trung ương` (với MDMA nhưng không có khối lượng cụ thể).
     - Kết quả là trên đồ thị xuất hiện 2 node `Case` tách rời nhau dù cùng xuất phát từ một chuỗi sự kiện và một địa điểm thu giữ tang vật. Đây là ví dụ kinh điển về **sự phân mảnh thực thể và nhập nhằng ngữ cảnh giữa sự kiện (event) với nguồn gốc phát hiện tang vật (evidence origin)** trong pipeline trích xuất tự động bằng LLM.
  5. **Kết quả:** Câu trả lời Q6 của GraphRAG trong benchmark cuối đạt recall **1.00** tuyệt đối, chứa đủ cả 3 chuỗi con quy định trong ground truth `must_include`: `"Cái Quang Huy"`, `"Lê Minh Thành"`, `"Pháp y tâm thần"`.

---

## 4. Kết luận (5 điểm)

Khi nào nên dùng KG, khi nào Flat RAG là đủ? Dẫn số liệu ở mục 1–2.
> - **Nên dùng Flat RAG khi:** Hệ thống phục vụ các câu hỏi tra cứu thông tin đơn lẻ (single-hop), định nghĩa trực tiếp trong văn bản quy phạm pháp luật (Q1: cả hai đều recall 1.00, judge 2) hoặc các sự kiện nằm trọn vẹn trong một bài báo tin tức (Q2: cả hai đều recall 1.00, judge 2). Trong các kịch bản này, Flat RAG mang lại ưu thế tuyệt đối về mặt chi phí và hiệu năng: rẻ hơn **8.3 lần chi phí Indexing** ($0.00112 so với $0.00929), rẻ hơn **4.85 lần chi phí mỗi câu hỏi** ($0.00013 so với $0.00063), và độ trễ nhanh hơn 47% (2.94s so với 4.33s).
> - **Nên ưu tiên cân nhắc GraphRAG khi:** Bài toán đòi hỏi suy luận xuyên miền tri thức (cross-kb), tổng hợp đa vụ việc (aggregation) hoặc phân tích đa bước (multi-hop) giữa hành vi thực tế và chế tài pháp luật (Q3, Q4, Q5, Q6). Trong phạm vi 6 câu hỏi thử nghiệm của lab, GraphRAG thể hiện ưu thế vượt trội: đạt recall **1.00 (100%)** trên toàn bộ 6 câu và judge trung bình **1.83/2** (so với 0.43 và 1.00 của Flat RAG), giải quyết tốt sự phân mảnh ngữ cảnh nhờ các quan hệ tri thức có cấu trúc qua node cầu nối `Crime` và quan hệ `INVOLVES`.
> - **Lưu ý đánh đổi:** Đây là kết luận thực nghiệm trong phạm vi corpus và các câu hỏi benchmark của bài lab; không nên khái quát hóa rằng mọi bài toán cross-KB đều bắt buộc phải dùng GraphRAG. Với các bài toán có ngân sách tài nguyên khắt khe hoặc khối lượng truy vấn lớn, chi phí xây dựng đồ thị ($0.00929) và độ trễ xử lý (4.33s) của GraphRAG là sự đánh đổi cần được cân nhắc kỹ lưỡng.

---

## 5. Tự kiểm (5 điểm)

Log kiểm thử tự động offline (48 tests pass):
```
$ pytest tests/ -q -p no:cacheprovider
................................................                         [100%]
48 passed in 0.31s
```

Log kiểm thử self-check (`bench_kg.py --check` trên graph nhỏ 1 bài báo):
```
$ python bench_kg.py --check
[OK] Dữ liệu: 18 điều luật, 20 bài báo
[OK] KG-1 link_entity
[OK] Neo4j kết nối được
[provider] chat = openrouter:openai/gpt-4o-mini | embedding = openrouter:openai/text-embedding-3-small
[OK] KG-2 build_graph: 146 node / 289 cạnh, đường xuyên 2 KB dài 2 cạnh
[OK] KG-3 context: 13 dữ kiện, có Điều 251
[OK] KG-4 GraphRAGAgent.answer
[OK] Chi phí check: 1 lần gọi LLM, $0.00064. Graph nhỏ (luật + 1 bài) vẫn còn trong Neo4j để bạn xem; chạy --judge để dựng graph đầy đủ.
```
*(Ghi chú: Lệnh `--check` chỉ nạp luật và 1 bài báo kiểm thử nên kích thước đồ thị là 146 node / 289 cạnh; sau đó lệnh `--judge` đã xây dựng toàn bộ đồ thị 20 bài báo đạt 206 node / 382 cạnh khớp với benchmark cuối).*

Ảnh minh chứng Neo4j Browser:
- `report/img/kg_count.png`: Thống kê toàn bộ các label và count trên đồ thị cuối (206 nodes, 382 rels).
- `report/img/kg_cross_kb.png`: Đường đi xuyên 2 KB từ Person (Lê Minh Thành) qua Case, Crime sang Article 251 và Clause.
- `report/img/kg_my_case.png`: Minh chứng vụ án của nhân vật khác Lê Minh Thành (Ngô Việt Dũng trong Vụ tổ chức sử dụng ma túy tại Sầm Sơn - liên kết Điều 255 BLHS).

## Vấn đề gặp phải (không tính điểm)

Lỗi chưa giải quyết được: Không có vi phạm nào về mặt hợp đồng code (KG-1..KG-4) hay kiểm thử tự động (48/48 unit tests passed, self-check 7/7 `[OK]`, benchmark tự động có LLM judge hoàn tất đủ 12 kết quả và ảnh minh chứng đồng bộ). Tuy nhiên, đồ thị vẫn phản ánh trung thực các hạn chế kỹ thuật cố hữu của baseline ontology đã được phân tích ở Mục 3:
1. **Phân mảnh Case và nhập nhằng nguồn gốc tang vật:** LLM trích xuất độc lập từng bài báo dẫn đến việc chia tách sự kiện Sầm Sơn và buồng bệnh Viện Pháp y tâm thần thành hai Case riêng biệt.
2. **Trùng lặp node Substance do phân biệt chữ hoa/thường:** Tồn tại song song `Ketamine`/`ketamine`, `Cần sa`/`cần sa`.
3. **Chưa mô hình hóa số học ngưỡng khối lượng trong Điều luật:** Vẫn cần LLM suy luận ngữ cảnh để chọn Khoản 4 Điều 250 cho vụ 9,6kg MDMA.

