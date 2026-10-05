# Bằng Chứng Lỗi và Dữ Liệu Thực Tế Trên Đồ Thị Cuối (S6)

## 1. Thống kê Node và Relationship hiện tại
- **Tổng số Node**: 206
- **Tổng số Quan hệ**: 382

Chi tiết theo nhãn Node:
- `Clause`: 99
- `Person`: 37
- `Article`: 18
- `Substance`: 18
- `Case`: 14
- `Crime`: 13
- `Location`: 7

Chi tiết theo loại Cạnh:
- `[:MENTIONS]`: 169
- `[:HAS_CLAUSE]`: 99
- `[:INVOLVED_IN]`: 44
- `[:INVOLVES]`: 24
- `[:CHARGED_WITH]`: 19
- `[:LOCATED_IN]`: 14
- `[:DEFINES]`: 13

## 2. Truy vấn: Case liên quan MDMA
```cypher
MATCH (k:Case)-[r:INVOLVES]->(s:Substance {name:'MDMA'})
RETURN k.name, k.doc_id, r.amount
ORDER BY k.doc_id, k.name;
```
Kết quả thực tế:
- Case: `Vụ vận chuyển ma túy từ Đức về Việt Nam` | doc_id: `news-100260917203001265` | amount: `4.3kg`
- Case: `Vụ góp tiền mua ma túy tại Hà Nội` | doc_id: `news-100260918080821054` | amount: `5 viên`
- Case: `Vụ án tại Viện Pháp y tâm thần Trung ương` | doc_id: `news-100260924105118645` | amount: ``
- Case: `Vụ tổ chức sử dụng ma túy tại Sầm Sơn` | doc_id: `news-100260930085028036` | amount: `0,686g`

## 3. Truy vấn: Trùng lặp biến thể cách viết tên chất (Case-insensitive)
```cypher
MATCH (s:Substance)
WITH toLower(s.name) AS normalized, collect(s.name) AS names
WHERE size(names) > 1
RETURN normalized, names;
```
Kết quả thực tế:
- `ketamine`: ['Ketamine', 'ketamine']
- `cần sa`: ['Cần sa', 'cần sa']
- `methamphetamine`: ['methamphetamine', 'Methamphetamine']

## 4. Truy vấn: Một người tham gia nhiều Case
```cypher
MATCH (p:Person)-[:INVOLVED_IN]->(k:Case)
WITH p.name AS person,
     collect(DISTINCT {name:k.name, doc_id:k.doc_id}) AS cases
WHERE size(cases) > 1
RETURN person, cases;
```
Kết quả thực tế:
- Person `Dương Minh Tuấn` (4 cases):
  * Case: `Vụ bắt giang hồ 'Hoàng Nato' và 126 người liên quan 8 đường dây ma túy` (doc_id: `news-100260920221957595`)
  * Case: `Vụ bắt giữ TikToker Phannhibeauty và giang hồ 'Hoàng Nato'` (doc_id: `news-100260922111804786`)
  * Case: `Vụ sử dụng ma túy etomidate của Hoàng Nato và Phan Kim Nhi` (doc_id: `news-100260924095400982`)
  * Case: `Vụ bắt 'Hoàng Nato' và triệt phá 8 đường dây ma túy` (doc_id: `news-100260925144412498`)
- Person `Phan Kim Nhi` (3 cases):
  * Case: `Vụ bắt giữ TikToker Phannhibeauty và giang hồ 'Hoàng Nato'` (doc_id: `news-100260922111804786`)
  * Case: `Vụ sử dụng ma túy etomidate của Hoàng Nato và Phan Kim Nhi` (doc_id: `news-100260924095400982`)
  * Case: `Vụ bắt 'Hoàng Nato' và triệt phá 8 đường dây ma túy` (doc_id: `news-100260925144412498`)
- Person `Lê Văn Đông` (2 cases):
  * Case: `Vụ án tại Viện Pháp y tâm thần Trung ương` (doc_id: `news-100260924105118645`)
  * Case: `Vụ tổ chức sử dụng ma túy tại Sầm Sơn` (doc_id: `news-100260930085028036`)
- Person `Nguyễn Thị Mai Anh` (2 cases):
  * Case: `Vụ án tại Viện Pháp y tâm thần Trung ương` (doc_id: `news-100260924105118645`)
  * Case: `Vụ tổ chức sử dụng ma túy tại Sầm Sơn` (doc_id: `news-100260930085028036`)

## 5. Truy vấn: Các khoản của Điều 250 đề cập MDMA
```cypher
MATCH (a:Article {doc_id:'blhs-dieu-250'})
      -[:HAS_CLAUSE]->(cl:Clause)
      -[:MENTIONS]->(:Substance {name:'MDMA'})
RETURN cl.number, cl.penalty
ORDER BY cl.number;
```
Kết quả thực tế:
- Khoản 1: `phạt tù từ 02 năm đến 07 năm`
- Khoản 2: `phạt tù từ 07 năm đến 15 năm`
- Khoản 3: `phạt tù từ 15 năm đến 20 năm`
- Khoản 4: `phạt tù 20 năm, tù chung thân hoặc tử hình`

## 6. Truy vấn: Các Case không có liên kết CHARGED_WITH
Số lượng Case không có CHARGED_WITH: 1
- Case `Vụ tông cảnh sát giao thông ở An Giang` (doc_id: `news-100260926112415229`): Nguyễn Minh Nhân đã tông vào Thiếu tá Trần Ngọc Nam trong khi chạy xe không có giấy phép lái xe và sử dụng rượu, ma túy.
