# Phản biện Domain Expert — US-22 Dịch EPUB (Architecture.md §6.20)

- **Người phản biện**: Domain Expert (đội hình mở rộng, CLAUDE.md global)
- **Ngày**: 2026-09-08
- **Đối tượng**: `docs/Architecture.md` §6.20 (11 tiểu mục, dòng 4241–4681), đối chiếu PRD US-22 + BR-EPUB-01..05, `docs/ba-analysis.md` §6.7
- **Phương pháp**: mọi kết luận dưới đây đều có bằng chứng TỰ đo — đọc file EPUB thật bằng stdlib (`zipfile` + `html.parser` + `ElementTree`, KHÔNG dùng chung code path với Tech Lead), đọc thẳng source `bbook_maker==1.1.0` đã cài trong cache uv (`~/.cache/uv/archive-v0/iZf9wPCckzKadLW_/book_maker/`), dựng venv riêng (`ebooklib 0.20 + bs4 4.15.0 + lxml 6.1.3`) để tái lập B-06/B-07 và thử các bước tinh vi của §6.20.5 trên chính file thật. Script probe lưu tại scratchpad phiên này (`measure_epub_stdlib.py`, `probe_bs4_ebooklib.py`).
- Ký hiệu: **[ĐÃ TỰ VERIFY]** = tôi tự đo/đọc và xác nhận; **[TIN BÁO CÁO]** = chỉ đọc Architecture.md, chưa tự kiểm; **[CHƯA VERIFY]** = giả định của chính tôi, cần Dev kiểm.

---

## 0. Kết luận tóm tắt

**Hướng kiến trúc (Phương án B — `ebooklib` đọc + Translation Engine nội bộ + `zipfile` ghi) ĐỨNG VỮNG sau phản biện.** Tôi đã tự đối chiếu 7/14 claim quan trọng nhất về `bbook_maker` vào source thật (E-03, E-05, E-06, E-09, E-10, E-11, E-13) và toàn bộ 8 số đo B-01..B-08 — tất cả đúng. Bác bỏ phương án A là đúng, **nhưng vì lý do cấu trúc (E-05 + E-13 + E-06), không phải vì con số 97,2% (B-03)** — B-03 là N=1 trên một bulletin 35 trang, không đại diện (xem §2).

**Thiết kế CHI TIẾT (§6.20.5 / §6.20.6 / §6.20.8) CHƯA AN TOÀN để giao Dev nguyên trạng.** Có **6 điểm chặn (X1–X6)** phải sửa trong Architecture.md trước khi Dev implement, trong đó 2 điểm là lỗi *nghiệp vụ ngành bánh* đo được trên chính file của user:

| # | Điểm chặn | Bằng chứng tự đo |
|---|---|---|
| X1 | Rule `extract()` bỏ `<sup>` **phá phân số định lượng**: `<sup>1</sup>/<sub>3</sub> cup` → `/3 cup`; `1<sup>1</sup>/<sub>3</sub> cups` → `1/3 cups` (sai 4×) | 6 dòng nguyên liệu thật trong `chapter01.html` |
| X2 | Lấy text thuần **gộp dòng danh sách nguyên liệu** (`<strong>…</strong><br/><strong>…</strong>`) và mất bold — Bug #7 tái sinh ở EPUB | 273/383 unit (71%) có inline child; 214 `<strong>`, 6 `<br/>` trong 1 file |
| X3 | Guard BR-EPUB-05 "số unit output == input" **mâu thuẫn** với `bilingual=True` mặc định (unit nhân đôi) → guard luôn fail hoặc phải bỏ | suy ra trực tiếp từ §6.20.5 bước 2 + §6.20.8 E9 |
| X4 | **Không tồn tại contract JSON** giữa app và LLM: `build_system_prompt()` không có chỉ thị JSON, user message của provider là `"Translate from en to vi:\n\n{text}"` — "Parse JSON trả về {unit_id: VI}" là mong muốn, không phải contract | đọc `src/core/prompt_builder.py`, `src/services/openai_provider.py:66-72` |
| X5 | Ước tính chi phí **thiếu JSON envelope**: +38% input / +23% output với `unit_id` dài như spec; +20% / +7% với id ngắn → vi phạm §6.11.6 "được ước cao, không được ước thấp" | đo trên 383 unit thật |
| X6 | **Lineage trap `doc_href`**: `ebooklib` trả `item.file_name == 'xhtml/chapter01.html'`, zip entry là `'ops/xhtml/chapter01.html'`; `book.opf_dir` KHÔNG tồn tại. Spec ghi "vd `ops/xhtml/chapter01.html`" mà không nói lấy `ops/` từ đâu | chạy `ebooklib` thật trên file |

Cộng thêm 8 điểm nên sửa (Y1–Y8) và 3 điểm cần đóng khung lại cho trung thực (Z1–Z3). Chi tiết ở §1–§5, đề xuất "Final Decision" ở §6.

---

## 1. Tự verify các claim của Tech Lead

### 1.1. Số đo cấu trúc EPUB (B-01..B-08) — [ĐÃ TỰ VERIFY, xác nhận đúng]

Đo bằng stdlib, không dùng `ebooklib`/`bs4`:

```
$ .venv/bin/python measure_epub_stdlib.py "data/uploads/9d436d7b-…Sourdough….epub"
entries: 28; first entry: 'mimetype' compress_type=0 (STORED); has META-INF/encryption.xml: False
OPF: ops/9781603424073.opf; spine items: 5; xhtml docs in spine: 5
per-document (href, raw_bytes, raw_units, kept_units, kept_chars):
   cover.html        567     0    0      0
   title.html        686     3    2     32
   copyright.html   2225     9    8   1339
   chapter01.html  66407   383  373  50868
   backmatter01.html 576     1    0      0
TOTAL kept units=383, kept chars=52239
largest doc share: chapter01.html -> 50868/52239 = 97.4%
chunk plan @8000: 7 chunks; sizes = [7922, 7808, 7999, 7794, 7568, 7627, 5521]
unit length: min=5 median=25 p90=451 max=989; units > 3000 chars: 0
```

| Claim TL | TL đo | Tôi đo | Kết luận |
|---|---|---|---|
| B-01 5 ITEM_DOCUMENT, spine 5 | 5/5 | 5/5 | đúng |
| B-02/B-03 `chapter01` chiếm 97,2% | 50.899/52.369 | 50.868/52.239 = **97,4%** | đúng (lệch <0,3% do parser khác nhau) |
| B-04 384 unit | 384 | 383 | đúng |
| 7 chunk @8000 | 7 | 7 | đúng |
| B-07 zipfile ghi tại chỗ | 27/27 byte-identical | **27/27** content byte-identical, thứ tự giữ nguyên, `mimetype` offset 0 / STORED / `extra=b''`, byte 30..58 = `mimetypeapplication/epub+zip`, `ebooklib` đọc lại 5 docs/spine 5 | đúng |
| B-08 không DRM | không có `encryption.xml` | không có | đúng |

B-05/B-06 (ebooklib chạy trên 3.14.7, `write_epub()` dời `ops/`→`EPUB/`) — **[TIN BÁO CÁO]**, không tái lập vì kết luận thiết kế (không dùng writer của ebooklib) đã được B-07 của tôi bảo đảm độc lập.

### 1.2. Sự thật về `bbook_maker==1.1.0` (E-01..E-14) — 7 claim quyết định [ĐÃ TỰ VERIFY]

Đọc thẳng source đã cài (`~/.cache/uv/archive-v0/iZf9wPCckzKadLW_/book_maker/`, `bbook_maker-1.1.0.dist-info` cùng thư mục):

| # | Tôi kiểm thế nào | Kết quả |
|---|---|---|
| E-03 không DeepSeek | `MODEL_DICT` keys + `grep -ri deepseek translator/ cli.py` | 28 key, **0** kết quả deepseek → đúng |
| E-05 `only_filelist` bỏ tài liệu không chọn | `epub_loader.py:384-391` | nhánh `only_filelist` `return index` **không** `add_item`; nhánh `exclude_filelist` **có** `add_item` → đúng |
| E-06 mọi lỗi → `sys.exit(0)` | `epub_loader.py:553-560` | `except (KeyboardInterrupt, Exception) as e: print(e); … sys.exit(0)` → đúng |
| E-09 `None` → `""` rồi vẫn chèn + xoá gốc | `helper.py:19-31` | đúng nguyên văn |
| E-10 backoff vô hạn | `helper.py:35-41` | `@backoff.on_exception(backoff.expo, Exception, …)` **không** `max_tries`/`max_time` → đúng |
| E-11 không usage accounting | `grep -rn "\.usage\|prompt_tokens\|completion_tokens\|input_tokens" book_maker/` | **0** kết quả → đúng |
| E-13 resume = pickle theo chỉ số tuyến tính | `epub_loader.py:117,565,616` + `_process_paragraph:147-148` (`if self.resume and index < p_to_save_len: p.string = self.p_to_save[index]`) | đúng — chỉ số `index` chạy xuyên mọi item được xử lý, đổi tập `--only_filelist` là lệch |

E-07/E-14 (chạy thật với key giả), E-12 (`--prompt` format) — **[TIN BÁO CÁO]**; không ảnh hưởng kết luận vì E-05/E-06/E-13 đã đủ để bác bỏ A.

**Phát hiện thêm về A mà Tech Lead chưa ghi** (bổ sung vào bảng so sánh, §4):
- `DEFAULT_PROMPT` của A (`chatgptapi_translator.py:69`) là đúng **1 câu**: *"Please help me to translate,`{text}` to {language}, please return only translated content not include the origin text"*. Luận điểm "cộng đồng đã tối ưu prompt riêng cho EPUB" (PM nêu trong brief cho tôi) **không có thật** — [ĐÃ TỰ VERIFY].
- A gửi `new_p.text` (`epub_loader.py:156`) — `.text` của bs4 nối các string con **không có dấu cách**: trên đoạn nguyên liệu thật ra `'4 cups unbleached white flour2 teaspoons salt2 tablespoons honey4 cups potato water'` — [ĐÃ TỰ VERIFY]. A **tệ hơn** B ở chính điểm này.
- A mặc định `exclude_translate_tags="sup"` (`cli.py:288`, `epub_loader.py:55`) → A cũng mắc đúng lỗi X1 (phá phân số) trên file này.
- `--translate-tags` mặc định của A = `"p"` → A bỏ qua mọi `h1..h6`, `li` — 34 tiêu đề công thức (`<h3>`) trong file này sẽ **không được dịch** nếu dùng mặc định.

---

## 2. Điểm PM yêu cầu #1 + #2 — B-03 có phải nền tảng vững không? Chunk theo "chương" có khả thi trên file thật không?

### 2.1. B-03 đúng về số, nhưng KHÔNG đại diện — [ĐÃ TỰ VERIFY]

`ops/9781603424073.opf` ghi rõ `<dc:format>35 Pages</dc:format>`, `<dc:publisher>Storey Publishing</dc:publisher>`, mô tả *"Storey's Country Wisdom Bulletins … 170 titles in this series"*. Đây là **một bulletin 35 trang** (Bulletin A-50, xem `copyright.html`), NCX có đúng 1 navPoint nội dung ("Chapter 1"). Toàn bộ 34 "chương" thật (công thức) là `<h3>` **bên trong** 1 file XHTML.

Sách EPUB thương mại thông thường (cookbook 200–400 trang) tách 1 XHTML mỗi chương/mục — trên sách như vậy, `--only_filelist` của A *có* thể chọn từng chương. Tức là **B-03 chỉ chứng minh A thất bại trên file này**, không chứng minh A thất bại nói chung. Câu "B-03 là con số quyết định cả section này" (§6.20.3) và "Lý do 1" trong QUYẾT ĐỊNH (§6.20.4) đang đặt trọng lượng lớn nhất lên lý do yếu nhất về tính tổng quát.

**Nhưng quyết định vẫn đúng**, vì 3 lý do cấu trúc bất biến theo sách:
- E-05: tài liệu ngoài `--only_filelist` **bị xoá khỏi output** → chunk theo tài liệu đòi tự ghép EPUB lại từ N bản output — công ngang tự viết writer.
- E-13: resume theo chỉ số tuyến tính toàn sách → **không thể** vừa chunk theo tài liệu vừa resume.
- E-06/E-08/E-09: exit 0 + đoạn rỗng thay bản gốc — 3 kiểu silent failure dự án đã bị.

→ **Đề nghị**: đổi thứ tự lý do trong §6.20.4: lý do 1 = E-05+E-13 (A không có cơ chế chunk *tương thích resume* nào cả), lý do 2 = E-06/E-08/E-09, lý do 3 = B-03 *minh hoạ* trên sách của user. Ghi rõ B-03 là N=1 bulletin. **Không đổi quyết định.**

### 2.2. Chunk theo "chương" (BR-EPUB-02) trên file thật — [ĐÃ TỰ VERIFY]

Nếu hiểu "chương" = tài liệu XHTML: **không khả thi** trên file này (1 tài liệu = 97,4%) — phương án B *cũng* gặp đúng vấn đề như A ở tầng file, đúng như PM lo. Tech Lead đã nhìn thấy điều này và §6.20.7 chốt "cắt ƯU TIÊN tại ranh giới tài liệu nhưng KHÔNG bị ràng buộc bởi nó" — mô hình chunk theo dãy unit. Tôi mô phỏng thuật toán §6.20.7 (cắt theo ngân sách ký tự tại ranh giới unit): 7 chunk 5.521–7.999 ký tự, **không chunk nào cắt giữa đoạn** — khả thi, và đây chính là điểm B làm được mà A không làm được (A không có granularity dưới tài liệu ngoài `--block_size` nhánh accumulated, mà nhánh đó dính E-10 retry vô hạn).

Lưu ý ngữ nghĩa cho PRD: BR-EPUB-02 viết "Đơn vị chunk = chương". Thực tế được chốt là "dãy unit ≤ 8.000 ký tự, ưu tiên ranh giới tài liệu". PM nên sửa câu chữ BR-EPUB-02 cho khớp, tránh QA test theo nghĩa đen "1 chunk = 1 chương" rồi fail.

---

## 3. Điểm PM yêu cầu #3 — Ghi ngược bằng `zipfile`

### 3.1. An toàn file gốc — [ĐÃ TỰ VERIFY qua spec] 

§6.20.5 bước 3 "Ghi zip **mới**" và §6.20.9 bước 7 output = `data/outputs/{job_id}/translated_vi.epub` ≠ `job.file_path` (`data/uploads/…`). **File input không bao giờ bị ghi đè** — không có rủi ro hỏng input khi fail giữa chừng. Xác nhận.

### 3.2. Rủi ro output cụt (crash giữa lúc ghi) — [CHƯA VERIFY, suy luận]

Spec chưa nói ghi qua file tạm. Nếu tiến trình chết giữa `ZipFile.write`, `translated_vi.epub` là zip cụt (thiếu central directory). Guard BR-EPUB-05 (E9) mở lại file **trước** khi set `job.output_path` (E10) nên user không tải nhầm file hỏng — tốt. Nhưng resume lần sau sẽ ghi đè file cụt mà không có gì bảo đảm. → **Y5**: ghi ra `merged_path.with_suffix(".epub.tmp")` rồi `os.replace()` — 2 dòng, đóng hẳn.

### 3.3. Tái lập B-07 độc lập — [ĐÃ TỰ VERIFY]

Tôi viết lại vòng ghi bằng `zipfile` từ đầu theo đúng mô tả §6.20.5 bước 3 (duyệt `infolist()`, thay đúng 1 entry, `ZipInfo` mới với `date_time` gốc, `mimetype` STORED, còn lại DEFLATED):

```
entries in=28 out=28 same_order=True
unchanged entries byte-identical (content): 27/27
first entry='mimetype' compress_type=0 header_offset=0 extra=b''
raw bytes 30..58: b'mimetypeapplication/epub+zip'
ebooklib re-read: docs=5 spine=5
```

Đúng OCF (mimetype đầu file, không nén, không extra field). Cách này **đứng vững**. Ghi chú nhỏ: "copy nguyên bytes" trong spec chỉ đúng cho *nội dung* (giải nén rồi nén lại), bytes nén có thể khác — vô hại.

### 3.4. Vấn đề THẬT nằm ở bước re-serialize XHTML, không ở zip — [ĐÃ TỰ VERIFY]

Spec §6.20.5 bước 2 "parse lại bằng `BeautifulSoup`" **không chỉ định parser**. Tôi thử cả 3 trên 5 XHTML thật:

| parser | well-formed XML sau `str(soup)`? | ghi chú |
|---|---|---|
| `html.parser` | 5/5 well-formed | **lowercase attribute**: `viewBox` → `viewbox` trên `cover.html` (đo được) → hỏng SVG nếu tài liệu có cả SVG + text |
| `lxml` (HTML mode) | 5/5 | như trên |
| `xml` (lxml-xml) | 5/5 | giữ `viewBox`, tự thêm `<?xml version="1.0" encoding="utf-8"?>` (hợp lệ) |

`cover.html` (0 unit) không bị ghi lại nên file này không lộ lỗi — nhưng EPUB có trang tiêu đề SVG + text là phổ biến. → **Y1**: chỉ định `features="xml"` làm parser chính; fallback `html.parser` chỉ khi XML parse fail, kèm **kiểm well-formed bằng `ET.fromstring()` trên output trước khi ghi**; không well-formed → fail chunk/job rõ ràng, **không bao giờ ghi XHTML hỏng vào EPUB** (reader XHTML strict như Apple Books hiện trang trắng, không báo lỗi — silent failure với user).

---

## 4. Điểm PM yêu cầu #4 — Bảng so sánh A vs B thiếu gì, thiên vị chỗ nào?

Bảng §6.20.4 đúng ở mọi dòng tôi kiểm. Thiếu 4 tiêu chí, và có 1 chỗ đánh giá B **quá lạc quan** (không phải thiên vị chống A):

| Tiêu chí thiếu | A | B (spec hiện tại) | B (sau khi sửa X1/X2) |
|---|---|---|---|
| Inline markup trong đoạn (`<strong>`, `<em>`, `<br/>`, `<a id>`) | **Mất hết** trong bản dịch (`new_p.string = text`); `.text` nối không dấu cách | **Mất hết** (spec: "thay nội dung text của node") | Giữ được nếu gửi inner-HTML |
| Phân số `<sup>1</sup>/<sub>3</sub>` | **Phá** (mặc định `exclude sup`) | **Phá** (spec mượn đúng rule đó) | Đúng nếu bỏ rule |
| Ngữ cảnh giữa đoạn | `--use_context` (rolling N đoạn trước, `chatgptapi_translator.py:140-186`) | mỗi request gộp ~3.000 ký tự đoạn liên tiếp — tương đương hoặc tốt hơn | như B |
| Dịch TOC (NCX/nav), `<title>` | A duyệt mọi `ITEM_DOCUMENT` (kể cả nav) | B chỉ theo spine, không đụng NCX → TOC trong reader vẫn tiếng Anh | ghi known limitation (Y7) |
| Chất lượng prompt | 1 câu generic (đã đọc source) | `build_system_prompt()` có glossary + unit conversion + typography rules | B hơn hẳn, **miễn là** có contract JSON (X4) |

Kết luận về "rủi ro chất lượng dịch" mà PM hỏi: §6.20.11 mục 6 nói "khác, không hiển nhiên tốt/xấu hơn" là **quá dè dặt theo hướng có lợi cho A** — A không có ưu thế prompt nào; nhưng đồng thời §6.20.4 dòng "Công phải tự viết: Parse XHTML → unit, ghi ngược, chunk plan (~1 module)" **đánh giá thấp** công của B: xử lý inline markup + contract JSON + guard bilingual là phần khó thật, không phải "vài chục dòng BeautifulSoup" như §6.20.4 viết.

---

## 5. Các điểm chặn và điểm nên sửa — chi tiết + bằng chứng

### X1 — Rule `extract()` `<sup>` phá định lượng công thức [ĐÃ TỰ VERIFY] — CHẶN

`chapter01.html` có 6 dòng nguyên liệu dùng phân số dựng bằng `<sup>`/`<sub>`:
```
<p class="indent2"><strong><sup>1</sup>/<sub>3</sub> cup soy grits</strong></p>
<p class="indent2"><strong>1<sup>1</sup>/<sub>3</sub> cups unbleached white flour</strong></p>
```
Áp đúng rule §6.20.5 ("Trước khi lấy text, `extract()` bỏ các thẻ con `sup`, `code`, `pre`"):
```
original text : 1/3 cup soy grits
after extract : /3 cup soy grits          ← mất tử số
"1 1/3 cups"  → "1/3 cups"                ← sai 4 lần lượng bột trong bánh mì
```
Đây là lỗi **nghiệp vụ ngành bánh** loại tệ nhất: bản dịch trông hoàn toàn bình thường, chỉ sai con số. Prompt của app có rule "BẤT BIẾN NỘI DUNG: giữ đủ số" nhưng LLM không cứu được thứ đã bị cắt **trước** khi nó nhìn thấy. Rule này mượn từ mặc định của bbook_maker (E-01 "ý tưởng đúng, mượn lại") — trên cookbook, nó là ý tưởng **sai**. Ngoài ra file còn 107 ký tự phân số Unicode (`½`×63, `¼`×27, `¾`×17) đi qua an toàn — chỉ dạng `<sup>/<sub>` bị phá.

**Sửa**: bỏ hoàn toàn rule extract `sup`/`sub`. Gộp vào giải pháp X2 (gửi inline HTML — `<sup>`/`<sub>` đi nguyên vẹn qua LLM).

### X2 — Text thuần làm gộp dòng danh sách nguyên liệu, mất bold [ĐÃ TỰ VERIFY] — CHẶN

Census trên 383 unit của `chapter01.html`: **273 unit (71%) có ít nhất 1 thẻ con**; phân bố `{strong: 214, a: 35, em: 26, img: 10, br: 6, sup: 6, sub: 6, small: 1}`. Ví dụ thật:
```html
<p class="blockquote"><strong>4 cups unbleached white flour</strong><br/><strong>2 teaspoons salt</strong><br/><strong>2 tablespoons honey</strong><br/><strong>4 cups potato water</strong></p>
```
`get_text(" ", strip=True)` (cách tự nhiên nhất Dev sẽ viết) → `'4 cups unbleached white flour 2 teaspoons salt 2 tablespoons honey 4 cups potato water'` — 4 nguyên liệu thành 1 dòng, không bold. Đây chính là **Bug #7 (line-break/list bị gộp) mà user đã báo trên PDF**, tái sinh ở EPUB ngay increment đầu tiên, trên nội dung quan trọng nhất của sách bánh.

**Sửa (đề xuất)**: `EpubUnit.text` = **inner-HTML** của node (chuỗi `"".join(str(c) for c in node.children)`), giữ `strong/em/b/i/sup/sub/br/a/span/small`; system prompt EPUB nói rõ "giữ nguyên mọi thẻ HTML inline, chỉ dịch text"; khi ghi ngược, parse fragment trả về bằng bs4 rồi `node.clear(); node.append(fragment children)`. Rule 4 của `build_system_prompt()` ("Bold, italic… phải giữ nguyên vị trí") **chỉ có nghĩa nếu LLM nhìn thấy markup** — spec hiện tại tự mâu thuẫn với prompt mình dùng. Phương án tối thiểu nếu PM muốn giảm scope: `get_text("\n")` + tái tạo `<br/>` từ `\n` — cứu được dòng, không cứu được bold.

### X3 — Guard BR-EPUB-05 mâu thuẫn với `bilingual=True` mặc định — CHẶN

§6.20.8 E9: "số unit của file output **bằng** số unit của file input" và "ít nhất 90% unit có nội dung khác bản gốc". Với `bilingual=True` (đã chốt §6.20.11 mục 2), `write_translated()` **chèn thêm** 1 node copy sau mỗi unit → `EpubDocument.load(merged_path)` sẽ đếm **~2×** unit, và ~50% unit (bản gốc) có nội dung **giống hệt** bản gốc. Guard như viết sẽ **fail mọi job bilingual**, hoặc Dev sẽ "nới" guard cho qua — cả 2 đều là mất guard.

**Sửa**: (a) node copy phải được **đánh dấu tường minh**: `lang="vi"` (đúng ngữ nghĩa XHTML, giúp reader/TTS) + `class="bb-vi"`; (b) `EpubDocument.load()` **bỏ qua** node có dấu đó theo mặc định (hệ quả tốt: upload lại 1 EPUB đã dịch song ngữ sẽ không dịch đôi); (c) guard viết lại: `originals == total_units input` **và** `số node bb-vi ≥ 90% originals` **và** `≥ 90% cặp (gốc, vi) có text khác nhau`. Với `bilingual=False`: giữ guard cũ.

### X4 — Không tồn tại contract JSON app↔LLM — CHẶN

Đọc code thật: `OpenAIProvider.translate()` gửi `system=glossary_prompt`, `user="Translate from {src} to {tgt}:\n\n{text}"` (`openai_provider.py:66-72`); `build_system_prompt()` không có dòng nào về JSON/id. §6.20.8 bước 2 nói "Dựng payload JSON array … Parse JSON trả về `{unit_id: VI}`" — không có gì ép model trả JSON, trả đúng id, hay không bọc trong ```json fence. Với DeepSeek/GPT, đưa JSON vào sau câu "Translate…" sẽ ra kết quả **không ổn định** (khi thì JSON, khi thì prose, khi thì dịch cả key). babeldoc đã phải viết "mandatory per-paragraph JSON output contract" riêng (đã ghi trong `prompt_builder.py` docstring) — app đang lặp lại đúng bài toán đó mà chưa thiết kế.

**Sửa**: (a) thêm `build_epub_batch_prompt()` trong `prompt_builder.py` (3 phần: system prompt hiện có + đoạn contract JSON tường minh + ví dụ 1 cặp); (b) parser trả về chịu được code fence, khoảng trắng, id dạng số/chuỗi; (c) **golden fixture từ output thật** `tests/fixtures/epub_llm/deepseek_batch_response_*.json` capture ở R5-02 spike — định dạng output của LLM là external contract theo tinh thần Protocol 5, không được viết mock tay; (d) DeepSeek có JSON mode (`response_format={"type":"json_object"}`) **[CHƯA VERIFY]** — nếu Dev verify được thì thêm tham số optional vào provider, không bắt buộc.

### X5 — Ước tính chi phí thiếu JSON envelope [ĐÃ TỰ VERIFY] — CHẶN

Đo trên 383 unit thật (`json.dumps` payload trừ đi ký tự nội dung):

| | overhead input | overhead output (id echo lại, VI 2 ký tự/token) |
|---|---|---|
| `unit_id` dài như spec (`ops/xhtml/chapter01.html#123`) | 19.286 ký tự ≈ **+38%** so với 50.899 ký tự nội dung | ≈ 6.8k token ≈ **+23%** so với ~29.5k token VI |
| id ngắn cục bộ trong request (`"0".."N"`) | 9.961 ký tự ≈ **+20%** | ≈ 2.2k token ≈ **+7%** |

Công thức §6.20.6 (`source_text_chars / 4 + llm_request_count × overhead / 4`) **không có số hạng nào** cho envelope → ước **thấp** 20–38% input. §6.11.6 cho phép ước cao, cấm ước thấp — đây là vi phạm trực tiếp, ở đúng lớp bảo vệ tài chính.

**Sửa**: (a) trong request dùng id ngắn `0..N`, map ngược sang `unit_id` ở app (giảm 1/2 overhead, giảm cả rủi ro model gõ sai id dài); (b) thêm `EPUB_JSON_ENVELOPE_CHARS_PER_UNIT = 26` (đo: 9.961/383) vào công thức: `source_text_chars += len(units) × 26` — vẫn đi qua `estimate_job_cost_v2()`, không tạo công thức thứ hai; (c) sau live run R5-03, so `actual_cost` (metered) với ước tính — phải ≥ 1,0× (bài học golden file §6.11.6).

### X6 — Lineage trap `doc_href` (ebooklib ≠ zip) [ĐÃ TỰ VERIFY] — CHẶN

```
file_name='xhtml/chapter01.html'  get_name='xhtml/chapter01.html'  in_zip_as_is=False
book.opf_dir attr: <none>
```
`ebooklib` trả href **tương đối OPF**, zip cần đường dẫn **đầy đủ** (`ops/…`). Spec §6.20.5 định nghĩa `doc_href` là "tên entry trong zip, vd ops/xhtml/chapter01.html" nhưng không nói lấy `ops/` ở đâu; `EpubBook` không expose `opf_dir`. Hai kịch bản khi Dev dùng thẳng `item.file_name`: (i) `zin.read(doc_href)` → `KeyError` (ồn, tốt); (ii) vòng ghi so `info.filename == doc_href` → **không khớp gì**, mọi entry copy nguyên → output == input, `status=completed` — chính xác Bug #5 dạng EPUB. Guard X3 (sau khi sửa) sẽ bắt được, nhưng không nên để guard là lớp duy nhất.

**Sửa**: `load()` tự đọc `META-INF/container.xml` → `rootfile/@full-path` → `opf_dir = posixpath.dirname(full_path)`; `doc_href = posixpath.normpath(posixpath.join(opf_dir, item.file_name))`; **test bắt buộc**: `all(u.doc_href in zip.namelist() for u in doc.units)` trên file thật (R6-02).

### Y1 — Parser XHTML (xem §3.4) — nên sửa
### Y2 — Quy tắc chèn bản dịch trong `bilingual=True` — nên sửa [ĐÃ TỰ VERIFY một phần]

- **32 unit** chứa `<a id="page_N"/>` (anchor trang). `copy(node)` mang theo `id` → **duplicate id** trong 1 document → XHTML không hợp lệ (epubcheck error), link nội bộ/page-list trỏ sai. Sửa: strip mọi `id` trong bản copy (node và descendants).
- `<td>`/`<th>`: `insert_after` tạo **ô mới** → phá số cột bảng nguyên liệu. File này không có bảng (0 `<table>`), nhưng cookbook thương mại có. Sửa: với td/th chèn `<br/><span lang="vi">…</span>` **bên trong** ô thay vì sibling.
- `<img>` trong `<p>` (10 trường hợp, `<img>` parent luôn là `<p>`): bản copy bị `.string=` xoá img — chấp nhận được ở bilingual (gốc còn), nhưng ở `bilingual=False` là **mất ảnh**. Sửa: monolingual chỉ thay text node, không đụng element con (đi cùng giải pháp X2).
- Nested `li > ul`: "chỉ lấy node ngoài cùng" → 1 unit khổng lồ, bản dịch copy phẳng → mất cấu trúc lồng. Sửa: lấy **innermost** block có text trực tiếp; `li` chứa `ul` con thì chỉ dịch phần text trực tiếp của `li`.

### Y3 — `unit_id` ordinal nhạy với drop rules; thiếu kiểm hash — nên sửa

`ordinal` = chỉ số trong danh sách **đã lọc** (§6.20.5) → sửa 1 drop rule (vd rule ISBN) ở version sau là mọi id sau điểm đó lệch **trong cùng tài liệu** — resume job cũ sẽ **dán bản dịch vào sai đoạn**, nguy hiểm hơn cả rỗng. Sửa: (a) `ordinal` đếm trên **mọi** node thuộc tag list *trước* lọc (drop rule không ảnh hưởng id); (b) `units.json` lưu `{unit_id: {"src_sha1": …, "vi": …}}`, merge kiểm hash; lệch → chunk `failed` + message rõ. Spec đã bác "hash làm key" (đúng) — nhưng hash làm **check** là thứ khác và cần thiết.

### Y4 — Unit quá khổ không có rule — nên sửa

Spec "không bao giờ cắt giữa 1 đoạn văn" nhưng không nói unit > `EPUB_REQUEST_CHAR_BUDGET` xử lý sao. Tính ngưỡng: `max_tokens=8192` (cả 4 provider); VI ≈ 1,16 × EN ký tự / 2 ký tự/token → unit > ~13.000 ký tự EN làm output **cụt** → JSON hỏng → retry lẻ vẫn cụt → chunk failed, không có lối thoát. File này max unit = 989 ký tự (an toàn), nhưng `blockquote` dài/`li` lồng ở sách khác thì không. Sửa: unit > request budget → gửi **một mình**; unit > `EPUB_UNIT_HARD_MAX_CHARS=10_000` → job `failed` với message nêu đúng `unit_id` (không cắt câu ở v1, ghi known limitation).

### Y5 — Ghi qua file tạm + `os.replace` (§3.2) — nên sửa
### Y6 — `with_retry` không retry lỗi 5xx — nên sửa

`src/utils/retry.py`: transient = `RateLimitError, TimeoutError, ConnectionError`; `openai.APIError` (gồm `InternalServerError`, `APIConnectionError`, `APITimeoutError`) bị map thành `TranslationProviderError` → **không retry**. Nhánh PDF ít gặp vì pdf2zh/babeldoc tự retry bên trong; nhánh EPUB gọi API trực tiếp ~18 request/50k ký tự (sách 600k ký tự ≈ 200 request tuần tự) — 1 lỗi 502 làm job `failed`. Resumable nên không mất tiền, nhưng UX kém. Sửa: provider map 5xx/connection/timeout của SDK sang lớp transient (nhỏ, có test).

### Y7 — Known limitations phải ghi vào Architecture.md + PRD

NCX `navLabel`/EPUB3 `nav.xhtml` (nếu ngoài spine) và `<title>` **không được dịch** → mục lục trong reader vẫn tiếng Anh; `<dc:language>` giữ `en`; tài liệu ngoài spine không dịch. Không chặn v1, nhưng user sẽ hỏi.

### Y8 — Rule ISBN bỏ cả đoạn

`copyright.html` có `<p class="blockquote">Baking with sourdough / by Sara Pitzer<br/>A Storey Publishing Bulletin, A-50<br/>ISBN 978-0-88266-225-1</p>` → rule "khớp ISBN" bỏ **cả đoạn** kể cả tên sách/tác giả. Chấp nhận được cho trang bản quyền; ghi rõ rule là "chứa ISBN" hay "chỉ là ISBN".

### Z1 — Tăng N trước spike (§2.1)

Trên máy này chỉ có đúng 1 EPUB thật (`~/Downloads/…Sourdough….epub` **byte-identical** với bản trong `data/uploads/`, `cmp` xác nhận). Đề nghị PM xin user **≥1 EPUB sách dài thật** (cookbook nhiều chương) trước R5-02, để Dev đo thêm: số XHTML, có `<table>` không, nested list, max unit, SVG trong tài liệu có text, EPUB3 nav. Không có dữ liệu này, Y2/Y4 chỉ là phòng thủ lý thuyết.

### Z2 — Bảng so sánh (§4) — bổ sung 4 dòng, bỏ ngầm định "prompt cộng đồng".

### Z3 — `EPUB_CHUNK_CHAR_BUDGET=8000` — hợp lý, nhưng gọi đúng tên

8.000 là **granularity checkpoint** (Lớp 3 overshoot tối đa = 1 chunk ≈ $0,003 DeepSeek / ≈ $0,05 Claude Sonnet), không phải giới hạn context. Giới hạn context nằm ở `EPUB_REQUEST_CHAR_BUDGET=3000`: ≈ 900 token nội dung + 20% envelope + ~450 token system prompt ≈ 1,4k in / ≈ 2k out — cách xa `max_tokens=8192` của cả 4 provider. Trade-off cần ghi: 18 request × ~450 token system prompt ≈ 8k token overhead ≈ **40% token nguồn** — nếu JSON ổn định ở spike, cân nhắc nâng request budget lên 5.000–6.000 để giảm một nửa overhead. Cả 2 hằng số nên ở `Settings` (`.env`), đúng như TL đề xuất. **Đồng ý với TL**: N=1, đánh dấu ⚠️ chưa kiểm chứng sách lớn.

---

## 6. Final Decision (đề xuất cho PM/Tech Lead)

1. **Giữ Phương án B.** Không mở lại A. Viết lại thứ tự lý do trong §6.20.4 (E-05+E-13 → E-06/08/09 → B-03 minh hoạ), ghi rõ B-03 là bulletin 35 trang N=1.
2. **Chưa giao Dev** cho tới khi Tech Lead cập nhật §6.20.5/§6.20.6/§6.20.8 cho 6 điểm X1–X6. Ước lượng: 1 vòng sửa Architecture (không cần research ngoài — mọi bằng chứng đã có trong file này), rồi Human Checkpoint 2 lại cho riêng §6.20.
3. **Thứ tự bắt buộc trong R5-02 spike của Dev** (bổ sung vào §6.20.10 mục 1): (a) `doc_href` ∈ `zip.namelist()` cho 100% unit; (b) round-trip `chapter01.html` qua parser `xml` → `ET.fromstring` OK; (c) 6 dòng `<sup>1</sup>/<sub>3</sub>` ra đúng "1/3"; (d) đoạn nguyên liệu 4 `<br/>` ra đúng 4 dòng + bold; (e) 1 request thật DeepSeek với payload JSON → capture golden fixture; (f) so ước tính (có envelope) với `actual_cost` metered ≥ 1,0×.
4. **QA gate bổ sung** (§6.20.10): mở file output bằng reader thật (Apple Books hoặc Calibre viewer), kiểm 1 công thức có phân số + danh sách nguyên liệu; chạy `epubcheck` nếu cài được (duplicate id, well-formedness) — **[CHƯA VERIFY]** epubcheck có cài được trên máy này không.
5. **PRD**: sửa câu chữ BR-EPUB-02 ("đơn vị chunk = dãy đoạn ≤ ngân sách ký tự, ưu tiên ranh giới tài liệu"); BR-EPUB-05 viết lại theo X3; thêm known limitations Y7.

**Trả lời câu hỏi cốt lõi của PM — "thiết kế có AN TOÀN để giao Dev ngay không?"**: **Chưa.** Về tài chính: X5 (ước thấp 20–38%) và X4 (không có contract JSON → retry/fail không đoán được) là 2 gap nằm đúng trên lớp bảo vệ chi phí. Về nghiệp vụ: X1/X2 làm sai định lượng và gộp dòng nguyên liệu — trên sách bánh, đây là lỗi user sẽ phát hiện ngay ở công thức đầu tiên, và là đúng loại lỗi (Bug #7) vừa tốn 8 vòng QA để sửa bên PDF. Cả 6 điểm đều sửa được trong Architecture.md mà không đổi hướng kiến trúc.
