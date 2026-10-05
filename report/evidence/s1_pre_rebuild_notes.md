# Snapshot Lịch Sử Trước Khi Rebuild (Commit 92c57d8)

- Thời điểm kiểm tra: 2026-10-05
- Neo4j URI: bolt://localhost:7687

## 1. Thống kê Node theo Label
- **Clause**: 99
- **Person**: 38
- **Article**: 18
- **Substance**: 17
- **Case**: 14
- **Crime**: 13
- **Location**: 7

**Tổng cộng**: 206 nodes, 384 relationships.

## 2. Các Case liên quan MDMA hiện tại (k:Case)-[:INVOLVES]->(s:Substance)
- Case: `Vụ tổ chức sử dụng ma túy tại Sầm Sơn` | doc_id: `news-100260930085028036` | substance: `MDMA` | amount: `0,686g`
- Case: `Vụ án tại Viện Pháp y tâm thần Trung ương` | doc_id: `news-100260924105118645` | substance: `MDMA` | amount: ``
- Case: `Vụ góp tiền mua ma túy tại Hà Nội` | doc_id: `news-100260918080821054` | substance: `MDMA` | amount: `5 viên`
- Case: `Vụ vận chuyển ma túy từ Đức về Việt Nam` | doc_id: `news-100260917203001265` | substance: `MDMA` | amount: `9.6kg`

## 3. Trùng lặp tên Substance (khác chữ hoa/thường)
- Normalized: `methamphetamine` -> Variants: ['Methamphetamine', 'methamphetamine']
- Normalized: `ketamine` -> Variants: ['Ketamine', 'ketamine']

## 4. Thực thể Người liên quan Cái Quang Huy
- Person: `Cái Quang Huy` | Case: `Vụ vận chuyển ma túy từ Đức về Việt Nam` | doc_id: `news-100260917203001265`

## 5. Các Khoản của Điều 250 đề cập MDMA
- Khoản 1: penalty = `phạt tù từ 02 năm đến 07 năm`
- Khoản 2: penalty = `phạt tù từ 07 năm đến 15 năm`
- Khoản 3: penalty = `phạt tù từ 15 năm đến 20 năm`
- Khoản 4: penalty = `phạt tù 20 năm, tù chung thân hoặc tử hình`

## 6. Các vấn đề cần xác minh trên đồ thị cuối (R5, R8)
1. **Ba doc_id không tồn tại trong phần E4 của REPORT_KG.md**: Các doc_id `news-100260918080821051`, `news-100260918080821053`, `news-100260918080821050` trong báo cáo cũ không có trong thư mục `data/drug_news/`. Báo cáo mới phải dùng doc_id thật.
2. **Query E2**: Cần kiểm tra xem Clause 1 của Điều 250 có liên kết MENTIONS MDMA không hay chỉ các khoản 2, 3, 4.
3. **Case Cái Quang Huy**: Tên vụ án trích xuất từ tin tức có thể bị biến thể giữa các lần gọi LLM.
4. **Substance trùng khác chữ hoa/thường**: Kiểm tra có xuất hiện cả `MDMA` và `mdma` hoặc `Ma túy` và `ma túy`.
5. **Q6 nhập nhằng giữa sự kiện Sầm Sơn và tang vật thu tại viện**: Cần đối chiếu chính xác các Case được link tới MDMA.
