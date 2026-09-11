# Domain Expert (PDF/typography) — phản biện BL-04 (Architecture.md §6.22)

- **Ngày**: 2026-09-11
- **Vai**: Domain Expert one-off (Protocol D), lần 1/2 cho hạng mục BL-04
- **Phạm vi đọc**: `docs/Architecture.md` 6798-7161 · `docs/design-log.md` 5726-5886 (BL4.1–BL4.7) ·
  `src/core/job_orchestrator.py` 1733-1920 · `src/services/babeldoc_runner.py` ·
  `src/babeldoc_shim/sitecustomize.py` 596-744 · `src/postprocess/chunk_merge.py` ·
  `src/services/layout_qa.py` · source thật babeldoc 0.6.4 tại
  `/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/` (viết tắt `<BD>/`)
- **Đo thật**: job `1ee1fdee-746e-4d3b-a54c-d27f7f2aa763` (Le Cordon Bleu 418 trang, chạy 2026-09-09
  bằng babeldoc sau khi Bug #9 tắt font_shrink), so từng trang `data/uploads/f07b3194-..._Le-Cordon-Bleu-...pdf`
  ↔ `data/outputs/1ee1fdee-.../translated_vi.pdf` bằng PyMuPDF 1.28.2.

---

## Kết luận ngắn

**Cơ chế cốt lõi của thiết kế là ĐÚNG** — tôi đã tự đọc lại `<BD>/format/pdf/document_il/midend/typesetting.py`
và `<BD>/.../backend/pdf_creater.py` và xác nhận độc lập cả 3 điểm Tech Lead nêu (composition bị xoá
trắng trước typeset · chỉ ghi lại khi `all_units_fit` · `paragraph.scale` là `None` ở đúng ca drop).
Điểm hook `create_render_units_for_page` là **điểm chặn đúng** cho kênh mất-chữ-do-không-vừa-khung.

**Nhưng CHƯA nên cho Dev implement nguyên trạng.** Có 4 điểm phải sửa trước (F1–F4), trong đó 2 điểm
là lỗ hổng đúng nghĩa chứ không phải góp ý phong cách:

| # | Vấn đề | Mức |
|---|---|---|
| **F1** | Chunk **chồng lấn 2 trang** và `merge_chunk_pdfs` **vứt bỏ** 2 trang đầu của mọi chunk sau chunk 0 → drop báo trên các trang đó là **false positive**, đồng thời trang chồng lấn bị **đếm 2 lần**. Dedupe theo `debug_id` KHÔNG bắt được vì `debug_id` sinh lại mỗi lần chạy | **BLOCKING** |
| **F2** | Dòng `header` chỉ chứng minh *patch đã cài*, KHÔNG chứng minh *hook đã chạy trên các trang của chunk* → trạng thái 3 yếu hơn nhiều so với mức thiết kế tự nhận | **BLOCKING** |
| **F3** | Shim chỉ thấy **1 trong ít nhất 3 kênh mất chữ**. Kênh lọc góc xoay ở `il_creater.on_lt_char:968-974` xảy ra **trước** khi ký tự thành IL → shim mù hoàn toàn. Đã **đo được** trên trang 19 và 31 | **BLOCKING (phải ghi rõ vào tài liệu)** |
| **F4** | `grep -rln "LayoutQaFinding" src/ web/ scripts/` → **không có API/UI nào đọc** bảng `layout_qa_findings`. Câu "đã có UI/QA đọc" trong §6.22.6 là **sai**. Ghi finding vào bảng không ai đọc ≈ vẫn không có cờ cảnh báo | **BLOCKING (quyết định, không phải code)** |

**Và quan trọng nhất cho Dev: gate E2E ở §6.22.9 đang nhắm SAI tài liệu.** Chunk 0 (40 trang đầu
Le Cordon Bleu) **không có ca drop nào** — đo thật, xem §Q4. Ca drop thật duy nhất trong cả 418
trang nằm ở **trang 230, thuộc chunk 5 (`--pages 199-240`)**. Chạy gate trên chunk 0 sẽ ra "0 drop"
và không chứng minh được gì.

---

## Phần A — Những điểm tôi đã tự verify lại và THẤY ĐÚNG

Ghi ra để PM biết phạm vi đã phủ, và để Tech Lead không phải verify lại lần nữa.

| # | Claim của thiết kế | Kết quả | Nguồn tôi tự đọc |
|---|---|---|---|
| A1 | Engine thật = babeldoc **0.6.4** (uv tool riêng); `0.2.33` là dep bắc cầu chết của pdf2zh | **ĐÚNG** | `ls .../uv/tools/{babeldoc,pdf2zh}/.../babeldoc-*.dist-info`; shebang `/Users/hieutt/.local/bin/babeldoc` dòng 1 |
| A2 | `render_paragraph()` xoá trắng composition **trước** khi typeset lại | **ĐÚNG** | `<BD>/format/pdf/document_il/midend/typesetting.py:1277` (`paragraph.pdf_paragraph_composition = []`, nhánh `else` của `all(can_passthrough)`) |
| A3 | Chỉ ghi lại layout khi `all_units_fit` | **ĐÚNG** | `typesetting.py:986-1002`; hết vòng `while scale >= min_scale` (`:974`, `min_scale=0.1` `:968`) → `return min_scale, final_typeset_units` với `final_typeset_units = None` (`:1076`) |
| A4 | `paragraph.scale is None` ở ca drop là **thông tin đúng**, không phải thiếu dữ liệu | **ĐÚNG, và mạnh hơn TL trích** — tôi grep toàn bộ `document_il/`: `paragraph.scale` chỉ được gán ở **đúng 2 chỗ**, `typesetting.py:989` (nhánh fit) và `:1266` (nhánh passthrough). Không có chỗ thứ ba. Nên ở ca drop nó chắc chắn `None` | `grep -rn "paragraph\.scale = " <BD>/format/pdf/document_il/` |
| A5 | `create_render_units_for_page` chạy **đúng 1 lần/trang**, sau typesetting | **ĐÚNG** | `pdf_creater.py:1698` được gọi từ `update_page_content_stream`, mà `update_page_content_stream` chỉ xuất hiện **1 lần** trong cả file, ở vòng `for page in self.docs.page` của `write()` (`:1465-1466`) |
| A6 | Nhánh debug không đi qua hàm này | **ĐÚNG, và không bao giờ chạy trong production** | `write_debug_info` gọi thẳng `render_paragraph_to_char` (`:1165`), và `write_debug_info` chỉ được gọi dưới `if translation_config.debug:` (`:1537-1541`); `BabeldocRunner` không bao giờ truyền `--debug` |
| A7 | `page.page_number` = chỉ số **0-based của tài liệu GỐC** | **ĐÚNG, và tôi có bằng chứng chắc hơn TL** — TL suy từ `pdf[page.page_number].xref`. Bằng chứng trực tiếp: `legacy_parse.py:77-84` gán `page.pageno = pageno` từ `enumerate(PDFPage.create_pages(doc))` trên **toàn tài liệu**, rồi `il_creater.create_il()` (`:1347-1353`) **lọc** `self.docs.page` xuống chỉ còn trang được chọn mà **giữ nguyên** `page_number` | `legacy_parse.py:77-84`, `il_creater.py:1347-1353`, `il_creater.py:968` (`on_page_number`) |
| A8 | Predicate `_has_rendered_chars` khớp định nghĩa của chính babeldoc | **ĐÚNG** — tương đương `render_paragraph_to_char` (`pdf_creater.py:810-836`): composition không character và không formula-có-char → `chars` rỗng; nhánh "Unknown composition type" cũng `continue` (không thêm char) ở cả 2 bên | `pdf_creater.py:810-836` |
| A9 | Sidecar đặt trong `output_dir` an toàn với retry | **ĐÚNG, nhưng là phụ thuộc TÌNH CỜ — phải viết vào spec** | `job_orchestrator.py:1801-1802`: `_call_translator()` `shutil.rmtree(chunk_output_dir)` ở **đầu MỖI attempt** (kể cả attempt ngầm trong `with_retry`, và cả lần resume sau crash). Nếu Dev đặt sidecar ở bất kỳ đâu **ngoài** `chunk_output_dir`, bản ghi của attempt hỏng sẽ sống sót và bị đếm chung với attempt thành công |
| A10 | `page_number = chunk.page_start` cho finding "unavailable" là 1-based | **ĐÚNG** | `job_orchestrator.py:1901` dùng `chunk.page_start - 1` để index PyMuPDF ⇒ `page_start` là 1-based |
| A11 | `LayoutQaFindingData` / `persist_findings` nhận được `detail` dict tự do; `critical` có trọng số | **ĐÚNG** | `layout_qa.py:99-107`, `:451-479` (`json.dumps(..., ensure_ascii=False)`), `_SEVERITY_WEIGHT` `:86` |
| A12 | babeldoc nới box xuống dưới rồi sang phải trước khi bỏ cuộc | **ĐÚNG** | `typesetting.py:1020-1056` (`get_max_bottom_space` / `get_max_right_space`, cập nhật `paragraph.box`) |
| A13 | Vòng giảm scale chỉ chạy quá 1 vòng khi có `debug_id`, và `debug_id` luôn có | **ĐÚNG** | `typesetting.py:1008-1009`; `paragraph_finder.py:500`, `:874`, `:911` (`debug_id=generate_base58_id()`) |
| A14 | Quyết định KHÔNG tái dùng `overflow_reports` | **ĐỒNG Ý** — lập luận đúng. Bổ sung 1 lý do nữa TL chưa nêu: `OverflowReport` có `original_text` (chữ **gốc EN** trước khi co), còn ở ca drop thứ mất là **bản dịch VI** (`paragraph.unicode` đã bị ghi đè bằng bản dịch tại `il_translator.py:1004`). Cùng tên cột, khác hẳn ngữ nghĩa — nhét vào là tạo dữ liệu sai kiểu tinh vi nhất | `il_translator.py:1004` |

---

## Phần B — Phát hiện BẮT BUỘC sửa trước khi Dev implement

### F1 (BLOCKING) — Trang chồng lấn giữa các chunk: false positive + đếm 2 lần

**Mô tả.** `calculate_chunks(chunk_size=40, overlap=2)` (`src/core/chunking.py:28`) sinh các chunk
**chồng nhau 2 trang**. Đo thật trên job `1ee1fdee` (`chunks` table):

```
chunk 0: 1-40    (overlap_start/end = NULL)
chunk 1: 39-80   (overlap 39-40)
chunk 2: 79-120  (overlap 79-80)
...
chunk 10: 399-418 (overlap 399-400)
```

`merge_chunk_pdfs` (`src/postprocess/chunk_merge.py:85-91`) **bỏ** phần đầu chồng lấn của mọi chunk
sau chunk 0: `actual_start = chunk.overlap_end + 1`. Nghĩa là **bản render trang 39-40 của chunk 1
không bao giờ có mặt trong PDF cuối cùng** — bản của chunk 0 mới là bản người dùng thấy.

**Hậu quả nếu bỏ qua.** Thiết kế hiện tại map **toàn bộ** `drop_report` của chunk sang finding:

1. **False positive**: drop xảy ra ở trang 39 trong lần chạy của chunk 1 → ghi finding `critical`
   "mất nội dung trang 39", trong khi trang 39 trong file giao cho người dùng là bản của chunk 0 và
   hoàn toàn bình thường. QA mở PDF ra soi tay sẽ thấy chữ vẫn còn → mất niềm tin vào chính cơ chế
   cảnh báo (đúng loại hỏng mà một cờ QA không được phép mắc).
2. **Đếm 2 lần**: nếu cùng 1 đoạn bị drop ở cả 2 lần chạy → 2 finding cho 1 sự cố. Dedupe
   `(page_number, debug_id)` **không cứu được**: `debug_id` là `generate_base58_id()`
   (`paragraph_finder.py:46`, `:500`) sinh **ngẫu nhiên mỗi lần chạy**, nên 2 lần chạy cho ra 2 id
   khác nhau trên cùng 1 đoạn.
3. Tệ hơn: hai lần chạy **không** nhất thiết cho cùng kết quả. `preprocess_document` ép
   `optimal_scale` của mọi đoạn xuống **mode của toàn bộ tập trang trong CHÍNH lần gọi đó**
   (`typesetting.py:919-935`). Chunk 0 (trang 1-40) và chunk 1 (trang 39-80) có tập trang khác nhau
   → mode khác nhau → cùng 1 đoạn ở trang 39 có thể fit ở chunk 0 và drop ở chunk 1, hoặc ngược lại.
   Nên đây không phải "trùng lặp vô hại", mà là **hai phép đo trên hai vật thể khác nhau**, trong đó
   chỉ một cái được giao cho người dùng.

**Quy mô đo được**: 10/11 chunk × 2 trang = **20 trang/cuốn** nằm trong vùng rủi ro này.

**Đề xuất.** Trong `_process_chunk()`, lọc bản ghi drop xuống đúng **dải trang sống sót** của chunk:

- `surviving_start = chunk.overlap_end + 1 if (chunk_index > 0 and overlap_end is not None) else chunk.page_start`
- Chỉ giữ record có `surviving_start <= page_number_1based <= chunk.page_end`.

**Và tách quy tắc đó thành một hàm dùng chung** với `merge_chunk_pdfs` (ví dụ
`surviving_page_range(chunk, position) -> tuple[int, int]`), thay vì chép logic lần 2. Hai chỗ tự
tính "trang nào của chunk này sống sót" là đúng khuôn Bug #5: hai bản sao sẽ lệch nhau lúc ai đó
sửa một bên.

**Ghi chú kèm (KHÔNG blocking, backlog riêng)**: vòng ghi `OverflowReport` của nhánh pdf2zh
(`job_orchestrator.py:1901`) có **cùng** lỗi này — `range(chunk.page_start - 1, ...)` không loại trang
chồng lấn, nên `overflow_reports` của nhánh pdf2zh cũng đang đếm 2 lần trên 20 trang/cuốn. Đây là lỗi
có sẵn từ BL-01, không thuộc BL-04, nhưng nếu Dev tách hàm chung ở trên thì sửa luôn là gần như miễn phí.

---

### F2 (BLOCKING) — `header` chứng minh sai thứ: "patch đã cài" ≠ "đã quan sát"

**Mô tả.** §6.22.4 ghi header được ghi "1 lần lúc patch được áp thành công". Patch được áp trong
`_PatchingLoader.exec_module` (`sitecustomize.py:626-637`), tức **lúc import module**, trước khi
render bất cứ trang nào. Vậy `available=True` chỉ chứng minh module `pdf_creater` đã được import và
patch không ném lỗi. Nó **không** chứng minh `create_render_units_for_page` đã thực sự chạy trên
trang nào.

Thêm 2 sắc thái:

- macOS dùng `mp.set_start_method("spawn")` (`<BD>/main.py:951`) → mọi process con re-import
  `sitecustomize` qua `PYTHONPATH` → **nhiều dòng header** trong cùng 1 file. Spec hiện viết "dòng
  đầu tiên **luôn** là header" — không đúng: thứ tự append giữa các process không được đảm bảo, và
  parser không được phép dựa vào vị trí dòng.
- Ngược lại, phần render chạy trong **process chính**; `subset_fonts_in_subprocess`
  (`pdf_creater.py:1220`) là process con duy nhất và nó **không** render paragraph. Nên thực tế chỉ
  có **một** process ghi dòng `drop`.

**Hậu quả nếu bỏ qua.** Trạng thái 3 ("không đo được") — đúng cái TL tự nhận là "điểm dễ sai nhất của
cả thiết kế" — chỉ bắt được ca thô (shim tắt / sai version). Nó **không** bắt được ca tinh vi hơn:
patch cài xong nhưng hook không chạy đủ trang (babeldoc đổi đường gọi ở bản sau, trang bị bỏ qua vì
exception trong `write()`, v.v.). Khi đó hệ thống lại báo "đo được, 0 drop" = tin tốt giả — đúng kiểu
Bug #5 mà BL4.5 viện dẫn để biện minh cho chính thiết kế này.

**Đề xuất.** Nhờ A7, ta **biết trước chính xác** số trang mà hook phải chạy: đúng bằng số trang trong
`--pages` của chunk (`create_il()` đã lọc `docs.page` xuống đúng tập đó). Vậy:

1. Shim ghi thêm 1 record **mỗi trang** đi qua hook:
   `{"type":"page","page_number_1based":N,"paragraph_count":M,"dropped_count":K}`.
2. `BabeldocRunner` assert `len(observed_pages) == chunk.page_end - chunk.page_start + 1` và
   `observed_pages == set(range(page_start, page_end+1))`.
3. Thiếu trang → finding riêng `babeldoc_drop_report_incomplete` (`severity="major"`),
   `detail={"expected": [...], "observed": [...]}`.
4. Parser **không** giả định dòng đầu là header; chấp nhận N dòng header, chỉ cần ≥1.

Chi phí: vài dòng. Lợi ích: biến trạng thái 3 từ "kiểm tra hình thức" thành "kiểm tra thật", và cho
ta luôn mẫu số để nói "0 drop trên 42/42 trang đã quan sát" thay vì "0 drop".

---

### F3 (BLOCKING — phải ghi rõ vào tài liệu) — Shim chỉ phủ 1 trong ít nhất 3 kênh mất chữ

**Mô tả.** Thiết kế (và cả tiêu đề §6.22 "Phát hiện babeldoc TỰ bỏ đoạn") ngầm để người đọc hiểu
"drop report = mọi trường hợp babeldoc làm mất nội dung". **Không đúng.** Có ít nhất 3 kênh, shim chỉ
thấy 1:

| Kênh | Cơ chế | Shim có thấy? |
|---|---|---|
| (1) Không vừa khung sau khi bóp tới `min_scale` | composition rỗng ở `pdf_creater` | **CÓ** — đây là cái §6.22 thiết kế |
| (2) **Lọc góc xoay lúc parse** | `il_creater.on_lt_char:971-974`: `rotation_angle = atan2(b, a)`; nếu **không** thuộc `[-0.1, 0.1] ∪ [89.9, 90.1]` thì `return` — ký tự **không bao giờ** thành `PdfCharacter`, không thuộc paragraph nào | **KHÔNG** — không có paragraph nào để mà "rỗng". Cả sentinel ở `pdf_creater:832` cũng không kêu |
| (3) Ký tự không có font id | `il_creater.on_lt_char:969-970`: `if char.aw_font_id is None: return` | **KHÔNG** — cùng lý do |

**Nguồn xác thực cho (2) — đã ĐO, không suy đoán.** Trên chính chunk 0 mà §6.22.9 định dùng làm gate:

- Trang 19 nguồn có 2 block: `'1'` (ngang) và `'History of Pâtisserie in France'`
  — bbox `(599.4, 156.4, 633.0, 528.3)`, `dir = (0.0, 1.0)` theo `page.get_texttrace()`, size 31pt.
- Trang 19 output **chỉ còn** `'1'`.
- Trang 31: y hệt — mất `'A Life and Career in the Pastry Kitchen'` (bbox `(591.4, 156.4, 625.0, 643.7)`).
- `dir=(0,1)` trong hệ toạ độ PyMuPDF (y hướng xuống) ⇒ ma trận chữ trong PDF có `b < 0` ⇒
  `atan2(b, a) ≈ -90°` ⇒ **rơi ra ngoài** cả 2 khoảng chấp nhận ở `il_creater.py:973`.
  *(Mức chắc chắn: ĐÃ ĐO phần `dir` và phần chữ biến mất; phần quy đổi `dir` → dấu của `b` là suy
  luận từ quy ước toạ độ, **NGHI NGỜ — nên Dev xác nhận bằng 1 lần chạy thật**: nếu là -90 thì shim
  sẽ KHÔNG ra record cho trang 19/31; nếu là +90 thì shim SẼ ra record — và khi đó phát sinh vấn đề
  ngược lại là **trùng lặp** với `rotated_text_overlay_flag`, phải xử lý.)*
- Quy mô: **52/418 trang** của cuốn này có chữ dọc; tổng ký tự dọc nguồn **2.303** → output **1.327**.

**Hậu quả nếu bỏ qua.** Sau khi BL-04 lên, một chunk báo "đo được, 0 drop" sẽ được đọc là "chunk này
không mất chữ". Sai. Chunk 0 của Le Cordon Bleu chính là ví dụ: **0 drop theo cơ chế (1)**, nhưng
**mất 2 tiêu đề chương thật** theo cơ chế (2). Đây đúng là kiểu gộp-nhầm-hai-trạng-thái mà BL4.5 tự
đặt ra làm nguyên tắc — chỉ khác là nó xảy ra ở tầng cao hơn một bậc so với chỗ TL đang canh.

**Đề xuất.** Không phải viết thêm code. Chỉ cần:
1. §6.22.6, ngay cạnh bảng 3 trạng thái, thêm 1 đoạn: *"`babeldoc_paragraph_drop` = 0 chỉ có nghĩa
   **không có đoạn nào bị bỏ vì không vừa khung**. Nó KHÔNG có nghĩa 'không mất nội dung': ký tự bị
   lọc ở `il_creater.on_lt_char` (góc xoay ngoài ≈0°/≈+90°, hoặc thiếu `aw_font_id`) không bao giờ đi
   qua điểm quan sát này — kênh đó do `overlay_rotated_text` phụ trách và nó KHÔNG phủ hết."*
2. Đổi tên `check_type` cho đúng phạm vi: `babeldoc_paragraph_drop_unfit` (hoặc giữ tên nhưng bắt buộc
   `detail["cause"] = "typeset_unfit"`). Tên hiện tại hứa nhiều hơn thứ nó đo.
3. Ghi nhận vào backlog: kênh (2)/(3) hiện chỉ được `overlay_rotated_text` phủ một phần — trang 19/31
   vẫn mất chữ trong file giao cho người dùng, và job `1ee1fdee` có **0 row** `layout_qa_findings`.

*(Điểm tích cực: nếu góc đúng là -90 như tôi suy luận, thì lo ngại "hai cơ chế báo trùng nhau" là
**không** xảy ra — chúng phủ 2 tập rời nhau. Đó là tin tốt cho §6.22.7, nhưng lý do phải ghi rõ,
không để may rủi.)*

---

### F4 (BLOCKING — quyết định của PM/Hiếu, không phải code) — không ai đọc `layout_qa_findings`

**Mô tả.** §6.22.6 viết: chọn `layout_qa_findings` vì *"đã có sẵn đường ghi (`persist_findings`) và
**đã có UI/QA đọc**"*. Vế sau **sai**.

```
$ grep -rln "LayoutQaFinding\|layout_qa_finding" src/ web/ scripts/
src/models/layout_qa.py            # định nghĩa bảng
src/models/database.py             # đăng ký metadata
src/models/__init__.py             # export
src/postprocess/rotated_text_overlay.py   # GHI
src/services/layout_qa.py                 # GHI
src/services/mineru_det_probe.py          # GHI
```

3 writer, **0 reader**. Không có route trong `src/api/`, không có gì trong `web/`.

**Hậu quả nếu bỏ qua.** BL-04 sinh ra từ B9.7: *"nhánh babeldoc không có bất kỳ cờ cảnh báo nào"*.
Nếu kết quả cuối cùng là vài dòng trong một bảng SQLite mà không lộ trình nào của con người chạm tới,
thì cờ cảnh báo vẫn chưa tồn tại theo nghĩa người dùng được biết — chỉ khác là bây giờ tồn tại một
niềm tin rằng nó đã tồn tại. Với severity `critical`/"mất nội dung thật" thì đó là khoảng cách đáng kể.

Bằng chứng cụ thể: job `1ee1fdee` mất **614 ký tự nguồn** (một đoạn sidebar hoàn chỉnh, trang 230),
`layout_qa_findings` cho job đó = **0 row**, `overflow_reports` = **0 row**, `status = completed`.
Nếu BL-04 đã có sẵn lúc đó, nó sẽ tạo đúng 1 row — và không ai thấy row đó.

**Đề xuất (chọn 1, PM/Hiếu quyết, đừng để mặc định)**:
- (a) **Tối thiểu, rẻ**: `logger.warning` 1 dòng/chunk có drop + tổng số drop ghi vào phần tóm tắt khi
  job hoàn tất (chỗ đã có sẵn log job summary). Cộng 1 dòng trong `docs/test-report.md` cho QA biết
  câu SQL để soi.
- (b) **Đúng hơn**: thêm `paragraph_drops` (count) vào response chi tiết job, hiện 1 badge ở UI.
- (c) **Trung thực nếu không làm gì**: sửa §6.22.6 bỏ vế "đã có UI/QA đọc", ghi thẳng *"BL-04 chỉ
  giao phần LƯU TRỮ; phần hiển thị là backlog `BL-xx` riêng"* và mở item đó ngay.

Điều **không** chấp nhận được là để nguyên câu "đã có UI/QA đọc" trong hợp đồng — vì đó là loại claim
mà 6 tháng sau sẽ có người dựa vào mà không kiểm lại.

---

## Phần C — Nên sửa, không chặn

**F5 — Đối chiếu sentinel phải một chiều, và phải nói thật nó yếu tới đâu.**
Thiết kế ghi finding `babeldoc_drop_report_mismatch` khi `stdout_sentinel_count != len(dropped)`.
Hai vấn đề:
- `EvictQueue(1000)` (`<BD>/main.py:887-909`) làm sentinel **≤** structured theo thiết kế. Dùng `!=`
  ⇒ sinh finding rác một cách hệ thống mỗi khi log dồn. Chỉ nên cảnh báo khi **sentinel > structured**
  (chiều duy nhất hàm ý shim bỏ sót).
- Hai con số **không độc lập**: `logger.error` ở `pdf_creater.py:831` nằm trong
  `render_paragraph_to_char`, mà hàm đó được gọi **từ chính** `create_render_units_for_page`
  (`pdf_creater.py:852`) — tức cùng call site, cùng dữ liệu, cùng thời điểm. Nó chỉ bắt được
  *sai lệch predicate*, không bắt được *hook không chạy* (F2 mới bắt được cái đó). Nên ghi rõ giới hạn
  này trong §6.22.6 thay vì để người đọc tưởng đây là phép đo chéo độc lập.

**F6 — Severity phải đăng ký ở `_SEVERITY_BY_CHECK`, không hardcode ở orchestrator.**
`src/services/layout_qa.py:76-84` là nguồn sự thật duy nhất hiện có ánh xạ `check_type → severity`
(và mọi check_type hiện có đều nằm trong đó). Thiết kế lại truyền `severity="critical"` cứng từ
`job_orchestrator`. Hai nguồn sự thật ⇒ sẽ lệch. Thêm nữa, danh sách "check_type hiện có" ở §6.22.6
(`overlap`, `text_over_drawing`, `text_over_image`, `rotated_text_prescan`, `entity_loss`) **thiếu 2
giá trị**: `rotated_text_overlay_flag` (`layout_qa.py:66`) và `rotated_text_scan_unsupported`
(`layout_qa.py:74`) — và trớ trêu là `rotated_text_overlay_flag` lại là giá trị **duy nhất** thực sự
có trong DB hiện tại (221 row). Danh sách sai ⇒ lập luận "check_type khác nhau nên không lẫn" đứng
trên nền không đầy đủ.

**F7 — Lý do "cắt 400 ký tự cho ghi nguyên tử O_APPEND" là sai về kỹ thuật.**
400 ký tự tiếng Việt với `ensure_ascii=False` = tới ~1.200 byte UTF-8, cộng `box`/`debug_id`/
`layout_label` ⇒ vượt xa mọi ngưỡng kiểu `PIPE_BUF` (512B); và `open(..., "a")` của Python là text I/O
có buffer, có thể tự tách thành nhiều `write()` syscall. Nên câu chữ hiện tại là một lý lẽ nghe hợp lý
mà không đúng. Ngoài ra (xem F2) **chỉ có 1 process ghi dòng `drop`**, nên nguy cơ đan xen gần như
không tồn tại. Chọn 1:
- bỏ phần biện minh, giữ 400 ký tự với lý do thật là "đủ để QA nhận ra đoạn, giữ file nhỏ"; hoặc
- nếu thật sự muốn nguyên tử: dựng sẵn `bytes` rồi `os.write(fd, line_bytes)` **một** syscall trên fd
  mở bằng `os.open(path, O_WRONLY|O_CREAT|O_APPEND)`.

Cách nào cũng được, nhưng đừng để một ràng buộc thiết kế (400) đứng trên một lý do sai — lần sau có
người sẽ nâng lên 2000 và tưởng mình đang phá vỡ một bất biến.

**F8 — `optimal_scale` có ngữ nghĩa chẩn đoán, nên ghi vào schema.**
Khi `_find_optimal_scale_and_layout(apply_layout=False)` không tìm được scale nào fit, nó trả về
`min_scale = 0.1` (`typesetting.py:1076`); và `preprocess_document` chỉ **hạ** các giá trị **lớn hơn**
mode (`:929-935`), nên 0.1 sống sót. Vậy `optimal_scale == 0.1` trong record = "đoạn này đã được biết
là không fit ngay từ bước preprocess". Đó là thông tin triage rất có giá trị, đáng ghi vào cột "Ghi
chú" của bảng schema thay vì mô tả trung tính "scale tính ở preprocess_document".

**F9 — Bước dedupe giải quyết một vấn đề không tồn tại (soi ngược R8-01 vào chính bước mới).**
A5 đã chứng minh hook chạy đúng 1 lần/trang và mỗi paragraph xuất hiện đúng 1 lần trong
`page.pdf_paragraph`. Vậy **trong một lần chạy không có gì để dedupe**. Cái thật sự cần khử trùng là
chồng lấn giữa các chunk — mà dedupe theo `debug_id` lại **không** làm được (F1). Ngược lại,
`generate_base58_id(length=5)` chỉ 5 ký tự: về lý thuyết 2 đoạn khác nhau trên cùng 1 trang có thể
trùng id và bị **gộp nhầm**, tức bước dedupe chỉ có thể gây hại chứ không thể có lợi. Đề xuất: **bỏ
dedupe**, thay bằng bộ lọc dải trang ở F1.

---

## Phần D — Câu hỏi 4: tìm ca drop thật ở đâu (trả lời tường minh cho Dev)

### D1. Chunk 0 Le Cordon Bleu KHÔNG phải ứng viên tốt — đã đo

Tôi không dựa vào trí nhớ. Trên máy đã có sẵn output babeldoc thật của đúng cuốn đó:

- Job `1ee1fdee-746e-4d3b-a54c-d27f7f2aa763`, tạo 2026-09-09, 418 trang, 11 chunk, status `completed`.
- Xác nhận đây là nhánh **babeldoc sau Bug #9**: `overflow_reports` cho job này = **0 row** (nhánh
  pdf2zh luôn có row), `pdf_translate_engine` mặc định = `"babeldoc"` (`src/core/config.py:150`) và
  `.env` không override.
- So từng trang 1-40, số ký tự (bỏ whitespace) nguồn ↔ output:

```
tỉ lệ out/src trên 40 trang: min 0.80 (trang 17, 30 ký tự), phần lớn 0.92–1.13
ứng viên "mất chữ" (src>300 ký tự, tỉ lệ <0.75): 0
```

⇒ **Chunk 0 không có ca drop kiểu (1).** Hai chỗ mất chữ duy nhất (trang 19, 31) là kênh (2) — chữ
xoay, shim không thấy (F3). Chạy gate §6.22.9 trên chunk 0 sẽ ra `available=True, dropped=[]` và
không chứng minh được điều gì về cơ chế mới.

### D2. Ca drop thật ĐÃ ĐO ĐƯỢC: trang 230, thuộc chunk 5 (`--pages 199-240`)

Quét toàn bộ 418 trang, chỉ đếm ký tự **ngang** (loại nhiễu của kênh chữ xoay), tìm trang mất >200 ký
tự và tỉ lệ <0.88:

```
page  src_h  out_h  ratio
 112   2010   1768  0.88
 113   2844   2489  0.88
 140   1964   1699  0.87
 167   2189   1845  0.84
 193   2600   2241  0.86
 230   2318   1440  0.62   <<<
 347   2711   2362  0.87
```

Sáu trang 0.84–0.88 là co ngót dịch thuật bình thường (đã kiểm: số block nguồn/đích khớp, không block
nào vắng mặt). **Trang 230 là ngoại lệ thật.**

**Bằng chứng trực tiếp (đọc toàn văn output trang 230, không dựa vào heuristic):**

Block nguồn biến mất hoàn toàn:

- bbox `(61.5, 223.6, 332.3, 466.6)` → khung **271 × 243 pt**, 13 dòng, font `BernhardModernStd-Roman`
  **12 pt**, **614 ký tự**
- nội dung: *"The term feuilletage appeared in the 15th century and some attribute its invention to
  Feuillet, the pâtissier to the Marshall of Conde. … including Carême who innovated the fifth turn of
  the dough!"*
- Toàn văn trang 230 của output (1.126 ký tự) **không chứa** bất kỳ dấu vết nào của đoạn này: không
  "feuilletage" theo nghĩa lịch sử, không Feuillet / Conde / Le Lorrain / Médicis / Carême. Mọi block
  còn lại của trang đều có bản dịch tương ứng.

Đây là **đúng hồ sơ** của cơ chế (1): cột sidebar hẹp, chữ 12pt dày đặc, bản dịch VI dài hơn ⇒ không
scale nào fit ⇒ composition ở nguyên trạng thái rỗng ⇒ biến mất, không một dòng cảnh báo nào.

*(Mức chắc chắn: **ĐÃ ĐO** — nội dung nguồn, nội dung output, toạ độ, cỡ chữ đều đọc trực tiếp từ 2
file PDF thật. Điều **chưa** verify: rằng khi chạy lại, babeldoc sẽ drop **đúng** đoạn đó — dịch máy
không tất định, một bản dịch VI ngắn hơn có thể vừa khung.)*

### D3. Cách chạy E2E — và một cái bẫy phải tránh

**Lệnh mục tiêu**: chạy đúng chunk 5, tức `--pages 199-240`, trên đúng file
`data/uploads/f07b3194-4d26-...-Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf`.

**BẪY — đừng cắt lấy 2-3 trang quanh trang 230 cho rẻ.** `preprocess_document` ép `optimal_scale` của
**mọi** đoạn xuống **mode tính trên toàn bộ tập trang của chính lần gọi đó** (`typesetting.py:919-935`).
Một lần chạy 3 trang có mode khác hẳn lần chạy 42 trang ⇒ đoạn ở trang 230 có thể **fit** và ca drop
biến mất. Muốn tái hiện trung thực thì phải giữ nguyên tập trang: `199-240`.

**Assertion cho gate (R6-02 — đúng giá trị, không đếm):**
1. `drop_report.available is True`, và (nếu làm F2) `observed_pages == set(range(199, 241))`.
2. Tồn tại record với `page_number_1based == 230`.
3. `text_excerpt` của record đó là bản dịch VI của đoạn feuilletage (soi tay 1 lần, rồi chốt vào
   golden file).
4. Mở `translated_vi.pdf` trang 230, xác nhận đoạn đó **thật sự vắng** — không chỉ tin số đếm (R6-03).
5. Sau F1: xác nhận **không** có record nào ở trang 199-200 lọt vào finding (đó là 2 trang chồng lấn
   bị merge vứt bỏ).

**Nếu không tái hiện được** (bản dịch lần này vừa khung): đừng kết luận thiết kế sai. Hai lựa chọn,
theo thứ tự ưu tiên:
- (a) chạy lại nguyên cuốn với cùng model/prompt như job `1ee1fdee` (`deepseek`) — xác suất ra ít nhất
  1 ca drop ở đâu đó là cao, vì cuốn này có nhiều sidebar khung hẹp;
- (b) dựng tài liệu ép drop: 1 trang, **một** text box ~270 × 240 pt, ~650 ký tự tiếng Anh ở 12 pt
  (tức chép đúng hình học của khối đã đo ở trang 230), dịch EN→VI. Đây không phải "bịa ca test" — nó
  là bản sao hình học của một ca thật đã đo.

**Chi phí**: 42 trang thay vì 418 trang. Và golden file cho test 1 sinh ra từ đúng lần chạy này.

### D4. Một số liệu nên đưa vào quyết định của PM

Cuốn 418 trang, chạy thật, **1** ca drop kiểu (1) trong toàn bộ tài liệu. Tức hiện tượng **hiếm**.
Hệ quả:
- `stdout_sentinel_count` gần như luôn là `0 == 0` ⇒ phép đối chiếu ở F5 trong thực tế hầu như không
  kiểm được gì. Đừng đầu tư thêm vào nó.
- Ngược lại, **giá trị của BL-04 nằm ở chỗ nó hiếm**: chính vì hiếm nên không ai soi tay ra được, và
  chính vì hiếm nên khi nó xảy ra thì không có bất kỳ cơ chế nào khác bắt. Một đoạn 614 ký tự về lịch
  sử pâte feuilletée biến mất khỏi sách dạy nghề mà job vẫn báo `completed` — đó là đúng loại lỗi mà
  người dùng chỉ phát hiện khi đã in ra giấy.
- Đồng thời, vì hiếm, **F4 (không ai đọc bảng) càng nặng**: 1 row/cuốn nằm trong bảng không có reader
  thì thực tế bằng 0 row.

---

## Phần E — Tóm tắt khuyến nghị cho PM

**Không cho Dev implement nguyên trạng.** Yêu cầu Tech Lead sửa §6.22 ở 4 điểm:

1. **F1** — thêm bộ lọc dải trang sống sót của chunk (dùng chung hàm với `chunk_merge`), bỏ dedupe
   theo `debug_id` (F9).
2. **F2** — shim ghi thêm record `type="page"`; runner đối chiếu tập trang quan sát được với dải trang
   của chunk; parser không giả định vị trí dòng header.
3. **F3** — ghi tường minh vào §6.22.6 rằng "0 drop" **không** đồng nghĩa "không mất nội dung", nêu rõ
   kênh `il_creater.on_lt_char:969-974`; cân nhắc đổi tên `check_type` cho đúng phạm vi.
4. **F4** — PM/Hiếu chọn một trong 3 phương án surfacing, và sửa câu "đã có UI/QA đọc" (sai) trong
   §6.22.6 dù chọn phương án nào.

Nên sửa kèm (rẻ, không chặn): **F5** (mismatch một chiều + nói rõ giới hạn), **F6** (đăng ký severity
ở `_SEVERITY_BY_CHECK`, sửa danh sách check_type), **F7** (bỏ lý do O_APPEND sai), **F8**
(`optimal_scale == 0.1` là marker chẩn đoán), **A9** (viết vào spec rằng sidecar **phải** nằm trong
`chunk_output_dir` vì `_call_translator` rmtree mỗi attempt).

**Sửa §6.22.9**: đổi mục tiêu E2E từ "chunk 0 (40 trang đầu)" sang **chunk 5, `--pages 199-240`**, với
assertion cụ thể ở D3 và cảnh báo không được cắt nhỏ dải trang (D3, bẫy mode-scale).

Phần còn lại của thiết kế — điểm hook, predicate, kênh JSONL sidecar, 3 trạng thái, capability
`reports_own_paragraph_drops`, quyết định không tái dùng `overflow_reports`, không đụng vào quyết định
Bug #9 — tôi đã kiểm và **đồng ý**, không có ý kiến sửa.

---
---

# Xác nhận lần 2 (2026-09-11) — Domain Expert, lượt 2/2 Protocol D

- **Phạm vi đọc lượt này**: `docs/Architecture.md` §6.22 (6798–7500, bản đã sửa) ·
  `docs/design-log.md` BL4.8–BL4.14 (5889–6123) · `src/core/chunking.py:28-78` ·
  `src/postprocess/chunk_merge.py:64-131` · `src/core/job_orchestrator.py` (405-435, 540-600,
  685-700, 800-812, 1733-1743, 1786-1815, 1890-1925) · `src/services/layout_qa.py:60-110, 278-310,
  386-425` · `src/models/chunk.py` · `src/babeldoc_shim/sitecustomize.py:596-700` · source babeldoc
  0.6.4 (`<BD>/`): `format/pdf/high_level.py`, `format/pdf/document_il/backend/pdf_creater.py`,
  `format/pdf/document_il/frontend/il_creater.py`, **`.../frontend/il_creater_active.py`**,
  `format/pdf/new_parser/*.py`, `format/pdf/translation_config.py`
- **Đo thật lượt này**: `data/bb_translation.db` — bảng `chunks` của job `1ee1fdee` (11 row),
  `jobs.chunk_size_used`, bảng `concurrency_state`.
- **Nguyên tắc**: không kế thừa trích dẫn của Tech Lead, cũng không kế thừa trích dẫn của **chính
  tôi ở lượt 1**. Việc đó có ích — nó lộ ra một sai sót mà **cả hai chúng tôi cùng mắc** (X1 dưới).

## Kết luận ngắn

**APPROVE cho Dev implement — kèm 3 điều kiện bắt buộc (X1, X6, X7) và 5 điểm nên sửa trước khi
code (X2–X5, X8).**

Cả 4 điểm blocking F1–F4 đều đã được xử lý ở mức tôi chấp nhận được. F1 và F2 tôi verify độc lập là
**đúng về bản chất**, không chỉ đúng về câu chữ. F3 (chỉ giải quyết vế "trung thực") là **ranh giới
an toàn đủ**, không phải "biết gap mà không vá" — lập luận đầy đủ ở X6. F4 (log-only) đạt tinh thần
phản biện ban đầu, với 1 chỗ phải sửa (X7).

Phát hiện **mới** của lượt này, nặng nhất, là X1: §6.22 trích dẫn **nhầm class frontend** của
babeldoc. Kết luận kỹ thuật vẫn đúng (class thật có predicate y hệt), **code BL-04 không phải đổi
một dòng nào**, nhưng 4 trích dẫn trong hợp đồng đang trỏ vào code **không chạy** — và ứng viên
thiết kế đã ghi sẵn cho BL-08 nếu implement đúng như viết sẽ là **patch vô tác dụng**. Đây đúng
khuôn Bug #9 (hành động theo một trích dẫn cũ không còn đúng), nên phải sửa **trước** khi Dev bắt
đầu, dù nó không chặn code.

| # | Phát hiện | Mức | Thuộc |
|---|---|---|---|
| **X1** | §6.22 trích `il_creater.py` (ILCreater) — **class đó không chạy** trong luồng dịch của 0.6.4; luồng thật dùng `ActiveILCreater` (`il_creater_active.py`) | **ĐIỀU KIỆN APPROVE** (sửa tài liệu, không sửa code) | F2, F3, BL-08 |
| X2 | `_ChunkLike.page_start: int` vs `models.Chunk.page_start: int \| None` | nên sửa | F1 |
| X3 | Hàm chung chỉ sở hữu quy tắc **start**; `merge_chunk_pdfs` còn kẹp **end** theo `chunk_doc.page_count` — test 5 viết dễ gây hiểu nhầm | nên sửa | F1 |
| X4 | Bất biến "hook chạy đúng 1 lần/trang" còn phụ thuộc **`--watermark-output-mode no_watermark`** — chưa ghi trong hợp đồng | nên sửa | F2 |
| X5 | `checksum_mismatch_pages` **không có chỗ đi** khi `observed == expected` (trạng thái 1/2) | nên sửa | F2 |
| **X6** | Quyết định F3 (không làm counter kênh (2)/(3)) — **chấp nhận được**, kèm điều kiện về thứ tự ưu tiên BL-08 | **ĐIỀU KIỆN APPROVE** | F3 |
| **X7** | Log R-2 "đếm từ list đã map, không query DB" **đếm thiếu khi job resume** | **ĐIỀU KIỆN APPROVE** (sửa 1 dòng spec) | F4 |
| X8 | Gate E2E: `chunk_size_used` là **thích ứng** (20/40) → biên chunk có thể khác 199-240; và §6.22.9 không nói chạy bằng harness nào | nên sửa | Gate |

---

## Phần A2 — Đã tự verify lại và THẤY ĐÚNG (để PM biết phạm vi đã phủ lượt này)

| # | Claim | Kết quả | Nguồn tôi tự đọc/đo |
|---|---|---|---|
| B1 | Chunk chồng nhau 2 trang, merge vứt phần đầu | **ĐÚNG** | `chunking.py:60-61, 75`; `chunk_merge.py:85-91`; và **đo DB thật**: 11 row `chunks` của job `1ee1fdee` đúng `1-40, 39-80, …, 399-418` |
| B2 | Dải sống sót **phủ kín + rời nhau** | **ĐÚNG, và tôi chứng minh mạnh hơn TL** — không chỉ đúng với 418 trang mà đúng **đại số** với mọi `(total_pages, chunk_size, overlap ≥ 0)` do `calculate_chunks` sinh: `start_i = e_{i-1} - overlap + 1` và `overlap_end_i = start_i + overlap - 1` ⇒ `surviving_i = [e_{i-1}+1, e_i]`. Nối liền, không hở, không đè | `chunking.py:52-77` |
| B3 | `actual_start > page_end` (chunk đóng góp 0 trang) không xảy ra với plan thật | **ĐÚNG** — luôn có `e_i ≥ start_i + overlap` vì `e_{i-1} < total_pages` ⇒ `overlap_end_i ≤ e_i − 1`. Nhánh `continue` chỉ là phòng thủ | `chunking.py:71-76`; `chunk_merge.py:93-94` |
| B4 | `position == chunk.chunk_index` hiện đúng | **ĐÚNG** — `merge_chunk_pdfs(chunks, …)` nhận **nguyên** list (`job_orchestrator.py:693`), và vòng Bước 7 (`:577`) chỉ *bỏ qua* chunk đã completed chứ **không lọc khỏi list** | đọc call site |
| B5 | Hook `create_render_units_for_page` chạy **đúng 1 lần/trang**, đúng 1 lần `write()` mỗi lần chạy | **ĐÚNG với điều kiện** — có **3** call site `PDFCreater.write()` trong `high_level.py`: `:930` (chỉ khi `only_parse_generate_pdf`, app không truyền), `:1047` (đường chính), `:1103` (trong `generate_first_page_with_watermark`, **chỉ chạy khi `watermark_output_mode == Both`** — app truyền `no_watermark`). Xem X4 | `high_level.py:925-931, 1024-1029, 1046-1047, 1096-1103`; `babeldoc_runner.py` (args `--watermark-output-mode no_watermark`) |
| B6 | `render_paragraph_to_char` **không mutate** composition ⇒ quan sát sau khi gọi hàm gốc là hợp lệ | **ĐÚNG** | `pdf_creater.py:810-836` |
| B7 | Predicate `_has_rendered_chars` tương đương định nghĩa babeldoc | **ĐÚNG** — babeldoc dùng *truthiness* (`if composition.pdf_character:`), thiết kế dùng `is not None`. Tương đương vì `il_version_1.PdfCharacter` là dataclass thuần, **không** định nghĩa `__bool__`/`__len__` (grep cả file: 0 kết quả) ⇒ mọi instance truthy | `il_version_1.py:627+`; `grep "__bool__\|__len__"` |
| B8 | `expected_pages` là con số xác định | **ĐÚNG, và mạnh hơn TL viết** — `--pages 199-240` → `parse_pages` cho `(199, 240)` **inclusive** (`translation_config.py:396-406`), rồi lọc **3 lần độc lập**: `load_prepared_pdf_pages(should_include_page=…)`, `prepared_page_execution.py:22`, và `create_il()`. 42 trang, khả năng báo động giả của trạng thái 3 rất thấp | các file nêu bên trái |
| B9 | `page.page_number` = chỉ số **0-based tài liệu GỐC** (A7 lượt 1) | **ĐÚNG cả với parser mới** — `pymupdf_page_view_access.py:56` `for pageno, page in enumerate(document)` chạy trên **toàn** document trước khi lọc; `prepared_page_execution.py:24` truyền `page.pageno` nguyên vẹn vào `sink.on_page_number` | 2 file trên |
| B10 | babeldoc **không** chia part (page number sẽ bị đánh lại) | **ĐÚNG** — `split_strategy` chỉ khác `None` khi có `--max-pages-per-part` (`main.py:672-675`), `BabeldocRunner` không truyền. *Điểm cộng ngoài dự kiến*: nếu ai đó thêm flag đó, page number part-relative sẽ làm `observed_pages ≠ expected_pages` ⇒ trạng thái 3 **kêu to** thay vì hỏng âm thầm. Cơ chế F2 tự phòng được ca này | `main.py:672-675`, `high_level.py:547-560` |
| B11 | 3 lý do TL bác counter kênh (2)/(3) | **ĐÚNG cả 3** — (1) `project_native_char` chạy **mỗi ký tự**; (2) `_collect_valid_char` thật sự còn lọc thêm `unicodedata.category ∈ {Cc,Cs,Co,Cn}`, `"(cid:"`, `font_mapper.has_char()`; (3) hook hiện có chạy sau dịch | `il_creater_active.py:1292-1306, 1439-1466`; `pdf_creater.py:1465-1466` |
| B12 | Sidecar trong `chunk_output_dir` an toàn nhờ rmtree mỗi attempt | **ĐÚNG**, đọc lại nguyên khối comment + code | `job_orchestrator.py:1801-1806` |
| B13 | `_SEVERITY_BY_CHECK` có **7** khoá, `_install_patch_hook` đã generic cho module thứ 3 | **ĐÚNG** | `layout_qa.py:77-85`; `sitecustomize.py:683-700` |
| B14 | Mục tiêu E2E (chunk 5 = 199-240, overlap_end=200, surviving 201-240, trang 230 nằm trong) | **ĐÚNG, đo trực tiếp trên DB** | `select … from chunks where job_id like '1ee1fdee%'` |
| B15 | Các patch shim cũ (Bug #7 `paragraph_finder`, Bug #10 `typesetting`) vẫn nằm trên đường chạy sau khi babeldoc đổi parser | **ĐÚNG** — `high_level.py:971` `ParagraphFinder(...).process(docs)`, `:1038` `Typesetting(...).typesetting_document(docs)`. Chỉ **frontend** đổi, midend giữ nguyên | `high_level.py:971, 1038` |

---

## X1 (ĐIỀU KIỆN APPROVE) — §6.22 trích dẫn nhầm class frontend: `ILCreater` không chạy trong luồng dịch

**ĐÃ VERIFY.** Trong babeldoc 0.6.4, `_do_translate_single()` parse bằng:

```python
# <BD>/format/pdf/high_level.py:902-910
from babeldoc.format.pdf.new_parser.native_parse import (
    parse_prepared_pdf_with_new_parser_to_legacy_ir,
)
docs = parse_prepared_pdf_with_new_parser_to_legacy_ir(temp_pdf_path, config=..., doc_pdf=...)
```

và `native_parse.py:57` dựng sink là **`ActiveILCreater`** (`document_il/frontend/il_creater_active.py`),
**không** phải `ILCreater` (`document_il/frontend/il_creater.py`). `ILCreater` + `legacy_parse.start_parse_il`
chỉ còn **một** người dùng trong toàn package: `format/pdf/parse_only.py:6, 29` — một entry point
tách biệt, không nằm trên đường dịch.

Nghĩa là các trích dẫn sau trong §6.22 (và trong note lượt 1 của **chính tôi** — tôi mắc cùng lỗi,
ghi ra để không ai phải đoán) đang trỏ vào **code không chạy**:

| Trích dẫn trong §6.22 | Trỏ vào | Địa chỉ ĐÚNG trong luồng dịch |
|---|---|---|
| §6.22.6.1 kênh (2): `il_creater.py:972-974` | dead | **`il_creater_active.py:1295-1297`** (trong `project_native_char`, `:1292`) |
| §6.22.6.1 kênh (3): `il_creater.py:969-970` | dead | **`il_creater_active.py:1293-1294`** |
| §6.22.6 trạng thái 3: `create_il()` lọc `docs.page` — `il_creater.py:1347-1353` | dead | **`il_creater_active.py:245`** (+ `pymupdf_prepared_page_access` `should_include_page`, `prepared_page_execution.py:22`) |
| §6.22.6.1 bảng bác bỏ + BL-08: `_collect_valid_char` `il_creater.py:1122-1157`, ứng viên hook `ILCreater.on_page_end` `il_creater.py:641-664` | dead | **`il_creater_active.py:1439-1466`** và **`il_creater_active.py:386-407`** |

**Tin tốt — kết luận kỹ thuật KHÔNG đổi.** Tôi đã đọc `ActiveILCreater.project_native_char` và nó
có predicate **y hệt từng ký tự**:

```python
# <BD>/format/pdf/document_il/frontend/il_creater_active.py:1292-1300
def project_native_char(self, char: LTChar) -> None:
    if char.aw_font_id is None:
        return
    try:
        rotation_angle = get_rotation_angle(char.matrix)
        if not (-0.1 <= rotation_angle <= 0.1 or 89.9 <= rotation_angle <= 90.1):
            return
    except Exception:
        logger.warning("Failed to get rotation angle for char %s", char.get_text())
```

(gọi từ `on_lt_char`, `:1423-1427`). `create_il()` lọc trang: `:245`. `on_page_end` +
`_page_valid_chars_buffer`: `:386-407`. ⇒ **F3 đúng, F2 đúng, BL-08 khả thi** — chỉ sai địa chỉ.

**Hậu quả nếu bỏ qua.** Không phải bug hôm nay (BL-04 chỉ patch `pdf_creater`, không đụng frontend).
Hậu quả nằm ở **tương lai gần**: BL-08 đã được ghi sẵn "ứng viên thiết kế đã khảo sát:
`ILCreater.on_page_end` (`il_creater.py:641-664`)" — đúng loại chỉ dẫn mà người sau sẽ tin và
implement thẳng. Patch `ILCreater.on_page_end` trong luồng dịch là **no-op**: không ném lỗi, không
ghi gì, và người đó sẽ kết luận *"đo rồi, không có ký tự nào bị lọc"* — một **false negative im
lặng**. Đây chính xác là cơ chế Bug #9 (một bước hành động dựa trên trích dẫn không còn đúng ngữ
cảnh), khác chỗ nó chưa kịp xảy ra.

Nó cũng làm hỏng một lập luận nhỏ của §6.22.6.1: "patch `on_lt_char` … trên hàm nóng nhất của
parser" — ở `ActiveILCreater`, `on_lt_char` (`:1423`) chỉ là vỏ, chỗ thật cần patch là
`project_native_char` (`:1292`). Lý do bác bỏ vẫn đứng vững (vẫn là mỗi ký tự, vẫn phải chép
predicate), nhưng viết sai tên hàm thì người sau sẽ patch nhầm chỗ.

**Đề xuất (bắt buộc, chỉ sửa tài liệu — 0 dòng code)**:
1. Sửa 4 nhóm trích dẫn ở bảng trên trong §6.22.6, §6.22.6.1.
2. Thêm **1 dòng** vào §6.22.1 "Nguồn xác thực" (R5-01): *"Luồng dịch 0.6.4 parse bằng
   `new_parser/native_parse.py` → `ActiveILCreater` (`il_creater_active.py`). `ILCreater`
   (`il_creater.py`) + `legacy_parse.py` CHỈ được dùng bởi `parse_only.py`, **không** nằm trên đường
   dịch — mọi trích dẫn frontend phải trỏ vào bản `_active`."* Đây là loại lệch mà R5-05 sinh ra để
   bắt, giống hệt ca "0.2.33 có `document_il/` không có `format/pdf/`" mà §6.22.1 đã bắt đúng — chỉ
   là lần này lệch **trong cùng một version**.
3. Sửa BL-08 trong backlog: ứng viên là **`ActiveILCreater.on_page_end`** (`il_creater_active.py:386-407`),
   đọc `_page_valid_chars_buffer` (`:230`, `:384`, clear ở `:407`).
4. Ghi rõ midend **không** bị ảnh hưởng (B15) để không ai hoảng và đi audit lại patch Bug #7/#10.

---

## X2–X3 — F1: đúng về bản chất, 2 chỗ cần chính xác hơn trước khi Dev code

**X2 (kiểu dữ liệu).** `_ChunkLike` khai `page_start: int`, `page_end: int`. Nhưng
`src/models/chunk.py:23-24` là `page_start: int | None`, `page_end: int | None` (nullable từ 6.20.7
vì EPUB dùng `unit_start`/`unit_end`). `merge_chunk_pdfs(chunks: Sequence[Chunk])` truyền đúng model
đó vào hàm chung ⇒ Protocol không khớp. Đường EPUB **không** đi qua `_process_chunk`/`merge_chunk_pdfs`
(đã kiểm: `run_job` rẽ sang `run_epub_job` ngay tại `job_orchestrator.py:457`), nên **không có bug
runtime hôm nay** — nhưng khai `int` là khai sai sự thật. Đề xuất: khai `int | None` và **raise
tường minh** trong hàm khi gặp `None` ("chunk EPUB không có dải trang") thay vì để `None + 1` nổ ở
chỗ khác.

**X3 (hàm chung sở hữu quy tắc nào).** `merge_chunk_pdfs` có **2** quy tắc, không phải 1:
- quy tắc **start**: `actual_start = chunk.overlap_end + 1` khi `position > 0` **và**
  `overlap_start is not None` **và** `overlap_end is not None` (`chunk_merge.py:85-91`);
- quy tắc **end**: kẹp theo `chunk_doc.page_count` (`:97-107`) — phụ thuộc **file thật**, hàm thuần
  không thể biết.

Hàm chung chỉ sở hữu quy tắc start. Hai hệ quả cho Dev:
1. Phải **giữ nguyên** guard `overlap_start is not None and overlap_end is not None` trong hàm
   chung, nếu không `merge_chunk_pdfs` đổi hành vi ở ca chunk có `overlap_* = None` — trái cam kết
   "giữ nguyên hành vi" của §6.22.5.1.
2. Test 5 (`test_surviving_range_shared`) hiện viết *"dải trả về **trùng khít** `(actual_start, page_end)`
   mà `merge_chunk_pdfs()` thực sự dùng"* — dễ bị hiểu là so với **số trang thực sự chèn vào file
   merge**, vốn đã bị kẹp bởi `page_count`. Nên viết lại: so với **`actual_start`** mà
   `merge_chunk_pdfs` tính ra (refactor cho nó gọi hàm chung là đủ), và ghi rõ việc kẹp `end` **vẫn
   ở lại** `chunk_merge.py`, không chuyển vào hàm chung.

Ngoài 2 điểm đó, F1 **đạt**: chứng minh phủ-kín/rời-nhau của TL tôi đã kiểm lại và thấy nó đúng
**tổng quát hơn** cả mức TL tự nhận (B2), và bất biến `position == chunk.chunk_index` được kiểm bằng
`logger.warning` chứ không giả định (§6.22.5.1 + §6.22.8 đều ghi) — đúng thứ tôi yêu cầu. Ghi nhận
thêm: khi hai tham số lệch nhau (chunk 0 vắng mặt), hướng sai là **bỏ sót finding**, không phải
**false positive** — hướng sai an toàn hơn. TL chọn đúng.

---

## X4–X5 — F2: đủ, nhưng còn 2 lỗ nhỏ

**F2 đạt.** Record `type="page"` thật sự trả lời được câu hỏi "hook đã chạy trên đúng tập trang
chưa", vì (a) hook nằm trong vòng `for page in self.docs.page` chạy đúng 1 lần (B5), (b) `docs.page`
đã bị lọc xuống đúng `--pages` bởi 3 cơ chế độc lập (B8), (c) `page.page_number` là chỉ số tuyệt đối
(B9). Trạng thái 4 (`available=False`) cũng deny-by-default đúng: `_PatchingLoader.exec_module` nuốt
exception và chạy hành vi gốc (`sitecustomize.py:626-637`) ⇒ patch fail = không header = trạng thái
4, không phải "im lặng 0 drop".

**X4 (chưa ghi trong hợp đồng).** Bất biến "đúng 1 lần/trang" còn phụ thuộc một cờ CLI mà §6.22.4
không nhắc: nếu `watermark_output_mode == Both`, `generate_first_page_with_watermark()`
(`high_level.py:1024-1029`, `:1096-1103`) dựng **PDFCreater thứ hai** trên `deepcopy(doc_il.page[0])`
và gọi `write()` lần nữa ⇒ **trang đầu của mỗi chunk có 2 record `page` và có thể 2 record `drop`**.
Hôm nay an toàn vì `BabeldocRunner` hardcode `--watermark-output-mode no_watermark`. Đề xuất: thêm 1
dòng vào bảng "Chỉ chạy đúng 1 lần / trang" của §6.22.4: *"…và `--watermark-output-mode` **không
phải** `both` — chế độ `both` render lại trang đầu lần hai (`high_level.py:1096-1103`)."* Rẻ, và nó
biến một phụ thuộc tình cờ thành ràng buộc có tên (đúng cách A9 đã được xử lý).

**X5 (checksum không có chỗ đi).** §6.22.6 ghi `checksum_mismatch_pages` nằm trong `detail` của
**finding trạng thái 3**. Nhưng trạng thái 3 chỉ kích hoạt khi `observed_pages != expected_pages`.
Ca đáng lo nhất của checksum là ngược lại: **đủ trang** (`observed == expected`) nhưng một dòng
`drop` bị xé/mất ⇒ `page.dropped_count = 3` mà chỉ có 2 dòng `drop`. Khi đó không có finding nào để
gắn `checksum_mismatch_pages` vào, và hệ thống rơi về trạng thái 2 với **số finding ít hơn sự thật**
— đúng loại "giảm âm thầm" mà chính checksum sinh ra để chặn. Đề xuất (1 dòng): điều kiện trạng
thái 3 là `observed_pages != expected_pages` **HOẶC** `checksum_mismatch_pages` khác rỗng. Nếu không
muốn đổi bảng trạng thái thì tối thiểu phải đưa `checksum_mismatch=K` vào **định dạng log R-1 bắt
buộc**, để nó không biến mất.

---

## X6 (ĐIỀU KIỆN APPROVE) — Trọng tâm: quyết định F3 có chấp nhận được không?

**Câu trả lời: CÓ, chấp nhận được — và tôi nói rõ vì sao đây không phải "biết có gap mà không vá".**

Bốn lý do, theo thứ tự sức nặng:

**(1) BL-04 không tạo ra gap này, và không làm nó nặng thêm.** Kênh (2) mất chữ xoay đã tồn tại từ
trước BL-04, thuộc trách nhiệm `overlay_rotated_text` (§U3–U7). Chặn BL-04 để bắt vá kênh (2) là
**buộc hai khiếm khuyết độc lập vào chung một hạng mục**, và cái giá là hoãn cơ chế duy nhất hiện
bắt được ca mất 614 ký tự ở trang 230 — ca mà **hôm nay không cơ chế nào bắt**. Đó là đánh đổi lỗ.

**(2) Vế nguy hiểm thật của F3 đã được đóng — bằng ràng buộc định dạng, không bằng văn xuôi.** Lo
ngại lượt 1 của tôi không phải "hệ thống chưa đo kênh (2)"; mà là **"hệ thống sẽ nói 0 drop và
người đọc hiểu thành không mất chữ"**. §6.22.6.1 cấm phát ra chuỗi "0 drop" trần, bắt buộc kèm mẫu
số `observed=42/42` **và** câu PHAM VI trong **mọi** nơi con số xuất hiện (log, `detail`, báo cáo
QA). Đó là chỗ tôi đề xuất "thêm 1 đoạn văn", TL làm **chặt hơn đề xuất của tôi** — chuyển từ tài
liệu sang định dạng output. Một câu PHAM VI dính liền con số thì không đọc lướt qua được; một đoạn
văn ở dòng 6.900 của tài liệu 7.911 dòng thì có.

**(3) R8-02 được tuân thủ đúng tinh thần, không phải bị lách.** Deny-by-default yêu cầu: chưa verify
thì **SKIP**, không đoán. TL đã khảo sát 3 cách, bác từng cách **có nguồn** (tôi đã kiểm cả 3 — B11),
và ghi lại ứng viên + **điều kiện tiên quyết "phải đo nhiễu trước khi đặt ngưỡng"**. So sánh: làm
counter ngay bây giờ trên `_page_valid_chars_buffer` mà chưa đo nhiễu sẽ sinh một counter trộn 3
nguyên nhân (góc xoay / thiếu glyph trong font map / khác biệt bộ trích xuất) — tức một cờ báo động
giả có hệ thống, **loại cờ mà QA sẽ học cách bỏ qua**. Đó là đúng chế độ hỏng tôi cảnh báo ở F1 mục
1. Không làm, có lý do, có ứng viên — an toàn hơn làm vội.

**(4) TL tự kiểm thêm một vế tôi bỏ sót, theo hướng làm vấn đề NẶNG hơn cho chính mình.** `babeldoc_rotated_text_overlay`
có từ commit `b9c8952` (2026-09-07) < ngày job `1ee1fdee` (2026-09-09) ⇒ overlay **đã bật khi tôi đo
trang 19/31 mất chữ**, nên phản bác "overlay lo rồi" chết. Tôi xác nhận lập luận đó hợp lệ. Một
người muốn né việc sẽ không đi tìm thêm bằng chứng chống lại mình.

### Nhưng kèm 3 điều kiện — nếu không có, đây SẼ thành "biết gap mà không vá"

**(a) BL-08 phải có chủ và có mốc, không được nằm chờ trong backlog.** Số đo của tôi: kênh (2) làm
mất **~976 ký tự dọc** trên 52/418 trang (2.303 → 1.327), **gồm 2 tiêu đề chương** (trang 19, 31) —
tức **nhiều hơn** kênh (1) (614 ký tự, 1 đoạn) trên đúng cuốn sách này. BL-04 vá kênh nhỏ hơn. Điều
đó ổn (kênh nhỏ hơn hiện **hoàn toàn không có cơ chế nào**, kênh lớn hơn có overlay phủ một phần),
nhưng nó có nghĩa **BL-08 là hạng mục ưu tiên cao nhất còn lại của mảng mất-chữ**, không phải mục
"nice to have". Khuyến nghị PM: BL-08 xếp ngay sau BL-04, và nếu bị đẩy lùi thì phải ghi lý do vào
`design-log.md`.

**(b) Sửa địa chỉ BL-08 theo X1 trước khi ai đó nhận việc đó.** Ứng viên hiện ghi là
`ILCreater.on_page_end` — **no-op**. Điều kiện này không tốn công: sửa 1 dòng backlog.

**(c) Ghi nhận một sự thật PM nên biết khi lên kế hoạch BL-08** (ĐÃ VERIFY, phát hiện lượt này):
`src/services/layout_qa.py:386` `run_layout_qa_gate()` — chứa sẵn `_check_rotated_text_prescan()`
(`:278-310`) quét **file GỐC**, bắt mọi dòng chữ xoay kèm `bbox` + text đầy đủ, severity `blocker`,
có test (`tests/test_layout_qa.py:116-161`) — **chưa từng được gọi ở bất kỳ đâu trong `src/`**.
`grep -rn "run_layout_qa_gate" src/ web/ scripts/` = **0 kết quả**; chỉ tests tham chiếu. Đó là lý do
thứ hai (ngoài overlay không phủ hết) khiến job `1ee1fdee` có 0 row: **bộ dò đã có sẵn nhưng không
nằm trên đường chạy**.
⚠️ Tôi **không** đề xuất bật nó lên trong BL-04: trên cuốn này nó sẽ sinh ≥52 finding `blocker`/cuốn
cho **mọi** dòng chữ xoay, kể cả những dòng overlay khôi phục thành công ⇒ đúng loại báo động giả
cần tránh. Nhưng khi làm BL-08, **không được bắt đầu từ con số 0**: đã có sẵn một bộ dò + fixture +
test, việc còn lại là biến "có chữ xoay" thành "chữ xoay **bị mất**" (đối chiếu gốc ↔ dịch) và đặt
ngưỡng sau khi đo nhiễu.

---

## X7 (ĐIỀU KIỆN APPROVE) — F4: log-only là đủ, nhưng R-2 đếm thiếu khi job resume

**F4 đạt về nguyên tắc.** Yêu cầu lượt 1 của tôi là: *"không được để nguyên câu 'đã có UI/QA đọc'"*
và *"chọn 1 trong 3 phương án, đừng để mặc định"*. TL đã xoá câu sai, chọn (a) + mở (b) thành BL-09,
**và** ghi giới hạn thẳng vào hợp đồng ("cảnh báo chỉ tới được người đọc log server"). Log server
+ câu SQL sẵn cho QA là **đường đọc thật của con người** — đủ cho một sự kiện tần suất 1 row/cuốn
mà đối tượng đọc trước mắt là QA/Dev, không phải người dùng cuối. Không nửa vời.

**Nhưng R-2 có một lỗ đo được.** §6.22.6.2 yêu cầu R-2 tổng hợp *"tổng số finding `babeldoc_*` của
job này (đếm từ list đã map, **không** query lại DB)"*. Ba sự thật đã verify làm yêu cầu đó sai
hướng:
- `_process_chunk()` trả về `None` (`job_orchestrator.py:1733-1743`) ⇒ không có đường tự nhiên để
  đưa list lên `run_job()`; phải thêm accumulator.
- Vòng Bước 7 (`:577-579`) **bỏ qua** chunk đã `completed`: `if chunk.status != "completed"`.
- ⇒ Job **resume sau crash**: các chunk đã xong ở lần chạy trước **đã ghi finding vào DB** nhưng
  **không** xuất hiện trong list của lần chạy này ⇒ R-2 in ra con số **nhỏ hơn sự thật**, ở đúng
  kịch bản rủi ro cao nhất (job từng crash). Với R-2 là *mặt hiển thị duy nhất* của BL-04, hướng sai
  "báo ít hơn thực tế" là hướng tệ nhất.

**Đề xuất (chọn 1, cả hai đều 1 dòng spec)**:
- **(i) khuyến nghị**: cho phép R-2 chạy **1 câu `SELECT COUNT(...)`** trên `layout_qa_findings` theo
  `job_id` + `check_type LIKE 'babeldoc_%'`. Nó chạy **đúng 1 lần/job**, tại bước hoàn tất — chi phí
  bằng không, và đúng bằng câu SQL R-3 đã viết sẵn cho QA (một nguồn sự thật, không hai).
- (ii) nếu vẫn muốn tránh DB: đổi tên trường trong log thành `unfit_drops_this_run=` và thêm
  `skipped_completed_chunks=K`, để con số **không tự nhận là tổng của job**.

Điều không chấp nhận được là giữ nguyên câu chữ hiện tại — vì nó hứa "tổng của job" và giao một con
số "của lần chạy này".

---

## X8 — Gate E2E: mục tiêu ĐÚNG, thủ tục còn 2 chỗ sẽ đốt một vòng chạy thật

Mục tiêu mới **chính xác**, tôi đã đo lại trên DB (B14): chunk 5 = `199-240`, `overlap_end = 200`,
surviving = `201-240`, trang 230 nằm trong dải sống sót. Assertion `observed_pages == set(range(199,241))`
**hợp lý** và ít rủi ro báo động giả (B8). Assertion "không có finding ở trang 199-200" **hợp lý** và
là phép kiểm sống đúng chỗ cho bộ lọc F1 (199-200 chính là 2 trang bị `merge_chunk_pdfs` vứt).

Hai chỗ phải bổ sung, nếu không QA sẽ chạy xong mới biết mình đo nhầm vật:

**(1) Biên chunk KHÔNG cố định — nó phụ thuộc trạng thái thích ứng.** `chunk_size_used` là
`COLD_START_CHUNK_SIZE = 20` hoặc `WARM_CHUNK_SIZE = 40` (`job_orchestrator.py:112-113`), chọn tại
`:555-561` theo `state.observation_count >= 3 and state.consecutive_successes >= 3`. Đo thật hôm nay
(`concurrency_state`): `('babeldoc','deepseek','deepseek:deepseek-v4-flash', thread=32,
consecutive_successes=95, observation_count=133)` ⇒ **đang warm**, chạy mới sẽ ra 40 và chunk 5 đúng
`199-240`. **Nhưng `consecutive_successes` về 0 sau một lần fail** ⇒ chunk_size 20 ⇒ chunk 5 thành
`99-120`, trang 230 rơi sang chunk khác, **và** tập trang đổi ⇒ dính đúng cái bẫy mode-scale mà
§6.22.9 cảnh báo. Đề xuất: thêm **assertion 0** (tiền điều kiện): trước khi tin bất cứ assertion nào,
xác nhận `job.chunk_size_used == 40` **và** chunk đang đo có `page_start == 199 and page_end == 240`.
Một dòng, cứu một vòng chạy thật.

**(2) §6.22.9 không nói chạy bằng harness nào — mà 3 assertion đòi 3 tầng khác nhau.** Assertion 1-3
cần `BabeldocRunner` thật; assertion **5** cần bộ lọc trong `_process_chunk()`; assertion 6 cần log
R-1 (cũng trong `_process_chunk()`). Đồng thời §6.22.9 hứa *"chi phí 42 trang thay vì 418"*. Ba yêu
cầu đó **chỉ đồng thời thoả** nếu E2E là một **integration test gọi thẳng `_process_chunk()`** với
một `Chunk` thật (`chunk_index=5, page_start=199, page_end=240, overlap_start=199, overlap_end=200`)
+ `BabeldocRunner` thật (không mock) + DB session thật. Chạy qua `run_job()` sẽ dịch cả 418 trang
(tốn tiền thật) và vẫn phụ thuộc (1). Đề xuất: ghi thẳng harness đó vào §6.22.9. Kèm ghi chú: cách
này **không** phủ R-2 và `merge_chunk_pdfs` — chấp nhận được, nhưng phải nói ra thay vì để QA tự
hiểu là đã phủ.

---

## Phần E2 — Tóm tắt cho PM

**APPROVE cho Dev implement**, với:

**3 điều kiện bắt buộc (làm TRƯỚC khi Dev bắt đầu — đều là sửa tài liệu, không phải code):**
1. **X1** — sửa 4 nhóm trích dẫn `il_creater.py` → `il_creater_active.py` trong §6.22.6/§6.22.6.1,
   thêm 1 dòng cảnh báo vào §6.22.1 (R5-01/R5-05), và sửa ứng viên BL-08 thành
   `ActiveILCreater.on_page_end` (`il_creater_active.py:386-407`).
2. **X6** — BL-08 xếp ngay sau BL-04 (không để treo vô thời hạn); ghi vào BL-08 sự thật
   `run_layout_qa_gate()` hiện là dead code trong production (0 caller trong `src/`), kèm cảnh báo
   không bật nguyên trạng vì sẽ sinh ≥52 finding `blocker`/cuốn.
3. **X7** — sửa R-2: hoặc cho phép 1 câu `SELECT COUNT` (khuyến nghị), hoặc đổi tên trường thành
   `unfit_drops_this_run` + `skipped_completed_chunks`. Giữ nguyên câu chữ hiện tại là hứa sai.

**5 điểm nên sửa cùng lúc (rẻ, không chặn):** X2 (`int | None` trong `_ChunkLike`), X3 (hàm chung chỉ
sở hữu quy tắc start; sửa câu chữ test 5), X4 (ghi ràng buộc `--watermark-output-mode ≠ both` vào
§6.22.4), X5 (checksum mismatch phải có chỗ đi khi `observed == expected`), X8 (assertion 0 về
`chunk_size_used == 40` + nêu rõ harness E2E là `_process_chunk()` trực tiếp).

**Đã kiểm và đồng ý, không có ý kiến sửa**: điểm hook `create_render_units_for_page`; predicate
`_has_rendered_chars`; kênh JSONL sidecar + ràng buộc đặt trong `chunk_output_dir`; bốn trạng thái;
bỏ dedupe `debug_id`; mismatch sentinel một chiều + tuyên bố giới hạn; `optimal_scale == 0.1` là
marker chẩn đoán; đăng ký severity ở `_SEVERITY_BY_CHECK`; capability `reports_own_paragraph_drops`
+ guard `isinstance`; không đụng nhánh pdf2zh (BL-07); không tái dùng `overflow_reports`; bảng audit
R8-01 ở §6.22.7 (đã sửa đúng dòng `merge_chunk_pdfs`); mục tiêu E2E trang 230 / chunk 5 và cảnh báo
bẫy mode-scale.

**Nếu PM bác điều kiện X1** (ví dụ vì muốn Dev bắt đầu ngay): đây là điểm duy nhất tôi đề nghị
escalate lên Hiếu, vì nó không tốn công sửa (dưới 15 phút) mà cái giá bỏ qua là một patch no-op
trong tương lai — cùng khuôn Bug #9, tức cùng khuôn lỗi project này đã trả giá 2 lần.
