# UX Review Report — Bản dịch PDF "Pâtisserie and Baking Foundations" (EN→VI)

**Ngày**: 2026-09-07
**Người thực hiện**: UX/UI Designer (đội hình mở rộng)
**Nguồn dữ liệu**: 13 cặp ảnh so sánh (gốc EN vs. dịch VI) do PM xem trực tiếp và mô tả lại
bằng văn bản; cộng dồn với 8 ảnh đã xem ở vòng trước (tổng 21 ảnh).
**Giới hạn phạm vi**: Báo cáo này phân tích HIỆN TƯỢNG HIỂN THỊ thuần tuý. Không điều tra
source code, không kết luận nguyên nhân kỹ thuật. Mục 3 chỉ là giả thuyết khởi đầu cho Tech Lead.

> ⚠️ Lưu ý về độ tin cậy đầu vào: người viết báo cáo KHÔNG trực tiếp xem ảnh. Toàn bộ quan sát
> đến từ mô tả bằng văn bản của PM (PM xác nhận đã verify bằng mắt). Các nhận định về tần suất
> và mức độ ở đây kế thừa độ tin cậy của mô tả đó, không phải đo đạc độc lập.

---

## 1. Phân loại nhóm hiện tượng (góc nhìn UX)

### UX-A — Overlap giữa 2 khối text liền kề theo trục dọc
Hai đoạn văn nằm kế nhau theo chiều dọc bị đè lên nhau, thường ở ranh giới chuyển đoạn: dòng
cuối của đoạn trên và dòng đầu của đoạn dưới in chồng tại cùng toạ độ.

Bằng chứng: trang 6 (2 điểm chồng — giữa trang và cuối trang, đều là văn xuôi thường); trang
chân dung Antonin Carême (block quote nghiêng chồng cả trước lẫn sau); trang "History of
Pâtisserie in France" (dày đặc, gần như mọi ranh giới đoạn); trang "Communard/Pâtisserie
Department" (đoạn trên đè vào heading "BỘ PHẬN BÁNH PÂTISSERIE" và đè dòng "phải báo cáo cho
bếp trưởng").

Đặc điểm UX quan trọng: lỗi xảy ra trên **văn xuôi bình thường**, không giới hạn ở phần tử
trang trí → không thể xử lý bằng cách chỉ "sửa các box đặc biệt".

### UX-B — Vỡ layout bên trong 1 box cỡ cố định
Text dịch dài hơn text gốc nhưng khung chứa giữ nguyên kích thước gốc → chữ bị nén, đè lên
nhau trong box, và tràn qua viền box đè lên nội dung bên cạnh.

Bằng chứng: box xám caption "Guillaume Tirel..." (trang 6) — nặng nhất trong toàn bộ 21 ảnh.
Cùng pattern ở org-chart cell và pull-quote xoay nghiêng ở vòng ảnh trước.

Đối chứng quan trọng: box chân dung xoay nghiêng "Antonin Carême"/"Auguste Escoffier" hiển thị
ĐÚNG → không phải mọi box trang trí đều hỏng; chỉ box có lượng text nhiều/dài mới hỏng. Suy ra
biến quyết định là **tỉ lệ giãn nở độ dài text so với sức chứa khung**, không phải "loại box".

### UX-C — Mất nội dung thành ô trắng (content loss thực sự) — MỚI
Không có chữ nào ở vị trí lẽ ra phải có chữ dịch. Khác hẳn UX-A/UX-B: ở đó chữ vẫn tồn tại
nhưng khó đọc; ở đây thông tin biến mất, người đọc không có cách nào biết mình đang thiếu gì.

Bằng chứng: trang "Fiche de Technique" — các ô phân loại nguyên liệu ("Dry goods"/"Dairy")
trống hoàn toàn; vài dòng trong "Progression" trống. Trang "Common Types of Honey"
(infographic 8 cột) — nhiều ô bullet trống, đồng thời các bullet còn lại chồng chéo lấn cột
kế bên. Trang bìa: 1 ô trắng nhỏ thừa dưới subtitle (nghi là mảnh sót của bước xoá text gốc).

Pattern: tập trung ở **layout dạng ô/lưới nhiều cell nhỏ** (bảng, infographic đa cột), không
thấy ở văn xuôi 1 cột.

### UX-D — Sai thứ tự đọc — MỚI
Nội dung không chỉ đặt sai vị trí mà đảo cả trật tự đọc logic: phần tử con xuất hiện PHÍA TRÊN
phần tử cha của nó.

Bằng chứng: trang "Nội dung" (mục lục 2 cột) — sub-entry "Hai chữ T: Nhiệt độ" (thuộc mục 4)
đè lên chính heading cha "4. Kỹ Thuật và Kỹ Năng Làm Bánh 172". Số trang 2 mục khác nhau
(Glossary 384, Index 391) dính thành cụm "391 384" tại cùng vị trí — thứ tự cũng bị đảo (391
đứng trước 384).

### UX-E — Font-size không nhất quán
Heading cùng cấp nhưng cỡ chữ khác nhau giữa các trang; trong cùng 1 box cũng có chữ to nhỏ
lệch nhau. (Quan sát của user, không đo đạc định lượng — cần QA đo lại bằng công cụ.)

Ghi chú UX: hiện tượng này có thể là **hệ quả**, không phải lỗi độc lập — nếu hệ thống có cơ
chế thu nhỏ font để nhét text dài vào khung, thì mỗi khung sẽ tự chọn 1 cỡ khác nhau, tạo ra
đúng cảm giác "to nhỏ không đều". Cần Tech Lead xác nhận có cơ chế đó không.

---

## 2. Severity & tần suất

| Nhóm | Hiện tượng | Severity | Tần suất / Pattern trang bị lỗi |
|------|-----------|----------|-------------------------------|
| **UX-C** | Mất nội dung (ô trắng) | **Blocker** — người đọc mất thông tin mà KHÔNG biết mình mất; sách dạy nghề, thiếu 1 bước "Progression" hoặc 1 phân loại nguyên liệu có thể làm hỏng công thức thật | Trung bình về số trang, nhưng 100% ở trang dạng bảng/infographic nhiều cell (Fiche de Technique, Common Types of Honey). Không thấy ở văn xuôi |
| **UX-A** | Overlap 2 block liền kề | **Critical** — nội dung còn nhưng phải giải mã từng dòng; đọc liên tục 1 chương là bất khả thi | **Cao nhất** — xuất hiện ở hầu hết trang có ≥2 đoạn văn. Nặng nhất ở trang nhiều đoạn ngắn (History of Pâtisserie in France). Nhẹ/không có ở trang ít text (bìa) và phần đầu trang trước heading đầu tiên |
| **UX-B** | Vỡ layout trong box cố định | **Critical** — box hỏng vừa mất nội dung của chính nó, vừa phá luôn văn bản xung quanh khi tràn viền | Xảy ra ở box có text dài. KHÔNG xảy ra ở box text ngắn (chân dung Carême/Escoffier) → tương quan với độ dài text, không phải loại box |
| **UX-D** | Sai thứ tự đọc | **Major** — người đọc hiểu sai cấu trúc phân cấp; ở mục lục, sai số trang khiến tra cứu hỏng | Thấp về số lượng, nhưng tập trung ở trang có phân cấp cha–con và cột số căn phải (mục lục). Đây là trang người đọc dùng ĐẦU TIÊN → ấn tượng xấu sớm |
| **UX-E** | Font-size không đều | **Minor–Major** — không chặn đọc, nhưng phá cảm giác chuyên nghiệp của 1 sách Le Cordon Bleu; làm mất tín hiệu phân cấp heading | Rải rác toàn sách, chưa định lượng |

**Quan sát baseline (rất giá trị)**: trang bìa gần sạch, và phần đầu trang "Communard" (trước
heading giữa trang) sạch, chỉ hỏng dần từ heading trở xuống. Điều này cho thấy lỗi **không
ngẫu nhiên** mà **tích luỹ theo chiều dọc trang**: càng xa điểm bắt đầu (đầu trang / đầu cột),
sai lệch càng lớn.

---

## 3. Giả thuyết nguyên nhân chung (khởi đầu cho Tech Lead — KHÔNG phải kết luận)

**Giả thuyết chính — "Text dịch dài hơn nhưng khung chứa không đổi, sai lệch cộng dồn":**

Tiếng Việt sau dịch dài hơn tiếng Anh đáng kể (thường +20–40% ký tự do dấu, từ ghép, hư từ).
Nếu engine giữ nguyên hộp/toạ độ layout của bản gốc và chỉ thay nội dung chữ, thì mỗi khối
text sẽ cần nhiều dòng hơn khung dành cho nó. Một mô hình duy nhất giải thích được cả 5 nhóm:

- Block tràn xuống chiếm chỗ block kế tiếp, mà block kế tiếp vẫn giữ toạ độ cũ → **UX-A**, và
  sai lệch cộng dồn theo chiều dọc → giải thích đúng hiện tượng "đầu trang sạch, cuối trang nát".
- Khung cứng không giãn được, text quá dài → nén/chồng trong box và tràn viền → **UX-B**; box
  text ngắn (đủ chỗ) không hỏng → khớp với đối chứng Carême/Escoffier.
- Ở lưới nhiều cell nhỏ, khi text không nhét vừa cell, nội dung có thể bị cắt bỏ thay vì tràn
  → **UX-C** (ô trắng). Cell càng nhỏ, xác suất mất càng cao → khớp với bảng/infographic.
- Khi các block bị dịch chuyển tự do khỏi vị trí gốc, trật tự dọc giữa cha–con không còn được
  bảo đảm → **UX-D**.
- Nếu có cơ chế auto-shrink font để cứu text quá dài, mỗi khung tự chọn 1 cỡ → **UX-E**.

**Giả thuyết phụ (cần loại trừ)**: bước xoá text gốc và bước vẽ text dịch là 2 bước độc lập —
xoá thành công nhưng vẽ thất bại một phần thì ra ô trắng (UX-C, và mảnh trắng thừa ở trang bìa).
Nếu đúng, UX-C là lỗi RIÊNG chứ không phải hệ quả của độ dài text — Tech Lead nên kiểm chứng
điểm này trước, vì nó quyết định fix 1 chỗ hay 2 chỗ.

**Câu hỏi gợi ý cho Tech Lead**: engine xử lý thế nào khi text dịch không vừa khung gốc — giãn
khung, thu font, xuống dòng tràn ra ngoài, hay cắt bỏ? Ba hành vi khác nhau này tương ứng chính
xác với UX-B, UX-E, UX-A và UX-C.

---

## 4. Definition of Done (UX) — tiêu chí QA kiểm tra

### DoD-UX-01 — Không có chồng lấn text (chặn release)
Trên mẫu kiểm tra tối thiểu 20 trang trải đều các loại layout (văn xuôi, có box, bảng,
infographic, mục lục), **không có 2 khối text nào có hộp bao (bounding box) giao nhau quá 5%
diện tích của khối nhỏ hơn**. Ngưỡng 5% để bỏ qua sai số render/khoảng đệm, không phải để dung
thứ chồng chữ thật.
*Cách kiểm*: trích bounding box của các text block trên trang dịch, tính giao nhau từng cặp.
Bất kỳ cặp nào vượt ngưỡng → fail, ghi rõ số trang.

### DoD-UX-02 — Không mất nội dung (chặn release)
Với mỗi trang, **số khối text và tổng số ký tự (không tính khoảng trắng) của bản dịch phải ≥
70% bản gốc**, và **không có khối text nào ở bản gốc có nội dung mà bản dịch rỗng**. Đối chiếu
theo vị trí khối (block-level), không chỉ so tổng ký tự toàn trang — vì tổng có thể vẫn đạt
trong khi vài ô riêng lẻ trống.
*Cách kiểm*: đây chính là kịch bản R6-03 (live E2E, kiểm nội dung output cuối) áp cho từng
trang. Đặc biệt bắt buộc chạy trên 2 trang chứng cứ đã biết: "Fiche de Technique" và "Common
Types of Honey".

### DoD-UX-03 — Box cỡ cố định phải chứa hết text (chặn release)
Với mọi khung có viền/nền (sidebar, callout, cell bảng, org-chart, pull-quote): text dịch phải
nằm **hoàn toàn bên trong** viền khung — hoặc bằng cách khung tự giãn, hoặc bằng cách tự động
giảm cỡ chữ (nhưng **không nhỏ hơn 70% cỡ chữ gốc của khung đó**, dưới ngưỡng này coi như fail
và phải cho giãn khung). Không chấp nhận chữ tràn qua viền dù chỉ 1 dòng.

### DoD-UX-04 — Thứ tự đọc và tính nhất quán typography (non-blocking, nên đạt)
- Thứ tự dọc giữa heading cha và các entry con phải giữ nguyên như bản gốc (kiểm thủ công
  trang mục lục và mọi trang có danh sách phân cấp).
- Trong cùng 1 trang, các heading cùng cấp phải có cùng cỡ chữ; sai lệch cỡ chữ giữa các heading
  cùng cấp trên toàn sách không quá 1 bậc (~2pt).

**Điều kiện release tổng**: DoD-UX-01, 02, 03 đều PASS trên bộ mẫu ≥20 trang thì mới được đánh
`ready_for_release`. DoD-UX-04 fail chỉ ghi nhận là suggestion, không chặn.
