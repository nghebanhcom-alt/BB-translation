# Design Log — BB-Translation

> **Nhật ký thiết kế / Root Cause Analysis / Final Decision** — tách khỏi `docs/Architecture.md`
> ngày **2026-09-10** theo **Protocol C** (kỷ luật tài liệu đặc tả, CLAUDE.md).
>
> **Vì sao tách**: `Architecture.md` đã phình lên 12.818 dòng (~238k token — lớn hơn cả context
> window của một agent), trong đó **44% là nhật ký sự kiện** chứ không phải mô tả kiến trúc hiện
> hành. Hệ quả thật: một brief kiểu "Dev đọc Architecture.md trước khi code" **về mặt vật lý không
> thực thi được** — mỗi agent buộc phải đọc chắp vá một mảnh khác nhau. Đây chính là cơ chế đã sinh
> ra Bug #5 và Bug #9.
>
> **Nội dung KHÔNG bị đổi một chữ nào** — chỉ chuyển chỗ nguyên văn. Lịch sử đầy đủ vẫn ở
> `git log -p -- docs/Architecture.md`.
>
> **Ranh giới trách nhiệm giữa 2 file** (bắt buộc, Protocol C):
> - `docs/Architecture.md` = **trạng thái hiện hành**. Hợp đồng đang có hiệu lực: tech stack, data
>   model, API, luồng xử lý, quyết định kiến trúc đang áp dụng. Dev/Reviewer/QA đọc file này để biết
>   *hệ thống PHẢI như thế nào*.
> - `docs/design-log.md` (file này) = **vì sao tới được trạng thái đó**. RCA, phản biện Domain
>   Expert, Final Decision, đo đạc thực nghiệm — theo thứ tự thời gian, chỉ append. Đọc file này khi
>   cần biết *tại sao lại thế*, hoặc trước khi định lật một quyết định cũ.
>
> **Luật ghi mới**: mọi RCA/phản biện/Final Decision mới append vào **cuối file này**. Khi một quyết
> định ở đây làm đổi hợp đồng hệ thống, Tech Lead phải cập nhật phần tương ứng trong
> `Architecture.md` §1–10 — **không để hợp đồng chỉ sống trong nhật ký**.

## Mục lục

1. [Root Cause Analysis: Line-break/List Regression (2026-09-06)](#root-cause-analysis-line-breaklist-regression-2026-09-06)
2. [Đánh giá hướng Post-Processing cho lỗi gộp dòng Numbered List (2026-09-06)](#đánh-giá-hướng-post-processing-cho-lỗi-gộp-dòng-numbered-list-2026-09-06)
3. [Đo lại F1 trên nhiều trang — kết quả live A/B/C (2026-09-06)](#đo-lại-f1-trên-nhiều-trang-kết-quả-live-abc-2026-09-06)
4. [US-16 — Nén ảnh sau khi ghép (`compress_pdf_images`) — thiết kế (2026-09-06)](#us-16-nén-ảnh-sau-khi-ghép-compress_pdf_images-thiết-kế-2026-09-06)
5. [Root Cause Analysis: Text Overlap, Content-Loss & Reading-Order trên trang layout phức tạp (2026-09-07)](#root-cause-analysis-text-overlap-content-loss-reading-order-trên-trang-layout-phức-tạp-2026-09-07)
6. [Final Decision: Babeldoc Layout Bug Fix Roadmap (sau phản biện Domain Expert, 2026-09-07)](#final-decision-babeldoc-layout-bug-fix-roadmap-sau-phản-biện-domain-expert-2026-09-07)
7. [US-16 v2 — Mở rộng phạm vi sang ảnh `/FlateDecode` (2026-09-08)](#us-16-v2-mở-rộng-phạm-vi-sang-ảnh-flatedecode-2026-09-08)
8. [US-16 v2 — Phản biện của Domain Expert (2026-09-08)](#us-16-v2-phản-biện-của-domain-expert-2026-09-08)
9. [US-16 v2 — Final Decision sau phản biện Domain Expert (2026-09-08)](#us-16-v2-final-decision-sau-phản-biện-domain-expert-2026-09-08)
10. [Bug #9 — `font_shrink_page()` phá output của babeldoc: tắt hẳn cho engine `babeldoc` (2026-09-08)](#bug-9-font_shrink_page-phá-output-của-babeldoc-tắt-hẳn-cho-engine-babeldoc-2026-09-08)
11. [Bug #10 — babeldoc cắt ngang từ tiếng Việt giữa chừng (`_get_width_before_next_break_point` đếm đôi bề rộng ký tự hiện tại) — thiết kế bản vá (Tech Lead, 2026-09-09)](#bug-10-babeldoc-cắt-ngang-từ-tiếng-việt-giữa-chừng-_get_width_before_next_break_point-đếm-đôi-bề-rộng-ký-tự-hiện-tại-thiết-kế-bản-vá-tech-lead-2026-09-09)
12. [Bug #EPUB-3 — Quét job mồ côi (orphan) lúc server startup (Tech Lead, 2026-09-10)](#bug-epub-3-quét-job-mồ-côi-orphan-lúc-server-startup-tech-lead-2026-09-10)
13. [BL-04 — Phát hiện babeldoc tự bỏ đoạn: verify lại R5-05 + Final Decision (Tech Lead, 2026-09-11)](#bl-04-phát-hiện-babeldoc-tự-bỏ-đoạn-verify-lại-r5-05-final-decision-tech-lead-2026-09-11)
14. [Final Decision: Hiếu trả lời HOI-04/HOI-05 (Bug #EPUB-5) — 2026-09-11](#final-decision-hiếu-trả-lời-hoi-04hoi-05-bug-epub-5-2026-09-11)

---

## Root Cause Analysis: Line-break/List Regression (2026-09-06)

**Tác giả**: Tech Lead — phân tích, KHÔNG implement. Dev implement ở bước sau.
**Triệu chứng user báo**: "Đôi chỗ bóc tách xuống dòng chưa chính xác" + "Xuống dòng ở
các chỗ bulleted/numbered".

### N1. Kết luận ngắn

Root cause **KHÔNG nằm trong code của team**. Nó nằm ở heuristic tách đoạn của babeldoc,
được kích hoạt bởi flag `--split-short-lines` mà `BabeldocRunner` hardcode bật:

- `src/services/babeldoc_runner.py:278` — `"--split-short-lines"` trong list `args`.

Commit `250709c` **không tạo ra** bug này. `git log -S "--split-short-lines" --
src/services/babeldoc_runner.py` chỉ trả về đúng 1 commit: `b29a54b` (Initial commit
v1.2.0, 2026-09-05) — flag đã có từ đầu. `250709c` chỉ đụng `_thinking_args` và
`_assert_gemini_model_safe`.

**Vì sao bug xuất hiện "sau" 250709c**: đây là bug latent bị **bóc trần** (unmask) chứ
không phải bug mới — cùng dạng với Bug #5 trong bối cảnh Protocol 6. Trước 250709c,
`deepseek-v4-flash` đốt hết `max_tokens=2048` vào thinking token → `json.loads("")` raise →
babeldoc rơi cả batch xuống nhánh fallback (giữ nguyên text gốc, không render lại layout
đã tách đoạn). Sau khi 250709c gửi `--openai-thinking disabled`, dịch **thành công** →
babeldoc lần đầu tiên thực sự **render theo cấu trúc đoạn mà `paragraph_finder` đã tách**.
Cấu trúc đó vốn đã sai từ đầu, chỉ là trước đây không ai nhìn thấy vì nội dung bị mất
trước khi tới bước render.

### N2. Nguồn xác thực (Protocol 5 / R5-01)

Toàn bộ claim dưới đây đọc trực tiếp từ **source thật của babeldoc 0.6.4 đã cài**
(`babeldoc --version` → `babeldoc 0.6.4`), tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`.
Không có claim nào từ trí nhớ.

| # | Claim | Nguồn (file:line) |
|---|-------|-------------------|
| L1 | `--split-short-lines` là `store_true`, help ghi rõ **"may cause poor typesetting & bugs"** | `babeldoc/main.py:179-182` |
| L2 | `--short-line-split-factor` default `0.8` | `babeldoc/main.py:184-189`; `format/pdf/translation_config.py:179` |
| L3 | Heuristic tách đoạn nằm ở `process_independent_paragraphs()` | `format/pdf/document_il/midend/paragraph_finder.py:841-925` |
| L4 | Điều kiện tách: `split_short_lines AND prev_width < median_width * factor` **OR** `is_bullet_point(chars[0])` của dòng hiện tại | `paragraph_finder.py:891-901` |
| L5 | `median_width` tính trên **TẤT CẢ dòng của cả trang**, gộp chung mọi paragraph (heading, caption, ô bảng, footnote, số trang) | `paragraph_finder.py:822-839`, gọi tại `:284` |
| L6 | `BULLET_POINT_PATTERN` chỉ khớp **glyph bullet**: `■•⚫⬤◆◇○●◦‣⁃▪▫∗†‡¹²³…·`. **KHÔNG có** `-` (hyphen-minus), `–`, `*`, và **KHÔNG có** hỗ trợ numbered list (`1.`, `a)`, `(1)`) | `format/pdf/document_il/utils/layout_helper.py:50-52` |
| L7 | `is_bullet_point()` chỉ xét **ký tự đầu tiên** của dòng (`chars[0]`) | `layout_helper.py:55-65`; call site `paragraph_finder.py:899-901` |
| L8 | babeldoc chỉ `.strip()` output LLM — newline **bên trong** chuỗi trả về KHÔNG bị loại bỏ | `format/pdf/document_il/midend/il_translator_llm_only.py:718, 987, 998` |

### N3. Root cause chi tiết — 3 cơ chế độc lập

#### RC-1 (chính) — `--split-short-lines` tách nhầm dòng ngắn giữa đoạn

`paragraph_finder.py:891-895`: với mỗi cặp dòng liền kề trong 1 paragraph, nếu **dòng
trước** (`prev_width`) hẹp hơn `median_width * 0.8` thì mọi dòng từ vị trí `j` trở đi bị
cắt ra thành paragraph mới.

Heuristic này giả định "dòng ngắn = dòng cuối đoạn". Giả định đó **sai** trong đúng loại
tài liệu của project (sách dạy làm bánh):

- Dòng ngay trước công thức/đơn vị đo, dòng kết câu trong cột căn đều.
- **Nghiêm trọng nhất (L5)**: `median_width` gộp mọi dòng của cả trang. Một trang vừa có
  body full-width vừa có bảng nguyên liệu / caption / cột hẹp → median bị kéo lệch → **mọi
  dòng của khối hẹp** đều `< 0.8 * median` → mỗi dòng thành 1 paragraph riêng → LLM dịch
  từng dòng rời rạc, mất ngữ cảnh câu → đúng triệu chứng "bóc tách xuống dòng chưa chính xác".

Đây cũng chính là rủi ro mà chính babeldoc cảnh báo trong help text (L1) — flag này được
bật hardcode mà không có nguồn xác thực nào trong Architecture.md chứng minh lợi ích của
nó lớn hơn tác hại.

#### RC-2 — bullet pattern không phủ `-` và numbered list

Nhánh `or` ở `paragraph_finder.py:896-901` chạy **độc lập với `split_short_lines`** (nó
nằm ngoài mệnh đề `and`). Nghĩa là: **babeldoc đã tự tách bullet item đúng cách mà KHÔNG
cần `--split-short-lines`** — flag kia không đóng góp gì cho việc nhận diện list.

Nhưng nhánh đó chỉ nhận diện được glyph bullet (L6) trên ký tự đầu dòng (L7). Hệ quả:

- `• Trộn bột` → `chars[0] = "•"` → khớp → tách đúng.
- `- Trộn bột` → `chars[0] = "-"` (U+002D) → **không khớp** → không tách.
- `1. Nướng ở 180°C` → `chars[0] = "1"` (ASCII digit) → **không khớp** → không tách.
  (Pattern có `¹²³` superscript, không có digit thường.)

→ Dash-bullet và numbered list **hoàn toàn phụ thuộc vào RC-1** để được tách. Mà RC-1 tách
theo hình học, không theo ngữ nghĩa → khi các item cùng dài (gần median) chúng bị **gộp**
thành một đoạn; khi một item xuống dòng thứ 2 ngắn thì bị **tách sai chỗ**. Đúng triệu
chứng thứ hai user báo: "Xuống dòng ở các chỗ bulleted/numbered".

Tác dụng phụ khác của L6: pattern chứa `¹²³` và `·` → **marker footnote** và **dấu chấm
giữa** bị hiểu nhầm là bullet → tách đoạn thừa.

#### RC-3 (phụ) — prompt yêu cầu giữ list ở cấp fragment

`src/core/prompt_builder.py:53-54, 111-112, 247-248` yêu cầu "Bullet list phải dịch thành
bullet list, numbered list phải dịch thành numbered list".

babeldoc gửi LLM **từng paragraph đã tách sẵn** (sản phẩm của RC-1/RC-2), không phải cả
khối list. Khi 1 item bị cắt thành fragment không còn ký tự bullet, chỉ thị này khiến LLM
có xu hướng **tự thêm lại** bullet/newline vào fragment. Vì babeldoc chỉ `.strip()` hai
đầu (L8), newline nội bộ do LLM sinh ra **sống sót** vào output.

⚠️ **CHƯA VERIFY**: chưa đo được tần suất LLM thực sự thêm newline, và chưa verify renderer
của babeldoc xử lý `\n` nội bộ ra sao (xuống dòng thật hay thành ô vuông tofu). Dev/QA cần
đo bằng live run trước khi coi RC-3 là nguyên nhân thật — hiện chỉ là giả thuyết có cơ sở
source (L8), không phải kết luận.

### N4. Vì sao lọt qua toàn bộ review/test

`tests/test_babeldoc_runner.py:201` chỉ assert `"--split-short-lines" in args` — tức là
test **xác nhận lại chính giả định đang sai**, không kiểm chứng flag đó có tạo layout đúng
hay không. Không có test nào trong toàn repo dựng PDF có bullet/numbered list rồi kiểm tra
cấu trúc đoạn của output (`grep -rn "bullet" tests/` chỉ hit `test_prompt_builder.py:62`,
mà file đó chỉ assert chuỗi "bullet" có mặt trong prompt).

Đây đúng dạng lỗ hổng Protocol 5 mô tả: mock/assert tự nhất quán với giả định, không nhất
quán với thực tế. Bổ sung đề xuất cho Protocol 5: **flag CLI bật hardcode cũng là một
"contract" cần nguồn xác thực** — hiện `--split-short-lines` được biện minh trong docstring
`babeldoc_runner.py:242-243` là "fix lỗi gộp dòng danh sách của pdf2zh" nhưng không có
nguồn xác thực nào, và theo L4 thì lý do đó **sai**: việc tách list do nhánh
`is_bullet_point` đảm nhiệm, độc lập hoàn toàn với flag này.

### N5. Phương án fix đề xuất

**F1 (bắt buộc, gốc rễ) — Bỏ `--split-short-lines` khỏi list hardcode.**
Sửa `src/services/babeldoc_runner.py:278`. Theo L4, nhánh `is_bullet_point` vẫn chạy khi
không có flag → glyph bullet vẫn được tách đúng, chỉ mất đi heuristic hình học đang gây
hại. Đây là fix triệt để cho RC-1, không phải patch tạm.

**F2 — Đưa flag thành tham số có kiểm soát, không hardcode.**
Thêm `split_short_lines: bool = False` vào signature `translate_pages()` và một field
tương ứng trong `Settings` (`src/core/config.py`), mặc định `False`. Lý do: một số tài liệu
scan qua cầu nối `searchable_pdf` có thể vẫn cần heuristic này; khoá cứng ở một trong hai
đầu đều sai. Nếu bật, đồng thời cho phép chỉnh `--short-line-split-factor` (mặc định
babeldoc `0.8` theo L2; hạ xuống ~`0.5` sẽ giảm mạnh false-positive vì chỉ còn dòng thật
sự ngắn mới bị tách).

**F3 — Bù cho RC-2 bằng tiền xử lý, KHÔNG fork babeldoc.**
babeldoc không có hook nào cho `BULLET_POINT_PATTERN`, và monkey-patch một
`frozenset`/`re.Pattern` module-level của tool bên thứ 3 chạy trong **subprocess riêng** là
bất khả thi (ta gọi qua CLI, không import). Hai hướng khả thi, theo thứ tự ưu tiên:

- **F3a**: chuẩn hoá ở bước tiền xử lý cho nhánh `pdf_scan` — trong
  `src/preprocess/searchable_pdf.py`, khi ghi lại text span OCR (`page.insert_text`,
  `:226`), map dash-bullet `-`/`–`/`*` đầu dòng sang `•` (U+2022, có trong L6) để nhánh
  `is_bullet_point` của babeldoc nhận ra. **Chỉ áp dụng được cho nhánh scan** — nhánh
  born-digital không đi qua file này.
- **F3b** (cho born-digital): chấp nhận giới hạn, ghi nhận là known limitation của babeldoc
  0.6.4, và mở issue upstream. **Không tự viết lại paragraph finder** — chi phí/rủi ro vượt
  xa lợi ích, và sẽ tạo đúng loại nợ mà Protocol 5 sinh ra để tránh.

⚠️ **ASSUMED — chưa verify**: F3a giả định việc đổi ký tự bullet trong lớp text vô hình
không làm lệch bbox hay hỏng layout render. Dev phải verify bằng 1 live run trước khi
implement đầy đủ (Protocol 5 R5-02 spike).

**F4 — Sửa prompt cho đúng cấp độ (giảm RC-3).**
`src/core/prompt_builder.py` (3 chỗ: `:53-54`, `:111-112`, `:247-248`). Riêng biến thể
babeldoc (`:247-248`) cần nói rõ: input là **một đoạn đơn lẻ**, phải dịch thành **đúng một
đoạn**, **không được thêm ký tự xuống dòng**, không tự thêm bullet nếu input không có. Giữ
nguyên chỉ thị list cho biến thể `_FILE_*` (dùng cho EPUB/bilingual_book_maker — nơi LLM
thực sự thấy cả khối list).

### N6. Yêu cầu test kèm fix (Protocol 5 + 6)

1. **Golden-file test, không mock tay** (R5-03 / Protocol 5 mục 3): tạo fixture PDF thật có
   3 khối — bullet `•`, bullet `-`, numbered `1./2./3.` — cạnh một bảng hẹp (để ép
   `median_width` lệch, tái hiện RC-1). Lưu tại `tests/fixtures/babeldoc/`.
2. **Assert cấu trúc, không assert flag**: thay assert kiểu
   `assert "--split-short-lines" in args` bằng test đọc output PDF bằng PyMuPDF và đếm số
   block/đoạn, so với số item mong đợi. Assert flag chỉ chứng minh ta gọi đúng cái ta định
   gọi, không chứng minh kết quả đúng.
3. **Live E2E (R6-03)**: chạy xuyên suốt 1 file thật, **mở PDF output và đọc nội dung**
   vùng list, xác nhận số item khớp bản gốc — không tin field `status`.
4. **Data lineage (R6-02)**: nếu implement F2, test phải assert giá trị
   `split_short_lines` từ `Settings` thực sự tới được `args` của subprocess, không chỉ
   `assert_awaited()`.

### N7. Việc KHÔNG phải nguyên nhân (đã loại trừ)

- `src/core/chunking.py` — chunking thuần **theo trang** (`ChunkPlan.page_start/page_end`),
  không hề đụng tới text. Không thể cắt giữa một list item. Loại trừ giả thuyết (d).
- `src/postprocess/chunk_merge.py`, `bilingual_merge.py` — ghép **ở cấp trang** bằng
  `fitz.insert_pdf()`, không đọc/ghi text. Không thể chèn xuống dòng. Loại trừ.
- `src/postprocess/font_shrink.py` — không nằm trong nhánh babeldoc (babeldoc tự vẽ lại
  text). Loại trừ giả thuyết (c).
- `250709c` — không đụng bất kỳ file nào trong `src/core/`, `src/postprocess/`,
  `src/preprocess/`. Chỉ `babeldoc_runner.py` (2 hàm mới), `config.py` (đổi default model),
  routes API + web UI. Loại trừ giả thuyết "commit gần nhất refactor làm hỏng regex".

### N8. Thứ tự implement đề xuất cho Dev

1. **F1** trước, một mình (một dòng), rồi live-run lại đúng file user báo lỗi → đo xem RC-1
   chiếm bao nhiêu phần triệu chứng. Đây là bước rẻ nhất và có khả năng giải quyết phần lớn.
2. Chỉ khi F1 chưa đủ mới làm **F4**, rồi đo lại.
3. **F2** làm cùng F1 (cùng file, cùng review).
4. **F3a** để sau cùng, và chỉ sau spike verify theo R5-02.

**Trạng thái**: Phân tích — chờ PM/user duyệt trước khi Dev implement.

---

## Đánh giá hướng Post-Processing cho lỗi gộp dòng Numbered List (2026-09-06)

**Tác giả**: Tech Lead — research/đánh giá, KHÔNG implement.
**Bối cảnh**: F1/F2/F4 đã ship, F3 (pre-processing injection ký tự bullet) đã THẤT BẠI qua
spike thật (xem CHANGELOG "F3 — Spike verify"). PM yêu cầu đánh giá hướng can thiệp SAU khi
babeldoc chạy, thay vì trước.

Toàn bộ claim dưới đây đọc trực tiếp từ **source thật babeldoc 0.6.4 đã cài** tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`
(`babeldoc/main.py:29` → `__version__ = "0.6.4"`), hoặc đo bằng script chạy thật trên
fixture có sẵn. Không có claim nào từ trí nhớ (Protocol 5 R5-01).

### P1. babeldoc trả về gì — nguồn xác thực

| # | Claim | Nguồn (file:line) |
|---|-------|-------------------|
| P1 | `BabeldocRunner.translate_pages()` trả `BabeldocResult` chỉ mang `mono_path`/`dual_path` (2 đường dẫn PDF) + stdout/stderr/duration/rate_limit_hits. **Không có bất kỳ cấu trúc text/layout nào** | `src/services/babeldoc_runner.py:191-199` (dataclass), `:374-388` (chỗ dựng return) |
| P2 | App gọi babeldoc qua **CLI trong subprocess riêng** (`asyncio.create_subprocess_exec`), không import in-process | `src/services/babeldoc_runner.py:325-331` |
| P3 | Console script `babeldoc` trỏ tới `babeldoc.main:cli` | `babeldoc-0.6.4.dist-info/entry_points.txt` |
| P4 | Nội bộ babeldoc CÓ 1 cấu trúc trung gian đầy đủ: IL (`il_version_1.Document` → `Page` → `PdfParagraph` → `PdfParagraphComposition` → `PdfLine` → `PdfCharacter`) | `format/pdf/document_il/il_version_1.py`; dùng xuyên suốt `high_level.py:836-1050` |
| P5 | Pipeline nội bộ (hàm `_do_translate_single`) chạy tuần tự **trong cùng 1 process**, các stage là lời gọi hardcode: `LayoutParser` → `ParagraphFinder` → `StylesAndFormulas` → `ILTranslatorLLMOnly` → `Typesetting` → `PDFCreater` | `high_level.py:953-1046`; `_do_translate_single` được gọi trực tiếp tại `:548,558,564,659` (không qua process pool) |
| P6 | `--debug` map thẳng vào `TranslationConfig.debug` | `main.py:53-56` (định nghĩa flag), `main.py:694` (`debug=args.debug`), `translation_config.py:171,233` |
| P7 | Khi `debug=True`, babeldoc **dump IL ra JSON tại 8 mốc**: `create_il.debug.json`, `detect_scanned_file.json`, `layout_generator.json`, `table_parser.json`, `paragraph_finder.json`, `styles_and_formulas.json`, `il_translated.json`, `add_debug_information.json`, `typsetting.json` | `high_level.py:916-919, 946-951, 957-961, 966-970, 973-977, 980-984, 1009-1013, 1015-1021, 1040-1044` |
| P8 | Các dump này ghi vào `working_dir` (mặc định `<CACHE_FOLDER>/working/<stem>`, đổi được bằng `--working-dir`) | `translation_config.py:428-429` (`get_working_file_path`), `:287-298`; `main.py:101` (flag), `:719` |
| P9 | **Dump là MỘT CHIỀU**: `XMLConverter` có `read_xml()`/`from_xml()` (`xml_converter.py:33,40`) nhưng **không có call site nào trong pipeline đọc IL ngược trở lại**. Không có flag kiểu `--resume-from-il`. `grep -rn "read_xml\|from_xml"` toàn source chỉ hit chính định nghĩa | `format/pdf/document_il/xml_converter.py:29-62`; `high_level.py` chỉ gọi `write_json` |

**Kết luận P1**: babeldoc CLI là hộp đen **PDF vào → PDF ra**. IL trung gian tồn tại và
**quan sát được** (`--debug`), nhưng **không tiêm ngược vào được** — nó là dump chẩn đoán,
không phải checkpoint có thể resume. Vì vậy câu hỏi 3 của PM ("hook vào cấu trúc trung gian
qua CLI") **không có đường đi trực tiếp**; muốn hook phải chạy babeldoc in-process (xem
Hướng B).

### P2. Phát hiện mới quan trọng — số liệu biện minh cho F1 đã bị đo sai

Trước khi bàn hướng đi mới, cần sửa lại một kết luận cũ. CHANGELOG F1 ghi:

> "F1 giảm mạnh over-fragmentation của đoạn văn thường (36→11 block — đúng triệu chứng RC-1
> 'xuống dòng chưa chính xác' mà user báo)"

**Số liệu này diễn giải SAI.** Đo lại trực tiếp trên chính 2 fixture đã capture
(`tests/fixtures/babeldoc/page14_split_short_lines_{true,false}_mono.pdf`, PyMuPDF
`get_text("blocks")`, chia vùng theo toạ độ y — danh sách ở `y < 505`, phần văn xuôi
"LỜI CẢM ƠN" ở `y >= 505`):

| Vùng | `--split-short-lines` BẬT (cũ) | TẮT (F1, hiện tại) |
|---|---|---|
| Văn xuôi (`y>=505`) — số block | 4 | 4 |
| Văn xuôi — text sau khi normalize whitespace | **giống hệt nhau, 1368 ký tự, `==` True** | như bên trái |
| Danh sách (`y<505`) — số block | 32 | 7 |
| Danh sách — số block bắt đầu bằng marker `N.` | 28 | 3 |
| Danh sách — các marker nhận ra được | 1,2,3,...,35 (31 marker) | chỉ 1, 2, 17, 27 |

Nghĩa là: **toàn bộ chênh lệch 36 vs 11 block nằm ở vùng danh sách, không phải ở văn xuôi.**
Trên trang này, `--split-short-lines` gây **0 (không) tổn hại** cho đoạn văn thường — văn bản
văn xuôi ra giống hệt từng ký tự ở cả 2 chế độ. 25 block "thêm" chính là 25 mục danh sách
được tách ĐÚNG.

Hệ quả với bản TẮT flag còn nặng hơn con số block gợi ý: các mục bị **dính liền không cả
dấu cách** trong cùng một chuỗi LLM trả về — ví dụ đọc được trong output thật:
`"...nhiều kích cỡ khác nhau3. Rây hoặc lưới lọc4. Máy trộn với tô 5 quart..."`. Đây là lỗi
nội dung nhìn thấy được, không chỉ lỗi thẩm mỹ layout.

⚠️ **Giới hạn của bằng chứng này**: chỉ đo trên **1 trang** (trang 14). RC-1 (heuristic
`median_width` toàn trang, `paragraph_finder.py:822-839,891-895`) vẫn là cơ chế **có thật đã
verify trong source** và vẫn có thể gây hại trên trang có bố cục khác (bảng hẹp cạnh body
full-width). Kết luận đúng là: **tác hại của RC-1 chưa từng được quan sát bằng dữ liệu thật
trên bất kỳ trang nào**, còn lợi ích của flag thì đã quan sát được rõ ràng. Trước đây ta đổi
một tác hại ĐÃ ĐO (gộp danh sách) lấy một tác hại mới CHỈ SUY LUẬN TỪ SOURCE.

### P3. Ba hướng khả thi

#### Hướng A — Hậu xử lý PDF output (câu hỏi 2 của PM)

Sửa `mono.pdf` sau khi babeldoc trả về: tìm block có nhiều marker `N.` dính liền, tách và vẽ
lại.

**Khả thi về mặt phát hiện**: marker vẫn còn trong text (`"...khác nhau3. Rây..."`), regex
tìm được. Project cũng đã có sẵn năng lực vẽ lại text lên PDF đã render
(`src/postprocess/font_shrink.py:311-345`, `_redraw_span()` dùng `page.insert_text()` với
`fontfile`).

**Nhưng không khả thi về mặt chất lượng**, vì việc cần làm không phải "merge dòng" như PM
mô tả ban đầu — mà là **tách một đoạn đã dính liền rồi TÁI TYPESET**: xoá text cũ, chèn
newline tại mỗi marker, tính lại ngắt dòng cho vừa bề rộng cột, tính lại chiều cao khối,
dịch chuyển mọi thứ bên dưới xuống, rồi vẽ lại toàn bộ bằng đúng font subset babeldoc đã
nhúng. Cụ thể:

- Đây là **viết lại module Typesetting của babeldoc** (`high_level.py:1039`) ở phía ngoài,
  không có thông tin layout (`Layout`, `layout_label`, bbox cột) mà babeldoc có sẵn trong IL
  — ta chỉ còn bbox của block sau khi đã render.
- `font_shrink.py:15-25` đã ghi rõ bài học: vẽ lại text bằng font SAI làm hỏng glyph tiếng
  Việt (`"thơm" -> "th·m"`); phải dùng **đúng file font đã nằm trên trang**. Font đó do
  babeldoc nhúng và subset, không phải file trong `fonts/` của project → phải extract font
  ra từ chính PDF output trước khi vẽ, thêm một lớp rủi ro nữa.
- Nội dung dài ra (thêm ngắt dòng) → khối cao lên → tràn sang phần dưới trang. Không có chỗ
  nào để "đẩy xuống" an toàn trong một PDF đã render.

**Đánh giá**: độ phức tạp **rất cao**; rủi ro hỏng nội dung/layout **cao** (đụng đúng 2 loại
lỗi đã có tiền sử trong project: glyph corruption và mất nội dung âm thầm); không phải fork
babeldoc nhưng **tệ hơn fork** ở chỗ phải tái hiện lại logic typeset mà không có dữ liệu
layout; effort **lớn**. → **Không khuyến nghị.**

#### Hướng B — Hook vào IL trước bước render, qua wrapper script (không fork)

babeldoc không có plugin/hook API (`ParagraphFinder(translation_config).process(docs)` là
lời gọi hardcode, `high_level.py:960`). Nhưng vì mọi stage chạy **trong cùng 1 process** (P5),
một **wrapper script** import babeldoc, thay thế hành vi tại runtime, rồi gọi
`babeldoc.main.cli()` là đủ — **không sửa 1 dòng source nào của babeldoc**, không phải fork,
và vẫn giữ nguyên mô hình subprocess hiện tại (`BabeldocRunner` chỉ đổi từ gọi `babeldoc`
sang gọi `<babeldoc-python> wrapper.py <args cũ>`).

Hai biến thể, **đã verify sống 2026-09-06** bằng cách chạy interpreter của chính tool
babeldoc (`/Users/hieutt/.local/share/uv/tools/babeldoc/bin/python`):

- **B-1 (nhỏ, thô)** — nới `BULLET_POINT_PATTERN`.
  Verify: `paragraph_finder.py:30` import `is_bullet_point` **theo tên** vào namespace riêng
  → patch `layout_helper.is_bullet_point` sẽ KHÔNG có tác dụng lên `paragraph_finder`.
  NHƯNG `is_bullet_point` đọc `BULLET_POINT_PATTERN` như **module global tại thời điểm gọi**
  (`layout_helper.py:65`) → patch chính cái pattern thì CÓ tác dụng. Đo thật:
  gán `lh.BULLET_POINT_PATTERN = re.compile(r"[■•⚫◆○●◦‣⁃▪▫0-9]")` rồi gọi
  `paragraph_finder.is_bullet_point(char("1"))` → trả `True` (trước khi patch: `False`);
  `char("a")` vẫn `False`.
  **Hạn chế cố hữu**: call site chỉ truyền `chars[0]` — MỘT ký tự
  (`paragraph_finder.py:899-902`). Không thể phân biệt `"1. Trộn bột"` với một dòng nối tiếp
  vô tình bắt đầu bằng `"180°C..."`. Thêm `0-9` = **mọi dòng bắt đầu bằng chữ số đều thành
  paragraph mới**. False-positive bị chặn ở mức "tách thừa 1 đoạn", cùng loại tác hại với
  RC-1 nhưng hẹp hơn nhiều (chỉ dòng bắt đầu bằng digit, thay vì mọi dòng ngắn).
  → Phức tạp: **thấp** (~20 dòng wrapper). Rủi ro: **thấp-trung bình**. Fork: **không**.
  Effort: **nhỏ**.

- **B-2 (đúng bài)** — bọc `ParagraphFinder.process`.
  Chạy `process()` gốc trước, rồi duyệt IL đã có (`document.page[*]` → paragraph →
  `pdf_paragraph_composition` → `pdf_line`) và tự tách paragraph tại các dòng mở đầu bằng
  marker. Ở tầng này ta thấy **toàn bộ text của dòng**, không chỉ `chars[0]` — nên áp được
  heuristic chống false-positive thật sự mà PM từng yêu cầu (marker tăng dần 1,2,3...; loại
  `"2 cups flour"`; loại dòng mục lục). Code tách có sẵn để tái dùng nguyên xi
  (`paragraph_finder.py:903-929`: dựng `PdfParagraph` mới, cắt composition, gọi
  `self.update_paragraph_data()` cho cả 2, `insert` vào list) — ta gọi lại chính các method
  đó qua `self`, không chép logic typeset.
  Quan trọng: can thiệp diễn ra **TRƯỚC** `ILTranslatorLLMOnly` (`high_level.py:1003`) và
  trước `Typesetting` (`:1039`) → babeldoc vẫn tự dịch và tự dàn trang bình thường, ta không
  đụng gì tới render. Đây chính là điều Hướng A không làm được.
  **Rủi ro thật sự**: phụ thuộc **internal API riêng của babeldoc 0.6.4** (tên method, shape
  `PdfParagraph`). Nâng version babeldoc = phải verify lại toàn bộ (Protocol 5 mục 5). Cần
  pin cứng version và có smoke test fail rõ ràng khi shape đổi.
  → Phức tạp: **trung bình** (~80-120 dòng wrapper + heuristic + test). Rủi ro: **trung
  bình** (không đụng render, không đụng nội dung; rủi ro chính là brittleness theo version).
  Fork: **không** (không sửa source babeldoc, không vendor code). Effort: **vừa**.

#### Hướng C — Chấp nhận known limitation, chỉnh lại default của F2

Không viết thêm code. Chỉ dựa vào `Settings.babeldoc_split_short_lines` (đã ship ở F2) và
chọn default cho đúng theo dữ liệu đo được.

Theo P2, trên trang duy nhất đã đo thật, `True` **tốt hơn nghiêm ngặt** so với `False`
(văn xuôi giống hệt nhau; danh sách đúng 28/32 block có marker thay vì 3/7 và không bị dính
chữ). Default hiện tại là `False`.

→ Phức tạp: **rất thấp** (1 dòng + đo thêm). Rủi ro: **thấp nhưng chưa đo đủ**. Effort:
**rất nhỏ**.

### P4. Khuyến nghị

**Bước 1 (làm ngay, rẻ nhất, chặn quyết định sai) — đo lại F1 trên nhiều trang.**
Chạy babeldoc thật ở cả 2 chế độ trên **3-5 trang có bố cục khác nhau** của chính cuốn "How
baking works" (bắt buộc có: 1 trang toàn văn xuôi, 1 trang có bảng nguyên liệu cạnh body
full-width — đúng kịch bản RC-1 dự đoán, 1 trang có công thức đánh số). Với mỗi trang, so
sánh theo **vùng** như bảng P2 (văn xuôi vs danh sách riêng), **không** so tổng số block —
tổng số block là proxy sai, chính nó đã dẫn tới kết luận nhầm ở F1. Đây là điều kiện tiên
quyết: nếu RC-1 không gây hại thật trên trang nào, thì Bước 2 giải quyết xong vấn đề mà
không cần viết code.

**Bước 2 (nhiều khả năng là đủ) — nếu Bước 1 xác nhận, đổi default
`Settings.babeldoc_split_short_lines` về `True`** (`src/core/config.py`), giữ nguyên
`babeldoc_short_line_split_factor` ở `0.5` (thấp hơn default `0.8` của babeldoc — chỉ dòng
thật sự ngắn mới bị tách, giảm mạnh false-positive của RC-1, xem L2/N5-F2). Nếu Bước 1 tìm
ra trang bị RC-1 làm hỏng thật, **không** đổi default; đi tiếp Bước 3.

**Bước 3 (chỉ khi Bước 2 không đủ) — làm Hướng B-2.** Khi đó bật lại
`--split-short-lines` **không còn cần thiết**: B-2 tách numbered list theo ngữ nghĩa, nên có
thể để `split_short_lines=False` (tránh hẳn RC-1) mà vẫn giữ danh sách đúng. Đây là phương
án duy nhất giải quyết triệt để cả RC-1 lẫn RC-2 cùng lúc.

**Không khuyến nghị Hướng A** trong mọi trường hợp: sửa PDF đã render đòi hỏi tái hiện lại
Typesetting của babeldoc mà không có dữ liệu layout, và đụng đúng 2 lớp rủi ro đã có tiền sử
gây sự cố trong project (glyph tiếng Việt hỏng khi vẽ lại bằng font sai; mất nội dung âm
thầm). Chi phí/rủi ro vượt xa lợi ích so với B-2.

### P5. Điều kiện kèm theo nếu chọn Hướng B (bắt buộc, Protocol 5/6)

1. **Pin version**: wrapper phải assert `babeldoc.__version__ == "0.6.4"` và **raise ngay**
   nếu lệch — không "chạy tiếp cho lành". Đổi version babeldoc = verify lại toàn bộ contract
   internal (Protocol 5 mục 5).
2. **Smoke test gọi thật** (R5-03): 1 test chạy wrapper thật trên fixture
   `page14_numbered_list_source.pdf`, assert số block có marker trong output ≥ 25.
3. **Assert nội dung, không assert flag** (bài học N4): không được viết test kiểu
   `assert "--wrapper" in args`. Phải đọc PDF output bằng PyMuPDF và đếm marker.
4. **Kiểm tra không dính chữ**: assert output KHÔNG chứa pattern `\S\d{1,2}\.\s` (chữ dính
   liền marker, dấu hiệu của lỗi gộp hiện tại).
5. Với B-2, cần assert cả **văn xuôi không bị đổi**: so text vùng văn xuôi trước/sau khi bật
   wrapper phải bằng nhau (đúng phương pháp đã dùng ở P2).

**Trạng thái**: Đánh giá — chờ PM/user quyết định. Không có code nào được viết trong task này.

---

## Đo lại F1 trên nhiều trang — kết quả live A/B/C (2026-09-06)

**Tác giả**: Tech Lead — đo lường, KHÔNG implement, KHÔNG sửa default. PM quyết định cuối cùng.
**Bối cảnh**: thực hiện đúng "Bước 1" của section trước (P4). Mục tiêu: xác định tác hại RC-1
có THẬT trên dữ liệu thật hay không, trước khi giữ/đổi `Settings.babeldoc_split_short_lines`.

### Q1. Phương pháp (live, không mock — Protocol 5 R5-03 / Protocol 6 R6-03)

- **Engine**: `babeldoc` 0.6.4 CLI thật, gọi qua chính production code path của app
  (`BabeldocRunner.translate_pages()` + `Pdf2zhServiceMapper().map("deepseek", settings)`),
  không tự dựng lại lệnh CLI bằng tay.
- **LLM**: DeepSeek API thật, model `deepseek-v4-flash` — lấy đúng giá trị đang chạy production
  trong bảng `settings` của `data/bb_translation.db` (KHÔNG phải `deepseek-chat` mặc định trong
  `.env`; `get_settings()` chỉ đọc `.env` nên harness override tường minh).
- **Prompt**: prompt babeldoc thật do `build_babeldoc_prompt_text()` sinh (đã bao gồm bản sửa
  F4), dùng chung 1 file cho toàn bộ 21 lần chạy để loại prompt khỏi biến số.
- **File nguồn**: `data/uploads/898a567a-..._Figoni, Paula - How baking works...-1-25.pdf`.
- **3 nhánh (arm)** cho MỖI trang:
  - `false` — `split_short_lines=False` (F1, default đang ship).
  - `true` — `split_short_lines=True`, `factor=0.5` (F2, giá trị
    `Settings.babeldoc_short_line_split_factor` đang ship).
  - `true08` — `split_short_lines=True`, `factor=0.8` (**default của chính babeldoc**,
    `main.py:184-189` / `translation_config.py:179` — chính là hành vi TRƯỚC F1).
- **Tổng**: 7 trang × 3 nhánh = **21 lần chạy babeldoc + DeepSeek thật**, 0 rate-limit hit,
  0 lần fail.
- **Artifact đã lưu lại** (golden file, không phải mock viết tay):
  `tests/fixtures/babeldoc/ab_split_short_lines/page{N}_{arm}_mono.pdf` (21 PDF) +
  `run_measure.py` (harness đã chạy) + `analyze.py` (script đo). Tái chạy được nguyên trạng.

⚠️ Nhánh `true08` **không có trong đề bài PM giao** (PM chỉ yêu cầu A/B True-vs-False). Bổ sung
vì phát hiện giữa chừng: fixture cũ của F1 dùng factor **0.8**, còn `Settings` sau F2 mặc định
**0.5** — nên "bật lại flag" theo cấu hình hiện tại KHÔNG tái hiện hành vi trước F1. Nếu chỉ đo
A/B như đề bài, kết luận sẽ sai lệch (xem Q3).

### Q2. Chọn trang — 7 trang, 5 loại bố cục

Chọn bằng cách quét thống kê toàn bộ 25 trang (số block, số marker `N.`, số bullet glyph,
median width, số block hẹp < 0.6 × median) rồi lấy đại diện mỗi loại:

| Trang | Loại bố cục | Lý do chọn |
|---|---|---|
| 13 | **Văn xuôi thuần**, 1 cột full-width, không list/bảng | Yêu cầu (a) của PM. Baseline sạch nhất |
| 21 | Có **bảng** (TABLE 1.2) + văn xuôi | Yêu cầu (c) |
| 20 | Văn xuôi + **bảng hẹp + caption** ở cột trái (8 block hẹp — cao nhất tài liệu, median_width bị lệch mạnh nhất) | Yêu cầu (c), đúng kịch bản RC-1 mô tả |
| 22 | **Mix nhiều loại**: văn xuôi 2 cột + bảng + caption ảnh + heading giãn chữ | Yêu cầu (d) |
| 8 | **Mục lục** (72 block nguồn, toàn dòng ngắn) | Yêu cầu (d) |
| 17 | **Mix**: numbered list ngắn (5 mục "CHAPTER OBJECTIVES") + văn xuôi | Yêu cầu (b) + (d) |
| 14 | **Numbered list dài** (35 mục) trong 2 cột hẹp | Yêu cầu (b), trang user báo lỗi |

### Q3. Số liệu thô

Chỉ số dùng (đo bằng PyMuPDF `get_text("blocks")` trên PDF output thật):

- `blk` — số text block; `chars` — tổng ký tự (kiểm tra mất nội dung).
- `glue:N+UP` — số lần **một chữ số dính liền ngay một chữ HOA** trong CÙNG 1 block
  (vd `"CHƯƠNG 6CÁC LOẠI NGŨ CỐC"`). Lỗi nội dung nhìn thấy được.
- `glue:x+N.` — số lần **một chữ cái dính liền ngay marker `N.`** (vd `"khác nhau3. Rây"`).
  Đây chính là triệu chứng gộp danh sách user báo.
- `mkBlk` — số block **bắt đầu bằng** marker `N.` (mục còn đứng đúng dòng riêng).

Cả 2 chỉ số `glue` đếm **trong từng block**, không nối các block lại — nối block sẽ tự tạo ra
đúng cái ranh giới mà chỉ số này dùng để kiểm tra sự VẮNG MẶT (lỗi của lần đo đầu tiên).

| Trang | arm | blk | chars | glue:N+UP | glue:x+N. | mkBlk |
|---|---|---:|---:|---:|---:|---:|
| **13** (văn xuôi thuần) | false | 10 | 4243 | 0 | 0 | 0 |
| | true (0.5) | 10 | 4243 | 0 | 0 | 0 |
| | true08 | 10 | 4243 | 0 | 0 | 0 |
| **21** (bảng) | false | 30 | 2402 | 0 | 0 | 0 |
| | true (0.5) | 30 | 2402 | 0 | 0 | 0 |
| | true08 | 30 | 2402 | 0 | 0 | 0 |
| **20** (bảng hẹp + caption) | false | 19 | 3320 | 0 | 0 | 0 |
| | true (0.5) | 22 | 3310 | 0 | 0 | 0 |
| | true08 | 22 | 3310 | 0 | 0 | 0 |
| **22** (mix) | false | 31 | 3264 | 0 | 0 | 0 |
| | true (0.5) | 32 | 3280 | 0 | 0 | 0 |
| | true08 | 35 | 3255 | 0 | 0 | 0 |
| **8** (mục lục) | false | 15 | 1952 | **7** | 0 | 0 |
| | true (0.5) | 17 | 1937 | **7** | 0 | 0 |
| | true08 | 34 | 1930 | **0** | 0 | 0 |
| **17** (list ngắn + văn xuôi) | false | 8 | 2044 | 0 | 0 | 1/5 |
| | true (0.5) | 9 | 2096 | 0 | 0 | 2/5 |
| | true08 | 11 | 2077 | 0 | 0 | **4/5** |
| **14** (list 35 mục) | false | 11 | 2764 | 0 | **28** | 3/35 |
| | true (0.5) | 20 | 2804 | 0 | **21** | 12/35 |
| | true08 | 34 | 2801 | 0 | **3** | **26/35** |

**Kiểm tra mất nội dung**: `chars` của mọi arm nằm trong ±1.5% so với nhau và so với trang
nguồn. **Không arm nào làm mất nội dung** — khác hẳn lớp lỗi Bug #2/#5 trước đây.

**Kiểm tra "output có giống hệt nhau không"** (so text toàn bộ block sau khi normalize
whitespace):

| Trang | `false` == `true(0.5)` | `false` == `true08` |
|---|---|---|
| 13 | **True** | **True** |
| 21 | **True** | **True** |
| 20 | False | False |
| 22 | False | False |
| 8 | False | False |
| 17 | False | False |
| 14 | False | False |

### Q4. Phân tích từng trang (đọc nội dung thật, không chỉ đếm block)

**Trang 13 — văn xuôi thuần: KHÔNG KHÁC BIỆT.**
(a) văn xuôi: không arm nào tách vụn. (b) không có list/bảng. (c) **Kết luận: không khác biệt** —
output giống hệt nhau từng ký tự ở cả 3 arm. **RC-1 không hề kích hoạt trên trang văn xuôi thuần.**

**Trang 21 — có bảng: KHÔNG KHÁC BIỆT.**
(a) văn xuôi nguyên vẹn ở cả 3 arm. (b) bảng không dính chữ ở arm nào. (c) **Kết luận: không
khác biệt** — giống hệt nhau từng ký tự. Đáng chú ý vì đây là trang có bảng mà RC-1 lẽ ra phải
gây hại.

**Trang 20 — bảng hẹp + caption (kịch bản RC-1 nặng nhất): `false` tốt hơn chút ít.**
(a) văn xuôi: **giống hệt nhau ở cả 3 arm** (5 đoạn body, từng chữ như nhau). (b) khác biệt DUY
NHẤT: caption bảng. `false` giữ nguyên 1 khối
`"BẢNG 1.1 ■ SỰ TƯƠNG ĐƯƠNG GIỮA ĐƠN VỊ THÔNG DỤNG CỦA MỸ (IMPERIAL) VÀ ĐƠN VỊ MÉT"`;
`true`/`true08` cắt thành 4 fragment (`"BẢNG 1.1 ■"` / `"SỰ TƯƠNG ĐƯƠNG GIỮA"` /
`"ĐƠN VỊ THÔNG DỤNG CỦA MỸ (IMPERIAL)"` / `"VÀ ĐƠN VỊ HỆ MÉT"`). Ghép lại vẫn đọc đúng nghĩa,
không dính chữ, không mất nội dung. (c) **Kết luận: `false` tốt hơn, mức độ nhẹ** — đây là bằng
chứng THẬT ĐẦU TIÊN của RC-1, nhưng tác hại giới hạn ở 1 caption và không làm sai nội dung.
`0.5` và `0.8` cho kết quả y hệt nhau ở trang này.

**Trang 22 — mix: KẾT QUẢ TRÁI CHIỀU (cả 2 arm đều có lỗi riêng).**
(a) văn xuôi: không arm nào tách vụn. (b) **`true08` gây hại**: cắt vụn 2 caption, và một trong
số đó mất mạch nghĩa thật sự — caption gốc `"TABLE 1.3 ■ VOLUME CONVERSIONS FOR COMMON U.S.
UNITS"` ra thành 3 fragment dịch rời rạc, lặp ý:
`"BẢNG 1.3 ■ QUY ĐỔI THỂ TÍCH"` / `"CHO CÁC ĐƠN VỊ"` / `"CÁC ĐƠN VỊ THÔNG DỤNG"`. Đây là **tác
hại RC-1 rõ ràng nhất tìm được trong toàn bộ mẫu**. NHƯNG (b') **`false` cũng gây hại riêng**:
heading giãn chữ ra thành `"MẸ O H A Y"` (hỏng, `true08` ra đúng `"MẸO HỮU ÍCH"`), và credit ảnh
bị dính vào caption: `"...siro cây phong, nước và bột mì.Ảnh: Aaron Seyfarth"` (`true08` tách
đúng thành 2). (c) **Kết luận: trái chiều, không arm nào thắng** — mỗi arm hỏng một chỗ khác nhau.

**Trang 8 — mục lục: `true08` tốt hơn RÕ RỆT.**
(a) không có văn xuôi. (b) `false` VÀ `true(0.5)` đều dính chữ **7 lần**, kiểu
`"CHƯƠNG 6CÁC LOẠI NGŨ CỐC"`, `"CHƯƠNG 7GLUTEN 117"`, `"CHƯƠNG 10CHẤT BÉO"` — số chương dính
liền tên chương, lỗi nội dung nhìn thấy ngay. Các mục con cũng bị gộp thành chuỗi dài
(`"Giới thiệu 101 Ngũ cốc 102 Các loại ngũ cốc và bột không chứa gluten 106..."`). `true08`:
**0 lần dính**, mỗi mục mục lục một block (`"Giới thiệu 101"`, `"Ngũ cốc có gluten 102"`), và
`"CHƯƠNG 6"` xuống dòng đúng trước tên chương. (c) **Kết luận: `true08` tốt hơn rõ rệt**; `0.5`
gần như không cải thiện gì so với `false`.

**Trang 17 — numbered list ngắn + văn xuôi: `true08` tốt hơn.**
(a) văn xuôi: cả 3 arm đều giữ nguyên 3 đoạn body, không tách vụn. (b) `false` gộp cả 5 mục
"CHAPTER OBJECTIVES" vào 1 block dính chữ
(`"...cách đạt được điều đó.2. Phân biệt giữa..."`), chỉ 1/5 mục đứng riêng. `true08` tách được
**4/5**, các mục 3/4/5 mỗi mục 1 block sạch. `true(0.5)` chỉ được 2/5. (c) **Kết luận: `true08`
tốt hơn**, không kèm tác hại nào quan sát được trên trang này.

**Trang 14 — numbered list 35 mục: `true08` tốt hơn RẤT RÕ.**
(a) văn xuôi ("LỜI CẢM ƠN", 3 đoạn): **giống hệt nhau ở cả 3 arm** — xác nhận lại kết luận P2 của
section trước bằng một lần chạy độc lập, prompt mới. (b) dính chữ: `false` **28 lần**,
`true(0.5)` **21 lần**, `true08` chỉ **3 lần**. Số mục đứng đúng dòng riêng: 3/35 → 12/35 →
**26/35**. `false` dồn 33 mục vào đúng 2 khối khổng lồ. (c) **Kết luận: `true08` tốt hơn rất rõ.**

### Q5. Tổng hợp

| Trang | Loại | Kết luận |
|---|---|---|
| 13 | văn xuôi thuần | không khác biệt (identical) |
| 21 | bảng | không khác biệt (identical) |
| 20 | bảng hẹp + caption | `false` tốt hơn (nhẹ — 1 caption bị cắt 4) |
| 22 | mix | trái chiều (mỗi arm hỏng 1 chỗ khác nhau) |
| 8 | mục lục | **`true08` tốt hơn rõ rệt** (7 lỗi dính chữ → 0) |
| 17 | list ngắn + văn xuôi | **`true08` tốt hơn** (1/5 → 4/5 mục đúng) |
| 14 | list 35 mục | **`true08` tốt hơn rất rõ** (28 → 3 dính chữ; 3/35 → 26/35) |

**Tổng kết: `true08` thắng rõ 3 trang, trái chiều 1 trang, thua nhẹ 1 trang, hoà 2 trang.**

Ba kết luận quan trọng:

1. **RC-1 CÓ THẬT nhưng hẹp hơn nhiều so với dự đoán từ source.** Phân tích N3/RC-1 dự đoán
   `median_width` toàn trang sẽ làm "mọi dòng của khối hẹp" bị tách, gây hại cho **đoạn văn
   thường**. Đo thật: **không có một đoạn văn xuôi nào trong toàn bộ 7 trang bị tách vụn ở bất kỳ
   arm nào.** Tác hại thật của RC-1 chỉ xuất hiện ở **caption của bảng/ảnh** (trang 20, 22) —
   một loại nội dung ngắn, ít quan trọng hơn nhiều so với body text và list.

2. **`factor` quan trọng hơn cả bản thân flag.** Đây là phát hiện làm thay đổi kết luận:
   `true(0.5)` — chính là cấu hình `Settings` đang ship sau F2 — là **tệ nhất trong ba**: nó giữ
   gần như trọn vẹn lỗi gộp danh sách của `false` (trang 8: vẫn 7 lỗi dính chữ, y hệt `false`;
   trang 14: 21/28 lỗi còn lại) mà **vẫn phải trả đủ giá RC-1** (trang 20 cắt caption y hệt
   `true08`). Nghĩa là nếu PM bật `babeldoc_split_short_lines=True` với default `factor` hiện tại,
   sẽ nhận về **gần như toàn bộ tác hại và rất ít lợi ích**. Hạ factor từ 0.8 xuống 0.5 ở F2 được
   suy luận là "giảm false-positive" nhưng chưa từng đo — đo thật cho thấy nó chủ yếu giảm
   TRUE-positive.

3. **Kết quả KHÔNG mâu thuẫn theo loại trang** theo cách cần setting per-document. Trang văn xuôi
   thuần và trang bảng **hoàn toàn không bị ảnh hưởng** (identical) — tức là bật flag không có
   rủi ro gì với chúng. Chỉ trang có caption ngắn mới chịu thiệt. Vì vậy **không cần** heuristic
   "phát hiện tài liệu nhiều list" hay setting per-file-type: một default duy nhất là đủ, vì chi
   phí của việc bật flag bằng 0 trên đúng những trang mà nó không giúp gì.

### Q6. Khuyến nghị

**Khuyến nghị chính: đổi CẢ HAI default trong `src/core/config.py`:**

- `babeldoc_split_short_lines: bool = False` → **`True`**
- `babeldoc_short_line_split_factor: float = 0.5` → **`0.8`** (bằng đúng default của babeldoc)

Tức là **hoàn nguyên hành vi runtime về trước F1**, nhưng **GIỮ NGUYÊN toàn bộ phần plumbing của
F1/F2** (tham số hoá, `Settings`, data-lineage test) — đó mới là giá trị thật của F1/F2: biến một
flag hardcode không nguồn xác thực thành một tham số đo được, đổi được. Không đề xuất revert code.

Lý do, theo đúng thứ tự sức nặng bằng chứng:

1. Lợi ích **đã đo được** trên 3/7 trang, gồm cả trang user trực tiếp báo lỗi (trang 14), và gồm
   loại lỗi **nhìn thấy được trong bản dịch giao cho user** (dính chữ `"CHƯƠNG 6CÁC LOẠI"`,
   `"khác nhau3. Rây"`).
2. Tác hại **đã đo được** giới hạn ở caption bảng/ảnh trên 2/7 trang, và trên 1 trong 2 trang đó
   (trang 22) arm `false` cũng có lỗi riêng tương đương — nên tác hại ròng thực tế chỉ là **1
   caption trên 7 trang**.
3. Trang văn xuôi thuần và trang bảng: **bật flag không gây bất kỳ thay đổi nào** — rủi ro bằng 0
   trên phần lớn nội dung của một cuốn sách.
4. Giữ `factor=0.5` là lựa chọn tệ nhất trong cả ba (điểm 2 mục Q5) — nếu PM chọn giữ
   `split_short_lines=False`, cũng nên sửa `0.5` về `0.8`, vì giá trị 0.5 hiện tại chỉ có hại khi
   ai đó bật flag lên qua `.env`.

**Không khuyến nghị**: setting per-`file_type` hoặc heuristic tự phát hiện "tài liệu nhiều list".
Dữ liệu không ủng hộ (điểm 3 mục Q5): chi phí bật flag trên trang không có list bằng 0, nên phân
nhánh chỉ thêm phức tạp mà không mua được gì.

**Việc kèm theo nếu PM duyệt** (Dev thực hiện, Protocol 5/6):

1. Sửa 2 default nói trên trong `src/core/config.py`. Cập nhật docstring
   `BabeldocRunner.translate_pages()` — hiện đang viết `--split-short-lines` là "tác hại hình học
   lan rộng hơn toàn bộ trang", câu này **đã bị dữ liệu ở đây bác bỏ** và cần sửa lại theo phạm vi
   thật (chỉ caption).
2. Cập nhật 2 test đang khoá default cũ trong `tests/integration/test_job_orchestrator.py`
   (`test_babeldoc_split_short_lines_defaults_to_disabled`) — đổi tên và đảo assert theo default
   mới. Giữ nguyên test data-lineage (R6-02).
3. Thêm golden-file test đọc **cấu trúc** từ fixture đã lưu
   (`tests/fixtures/babeldoc/ab_split_short_lines/`), tối thiểu 3 assert:
   `page8_true08` có `glue:N+UP == 0` (arm `false` là 7); `page14_true08` có ≥ 24 block bắt đầu
   bằng marker (arm `false` là 3); `page13` giống hệt nhau ở cả 3 arm. **Không** assert sự có mặt
   của flag trong `args` — đó đúng là lỗi N4 đã mắc một lần.
4. Ghi **known limitation** vào CHANGELOG: caption bảng/ảnh có thể bị cắt thành nhiều fragment
   (trang 20, 22). Đây là giá đã biết và đã chấp nhận có ý thức, không phải bug chưa phát hiện.

**Hướng B-2 (section trước) vẫn là fix triệt để duy nhất** và bây giờ có thêm lý do: nó tách
numbered list theo **ngữ nghĩa**, nên cho phép đặt `split_short_lines=False` mà vẫn giữ list
đúng — tức là loại bỏ hoàn toàn cái giá "caption bị cắt" mà khuyến nghị trên đang phải trả. Nhưng
khuyến nghị trên rẻ hơn nhiều (2 dòng config) và đã đủ để xử lý triệu chứng user báo, nên nên làm
trước; B-2 chỉ cần khi caption bị cắt trở thành phàn nàn thật từ user.

**Trạng thái**: Đo lường xong — chờ PM/user quyết định. Không sửa code, không đổi default.

---

## US-16 — Nén ảnh sau khi ghép (`compress_pdf_images`) — thiết kế (2026-09-06)

Thiết kế cho US-16 / BR-IMGCOMP-01..04 (`docs/PRD.md` §3, §4.9). Trạng thái: **đã spike đo
thật trên dữ liệu production, không có phần nào `[UNVERIFIED]`** — mọi contract PyMuPDF dưới
đây đều đã chạy thật trong `.venv` của project và có output kèm theo.

### S1. Nguồn xác thực (Protocol 5 R5-01 — áp dụng tự nguyện)

PyMuPDF là thư viện Python import trực tiếp (không phải subprocess/HTTP service) nên **không
thuộc phạm vi bắt buộc** của Protocol 5 (xem "Phạm vi áp dụng" trong `CLAUDE.md` project).
Tuy nhiên toàn bộ contract dưới đây vẫn được verify bằng cách chạy thật, không viết từ trí nhớ.

**Version đã cài** (lệnh: `.venv/bin/python -c "import fitz; print(fitz.VersionBind, fitz.version)"`):

```
PyMuPDF 1.28.2: Python bindings for the MuPDF 1.28.2 library.
Python 3.14 running on darwin (64-bit).
VersionBind 1.28.2
version ('1.28.2', '1.28.2', None)
```

⚠️ **Deprecation warning đã quan sát thấy**: `import fitz` in ra
`"The fitz API is deprecated and will be removed in future. Use import pymupdf instead."`
`src/postprocess/chunk_merge.py:54` hiện đang dùng `import fitz`. **Không đổi trong scope
US-16** (ngoài phạm vi, sẽ gây diff nhiễu); hàm mới bám theo import sẵn có của file.

**Signature đã verify bằng `inspect.signature`** (không có cái nào là suy đoán):

| API | Signature thật (1.28.2) | Ghi chú |
|---|---|---|
| `Document.get_page_images` | `(self, pno: int, full: bool = False) -> list` | `full=True` mới có trường filter |
| `Document.xref_get_key` | `(self, xref, key)` | trả tuple `(type, value)`, ví dụ `('null','null')` / `('name','/DCTDecode')` |
| `Document.xref_stream_raw` | `(self, xref)` | bytes stream **chưa** giải nén — dùng để đo size thật |
| `Document.update_stream` | `(self, xref=0, stream=None, new=1, compress=1)` | **phải truyền `compress=0`** khi ghi JPEG |
| `Document.xref_set_key` | `(self, xref, key, value)` | sửa `/Filter`, `/ColorSpace`... |
| `Pixmap.tobytes` | `(self, output='png', jpg_quality=95)` | **`jpg_quality` là tên tham số đúng**, không phải `quality` |
| `Page.replace_image` | `(page, xref, *, filename=None, pixmap=None, stream=None)` | tồn tại, nhưng **KHÔNG dùng** — xem S4 |
| `Document.extract_image` | `(self, xref)` | tồn tại, **KHÔNG dùng** — xem S4 |

**Tuple của `get_page_images(pno, full=True)`** — đã verify thứ tự thật trên dữ liệu production:

```
(12, 0, 859, 1582, 8, 'ICCBased', '', 'Im1', '', 0)
 ^   ^   ^    ^     ^   ^          ^    ^     ^   ^
 |   |   w    h    bpc  colorspace alt  name  |   referencer
 |   smask xref (0 = khong co)                filter (chuoi rong = raw)
 xref
```

⚠️ **Cạm bẫy đã thực sự mắc phải trong lúc spike**: index `1` là `smask`, index `8` là
`filter` — dễ nhầm lẫn nhau. Lần đo đầu tiên của spike này dùng nhầm `info[8]` làm smask và
báo "0 ảnh có smask" từ một trường hoàn toàn khác. Đã đo lại bằng index đúng (`info[1]`) và
kết quả tình cờ vẫn là 0, nhưng **Dev không được tin vào sự trùng hợp đó** — dùng đúng index.

**Đã verify `info[8]` và `xref_get_key(xref,"Filter")` cho kết quả nhất quán 100%** trên cả
538 image xref của file thật (`agree: 538, disagree: 0`). Dev dùng cách nào cũng được;
thiết kế dưới đây dùng `xref_get_key` cho khớp cách diễn đạt của BR-IMGCOMP-02 (`Filter: null`).

### S2. Vấn đề đo được trên dữ liệu thật

Đo trên chính file đã sinh ra US-16 — `data/outputs/3594a7a3-8b72-4390-9d9b-159769a2a215/translated_vi.pdf`
(job thật 415 trang, engine `babeldoc`, `status=completed`):

| Chỉ số | Giá trị đo |
|---|---|
| Kích thước file | **846.79 MB** |
| Số trang | 415 |
| Unique image xref | 538 |
| `Filter: null` (raw) | **357 xref — 690.96 MB** stream bytes |
| `DCTDecode` (JPEG sẵn) | 156 xref — 1.60 MB |
| `CCITTFaxDecode` | 25 xref — 0.04 MB |
| Phần còn lại (font, content stream, metadata) | ~155.82 MB |

=> **81.6% dung lượng file** nằm ở 357 ảnh raw không nén. Đúng như PRD mô tả.

Đặc điểm của 357 ảnh raw (đã đo, quan trọng cho S4): **tất cả** đều `ColorSpace: ICCBased`,
`BitsPerComponent: 8`, **0 ảnh có `/SMask`**, **0 ảnh là `/ImageMask`**. Tức là trên dữ liệu
thật hiện có, các edge case nguy hiểm nhất **không xuất hiện** — nhưng thiết kế vẫn phải guard
chúng (S4/S6), vì file khác có thể có.

### S3. Kết quả spike dedupe — **KHÔNG đạt ngưỡng, LOẠI khỏi scope** (BR-IMGCOMP-04)

Phương pháp: SHA-256 trên nội dung stream thật của từng xref, gom nhóm theo hash, tính phần
dung lượng thừa (`size × (số bản sao − 1)`). Đo trên chính file production 846.79 MB ở trên —
**không phải fixture, không phải ước lượng**.

**Đo 1 — dedupe trong nhóm ảnh raw (nhóm mà US-16 thực sự nén):**

```
raw-content dup groups: 0    redundant xrefs: 0    wasted bytes: 0.0 MB / 690.96 MB
```

**0 nhóm trùng.** Đáng chú ý: có những cặp xref *trông như* trùng (ví dụ xref 12 và 58: cùng
`859×1582`, cùng đúng 5,435,752 bytes) nhưng hash khác nhau (`64fddbc4…` vs `80593ef4…`) —
tức là babeldoc render lại ảnh cho từng trang, gần giống nhau về thị giác nhưng **không
byte-identical**. Đây chính là lý do không được suy đoán: nhìn bảng size/dims sẽ kết luận
ngược hoàn toàn với kết quả hash.

**Đo 2 — dedupe trên TOÀN BỘ 538 ảnh (kể cả DCTDecode/CCITT, rộng hơn cách diễn đạt của BR):**

```
ALL images: 538   unique: 460   dup groups: 19   redundant xrefs: 78
total img bytes 692.60 MB, exact-dup waste 0.349 MB (0.05%)
```

Có trùng lặp thật (78 xref thừa), nhưng **chỉ nằm ở nhóm ảnh vốn đã nhỏ** (icon/logo lặp lại
qua các chương), tổng cộng 0.349 MB.

**So với ngưỡng 20% của BR-IMGCOMP-04** — "giảm THÊM ≥20% so với chỉ nén JPEG", nên mẫu số
phải là dung lượng ảnh **sau khi** đã nén JPEG (6.64 MB raw-đã-nén + 1.64 MB DCT/CCITT giữ
nguyên = 8.28 MB):

| Phép so | Kết quả |
|---|---|
| Dedupe / tổng ảnh gốc | 0.349 / 692.60 = **0.05%** |
| Dedupe / ảnh sau nén JPEG (mẫu số đúng theo BR) | 0.349 / 8.28 = **4.2%** |
| Ngưỡng yêu cầu | ≥ 20% |
| Trên tổng file sau nén (19.34 MB) | 0.349 / 19.34 = **1.8%** |

=> **4.2% < 20% → KHÔNG đạt ngưỡng.**

**QUYẾT ĐỊNH: dedupe KHÔNG vào scope implement lần này.** Defer về backlog kèm số liệu trên.
Dev **không** implement dedupe. Acceptance criterion điều kiện cuối cùng của US-16 ("Nếu spike
dedupe đạt ngưỡng ≥ 20%…") **không kích hoạt**.

Giới hạn của kết luận (nêu rõ, không giấu): đo trên **1 job thật duy nhất** (415 trang, sách
`How Baking Works`). Đây là job lớn nhất và chính là case đã gây ra US-16, nên đại diện tốt
cho vấn đề cần giải; nhưng nếu sau này gặp tài liệu dạng catalogue lặp ảnh nhiều, con số có
thể khác — lúc đó **đo lại**, không kế thừa kết luận này. Các fixture nhỏ trong
`tests/fixtures/babeldoc/` đã được khảo sát và **không đủ đại diện** (chunk0 chỉ có 5 ảnh,
chunk1 và `page14_*` chỉ có 1 ảnh) — đó là lý do spike dùng thẳng file production.

### S4. Vì sao KHÔNG dùng `extract_image()` / `replace_image()`

Cả hai API đều tồn tại thật trong 1.28.2 (S1), nhưng thiết kế **cố ý không dùng**:

- `Page.replace_image()` cần đối tượng `Page`, buộc phải theo dõi xref ↔ page và sẽ xử lý lặp
  với ảnh dùng ở nhiều trang. Đi thẳng qua xref ở cấp `Document` đơn giản và ít trạng thái hơn.
- `Document.extract_image()` trả về dict đã **giải mã sang một format ảnh** (`image` bytes +
  `ext`). Muốn re-encode sang JPEG từ đó thì cần một thư viện ảnh (Pillow) để decode lại.
  **Pillow KHÔNG có trong `.venv`** (đã kiểm tra: `ModuleNotFoundError: No module named 'PIL'`).

=> **Dùng `pymupdf.Pixmap(doc, xref)` + `Pixmap.tobytes("jpeg", jpg_quality=85)`** — PyMuPDF
tự encode JPEG, **không cần thêm dependency nào**. Đã verify chạy thật (S6).

### S5. Vị trí gắn code, signature, data lineage (Protocol 6 — R6-01)

**File**: `src/postprocess/image_compress.py` (module mới, cạnh `chunk_merge.py`).
Không nhét vào `chunk_merge.py`: `merge_chunk_pdfs()` là code đã 2 lần dính bug trang
(Bug #7, Bug #8) và đang có test golden bám sát; nén ảnh là mối quan tâm tách biệt, gộp vào sẽ
làm bề mặt hồi quy của hàm ghép rộng ra vô cớ.

**Signature** (async cho đồng nhất với `merge_chunk_pdfs`, dù thân hàm là CPU-bound thuần):

```python
async def compress_pdf_images(pdf_path: str | Path, *, jpeg_quality: int = 85) -> ImageCompressStats
```

`jpeg_quality` là **keyword-only, mặc định 85, KHÔNG đọc từ `Settings`/`.env`/UI**
(BR-IMGCOMP-03). Tham số tồn tại chỉ để test tham số hoá được, không phải điểm cấu hình.

`ImageCompressStats` — dataclass thuần để log/test, không ghi DB, không lên UI:
`images_scanned: int`, `images_recompressed: int`, `images_skipped_already_compressed: int`,
`images_skipped_larger: int`, `images_skipped_unsupported: int`,
`size_before: int`, `size_after: int`.

**Data lineage — tường minh (R6-01), đây là phần bắt buộc đọc kỹ:**

| | |
|---|---|
| **Artifact vào** | `merged_path` — chính biến `merged_path` mà `run_job()` tạo ở Step 8 (`src/core/job_orchestrator.py:477`) và truyền cho `merge_chunk_pdfs(chunks, merged_path)` (`:479`). **KHÔNG** phải `job.file_path`, **KHÔNG** phải `chunk.output_path`. |
| **Artifact ra** | **Ghi đè in-place chính `merged_path`** — không tạo file mới, không đổi tên. Lý do: `job.output_path = str(merged_path)` ở `:508`, và `create_bilingual_pdf(merged_path, …)` ở Step 9 đều đang trỏ vào đúng path này. Sinh file mới sẽ tạo ra đúng loại lỗ hổng Bug #5 (bước sau vẫn dùng file cũ chưa nén, "thành công" nhưng sai artifact). |
| **Ai gọi** | `JobOrchestrator.run_job()`, **trong cùng khối `try` của Step 8**, **sau** `merge_chunk_pdfs(...)` và **sau** guard rỗng-chữ BR-OCR-03, **trước** `job.output_path = str(merged_path)` (`:508`). |
| **Điều kiện gọi** | `if self._settings.pdf_translate_engine == "babeldoc":` (BR-IMGCOMP-01, `src/core/config.py:135`). Nhánh `pdf2zh` **không gọi**, không đổi một dòng hành vi nào. |

**Thứ tự bắt buộc — đặt SAU guard BR-OCR-03, không phải trước.** Guard đó (`job_orchestrator.py:481-491`)
đọc `page.get_text()` để bắt job dịch ra file rỗng chữ. Nếu nén chạy trước guard, một lỗi trong
bước nén sẽ làm job `failed` với thông báo "bản dịch không chứa chữ nào" — chẩn đoán sai hoàn
toàn nguyên nhân. Nén sau guard thì lỗi nén báo đúng là lỗi nén.

**Ghi đè in-place: PyMuPDF KHÔNG cho save đè file đang mở.** Đã verify bằng cách chạy thật:

```
ValueError: save to original must be incremental
```

=> Dev **phải** ghi ra file tạm cùng thư mục rồi `os.replace()`:
`doc.save(tmp, garbage=4, deflate=True)` → `doc.close()` → `os.replace(tmp, pdf_path)`.
`os.replace` là atomic trong cùng filesystem — nếu tiến trình chết giữa chừng, `merged_path`
vẫn là bản chưa nén hợp lệ, không bao giờ là file cụt.

### S6. Thuật toán (spec cho Dev — KHÔNG phải code để copy)

1. Mở `pdf_path`. Ghi lại `size_before`.
2. Duyệt `for pno in range(doc.page_count)` → `doc.get_page_images(pno, full=True)`.
   Gom **xref duy nhất** vào một `set` trước — ảnh dùng ở nhiều trang chỉ được xử lý **một lần**
   (trong file thật có xref xuất hiện tới 10 lần; nén lại nhiều lần vừa lãng phí vừa gây
   generation loss chồng nhau).
3. Với mỗi xref, **bỏ qua** nếu `doc.xref_get_key(xref, "Filter")[0] != "null"` — tức mọi ảnh đã
   có filter (`DCTDecode`, `CCITTFaxDecode`, `JPXDecode`, `FlateDecode`, `JBIG2Decode`…) đều giữ
   nguyên. Đây chính là BR-IMGCOMP-02 "không nén chồng JPEG".
4. **Guard các trường hợp không được đụng vào** (chưa xuất hiện trong dữ liệu hiện có, nhưng
   bắt buộc phải có — đếm vào `images_skipped_unsupported`):
   - `doc.xref_get_key(xref, "ImageMask")[1] == "true"` → **bỏ qua**. Stencil mask là ảnh 1-bit
     dùng làm khuôn tô màu; biến thành JPEG 8-bit sẽ hỏng cách vẽ.
   - `info[1] != 0` (có `/SMask`, tức có kênh alpha) → **bỏ qua**. JPEG không mang được alpha.
     Có thể xử lý bằng cách tách alpha ra giữ riêng, nhưng đó là độ phức tạp không có dữ liệu
     nào hiện tại biện minh (đo được: 0/357 ảnh có SMask).
5. Tạo `pix = pymupdf.Pixmap(doc, xref)`. Nếu `pix.alpha` → `pix = pymupdf.Pixmap(pix, 0)`
   (bỏ kênh alpha) — lưới an toàn thứ hai cho bước 4.
6. `jb = pix.tobytes("jpeg", jpg_quality=jpeg_quality)`.
7. **Guard nở file**: nếu `len(jb) >= len(doc.xref_stream_raw(xref))` → **bỏ qua**, đếm vào
   `images_skipped_larger`. Ảnh rất nhỏ hoặc nhiễu cao có thể to ra sau khi encode JPEG.
8. Ghi đè:
   - `doc.update_stream(xref, jb, new=1, compress=0)` — **`compress=0` là bắt buộc**: JPEG đã nén
     rồi, để `compress=1` (mặc định!) sẽ bọc thêm một lớp Flate vô ích lên trên.
   - `doc.xref_set_key(xref, "Filter", "/DCTDecode")`
   - `doc.xref_set_key(xref, "BitsPerComponent", "8")`
   - `doc.xref_set_key(xref, "ColorSpace", …)` theo `pix.n`: `4 → /DeviceCMYK`,
     `3 → /DeviceRGB`, còn lại `→ /DeviceGray`.
   - `doc.xref_set_key(xref, "Width", str(pix.width))`, `"Height", str(pix.height)`.

   ⚠️ Ghi `/ColorSpace` là **bắt buộc, không được bỏ**: 357/357 ảnh thật đang là `ICCBased`.
   Stream mới là JPEG thường, ICC profile cũ không còn khớp — để nguyên key cũ thì màu sai.
9. `doc.save(tmp, garbage=4, deflate=True)` → `close()` → `os.replace(tmp, pdf_path)` (S5).

**Về `/DeviceCMYK` và hiện tượng đảo màu**: `Pixmap.tobytes("jpeg")` trên ảnh CMYK sinh JPEG có
marker Adobe APP14 (đã quan sát: byte đầu `ff d8 ff ee`), thường đi kèm quy ước CMYK **đảo**.
Đây là rủi ro thật và đã được **kiểm chứng bằng pixel**, không chỉ bằng "file mở được" — xem S7.

**Xử lý lỗi**: bọc phần xử lý **từng xref** trong `try/except` — một ảnh dị dạng chỉ nên bị bỏ
qua (log `warning`, tăng `images_skipped_unsupported`), **không được làm hỏng cả job** ở bước
gần cuối pipeline khi tiền dịch đã tiêu. Ngược lại, lỗi ở bước `save`/`os.replace` **phải** raise
lên — lúc đó file đích không còn tin được nữa.

### S7. Kết quả verify chạy thật — end-to-end trên file production 846.79 MB

Không phải mock, không phải ước lượng: chạy đúng thuật toán S6 trên bản copy của file thật.

| Chỉ số | Trước | Sau |
|---|---|---|
| Kích thước | 846.79 MB | **19.34 MB (−97.7%)** |
| Số trang | 415 | **415** |
| Tổng ký tự text | 1,160,121 | **1,160,121 — giống hệt từng trang** |
| Ảnh re-encode | — | 357/357 raw, 0 lỗi, 0 bị guard nở file |
| Render toàn bộ trang | — | **all pages render OK** |
| Thời gian chạy | — | **~30 giây** (415 trang) |

**Kiểm chứng thị giác bằng pixel** (chống đúng cái bẫy "tin vào status" của Bug #5 / R6-03):
render trước-sau ở 25 trang mẫu và so sánh từng pixel.

```
worst pages by mean abs pixel diff: [(0.08, 0), (0.02, 68), (0.02, 102), (0.02, 51), ...]
mean over sampled pages: 0.009  / 255
```

Sai khác trung bình **0.009/255** — mất mát thị giác không đáng kể. Trang bìa (trang 0, chứa
ảnh CMYK 5.4 MB) đã được render ra PNG và **xem tận mắt**: màu đúng, **không bị đảo màu CMYK**.

Chạy thêm trên fixture nhỏ `tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf`:
7.42 MB → 0.61 MB (−91.8%), 5/5 trang, text giống hệt, 1 ảnh raw 5,435,752 → 52,245 bytes.

### S8. Phát hiện phụ — `merge_chunk_pdfs()` đang save KHÔNG nén (cần PM quyết định)

Đo tách riêng hai tác nhân, phát hiện ngoài dự kiến ban đầu:

| Xử lý | Kích thước |
|---|---|
| Hiện tại | 846.79 MB |
| **Chỉ** `save(garbage=4, deflate=True)`, không đụng gì tới ảnh | **44.93 MB (−94.7%)** |
| Thêm re-encode JPEG q85 (thiết kế S6 đầy đủ) | **19.34 MB (−97.7%)** |

Nguyên nhân: `chunk_merge.py:131` đang gọi `output_doc.save(output_path)` **trần** — mặc định
của PyMuPDF là `deflate=False`, `garbage=0`, nên mọi stream (kể cả bitmap thô 691 MB) được ghi
ra **hoàn toàn không nén**. Phần lớn con số 846 MB đến từ đây chứ không riêng từ việc ảnh chưa
phải JPEG.

Nghĩa là: **phần lớn thắng lợi (−94.7%) đến từ một sửa đổi một dòng**, và JPEG re-encode đóng
góp thêm 57% trên phần còn lại (44.93 → 19.34 MB). Cả hai đều đáng làm; thiết kế S6 đã bao gồm
`garbage=4, deflate=True` trong bước save của nó, nên **job `babeldoc` hưởng cả hai mà không
cần đụng vào `chunk_merge.py`**.

**Điểm cần PM/user quyết định** — job dùng engine `pdf2zh` hiện cũng đang chịu đúng vấn đề save
không nén này, nhưng BR-IMGCOMP-01 nói rõ "job dùng `pdf2zh` không đổi hành vi". Hai lựa chọn:

- **(A) Giữ nguyên scope PRD** (khuyến nghị mặc định): chỉ nhánh `babeldoc` được nén; không đụng
  `chunk_merge.py`. Rủi ro hồi quy bằng 0 với đường `pdf2zh` và với các test golden Bug #7/#8.
- **(B) Mở rộng nhẹ**: đổi `chunk_merge.py:131` thành `save(output_path, garbage=4, deflate=True)`
  cho **cả hai** engine. Job `pdf2zh` cũng nhỏ đi rõ rệt, nhưng đây là thay đổi hành vi nằm
  ngoài US-16, chạm vào file đã 2 lần dính bug — cần user duyệt như một thay đổi có chủ đích,
  và cần chạy lại toàn bộ test golden của `chunk_merge`.

Tech Lead **không tự quyết** cái này vì nó mâu thuẫn trực tiếp với một business rule đã chốt.
Mặc định giao Dev là **(A)**, trừ khi PM/user chọn (B).

### S9. Yêu cầu test kèm implementation (Protocol 6 R6-02 + R6-03)

1. **Test data lineage (R6-02) — không chấp nhận `assert_awaited()` trần.** Phải khẳng định
   được giá trị cụ thể đi giữa hai bước:

   ```
   compress_pdf_images.assert_called_with(merged_path, ...)   # đúng cái merge vừa ghi ra
   ```

   với `merged_path` là chính path đã truyền cho `merge_chunk_pdfs` trong cùng test — đây đúng
   là dạng ràng buộc mà Bug #5 đã thiếu. Test riêng cho nhánh `pdf2zh`: khẳng định
   `compress_pdf_images` **không** được gọi (BR-IMGCOMP-01).
2. **Test thứ tự**: khẳng định nén chạy **sau** guard BR-OCR-03 — một job có output rỗng chữ
   phải `failed` với thông báo của guard, không phải thông báo lỗi nén.
3. **Test nội dung, không chỉ status (R6-03)**: chạy `compress_pdf_images` thật trên fixture
   `tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf` (đã có sẵn, 5 trang, 1 ảnh raw
   5.4 MB) và khẳng định: `page_count` không đổi (5), **text từng trang giống hệt trước/sau**,
   file sau nhỏ hơn, và **mọi image xref đều có `Filter != null`** sau khi chạy. Đây là test
   bắt được đúng lớp lỗi mà "job status = completed" không bao giờ bắt được.
4. **Test guard**: ảnh `DCTDecode` sẵn có phải giữ **nguyên byte** stream sau khi chạy (chống
   nén chồng — dùng luôn 3 ảnh DCTDecode có sẵn trong chính fixture đó).
5. **Không cần golden file mới**: các fixture cần thiết đã tồn tại và đã có xuất xứ ghi trong
   `tests/fixtures/babeldoc/README.md`.

### S10. Trạng thái verify

| Hạng mục | Trạng thái |
|---|---|
| Version + signature PyMuPDF | ✅ Verified — chạy thật, output ở S1 |
| Thứ tự tuple `get_page_images(full=True)` | ✅ Verified trên 538 xref thật |
| Đọc `Filter`, phát hiện ảnh raw | ✅ Verified — khớp 538/538 qua 2 cách độc lập |
| Encode JPEG q85 không cần Pillow | ✅ Verified |
| Ghi đè stream + đổi `/Filter`,`/ColorSpace` | ✅ Verified end-to-end, 357 ảnh |
| Bảo toàn text/số trang | ✅ Verified — 1,160,121 ký tự giống hệt, 415/415 trang |
| Bảo toàn màu (CMYK không đảo) | ✅ Verified bằng pixel-diff + xem ảnh render thật |
| Không save đè được file đang mở | ✅ Verified — `ValueError` thật ở S5 |
| Số liệu dedupe | ✅ Verified trên job production, **không đạt 20% → loại khỏi scope** |
| Hành vi với ảnh có `/SMask` hoặc `/ImageMask` | ⚠️ **`[UNVERIFIED]`** — không có mẫu nào trong dữ liệu hiện có (0/357). Thiết kế **bỏ qua** các ảnh này (S6 bước 4), tức nhánh code an toàn theo mặc định; nhưng chính đường `skip` đó chưa từng chạy trên dữ liệu thật. Không chặn Dev implement (hành vi mong đợi là "không làm gì"). |
| Lựa chọn (A)/(B) ở S8 | ⏸ **Chờ PM/user quyết định** — không chặn phần còn lại của US-16 |


---

## Root Cause Analysis: Text Overlap, Content-Loss & Reading-Order trên trang layout phức tạp (2026-09-07)

**Tác giả**: Tech Lead — phân tích/research, KHÔNG implement.
**Đầu vào**: `docs/ux-review-report.md` (UX-A…UX-E, 21 ảnh trang PDF đã dịch).
**Trạng thái**: ⏸ **Chưa phải kết luận cuối** — PM sẽ mời Domain Expert phản biện trước khi chốt.

### T1. Kết luận ngắn

Năm nhóm hiện tượng UX báo cáo **KHÔNG có chung một nguyên nhân**. Có ít nhất **3 lỗi độc
lập**:

| Nhóm UX | Root cause | Nằm ở đâu | Mức verify |
|---------|-----------|-----------|-----------|
| UX-A (overlap 2 block), UX-B (vỡ box), UX-E (font không đều) | **Cùng 1 nguyên nhân**: babeldoc typeset mỗi paragraph ĐỘC LẬP, neo tuyệt đối vào bbox GỐC của chính nó, không reflow theo chiều cao thực tế của paragraph trước; khi text dịch tràn đáy box thì **vẫn vẽ tiếp ra ngoài box** thay vì dừng | babeldoc `typesetting.py` | ✅ Verified (source + đo trên output thật) |
| UX-C (mất nội dung → ô trắng) | **Lỗi KHÁC HẲN**: mọi glyph có góc xoay ≠ 0°/90° (±0.1°) bị **loại bỏ khỏi IL ngay bước parse** → không dịch, không vẽ lại, mà text gốc thì đã bị xoá | babeldoc `il_creater.py:968-978` | ✅ Verified (source + tái hiện live 1 trang) |
| UX-D (sai thứ tự đọc) | **Chưa xác định** — chạy lại đúng trang mục lục đó ở chế độ 1-trang-độc-lập thì render ĐÚNG, không tái hiện được | phụ thuộc ngữ cảnh nhiều trang / chunk | ⚠️ `[UNVERIFIED]` |

Giả thuyết chính của UX ("tiếng Việt dài hơn, khung không giãn, sai lệch cộng dồn") **đúng
cho UX-A/B/E** và **sai cho UX-C** — UX-C không liên quan gì tới độ dài text.
Giả thuyết phụ của UX ("xoá text gốc xong nhưng vẽ text mới thất bại") **đúng về hiện tượng,
sai về cơ chế**: không có bước "vẽ thất bại", mà là **chưa bao giờ có gì để vẽ** vì ký tự đã
bị vứt từ bước đọc PDF.

### T2. Nguồn xác thực (Protocol 5 / R5-01)

babeldoc **0.6.4** đã cài (`babeldoc --version` → `babeldoc 0.6.4`), source tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`.
Prefix `format/pdf/document_il/` viết tắt là `IL/`.

| # | Claim | Nguồn (file:line) |
|---|-------|-------------------|
| T-01 | `on_lt_char()` **return sớm** (bỏ hẳn ký tự) nếu góc xoay của text matrix không nằm trong `-0.1..0.1` hoặc `89.9..90.1` độ | `IL/frontend/il_creater.py:968-974` |
| T-02 | Góc xoay tính bằng `atan2(b, a)` từ matrix ký tự | `il_creater.py:390-397` |
| T-03 | Mỗi paragraph được typeset bắt đầu từ **đỉnh bbox của CHÍNH NÓ** (`current_y = box.y2 - avg_height`, `current_x = box.x`) — không có tham số nào mang chiều cao thực tế của paragraph trước vào | `IL/midend/typesetting.py:1349-1350` |
| T-04 | Khi xuống dòng vượt đáy box: chỉ set cờ `all_units_fit = False`, **comment ghi rõ "这里不要 break，继续排版剩余内容"** (đừng break, tiếp tục xếp phần còn lại) → text tràn được **vẽ ra ngoài box**, đè lên block dưới | `typesetting.py:1440-1444` |
| T-05 | Vòng thu nhỏ font: `scale` giảm 0.05 (khi >0.6) rồi 0.1, tới `min_scale = 0.1` | `typesetting.py:967-1015` |
| T-06 | **Giãn khung chỉ được thử khi `scale < 0.7`**, và chỉ 2 lần: giãn xuống (`get_max_bottom_space`) rồi giãn phải (`get_max_right_space`); giãn thất bại (không còn chỗ trống) → reset `scale = 1.0` và tiếp tục thu nhỏ | `typesetting.py:1017-1062` |
| T-07 | `preprocess_document()` gom `optimal_scale` của **mọi paragraph trong CẢ tài liệu**, lấy **mode**, rồi ép mọi paragraph có scale > mode **xuống bằng mode** | `typesetting.py:919-935` |
| T-08 | Trước khi render, có bước chống chồng lấn nhưng nó chỉ **cắt ngắn box trên từ phía dưới** (`p_upper.box.y = new_y`), **không đẩy block dưới xuống** — tức làm box trên NHỎ đi (dễ tràn hơn), không tạo thêm chỗ | `typesetting.py:1172-1211` |
| T-09 | `render_paragraph()` gán `pdf_paragraph_composition = []` TRƯỚC khi gọi retypeset; nếu retypeset không apply được thì composition ở lại rỗng | `typesetting.py:1277-1280` |
| T-10 | Paragraph có composition rỗng → `render_paragraph_to_char()` trả list rỗng, log `ERROR "Unable to export paragraphs that have not yet been formatted"` | `IL/backend/pdf_creater.py:831-836` |
| T-11 | `debug_id` được sinh **luôn luôn** (`generate_base58_id()`), không phụ thuộc `--debug` → guard `typesetting.py:1008` thực tế không chặn vòng thu nhỏ | `IL/midend/paragraph_finder.py:500, 874, 911` |
| T-12 | `--translate-table-text` mặc định **False**; bật lên mới nạp `RapidOCRModel` cho table detection | `main.py:238-242, 586-591` |
| T-13 | `--max-pages-per-part` **không set thì không split** → 1 lần gọi babeldoc = 1 "document" cho T-07 | `main.py:222-225`; `format/pdf/split_manager.py:27-40` |
| T-14 | `--ocr-workaround` (vẽ nền trắng dưới text) mặc định False; `BabeldocRunner` **không** truyền flag này → ô trắng quan sát được **không phải** do rectangle nền trắng | `main.py:256`; `pdf_creater.py:882-887`; `src/services/babeldoc_runner.py:280-311` |

### T3. Bằng chứng sống (Protocol 6 / R6-03) — đo trên output production thật

**Dữ liệu**: job `136645f9-ffe8-4927-afb2-b725236ede44` (Le Cordon Bleu Pâtisserie and Baking
Foundations, 418 trang, `pdf_digital`, status `completed`).
Nguồn: `data/uploads/f88282bb-…_Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf`;
output: `data/outputs/136645f9-…/translated_vi.pdf`. Đo bằng PyMuPDF `get_text("blocks")` /
`get_text("dict")`.

**(a) Chồng lấn text tăng vọt sau khi dịch** — đếm cặp block có diện tích giao > 5% diện tích
block nhỏ hơn (đúng ngưỡng DoD-UX-01):

| Trang | Cặp chồng lấn ở BẢN GỐC | Cặp chồng lấn ở BẢN DỊCH | Tỉ lệ giao lớn nhất |
|-------|------------------------|--------------------------|---------------------|
| 6 (mục lục) | 3 | 8 | 0.95 |
| 12 | 7 | 18 | 1.00 |
| 13 | 28 | 62 | 1.00 |
| 26 | 3 | 9 | 1.00 |
| 21, 27, 39 | 0 | 5 mỗi trang | 0.90 |

→ DoD-UX-01 **FAIL** rõ rệt; trang văn xuôi thường (21, 27, 39) vốn 0 cặp chồng ở bản gốc
cũng thành 5 cặp. Khớp nhận định UX-A "xảy ra trên văn xuôi bình thường".

**(b) Tổng ký tự bản dịch THẤP HƠN bản gốc**: 520.855 / 573.211 = **0,909**. Tiếng Việt lẽ ra
phải **dài hơn** ~20–40% → thiếu hụt thực tế lớn hơn con số 9% này nhiều.

**(c) Ký tự bị xoay trong bản gốc** (`line["dir"]` ≠ 0°/90°, đúng ngưỡng T-01): **7.832 ký tự
trên 19/418 trang** (1,17% toàn sách). Danh sách trang: 11, 12, 13, 14, 25, 26, 66, 69, 73,
75, 80, 83, 86, 158, 159, 160, 171, 229, 268.

**(d) Tái hiện live UX-C** — trích trang 67 (0-index 66) ra file 1 trang, chạy babeldoc THẬT
(deepseek-chat, đúng bộ flag production + `--debug`): khối chú giải nghiêng "Disaccharide — The
word disaccharide is composed of…" (16 dòng, `dir = (0.982, -0.191)` ≈ **-11°**) **biến mất
hoàn toàn** khỏi output ở CẢ bản chạy độc lập LẪN bản production. Không có dòng log `ERROR`
nào — đúng như T-01 dự đoán: ký tự bị bỏ ở bước parse nên không có gì để báo lỗi ở bước render.
Cùng cơ chế với bảng quy đổi trang 15 (bảng nghiêng, mất 39/58 block).

**(e) Đối chứng loại trừ T-09/T-10 làm nguyên nhân chính**: 3 trang chạy lại độc lập
(trang 7 mục lục, 63 Fiche de Technique, 67) — **không** trang nào sinh log
`"Unable to export paragraphs that have not yet been formatted"`. Cơ chế T-09/T-10 **tồn tại
trong source nhưng chưa quan sát thấy kích hoạt** trên dữ liệu này → giữ lại như rủi ro đã
biết, KHÔNG kết luận là nguyên nhân của UX-C.

**(f) Kết quả bất ngờ, quan trọng cho UX-D**: trang mục lục (trang 7, 0-index 6) và trang
"Fiche de Technique" (trang 63) khi chạy LẠI ở chế độ **1 trang độc lập** thì render **ĐÚNG** —
dòng nối tiếp đều đặn `y = 289.5 → 305.1 → 320.7 → 336.3`, cùng `x = 119.9`, không lệch cột,
không đè heading. Trong bản production **cùng trang đó** các dòng nối tiếp lại nhảy ngược lên
trên và lệch trái (`y=289.6 x=119.9` → dòng tiếp theo `y=271.1 x=101.0`), và dòng
"Hai chữ T: Nhiệt độ" (`y=329.7 x=328.2`, cỡ 10.0) đè lên heading cha "4. Kỹ Thuật và Kỹ Năng
Làm Bánh 172" (`y=330.2 x=330.0`, cỡ 12.0) — **đúng hiện tượng UX-D**.

⚠️ **`[UNVERIFIED]`** — chưa xác định được biến nào tạo ra khác biệt production vs 1-trang.
Hai ứng viên, cả hai đều **chưa** kiểm chứng:
1. **T-07 (nghi ngờ mạnh nhất)**: mode-scale tính trên TOÀN BỘ document của 1 lần gọi babeldoc.
   Production gọi babeldoc theo **chunk ~38 trang** (11 chunk cho 418 trang) → mode lấy trên 38
   trang; chạy 1 trang → mode lấy trên 1 trang → `optimal_scale` khác → font khác → số dòng
   khác → vị trí khác. Số đo ủng hộ: các dòng lệch trong production đều có cỡ chữ **nhỏ hơn**
   (8.3/9.2/9.9/10.0) so với các dòng đặt đúng (10.2/12.8).
2. Độ dài text LLM trả về khác nhau giữa 2 lần chạy (không deterministic).

Không được viết fix cho UX-D trước khi phân biệt được 2 khả năng này (xem T6-1).

### T4. Root cause chi tiết

#### RC-T1 — UX-A / UX-B / UX-E: không có reflow giữa các paragraph, tràn box vẫn vẽ

Chuỗi nhân quả, mỗi mắt xích có nguồn:

1. Text dịch VI dài hơn EN → cần nhiều dòng hơn trong đúng bbox gốc.
2. Vòng `_find_optimal_scale_and_layout` thu nhỏ font để cứu (T-05). Mỗi paragraph tự chọn
   scale riêng → **UX-E (font-size không đều)**. UX đoán đúng: UX-E là **hệ quả**, không phải
   lỗi độc lập.
3. Giãn khung chỉ được thử **sau khi đã thu nhỏ xuống dưới 0.7** và chỉ khi cạnh dưới/phải còn
   khoảng trống (T-06). Trong box trang trí cỡ cố định hoặc ô bảng chật, không có chỗ trống →
   giãn thất bại → chỉ còn cách bóp chữ → **UX-B**. Box text ngắn (caption "Antonin Carême")
   vừa ngay ở scale 1.0 → không hỏng. Đúng đối chứng UX nêu: biến quyết định là **tỉ lệ độ dài
   text / sức chứa khung**, không phải loại box.
4. Nếu tới `min_scale = 0.1` vẫn không vừa: **không có nhánh nào cắt bớt hay dừng vẽ** — T-04
   nói thẳng là cố ý vẽ tiếp ra ngoài box.
5. Paragraph kế tiếp vẫn neo vào `box.y2` gốc của chính nó (T-03), không hề biết paragraph
   trước đã tràn tới đâu → chữ tràn nằm chồng lên chữ của block dưới → **UX-A**.
6. Bước chống chồng lấn duy nhất (T-08) đi **sai hướng**: nó **cắt ngắn** box trên chứ không
   đẩy block dưới xuống → giảm chỗ chứa, làm bước 4 dễ xảy ra hơn.

Điểm này giải thích luôn quan sát baseline "đầu trang sạch, cuối trang nát" của UX: không phải
sai số cộng dồn theo toạ độ, mà là **xác suất cộng dồn** — trang càng xuống dưới càng nhiều
paragraph đã tràn đè lên nhau, và block dưới không có cách nào tự tránh.

#### RC-T2 — UX-C: ký tự xoay bị vứt ở bước parse (lỗi ĐỘC LẬP, không liên quan độ dài text)

`il_creater.py:968-974` (T-01): bất kỳ glyph nào có góc xoay ngoài `0°±0.1` và `90°±0.1` bị
`return` — không vào IL, không được dịch, không được vẽ lại. Vì babeldoc **dựng lại content
stream** thay vì sửa tại chỗ, text gốc cũng không còn → đúng hiện tượng "ô trắng trống, không
ai biết mình đang thiếu gì".

Sách Le Cordon Bleu dùng rất nhiều khối nghiêng nhẹ (~11°) làm chú giải/pull-quote và bảng
quy đổi đặt nghiêng → 7.832 ký tự / 19 trang mất trắng (T3-c). Đây là **Blocker** đúng như UX
xếp hạng.

Lưu ý phân biệt: hiện tượng "vài ô trong bảng Fiche de Technique trống" mà UX quan sát **không**
tái hiện được khi chạy lại trang đó độc lập (T3-e/f: 42 block / 1.352 ký tự, gần bằng bản gốc
41 block / 1.320 ký tự). Nhiều khả năng phần lớn "ô trống" trong ảnh chụp trang đó thực ra là
**chữ bị dời chỗ (RC-T1)** chứ không phải mất hẳn — người đọc nhìn ảnh không phân biệt được 2
loại. Chỉ nội dung xoay là mất thật, đã chứng minh.

#### RC-T3 — UX-D: chưa xác định, phụ thuộc ngữ cảnh chunk

Xem T3-f. `[UNVERIFIED]`. Không gộp vào RC-T1 vì RC-T1 chỉ giải thích được dịch chuyển **xuống
dưới**, còn quan sát production là dòng nối tiếp nhảy **lên trên và sang trái**.

### T5. Phần thuộc về code của team (không phải "toàn bộ nằm ở babeldoc")

Khác kết luận RC-1 (2026-09-06, "root cause không nằm trong code của team"), lần này team có
đóng góp thật vào triệu chứng:

| # | Vấn đề phía team | Nguồn |
|---|------------------|-------|
| P-1 | Chunk theo trang (~38 trang/chunk) = **ranh giới document của T-07**. Mode-scale — tức cỡ chữ cuối cùng — phụ thuộc vào việc trang nào rơi vào chunk nào. Cùng 1 trang, chunk khác nhau ⇒ cỡ chữ khác nhau ⇒ **UX-E xuyên chương** và (nghi) **UX-D**. | T-07 + `src/core/chunking.py` (chunk theo `page_start/page_end`) |
| P-2 | `BabeldocRunner` **không** truyền `--translate-table-text` (T-12). Chưa đo được flag này ảnh hưởng gì tới trang bảng — có thể tốt hơn, có thể tệ hơn. | `babeldoc_runner.py:280-311` |
| P-3 | `BabeldocRunner` **không** truyền `--max-pages-per-part` (T-13) → không kiểm soát được đơn vị tính mode-scale độc lập với kích thước chunk. | như trên |
| P-4 | Không có kiểm tra hậu kỳ nào phát hiện chồng lấn hay mất nội dung. Job báo `completed` với 19 trang mất chữ và hàng trăm cặp block chồng nhau. Đây đúng dạng lỗ hổng Protocol 6 R6-03 đã mô tả, ở cấp **chất lượng render** thay vì cấp **liên kết bước**. | `src/core/job_orchestrator.py` |

### T6. Phương án đề xuất — theo TỪNG nhóm lỗi

Không có 1 giải pháp chung. Effort tính theo ngày-người của 1 Dev.

#### G1 (UX-C, Blocker) — patch runtime cho ngưỡng góc xoay của babeldoc

Nới điều kiện `il_creater.py:973` từ `±0.1°` lên ngưỡng cấu hình được (đề xuất `±15°`), để text
nghiêng nhẹ vẫn vào IL. Có 3 cách thực thi:

| Cách | Mô tả | Effort | Risk |
|------|-------|--------|------|
| G1a | **Fork/patch có kiểm soát**: `uv tool` cài babeldoc từ fork nội bộ đã sửa 1 dòng đó | 1–2 ngày (gồm dựng pipeline build fork) | **Cao** — nợ bảo trì vĩnh viễn, mỗi lần babeldoc lên version phải rebase; đúng loại nợ Protocol 5 sinh ra để tránh |
| G1b | **`sitecustomize`/wrapper monkey-patch**: vì gọi qua **subprocess**, có thể chèn 1 module patch qua `PYTHONPATH` + `PYTHONSTARTUP` không đụng file cài | 1 ngày | **Cao** — sửa hành vi tool bên thứ 3 từ bên ngoài, khó debug, dễ vỡ âm thầm khi đổi version |
| G1c | **Tiền xử lý: "duỗi thẳng" text nghiêng** — dùng PyMuPDF phát hiện line có `dir` ngoài 0°/90°, redact text gốc và vẽ lại cùng nội dung ở góc 0° trong cùng bbox, TRƯỚC khi đưa vào babeldoc | 2–3 ngày | **Trung bình** — không đụng babeldoc; đánh đổi: mất hiệu ứng nghiêng thẩm mỹ (chấp nhận được: thà chữ thẳng còn hơn mất chữ). Rủi ro thật: bbox của text nghiêng rộng hơn text thẳng nên thường đủ chỗ, nhưng **chưa verify** trên mẫu thật |
| G1d | **Chấp nhận + cảnh báo**: không sửa render, nhưng **phát hiện và báo cáo** — quét trước, ghi vào job "19 trang chứa 7.832 ký tự xoay sẽ bị mất", xuất phụ lục text các khối đó | 0,5 ngày | **Thấp** |

**Khuyến nghị**: **G1d ngay** (rẻ, biến lỗi im lặng thành lỗi nhìn thấy được — đúng tinh thần
UX xếp UX-C là Blocker *vì người đọc không biết mình mất gì*), rồi **G1c** làm fix thật.
**Không** chọn G1a/G1b nếu chưa thử G1c.

⚠️ **`[UNVERIFIED]`**: G1c chưa được spike. Bắt buộc R5-02 spike trên trang 67 và trang 15
trước khi implement đầy đủ.

#### G2 (UX-A/B/E, Critical) — giảm áp lực tràn thay vì sửa engine typeset

Viết lại thuật toán typeset của babeldoc là ngoài tầm (≈ toàn bộ `typesetting.py`, 1.682 dòng).
Bốn hướng khả thi:

| Hướng | Mô tả | Effort | Risk | Ghi chú |
|-------|-------|--------|------|---------|
| G2a | **Prompt "dịch cô đọng"**: bắt buộc bản dịch ≤ ~110% độ dài nguồn (đo bằng ký tự), thêm chỉ thị vào `src/core/prompt_builder.py` biến thể babeldoc | 0,5 ngày | Thấp | Chỉ giảm áp lực, không xoá lỗi. PRD đã có chiến lược "concise prompt" — hiện chưa áp cho nhánh babeldoc. **Đo được**: so tỉ lệ ký tự VI/EN trước–sau |
| G2b | **Chuẩn hoá đơn vị tính mode-scale**: truyền `--max-pages-per-part` cố định (vd 4) độc lập với chunk size → cỡ chữ không còn phụ thuộc chunk nào chứa trang nào (P-1/P-3) | 0,5 ngày | Thấp–TB | Sửa **UX-E xuyên chương** và có thể cả UX-D. **Phải A/B đo trước** — chưa verify part nhỏ hơn có tốt hơn không |
| G2c | **Gate chất lượng tự động (DoD-UX-01/02)**: hậu kiểm output — đếm cặp block chồng > 5% và block gốc không có text dịch tương ứng; vượt ngưỡng → đánh dấu trang cần review, không báo `completed` trắng trơn | 1,5–2 ngày | Thấp | Script đo đã có sẵn ở T3 (chạy thật rồi). Đây là món **giá trị nhất trên đơn vị công**: không sửa được lỗi nhưng chặn được việc giao hàng lỗi mà không ai biết |
| G2d | **Fallback engine cho trang phức tạp**: phát hiện trang nhiều cột/bảng → dịch bằng `pdf2zh` thay vì babeldoc | 3–5 ngày | **Cao** | ⚠️ **`[UNVERIFIED]` — CHƯA ĐƯỢC ĐỀ XUẤT**: chưa đo pdf2zh trên đúng các trang này. pdf2zh cũng neo bbox gốc và cũng có tràn chữ (chính lý do project thêm babeldoc). **Không implement trước khi có 1 lần đo A/B thật trên trang 6, 13, 63, 67** |

**Khuyến nghị**: **G2c + G2a** trước (rẻ, rủi ro thấp, kết quả đo được ngay), **G2b** sau khi
A/B; **G2d chỉ khi đã verify pdf2zh thực sự tốt hơn trên đúng bộ trang này**.

#### G3 (UX-D, Major) — điều tra trước, sửa sau

Chưa đủ dữ liệu để đề xuất fix. Việc cần làm (0,5 ngày, không cần code sản phẩm):
chạy babeldoc trên **cùng trang mục lục** với 3 cấu hình — (i) 1 trang, (ii) 38 trang giống
chunk production, (iii) 38 trang + `--max-pages-per-part 4` — rồi so vị trí/cỡ chữ. Nếu (ii)
tái hiện lỗi còn (iii) thì không → xác nhận T-07 là nguyên nhân, và **G2b chính là fix cho cả
UX-D**. Nếu cả (ii) và (iii) đều tái hiện → nguyên nhân khác, điều tra tiếp.

#### G4 — Report upstream

Cả RC-T1 (T-04, cố ý vẽ tràn) và RC-T2 (T-01, vứt ký tự xoay) đều là hành vi của babeldoc, ảnh
hưởng mọi người dùng dịch sang ngôn ngữ dài hơn ngôn ngữ nguồn. Nên mở issue upstream kèm 2
file tái hiện tối thiểu đã có sẵn (`p67.pdf`, `p15.pdf`). Effort 0,5 ngày, risk 0, nhưng
**không tính là fix** — không được chờ upstream để đóng task.

**✅ Đã thực hiện (2026-09-07)**: đã mở issue tại
[funstory-ai/BabelDOC#615](https://github.com/funstory-ai/BabelDOC/issues/615) — tổng hợp
3 lỗi kèm nguồn xác thực (file:line): Bug A = RC-T2 (T-01, vứt glyph xoay), Bug B = RC-T1
(T-04 vẽ tràn + T-08 chống chồng lấn sai hướng), Bug C = root cause `max_tokens=2048` hardcode
mất nội dung với reasoning model (CHANGELOG 2026-09-06). Repro file (`p67.pdf`, `p15.pdf`)
chưa đính kèm trực tiếp trong issue, sẽ gửi khi maintainer yêu cầu. **Không chờ phản hồi
upstream để đóng bất kỳ task nào** — giữ nguyên tinh thần G4/P2.2.

#### G5 — Known limitation trong PRD

Dù chọn hướng nào, ghi vào PRD: bản dịch giữ layout PDF **không** đảm bảo 100% không chồng
chữ trên trang bố cục phức tạp với engine hiện tại; kèm số đo thật ở T3 để người dùng biết quy
mô. Effort 0,5 ngày.

### T7. Yêu cầu test kèm bất kỳ fix nào (Protocol 5 + 6)

1. **Golden fixture từ output thật, không viết tay** (Protocol 5 mục 3): lưu
   `tests/fixtures/babeldoc/rotated_text_p67.pdf` (đã trích, có khối -11°) và
   `toc_2col_p7.pdf`. Assert: sau khi dịch, **số ký tự của khối nghiêng > 0**.
2. **Test theo DoD-UX-01/02 của UX**, không phải theo flag: đo cặp bbox giao > 5% và block gốc
   không có text dịch — chính script ở T3.
3. **Live E2E (R6-03)**: mở PDF output và **đọc nội dung** vùng khối nghiêng; không tin field
   `status`.
4. **Data lineage (R6-02)**: nếu làm G2b, assert giá trị `max_pages_per_part` từ `Settings` đi
   thật tới `args` của subprocess, không chỉ `assert_awaited()`.

### T8. Trạng thái verify (tổng hợp)

| Claim | Trạng thái |
|-------|-----------|
| Ngưỡng góc xoay ±0.1° làm mất ký tự | ✅ Verified — source `il_creater.py:968-974` + tái hiện live trang 67 |
| Quy mô mất chữ do xoay (7.832 ký tự / 19 trang) | ✅ Verified — đo trên PDF gốc thật |
| Overflow được cố ý vẽ ra ngoài box | ✅ Verified — `typesetting.py:1440-1444` + comment gốc |
| Không reflow giữa các paragraph | ✅ Verified — `typesetting.py:1349-1350` |
| Giãn khung chỉ chạy khi scale < 0.7 | ✅ Verified — `typesetting.py:1017-1062` |
| Mode-scale tính trên cả document | ✅ Verified — `typesetting.py:919-935` |
| Chồng lấn tăng sau dịch (số liệu bảng T3-a) | ✅ Verified — đo trên output production |
| T-09/T-10 (composition rỗng) là nguyên nhân UX-C | ❌ **Đã loại trừ trên dữ liệu này** — 3 lần chạy live không sinh log tương ứng; giữ lại như rủi ro đã biết |
| Nguyên nhân UX-D | ⚠️ **`[UNVERIFIED]`** — không tái hiện được ở chế độ 1 trang; xem G3 |
| Mode-scale/chunk là nguyên nhân UX-D và UX-E xuyên chương | ⚠️ **`[UNVERIFIED]`** — mới là suy luận từ source + 1 quan sát cỡ chữ; cần A/B ở G3 |
| pdf2zh có bị lỗi tương tự hay không | ⚠️ **`[UNVERIFIED]`** — chưa đo. **Chặn** đề xuất G2d |
| `--translate-table-text` ảnh hưởng trang bảng | ⚠️ **`[UNVERIFIED]`** — chưa đo |
| G1c (duỗi thẳng text nghiêng) khả thi | ⚠️ **`[UNVERIFIED]`** — chưa spike (bắt buộc R5-02) |

---

## Final Decision: Babeldoc Layout Bug Fix Roadmap (sau phản biện Domain Expert, 2026-09-07)

**Tác giả**: Tech Lead. **Đầu vào**: section "Root Cause Analysis: Text Overlap, Content-Loss
& Reading-Order…" (T1–T8, 2026-09-07) + phản biện độc lập của Domain Expert (PDF typesetting).
**Trạng thái**: ✅ **Đây là quyết định kỹ thuật cuối cùng** cho nhóm lỗi UX-A…UX-E. Ba mục
thuộc thẩm quyền PM/user được tách riêng ở U7 (escalation).

Mọi claim mới trong section này đã được Tech Lead **tự verify lại**, không kế thừa từ phản
biện. Nguồn xác thực ghi ở U1.

### U1. Kết quả tự verify các phát hiện mới của Domain Expert (Protocol 5 / R5-01)

Môi trường: babeldoc **0.6.4** (`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`),
pdf2zh **1.9.11** (`/Users/hieutt/.local/share/uv/tools/pdf2zh/lib/python3.12/site-packages/pdf2zh/`),
PyMuPDF **1.28.2 / MuPDF 1.28.2**. Prefix `IL/` = `format/pdf/document_il/`.

| ID | Claim của Expert | Phán quyết | Nguồn xác thực Tech Lead tự chạy/đọc |
|----|------------------|-----------|--------------------------------------|
| V-1 | Backend babeldoc **không** render được chữ xoay góc tuỳ ý → nới ngưỡng góc KHÔNG phải fix tận gốc | ✅ **ĐÚNG — xác nhận** | `IL/backend/pdf_creater.py:111-120` chỉ phát 2 dạng `Tm`: `0 1 -1 0` (khi `char.vertical`) và `1 0 0 1` (mọi trường hợp khác). `IL/il_version_1.py:627-663`: `PdfCharacter` có `vertical: bool`, `scale: float` — **không có field góc xoay nào**. Kể cả nới ngưỡng ở `il_creater.py:973`, char nghiêng vẫn bị vẽ lại NGANG. |
| V-2 | pdf2zh 1.9.11 **không** vứt chữ nghiêng nhẹ; chỉ lọc font dọc | ✅ **ĐÚNG — xác nhận** | `pdf2zh/converter.py:244`: điều kiện duy nhất liên quan matrix là `child.matrix[0] == 0 and child.matrix[3] == 0` (font dọc thuần). Char nghiêng ~11° có `matrix[0]≈matrix[3]≈0.98` → không khớp → đi tiếp như text thường; render tại `converter.py:384` với `1 0 0 1 x y Tm` (ngang). Kết luận: pdf2zh **không mất chữ**, nhưng **cũng duỗi thẳng** — thẩm mỹ ≈ G1c. |
| V-3 | Text trong vùng nhãn `table` **không được dịch**, giữ nguyên tiếng Anh (loại content-loss thứ 4) | ❌ **BÁC BỎ** — xem U2 | Cơ chế Expert mô tả có thật nhưng **bị vô hiệu hoá bởi `fallback_line`**; và đo trên output production cho kết quả ngược lại. Chi tiết + số liệu ở U2. |
| V-4 | `babeldoc` latest trên PyPI = 0.6.4 = bản đang cài; nên pin | ✅ **ĐÚNG — xác nhận** | PyPI JSON API `https://pypi.org/pypi/babeldoc/json` (fetch 2026-09-07): `info.version = 0.6.4`; releases gần nhất `0.5.9 → 0.6.0 → 0.6.1 → 0.6.2 → 0.6.3 → 0.6.4`. |
| E-1 | `get_max_bottom_space()` đo chỗ trống thật, không đè paragraph khác → "giãn trước, bóp sau" là patch nhỏ không dây chuyền | ✅ **ĐÚNG — xác nhận** | `IL/midend/typesetting.py:1628-1660`: hàm loại trừ mọi `page.pdf_paragraph`, `page.pdf_character`, `page.pdf_figure` nằm dưới và có giao ngang, chặn dưới bằng `page.cropbox.box.y * 1.1`. **Phát hiện bổ sung của Tech Lead**: khi giãn xuống THÀNH CÔNG (`typesetting.py:1036-1037`) vòng lặp `continue` với `scale` ĐANG ở mức < 0.7 — **không bao giờ thử lại scale 1.0 trong box đã giãn**. Tức chữ bị bóp nhỏ vĩnh viễn dù sau đó đã có đủ chỗ. Đây là 1 lỗi logic thật, đúng như Expert dự đoán, và mạnh hơn Expert mô tả. |
| E-2 | babeldoc vứt char xoay **im lặng**, không cả `logger.debug` | ✅ **ĐÚNG — xác nhận** | `IL/frontend/il_creater.py:968-974`: nhánh `return` ở dòng 974 không có log; chỉ nhánh `except` (dòng 975-979) mới `logger.warning`. |
| E-3 | `insert_text(..., morph=(pivot, Matrix(angle)))` của PyMuPDF vẽ được text xoay góc tuỳ ý (khác `insert_textbox` chỉ 0/90/180/270) | ✅ **ĐÚNG — đã spike chạy thật** | Xem U3. |

### U2. BÁC BỎ V-3 — bảng KHÔNG bị bỏ dịch (bằng cả source lẫn dữ liệu sống)

Đây là điểm PM yêu cầu ưu tiên verify vì nếu đúng sẽ là loại content-loss thứ 4. **Kết luận:
không phải.** Bốn tầng bằng chứng:

**(1) Expert đọc `is_text_layout()` bị cắt cụt.** Expert trích `layout_helper.py:801-813` và
kết luận danh sách "chỉ chứa `table_text`". Danh sách thật kéo dài tới **dòng 849**, gồm
`table_caption`, `table_footnote`, `table_title`, `table_cell`, `wired_table_cell`,
`wireless_table_cell`, `table_cell_hybrid`… (`layout_helper.py:803-849`). Đúng là **không có
nhãn trần `table`** — phần này Expert nói đúng.

**(2) Model layout mặc định thật sự sinh nhãn `table`** — nên nguy cơ là có thật, không phải
tưởng tượng. Tech Lead nạp trực tiếp metadata của model ONNX đang dùng
(`~/.cache/babeldoc/models/doclayout_yolo_docstructbench_imgsz1024.onnx`, đọc bằng
`onnx.load` + `metadata_props`, đúng cách `docvision/doclayout.py:47-49` làm):

```
{0:'title', 1:'plain text', 2:'abandon', 3:'figure', 4:'figure_caption',
 5:'table', 6:'table_caption', 7:'table_footnote', 8:'isolate_formula', 9:'formula_caption'}
```

Chạy chính model này trên file gốc, trang 63 (Fiche de Technique) cho:
`{'table': 1, 'table_caption': 1, 'abandon': 2}` với box `table` = `[88.8, 78.1, 612.8, 462.5]`
— tức **gần trọn trang**. Nếu chỉ có cơ chế Expert mô tả thì cả trang 63 phải là tiếng Anh.

**(3) Nhưng `fallback_line` chặn đường đó lại.** `IL/midend/layout_parser.py:171-208`: sau khi
chạy model, babeldoc **luôn** gọi `generate_fallback_line_layout_for_page()` cho MỌI trang,
sinh thêm 1 `PageLayout(class_name="fallback_line", conf=1)` bao quanh **từng cụm dòng chữ**.
`fallback_line` **có** trong `is_text_layout` (`layout_helper.py:844`) và đứng **trên**
`table`/`figure`/`image` trong `layout_priority` (`layout_helper.py:725-728`) —
`get_character_layout()` trả về layout ưu tiên cao nhất khớp char, nên char trong ô bảng nhận
`fallback_line`, **không** nhận `table` → không rơi vào `skip_chars` ở
`paragraph_finder.py:454-455` → **được dịch bình thường**.

**(4) Đo trên output production thật (R6-03)** — job `136645f9-…`, `translated_vi.pdf`, đếm ký
tự trong block ≥ 25 ký tự không mang dấu tiếng Việt (chuẩn hoá NFD, bắt cả `ăâđêôơư`):

| Chỉ số | Giá trị |
|--------|---------|
| Tổng ký tự (block ≥ 25 ký tự) | 631.947 |
| Ký tự trong block **không có dấu tiếng Việt** | 17.180 (**2,7%**) |
| Số trang có > 200 ký tự không dấu | **11 / 418** |
| Trang 63 (Fiche de Technique, vùng `table` gần trọn trang) | 39 block, chỉ **3** block không dấu, đều là tên riêng: `"Fondant au chocolat, coulis de framboise"`, `"© Le Cordon Bleu International"`, `"Gluxit Protein 100 200"` (`Gluxit` LÀ tiếng Việt) |

11 trang còn lại là **index/mục lục cuối sách (409–418)**, **credit ảnh** (`"Credits: …
© iStockphoto.com"`, trang 18, 188) và **danh sách tên riêng** (trang 16: tên các cơ sở
Le Cordon Bleu, tên người). Không có trang nào là bảng bị bỏ dịch.

**Kết luận U2**: V-3 **sai về hệ quả**. Không tồn tại loại content-loss thứ 4. Cơ chế
`is_text_layout` → `skip_chars` là **rủi ro đã biết** (nếu upstream đổi/bỏ `fallback_line`, hoặc
nếu bật `--translate-table-text` làm đổi tập nhãn), nên ghi vào bảng rủi ro U6, **không** đưa
vào roadmap fix.

**Hệ quả cho đề xuất `--translate-table-text`**: Expert nâng flag này thành "quyết định sản
phẩm hạng nhất" **dựa trên tiền đề vừa bị bác bỏ**. Vì bảng đã được dịch sẵn, flag này mất lý
do chính. Nó vẫn có thể cải thiện **cách gom dòng** trong bảng (thay `fallback_line` theo dòng
bằng `wired/wireless_table_cell` theo ô), nhưng đó là câu hỏi chất lượng dàn trang, kèm chi
phí nạp thêm RapidOCR và rủi ro "experimental". → **Giữ nguyên mức P2 tuỳ chọn**, đo kèm trong
thí nghiệm A/B duy nhất (P0.2), **không** nâng ưu tiên.

### U3. G1e (overlay PyMuPDF `morph`) — ĐÃ SPIKE THẬT, KHẢ THI

Tech Lead đã chạy spike (không mock), PyMuPDF 1.28.2:

```python
page.insert_text(pivot, text, fontsize=11,
                 morph=(pivot, pymupdf.Matrix(11)),      # xoay 11°
                 fontname="vi", fontfile="fonts/NotoSerif-Regular.ttf")
```

Kết quả đọc lại bằng `get_text("dict")` trên chính file vừa ghi:

```
dir: (0.9816271066665649, -0.19080941379070282)
text: 'Đường nghiêng: nhiệt độ 180°C, 250g bột mì'
```

Hai điều được chứng minh cùng lúc:
1. `morph` cho ra góc xoay tuỳ ý thật — và `dir` thu được **trùng khít** với `dir` của khối
   nghiêng trang 67 trong sách gốc đã đo ở T3-d (`(0.982, -0.191)`). Tức đây đúng là công cụ
   tái tạo lại được hiệu ứng thiết kế đã mất.
2. Dấu tiếng Việt đầy đủ (`Đ ườ ệ độ ộ ì`) + ký hiệu `°C` render và trích xuất lại đúng, với
   **font project đã có sẵn** — `fonts/NotoSerif-Regular.ttf` là file font duy nhất trong repo,
   không cần thêm dependency.

**Rủi ro còn lại của G1e (chưa spike, phải làm ở P1.1)**: `insert_text` **không tự xuống dòng**
— phải tự tách dòng + tự bóp font cho vừa bbox nghiêng. Đây chính là "tam nan" ở U5 nhưng trong
phạm vi **ta kiểm soát được**: bóp tới 70% (đúng DoD-UX-03) rồi FLAG, không bao giờ bóp tới 0.1
như `min_scale` của babeldoc.

**Quyết định**: **CHỌN G1e làm hướng chính cho UX-C**, thay thế G1c trong đề xuất T6. Lý do
quyết định là **V-1**, không phải "nợ bảo trì": vì backend babeldoc không có khả năng render
góc xoay (không có field góc trong `PdfCharacter`), **mọi** hướng đi xuyên qua babeldoc —
G1a fork, G1b monkey-patch, G1c duỗi thẳng — đều **bắt buộc** mất góc nghiêng. G1e là hướng
duy nhất giữ được thẩm mỹ, effort ngang G1c (2–3 ngày). **G1a/G1b bị LOẠI vĩnh viễn**: chúng
không những mang nợ bảo trì mà còn **không đạt được mục tiêu** (V-1) — nới ngưỡng chỉ đổi "mất
chữ" thành "chữ bị duỗi thẳng + gom dòng sai", vì `paragraph_finder` gom dòng bằng hình học
ngang sẽ băm 1 dòng nghiêng 11° thành nhiều mảnh. Đồng ý với Expert ở điểm này.
**G1c giữ lại làm phương án dự phòng** nếu spike fit-text của G1e thất bại.

### U4. Roadmap đã chốt

Nguyên tắc: **đo trước, mọi fix phải A/B được, KHÔNG fork engine reflow.**

#### P0 — Thiết bị đo + khoá nền (≈ 3,5 ngày, làm trước mọi fix)

**P0.1 — Gate chất lượng G2c MỞ RỘNG (2 ngày).** Hậu kiểm output PDF, 5 kiểm tra:

| Kiểm tra | Nguồn / lý do | Ứng với |
|----------|---------------|---------|
| a. cặp block text giao > 5% diện tích block nhỏ hơn | script đã chạy thật ở T3-a | DoD-UX-01 / UX-A |
| b. text vượt qua **đường viền vẽ** (`page.get_drawings()`) | ✅ đồng ý với Expert (5c) — gate chỉ đo text∩text sẽ cho PASS sai 1 trang có đúng 1 box tràn viền mà không đè text nào | DoD-UX-03 / UX-B |
| c. text đè lên **ảnh** (`page.get_image_rects()`) | như trên | UX-B |
| d. **pre-scan chữ xoay** trên file GỐC (`line["dir"]` ngoài 0°/90°) → cảnh báo trước + xuất phụ lục text (chính là G1d) | T3-c (7.832 ký tự / 19 trang) | UX-C |
| e. **bảo toàn thực thể**: regex trích `số + đơn vị` (`180°C`, `250g`, `10 min`, `1/2`) từ block GỐC, assert xuất hiện đủ trong block dịch tương ứng | ✅ đồng ý với Expert (mục 2) — **đây là lỗ hổng nghiêm trọng nhất của đề xuất T6 cũ: toàn bộ test đang đo hình học, không có dòng nào đo nội dung** | DoD-UX-02 |

Output **bắt buộc** là **hàng đợi review theo trang, xếp hạng mức nghiêm trọng + ảnh overlay**,
không phải 1 kết quả pass/fail toàn tài liệu — với 418 trang, mục tiêu là QA soi 30–50 trang bị
flag. ✅ Đồng ý hoàn toàn với Expert. Bổ sung của Tech Lead: gate phải **ghi số đo vào DB theo
job** để so được giữa các lần chạy — nếu không thì không A/B được, và đó chính là lý do gate
phải đứng TRƯỚC mọi fix.

**P0.2 — MỘT thí nghiệm A/B duy nhất (1 ngày).** ✅ Đồng ý gộp G3 + G2b-A/B + P-2 + G2d thành
1 lần chạy — chúng vốn là cùng 1 thí nghiệm; chạy tách là lãng phí 1 vòng round-trip.
- Trang: **7, 13, 15, 63, 67** (đã trích sẵn từ T3; phủ mục lục / văn xuôi 2 cột / bảng nghiêng
  / bảng lớn / khối chú giải nghiêng).
- Cấu hình: (i) 1 trang; (ii) chunk 38 trang giống production; (iii) chunk 38 +
  `--max-pages-per-part 4`; (iv) (ii) + `--translate-table-text`; (v) pdf2zh cùng bộ trang.
- **Khoá biến "LLM không deterministic"** ✅ (đồng ý — Expert đúng, và đây là điều T6/G3 bỏ
  sót): chạy (i) trước để làm ấm cache babeldoc, các lần sau **KHÔNG** truyền `--ignore-cache`
  (`src/services/babeldoc_runner.py:323-324` chỉ thêm flag khi `ignore_cache=True` → chỉ cần
  đặt False). Không khoá cache thì mọi kết luận đều bị nghi ngờ.
- **Dump debug paragraph boxes; so SỐ PARAGRAPH + BOX, không chỉ so vị trí dòng cuối** ✅
  (đồng ý). Tech Lead xác nhận tiền đề suy luận của Expert là đúng: RC-T3 ghi nguyên văn hiện
  tượng production là dòng nhảy **"lên trên và sang trái"**, không phải xuống dưới — nên "gom
  nhầm paragraph" là ứng viên hợp lệ ngang hàng T-07 mode-scale, và `--split-short-lines` (app
  đang bật, `babeldoc_runner.py:308-309`) là biến nghi ngờ chính.
- Trả lời **cùng lúc 4 câu**: UX-D do đâu; G2b (`--max-pages-per-part`) có đáng không;
  `--translate-table-text` đổi gì trên trang bảng; pdf2zh có đáng làm fallback cho 19 trang chữ
  xoay không.

**P0.3 — Pin `babeldoc==0.6.4` (0,1 ngày).** ✅ Đồng ý. Mọi số đo ở T3/U1/U2 và toàn bộ thiết
kế G1e đều gắn với hành vi bản này; upstream đang release dày (6 bản gần đây).

#### P1 — Fix thật (≈ 3 ngày, chỉ bắt đầu sau khi P0 xanh)

**P1.1 — UX-C: spike fit-text cho G1e (0,5 ngày) → implement (2 ngày).**
Spike phải trả lời: với khối 16 dòng nghiêng −11° ở trang 67, bản dịch VI có vừa bbox gốc ở
scale ≥ 0,7 không. Đạt → implement. Không đạt → **G1c** (duỗi thẳng, mất góc nghiêng) hoặc
**pdf2zh cho riêng 19 trang xoay**, chọn theo số đo P0.2-(v).
**Data lineage (R6-01)**: `rotated_blocks ← source.pdf` (quét bằng PyMuPDF, `line["dir"]`) →
`translated_blocks ← LLM provider của app` (KHÔNG qua babeldoc) → overlay lên
`babeldoc_output.pdf` bằng `insert_text(..., morph=…)`. Bước overlay đọc `translated_blocks`,
**không** đọc lại `source.pdf`.
G1d (phụ lục text cho QA) đã nằm trong P0.1-d và giao **luôn** kèm mọi phương án — nhưng ✅ đồng
ý với Expert: đó là **phụ lục cho QA**, không phải sản phẩm giao người đọc.

**P1.2 — Viết lại G2a theo hướng bất biến nội dung (0,5 ngày).** ✅ **Đồng ý với Expert, và đây
là chỗ Tech Lead tự nhận đề xuất T6/G2a cũ SAI.** Bản cũ ghi "bắt buộc bản dịch ≤ ~110% độ dài
nguồn" — hard cap độ dài trong prompt ép LLM lược bỏ định lượng/gộp bước. Với sách công thức,
mất "180°C" hay "10 phút" nguy hiểm hơn UX-C nhiều: bản dịch **trông hoàn hảo**, gate hình học
không bao giờ bắt được. G2a bản chốt:
- (a) prompt nêu **bất biến nội dung tường minh**: mọi con số, đơn vị, nhiệt độ, thời gian, tên
  nguyên liệu, số bước phải có đủ trong bản dịch;
- (b) khuyến khích **văn phong cô đọng** (bỏ hư từ, câu ngắn) — KHÔNG đưa con số 110% vào
  prompt; tỉ lệ ký tự chỉ là **metric đo SAU**, không phải chỉ thị cho LLM;
- (c) chốt chặn là **gate P0.1-e** (bảo toàn số + đơn vị), không phải lời hứa của prompt.
Ghi rõ: G2a chỉ tác dụng ở văn xuôi, **không cứu được UX-B** (box cố định vốn text đã ngắn).

**P1.3 — G2b (`--max-pages-per-part`) chỉ implement nếu P0.2 chứng minh.** Kèm assert data
lineage R6-02: giá trị từ `Settings` phải đi thật tới `args` của subprocess, không chỉ
`assert_awaited()`.

#### P2 — Nền dài hạn

- **P2.1 — Chính sách "tam nan" theo loại phần tử** → **escalate PM/user**, xem U7.
- **P2.2 — Upstream babeldoc**: 2 PR nhỏ + 1 issue.
  - PR (a): **đảo thứ tự "giãn xuống TRƯỚC, bóp SAU"**. ✅ Đồng ý với Expert, và Tech Lead
    verify ra lý do mạnh hơn (E-1): hiện tại khi giãn xuống thành công, vòng lặp `continue` với
    `scale` đang < 0.7 và **không bao giờ thử lại 1.0** trong box mới — chữ bị bóp nhỏ vĩnh viễn
    dù đã có đủ chỗ. Đây là **bug logic**, không chỉ "thứ tự chưa tối ưu" → khả năng merge cao.
  - PR (b): biến ngưỡng góc `il_creater.py:973` thành tham số CLI + **thêm log khi vứt char**
    (hiện `return` im lặng, E-2). Không đổi default → rủi ro merge thấp.
  - Issue: kèm `p67.pdf` / `p15.pdf` (đã có sẵn từ T3). **✅ Đã mở
    [funstory-ai/BabelDOC#615](https://github.com/funstory-ai/BabelDOC/issues/615)
    (2026-09-07)** — xem chi tiết ở G4. PR (a)/(b) ở trên **chưa** mở, mới dừng ở đề xuất trong
    thân issue #615 (đợi phản hồi maintainer trước khi bỏ công viết PR thật).
  Ghi rõ: **không được chờ upstream để đóng task** (giữ nguyên tinh thần G4).
- **P2.3 — `--translate-table-text`**: chỉ xét lại nếu P0.2-(iv) cho số đo tốt hơn rõ rệt.
  Không còn là ưu tiên sản phẩm sau khi V-3 bị bác bỏ (U2).
- **P2.4 — G5 known limitation trong PRD**, kèm số đo thật ở T3 + U2.
- **P2.5 — KHÔNG fork engine reflow.** ✅ Đồng ý tuyệt đối với Expert. Reflow đúng nghĩa = đẩy
  paragraph N+1 xuống theo chiều cao thật của N → dây chuyền toàn trang → đụng hình/box cố
  định/footer → phải tràn sang trang sau → **lệch số trang so với mục lục/index**. Đó là viết
  lại 1 engine dàn trang, không phải patch. Nếu sau P0–P1 văn xuôi vẫn vượt ngưỡng chấp nhận,
  thứ tự xét là: PR upstream (P2.2a) → monkey-patch có pin version (phương án cuối cùng, chỉ
  khi PR bị từ chối).

### U5. Khung "tam nan" — điểm Expert đúng mà T6 cũ nói chưa đủ rõ

✅ Đồng ý, và ghi nhận đây là đóng góp có giá trị nhất của phản biện. Khi text đích dài hơn
nguồn 20–40% mà khung giữ nguyên, phần dôi ra chỉ có 3 chỗ để đi: **(1) bóp font** (→ UX-E),
**(2) giãn khung** (→ phá layout, đẩy khối dưới, tràn trang), **(3) cắt/rút text** (→ rủi ro
nội dung). babeldoc chọn (1), và khi hết cách thì **cố ý vẽ tràn** (T-04) — đây là **quyết định
POLICY của một tool dùng chung**, không phải bug ngẫu nhiên.

Hệ quả với cách trình bày của T6 cũ: T6-G2c tuy có tự ghi "không sửa được lỗi, chỉ chặn giao
hàng lỗi", nhưng đặt nó ở vị trí "khuyến nghị hàng đầu" dễ khiến người đọc hiểu thành "làm gate
là xong". **Nói lại cho rõ**: gate là **thiết bị đo**, không phải fix. Nó đứng đầu P0 vì
**không có nó thì không A/B được bất kỳ patch nào** — chứ không phải vì nó giải quyết được
UX-A/B/E.

### U6. Rủi ro đã biết (theo dõi, không fix ngay)

| # | Rủi ro | Vì sao không fix ngay |
|---|--------|----------------------|
| RK-1 | `is_text_layout()` không chứa nhãn trần `table`; text vùng `table` chỉ thoát được nhờ `fallback_line` (U2-3). Nếu upstream bỏ/đổi `generate_fallback_line_layout_for_page`, **toàn bộ bảng sẽ ngừng được dịch trong im lặng** | Đã đo: hiện KHÔNG xảy ra (U2-4). Đã pin version (P0.3). Gate P0.1-e (bảo toàn số/đơn vị) sẽ bắt được nếu nó xảy ra về sau |
| RK-2 | T-09/T-10 (paragraph composition rỗng → log `"Unable to export paragraphs…"`) | Đã loại trừ trên dữ liệu này (T3-e); giữ nguyên trạng thái theo dõi |
| RK-3 | G1e overlay đặt text lên PDF đã qua `compress_pdf_images` (US-16) — thứ tự 2 bước phải cố định | Ghi vào spec P1.1: overlay chạy **sau** merge chunk, **trước** nén ảnh, để bước nén không đụng text mới thêm |

### U7. Escalate cho PM/user (không thuộc thẩm quyền Tech Lead)

✅ Đồng ý với Expert: đây là **quyết định sản phẩm**, phải do PM/user chốt rồi ghi vào PRD.
Tech Lead chỉ trình bày lựa chọn và hệ quả.

**E-1. Chính sách tam nan theo TỪNG loại phần tử.** Đề xuất của Tech Lead để PM duyệt:

| Loại phần tử | Chính sách đề xuất | Hệ quả người dùng nhìn thấy |
|--------------|-------------------|----------------------------|
| Văn xuôi 1 cột có khoảng trắng dưới | Cho phép **giãn khung xuống** trước, giữ font 100% | Khoảng cách giữa các khối thay đổi nhẹ |
| Box trang trí / ô bảng cỡ cố định | Bóp font tối đa tới **70%** (DoD-UX-03) rồi **FLAG**, KHÔNG bóp tới 0.1 | Một số box bị flag để QA sửa tay |
| Mục lục / index | KHÔNG bóp, KHÔNG giãn — ưu tiên **rút gọn tiêu đề mục** | Tên mục có thể ngắn hơn bản gốc |
| Khối chữ xoay | Overlay G1e giữ góc; không vừa thì bóp tới 70% rồi FLAG | Giữ được thiết kế nghiêng |

**E-2. Ngưỡng chấp nhận release.** DoD-UX-01/02/03 hiện là "chặn release" tuyệt đối. Với số đo
T3-a (trang văn xuôi thường cũng có 5 cặp chồng lấn), **giữ nguyên = không bao giờ release
được**. PM cần chốt ngưỡng định lượng, ví dụ "≤ 5% số trang bị flag ở mức nghiêm trọng".

**E-3. Review thủ công bắt buộc.** ✅ Đồng ý với Expert (5d): 3 lớp trang phải QA soi tay 100%
**bất kể gate nói gì** — 19 trang chữ xoay (danh sách ở T3-c), mọi trang có vùng nhãn `table`,
và mục lục/index. Ước tính ~40–60 trang — khả thi; 418 trang thì không. PM cần xác nhận QA có
ngân sách thời gian cho việc này.

### U8. Trạng thái verify (tổng hợp section này)

| Claim | Trạng thái |
|-------|-----------|
| V-1 backend babeldoc không render được góc xoay tuỳ ý | ✅ Verified — `pdf_creater.py:111-120`, `il_version_1.py:627-663` |
| V-2 pdf2zh không vứt chữ nghiêng nhẹ, nhưng cũng duỗi thẳng | ✅ Verified — `converter.py:244, 384` |
| V-3 bảng chưa từng được dịch | ❌ **BÁC BỎ** — `layout_parser.py:171-208` + `layout_helper.py:725-728, 844` + đo output production (2,7% ký tự không dấu; trang 63 đã dịch) |
| V-4 babeldoc latest = 0.6.4 | ✅ Verified — PyPI JSON, fetch 2026-09-07 |
| E-1 "giãn trước, bóp sau" khả thi + scale không bao giờ về 1.0 sau khi giãn | ✅ Verified — `typesetting.py:1017-1062, 1628-1660` |
| G1e `insert_text(morph=…)` xoay góc tuỳ ý + dấu tiếng Việt | ✅ Verified — spike chạy thật, PyMuPDF 1.28.2, `dir=(0.9816,−0.1908)` trùng khít khối gốc trang 67 |
| G1e fit text dài trong bbox nghiêng | ⚠️ `[UNVERIFIED]` — spike bắt buộc ở P1.1 (R5-02) |
| Nguyên nhân UX-D | ⚠️ `[UNVERIFIED]` — thí nghiệm P0.2 phải phân biệt mode-scale (T-07) vs gom nhầm paragraph (`--split-short-lines`) |
| pdf2zh có tốt hơn babeldoc trên 19 trang xoay không | ⚠️ `[UNVERIFIED]` — đo ở P0.2-(v) |
| `--translate-table-text` ảnh hưởng trang bảng | ⚠️ `[UNVERIFIED]` — đo ở P0.2-(iv); đã hạ ưu tiên sau U2 |

---

### Kết quả thí nghiệm A/B — P0.2 (2026-09-07, Dev)

**Cách chạy** (đúng spec U4/P0.2, không mock — Protocol 5 R5-03): gọi thẳng
`babeldoc`/`pdf2zh` CLI thật qua `asyncio.create_subprocess_exec`, dùng chung file gốc
`data/uploads/f88282bb-…_Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf` (418 trang,
xác nhận lại bằng PyMuPDF), cùng flag production (`--split-short-lines --short-line-split-factor
0.8`, `--openai-thinking disabled` cho DeepSeek, model `deepseek-v4-flash` — đúng giá trị đang
override trong bảng `settings` của DB, không phải default `deepseek-chat` trong code). Script
spike lưu tại
`/private/tmp/.../scratchpad/p02_experiment/run_experiment.py` (không phải code sản phẩm).

**Khoá cache**: chạy (i) 1-trang riêng lẻ cho cả 5 trang TRƯỚC để làm ấm cache, các lần sau
không truyền `--ignore-cache`. Ghi chú quan trọng phát hiện thêm: dù đã làm ấm cache, một vài
đoạn dịch vẫn đổi nhẹ giữa các lần gọi khác batch-context (ví dụ tiêu đề trang 7 dịch ra
"Mục lục" ở chế độ 1 trang nhưng "Nội dung" ở chế độ chunk, "Hai Chữ T: Nhiệt Độ" viết hoa khác
"Hai chữ T: Nhiệt độ") — tức cache của babeldoc không khoá được 100% biến LLM non-deterministic
khi ngữ cảnh batch xung quanh đoạn đó thay đổi (batch cùng 1 request gồm nhiều đoạn). Các so
sánh dưới đây vì vậy ưu tiên tín hiệu HÌNH HỌC (bbox, số block, overlap) hơn là tín hiệu câu chữ
chính xác.

**Cách bật debug JSON**: `--debug` CLI flag chỉ set `TranslationConfig.debug=True` (help text
"Use debug logging level" gây hiểu lầm — đã đọc source `main.py:694`/`high_level.py:916-1030`
để verify). Khi `debug=True`, JSON được ghi vào `working_dir` (không phải `--output`!),
`working_dir` mặc định là `~/.cache/babeldoc/working/<stem file input>/` nếu không truyền
`--working-dir` — **và bị GHI ĐÈ giữa các lần chạy cùng 1 file input** nếu không tách riêng.
Đã tự truyền `--working-dir <thư mục riêng theo config>` cho mỗi lần gọi để tránh mất dữ liệu.
Với `--max-pages-per-part`, `working_dir` của từng part bị `cleanup_part_working_dir()` xoá
NGAY sau khi part đó xong (`high_level.py:671`) — nên KHÔNG lấy được JSON debug per-part cho
cấu hình (iii); phải đối chiếu bằng cách đọc trực tiếp PDF output cuối (mono) thay vì JSON.

**Câu hỏi 1 — UX-D do mode-scale-theo-chunk (T-07) hay gom nhầm paragraph do
`--split-short-lines`?**

Đối chiếu đúng cặp đoạn PM từng thấy lỗi trong production ("4. Kỹ Thuật và Kỹ Năng Làm Bánh
Ngọt 172" / "Hai chữ T: Nhiệt độ", trang 7) qua `typsetting.json` (IL, toạ độ PDF-native
y-up) VÀ qua PDF output cuối (PyMuPDF, toạ độ top-left) ở cả 3 cấu hình — (i) 1 trang, (ii)
chunk 1-40 y hệt production, (iii) chunk 1-40 + `--max-pages-per-part 4`:

| Cấu hình | bbox heading | bbox sub-entry | Thứ tự |
|---|---|---|---|
| (i) 1 trang | (330.0,330.3)-(546.6,344.6) | (361.2,361.5)-(467.5,377.0) | heading TRÊN, sub-entry DƯỚI — ĐÚNG |
| (ii) chunk 1-40 | (330.0,330.3)-(546.6,344.6) | (361.2,361.4)-(469.6,377.8) | heading TRÊN, sub-entry DƯỚI — ĐÚNG |
| (iii) chunk + mpp4 | (330.0,330.3)-(546.6,344.6) | (361.2,361.4)-(469.6,377.8) | heading TRÊN, sub-entry DƯỚI — ĐÚNG |

**Kết quả bất ngờ**: KHÔNG tái hiện được hiện tượng UX-D cho đúng cặp đoạn này ở BẤT KỲ cấu
hình nào trong lần chạy này — bbox gần như giống hệt nhau giữa cả 3 cấu hình (heading giống
tuyệt đối, sub-entry lệch < 2pt do word-wrap khác 1 chữ). Điều này **không xác nhận** T-07 hay
`--split-short-lines` là biến quyết định cho CHÍNH cặp đoạn này ở lần chạy hiện tại — nhiều khả
năng lỗi PM thấy trong production (T3-f, "391 384" và cặp "Hai chữ T" nói trên) là sản phẩm của
1 lần gọi LLM cụ thể khác (tổ hợp câu chữ/độ dài dịch khác đủ để đẩy paragraph qua ngưỡng
overflow) — **không loại trừ T-07** (chỉ là không tái hiện được lần này), nhưng cũng không xác
nhận được. Giữ nguyên trạng thái `[UNVERIFIED]` cho câu hỏi "nguyên nhân UX-D", không nâng
thành kết luận.

Tuy vậy, khi quét TOÀN BỘ trang 7 bằng gate P0.1 (không chỉ 1 cặp), chồng lấn là RẤT LỚN và
đồng nhất giữa (ii)/(iii): **149 cặp overlap ở cả (ii) và (iii)** (so với **157** ở (i) — chênh
lệch do khác câu chữ dịch, không phải do vị trí). Trên TOÀN BỘ 40 trang của chunk 1-40, tổng số
cặp overlap là **410.898 (ii)** so với **411.832 (iii)** — cùng bậc độ lớn, 25/40 trang có
chênh lệch nhưng không theo chiều hướng nhất quán (một số trang giảm: trang 30 giảm 1074→723,
trang 18 giảm 1240→881; một số trang tăng: trang 27 tăng 184→345, trang 6 tăng 175→208). Số
liệu áp đảo này (hàng trăm nghìn cặp overlap/40 trang) đến từ rất nhiều block cực nhỏ/trùng lặp
gần như tuyệt đối (`fallback_line` trùng khít `plain text` ở tỉ lệ giao 1.0) — đây là hạn chế
đã biết của gate P0.1-a khi áp lên trang dày đặc block nhỏ (bảng/mục lục nhiều dòng ngắn): số
đếm thô bị "ngợp" bởi nhiễu hình học chứ không phản ánh đúng mức độ nghiêm trọng thực tế — ghi
nhận đây là điểm cần tinh chỉnh gate (lọc block quá nhỏ hoặc dedupe trùng khít) ở vòng sau,
KHÔNG sửa trong task này (ngoài scope P0.1 đã chốt).

**Câu hỏi 2 — `--max-pages-per-part 4` có cải thiện đáng kể không?**

**KHÔNG.** Trên cả 3 trang đo trực tiếp (7, 63, 67):

| Trang | Overlap (ii, mặc định) | Overlap (iii, mpp4) | Char count (ii) | Char count (iii) |
|---|---|---|---|---|
| 7 | 149 | 149 | — | — |
| 63 | 55 | 57 | 3.286 | 3.318 |
| 67 | 4.243 | 4.243 | 5.978 | 5.962 |

Trang 7 và 67: SỐ OVERLAP GIỐNG HỆT NHAU giữa (ii) và (iii) — `--max-pages-per-part 4` không
đổi gì đo được ở 2 trang này trong lần chạy này. Trang 63 chỉ lệch ±2 (nhiễu). Tổng thể 40
trang của chunk 1-40 cũng cùng bậc độ lớn (410.898 vs 411.832, xem Câu hỏi 1). **Kết luận**:
không có bằng chứng `--max-pages-per-part 4` cải thiện đáng kể trên bộ trang này — **P1.3
(G2b) KHÔNG nên implement** dựa trên số đo P0.2 này (đúng điều kiện đã chốt ở U4: "P1.3 chỉ
implement nếu P0.2 chứng minh" — P0.2 KHÔNG chứng minh).

**Câu hỏi 3 — `--translate-table-text` đổi gì trên trang bảng (63)?**

Gần như KHÔNG đổi gì: 117 block text (mặc định) so với 118 block (`--translate-table-text`),
3.286 ký tự so với 3.319 ký tự, 55 overlap so với 57 overlap — sample nội dung dịch giống hệt
nhau theo thứ tự block. Khớp với kết luận U2 (V-3 "bảng chưa từng được dịch" đã bị BÁC BỎ —
bảng ĐÃ được dịch qua cơ chế `fallback_line` mặc định, xem `layout_helper.py:725-728, 844`) —
`--translate-table-text` không mang lại giá trị đo được thêm trên đúng trang bảng này.
**Kết luận**: giữ nguyên quyết định U2/T6 — **không nâng ưu tiên P2.3**.

**Câu hỏi 4 — pdf2zh có đáng làm fallback cho 19 trang chữ xoay không?**

So sánh trực tiếp bằng chính gate P0.1 vừa xây, chạy trên CẢ HAI output (babeldoc chunk 39-80
và pdf2zh 5-trang) cho 3 trang xoay (15, 63, 67):

| Trang | Char count pdf2zh | Char count babeldoc | Overlap pdf2zh | Overlap babeldoc | Nội dung nghiêng còn không? |
|---|---|---|---|---|---|
| 15 (bảng quy đổi, xoay 20°) | 1.651 | 860 | 74 | 47 | pdf2zh: nhiều chữ hơn hẳn (babeldoc mất phần lớn, khớp T3-c "39/58 block mất"); chưa xác nhận có đúng nội dung "CONVERSION CHART" bằng regex đơn giản |
| 63 (Fiche de Technique, không xoay) | 1.374 | 3.286 | **0** | 55 | N/A (không xoay) — pdf2zh **0 overlap** trên trang bảng này, tốt hơn hẳn babeldoc |
| 67 (chú giải xoay -11°, "Disaccharide") | 3.631 | 5.978 | 65 | 4.243 | **pdf2zh GIỮ ĐƯỢC nội dung** (`"...một loại disaccharide..."`, `"Disaccharide"`, `"The word disaccharide is composed..."`) — babeldoc **MẤT TRẮNG** hoàn toàn (khớp T3-d) |

Kiểm tra trực tiếp góc xoay (`line["dir"]`) trên output pdf2zh trang 67: **`dir=(1.0, 0.0)`**
— tức pdf2zh **duỗi thẳng** khối chữ nghiêng (khớp đúng V-2 đã verify trước đó qua source
`converter.py:244,384`: "pdf2zh không vứt chữ nghiêng nhẹ nhưng cũng duỗi thẳng"). Đồng thời
phát hiện MỚI: nội dung bên trong khối đó ở pdf2zh bị **dịch DỞ DANG** — dòng đầu đã dịch sang
tiếng Việt, 3 dòng còn lại (bao gồm chính tiêu đề "Disaccharide") **vẫn nguyên văn tiếng Anh**
— tức pdf2zh không mất chữ hoàn toàn nhưng chất lượng dịch không đồng nhất trên khối này.

**Kết luận, có điều kiện**: pdf2zh **đáng cân nhắc làm fallback cho vấn đề MẤT NỘI DUNG** (UX-C)
trên trang chữ xoay — nó KHÔNG BAO GIỜ tạo ra "ô trắng" như babeldoc quan sát được trên cả 3
trang test (15/63/67), và trên trang 63 (bảng, không xoay) overlap = 0 tuyệt đối tốt hơn hẳn.
NHƯNG: (a) nó đánh đổi mất góc nghiêng thẩm mỹ (duỗi thẳng, đã biết trước ở V-2 — đây chính là
lý do project chọn babeldoc lúc đầu), (b) chất lượng dịch không đồng nhất trong 1 khối (phát
hiện mới, `[UNVERIFIED]` cần đo thêm mẫu lớn hơn trước khi kết luận đây là hiện tượng hệ thống
hay ngẫu nhiên 1 lần), và (c) trên trang 15, pdf2zh có overlap CAO HƠN babeldoc (74 so với 47)
— tức không phải lúc nào pdf2zh cũng thắng tuyệt đối. **Giữ nguyên roadmap U4/P1.1**: hướng
chính cho UX-C vẫn là G1e (overlay giữ góc nghiêng, đã spike khả thi ở U3); pdf2zh cho 19 trang
xoay **chỉ nên là phương án dự phòng cuối** nếu spike fit-text G1e ở P1.1 thất bại — đúng thứ tự
đã chốt ở P1.1, số đo P0.2-(v) này KHÔNG đủ mạnh để đảo ngược quyết định đó (mới đo 3/19 trang,
1 lần chạy, chưa loại trừ non-determinism của LLM).

**Thời gian chạy thật** (tham khảo cho ước tính chi phí, KHÔNG phải benchmark hiệu năng
nghiêm ngặt — máy Dev, không kiểm soát tải hệ thống): 1 trang babeldoc ~42-51s; chunk 40 trang
babeldoc ~176-255s (~4-6s/trang); pdf2zh 5 trang riêng lẻ (không liền mạch, `--pages
"7,13,15,63,67"`) ~427s tổng — dùng cùng `--thread 8`/`--pool-max-workers 8` cho công bằng.

**File/artifact của thí nghiệm** (không commit vào repo, chỉ tham chiếu): script + toàn bộ
output/debug JSON của 11 lần chạy lưu tại
`/private/tmp/claude-501/.../scratchpad/p02_experiment/` (`run_experiment.py`,
`results_summary.json`, `config_i/` .. `config_v/`) — PM/QA cần xem lại số đo thô có thể yêu
cầu Dev export lại vào `tests/fixtures/babeldoc/` theo đúng Protocol 5 mục 3 (golden file) nếu
muốn dùng làm fixture test lâu dài; hiện tại đây là dữ liệu spike một lần, không phải fixture
đã chốt.

---

### Bug #6 — Root Cause & Phương án fix: chữ xoay bị mất góc trong OCR bridge (2026-09-07)

**Người viết**: Tech Lead (Opus). **Trạng thái**: Đánh giá/đề xuất SƠ BỘ — chờ Domain Expert
phản biện + PM/user quyết định. **Không có code nào được viết trong task này.**

**Đầu vào**: `docs/test-report.md` mục "QA Vòng 6" — Bug #6: overlay chữ xoay (P1.1/G1e) không
bao giờ kích hoạt cho job `pdf_scan` + `babeldoc`; `layout_qa_findings` = 0 hàng (im lặng hoàn
toàn). QA đã đánh dấu `[CHƯA VERIFY]`: "MinerU 3.4.5 có API/field nào khác chứa góc không?".
Task này trả lời DỨT ĐIỂM câu hỏi đó theo Protocol 5 R5-01/R5-02.

#### 6.13.1 — Nguồn xác thực (Protocol 5 R5-01)

Bản đã cài: `mineru --version` → **3.4.5**, đường dẫn
`/Users/hieutt/.local/share/uv/tools/mineru/lib/python3.12/site-packages/mineru/`.
Toàn bộ trích dẫn dưới đây là **đọc trực tiếp source code của bản đã cài này** (không phải trí
nhớ, không phải suy đoán), cộng thêm 1 nguồn doc chính thức đã fetch thật để đối chiếu chéo.

| # | Nguồn | Nội dung xác thực |
|---|---|---|
| S-M1 | `mineru/model/ocr/pytorch_paddle.py:203-225, 242-291` | Detector (DBNet, `self.text_detector`) trả `dt_boxes` dạng **poly 4 điểm** — có mang thông tin góc. `ocr(det=True, rec=False)` trả thẳng poly (`tmp_res = [box.tolist() for box in dt_boxes]`). |
| S-M2 | `mineru/utils/ocr_utils.py:276-297` (`merge_det_boxes`), `211-236` (`update_det_boxes`) | Poly nghiêng (`calculate_is_angle()` = True) được **cố ý tách riêng** vào `angle_boxes_list` và bỏ qua bước gộp/làm phẳng — góc **vẫn sống** ở tầng này. Comment gốc của tác giả (pytorch_paddle.py:218): "merge_det_boxes 和 update_det_boxes 都会把poly转成bbox再转回poly，因此需要过滤所有倾斜程度较大的文本框". |
| S-M3 | **`mineru/utils/ocr_utils.py:399-410`** | **Điểm mất góc — chốt.** `if calculate_is_angle(poly):` → poly nghiêng bị **thay bằng 1 hình chữ nhật thẳng trục** dựng quanh **trọng tâm** poly: `x_center/y_center` = trung bình 4 đỉnh, `new_height` = trung bình 2 cạnh dọc, `new_width = p3[0] - p1[0]`. Góc bị **vứt bỏ có chủ đích**, không lưu ở đâu. |
| S-M4 | `mineru/utils/ocr_utils.py:391-392` | Dòng comment chết `# average_angle_degrees = calculate_angle_degrees(box_ocr_res[0])` — hàm `calculate_angle_degrees` **không còn tồn tại** trong bản 3.4.5 (`grep -rn "calculate_angle_degrees"` chỉ khớp đúng dòng comment này). Tức là tác giả từng tính góc rồi **bỏ hẳn**. |
| S-M5 | `mineru/utils/ocr_utils.py:418-432` | `ocr_item` cuối cùng chỉ có `{"label","bbox","score","text"}` — `bbox` qua `normalize_to_int_bbox` (`mineru/utils/bbox_utils.py:7-32`: lấy min/max, luôn ra 4 số thẳng trục). **Không có field góc nào.** |
| S-M6 | `mineru/backend/pipeline/batch_analyze.py:788, 832` và `mineru/backend/hybrid/hybrid_analyze.py:212, 285` | **MỌI** nhánh OCR (batch và single, pipeline và hybrid) đều đi qua đúng `get_ocr_result_list()` ở S-M3. Không có đường vòng nào giữ được poly. |
| S-M7 | `mineru/backend/vlm/vlm_magic_model.py:54, 225`; `mineru/backend/hybrid/hybrid_analyze.py:357-366` (`_normalize_medium_vlm_angle`), `437` | Backend **VLM/hybrid** CÓ field `angle` trong block — nhưng bị chuẩn hoá cứng: `if normalized_angle in {0, 90, 180, 270}: return normalized_angle; return 0`. Nguồn của nó là **table orientation classifier** (`AtomicModel.TableOrientationCls`, dòng 437) — tức "bảng bị xoay ngang/ngược", KHÔNG phải góc nghiêng tuỳ ý. |
| S-M8 | Doc chính thức, fetch thật 2026-09-07: https://opendatalab.github.io/MinerU/reference/output_files/ | Xác nhận chéo S-M7: chỉ backend VLM sinh field `angle`, giá trị giới hạn trong `{0, 90, 180, 270}`; `middle.json`/`model.json` của backend **pipeline** (backend app đang dùng, `MinerURunner(backend="pipeline")`) **không có** field angle. |
| S-M9 | `mineru/utils/ocr_utils.py:453-513` (`get_rotate_crop_image` → `get_rotate_crop_image_for_text_rec`), gọi tại `pytorch_paddle.py:276` | Crop để nhận dạng chữ được **warp phối cảnh về ngang** (rectify) trước khi đưa vào `text_recognizer`. Đây là lý do MinerU **đọc đúng nội dung** chữ nghiêng nhưng trả toạ độ ngang. |

#### 6.13.2 — Trả lời dứt điểm câu `[CHƯA VERIFY]` của QA

**VERIFIED — MinerU 3.4.5 KHÔNG cung cấp góc xoay tuỳ ý qua bất kỳ API/config/output nào.**
Cụ thể, 3 mệnh đề con, mỗi cái có nguồn:

1. **Không phải "MinerU không tính được góc"** — detector DBNet của nó trả poly 4 điểm có góc
   thật, và MinerU còn có hàm `calculate_is_angle()` nhận biết poly nghiêng (S-M1, S-M2).
2. **Giả thuyết "góc bị tiêu thụ ở bước rectify" của PM là ĐÚNG MỘT PHẦN, nhưng không phải cơ
   chế chính** (đây là khả năng PM yêu cầu loại trừ): góc quả thật bị tiêu thụ ở
   `get_rotate_crop_image` để nhận dạng chữ (S-M9) — nhưng ngay cả nếu bỏ qua bước rectify,
   góc vẫn sẽ mất, vì có **một bước làm phẳng riêng, tường minh, có chủ đích** ở
   `get_ocr_result_list` (S-M3) áp lên chính poly gốc (không phải lên bản đã rectify). Ma trận
   rectify KHÔNG được lưu lại ở đâu (S-M9 tạo `img_crop` rồi bỏ ma trận). ⇒ **Không có "ma trận
   rectify nội bộ để đọc lại"** — hướng fix "moi lại rectify matrix" bị **LOẠI**.
3. **Không có cờ/env/backend nào bật lại góc**: đã liệt kê toàn bộ `MINERU_*` env của bản 3.4.5
   (`grep -rhoE "MINERU_[A-Z_]+"`, 40 biến) — không biến nào liên quan góc/skew/deskew.
   Backend `vlm`/`hybrid` có `angle` nhưng lượng tử hoá về `{0,90,180,270}` và nguồn là bộ phân
   loại hướng BẢNG (S-M7, S-M8) ⇒ **không dùng được cho góc -11°**. Chuyển sang backend VLM
   **KHÔNG** giải quyết Bug #6.

**Hệ quả kiến trúc**: `middle.json` là **API công khai duy nhất** app đang tiêu thụ, và nó
**vĩnh viễn** không mang góc cho backend pipeline. Muốn có góc, app **bắt buộc phải tự tính**
(hoặc gọi tầng dưới `middle.json`). Đây không phải thiếu sót cấu hình — là thiết kế của MinerU.

**Điểm phụ nhưng quan trọng cho mọi phương án fix** (VERIFIED, S-M3): với dòng chữ nghiêng,
bbox MinerU trả về **KHÔNG phải bounding box của poly**, mà là 1 **dải ngang mỏng đi qua trọng
tâm** dòng chữ (cao = chiều cao chữ thật, rộng = bề rộng ngang của poly). Nghĩa là:
- (a) `_insert_invisible_text` hiện tại chèn chữ vô hình vào đúng dải mỏng đó — lệch khỏi vệt
  mực thật, nhưng vẫn nằm ở giữa nó (chấp nhận được cho mục đích "cầu nối để dịch").
- (b) **Chỉ cần biết thêm 1 số vô hướng θ** là tái dựng được hình bình hành thật:
  tâm = tâm bbox, chiều cao = `y1-y0`, chiều dài = `(x1-x0)/cos θ`, xoay quanh tâm góc θ.
  Đây là điều làm phương án (A) rẻ hơn nhiều so với cảm giác ban đầu.

#### 6.13.3 — Các phương án

| Mã | Phương án | Cách làm | Effort | Rủi ro | Tự tin |
|---|---|---|---|---|---|
| **A** | App tự đo góc trên ảnh raster, bổ sung vào bridge | Module mới `src/preprocess/skew_probe.py`: render trang bằng PyMuPDF `get_pixmap()`, với MỖI span bbox của `middle.json` cắt vùng (nới rộng theo 6.13.2-a), nhị phân hoá, đo θ bằng **projection-profile** (quét θ ∈ [-20°, +20°], chọn θ tối đa hoá phương sai tổng theo hàng). Truyền θ vào `_insert_invisible_text` → `insert_text(..., morph=(pivot, Matrix(-θ)))` + tái dựng hình học theo 6.13.2-b. Overlay P1.1 sau đó chạy **không cần sửa dòng nào**. | **Cao** (~2-3 ngày: 1 spike đo độ chính xác + 1 increment Dev + QA live E2E) | **Trung bình-cao** | Cơ chế đo: `assumed` (chưa spike). Hình học tái dựng: `verified` (S-M3). |
| **A′** | Như A nhưng **chỉ để FLAG**, không đổi hình học | Cùng module `skew_probe.py`, cùng θ — nhưng θ **không** đi vào `insert_text`; chỉ dùng để ghi `layout_qa_findings` ("trang N có K dòng nghiêng ~θ°, overlay không khả dụng cho `pdf_scan`, cần soát tay"). | **Thấp-trung bình** (~0.5-1 ngày) | **Thấp** (không đụng hình học output, chỉ thêm hàng DB) | Như A cho phần đo; phần ghi flag `verified` (đã có sẵn `LayoutQaFindingData`) |
| **B** | Chấp nhận known-limitation, FLAG mức job | Ghi known-limitation vào PRD; `JobOrchestrator` ghi **1 finding cho mỗi job** `pdf_scan` + `babeldoc`: "nhánh scan không phát hiện được chữ xoay — soát tay 100% trang". Không đo góc. | **Rất thấp** (~2 giờ) | **Thấp**, nhưng **nhiễu cao** (mọi job scan đều bị flag, kể cả job không có chữ xoay → nguy cơ "flag fatigue" làm mất tác dụng chính U7-E3) | `verified` |
| **C** | Tự xoay ảnh trước khi gửi MinerU | Bị **LOẠI**. Bài toán con gà-quả trứng (phải biết θ trước mới xoay được → nếu đã biết θ thì đã là phương án A), và MinerU vẫn rectify từng dòng ở tầng crop (S-M9) nên xoay cả trang không giữ được gì. | — | — | `verified` (S-M9, S-M3) |
| **D** | Đổi engine `pdf_scan` sang pdf2zh | Bị **LOẠI cho mục tiêu giữ góc**: đã đo ở P0.2 câu 4 — pdf2zh cũng **duỗi thẳng** (`dir=(1.0,0.0)`), chỉ hơn ở chỗ không mất nội dung. Nhưng nhánh `pdf_scan` **đã không mất nội dung** (QA Vòng 6 mục 4: 3.310 ký tự tiếng Việt đúng nghĩa) ⇒ đổi engine không mua được gì, lại mất các ưu điểm khác của babeldoc. | — | — | `verified` (P0.2 câu 4, đo thật) |
| **E** | Gọi thẳng detector của MinerU ngoài luồng | Chạy subprocess bằng chính interpreter của MinerU (`~/.local/share/uv/tools/mineru/bin/python`) gọi `PytorchPaddleOCR.ocr(img, det=True, rec=False)` → nhận poly 4 điểm **còn nguyên góc** (S-M1), match với bbox `middle.json` theo trọng tâm, suy ra θ. Chính xác hơn A (dùng đúng model đã tải sẵn, không cần dep mới nặng). | **Cao** (~3-4 ngày) | **Cao** — phụ thuộc **API nội bộ** của MinerU (không phải API công khai), Protocol 5 mục 5 bắt verify lại toàn bộ mỗi lần nâng version; chạy model lần 2 → tăng thời gian job đáng kể; ghép venv lạ vào runtime app | Poly có góc: `verified` (S-M1). Chi phí/độ ổn định: `assumed` |

**Ghi chú dependency cho A/A′**: app **chưa có** `numpy` lẫn `cv2` (`pyproject.toml` dòng 7-23;
`uv run python -c "import numpy"` → `ModuleNotFoundError`). Projection-profile trên vùng crop đã
hạ mẫu (≤200px bề rộng, ~13-27 góc thử) chạy được bằng **Python thuần + PyMuPDF `Pixmap`**, không
cần dep mới — `assumed`, phải đo trong spike; nếu quá chậm thì thêm `numpy` (nhẹ), **không** thêm
`opencv`.

#### 6.13.4 — Một rủi ro ẩn của phương án A mà Domain Expert cần soi kỹ

Nếu A thành công (bridge mang chữ vô hình ĐÃ xoay), hành vi babeldoc trên nhánh `pdf_scan` sẽ
**đổi**: hiện tại babeldoc dàn khối chữ đó thành hộp ngang (QA Vòng 6 mục 4); khi input đã
nghiêng, nhiều khả năng babeldoc sẽ **vứt bỏ** khối đó như nó vẫn làm với `pdf_digital` (T3-d,
P0.2) → chừa chỗ trống cho overlay P1.1 điền vào — tức nhánh `pdf_scan` **hội tụ về đúng nhánh
`pdf_digital` đã PASS**. Đây là kịch bản mong muốn, nhưng là **`[UNVERIFIED]` — assumed**, phải
là câu hỏi ĐẦU TIÊN của spike A. Nếu babeldoc **vẫn** vẽ hộp ngang, A sẽ tạo ra **chữ đè chữ**
(overlay nghiêng chồng lên hộp ngang của babeldoc) — tệ hơn hiện trạng — và khi đó A cần thêm
1 bước xoá/che vùng babeldoc đã vẽ (`page.add_redact_annot`), làm effort/rủi ro tăng thêm một
bậc. `overlay_rotated_text()` hiện **chỉ vẽ, không xoá** (`_draw_block`,
`rotated_text_overlay.py:367-389`) — `verified`.

#### 6.13.5 — Đề xuất SƠ BỘ của Tech Lead

**Trả lời câu hỏi cốt lõi của PM ("đào sâu sửa tiếp hay chấp nhận known-limitation"):
CHẤP NHẬN known-limitation cho hình học, NHƯNG BẮT BUỘC sửa phần FLAG — cụ thể là phương án
A′, không phải B.**

Lý do (theo thứ tự sức nặng):

1. **Ưu tiên sai đối tượng nếu làm A ngay**: ví dụ động lực của toàn bộ roadmap P1.1 (trang 67,
   khối "Disaccharide" nghiêng -11°) nằm trên nhánh **`pdf_digital`** — nhánh này **đã PASS,
   verify sống, góc khớp < 0.01°** (QA Vòng 6 mục 3). Nhánh `pdf_scan` có chữ xoay hiện là
   trường hợp **giả định**, chưa có tài liệu thật nào trong corpus chứng minh nó xảy ra. Đầu tư
   2-4 ngày + rủi ro trung bình-cao cho 1 nhánh chưa có bằng chứng nhu cầu là sai thứ tự — đúng
   tinh thần kỷ luật đã áp dụng khi **bác bỏ P1.3** ở P0.2 ("chỉ implement nếu số đo chứng minh").
2. **Thiệt hại thực tế là thẩm mỹ, không phải nội dung**: QA Vòng 6 xác nhận nội dung dịch
   **không mất** trên nhánh scan (3.310 ký tự tiếng Việt đúng nghĩa). Đây là mức nghiêm trọng
   khác hẳn Bug #5 (mất trắng nội dung).
3. **Nhưng phần "im lặng" thì KHÔNG được chấp nhận** — đây là chỗ tôi **không** đồng ý với việc
   chỉ ghi known-limitation rồi thôi. Hệ thống đang **báo sai** rằng không có trang nào cần soi,
   trong khi chính sách U7-E3 tự đặt ra là "soát tay bắt buộc 100% cho mọi trang có chữ xoay".
   Im lặng có hệ thống nguy hiểm hơn lỗi thẩm mỹ.
4. **Chọn A′ chứ không B**, vì B (flag mức job) sẽ flag **mọi** job scan kể cả job không có chữ
   xoay → flag fatigue làm hỏng chính cơ chế U7-E1/U7-E3 mà nó định cứu. A′ flag **đúng trang
   có chữ nghiêng thật**.
5. **A′ là bước 1 của A, không phải ngõ cụt**: cùng module `skew_probe.py`, cùng θ. Nếu sau này
   corpus thật xuất hiện tài liệu scan có chữ xoay (bằng chứng nhu cầu), nâng A′ → A chỉ còn là
   nối θ vào `insert_text(morph=...)` + trả lời câu hỏi `[UNVERIFIED]` ở 6.13.4 — phần đo góc,
   phần khó và rủi ro nhất, đã xong và đã chạy thật trong production suốt thời gian đó (tức là
   **đã tự tích luỹ dữ liệu độ chính xác thật** thay vì phải spike mù).

**Giải pháp cụ thể đề xuất (A′)** — để Dev không phải đoán:

- **Module mới** `src/preprocess/skew_probe.py`, hàm
  `estimate_span_skew_deg(page: fitz.Page, bbox, *, max_abs_deg=20.0, step_deg=1.0) -> float | None`.
  Render **một lần mỗi trang** (`page.get_pixmap(dpi=150, colorspace=fitz.csGRAY)`), cắt vùng
  bbox **nới rộng dọc theo `(x1-x0) * sin(max_abs_deg)`** (bắt buộc, vì bbox MinerU là dải mỏng
  qua trọng tâm — 6.13.2-a), nhị phân hoá theo ngưỡng Otsu đơn giản, quét θ và chọn θ tối đa hoá
  phương sai của projection profile. Trả `None` khi tín hiệu yếu (tránh dương tính giả).
- **Ngưỡng**: coi là "nghiêng" khi `|θ| >= 3.0°` (dưới ngưỡng này là skew scan bình thường, không
  phải chữ xoay có chủ đích) — con số này **`[UNVERIFIED]`, phải hiệu chỉnh bằng fixture thật**
  (`tests/fixtures/babeldoc/rotated_text_p67_source.pdf` raster hoá 200 DPI, ground truth
  -10.9999°, đã có sẵn từ QA Vòng 6) trước khi chốt.
- **Điểm nối (R6-01, khai báo lineage tường minh)**: gọi trong `searchable_pdf.py` ngay tại vòng
  lặp đã có sẵn qua các span của `middle.json` (nơi `_collect_text_spans()` trả về), **cùng lúc**
  với việc dựng bridge — không thêm lần render trang thứ 2. Kết quả θ **không** đi vào
  `_insert_invisible_text` ở giai đoạn A′; nó đi vào `MinerUResult`/kết quả bridge dưới dạng
  danh sách `(page_number, bbox, angle_deg)`, rồi `JobOrchestrator` chuyển thành
  `LayoutQaFindingData` với lý do `"rotated_text_scan_unsupported"`.
- **Test bắt buộc (R6-02)**: assert **giá trị θ cụ thể** đo được từ fixture raster hoá (sai số
  cho phép ±1.5°) và assert **số hàng `layout_qa_findings` > 0** cho đúng job `pdf_scan` fixture
  đó — không chấp nhận `assert_called()`.
- **Không đụng** `rotated_text_overlay.py` (module đó ĐÚNG, QA đã verify sống ở nhánh digital).
- **PRD**: ghi known-limitation tường minh — "overlay giữ góc chữ xoay chỉ hỗ trợ `pdf_digital`;
  với `pdf_scan`, hệ thống **phát hiện và FLAG** trang có chữ xoay để soát tay, nhưng **không**
  tái tạo góc — nguyên nhân gốc nằm ở MinerU (6.13.1 S-M3), không sửa được từ phía app mà không
  tự đo góc lại."

**Việc cần làm ngay, độc lập với mọi phương án** (đã được QA nêu ở test-report mục 8, tôi tán
thành và nâng lên thành hạng mục kiến trúc): `src/api/main.py` **chưa cấu hình logging handler**
nào cho logger `src.*` ⇒ mọi `logger.warning(..., exc_info=True)` trong các nhánh best-effort
(bao gồm nhánh nuốt exception của `overlay_rotated_text()` tại `job_orchestrator.py:533-539`)
**im lặng hoàn toàn** trong production. Đây là **điều kiện khiến Bug #6 khó phát hiện** và sẽ
khiến bug tiếp theo cũng khó phát hiện y hệt. Đề xuất tách 1 task riêng, ưu tiên cao hơn cả A′.

**Trạng thái**: Đề xuất sơ bộ — chờ Domain Expert (Fable) phản biện độc lập, sau đó PM/user
quyết định. Không tự chuyển sang implement.

---

### Bug #6 — Final Decision sau phản biện Domain Expert (2026-09-07)

**Người viết**: Tech Lead (Opus). **Trạng thái**: QUYẾT ĐỊNH CUỐI của Tech Lead — thay thế mục
6.13.5 (đề xuất sơ bộ) ở phần trên. Vẫn **không có code nào được viết trong task này**. Có 2 câu
hỏi escalate lên PM/user ở V7.

**Đầu vào**: phản biện độc lập của Domain Expert (Fable), kèm spike thật Expert tự chạy. Toàn bộ
mục này chỉ ghi những gì **tôi (Tech Lead) tự chạy lại / tự đọc lại source được**, không nhận
kết quả của Expert như dữ kiện.

#### V1. Kết quả TỰ VERIFY lại các claim của Expert (Protocol 5 R5-01)

Phiên bản đã cài dùng cho mọi phép đo dưới đây: MinerU **3.4.5**
(`/Users/hieutt/.local/share/uv/tools/mineru/`), babeldoc **0.6.4**
(`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`,
`babeldoc.__version__` in ra `0.6.4`), PyMuPDF của venv app.

| # | Claim của Expert | Kết quả tự verify | Nguồn |
|---|---|---|---|
| V-1 | `PytorchPaddleOCR.ocr(img, det=True, rec=False)` trả poly **còn góc** | **XÁC NHẬN — tự chạy lại, tái hiện được.** Render `tests/fixtures/babeldoc/rotated_text_p67_source.pdf` ở 200 DPI (1800×2175 px) rồi gọi detector bằng chính interpreter MinerU: **88 poly**, trong đó **19 poly có \|θ\| ≥ 3°**. Loại 1 poly nhiễu (`score=0.51`, text `"0"`) bằng ngưỡng `score ≥ 0.8` → còn **18 dòng, θ ∈ [-11.40°, -10.29°]**. | Spike tự chạy, script `det_spike.py`, output `det_probe_p67.json` |
| V-2 | Độ chính xác góc | **XÁC NHẬN, thậm chí tốt hơn Expert báo.** Ground truth đo bằng PyMuPDF trên chính fixture: 17 dòng có `dir` = **-11.0°** (và 75 dòng 0°). Sai số **median ≈ 0.1°**, **max 0.40°** trên 18 dòng (Expert báo ≤0.7°). | So sánh trực tiếp GT PyMuPDF vs poly detector |
| V-3 | `ocr(det=True, rec=True)` **vẫn** giữ poly còn góc (kèm text) ⇒ điểm làm phẳng nằm ở tầng backend, không nằm trong class detector | **XÁC NHẬN bằng cả 2 cách.** (a) Chạy thật: 88 item, 19 item nghiêng, text đọc đúng (`"Disaccharide"`, `"The word disaccharide is composed of the prefix di"`, ...), score 0.99-1.00. (b) Đọc source: `pytorch_paddle.py:196-201` (`tmp_res = [[box.tolist(), res] ...]`) trả thẳng `dt_boxes` chưa qua `get_ocr_result_list`. | Spike + `pytorch_paddle.py:190-291` |
| V-4 | Chi phí thời gian của (E) | **XÁC NHẬN và RẺ HƠN cả số Expert đo.** Trên máy này: init model **0.73s**; `det` only **0.36s/trang**; `det+rec` **2.00s/trang**. ⇒ 400 trang scan ≈ **2,4 phút** (det-only) hoặc **~13 phút** (det+rec). *Lưu ý*: đây là 1 lần chạy, không kiểm soát tải máy — dùng để so sánh bậc độ lớn, không phải benchmark. | Spike tự chạy |
| V-5 | babeldoc `il_creater` vứt glyph **deterministic theo ma trận ký tự**, không phân biệt `render_mode` | **XÁC NHẬN.** `il_creater.py:968-974` (`on_lt_char`, bản 0.6.4): `rotation_angle = get_rotation_angle(char.matrix)`; `if not (-0.1 <= rotation_angle <= 0.1 or 89.9 <= rotation_angle <= 90.1): return`. `get_rotation_angle` = `atan2(b, a)` của ma trận (`il_creater.py:390-398`). `grep -n "render_mode"` trên toàn file → **0 kết quả** ⇒ chữ vô hình (`render_mode=3`) bị xử lý y hệt chữ thường. | Đọc source bản đã cài |
| V-6 | "Không có paragraph thì không có ô nền trắng" | **XÁC NHẬN, và mạnh hơn Expert nói.** `paragraph_finder.py:89-121` (`add_text_fill_background`) lặp `for paragraph in page.pdf_paragraph` → không paragraph thì không sinh `PdfRectangle` nào. Thêm nữa: `grep -rn "fill_background=True"` trên **toàn bộ package babeldoc** chỉ khớp **đúng 1 dòng** (`paragraph_finder.py:117`) ⇒ đây là **nơi DUY NHẤT** ô nền trắng được sinh ra, không có đường vòng nào khác. | Đọc source + grep toàn package |

#### V2. Rủi ro 6.13.4 ("2 lớp chữ đè nhau") — GỠ `[UNVERIFIED]`, nhưng KHÔNG gỡ hết

**Đồng ý với Expert**: với dải góc của bài toán thật (\|θ\| khoảng 3°-30°), rủi ro "2 lớp chữ đè
nhau" **KHÔNG xảy ra** — `verified` bằng V-5 + V-6. Chuỗi nhân quả: glyph xoay bị `on_lt_char`
`return` sớm → không vào IL → không có `pdf_paragraph` → `add_text_fill_background` không sinh
`PdfRectangle` nào → **không có hộp ngang nào để đè lên**. Đây đúng là cơ chế đã làm nhánh
`pdf_digital` "chừa chỗ trống" mà overlay P1.1 đang tận dụng (đã PASS QA Vòng 6).

**Bổ sung một điểm cả tôi lẫn Expert đều chưa nêu** (`verified`, V-5): điều kiện vứt glyph có
**hai** khoảng an toàn, không phải một — `-0.1..0.1` **và `89.9..90.1`**. Nghĩa là với chữ xoay
**≈ ±90°** (nhãn trục dọc trong biểu đồ, chữ chạy dọc mép bảng — rất phổ biến trong sách kỹ
thuật), babeldoc **GIỮ** glyph, **dựng** paragraph, và **vẽ** ô nền trắng ⇒ trong dải góc đó
rủi ro "2 lớp chữ đè nhau" là **CÓ THẬT**. Ghi lại đây để bất kỳ ai làm Phase 2 sau này không
đọc kết luận "KHÔNG xảy ra" ở trên một cách quá rộng.

⇒ **Sửa 6.13.4**: `[UNVERIFIED]` → **`verified: KHÔNG xảy ra với \|θ\| nằm ngoài lân cận 0° và
90°; CÓ xảy ra với θ ≈ ±90°`** (nguồn: `il_creater.py:968-974`, `paragraph_finder.py:89-121`,
grep `fill_background=True` toàn package babeldoc 0.6.4).

#### V3. Rủi ro MỚI Expert nêu ("raster tiếng Anh còn nguyên dưới overlay") — ĐÚNG HƯỚNG, SAI MỨC ĐỘ

Expert cảnh báo: nếu Phase 2 chỉ nối θ vào `insert_text` mà không thêm bước che nền, chữ tiếng
Việt sẽ **in đè trực tiếp lên pixel tiếng Anh gốc → "không đọc được gì cả, tệ hơn hiện trạng"**,
và đề xuất thêm một bước vẽ tứ giác xoay che nền (~0.5 ngày), lấy mẫu màu nền từ pixmap.

**Tôi BÁC BỎ MỘT PHẦN — đo được, không phải suy đoán:**

1. **Bước che nền KHÔNG phải là bước còn thiếu — nó ĐÃ TỒN TẠI trong code.**
   `src/preprocess/searchable_pdf.py:113-125` đã có sẵn vòng lặp whiteout 2 pha: với **mọi**
   span, vẽ `page.draw_rect(..., fill=(1,1,1), overlay=True)` với `whiteout_padding=1.5pt`
   **trước** khi chèn chữ vô hình (comment trong code nói rõ vì sao phải tách 2 pha). Nhánh này
   vốn **chỉ chạy cho `pdf_scan`** (`build_searchable_pdf` chỉ được gọi ở cầu nối OCR), nên điều
   kiện "chỉ bật cho `pdf_scan`" Expert đề xuất cũng đã tự thoả mãn.
2. **Mức độ hở thực tế: 5,5%, không phải 100%.** Tôi mô phỏng đúng công thức làm phẳng của MinerU
   (`ocr_utils.py:399-410`) lên chính 18 poly nghiêng detector trả về ở V-1, dựng lại dải whiteout
   ngang + padding 1.5pt, rồi đo tỷ lệ diện tích vệt mực nghiêng **không** được che (lấy mẫu lưới
   1px): **5,5% tổng diện tích**. Phân bố **rất lệch**: 15/18 dòng ở giữa khối hở **≤ 2,2%** (các
   dải ngang của những dòng kề nhau chồng lấn và che hộ nhau), toàn bộ phần hở dồn vào **các dòng
   rìa khối**: 17,8% (dòng tiêu đề `"What's in a word?"`), 11,2% và **28,5%** (dòng cuối
   `"blocks of the sucrose molecule."`).
   ⇒ Kết quả thật sẽ là **vệt chữ tiếng Anh sót lại ở mép trên/mép dưới khối**, không phải "không
   đọc được gì cả". Nói cách khác **rủi ro là THẬT và phải fix, nhưng nó không đảo ngược so sánh
   với hiện trạng** — luận điểm "tệ hơn hiện trạng" của Expert là **quá mạnh so với số đo**.
3. **Hệ quả về thiết kế Phase 2** (rẻ hơn Expert ước tính): việc cần làm **không phải** thêm một
   module che nền mới, mà là **đổi hình dạng whiteout đã có**: trong đúng vòng lặp pha 1 của
   `searchable_pdf.py:113-125`, khi span có θ, thay `draw_rect` bằng tứ giác xoay
   (`Shape.draw_polygon` + `finish(fill=(1,1,1))`) dựng từ poly gốc + padding. **Không cần lấy
   mẫu màu nền** như Expert đề xuất: production hiện đã tô **trắng thuần** cho 100% span của mọi
   trang scan và QA Vòng 6 đã PASS ⇒ đổi màu tô là thay đổi hành vi ngoài phạm vi Bug #6, nếu
   muốn thì tách task riêng.
4. **`[CHƯA VERIFY]` mới, phải là câu hỏi ĐẦU TIÊN của Phase 2**: các hình chữ nhật whiteout do
   cầu nối vẽ có **sống sót** qua bước babeldoc dựng lại trang hay không (babeldoc chỉ vứt glyph,
   nhưng tôi **chưa** đo trực tiếp việc nó giữ nguyên vector rect của trang gốc). Bằng chứng gián
   tiếp ủng hộ: QA Vòng 6 không báo hiện tượng chữ tiếng Anh lộ ra trên toàn trang scan — nếu
   whiteout bị mất thì **mọi** span (kể cả 75 dòng ngang) đều sẽ lộ chữ gốc, khó bỏ sót. Nhưng
   suy luận gián tiếp không thay thế phép đo.

#### V4. Đánh giá lại phương án (E) — TÔI RÚT LẠI đánh giá cũ ở 6.13.3

Ở 6.13.3 tôi chấm (E) là "effort cao (~3-4 ngày), rủi ro cao, chạy model lần 2 → tăng thời gian
job đáng kể". **Đánh giá đó dựa trên phỏng đoán chưa đo, và số đo của tôi ở V1 bác bỏ nó**:

| Tiêu chí | (A) projection-profile tự viết (đánh giá cũ) | (E) gọi detector MinerU (số đo thật hôm nay) |
|---|---|---|
| Độ chính xác | `assumed`, chưa spike, yếu với dòng ngắn | **max 0.40°, median 0.1°** trên 18 dòng thật (V-2) |
| Ghép span với `middle.json` | theo trọng tâm bbox đã bị làm phẳng — mơ hồ | theo **TEXT** (`det+rec` trả text, score 0.99-1.00) — gần như không nhầm (V-3) |
| Dependency mới | có thể cần `numpy` | **không** — dùng lại venv MinerU đã cài |
| Chi phí | chưa đo | **0.36s/trang** (det) / **2.0s/trang** (det+rec) + 0.73s init (V-4) |

**Kết luận**: (E) **thắng (A) trên mọi tiêu chí đã đo**. Lý do duy nhất còn lại để dè chừng (E) là
**bề mặt API nội bộ** — và điều đó được xử lý bằng golden fixture (Protocol 5 mục 3), không phải
bằng cách né phương án. ⇒ **Phương án nền tảng chuyển từ (A) sang (E).** Đánh giá cũ ở bảng 6.13.3
dòng (A)/(E) coi như **bị thay thế bởi mục V4 này**.

#### V5. Điểm KHÔNG đồng ý với Expert: bỏ "bộ lọc bậc thang" khỏi Phase 1

Expert đề xuất dùng heuristic "bậc thang" (đo độ trôi trọng tâm bbox giữa các dòng trong 1 khối,
suy ra góc gần đúng, sai số ~1°) làm **pre-filter rẻ tiền** để chỉ chạy detector trên trang nghi
ngờ. **Tôi loại hạng mục này khỏi Phase 1**, lý do dựa trên chính số đo của tôi:

- Chi phí mà pre-filter định tiết kiệm là **2,4 phút cho 1 sách 400 trang** (det-only, V-4) — so
  với 1 job scan vốn mất **hàng giờ** (OCR toàn bộ + dịch LLM từng chunk). Tiết kiệm **dưới 1%**
  thời gian job.
- Đổi lại, nó thêm **một code path thứ hai, kém chính xác hơn**, với chế độ hỏng riêng mà chính
  Expert đã thừa nhận: **bỏ sót caption 1 dòng** — tức bỏ sót đúng loại khối mà cơ chế FLAG sinh
  ra để bắt (nhãn xoay, pull-quote ngắn). Một bộ lọc âm tính giả nằm **trước** cơ chế chống im
  lặng thì phá hỏng chính mục tiêu của cơ chế đó (đúng bài học Bug #6).
- Nguyên tắc đã áp dụng khi bác bỏ P1.3 ở P0.2: **chỉ tối ưu khi số đo chứng minh cần tối ưu**.
  Ở đây số đo chứng minh điều ngược lại.

Nếu sau này đo được thời gian probe thật sự đáng kể trên corpus lớn (ví dụ > 5% thời gian job),
mở lại hạng mục này — ghi vào backlog, không làm bây giờ.

#### V6. QUYẾT ĐỊNH CUỐI — 2 pha, xây trên (E)

**Tôi chấp nhận cấu trúc 2 pha của Expert thay cho A′ thuần tuý của tôi.** Lý do tôi đổi ý (chứ
không phải chỉ nhượng bộ): trong đề xuất cũ, lập luận số 5 của tôi ("A′ là bước 1 của A, không
phải ngõ cụt") là **suy đoán** — với (A) tự viết, phần đo góc là phần khó nhất và chưa ai biết nó
có đủ chính xác để dùng cho hình học hay không. Sau spike hôm nay, với (E), lập luận đó trở thành
**sự thật đo được**: góc đã có sẵn với sai số 0.4°, nên khoảng cách từ "chỉ flag" tới "dựng đúng
hình học" thu lại còn **2 chỉnh sửa cục bộ trong đúng 1 file** (`searchable_pdf.py`: nối θ vào
`insert_text(morph=...)`, và xoay tứ giác whiteout ở V3-3). Khi delta nhỏ và đã biết rõ như vậy,
việc **viết sẵn Phase 2 thành thiết kế có điều kiện kích hoạt** rẻ hơn hẳn việc để nó là "known
limitation vĩnh viễn" rồi phải research lại từ đầu. Đây là ưu điểm thật của đề xuất Expert so với
A′ của tôi.

**PHASE 1 — làm ngay, ~1 ngày** (mục tiêu: **hết im lặng**, không đụng hình học output)

1. **Task P0 (làm TRƯỚC mọi thứ, ~1-2 giờ)**: cấu hình logging handler cho logger `src.*` trong
   `src/api/main.py`. Cả tôi và Expert đều xếp đây trên cùng: mọi `logger.warning(exc_info=True)`
   ở các nhánh best-effort (gồm nhánh nuốt exception của `overlay_rotated_text()`,
   `job_orchestrator.py:533-539`) hiện **im lặng hoàn toàn** trong production. Bug #6 chỉ lộ ra vì
   QA mở file thủ công.
2. **Module mới `src/services/mineru_det_probe.py`** (đặt ở `services/` chứ không `preprocess/`
   vì đây là wrapper gọi tool ngoài qua subprocess — cùng loại với `*_runner.py`, chịu Protocol 5).
   - Chạy subprocess bằng interpreter MinerU (`~/.local/share/uv/tools/mineru/bin/python`), input
     là PNG từng trang render **200 DPI** bằng PyMuPDF, gọi
     `PytorchPaddleOCR(lang="en").ocr(img, det=True, rec=True)`.
   - Output JSON `[{page, poly_px, text, score}]`; lọc `score >= 0.8` và `|θ| >= 3.0°`.
   - Quy đổi toạ độ: poly ở px@200DPI → point nhân `72/200`. Góc trong hệ ảnh (y hướng xuống) có
     **dấu ngược** với `dir` của PyMuPDF — spike đo θ_ảnh ≈ -11° trùng dấu với `dir` = -11.0° ở
     fixture này, nhưng đây là chi tiết dễ sai dấu, **bắt buộc assert bằng fixture trong test**.
3. **Ghép với `middle.json`**: khớp theo **TEXT** (fuzzy, chuẩn hoá khoảng trắng/hoa thường) +
   ràng buộc khoảng cách trọng tâm < 0.5 chiều cao dòng. Góc của cả khối = **median** góc các dòng
   thành phần (median chứ không mean — spike cho thấy có poly nhiễu `-23.43°`, median miễn nhiễm).
4. **Ghi flag**: kết quả `(page_number, bbox, angle_deg)` → `LayoutQaFindingData` với lý do
   `"rotated_text_scan_unsupported"`, đúng trang/khối/góc. **θ KHÔNG đi vào `insert_text`** ở
   Phase 1.
5. **Golden fixture (Protocol 5 mục 3)**: lưu output spike hôm nay tại
   `tests/fixtures/mineru/det_probe_p67.json` — file này đã được sinh ra trong task này, Dev
   **copy vào repo, không viết tay lại**.
6. **Test bắt buộc (R6-02)**: assert **giá trị θ cụ thể** (median ≈ -11.0°, dung sai ±1.5°) và
   assert `layout_qa_findings` có **≥ 1 hàng** cho job `pdf_scan` fixture — không chấp nhận
   `assert_called()`. Thêm 1 smoke test gọi detector thật, được phép `skip` khi thiếu venv MinerU
   (R5-03).
7. **PRD**: ghi known-limitation — `pdf_scan` **phát hiện và FLAG** trang có chữ xoay để soát tay,
   nhưng **chưa** tái tạo góc; nguyên nhân gốc ở MinerU (6.13.1 S-M3).

**PHASE 2 — thiết kế đã chốt, KHÔNG implement bây giờ**

*Điều kiện kích hoạt*: job `pdf_scan` **thật trong production** đầu tiên sinh ra ≥ 1 finding
`"rotated_text_scan_unsupported"`. Khi điều kiện xảy ra, Tech Lead **re-scope rồi mới giao Dev**
(không tự động chuyển sang implement) — vì còn phải phân loại finding đó là khối nội dung thật
hay chỉ nhãn trang trí.

*Nội dung (ước ~1-1.5 ngày, đã tính cả 2 câu hỏi verify)*:
- **B2.1 (verify trước tiên)**: đo xem hình chữ nhật whiteout của cầu nối có sống sót qua babeldoc
  không (`[CHƯA VERIFY]` ở V3-4). Nếu **không** sống sót thì toàn bộ Phase 2 phải thiết kế lại —
  đây là gate, không phải chi tiết.
- **B2.2**: `searchable_pdf.py:113-125` — khi span có θ, thay `draw_rect` ngang bằng **tứ giác
  xoay** (`Shape.draw_polygon` + `finish(fill=(1,1,1))`) dựng từ poly gốc + padding 1.5pt. Vá
  đúng phần 5,5% hở đã đo ở V3-2.
- **B2.3**: `_insert_invisible_text()` nhận thêm `angle_deg`/`poly`; đặt baseline theo cạnh poly
  gốc; `insert_text(..., morph=(pivot, Matrix(-θ)))`; hình học tái dựng theo 6.13.2-b.
- **B2.4**: **KHÔNG** đụng `rotated_text_overlay.py` (module đó đã verify sống ở nhánh digital;
  chỉ cần input đúng) — điểm này tôi và Expert đồng ý hoàn toàn.
- **B2.5 (live E2E, R6-03)**: dựng lại fixture scan từ `tests/fixtures/babeldoc/rotated_text_p67_source.pdf`
  (raster hoá 200 DPI — cách QA đã mô tả trong `docs/test-report.md`; fixture scratchpad cũ của QA
  có thể đã bị dọn, tái tạo chứ đừng phụ thuộc vào nó), chạy **xuyên suốt** OCR → dịch → overlay,
  rồi **mở file output đọc nội dung thật**: assert ≥ 15 dòng có `dir` ≈ -11° và **không còn** dòng
  ngang nào chứa `"disaccharide"`.
- **B2.6**: nếu gặp khối chữ xoay ≈ ±90° thì áp dụng cảnh báo ở V2 (babeldoc **giữ** glyph và
  **vẽ** ô nền trắng ở dải góc đó) — cần bước xoá/che vùng babeldoc đã vẽ, effort tăng thêm.

**Vẫn giữ LOẠI**: phương án (B) flag mức job (flag fatigue), (C) tự xoay ảnh, (D) đổi engine sang
pdf2zh — lý do không đổi so với 6.13.3, Expert cũng đồng ý loại.

#### V7. Escalate lên PM/user (ngoài thẩm quyền Tech Lead)

1. **Câu hỏi sản phẩm (Expert nêu, tôi tán thành là đúng chỗ)**: **PM/user có kế hoạch nhận tài
   liệu PDF scan trong thời gian tới không?** Điều này quyết định Phase 2 là "thiết kế treo chờ
   điều kiện" (nếu chưa có kế hoạch — mặc định tôi chọn) hay nên đẩy lên làm ngay sau Phase 1
   (nếu sắp có sách scan thật). Dữ kiện để PM cân nhắc: cả **6 file đã upload đều là
   `pdf_digital`**, chưa có sách scan nào đi qua app; nhưng trong corpus digital cùng thể loại,
   ~4-5% số trang có khối chữ xoay có chủ đích (Expert quét: Le Cordon Bleu 19/418 trang, Figoni
   4 trang) ⇒ nếu một ấn bản **scan** cùng thể loại xuất hiện, kỳ vọng hợp lý là hiện tượng lặp
   lại. *Tôi đã sửa lại cách nói của mình ở 6.13.5-1*: gọi đây là "trường hợp giả định" là **quá
   nhẹ**; chính xác hơn là "chưa có bằng chứng trên nhánh scan, nhưng có bằng chứng gián tiếp
   mạnh từ bản digital song sinh".
2. **Ưu tiên task P0 logging**: xác nhận cho phép chen task này lên **trước** Phase 1 (~1-2 giờ,
   chạm `src/api/main.py`). Nó không sửa Bug #6 nhưng là điều kiện để bug kế tiếp không im lặng
   y hệt.

#### V8. Trạng thái verify (tổng hợp mục này)

| Nội dung | Trạng thái |
|---|---|
| Detector MinerU trả poly còn góc, sai số ≤ 0.40° trên 18 dòng | `verified` — spike Tech Lead tự chạy 2026-09-07 |
| Chi phí probe 0.36s/trang (det) — 2.0s/trang (det+rec), init 0.73s | `verified` (1 lần chạy, máy Dev, không kiểm soát tải) |
| babeldoc vứt glyph xoay deterministic, không phân biệt `render_mode` | `verified` — `il_creater.py:968-974, 390-398` (0.6.4) |
| Ô nền trắng chỉ sinh từ paragraph, đúng 1 nơi trong toàn package | `verified` — `paragraph_finder.py:117` + grep toàn package |
| Rủi ro "2 lớp chữ" với \|θ\| ngoài lân cận 0°/90° | `verified: KHÔNG xảy ra` (thay thế `[UNVERIFIED]` ở 6.13.4) |
| Rủi ro "2 lớp chữ" với θ ≈ ±90° | `verified: CÓ xảy ra` — phát hiện mới, chưa ai nêu trước đó |
| Cầu nối đã có sẵn whiteout ngang cho mọi span | `verified` — `searchable_pdf.py:113-125` |
| Vệt raster tiếng Anh hở 5,5% diện tích (dồn vào dòng rìa khối, tối đa 28,5%) | `verified` — mô phỏng công thức `ocr_utils.py:399-410` trên poly thật |
| Whiteout của cầu nối có sống sót qua babeldoc hay không | `[CHƯA VERIFY]` — **gate đầu tiên của Phase 2 (B2.1)** |
| Chữ ký `PytorchPaddleOCR` ở branch `dev`/version tương lai của MinerU | `[CHƯA VERIFY]` — khoá bằng golden fixture, verify lại khi nâng version (Protocol 5 mục 5) |

**Artifact của spike** (không commit vào repo trong task này): `render.py`, `det_spike.py`,
`coverage.py`, `p67_200dpi.png`, `det_probe_p67.json` tại scratchpad của session này. File
`det_probe_p67.json` là **golden fixture bắt buộc** của Phase 1 — Dev copy vào
`tests/fixtures/mineru/`, không viết tay lại (Protocol 5 mục 3).

---

### Bug #7 — List line-break regression tái phát + Bug #8 — Font quá nhỏ trong bảng (2026-09-07)

**Tác giả**: Tech Lead — phân tích/research, KHÔNG implement code.
**Triệu chứng user báo (v1.2.6, đã verify bằng mắt trên 4 ảnh so sánh song song)**:
- **Bug #7**: mục lục, danh sách "Questions for Review" đánh số 1–17, và bullet list lồng nhau
  trong box "Products Prepared"/"Materials and Equipment" bị dồn thành đoạn văn liền mạch; số thứ
  tự (`2.`, `3.`) và bullet (`■`/`▪`) nằm giữa dòng thay vì đầu dòng.
- **Bug #8**: cỡ chữ trong bảng "TABLE 4.2 — Texture Terms" không đồng đều và nhỏ bất thường so
  với bản gốc, ngay trong cùng 1 cột của cùng 1 bảng.

#### W0. Tóm tắt điều hướng

| | Bug #7 | Bug #8 |
|---|---|---|
| Có phải regression của fix cũ không? | **Không** — F1/F2/Q6 (`split_short_lines=True`, `factor=0.8`) vẫn đang chạy đúng; nó chỉ **không phủ được** 2 cơ chế mới tìm ra ở đây | Không — là biểu hiện cụ thể đầu tiên **đo được bằng số** của "tam nan" U5/U7-E1 |
| Nguyên nhân nằm ở đâu | 100% trong babeldoc 0.6.4 (`paragraph_finder.py`) | 100% trong babeldoc 0.6.4 (`typesetting.py`) |
| Code của team có sai gì không | Không | Không |
| Có flag CLI nào chữa được không | Không (đã hết tác dụng, xem W3) | **Không có flag nào tồn tại** (W5-3) |

#### W1. Nguồn xác thực (Protocol 5 / R5-01)

Toàn bộ claim dưới đây có nguồn trực tiếp. **Không có claim nào từ trí nhớ.**

**(a) Source thật babeldoc 0.6.4 đã cài** tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`
(`main.py:29` → `__version__ = "0.6.4"`).

**(b) Bằng chứng sống (Protocol 6 / R6-03) — chạy thật, $0 chi phí LLM**: chạy `babeldoc` 0.6.4
CLI thật với `--debug` trên 4 trang thật (`src` page 74–77) trích từ chính file production
`data/uploads/937b1d1c-…_Figoni, Paula - How baking works….pdf`, cùng flag production
(`--split-short-lines --short-line-split-factor 0.8`). Cố ý trỏ `--openai-base-url` tới
`http://127.0.0.1:1/v1` (không có server) → **0 token, 0 USD**, nhưng dump IL
`paragraph_finder.json` **vẫn được ghi vì nó nằm TRƯỚC bước dịch** (`high_level.py:973-977`).
Đây là cách quan sát trực tiếp cấu trúc đoạn mà babeldoc tạo ra, tách bạch hoàn toàn khỏi biến số
LLM. Artifact: `/tmp/bdprobe/wd/p74_77/paragraph_finder.json`.

**(c) Đo output production thật**: so `data/uploads/937b1d1c-…Figoni….pdf` (nguồn) với
`data/outputs/40cb4746-16ba-4c24-ab75-5b2cd9f83d0d/translated_vi.pdf` (job `40cb4746`, chạy
2026-09-06 14:00, **đúng bản v1.2.6 user đang báo lỗi**), bằng PyMuPDF 1.28.2.

| # | Claim | Nguồn |
|---|-------|-------|
| W-1 | `min_scale = 0.1` là **hằng số cứng trong thân hàm**, không phải tham số | `format/pdf/document_il/midend/typesetting.py:969` |
| W-2 | Vòng tìm scale: `while scale >= min_scale`, giảm `-0.05` khi `scale > 0.6`, `-0.1` khi thấp hơn | `typesetting.py:973, 1012-1015` |
| W-3 | **Không có CLI flag nào** và **không có field nào trong `TranslationConfig`** liên quan tới scale/min font size | `grep -n "scale" main.py` → 0 kết quả; `grep -n "scale" translation_config.py` → 0 kết quả |
| W-4 | Mỗi `PdfParagraph` (⇒ mỗi Ô BẢNG) có `optimal_scale` **riêng**, tìm độc lập từ 1.0 | `typesetting.py:895-914` (`preprocess_document`), `:1078-1094` (`_get_optimal_scale`) |
| W-5 | Chuẩn hoá theo mode **chỉ kéo XUỐNG**: `if paragraph.optimal_scale > mode_scale: = mode_scale`. **Không có nhánh nào nâng scale nhỏ lên** | `typesetting.py:919-936` |
| W-6 | `render_paragraph` dùng `optimal_scale` đã tính làm `initial_scale`, rồi lại chạy tiếp vòng giảm scale tới `min_scale` | `typesetting.py:1271-1281`, `:1096-1116` |
| W-7 | Gap giữa các dòng chỉ được ghi nhận khi collision count **`< 1`** (tức đúng bằng 0), **mâu thuẫn với chính docstring của hàm** ("less than 2") | `paragraph_finder.py:725` vs docstring `:657-661` |
| W-8 | Nếu `gaps` rỗng → **toàn bộ paragraph gộp thành MỘT `PdfLine` duy nhất** | `paragraph_finder.py:735-743` |
| W-9 | `process_independent_paragraphs` **bỏ qua hoàn toàn** paragraph có `len(pdf_paragraph_composition) <= 1` | `paragraph_finder.py:848-851` |
| W-10 | `is_bullet_point` chỉ xét `chars[0]` — ký tự ĐẦU TIÊN của dòng | `layout_helper.py:55-65`; call site `paragraph_finder.py:896-901` |
| W-11 | `BULLET_POINT_PATTERN` **CÓ** `■` (U+25A0) và `▪` (U+25AA); **KHÔNG CÓ** chữ số ASCII `0-9`, `-`, `–`, `*` | `layout_helper.py:48-50`; verify chạy thật bằng interpreter của chính babeldoc: `▪`→True, `■`→True, `1`→False, `2`→False, `-`→False |
| W-12 | Nhánh nhận diện mục lục chỉ kích hoạt khi có **≥ 20 dấu chấm liên tiếp** (dot leader) | `paragraph_finder.py:864-866` (`re.search(r"\.{20,}", prev_text)`) |
| W-13 | Cả 2 default hiện hành đúng như Q6 đã chốt: `babeldoc_split_short_lines = True`, `babeldoc_short_line_split_factor = 0.8` | `src/core/config.py:181, 188` |

#### W2. Bug #7 — bằng chứng sống: chuyện gì thực sự xảy ra

Đọc trực tiếp `paragraph_finder.json` (IL **trước khi dịch**, W1-b). Đây là bằng chứng mạnh nhất:
nó chứng minh cấu trúc đã sai **trước** khi LLM chạm vào, nên **loại trừ hoàn toàn** giả thuyết
"LLM gộp dòng" / "prompt sai" (RC-3 cũ) cho 2 ca này.

**Ca A — `QUESTIONS FOR REVIEW` (src page 74), numbered list 17 mục.**
IL page 0 sau `ParagraphFinder`, các paragraph `plain text`:

```
"1. Why is it that humans often "eat with their eyes"?"                      <- ĐÚNG (1 mục)
"2. What three things can happen…?  3. What makes limes green in color?"     <- GỘP 2 mục
"4. List the three main factors…  5. Explain why the appearance…"            <- GỘP 2 mục
"6. Explain and provide an example…  7. …"                                    <- GỘP
"8. Why is saliva necessary…  9. …  10. …  11. …  12. …  13. …  14. …  15. …" <- GỘP 8 mục (9 dòng)
"16. How does the perception of saltiness change…"                            <- ĐÚNG
"17. What is meant by mouthfeel?"                                             <- ĐÚNG
```

Paragraph "8.…15." có **9 `pdf_line` riêng biệt, tách dòng ĐÚNG** (đo được: `w=273.8 / 361.1 /
277.3 / 311.8 / 225.3 / 325.0 / 208.4 / 356.2 / 26.5`). Nghĩa là bước tách dòng chạy tốt; bước
**tách ĐOẠN** mới là chỗ hỏng. Với mỗi cặp dòng liền kề, điều kiện tách (`paragraph_finder.py:891-901`):
- nhánh bullet: `chars[0]` là `'8'`, `'9'`, `'1'` — chữ số ASCII → `is_bullet_point` **luôn False**
  (W-11). Nhánh này chết hoàn toàn với numbered list.
- nhánh hình học: `prev_width < median_width × 0.8`. Các dòng câu hỏi rộng **208–361pt**, tức là
  **chính chúng tạo ra median của trang** → điều kiện gần như không bao giờ đúng. Nó chỉ kích hoạt
  ở đúng chỗ dòng trước bị ngắn thật (dòng cuối bị wrap, `w=26.5` của `"usual?"`) — và đó chính
  là lý do mục 16 và 17 tách ra đúng còn 8–15 thì không.

Đo trên output production (W1-c), page 74:

| | Nguồn EN | Bản dịch VI (v1.2.6) |
|---|---:|---:|
| Số dòng **bắt đầu** bằng `N.` | **17** | **3** |
| Số lần `N.` nằm **giữa dòng** | 0 | **10** |

→ Khớp chính xác triệu chứng user mô tả.

**Ca B — box `PRODUCTS PREPARED` / `MATERIALS AND EQUIPMENT` (src page 77), bullet `■` (U+25A0).**
Đây là ca **QUAN TRỌNG NHẤT và HOÀN TOÀN MỚI**, vì `■` **NẰM TRONG** `BULLET_POINT_PATTERN`
(W-11) — tức là RC-2 cũ ("pattern thiếu marker") **KHÔNG giải thích được** ca này. Cơ chế thật:

IL cho thấy paragraph `"■ Sugar and acid  ■ Other (…)  ■ Your choice of additions"` có
**đúng 1 composition** — tức babeldoc coi cả 3 mục là **MỘT dòng duy nhất**. Đo toạ độ các ký tự
`■` trong "dòng" đó: `x=410.8 y=205.7`, `x=410.8 y=193.7`, `x=410.8 y=157.7` — **cùng x, khác y**,
tức là 3 mục **xếp chồng theo chiều dọc thật sự**, không phải nhiều cột.

Vì sao 3 dòng vật lý bị gộp thành 1 `PdfLine`? `_split_paragraph_into_lines`
(`paragraph_finder.py:652-776`) dùng phương pháp "line-threading": quét ngang theo y, chỗ nào có
ít ký tự cắt qua thì coi là khe giữa 2 dòng. **Docstring viết ngưỡng là "less than 2"
(`:657-661`) nhưng code implement là `count < 1` (`:725`) — tức đòi khe phải HOÀN TOÀN TRỐNG.**

Tự tính lại histogram từ chính dữ liệu IL đó (pure Python, cùng `step=0.25`, cùng `visual_bbox`
mà `_get_effective_y_bounds` dùng — `:600-609`):

```
y=204.24  count=21   [' ', ' ', ' ', ' ', 'S', 'u', …]   <- dòng "■ Sugar and acid"
y=203.99  count=1    ['g']        <- KHE giữa 2 dòng, nhưng bị 1 ký tự bắc cầu
…
y=202.24  count=1    ['g']
y=201.99  count=11   ['g', ' ', ' ', …]                  <- dòng kế tiếp
```

Khe giữa 2 dòng **có tồn tại**, nhưng bị bắc cầu bởi **đúng MỘT ký tự**: đuôi descender của chữ
`g` trong `"Sugar"`. Vì `1 < 1` là False → không ghi nhận gap nào → `gaps` rỗng → W-8 kích hoạt →
**cả box bullet gộp thành 1 `PdfLine`**. Hệ quả dây chuyền:

1. Paragraph còn đúng 1 composition → W-9: `process_independent_paragraphs` **bỏ qua không xét**.
2. Kể cả có xét, `is_bullet_point` chỉ nhìn `chars[0]` (W-10) → chỉ thấy `■` đầu tiên; `■` thứ 2,
   thứ 3 nằm giữa dòng, vô hình với thuật toán.
3. Cả 3 mục đi vào LLM như **một chuỗi**, quay về như một chuỗi, được typeset thành một đoạn chảy.

Đo trên output production, page 77: dòng bắt đầu bằng bullet **16 → 7**; bullet nằm giữa dòng
**1 → 10**. Ví dụ thật trong file giao cho user:
`"■ Không bổ sung (sản phẩm đối chứng) ■ Đường ■ Axit"` — **khớp chính xác** ảnh user gửi.

**Đây là một bug thật của babeldoc** (code lệch docstring của chính nó), không phải giới hạn thiết
kế. Một ký tự có đuôi (`g`, `y`, `p`, `q`, `j`) hoặc dấu tiếng Việt lấn vào dải giữa 2 dòng là đủ
phá vỡ việc tách dòng của **cả khối**. Điều này giải thích tính **thất thường** của lỗi: cùng một
kiểu box, chỗ hỏng chỗ không, phụ thuộc thuần vào việc dòng đó có chữ nào thò đuôi hay không.

**Ca C — trang mục lục (Contents).** Hai lớp bảo vệ đều không hoạt động:
- Nhánh mục lục chuyên dụng đòi **≥ 20 dấu chấm liên tiếp** (W-12). Mục lục của Figoni
  **không dùng dot leader** (chỉ `"Stage II: Baking 32"`) → nhánh này không bao giờ chạy.
- Nhánh hình học: mọi dòng mục lục đều ngắn như nhau ⇒ **chính chúng là median** ⇒
  `prev_width < 0.8 × median` hiếm khi đúng. Đây đúng là cơ chế "median bị kéo lệch" mà RC-1 đã
  cảnh báo, nhưng theo chiều **ngược lại** với dự đoán ban đầu: trang toàn dòng ngắn thì heuristic
  **mất tác dụng**, chứ không phải tách quá tay.
- Đo: page 7 (Contents), block **72 → 49**, dòng **88 → 81**.

#### W3. Vì sao fix F1/F2/Q6 đã ship KHÔNG chặn được (và không phải do đo sai)

Kết luận Q6 (đổi default sang `True`/`0.8`) **vẫn đúng với dữ liệu Q1–Q6** và **không nên revert**.
Vấn đề là **phạm vi**:

| | Trang 14 (đo ở Q1–Q6) | Trang 74 (bug này) |
|---|---|---|
| Bố cục list | 2 cột **hẹp**, mỗi mục 1 dòng ngắn | 1 cột **rộng**, mỗi mục 1–3 dòng gần full-width |
| Quan hệ với `median_width` | Dòng list **hẹp hơn** median toàn trang → heuristic kích hoạt | Dòng list **CHÍNH LÀ** median → heuristic im lặng |
| Kết quả `true08` | 26/35 mục đúng (tốt rõ rệt) | 3/17 mục đúng (gần như không tác dụng) |

`--split-short-lines` là **proxy hình học**, chỉ đúng khi list item tình cờ ngắn hơn văn xuôi xung
quanh. Nó **không phải** cơ chế nhận diện list. Q1–Q6 đo trên đúng chế độ mà proxy này hoạt động;
sách mới rơi vào chế độ ngược lại. **Không có giá trị `factor` nào chữa được ca này** — hạ factor
làm heuristic im lặng hơn; nâng factor > 1.0 sẽ tách vụn cả văn xuôi. Đây là **giới hạn cấu trúc**
của F2, không phải tham số chưa tune.

Tương tự, **Ca B nằm ngoài phạm vi của MỌI phân tích trước đó**: RC-1 (hình học) và RC-2 (pattern
thiếu marker) đều không đúng cho nó — bug nằm ở **tầng tách DÒNG**, một tầng thấp hơn cả hai.

#### W4. Bug #7 — quan hệ với F3 (spike đã thất bại) — KHÔNG lặp lại cách cũ

F3 (CHANGELOG "F3 — Spike verify … KHÔNG thành công", 2026-09-06) đã thử **chèn ký tự `•` vô hình
vào PDF NGUỒN** trước khi đưa cho babeldoc. Thất bại vì 2 lý do độc lập đã verify:
(1) thứ tự ký tự trong dòng **không sort theo x** (3 dòng `sort` bị comment out trong source thật)
→ ký tự chèn thêm không rơi vào vị trí `chars[0]`; (2) babeldoc **re-render toàn bộ**, không tôn
trọng `render_mode=3` → ký tự "vô hình" hiện ra thành rác trong output.

**Mọi đề xuất ở W6 dưới đây KHÔNG dùng lại cơ chế injection đó.** Chúng can thiệp **bên trong
process của babeldoc** (Hướng B, Architecture.md P3), nơi cả 2 lý do thất bại trên đều không tồn
tại: không chèn gì vào PDF nguồn, không phụ thuộc thứ tự extraction, không đụng bước render.

#### W5. Bug #8 — root cause (verified)

**Đo trên dữ liệu thật** (W1-c), trang `TABLE 4.2 — Texture Terms` (src page 75), phân bố cỡ chữ
(số span mỗi cỡ, đọc bằng PyMuPDF `get_text("dict")`):

| | Nguồn EN | Bản dịch VI (v1.2.6) |
|---|---|---|
| Phân bố cỡ chữ | `9.0pt × 101` span, `10.0 × 8`, `8.0 × 7` — **gần như đồng nhất** | `8.1 × 24`, `5.85 × 15`, `6.3 × 14`, `9.0 × 10`, `6.75 × 7`, `7.65 × 7`, `6.0 × 6`, `4.5 × 6`, `7.2 × 3`, `6.5 × 2`, `4.05 × 2`, `5.4 × 2` — **12 cỡ khác nhau** |
| Tỷ lệ so với 9.0pt gốc | 1.00 | **0.45 → 1.00** (`4.05/9.0 = 0.45`) |

Chuỗi nguyên nhân, mọi mắt xích đều có source:

1. **Mỗi ô bảng là một `PdfParagraph` riêng** → có `optimal_scale` riêng, tìm **độc lập** bằng
   `_find_optimal_scale_and_layout` khởi tạo từ `1.0` (W-4).
2. Vòng lặp giảm scale cho tới `min_scale = **0.1**` — **hằng số cứng trong thân hàm**, không phải
   tham số, không có flag CLI, không có field config (W-1, W-2, W-3).
3. Bước chuẩn hoá theo mode (`preprocess_document`) **chỉ kéo XUỐNG những paragraph cao hơn mode,
   không bao giờ nâng những paragraph thấp hơn mode lên** (W-5). Nghĩa là nó **áp một trần chung**
   nhưng **bảo toàn nguyên vẹn mọi sự chênh lệch phía dưới trần**. Đây chính là lý do bảng trông
   "vỡ": mode ở đây là `0.9` (⇒ `8.1pt`), các ô ngắn ("Mềm", "Dai") nằm ở trần; các ô dài
   ("Có thịt quả, ẩm…") tụt tự do xuống tới `0.45`.
4. Tiếng Việt dài hơn tiếng Anh ~20–40% ⇒ ô nào text dài hơn thì tụt sâu hơn. Chênh lệch độ dài
   giữa các ô trong cùng một cột **được khuếch đại thành chênh lệch cỡ chữ nhìn thấy được**.

**Đây chính là "tam nan" U5 đã mô tả** (bóp font / giãn khung / cắt text), lần đầu **đo được bằng
số** thay vì mô tả định tính. Với ô bảng, babeldoc gần như luôn chọn "bóp font": nhánh giãn khung
(`typesetting.py:1017-1062`) chỉ chạy khi `scale < 0.7`, và trong bảng thì
`get_max_bottom_space`/`get_max_right_space` gần như không có chỗ trống để giãn (ô bảng bị bao
quanh bởi ô khác) → rơi thẳng về nhánh bóp font tới đáy `0.1`.

**Chính sách U7-E1 ("bóp tối đa 70% rồi FLAG") CHƯA từng được implement ở đâu** — xác nhận bằng
`grep -rn "min_scale\|0\.7" src/` → không có chỗ nào áp sàn scale. U7-E1 tới nay vẫn ở trạng thái
"escalate cho PM/user, chưa chốt". **Bug #8 là bằng chứng thực nghiệm đầu tiên cho thấy nó cần
được chốt.**

#### W6. Đề xuất SƠ BỘ (Tech Lead — chưa chốt, chờ Domain Expert phản biện + PM duyệt)

##### Bug #7

**Đường đi khả thi duy nhất còn lại là Hướng B-2 (wrapper in-process)** đã đánh giá ở P3 và đã
verify sống cơ chế patch (P3/B-1: patch `BULLET_POINT_PATTERN` ở module global CÓ tác dụng lên
`paragraph_finder`). Hai patch, theo thứ tự lợi ích/rủi ro:

- **B-2a (ưu tiên cao nhất — rẻ, rủi ro thấp, sửa đúng một bug thật của babeldoc)**: nới ngưỡng
  gap của line-threading từ `count < 1` về `count < 2` — **đúng bằng con số docstring của chính
  babeldoc tuyên bố** (W-7). Đây không phải "chế thêm heuristic", mà là làm cho code khớp với đặc
  tả của chính nó. Sửa được **Ca B** (bullet `■` bị gộp) ở tận gốc, và có khả năng cải thiện cả
  **Ca C** (mục lục). Rủi ro cần đo: ngưỡng 2 có thể tách nhầm ở khối chữ dày đặc/nhiều dấu — phải
  A/B trên nhiều trang trước khi chốt.
  ⚠️ **`[UNVERIFIED]`**: chưa đo tác động của `count < 2` trên toàn tài liệu. Bắt buộc spike theo
  R5-02 trước khi implement đầy đủ.
- **B-2b — bọc `ParagraphFinder.process`**: chạy `process()` gốc trước, rồi duyệt IL và tách
  paragraph tại các **dòng** mở đầu bằng marker numbered (`1.`, `2.`, `a)`). Ở tầng này ta thấy
  **toàn bộ text của dòng**, không chỉ `chars[0]` (W-10) — nên áp được heuristic chống
  false-positive thật (marker phải tăng dần; loại `"2 cups flour"`; loại dòng mục lục). Sửa được
  **Ca A**. Code tách có sẵn để tái dùng nguyên xi (`paragraph_finder.py:868-925`), không phải
  chép lại logic typeset.
- **KHÔNG đề xuất**: (a) tiếp tục tune `short_line_split_factor` — đã chứng minh là ngõ cụt cấu
  trúc (W3); (b) nới `BULLET_POINT_PATTERN` thêm `0-9` (B-1 cũ) — vô dụng cho Ca A vì `chars[0]`
  chỉ 1 ký tự, không phân biệt được `"1. Trộn bột"` với `"180°C…"`, mà B-2b làm được đúng việc đó
  với cùng chi phí wrapper; (c) mọi biến thể của F3 (injection vào PDF nguồn) — đã thất bại, xem W4.

**Điều kiện bắt buộc kèm theo** (giữ nguyên P5): pin cứng `babeldoc.__version__ == "0.6.4"`, raise
ngay nếu lệch; smoke test gọi thật; assert **cấu trúc output** (đếm dòng bắt đầu bằng marker), tuyệt
đối không assert sự có mặt của flag trong `args` (bài học N4).

##### Bug #8

**Đề xuất: ĐÃ ĐỦ CƠ SỞ để chốt U7-E1, nhưng KHÔNG nên implement như "sàn 0.7 cứng".** Lý do: `0.7`
trong U7-E1 là con số **đề xuất chưa từng đo**. Số đo thật ở W5 cho thấy mode của trang bảng này là
`0.9` và đuôi kéo tới `0.45`. Một sàn cứng `0.7` sẽ biến mọi ô hiện ở `0.45–0.65` thành **tràn chữ**
(babeldoc cố ý vẽ tràn khi hết cách — T-04) — tức là **đổi một lỗi thẩm mỹ lấy một lỗi chồng chữ**,
đúng nhánh (2)/(3) của tam nan U5. Đề xuất 3 bước, theo thứ tự:

1. **Đo trước, chốt số sau** (P0, rẻ nhất): dùng chính phương pháp W1-c chạy trên ≥ 5 trang bảng
   thật, dựng **histogram scale thực tế**. Sàn phải chọn từ dữ liệu, không từ con số tròn.
2. **Ưu tiên "thu hẹp khoảng cách" hơn "áp sàn tuyệt đối"**: cái user thực sự phàn nàn là
   **KHÔNG ĐỒNG ĐỀU trong cùng 1 bảng**, không phải "chữ nhỏ" nói chung. Vì vậy đề xuất **đảo ngược
   chiều chuẩn hoá của W-5**: thay vì chỉ kéo xuống mode, **kéo mọi paragraph trong cùng một vùng
   layout `table` về CÙNG một scale** (= min scale của vùng đó). Bảng sẽ nhỏ đều thay vì vỡ — đây
   là thay đổi rẻ hơn, rủi ro thấp hơn nhiều so với áp sàn, vì **không tạo thêm tràn chữ nào**
   (mọi ô chỉ nhỏ đi hoặc giữ nguyên, không ô nào to lên). Cùng cơ chế wrapper B-2 (patch
   `preprocess_document`), không phát sinh hạ tầng mới.
3. **Sàn + FLAG (U7-E1 đúng nghĩa)** chỉ làm sau, và phải đi kèm cơ chế **flag vào
   `layout_qa_findings`** — sàn mà không flag thì chỉ là đổi lỗi im lặng này lấy lỗi im lặng khác
   (đúng bài học Bug #6: `scan_rotated_lines()` trả 0 block và **không flag gì cả**).

⚠️ **`[UNVERIFIED]`**: cả bước 2 lẫn bước 3 đều chưa spike. Phải verify theo R5-02 trước khi
implement.

#### W7. Trạng thái verify (tổng hợp mục này)

| Claim | Trạng thái |
|-------|-----------|
| Bug #7 Ca A — numbered list gộp do `chars[0]` là chữ số + median không lệch | ✅ **Verified** — IL dump thật (W1-b) + `paragraph_finder.py:891-901` + đo output production 17→3 |
| Bug #7 Ca B — `■` bị gộp do `count < 1` bắc cầu bởi descender `g` | ✅ **Verified** — IL dump thật, tự tính lại histogram, `paragraph_finder.py:725, 735-743, 848-851` |
| Bug #7 Ca C — mục lục không có dot leader nên nhánh TOC không chạy | ✅ **Verified** — `paragraph_finder.py:864-866` + đo page 7 (72→49 block) |
| Bug #7 KHÔNG do LLM/prompt gộp dòng | ✅ **Verified** — cấu trúc đã sai trong IL **trước** bước dịch, 0 token LLM |
| Bug #7 KHÔNG do code của team | ✅ **Verified** — default `True`/`0.8` đúng như Q6 chốt (`config.py:181,188`), flag truyền đúng (`babeldoc_runner.py:308-318`) |
| Bug #8 — `min_scale = 0.1` hardcode, không có flag/config nào | ✅ **Verified** — `typesetting.py:969` + grep 0 kết quả trên `main.py`/`translation_config.py` |
| Bug #8 — chuẩn hoá mode chỉ kéo xuống, không nâng lên | ✅ **Verified** — `typesetting.py:919-936` |
| Bug #8 — biểu hiện thật: 12 cỡ chữ, scale 0.45–1.0 trong 1 bảng | ✅ **Verified** — đo output production page 75 |
| U7-E1 (sàn 0.7) chưa từng được implement | ✅ **Verified** — `grep -rn "min_scale" src/` → 0 kết quả |
| B-2a (`count < 2`) không gây tách nhầm trên tài liệu thật | ⚠️ **`[UNVERIFIED]`** — spike bắt buộc (R5-02) |
| B-2b heuristic marker tăng dần không false-positive | ⚠️ **`[UNVERIFIED]`** tại thời điểm viết mục này — bảng này (W7) đã bị section "Bug #7/#8 — Final Decision…" phía dưới thay thế; xem bảng X10 (đã ✅ Verified sau bước 7.2, 2026-09-07) cho trạng thái mới nhất |
| Đồng bộ scale theo vùng `table` không gây tràn chữ | ⚠️ **`[UNVERIFIED]`** — spike bắt buộc (R5-02) |
| Con số sàn tối ưu (0.7 hay khác) | ⚠️ **`[UNVERIFIED]`** — phải đo histogram trước khi chốt |

**Artifact spike** (không commit trong task này, tái tạo được bằng lệnh ghi ở W1-b):
`/tmp/bdprobe/wd/p74_77/paragraph_finder.json` — dump IL thật, **golden file bắt buộc** nếu PM
duyệt đi tiếp: Dev copy vào `tests/fixtures/babeldoc/`, KHÔNG viết tay lại (Protocol 5 mục 3).

**Trạng thái**: Phân tích/research xong — **không có code nào được viết**. Chờ Domain Expert phản
biện rồi PM/user quyết định.

---

### Bug #7/#8 — Final Decision sau phản biện Domain Expert (2026-09-07)

Section này **thay thế phần đề xuất** ở mục W6/W7 của section trước (W0–W7 giữ nguyên làm hồ sơ
điều tra). Nơi nào mâu thuẫn, **section này thắng**.

#### X0. Phán quyết một dòng

Domain Expert **đúng ở cả 4 điểm phản biện chính**. Tôi đã tự verify độc lập bằng cách viết lại
thuật toán từ source (không dùng script của Expert) và tái tạo **chính xác** con số Expert báo cáo.
Hai đề xuất của tôi ở W6/W7 bị **rút lại**: B-2a (`count < 2`) và "đồng bộ scale toàn bảng về MIN".

#### X1. Bảo toàn bằng chứng (làm trước tiên)

Golden IL dump đã được đưa vào repo, nén gzip để giảm 17MB → 613KB:

`tests/fixtures/babeldoc/paragraph_finder_p74_77_dump.json.gz`

Nguồn: `/tmp/bdprobe/wd/p74_77/paragraph_finder.json`, sinh bởi babeldoc 0.6.4 `--debug` trên
Figoni p74–77 (cách tái tạo: W1-b của section trước). Mọi số liệu dưới đây tái tạo được **từ chính
file này** (Protocol 5 mục 3 — golden file, không phải mock viết tay). Đọc bằng
`gzip.open(path, "rt")`.

#### X2. Tự verify độc lập — kết quả

**Phương pháp**: tôi viết lại `_split_paragraph_into_lines` bằng numpy từ source đã cài
(`step=0.25`, cùng công thức difference-array của `_compute_collision_counts_histogram`), chạy trên
golden dump. Ground truth = cluster baseline `char.box.y` (dung sai 3pt) trên ký tự **có mực**
(loại space). Loại "space dummy" (`pdf_character_id is None`, do `add_space_dummy_chars` chèn SAU
bước thread) khỏi tập ký tự.

**Fidelity của reimplementation**: tái tạo đúng số `pdf_line` có thật trong dump ở mức
**162/163 paragraph** — đủ để tin rằng tôi đang đo đúng thuật toán thật, không phải đo mô hình của
chính mình.

| Biến thể | Đúng / 163 | Under-split còn lại | Hồi quy |
|---|---|---|---|
| Hiện tại (`count<1`, tính cả space) | **147** | 16 | — |
| B-2a của tôi (`count<2`) | **149** | 14 | 0 (trên mẫu này) |
| Expert (`count<1`, **loại ký tự trắng khỏi phép đếm**) | **161** | 2 | 0 |

→ **Cả ba con số 147 / 149 / 161 trên 163 khớp tuyệt đối với báo cáo của Expert.** Đây là replication
độc lập (tôi viết script riêng từ source + mô tả phương pháp), không phải chạy lại script của Expert.

**Chi tiết 16 paragraph hiện đang sai** (in ra từ script):

| Trang | GT | Hiện tại | `count<2` | Loại-space | Nội dung |
|---|---|---|---|---|---|
| p0 | 2 | 1 | 1 | 1 | `)60` — nhãn `abandon` (số trang) |
| p0 | 3 | 1 | **1** | **3** | `1. Explain what is meant by…` |
| p0 | 3 | 1 | **1** | **3** | `2. Explain what is meant by…` |
| p1 | 7 | 2 | 2 | **7** | `Using regular (water-soluble) blue food coloring…` |
| p1 | 5 | 1 | 2 | **5** | `Compare the texture of properly stored…` |
| p1 | 7 | 1 | 1 | **7** | `Compare the texture of two products…` |
| p2 | 2 | 1 | 1 | 1 | `)62` — nhãn `abandon` |
| p2 | 5 | 1 | 1 | **5** | `Apple juice is a relatively mild-tasting juice…` |
| p2 | 3 | 1 | 1 | **3** | `Work slowly through this exercise…` |
| p2 | 3 | 1 | 1 | **3** | `While diluted apple juice is used…` |
| p2 | 2 | 1 | 2 | 2 | `■ To identify and describe differences…` |
| p2 | 6 | 1 | **1** | **6** | `■ To demonstrate how sugar affects…` |
| p2 | 5 | 1 | **3** | **5** | `■ Sugar and acid ■ Other…` |
| p2 | 3 | 1 | **2** | **3** | `■ No additions (control product) ■ Sugar ■ Acid` |
| p2 | 2 | 1 | 2 | 2 | `■ Tannin powder ■ Caffeine` |
| p2 | 2 | 1 | **1** | **2** | `■ Apple juice, 6 quarts (liters) or more…` |

Ba kết luận rút ra, **tất cả đều xác nhận Expert**:

1. **Trên 6 paragraph bullet `■` — bằng chứng chính của tôi cho Ca B — `count<2` chỉ sửa đúng 2/6**
   (2 ca cải thiện một phần nhưng vẫn sai, 1 ca không đổi gì). Cách loại ký tự trắng sửa **6/6**.
2. **Ca A KHÔNG chỉ là lỗi tầng ghép đoạn.** Hai mục numbered-list `1. Explain…` / `2. Explain…`
   bị nén từ 3 dòng thật xuống **1 `PdfLine` duy nhất ngay ở tầng tách dòng**. `count<2` **không
   sửa được** (vẫn =1); loại ký tự trắng sửa đúng =3. Đây là điểm mô tả sai của tôi ở W2, và nó
   tạo ra một **dependency** mà tôi chưa nêu: **B-2b bắt buộc phải chạy SAU khi tầng dòng được sửa**,
   nếu không nó chỉ nhìn thấy một dòng gộp `"1. Explain… 2. Explain…"` và không có gì để tách.
3. **Phạm vi lỗi rộng hơn hẳn "bullet lồng nhau"**: 6 paragraph văn xuôi bình thường (không list,
   không bullet) cũng đang bị nén sai — nặng nhất là 7 dòng → 1 dòng. Mô tả của tôi ở W2 giới hạn
   lỗi vào list là **hẹp hơn thực tế**.

2 ca còn sai sau fix Expert đều là `)60` / `)62` nhãn `abandon` (page furniture, không đi vào nội
dung dịch) — **không đáng xử lý**.

##### X2-b. Rủi ro hồi quy của `count<2` — tôi tự dựng ca tổng hợp và XÁC NHẬN có thật

Expert cảnh báo `count<2` sẽ gộp sai mọi dòng chỉ có **đúng 1 ký tự** (ô bảng số hẹp, chữ cái đơn,
số trang 1 chữ số) vì dòng đó không bao giờ đạt count ≥ 2. Mẫu 4 trang không tình cờ có ca này nên
tôi chưa đo được. Tôi dựng ca tổng hợp bằng chính reimplementation:

| Ca | GT | `count<1` | `count<2` | Loại-space |
|---|---|---|---|---|
| 1 chữ số đứng riêng 1 dòng + 1 dòng văn xuôi bên dưới | 2 | 2 | **1 ✗** | 2 |
| 2 dòng, mỗi dòng đúng 1 chữ số (cột số hẹp) | 2 | 2 | **1 ✗** | 2 |

→ **Hồi quy có thật, và rơi đúng vào bảng số** — chính là loại nội dung Bug #8 đang xử lý. Đủ để
loại bỏ B-2a hoàn toàn, độc lập với việc nó kém hiệu quả hơn.

##### X2-c. Verify các claim về source (Protocol 5 R5-01)

Nguồn: babeldoc **0.6.4** đã cài tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/midend/`
— cộng thêm fetch upstream `main` qua raw.githubusercontent.com để đối chiếu.

| Claim của Expert | Kết quả tự verify |
|---|---|
| `_get_effective_y_bounds` có dead code sau `return` | ✅ **Đúng** — `paragraph_finder.py:608-613`: `return visual_box.y, visual_box.y2` rồi mới tới nhánh IoU/`pdf_box`, **không bao giờ chạy**; docstring `:601-606` mô tả đúng cái nhánh chết đó. Upstream `main` **y hệt**. |
| Lời gọi `_sort_characters_in_lines` bị comment out | ✅ **Đúng** — hàm tồn tại `:1032`, lời gọi `:305` là `# self._sort_characters_in_lines(page)`. Upstream `main` **y hệt**. **Tôi phát hiện thêm**: 3 chỗ sort theo x **ngay trong** `_split_paragraph_into_lines` cũng bị comment (`:696`, `:738`, `:772`) — tức thứ tự ký tự trong dòng **hoàn toàn không được đảm bảo**, mạnh hơn cả cảnh báo của Expert. |
| Docstring "less than 2" vs code `count < 1` | ✅ **Đúng** — docstring `:660-662`, code `:727`. Upstream `main` **y hệt** (chưa ai sửa). |
| Ký tự space giữ `visual_bbox` cao bằng font_size | ✅ **Đúng** — `il_creater.py:1048-1054` gán `visual_bbox` mặc định = `char.bbox` dịch theo descent; `:1092-1108` chỉ **thay** bằng bbox glyph khi `volume > 1`. Space không có glyph → `volume` = 0 → **giữ nguyên box cao bằng cả font_size**. |
| `scale < 0.7` mới kích hoạt giãn khung | ✅ **Đúng** — `typesetting.py:1017`. |
| Sau khi giãn khung thành công vẫn giữ scale thấp | ✅ **Đúng, và tệ hơn Expert mô tả** — `:1036-1037` và `:1055-1056` `continue` giữ scale hiện tại; nhưng `:1060-1062` lại **reset `scale = 1.0` đúng khi giãn khung THẤT BẠI**. Logic **bị đảo ngược**: thành công (khung to hơn, đáng thử lại từ 1.0) thì giữ scale thấp; thất bại (khung không đổi) thì reset về 1.0. |
| mode-scale tính theo `unit_count` toàn tài liệu | ✅ **Đúng, và mạnh hơn "side effect"** — `:892-935`: `all_paragraphs`/`all_scales` tích luỹ **qua mọi trang**, mỗi paragraph đóng góp `unit_count` phiếu; sau đó **mọi** paragraph có `optimal_scale > mode` bị **kẹp xuống bằng mode**. Một bảng nhiều ô nhỏ **kéo tụt văn xuôi toàn tài liệu**, không chỉ cùng trang. |

**Về "docstring nói 2 nên chủ đích ban đầu là 2"**: tôi **rút lại** kết luận này ở W2. Expert đúng —
với `_get_effective_y_bounds` có dead code và 4 lời gọi sort bị comment, đây rõ ràng là code thử
nghiệm dở dang; không thể suy ra chủ đích từ docstring, và không có git blame để chốt. Nó là **dấu
hiệu** đáng nghi, **không phải bằng chứng**.

##### X2-d. Verify claim Bug #8

Đo trên `page_number == 1` của golden dump (trang chứa TABLE 4.2):

| Claim | Kết quả |
|---|---|
| 77 ô bảng mang nhãn `fallback_line`, **không** ô nào nhãn `table` | ✅ **Đúng chính xác** — lọc paragraph có tâm nằm trong box layout `table`: được **đúng 77** paragraph, tập nhãn = `{'fallback_line'}`. **Spec W6 của tôi ("gom các ô theo vùng layout `table`" hiểu là gom theo nhãn paragraph) sẽ gom được 0 ô.** |
| Vẫn có căn cứ hình học để gom nhóm | ✅ **Có** — `page.page_layout` **có** entry `class_name == "table"`, `id=1`, box `(87.0, 252.0)-(583.0, 741.0)`. Phải gom theo **chứa trong box này**, không theo `paragraph.layout_label`. |
| 3 cụm cột x ≈ 96-97 / 241-242 / 432-433 | ✅ **Đúng** — cluster: x~96.2–97.3 (n=14), x~241.1–242.3 (n=31), x~431.8–433.3 (n=32). |
| Cột 2/3 còn thừa ~70–75pt ngang | ✅ **Đúng về hướng, số còn LỚN HƠN** — slack tới ô kế bên cùng hàng (hoặc mép bảng): median **cột 2 = 109.7pt**, **cột 3 = 98.1pt**. |
| Cột 1 "gần như dùng hết chỗ ngang" | ⚠️ **Chỉ đúng một phần** — median slack cột 1 = **51.8pt**, min toàn bảng = 12.2pt (nằm ở cột 1). Cột 1 chật **hơn** cột 2/3 nhưng **không hết chỗ**. Kỳ vọng cải thiện của (8a) nên bao gồm cả cột 1, chỉ là biên độ nhỏ hơn. |

**Phát hiện riêng của tôi — chặn một sai lầm trong roadmap đo đạc**: `paragraph.scale` và
`optimal_scale` là `None` ở **mọi** IL dump (`paragraph_finder`, `layout_generator`,
`styles_and_formulas`, `il_translated`, `add_debug_information` — kiểm tra cả 1230 paragraph).
Typesetting tính scale **trong bộ nhớ** rồi ghi thẳng ra PDF, **không persist vào IL**. Con số
`0.45` ở W6 đến từ **đo cỡ chữ trong PDF output production**, không phải từ dump. ⇒ **Bước đo
histogram của Bug #8 KHÔNG thể làm từ IL dump**; phải hoặc (i) đo font size trong PDF output bằng
pymupdf, hoặc (ii) instrument `typesetting.py` để log `optimal_scale`. Nếu không ghi rõ, Dev sẽ mất
thời gian tìm một field không tồn tại.

#### X3. Cơ chế thật của Bug #7 (thay thế mô tả ở W2)

Mô tả cũ ở W2 — "ký tự đuôi `g` trong *Sugar* bắc cầu qua khe giữa 2 dòng" — **đúng hiện tượng
quan sát được nhưng sai nguyên nhân gốc**. Cơ chế thật:

1. Ký tự **khoảng trắng** không có glyph ⇒ `il_creater.py` giữ `visual_bbox` mặc định **cao đúng
   bằng `font_size`** (`:1092-1108`, chỉ thay khi `volume > 1`).
2. Với font 10.0pt và pitch dòng 12pt, mỗi space **lấp 10/12pt** chiều cao ⇒ khe hở thật giữa 2
   dòng chỉ còn **~2pt**.
3. Bất kỳ ký tự nào có descender (`g`, `y`, `p`, `q`, `j` — và **dấu tiếng Việt**) chọc vào 2pt còn
   lại là đủ để `count` không bao giờ về 0 ⇒ `gaps` rỗng ⇒ **cả paragraph gộp thành 1 `PdfLine`**.

Chữ `g` trong "Sugar" chỉ là **giọt nước tràn ly**. Đây là lý do đổi ngưỡng sang `<2` chỉ sửa được
những dòng có **đúng một** ký tự descender — phần lớn câu tiếng Anh có nhiều hơn một, và tiếng Việt
thì gần như luôn có dấu.

**Hệ quả cho fix**: loại ký tự trắng khỏi **phép đếm va chạm** trả lại khe hở thật ~10pt giữa các
dòng. Ký tự trắng **vẫn được gán vào đúng dòng của nó** theo tâm y như thường (không mất space),
chỉ là không được bỏ phiếu vào việc "có khe hở hay không". Vì thế nó **không** mang rủi ro dòng-1-ký-tự
như `count<2`.

#### X4. Điểm tôi bổ sung thêm ngoài phản biện của Expert

**X4-1. Vector kỹ thuật để áp patch — chưa ai nêu, và nó quyết định effort.**
App gọi babeldoc **qua subprocess CLI** (`BabeldocRunner(executable="babeldoc")`,
`asyncio.create_subprocess_exec`), **không** import babeldoc trong process của app; babeldoc cài
bằng `uv tool` ở venv **riêng**, không phải dependency trong `pyproject.toml`. ⇒ **Monkey-patch
thuần Python trong code app sẽ KHÔNG có tác dụng.** Ba vector khả thi, theo thứ tự ưu tiên:

- **(V1) `sitecustomize.py` shim qua `PYTHONPATH`** (khuyến nghị): đặt một thư mục shim trong repo,
  truyền `PYTHONPATH=<shim_dir>` vào `env` của subprocess. CPython tự import `sitecustomize` lúc
  khởi động; shim cài một `meta_path` hook, đợi module `…midend.paragraph_finder` được import xong
  rồi thay `_split_paragraph_into_lines`. Không đụng file trong venv của tool, gỡ ra chỉ cần bỏ
  biến môi trường, và **tự vô hiệu hoá an toàn** nếu đường dẫn module đổi ở version sau.
- **(V2) Thêm `babeldoc` thành dependency của app** rồi chạy `python -m <wrapper>` thay vì binary
  `babeldoc`. Sạch hơn về mặt kiểm soát version, nhưng kéo toàn bộ cây phụ thuộc nặng của babeldoc
  vào app venv — cần cân nhắc riêng, **không làm trong scope này**.
- **(V3) Vendor/patch file trong venv của tool** — **loại bỏ**: mất khi `uv tool upgrade`, không tái
  lập được trên máy khác, vi phạm tinh thần Protocol 5 (bind cứng vào một bản cài cục bộ).

⇒ Chốt **V1**. Shim phải **fail-safe**: nếu không patch được (đổi tên hàm/module ở version khác),
**log cảnh báo và chạy tiếp với hành vi gốc**, tuyệt đối không crash job. Và phải có một
**assertion version**: shim chỉ áp dụng khi `babeldoc.__version__ == "0.6.4"`; version khác → log
cảnh báo, không patch (Protocol 5 mục 5: đổi version ⇒ verify lại contract).

**X4-2. Không đồng ý hoàn toàn về "cột 1 hết chỗ"** — xem X2-d, median slack cột 1 vẫn 51.8pt.

**X4-3. Bổ sung ràng buộc đo cho Bug #8** — scale không có trong IL dump (X2-d). Bước 1 của roadmap
Bug #8 phải nêu rõ công cụ đo, nếu không sẽ tắc.

**X4-4. Về yêu cầu tự sort theo x của Expert cho B-2b**: đồng ý, và **mạnh hơn** — không chỉ
`_sort_characters_in_lines` ở `:305` bị tắt, mà cả 3 lời gọi sort **bên trong** chính
`_split_paragraph_into_lines` (`:696`, `:738`, `:772`) cũng bị comment. Wrapper B-2b **bắt buộc**
tự sort theo `visual_bbox.box.x` trước khi ghép chuỗi tìm marker. Ghi vào spec trước khi giao Dev.

#### X5. QUYẾT ĐỊNH CUỐI — Bug #7

**D7-1. CHẤP NHẬN fix của Expert; RÚT LẠI B-2a.**
Sửa: **loại ký tự trắng khỏi phép đếm va chạm**, **giữ nguyên ngưỡng `count < 1`**. Ký tự trắng vẫn
được phân vào dòng theo tâm y như cũ. Không đổi ngưỡng — `count<2` đã được chứng minh (X2-b) là hồi
quy thật với dòng 1 ký tự trong bảng số.

**D7-2. Vector: V1 (sitecustomize shim qua `PYTHONPATH`)**, fail-safe + gate version `0.6.4` (X4-1).

**D7-3. Thứ tự bắt buộc — có dependency, không được đảo:**

| Bước | Nội dung | Gate trước khi qua bước sau |
|---|---|---|
| **7.0** | Spike: shim V1 patch được thật, `--debug` trên p74–77 sinh IL mới | Số `pdf_line` trong IL mới khớp ground truth **≥ 161/163**; job chạy xanh; shim tắt được bằng env |
| **7.1** | Ship fix tầng dòng (D7-1) | Chạy lại **cả 4 trang lần này VÀ 7 trang của nghiên cứu Q2**; đọc **nội dung** PDF output (R6-03), không tin `status` |
| **7.2** | Ca A — tách numbered-list theo marker tăng dần (B-2b) | **Chỉ bắt đầu sau khi 7.1 xanh.** Wrapper tự sort theo x (X4-4). Phải loại được false-positive kiểu `"2 cups"` trong công thức |
| **7.3** | Ca C — mục lục: **chưa code gì**, chỉ **đo lại** sau 7.1 | Đọc nội dung thật trang Contents; đo **cả 2 chiều**: cấu trúc tốt lên **và** tỷ lệ cắt nhầm caption (RC-1) — ✅ **Đã đo (2026-09-07)**, xem CHANGELOG.md "bước 7.3 (Ca C, mục lục)". Kết quả: (1) cấu trúc **KHÔNG cải thiện** — Ca C vẫn còn nguyên (7.1/7.2 không chạm tới, marker của B-2b ở đầu dòng, TOC có số trang ở cuối dòng); verify sống qua dịch thật cho thấy tác hại rõ (nhiều mục TOC bị trộn lẫn thành 1 câu chạy dài). (2) RC-1: **không hồi quy**, có 1 phát hiện MỚI ngoài Ca A/B/C — 7.1 vô tình sửa luôn lỗi heading 2 dòng bị đảo lộn ký tự chéo nhau (cùng root cause X3). **Ca C cần thiết kế fix riêng (heuristic theo marker cuối dòng, không phải B-2b) — chưa làm, chờ PM/user quyết định.** |

**D7-4. Effort ước lượng**: 7.0 + 7.1 ≈ **0.5–1 ngày** (logic lõi ~15 dòng; phần lớn công là shim
+ test lineage + đo 11 trang). 7.2 ≈ **1–1.5 ngày** (heuristic marker + chống false-positive).
7.3 ≈ **2–3 giờ** (thuần đo).

**D7-5. Test bắt buộc (Protocol 6 R6-02)**: test không được chỉ assert "đã gọi". Phải có test chạy
hàm tách dòng đã patch **trên golden fixture** `paragraph_finder_p74_77_dump.json.gz` và assert
**số dòng cụ thể** của các paragraph đã liệt kê ở bảng X2 (ví dụ `1. Explain…` phải ra **3** dòng,
`■ To demonstrate…` phải ra **6**). Bảng X2 chính là **oracle** cho test này.

#### X6. QUYẾT ĐỊNH CUỐI — Bug #8

**D8-1. RÚT LẠI hoàn toàn đề xuất "đồng bộ scale toàn vùng bảng về MIN".**
Lập luận của tôi ở W6 ("không tạo tràn chữ mới vì không ô nào bị phóng to") đúng hình học nhưng sai
mục tiêu: MIN của TABLE 4.2 là **0.45** ⇒ **cả 77 ô xuống 4.05pt**, không đọc được. Nó biến một vấn
đề cục bộ (vài ô xấu) thành hỏng **toàn bảng** — tệ hơn cả sàn cứng 0.7 mà chính tôi lo ngại.
Expert đúng.

**D8-2. Chấp nhận hướng của Expert: sửa nguyên nhân gốc (babeldoc bỏ phí chỗ trống ngang) trước,
chính sách sàn sau.**

| Bước | Nội dung | Gate |
|---|---|---|
| **8.1** | **Đo trước khi code.** Histogram scale trên **≥ 5 trang có bảng**, tách số liệu **theo từng cột**, kèm slack ngang mỗi ô. **Công cụ: đo font size trong PDF output bằng pymupdf, HOẶC instrument `typesetting.py` — KHÔNG có trong IL dump (X2-d).** | Có histogram thật; ước lượng được (8a) cứu được bao nhiêu % ô |
| **8.2** | **(8a) Nới khung ô TRƯỚC khi babeldoc tìm scale.** Với mỗi paragraph có tâm nằm trong box layout `class_name == "table"` (**gom theo hình học, KHÔNG theo `layout_label`** — X2-d), đặt lại `box.x2` = mép trái ô kế bên cùng hàng (hoặc `get_max_right_space`) trừ đệm; rồi để babeldoc tìm scale **từ 1.0 trên khung mới** | Cột 2/3 đạt scale ~1.0; **không** ô nào tràn sang ô bên cạnh — kiểm tra bằng mắt trên PDF output |
| **8.3** | **(8b) Đồng đều scale theo TỪNG CỘT + sàn**, sàn chọn **từ histogram 8.1** (tham chiếu khởi đầu ~0.67 ≈ 6pt với font gốc 9pt, **không phải kết luận**). Ô cần thấp hơn sàn → **giữ bằng sàn** và **ghi flag `layout_qa_findings` NGAY TRONG CÙNG lần implement này** | Không ô nào < sàn mà không có flag |

Đơn vị đồng đều hoá là **cột**, không phải bảng — mắt người so cỡ chữ dọc theo cột, và nó chặn được
đúng rủi ro "1 ô xấu kéo cả bảng".

**D8-3. Sàn và flag KHÔNG được tách làm 2 giai đoạn.** Sàn không kèm flag = đổi một lỗi im lặng lấy
một lỗi im lặng khác — đúng bài học Bug #6.

**D8-4. Effort**: 8.1 ≈ **0.5 ngày** (viết harness đo, không có sẵn field ⇒ tốn hơn dự kiến ban đầu).
8.2 ≈ **1 ngày**. 8.3 ≈ **0.5–1 ngày**.

**D8-5. Không đổi engine.** pdf2zh không giảm `size` mà chỉ giảm `line_height` rồi để chữ tràn ⇒
không mắc Bug #8 nhưng mắc nhóm lỗi T (chồng/tràn chữ) đã biết. Đây không phải lý do đổi default.
*(Nguồn: Expert đọc `converter.py`; **tôi chưa tự verify**, và nó không ảnh hưởng quyết định.)*

#### X7. Tương tác Bug #7 ↔ Bug #8 — ràng buộc thứ tự

Fix tầng dòng đổi số dòng/paragraph ⇒ đổi `unit_count` ⇒ đổi mode-scale toàn tài liệu
(`typesetting.py:892-935`, kẹp **xuyên trang**) ⇒ **mọi số đo của Bug #8 trước fix #7 đều hết hạn**.

⇒ **Bước 8.1 (đo histogram) BẮT BUỘC chạy SAU bước 7.1.** Đo trước sẽ phải đo lại. Và lần đo sau
7.1 phải bao cả **11 trang** (4 trang lần này + 7 trang Q2), đo đồng thời **3 chiều**: cấu trúc list,
tỷ lệ cắt nhầm caption (RC-1), và histogram scale.

#### X8. Báo cáo upstream babeldoc

Nên report (tinh thần P2.2), nhưng **theo đúng cơ chế thật**, không theo hướng "docstring nói 2":

1. Ký tự khoảng trắng không có glyph được gán `visual_bbox` cao bằng cả `font_size`
   (`il_creater.py:1092-1108`) ⇒ lấp khe giữa các dòng ⇒ `_split_paragraph_into_lines` gộp nhầm.
   Số đo: **147 → 161 / 163** paragraph đúng, 0 hồi quy.
2. `_get_effective_y_bounds` (`paragraph_finder.py:608-613`) có dead code sau `return`.
3. Logic **đảo ngược** ở `typesetting.py:1036-1062`: giãn khung **thành công** thì giữ scale thấp,
   **thất bại** thì reset `scale = 1.0`.

Đính kèm script tái tạo (X9) + golden fixture. **Không chờ phản hồi upstream để đóng task nào.**

#### X9. Script tái tạo số liệu

Không commit thành file `.py` trong repo (Protocol 7: mọi file code phải qua Reviewer; commit này
là docs + fixture). Dev tái tạo bằng cách chép khối dưới đây ra file tạm rồi chạy bằng python có
numpy. Nó **chính là** oracle cho test ở D7-5.

- Đọc fixture: `gzip.open("tests/fixtures/babeldoc/paragraph_finder_p74_77_dump.json.gz", "rt")`.
- Lọc paragraph: bỏ paragraph có composition `pdf_same_style_unicode_characters.debug_info` (chú
  thích debug của babeldoc); gom ký tự từ `pdf_line` / `pdf_formula` / `pdf_character` /
  `pdf_same_style_characters`; **bỏ ký tự có `pdf_character_id is None`** (space dummy chèn SAU bước
  thread); giữ paragraph có ≥ 2 ký tự ⇒ **163 paragraph**.
- Thuật toán: sao đúng `_compute_collision_counts_histogram` (difference array, `step=0.25`), dùng
  `visual_bbox.box.y/.y2`; `(ymax-ymin) < 5` ⇒ 1 dòng; gap khi `count < 1`; separator = `y` tại
  index bắt đầu mỗi gap; gán ký tự theo tâm y.
- 3 biến thể: (a) nguyên trạng; (b) `count < 2`; (c) loại ký tự trắng khỏi mảng `y1/y2` đưa vào
  histogram, giữ `count < 1`.
- Ground truth: cluster `char.box.y` của ký tự **có mực**, dung sai **3pt**.
- Kỳ vọng: fidelity **162/163**; đúng **147 / 149 / 161**; hồi quy **0 / 0**.

#### X10. Bảng trạng thái verify (Protocol 5 R5-01) — cập nhật

| Claim | Trạng thái |
|---|---|
| Con số 147 / 149 / 161 trên 163 của Expert | ✅ **Verified** — replication độc lập trên golden fixture (X2) |
| Cơ chế thật = space không glyph, `visual_bbox` cao bằng font_size | ✅ **Verified** — `il_creater.py:1048-1054, 1092-1108` |
| `count<2` gây hồi quy với dòng 1 ký tự | ✅ **Verified** — ca tổng hợp X2-b, 2/2 sai |
| Ca A cũng hỏng từ tầng dòng (⇒ B-2b phụ thuộc 7.1) | ✅ **Verified** — 2 paragraph numbered-list, gt=3 → cur=1 |
| Phạm vi lỗi gồm cả văn xuôi, không chỉ list | ✅ **Verified** — 6 paragraph văn xuôi, nặng nhất 7 dòng → 1 |
| Dead code trong `_get_effective_y_bounds` | ✅ **Verified** — `:608-613` + upstream `main` |
| Lời gọi sort bị comment (`:305`, `:696`, `:738`, `:772`) | ✅ **Verified** — + upstream `main` |
| 77 ô bảng nhãn `fallback_line`, 0 ô nhãn `table` | ✅ **Verified** — golden fixture, page_number 1 |
| Có box layout `class_name == "table"` để gom theo hình học | ✅ **Verified** — id=1, `(87,252)-(583,741)` |
| Slack ngang cột 2 = 109.7pt, cột 3 = 98.1pt (median) | ✅ **Verified** — golden fixture |
| "Cột 1 gần như hết chỗ" | ⚠️ **Sai một phần** — median slack 51.8pt (X2-d) |
| `scale`/`optimal_scale` KHÔNG có trong mọi IL dump | ✅ **Verified** — 1230 paragraph, 5 dump, 0 giá trị |
| mode-scale kẹp xuyên trang theo `unit_count` | ✅ **Verified** — `typesetting.py:892-935` |
| Logic reset scale bị đảo khi giãn khung | ✅ **Verified** — `typesetting.py:1036-1062` |
| Shim V1 (`PYTHONPATH` + `sitecustomize`) patch được babeldoc subprocess | ✅ **Verified** — spike 7.0 + ship 7.1 (xem "Bug #7 fix — bước 7.0+7.1" trong CHANGELOG.md), job chạy xanh sống nhiều lần |
| B-2b heuristic marker tăng dần không false-positive | ✅ **Verified** (7.2, 2026-09-07) — spike sống (R5-02): quét TOÀN BỘ text thật trên 2 fixture ("QUESTIONS FOR REVIEW" 1-17, "EQUIPMENT AND SMALLWARES" 35-mục, gồm cả các dòng có số lượng như `"1½ quart"`, `"2- and 4-quart sizes"`) — 0 false-positive. Live E2E qua đúng `BabeldocRunner.translate_pages()` với DeepSeek thật (R6-03): 35/35 và 17/17 mục xuống dòng đúng, 0 ca dính chữ, 0 mất nội dung. Xem CHANGELOG.md "Bug #7 fix — bước 7.2 (Ca A)". |
| (8a) nới khung không gây tràn sang ô bên cạnh | ⚠️ **`[UNVERIFIED]`** — spike 8.2 |
| Giá trị sàn cụ thể (~0.67 chỉ là tham chiếu) | ⚠️ **`[UNVERIFIED]`** — phải chốt từ histogram 8.1 |
| pdf2zh không giảm `size`, chỉ giảm `line_height` | ⚠️ **`[UNVERIFIED]`** — Expert đọc source, tôi chưa tự verify; không ảnh hưởng quyết định |

**Trạng thái**: quyết định đã chốt, **vẫn chưa có dòng code nào được viết**. Việc tiếp theo là
**spike 7.0** (shim V1) — cần PM/user duyệt trước khi giao Dev (Protocol 2).

---

### Bug #7 Ca C — Đề xuất thiết kế fix mục lục (Tech Lead, 2026-09-07)

> **TRẠNG THÁI: ĐỀ XUẤT, CHƯA CHỐT — chờ Domain Expert phản biện + PM/user duyệt.**
> Viết theo đúng văn phong/quy trình mục W6 cũ và section "Final Decision" (X0–X10) phía trên:
> Tech Lead đề xuất → Domain Expert phản biện → chốt. **Không được implement bất kỳ dòng nào
> của section này trước khi có bước phản biện + duyệt.** Mọi chỗ tôi chưa tự verify được đều
> gắn nhãn tường minh ở bảng Y12 để Expert biết chỗ cần đánh.
>
> Đây là bước **"7.4"** đã được D7-3 (dòng 7.3) nêu là *"Ca C cần thiết kế fix riêng (heuristic
> theo marker cuối dòng, không phải B-2b) — chưa làm, chờ PM/user quyết định."*

#### Y0. Phán quyết một dòng

Đề xuất **TOC-1**: tách paragraph tại các **dòng kết thúc bằng số trang** — nhận diện bằng
**khoảng hở hình học** giữa phần chữ và cụm chữ số cuối dòng (chuẩn hoá theo `font_size`), cộng
với một **cổng cố kết ở mức paragraph** (phải có ≥ 2 dòng cùng dạng và chiếm ≥ 60% số dòng của
paragraph). Dùng lại **đúng cơ chế shim V1** đã ship ở 7.1/7.2, nhưng **hook ở điểm khác** (bọc
`process_independent_paragraphs` thay vì bọc `process`) — lý do ở Y6.

Tôi đã **mô phỏng luật này trên IL dump thật** (không suy đoán): trên 2 trang Contents của Figoni
nó tách đúng **20/20** paragraph mục lục (66 điểm tách mới), **0 ca tách nhầm**; trên 4 bộ dump
trang KHÔNG phải mục lục (55 paragraph nhiều dòng) nó **không kích hoạt lần nào**; quét thô toàn
bộ 6 đầu sách trong `data/uploads/` (~4657 block nhiều dòng chỉ riêng Figoni) nó cho **0 điểm
tách sai** — lần kích hoạt duy nhất ngoài Figoni là **trang mục lục của Le Cordon Bleu** (đúng ca
cần fix). Số liệu chi tiết ở Y2/Y7/Y8.

#### Y1. Nguồn xác thực (Protocol 5 R5-01) — mọi claim về babeldoc trong section này

Nguồn: babeldoc **0.6.4** đã cài thật tại
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/`
(cùng bản đang chạy production, cùng bản mà 7.1/7.2 gate version `"0.6.4"`). **Tôi đã tự đọc từng
dòng dưới đây trong task này**, không kế thừa từ section trước:

| Claim | Nguồn (file:line, đã đọc thật) |
|---|---|
| Thứ tự các bước trong `process_page` | `midend/paragraph_finder.py:235-310` — `:245` gán `page.pdf_paragraph = paragraphs`; `:275` gọi `_split_paragraph_into_lines` (7.1 vá ở đây); `:278-281` `add_space_dummy_chars` + `process_paragraph_spacing`; `:284` `calculate_median_line_width`; `:287` `process_independent_paragraphs`; `:290-291` `merge_alternating_line_number_paragraphs`; `:302` `fix_overlapping_paragraphs`; `:305` lời gọi sort theo x **bị comment**; `:307` `add_debug_info`; `:310` `_set_paragraph_render_order` |
| Nhánh mục lục dot-leader đòi ≥ 20 dấu chấm liên tiếp | `paragraph_finder.py:864-866` — `if re.search(r"\.{20,}", prev_text):` |
| Nhánh hình học + nhánh bullet chỉ nhìn `chars[0]` | `paragraph_finder.py:891-903` — `prev_width < median_width * short_line_split_factor` HOẶC `is_bullet_point(chars[0])` |
| Nguyên mẫu tách paragraph (tái dùng được nguyên xi) | `paragraph_finder.py:868-888` (nhánh dot-leader) và `:904-926` (nhánh hình học) — tạo `PdfParagraph(box=Box(0,0,0,0), pdf_paragraph_composition=comp[j:], unicode="", debug_id=generate_base58_id(), layout_label=…, layout_id=…)`, gọi `update_paragraph_data` cho **cả hai**, rồi `paragraphs.insert(i+1, new_paragraph)` + `break`; vòng ngoài `i += 1` sẽ **xét lại chính paragraph mới** ⇒ tách dây chuyền (cascade) là hành vi **có sẵn**, không cần tự viết vòng lặp |
| `is_bullet_point` chỉ khớp ký tự bullet, **không** nhận chữ số | `utils/layout_helper.py:50-52` (`BULLET_POINT_PATTERN`, tập ký tự không chứa `0-9`) + `:55-65` |
| `font_size` có thật trên từng ký tự | `il_version_1.py:627-638` (`PdfCharacter.pdf_style`) + `:584-610` (`PdfStyle`, `font_id` `:596`, `font_size: float` `:603`) |
| `visual_bbox.box.x/.x2` có thật trên từng ký tự | `il_version_1.py:646-651` (`PdfCharacter.visual_bbox`) + `:613-623` (`VisualBbox.box`) |
| `merge_alternating_line_number_paragraphs` **KHÔNG** gộp lại được các paragraph mục lục vừa tách | `paragraph_finder.py:393-418` chỉ gộp `a` với `c` khi **mọi** paragraph nằm giữa là "thuần chữ số/khoảng trắng" theo `_is_ascii_digit_or_space_paragraph` (`:368-380` — gặp 1 ký tự không phải digit/space là `return False`). Paragraph mục lục luôn có chữ ⇒ `saw_l` không bao giờ True ⇒ không gộp. Thêm một lớp nữa: `_same_layout_and_xobj` (`:382-391`) đòi **cả hai** `xobj_id is not None` |
| Paragraph tạo sau khi `process()` kết thúc sẽ có `render_order = None`, và điều đó **không crash** | `paragraph_finder.py:310` gọi `_set_paragraph_render_order` (định nghĩa `:312-347`) **bên trong** `process_page`; `typesetting.py:1664-1670` `_update_paragraph_render_order` `return` ngay khi `paragraph.render_order is None` |

**Không có claim nào trong section này được viết từ trí nhớ.** Chỗ nào tôi chưa verify được đều
nằm ở bảng Y12 với nhãn `[UNVERIFIED]`.

#### Y2. Dữ liệu thật đã đo trong chính task này (cơ sở của mọi con số)

**Nguồn dữ liệu** (tái sử dụng đúng artifact của bước 7.3, không dựng mới):

- IL dump trang Contents (đã có shim 7.1+7.2 bật): `/tmp/bdprobe/wd_toc/figoni_p7_toc/paragraph_finder.json`,
  `/tmp/bdprobe/wd_toc2/figoni_p8_toc/paragraph_finder.json`.
- IL dump 4 bộ trang **KHÔNG** phải mục lục (đối chứng): `/tmp/bdprobe/wd74c/p74_77/`,
  `/tmp/bdprobe/wd72c/page14_numbered_list_source/`, `/tmp/bdprobe/wd_p20/figoni_p20/`,
  `/tmp/bdprobe/wd_p22/figoni_p22/`.
- PDF gốc 6 đầu sách khác nhau trong `data/uploads/` (Figoni bản đầy đủ ~400 trang, Figoni 1-25,
  Bo Friberg, Woodhead, Le Cordon Bleu, `qa_aimd_65pages`).

⚠️ Các dump `/tmp/bdprobe/**` là **artifact tạm của phiên trước, không commit**. Nếu PM duyệt đi
tiếp, **Dev bắt buộc phải sinh lại + commit golden fixture** cho 2 trang Contents theo đúng
Protocol 5 mục 3 (xem Y11 bước 7.4-a) — **tuyệt đối không viết tay mock theo bảng số dưới đây**.

**Cấu trúc thật của mục lục Figoni** (đọc từ IL, ký tự đã sort theo x):

```
para#105  label='plain text'  8 dòng — MỘT paragraph gộp 8 mục TOC:
  [x=354.5 x2=508.9] 'Commercial Grades of White Flours   77'
  [x=354.1 x2=484.1] 'Types of Patent Wheat Flours    79'
  … (6 dòng nữa) …
  [x=354.8 x2=473.6] 'Exercises and Experiments    89'
```

Bốn quan sát **quyết định thiết kế**, tất cả đều đo được:

1. **Số trang KHÔNG căn phải.** `x2` chạy từ 416.8 tới 513.0 trong cùng một cột ⇒ **không dùng
   được tín hiệu "cột số căn phải"**. Đây là lý do tôi loại hướng thiết kế "phát hiện cột số bên
   phải" ngay từ đầu (Y5-c).
2. **Khoảng trắng giữa tên mục và số trang là DUMMY, không có trong PDF gốc.** Mọi ký tự trắng
   trong khe đó có `pdf_character_id is None` ⇒ do `add_space_dummy_chars` (`:279`) chèn vào, **số
   lượng space là sản phẩm phụ của heuristic babeldoc**, không phải dữ liệu gốc. ⇒ **Không được
   xây luật trên "đếm ≥ N khoảng trắng"**; phải đo **khoảng hở hình học**.
3. **Khoảng hở hình học rất ổn định và rất lớn**: gap = 9.0pt trên font 9.0pt ⇒ **tỷ lệ đúng
   1.00** (median trên 57 dòng của trang 6 và 78 dòng của trang 7, đo bằng PyMuPDF `rawdict`).
   Dòng tiêu đề chương (`'OF FOOD   49'`, font 14pt) có tỷ lệ **2.0**. Trong khi đó khoảng cách
   từ chuẩn giữa 2 từ ≈ 0.25–0.35 em, và ca văn xuôi tệ nhất tìm được trong cả cuốn sách là
   **0.64**. ⇒ Có một **khe an toàn rộng** giữa hai phân bố.
4. **Mục TOC có thể xuống dòng**, và **tiêu đề chương chiếm 2 dòng với số ở dòng cuối**:
   - `['Flour and Dough Additives and', 'Treatments    72']` — 1 mục, 2 dòng.
   - `['SENSORY PROPERTIES', 'OF FOOD   49']` — 1 tiêu đề chương, 2 dòng.
   ⇒ Luật **bắt buộc** phải tách **SAU** dòng có số trang (không phải "tách trước mọi dòng"),
   nếu không sẽ xé đôi chính 2 ca này. Đây là ràng buộc thiết kế cứng, không phải tinh chỉnh.

#### Y3. Vì sao cả 3 lớp của babeldoc đều chết trên trang này (xác nhận lại, có nguồn)

| Lớp | Điều kiện | Vì sao chết |
|---|---|---|
| Dot leader (`:864-866`) | `re.search(r"\.{20,}", prev_text)` | TOC Figoni **không dùng dot leader** — 0 dấu chấm |
| Hình học (`:891-895`) | `prev_width < median_width × 0.8` | Trang toàn dòng TOC ⇒ **chính chúng là median** ⇒ điều kiện gần như không bao giờ đúng (đã ghi ở W3) |
| Bullet (`:896-903`) | `is_bullet_point(chars[0])` | Marker của TOC là **số trang ở CUỐI dòng**; `chars[0]` là chữ cái đầu tên mục. `BULLET_POINT_PATTERN` (`layout_helper.py:50-52`) **không chứa `0-9`** nên kể cả đảo ngược cũng vô nghĩa |
| 7.1 (đã ship) | Sửa tầng **tách dòng** | Các dòng TOC vốn đã tách đúng — 7.1 đo được **byte-for-byte không đổi** trên 2 trang này (CHANGELOG 7.3) |
| 7.2 / B-2b (đã ship) | Marker số ở **ĐẦU** dòng | TOC không có marker đầu dòng ⇒ `extract_leading_marker` trả `None` ngay ở dòng neo ⇒ **không bao giờ kích hoạt** |

⇒ Ca C là một **lỗ hổng độc lập**, không phải phần dư của 7.1/7.2.

#### Y4. Đề xuất chính — **TOC-1**: tách theo marker số trang ở CUỐI dòng

Toàn bộ quyết định "có tách không / tách ở đâu" nằm trong **một module thuần Python**
(`src/babeldoc_shim/toc_split.py`, không import babeldoc) — **dùng chung** bởi `sitecustomize.py`
và test, đúng khuôn mẫu `numbered_list_split.py` của 7.2 (Protocol 6 R6-02: test phải gọi đúng
logic production, không chép tay thuật toán).

**Bước 1 — trích đặc trưng từng dòng** (input: danh sách `(x, x2, char_unicode, font_size)` của
các ký tự trong `pdf_line`, **đã tự sort theo x** — bắt buộc, vì cả 4 lời gọi sort của babeldoc
đều bị comment, `paragraph_finder.py:305,696,738,772`, xem X4-4):

1. Bỏ mọi ký tự `.isspace()` (gồm cả dummy space — xem Y2 điểm 2).
2. Lấy **dãy chữ số liền cuối** (`str.isdigit()`), độ dài `k`. Loại nếu `k == 0`, `k > 4`, hoặc
   `k == len(chars)` (cả dòng chỉ là số ⇒ đây là số trang chân trang / ô bảng số, **không phải**
   mục TOC).
3. `gap = x(chữ số đầu tiên của dãy) − x2(ký tự có mực cuối cùng của phần thân)`.
4. `size = font_size` của ký tự ngay trước khe (`PdfStyle.font_size`, `il_version_1.py:603-610`).
5. Đánh dấu dòng là **"đuôi mục TOC"** khi **tất cả** đúng:
   - `gap ≥ TOC_GAP_RATIO × size` (đề xuất `TOC_GAP_RATIO = 0.8`);
   - phần thân chứa **≥ `TOC_MIN_BODY_WORDS` cụm chữ cái dài ≥ 2** (đề xuất `= 1`) ⇒ loại ô bảng
     thuần số, loại `"4.0"`, `"120"`;
   - `1 ≤ số ≤ 9999`.

**Bước 2 — cổng cố kết ở mức paragraph** (đây mới là lớp chống false-positive chính, **không phải**
regex):

- `m` = số dòng được đánh dấu, `L` = số composition của paragraph.
- Chỉ tách khi `m ≥ TOC_MIN_TAIL_LINES` (đề xuất `= 2`) **VÀ** `m / L ≥ TOC_MIN_TAIL_FRACTION`
  (đề xuất `= 0.6`).
- **Bổ sung, đề xuất bật**: dãy số trang của các dòng được đánh dấu phải **không giảm**
  (`n[i] ≤ n[i+1]`). Đo thật: **20/20** paragraph mục lục thoả (`[38,39,40,40]`,
  `[77,79,82,84,86,87,88,89]`, `[4,5,6,7,8,9,10,10,11]`, `[219,224,225,226,226]`…). Phải cho
  phép **bằng nhau** — mục lục thật có `[2,2,3]` và `[194,194,195,196]`. Nếu luật này sai trên
  sách khác, hậu quả là **không tách** (giữ nguyên hiện trạng), **không phải** tách sai — đây là
  hướng thất bại an toàn.

**Bước 3 — điểm tách**: mọi dòng được đánh dấu **mà không phải dòng cuối** ⇒ ranh giới nằm **NGAY
SAU** dòng đó. Đây chính là điều làm cho `['Flour and Dough Additives and', 'Treatments 72']` và
`['SENSORY PROPERTIES', 'OF FOOD 49']` **không bị xé** (dòng có số là dòng cuối ⇒ 0 điểm tách).

**Bước 4 — thực thi**: cắt `pdf_paragraph_composition` theo các nhóm, nhóm đầu giữ nguyên
paragraph gốc, mỗi nhóm sau tạo `PdfParagraph` mới **đúng theo nguyên mẫu `:868-888`** (copy
`layout_label`, `layout_id`, gọi `update_paragraph_data` cho cả hai). Composition **không phải**
`pdf_line` (`pdf_formula`, `pdf_character`) ⇒ không bao giờ được đánh dấu, dính vào nhóm liền
trước — giống hệt cách 7.2 xử lý.

#### Y5. Ba hướng thay thế — và vì sao tôi loại

- **(a) Nới nhánh dot-leader** (`\.{20,}` → `\.{3,}`): **không giải quyết được Ca C** (TOC Figoni
  có **0** dấu chấm), đồng thời tăng rủi ro với dấu ba chấm/ellipsis trong văn xuôi. **Loại làm
  giải pháp chính.** Nhưng đề xuất **giữ lại như một tín hiệu PHỤ** (TOC-1b): nếu phần thân kết
  thúc bằng ≥ 3 dấu chấm liên tiếp (hoặc ≥ 3 cặp `. `), coi như thoả điều kiện `gap` — để cùng
  một luật phục vụ được cả TOC có dot leader thưa (< 20 chấm) mà babeldoc đang bỏ lọt. **Đề xuất
  để TẮT mặc định ở v1**, chỉ bật sau khi đo được trên một cuốn có dot leader thật (Y12).
- **(b) Hạ `short_line_split_factor`**: đã chứng minh là **ngõ cụt cấu trúc** ở W3 — trên trang
  toàn dòng ngắn, chính chúng là median. Không giá trị nào chữa được. **Loại.**
- **(c) Nhận diện "cột số căn phải"** (gom các số cùng `x2`): **sai ngay trên dữ liệu thật** —
  `x2` của Figoni chạy 416.8 → 513.0 (Y2 điểm 1). **Loại.**
- **(d) Nhận diện "trang này là trang mục lục" rồi mới áp luật** (ví dụ tìm chữ "Contents" trên
  trang): **loại** — phụ thuộc ngôn ngữ/nhan đề, và mục lục thường tràn nhiều trang mà chỉ trang
  đầu có tiêu đề. Cổng cố kết ở Y4 bước 2 đã đóng vai trò "đây có phải khối mục lục không" ngay
  ở mức paragraph, **không cần biết trang nào là trang gì** — quan trọng, vì babeldoc xử lý toàn
  bộ IL và **không có khái niệm "trang mục lục"**.

#### Y6. Điểm hook — đề xuất **KHÁC** 7.2, và đây là điểm tôi muốn Expert soi kỹ nhất

7.2 bọc `ParagraphFinder.process` và chạy **sau khi `process()` kết thúc hoàn toàn**. Với TOC-1
tôi đề xuất hook **sớm hơn**: bọc `ParagraphFinder.process_independent_paragraphs(paragraphs,
median_width)` (`:841`) — chạy hàm gốc trước, rồi chạy TOC-1 trên **cùng list `paragraphs`** (hàm
gốc cũng mutate in-place bằng `paragraphs.insert`, và `page.pdf_paragraph` trỏ tới **cùng object
list**, gán ở `:245`).

Lý do (3 cái, đều có nguồn ở Y1):

1. **Paragraph mới sẽ được gán `render_order`**: `_set_paragraph_render_order` chạy ở `:310`,
   **sau** `:287`. Paragraph do 7.2 tạo (sau `process()`) hiện có `render_order = None` ⇒
   `typesetting._update_paragraph_render_order` (`:1664-1670`) `return` ngay, **bỏ qua việc chuẩn
   hoá render order cho mọi ký tự của paragraph đó**. Không crash, nhưng là một **sai khác âm
   thầm mà 7.2 đang mang sẵn** — tôi phát hiện trong task này, xem Y10-b.
2. **Paragraph mới sẽ có debug rectangle**: `add_debug_info` (`:307`, chỉ chạy khi `--debug`) —
   giúp chính việc đo/QA của chúng ta nhìn thấy ranh giới mới.
3. **Đúng tầng ngữ nghĩa**: `process_independent_paragraphs` **chính là** hàm babeldoc dành cho
   "tách paragraph theo marker", và nhánh mục lục (dot leader) của nó cũng ở đó. TOC-1 là **anh
   em cùng tầng** với nhánh `:864-866`, không phải một pass ngoại lai.

Rủi ro của hook sớm hơn (đã tự kiểm và **loại được bằng đọc source**, không phải phỏng đoán):
`merge_alternating_line_number_paragraphs` chạy ngay sau ở `:290-291` — nhưng nó **không thể gộp
lại** các paragraph mục lục vừa tách, vì `_is_ascii_digit_or_space_paragraph` (`:368-380`) trả
`False` ngay khi paragraph có chữ cái, và `_same_layout_and_xobj` (`:382-391`) còn đòi cả hai
`xobj_id is not None`. ⇒ Không có nguy cơ "tách xong bị gộp lại".

**Không đề xuất di dời 7.2 sang hook này trong cùng task** — 7.2 đã qua live E2E, đổi hook là mở
lại một thứ đã verify. Ghi lại thành **tech debt** (Y10-b).

#### Y7. Rủi ro false-positive — tôi tự liệt kê, và số đo cho từng loại

Đây là phần tôi muốn bị phản biện mạnh nhất. Các loại nội dung **không phải TOC** mà vẫn có thể
kết thúc bằng số:

| # | Loại nội dung | Luật nào chặn | Đo thật |
|---|---|---|---|
| FP-1 | Văn xuôi kết thúc bằng số liệu (`"…contains about 15"`, `"…amount—about 75"`) | `gap ≥ 0.8×size` (khoảng trắng từ thường ≈ 0.25–0.35 em) **và** `m ≥ 2` trong cùng paragraph | Quét **toàn bộ** Figoni (~400 trang, 4657 block nhiều dòng): ở ngưỡng tuyệt đối `gap ≥ 4pt` có **3** ca (p83, p92, p340, gap 4.1–6.4pt); ở `ratio ≥ 0.5` còn **1**; ở **`ratio ≥ 0.8` còn 0**. Trên IL thật của 4 bộ trang đối chứng: **0** dòng khớp |
| FP-2 | Số trang chân trang / đầu trang (folio) đứng một mình | Loại bởi `k == len(chars)` (cả dòng là số) **và** `TOC_MIN_BODY_WORDS ≥ 1` | Quét thô ban đầu cho thấy folio là nguồn nhiễu lớn nhất (hàng trăm dòng); sau khi thêm 2 điều kiện này ⇒ **0** |
| FP-3 | Ô bảng số (`"4.0"`, `"120"`, `"3000"`) | Như FP-2, cộng `k ≤ 4` chữ số và phải là **dãy digit liền cuối** (`"4.0"` kết thúc bằng `0` nhưng thân là `"4."` ⇒ 0 cụm chữ cái ⇒ loại) | IL thật `p20`/`p22` (đúng 2 trang bảng đã dùng làm bằng chứng RC-1): **0 kích hoạt** |
| FP-4 | Bảng công thức bánh (`"Bread flour   100"`, `"Water   62"`) — **rủi ro thật, chưa loại được** | Không có luật nào chặn: mọi dòng đều có chữ + số cuối + khe rộng | ⚠️ **Chưa đo được** — chưa có trang công thức nào trong 11 trang đã dump IL. Xem Y12 và Y11 bước 7.4-a. **Lưu ý giảm nhẹ**: nếu bị tách, mỗi dòng công thức thành 1 paragraph riêng — với chất lượng dịch đây **có thể là cải thiện chứ không phải hỏng** (LLM hết trộn các dòng nguyên liệu vào nhau, đúng bản chất Ca C). Nhưng nó **đổi `unit_count`** ⇒ đụng mode-scale của Bug #8 (X7) ⇒ **phải đo, không được đoán** |
| FP-5 | Chú thích hình/bảng kết thúc bằng số (`"…xem Bảng 4.2"`) | Thân kết thúc bằng `"4."` + dãy `2` ⇒ khe giữa `.` và `2` = 0 ⇒ `gap` gần 0 ⇒ loại | IL `p20`/`p22`: **0** |
| FP-6 | Danh mục tài liệu tham khảo (`"J. Food Sci. 45"`) | `gap` là khoảng trắng từ thường ⇒ tỷ lệ ~0.25 ⇒ loại | Không có trang references trong mẫu ⇒ ⚠️ chưa đo, nhưng cơ chế chặn giống FP-1 |
| FP-7 | Index (`"Sugar, 45"`) | `gap` nhỏ (sau dấu phẩy) ⇒ loại. **Kể cả nếu khớp**, tách index thành từng mục là **đúng**, không phải hỏng | ⚠️ chưa đo |
| FP-8 | Danh sách bảng/hình ("List of Tables") | **Cố ý khớp** — đây là TOC biến thể, tách là **đúng mong muốn** | — |

**Ba tín hiệu tôi coi là đáng tin nhất, xếp theo độ mạnh** (trả lời trực tiếp yêu cầu của brief):

1. **Cổng cố kết `m ≥ 2` trong CÙNG một paragraph** — mạnh nhất. Một câu văn xuôi kết thúc ngẫu
   nhiên bằng số là chuyện có thật (3 ca / 400 trang); **hai dòng trong cùng một paragraph cùng
   kết thúc bằng số với khe rộng** thì trong toàn bộ dữ liệu đã đo là **0 ca ngoài mục lục**.
2. **Khe hình học chuẩn hoá theo font** — TOC = 1.0–2.0, văn xuôi tệ nhất = 0.64. Khe an toàn
   rộng. Chuẩn hoá theo `font_size` (không dùng pt tuyệt đối) là điều bắt buộc để luật còn đúng
   với sách cỡ chữ khác.
3. **Số trang không giảm** — 20/20 đúng trên dữ liệu thật; và khi sai thì thất bại theo hướng an
   toàn (không tách).

Tín hiệu tôi **cố ý KHÔNG dùng** và lý do: đếm số khoảng trắng (dummy, Y2-2); căn phải `x2` (sai
trên dữ liệu thật, Y2-1); "số trang tăng đều/liên tục" (mục lục thật nhảy cóc: `[15,21,22,22]`,
`[245,250,253,256]`); "số trang phải khớp số trang vật lý của PDF" (mục lục dùng số trang **in
trong sách**, lệch offset với index PDF — chính CHANGELOG 7.3 đã ghi mapping "trang sách N ↔
PyMuPDF index N−1").

#### Y8. Rủi ro hồi quy trên trang KHÔNG phải mục lục

Trả lời thẳng câu hỏi của brief: **đúng, luật này chạy trên MỌI paragraph của MỌI trang** —
babeldoc không có khái niệm "trang mục lục", và tôi **cố ý không** thêm khái niệm đó (Y5-d). Vì
vậy phần chống hồi quy phải nằm hoàn toàn trong bản thân heuristic. Bằng chứng hiện có:

| Phạm vi đo | Đơn vị | Kích hoạt sai |
|---|---|---|
| IL thật, 4 bộ trang không phải TOC (p74–77, page14 35-mục, p20 bảng+caption, p22 mix) | 55 paragraph nhiều dòng | **0** |
| Figoni bản đầy đủ, quét toàn sách bằng PyMuPDF (`ratio ≥ 0.8`, thân ≥ 2 từ) | 4657 block nhiều dòng | **0** |
| 6 đầu sách khác nhau trong `data/uploads/` cùng ngưỡng | toàn bộ | **1 block** — và đó là **trang mục lục của Le Cordon Bleu** (`'Crème d'amandes—Almond Cream  352'`, gap 11.6pt / font 12pt = 0.97) ⇒ **true positive**, không phải FP |

⚠️ **Giới hạn của bằng chứng, phải nói rõ**: phép quét toàn sách dùng **block của PyMuPDF**, còn
babeldoc gom paragraph theo **layout model** — hai cách gom **khác nhau**, và babeldoc thường gom
**to hơn**. Vì vậy con số "0 trên 4657 block" là **ước lượng bề mặt rủi ro, KHÔNG phải bằng chứng
tương đương**. Chỉ 4 bộ dump IL (11 trang) là so sánh đúng-đối-đúng. **Đây là lý do bước spike
7.4-a ở Y11 là bắt buộc, không được bỏ.**

**Rủi ro gián tiếp (không phải tách sai, nhưng phải nêu)**: TOC-1 làm **tăng số paragraph** ⇒ đổi
`unit_count` ⇒ đổi **mode-scale toàn tài liệu** (`typesetting.py:892-935`, kẹp **xuyên trang** —
đã verified ở X2-c). Đúng ràng buộc X7. ⇒ Nếu Bug #8 (bước 8.1) đã đo histogram trước khi TOC-1
lên, **số đo đó hết hạn**. Phải ghi vào D-ordering.

#### Y9. Có tổng quát cho sách khác không?

**Tổng quát ở mức cơ chế, KHÔNG phải chỉ đúng cho Figoni** — nhưng có biên rõ ràng:

| Dạng mục lục | TOC-1 xử lý được? |
|---|---|
| Số trang cuối dòng, cách bằng khe rộng (Figoni, Le Cordon Bleu) | ✅ Đây là ca thiết kế chính. Đã thấy khớp trên **2 đầu sách khác nhau** |
| Dot leader ≥ 20 chấm | ✅ Đã được **babeldoc gốc** xử lý (`:864-866`), TOC-1 không cần đụng |
| Dot leader < 20 chấm hoặc chấm cách thưa (`. . . .`) | ⚠️ Hiện **lọt cả hai lưới**. TOC-1b (Y5-a) đóng được, đề xuất tắt mặc định ở v1 |
| Số trang là **chữ số La Mã** (phần đầu sách: `"Preface  vii"`) | ❌ **Không xử lý** — cố ý. Thêm La Mã sẽ khớp cả `"I"`, `"V"`, `"X"`, `"C"`, `"D"`, `"M"` đứng cuối dòng (chữ cái đầu tên riêng, ký hiệu đơn vị) ⇒ rủi ro FP tăng vọt so với lợi ích. **Đề xuất KHÔNG làm** |
| Mục lục 2 cột mà babeldoc gom **chéo cột** vào 1 paragraph | ⚠️ Chưa gặp. Nếu xảy ra, dãy số sẽ **giảm** ở chỗ nhảy cột ⇒ cổng "không giảm" sẽ **chặn toàn bộ paragraph** ⇒ mất fix (an toàn nhưng mất tác dụng). Nếu Expert cho rằng đây là ca phổ biến, cân nhắc **hạ cổng monotonic xuống mức "cảnh báo" thay vì "chặn"** |
| Mục lục có số trang dạng `"12–15"` hoặc `"3-1"` | ⚠️ Dãy digit liền cuối sẽ là `15` / `1`; vẫn tách đúng chỗ. Vô hại |

#### Y10. Chi tiết triển khai đề xuất (để Expert soi, **chưa phải lệnh cho Dev**)

**(a) File và cờ điều khiển** — theo đúng khuôn 7.2, kill-switch **RIÊNG**:

| Thành phần | Nội dung |
|---|---|
| `src/babeldoc_shim/toc_split.py` (mới) | Thuần Python, không import babeldoc. API đề xuất: `mark_toc_tail(chars) -> TocTail \| None` và `split_paragraph_by_toc_tails(lines) -> list[list[int]]`. **Hàm duy nhất** quyết định ranh giới; `sitecustomize.py` chỉ thực thi |
| `src/babeldoc_shim/sitecustomize.py` | Thêm patch thứ 3: bọc `ParagraphFinder.process_independent_paragraphs` (Y6). **Cùng `try/except` + cùng gate version `0.6.4`** với 7.1/7.2 — cả 3 rollback chung nếu cấu trúc babeldoc đổi |
| `src/core/config.py` | `Settings.babeldoc_toc_split_enabled: bool` — **đề xuất mặc định `False` ở lần ship đầu**, bật sau khi QA live xanh. Lý do: 7.1 đã qua 11 trang, 7.2 qua 2 fixture; TOC-1 mới nhất ⇒ rủi ro cao nhất ⇒ phải tắt được độc lập |
| `src/services/babeldoc_runner.py` | Nối `BABELDOC_SHIM_TOC_SPLIT=1/0` vào `env` của subprocess (đúng cách 7.2 làm với `BABELDOC_SHIM_NUMBERED_LIST_SPLIT`) |
| `src/core/job_orchestrator.py` | Truyền cờ vào `BabeldocRunner` |

Tham số (đề xuất, **phải chốt lại từ số đo của spike**, không phải hằng số thiêng):
`TOC_GAP_RATIO = 0.8`, `TOC_MIN_TAIL_LINES = 2`, `TOC_MIN_TAIL_FRACTION = 0.6`,
`TOC_MIN_BODY_WORDS = 1`, `TOC_MAX_DIGITS = 4`, `TOC_REQUIRE_NON_DECREASING = True`,
`TOC_DOT_LEADER_FALLBACK = False`.

**(b) Tech debt phát hiện trong task này (KHÔNG thuộc phạm vi Ca C, ghi để không mất dấu)**:
paragraph do **7.2** tạo ra có `render_order = None` (vì hook chạy sau `:310`), khiến
`typesetting._update_paragraph_render_order` (`:1664-1670`) bỏ qua paragraph đó. Không crash,
không thấy triệu chứng trong live E2E của 7.2, nhưng là sai khác âm thầm so với paragraph do
babeldoc tự tách. **Fix rẻ nhất**: copy `paragraph.render_order` sang paragraph mới trong
`_split_numbered_list_paragraphs_on_page` (`sitecustomize.py:219-226`). ⚠️ **`[UNVERIFIED]`** —
tôi **chưa đo** được nó có gây khác biệt nhìn thấy trong PDF output hay không. Đề xuất: **task
riêng**, không nhét vào 7.4.

#### Y11. Kế hoạch bước "7.4" và effort

| Bước | Nội dung | Gate bắt buộc trước khi qua bước sau |
|---|---|---|
| **7.4-a** — Spike (R5-02) | Sinh IL dump thật (`--debug`, LLM port chết, 0 token) cho: 2 trang Contents Figoni + **ít nhất 1 trang bảng công thức bánh** (FP-4) + 1 trang index/references nếu có + trang Contents của **Le Cordon Bleu** (sách thứ 2). Chạy TOC-1 offline trên các dump, báo cáo **recall** và **FP** riêng từng loại. **Commit golden fixture** (`.json.gz`) vào `tests/fixtures/babeldoc/` | FP trên trang không phải TOC = **0**; recall trên 2 trang Contents Figoni = **20/20 paragraph**; **có số liệu cho FP-4**. Nếu FP-4 kích hoạt ⇒ **dừng, escalate Tech Lead**, không tự chỉnh tham số |
| **7.4-b** — Implement | `toc_split.py` + patch thứ 3 + 3 file wiring (Y10-a) | `ruff check` + `ruff format` sạch |
| **7.4-c** — Test (R6-02) | Unit test cho từng luật (gồm ca âm tường minh: `"…about 15"`, `"4.0"`, folio thuần số, tiêu đề 2 dòng, mục TOC xuống dòng). Golden-fixture test assert **số nhóm VÀ nội dung từng nhóm** — bảng số ở Y2 là **oracle** | Test gọi **đúng** hàm production, không chép tay thuật toán |
| **7.4-d** — Live E2E (R6-03) | Dịch thật 2 trang Contents qua đúng `BabeldocRunner.translate_pages()` với DeepSeek, **mở PDF output đọc nội dung**, đếm số block và kiểm tra ranh giới mục. So với baseline 7.3 (**26 block**, các mục bị trộn) | Không còn ca "nhiều mục TOC trộn thành 1 câu"; multiset ký tự trước/sau **không đổi** (không mất chữ) |
| **7.4-e** — Đo hồi quy | Chạy lại **11 trang** của 7.1 (4 trang p74-77 + 7 trang Q2) + p20/p22, so IL trước/sau | **0** thay đổi trên các trang không phải TOC |
| **7.4-f** — Reviewer (Protocol 7 R7-01) | Spawn agent `Reviewer` thật, ghi **APPEND** vào `docs/review-report.md` | Bắt buộc, không tự review |

**Effort ước lượng**: 7.4-a ≈ **3–4 giờ** (phần lớn là sinh dump cho trang công thức/sách thứ 2);
7.4-b ≈ **3 giờ** (logic lõi ~60 dòng, phần lớn là wiring 4 file); 7.4-c ≈ **3 giờ**;
7.4-d + 7.4-e ≈ **3 giờ**. **Tổng ≈ 1.5 ngày**, tương đương 7.2.

**Ràng buộc thứ tự** (bổ sung vào D7-3/X7): 7.4 **phải xong trước** bước **8.1** (đo histogram
scale của Bug #8), vì TOC-1 đổi số paragraph ⇒ đổi `unit_count` ⇒ đổi mode-scale xuyên trang
(Y8). Nếu 8.1 đã chạy trước, **phải đo lại**.

#### Y12. Bảng trạng thái verify (Protocol 5 R5-01) — chỗ Domain Expert nên đánh

| Claim | Trạng thái |
|---|---|
| Mọi contract babeldoc trích ở Y1 (file:line) | ✅ **Verified** — đọc trực tiếp source 0.6.4 đã cài trong task này |
| TOC Figoni không dot leader, số trang **không** căn phải, khe = dummy space | ✅ **Verified** — IL dump thật + PyMuPDF `rawdict` |
| Tỷ lệ `gap/font_size` của mục TOC = 1.0 (tiêu đề 2.0), văn xuôi tệ nhất = 0.64 | ✅ **Verified** — 135 dòng trên 2 trang Contents + quét toàn sách |
| TOC-1 tách đúng **20/20** paragraph mục lục (66 điểm tách), **0** tách nhầm tiêu đề/dòng nối | ✅ **Verified** — mô phỏng trên IL dump thật của p7 (8/12 fire, 28 splits) và p8 (12/18 fire, 38 splits); 10 paragraph bị bỏ qua đều **đúng** là tiêu đề chương / mục xuống dòng |
| Dãy số trang không giảm trên **20/20** paragraph mục lục | ✅ **Verified** — cùng dump |
| TOC-1 **0** kích hoạt trên 55 paragraph nhiều dòng của 4 bộ trang không phải TOC | ✅ **Verified** — IL dump thật |
| `merge_alternating_line_number_paragraphs` không gộp lại paragraph mục lục vừa tách | ✅ **Verified** — `:368-380`, `:382-391`, `:393-418` |
| Hook `process_independent_paragraphs` mutate in-place và propagate qua `page.pdf_paragraph` | ⚠️ **`[UNVERIFIED]`** — suy ra từ việc `:247` gán cùng object list và hàm gốc dùng `paragraphs.insert`; **chưa chạy thật**. Spike 7.4-a phải chứng minh bằng dump |
| **FP-4 — bảng công thức bánh** (`"Bread flour  100"`) có kích hoạt TOC-1 không | ⚠️ **`[UNVERIFIED]` — RỦI RO LỚN NHẤT.** Chưa có trang nào loại này trong 11 trang đã dump. **Gate cứng của 7.4-a** |
| FP-6 (references), FP-7 (index) | ⚠️ **`[UNVERIFIED]`** — chưa có mẫu; cơ chế chặn giống FP-1 |
| Bộ tham số (0.8 / 2 / 0.6 / 1) là tối ưu | ⚠️ **`[UNVERIFIED]`** — tune trên **1 cuốn**. Phải chốt lại từ 7.4-a với ≥ 2 cuốn |
| Quét toàn sách bằng PyMuPDF ⇒ 0 FP có tương đương với babeldoc paragraph không | ❌ **KHÔNG tương đương** — cách gom khác nhau (Y8). Chỉ dùng làm ước lượng bề mặt rủi ro |
| TOC-1b (dot leader thưa) không gây FP với ellipsis văn xuôi | ⚠️ **`[UNVERIFIED]`** — đề xuất **tắt mặc định** ở v1 |
| Chữ số La Mã | ❌ **Cố ý không hỗ trợ** (Y9) — quyết định thiết kế, không phải thiếu sót |
| `render_order = None` của paragraph do 7.2 tạo có gây khác biệt nhìn thấy được không | ⚠️ **`[UNVERIFIED]`** — task riêng (Y10-b) |
| TOC-1 đổi `unit_count` ⇒ hết hạn số đo Bug #8 | ✅ **Verified về cơ chế** (`typesetting.py:892-935`, X2-c) — **chưa đo biên độ** |

#### Y13. Ba câu hỏi tôi muốn Domain Expert phản biện tập trung

1. **FP-4 (bảng công thức bánh)** — đây là chỗ tôi tự thấy yếu nhất. Với domain bánh, dòng
   `"Bread flour   100"` / `"Water   62%"` xuất hiện dày đặc, thoả **mọi** điều kiện của TOC-1
   (có chữ, số cuối, khe rộng, `m` lớn, thậm chí có thể không giảm). Câu hỏi: (a) khi babeldoc
   gom một cột công thức thành 1 paragraph rồi TOC-1 tách thành từng dòng — đó là **hỏng** hay
   thực ra là **cải thiện** cho chất lượng dịch? (b) nếu là hỏng, tín hiệu nào phân biệt được
   "bảng công thức" với "mục lục" mà **không** cần biết trang nào là trang gì?
2. **Cổng monotonic** — tôi đề xuất bật (20/20 đúng trên dữ liệu Figoni). Nhưng nếu mục lục 2 cột
   bị babeldoc gom chéo cột thì cổng này giết luôn cả fix. Expert có ca thật nào cho thấy nên hạ
   nó xuống mức "tín hiệu mềm" thay vì "điều kiện cứng" không?
3. **Điểm hook `process_independent_paragraphs` (Y6)** — tôi cố tình chọn **khác** 7.2 để paragraph
   mới nhận được `render_order` và debug rect. Đổi lại, nó chạy **trong lòng** `process_page` chứ
   không phải sau, nên bề mặt tương tác với các bước `:290-310` rộng hơn. Tôi đã đọc source và
   loại được nguy cơ bị `merge_alternating_line_number_paragraphs` gộp lại — Expert có thấy bước
   nào khác trong `:288-310` (`fix_overlapping_paragraphs` ở `:302`?) có thể phá hoặc gộp lại
   các paragraph vừa tách mà tôi bỏ sót không?

**Trạng thái**: thiết kế xong ở mức đề xuất, **chưa có dòng code nào được viết**. Việc tiếp theo:
Domain Expert phản biện → Tech Lead chốt → PM/user duyệt (Protocol 2) → mới giao Dev spike 7.4-a.

---

### Bug #7 Ca C — Phản biện của Domain Expert (2026-09-07)

> Phản biện độc lập cho đề xuất TOC-1 (Y0–Y13). Mọi số liệu dưới đây do tôi **tự đo lại** bằng script
> viết riêng (không chạy lại script của Tech Lead) và bằng **6 lần chạy `babeldoc --debug` mới** trên
> trang chưa từng được dump trước đây. Mọi trích dẫn source đều đã tự mở file đúng dòng.

#### Z0. Phán quyết một dòng

**ĐỒNG Ý cho TOC-1 đi tiếp sang spike 7.4-a**, với 3 sửa đổi thiết kế bắt buộc (Z8), và với **1 điều
kiện tiên quyết không thuộc Ca C**: phải hotfix một **bug production thật của 7.2** mà tôi phát hiện
trong lúc kiểm tra điểm hook (Z6) — mọi paragraph do 7.2 tách ra hiện **không được dịch** (giữ nguyên
tiếng Anh), và CHANGELOG 7.2 đã ghi nhận triệu chứng này nhưng **quy nhầm nguyên nhân** cho LLM fallback.

#### Z1. Dữ liệu tự sinh trong task này (tái tạo được, Protocol 5 mục 3)

Lệnh chạy (đúng flag production của `BabeldocRunner`, shim 7.1+7.2 bật qua `PYTHONPATH`, cổng LLM
chết, 0 token), mỗi file trích bằng `pymupdf.insert_pdf` từ `data/uploads/`:

```
PYTHONPATH=src/babeldoc_shim BABELDOC_SHIM_NUMBERED_LIST_SPLIT=1 babeldoc --files <f>.pdf --debug \
  --working-dir <wd> --output <out> -li en -lo vi --openai --openai-base-url http://127.0.0.1:1/v1 \
  --openai-api-key x --openai-model x --pool-max-workers 1 --watermark-output-mode no_watermark \
  --only-include-translated-page --no-auto-extract-glossary --skip-scanned-detection \
  --split-short-lines --short-line-split-factor 0.8 --ignore-cache
```

| Tên | Nguồn (PyMuPDF index) | Mục đích | Kết quả TOC-1 (mô phỏng độc lập) |
|---|---|---|---|
| `figoni_p25_recipe` | Figoni bản đầy đủ idx 40 (trang sách 25, "Drop Sugar Cookie Dough", cột BAKER'S PERCENTAGE **không có `%`**: 82/113/1.6/1.6/37/100/335.2) | **FP-4** | 9 paragraph nhiều dòng, **0 kích hoạt** |
| `figoni_p45_recipe` | Figoni idx 60 (trang công thức thứ 2) | FP-4 | 14 paragraph nhiều dòng, **0** |
| `figoni_p7_tables` | Figoni idx 22 (TABLE 1.4/1.5/1.6, có `%`) | FP-3/FP-4 | 6 paragraph nhiều dòng, **0** |
| `lcb_toc` | Le Cordon Bleu idx 6–7 (Contents, **2 cột**, nhiều mục xuống dòng) | Q2 + tổng quát hoá | 15 paragraph nhiều dòng, **11 kích hoạt, 64 điểm tách**, monotonic 11/11 |
| `friberg_toc` | Bo Friberg idx 6 (Contents, số trang căn phải xa, font 8pt) | Quy ước xuống dòng khác | 3 paragraph nhiều dòng, **0** (xem Z7-a) |
| `lcb_index` | Le Cordon Bleu idx 408 (Subject Index) | **FP-7** | 16 paragraph nhiều dòng, **0** |

Dump nằm tại scratchpad phiên này
(`/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/2d559074-2821-4566-91ff-969cf281d898/scratchpad/wd/<tên>/<tên>/paragraph_finder.json`,
script mô phỏng `toc1_sim.py`, `struct.py` cùng thư mục) — artifact tạm, **Dev phải sinh lại và commit
golden fixture ở 7.4-a** như Y2 đã yêu cầu.

Ngoài ra tôi tái mô phỏng TOC-1 trên 2 dump Contents Figoni của 7.3 (`/tmp/bdprobe/wd_toc*`): kết quả
**khớp tuyệt đối** với Y12 — 8/12 và 12/18 paragraph kích hoạt, 28 + 38 = **66 điểm tách**, 10
paragraph bị bỏ qua đúng là 7 tiêu đề chương 2 dòng + 3 mục xuống dòng. Con số của Tech Lead **đúng**.

#### Z2. Kiểm tra từng trích dẫn source ở Y1 (tự mở file 0.6.4 đã cài)

| Claim Y1 | Kết quả |
|---|---|
| `process_page` `:235-310`, thứ tự `:245/:275/:278-281/:284/:287/:290-291/:302/:305/:307/:310` | ✅ Đúng từng dòng. **Lỗi nhỏ**: Y12 ghi "`:247` gán cùng object list" — dòng đúng là **`:245`** (`page.pdf_paragraph = paragraphs`); `:247` là `page_level_formula_font_ids…`. Chỉ là lỗi đánh máy, kết luận không đổi |
| Dot-leader `\.{20,}` `:864-866`; hình học/bullet `:891-903`; nguyên mẫu tách `:868-888` và `:904-926`; cascade qua `paragraphs.insert(i+1)` + `break` + vòng ngoài `i += 1` | ✅ Đúng |
| `is_bullet_point` không nhận chữ số, `layout_helper.py:50-52`, `:55-65` | ✅ Đúng |
| `il_version_1.py` `PdfStyle.font_size`, `PdfCharacter.visual_bbox` | ✅ Đúng (font_size `:603`, VisualBbox `:613-623`, PdfCharacter `:627+`) |
| `merge_alternating_line_number_paragraphs` `:393-418`, `_is_ascii_digit_or_space_paragraph` `:368-380`, `_same_layout_and_xobj` `:382-391` | ✅ Dòng đúng — **nhưng lập luận "còn đòi cả hai `xobj_id is not None`" là SAI trên dữ liệu thật**: trong **mọi** dump tôi mở (Figoni p7/p8/p25/p45/p7-tables, LCB, Friberg, p74-77, page14) paragraph nội dung chính có **`xobj_id = 0`**, không phải `None` — `0 is not None` là `True`, guard này **không chặn gì cả**. Lớp bảo vệ thật là `_is_ascii_digit_or_space_paragraph` (TOC-1 không bao giờ tạo paragraph thuần số) **và** `a.layout_id == c.layout_id`. Kết luận "không bị gộp lại" **vẫn đúng**, nhưng vì lý do khác (Z5-a) |
| `_set_paragraph_render_order` `:312-347` chạy trong `process_page`; `typesetting.py:1664-1670` `return` khi `render_order is None` | ✅ Đúng. **Bổ sung TL chưa xem hạ nguồn**: `backend/pdf_creater.py:52-55` ép `render_order None → 9999999999999999`, `:66-68` sort key, `:934 sorted(render_units, key=get_sort_key)` ⇒ ký tự của paragraph không có `render_order` bị **vẽ sau cùng** trong content stream. Không crash, chỉ đổi z-order; không thấy hậu quả nhìn được — Y10-b xếp **ưu tiên thấp** là hợp lý (nhưng xem Z6: cùng dòng code đó còn thiếu thứ nghiêm trọng hơn) |
| `_update_paragraph_render_order` chỉ được gọi ở nhánh re-typeset (`typesetting.py:1283`), không gọi ở nhánh passthrough (`:1265-1269`) | ✅ Tôi tự kiểm, TL không nêu — nhánh passthrough giữ ký tự gốc (đã có `render_order`), nên khác biệt chỉ xuất hiện với paragraph **được dịch** |

#### Z3. Câu hỏi 1 — FP-4 (bảng công thức bánh): **KHÔNG kích hoạt trên dữ liệu thật của project — nhưng vì một lý do khác với những gì Y7 giả định**

**Bằng chứng (3 trang công thức thật, dump IL mới)**: trên cả 3 trang, layout model của babeldoc gán vùng
bảng nhãn `table` và `_group_characters_into_paragraphs` (`:447-507`, tạo paragraph mới mỗi khi
`layout_id` đổi trong thứ tự content stream) đưa **mỗi ô thành 1 paragraph `fallback_line` 1 dòng**
(`figoni_p25_recipe`: `'Shortening, all-purpose'` lid=34, `'410'` lid=30, `'Sugar, regular granulated'`
lid=39… — 82 ô `fallback_line` trên `figoni_p7_tables`). Dòng kiểu `"Bread flour   100"` mà Y7 lo ngại
**không tồn tại ở tầng IL**: tên nguyên liệu và con số nằm ở 2 paragraph khác nhau, TOC-1 (đòi ≥ 2 dòng
trong **cùng** paragraph) không có gì để xét. Đây đúng là hiện tượng X2-d đã ghi (77 ô `fallback_line`)
— Tech Lead đã có bằng chứng này trong tay từ Bug #8 nhưng không nối vào FP-4.

**Ba đầu sách còn lại** (đọc text thật): Bo Friberg viết định lượng **trước** tên nguyên liệu
(`'1 pound 6 ounces (625 g) cake flour'`, idx 118) ⇒ không có chữ số cuối dòng; Le Cordon Bleu ghi số
**kèm đơn vị** (`'20 g'`, `'350 ml'`) ⇒ `k = 0`; Woodhead: 0 dòng dạng `chữ  <2+ space>  số$` trong 298
trang. Bảng "Ingredient Ratios" của Friberg (idx 79) dùng `100%` ⇒ `k = 0`.

**Trả lời (a)**: đồng ý với TL — *nếu* một cột công thức bị gom thành 1 paragraph rồi bị tách từng dòng,
đó là **cải thiện** (LLM hết trộn dòng nguyên liệu), không phải hỏng; rủi ro duy nhất là đổi `unit_count`
(X7) — nhưng ca này **không xảy ra** trên dữ liệu đã có. **Trả lời (b)**: tín hiệu phân biệt đã có sẵn
và đã verify (X2-d): `page.page_layout` có entry `class_name == "table"` với box hình học. Đề xuất thêm
**guard rẻ**: bỏ qua paragraph có tâm nằm trong box `table` (cùng cách gom của bước 8.2). Không cần
biết "trang nào là trang gì".

**Rủi ro còn lại, phải ghi rõ**: kết luận trên phụ thuộc layout model nhận ra bảng. Bảng công thức
**không kẻ khung, không bị nhận là `table`** (nhãn `plain text`) sẽ đi vào đường bình thường — chưa có
mẫu nào như vậy trong 6 đầu sách, nên đánh dấu `[CHƯA VERIFY]` cho sách ngoài bộ này. Guard `table`
ở trên **không** che được ca đó; khi đó chỉ còn cổng `m/L ≥ 0.6` + monotonic (cột công thức thật hiếm
khi không giảm vì dòng `Total` luôn lớn nhất và ở cuối, còn `Flour 100` thường ở đầu — trên
`figoni_p25` dãy là `[82,113,37,100]`, không đơn điệu).

**KHÔNG ĐỒNG Ý với cách Y7/Y12 mô tả "khe an toàn rộng" (TOC ≥ 1.0 vs văn xuôi tệ nhất 0.64)**:
- Đo trên IL (`visual_bbox`, đúng đặc trưng Y4 dùng): mục TOC Figoni cho tỷ lệ **1.05–1.21** (không phải
  1.00 — số 1.00 của Y2 đo bằng bbox advance của PyMuPDF, hai hệ đo khác nhau, Dev phải chọn 1 và chốt
  ngưỡng theo hệ đó).
- Trên **LCB**, tên mục dài đẩy sát số trang: `'Pâte à croissants—Croissant Dough 332'` = **0.43**,
  `'Crème Chantilly—Chantilly Cream 348'` = **0.66**, `'Crème Chibouste—Chiboust Cream 350'` = **0.81**,
  `'Crème d'amandes—Almond Cream 352'` = 1.00. Phân bố TOC **tràn xuống dưới 0.8**.
- Ngược lại, dòng slug in ấn nhãn `abandon` (`'c04.indd 62'`, có trên **mọi** trang Figoni, ký tự bị nhân
  đôi thành `cc0044..iinndddd6622`) qua được **toàn bộ** luật mức dòng với tỷ lệ **0.92–0.93** — chỉ bị
  chặn vì là paragraph 1 dòng.
⇒ Ngưỡng 0.8 là **thoả hiệp**, không phải "khe an toàn"; lớp chống FP thật sự là cổng paragraph
(`m ≥ 2`, `m/L ≥ 0.6`, monotonic) — điểm này TL cũng đã xếp là tín hiệu mạnh nhất, nhưng phần mô tả
"khe rộng" cần sửa lại để Dev không hạ ngưỡng xuống 0.5–0.6 "cho chắc" (sẽ dính slug 0.92 nếu có
trang nào gom 2 slug vào 1 paragraph). **Giữ 0.8**, và chấp nhận 2/84 mục LCB bị bỏ sót (hướng an toàn).

**Về phép quét toàn sách bằng PyMuPDF (Y8, "0 FP trên 4657 block")**: tôi đo độ nhạy của cách quét này
trên chính 2 trang Contents Figoni — 123/152 dòng thoả luật mức dòng nhưng **0 block** có ≥ 2 dòng như
vậy (PyMuPDF tách mỗi mục TOC thành block riêng); trên LCB Contents chỉ **2/184** dòng thoả luật (số
trang nằm ở span/line riêng). Một phép quét **không phát hiện nổi chính mục lục** thì "0 FP" của nó
gần như **không có trọng lượng bằng chứng** — TL đã tự cảnh báo (Y8 "không tương đương") nhưng vẫn
đưa vào Y0 như một điểm mạnh. Bằng chứng FP thật chỉ là các dump IL (11 trang cũ + 6 trang mới ở Z1).

#### Z4. Câu hỏi 2 — Cổng monotonic: **giữ làm điều kiện cứng; rủi ro "gom chéo cột" là lý thuyết**

- **Bằng chứng thật**: cả 2 mục lục 2 cột trong project (Figoni p7/p8: cột trái x≈102, cột phải x≈354;
  LCB p6/p7: x≈123–153 và x≈363–393) đều được layout model chia **vùng riêng cho từng khối/cột**
  (Figoni: `layout_id` 1–6 khác nhau cho từng khối; LCB: lid 2/3/12 trái, 4/5/1 phải). **31/31**
  paragraph kích hoạt đều có dãy số không giảm; **không có** paragraph nào bị cổng này chặn.
- **Lập luận cấu trúc** (đọc `:747-776`): dòng trong paragraph được tạo bằng **phân cụm theo y** rồi sắp
  từ trên xuống. Nếu một vùng layout ôm cả 2 cột, ký tự cột trái và cột phải **cùng y sẽ dính vào cùng
  một `PdfLine`** (`'Mục trái 12   Mục phải 210'`) — dãy số cuối dòng khi đó chỉ là số của cột phải,
  **vẫn không giảm**. Ca "dãy số giảm ở chỗ nhảy cột" chỉ xảy ra khi vùng layout ôm 2 cột **và** 2 cột
  không giao nhau theo y (cột 2 bắt đầu ở đầu trang sau khi cột 1 kết thúc giữa trang) — chưa gặp, và
  khi đó vấn đề thật là dòng bị trộn chéo cột (TOC-1 không sửa được, cổng nào cũng vô nghĩa).
- Vì cổng này chưa từng "bắt" được gì trên dữ liệu, giá trị chống FP của nó **chưa được chứng minh**
  (nhưng cũng không tốn gì). Giữ, log khi nó chặn để 7.4-e có số liệu.

#### Z5. Câu hỏi 3 — Điểm hook `process_independent_paragraphs`: **ĐỒNG Ý, và lý do mạnh hơn TL nêu**

Tôi trace từng bước sau `:287`:

- **(a) `merge_alternating_line_number_paragraphs` `:290-291`** (config `merge_alternating_line_numbers`
  mặc định `True`, `translation_config.py:207`): guard `xobj_id is not None` **không có tác dụng** (Z2).
  Bảo vệ thật: (1) TOC-1 chỉ tạo paragraph chứa chữ ⇒ không bao giờ là "l"; (2) để "a l+ c" gộp cần 1
  paragraph thuần số **chen giữa** 2 paragraph TOC-1 vừa tách **cùng `layout_id`** — TOC-1 chèn liền kề
  (`insert(i+1)`), nên không có gì chen giữa. Trường hợp gần nhất trong dữ liệu là **Bo Friberg**: số
  trang là paragraph thuần số riêng (`'207'` lid=27, `'259'` lid=32…) xen kẽ tiêu đề — nhưng mỗi mục có
  `layout_id` riêng ⇒ `_same_layout_and_xobj` False ⇒ không gộp. Kết luận an toàn của TL **đứng vững**,
  nhưng Dev **không được** viết test/comment dựa vào guard `xobj_id`.
- **(b) `fix_overlapping_paragraphs` `:302`** (`:939-1030`): chỉ sửa **`paragraph.box`** (y/y2 về
  `mid ± 1`), không đụng composition, và chỉ khi 2 box giao nhau 2D. Đo thật: sau khi tách từng dòng
  trên Figoni p7/p8, khe dọc giữa 2 group liên tiếp = **2.85–2.95 pt** (âm = không giao) trên **toàn bộ
  66 điểm tách** ⇒ no-op. Với sách có leading chặt (font 10/pitch 11) box có thể giao < 1pt ⇒ mỗi box bị
  cắt ~1pt+ ⇒ khung typeset nhỏ đi một chút. Đây là **khác biệt hành vi có thật so với hook 7.2** (chạy
  sau `:302`), nhưng cùng cách babeldoc đối xử paragraph do chính nó tách — chấp nhận được, ghi vào
  7.4-e để đo.
- **(c) `:293-294` `update_paragraph_data(paragraph, update_unicode=True)`** — TL **không liệt kê**, và
  đây là lý do quan trọng nhất để hook sớm: chỉ lời gọi này mới ghi `paragraph.unicode` (`:147-148`).
  Paragraph tạo **sau** `process()` (cách 7.2 đang làm) không bao giờ đi qua đây ⇒ xem Z6.
- **(d) `add_debug_info` `:307`** chỉ khi `--debug`; **(e) `_set_paragraph_render_order` `:310`** gán
  đúng cho paragraph mới. ✅ như TL nói.
- **(f) Tương tác với patch 7.2** (bọc `process`, chạy sau toàn bộ `process_page`): 7.2 duyệt lại
  `page.pdf_paragraph` gồm cả paragraph TOC-1 mới; mục TOC không có marker đầu dòng dạng `\d{1,3}[.)]\s`
  (LCB `'1. History of Pâtisserie in France 2'` là paragraph 1 dòng ⇒ 7.2 bỏ qua) ⇒ không xung đột.

**Không có bước nào trong `:288-310` phá hoặc gộp lại paragraph TOC-1 tạo ra** — xác nhận Y6, thêm (b)
là điểm cần đo, (c) là điểm cần tận dụng.

#### Z6. PHÁT HIỆN QUAN TRỌNG NHẤT — 7.2 đang ship với bug thật: paragraph tách ra **không được dịch**

**Cơ chế** (đọc source, không suy đoán):
1. `sitecustomize.py:219-227` tạo `PdfParagraph(unicode="")` rồi gọi `self.update_paragraph_data(new_paragraph)`
   với `update_unicode` mặc định `False` ⇒ `unicode` **vẫn là `""`**; paragraph gốc (`:216`) giữ
   `unicode` **cũ** chứa cả các dòng đã bị cắt đi (stale).
2. Không stage nào giữa ParagraphFinder và ILTranslator tính lại `unicode`
   (`high_level.py:274-281`: StylesAndFormulas, AutomaticTermExtractor không ghi field này — grep toàn
   `midend/` chỉ có `il_translator.py:1004/1232` và `il_translator_llm_only.py:835/861`, đều là ghi **sau**
   khi dịch).
3. Translator đang dùng là `ILTranslatorLLMOnly` (CHANGELOG 7.2 trích log `il_translator_llm_only.py:828`).
   Cổng vào `:556-568`: `if paragraph.unicode is None: continue` … `if len(paragraph.unicode) <
   min_text_length: continue` với `min_text_length = 5` (`translation_config.py:187`, app không truyền
   `--min-text-length`). `len("") < 5` ⇒ paragraph **bị bỏ qua hoàn toàn, không gửi LLM, không log**.
   Paragraph gốc không bị ảnh hưởng vì text gửi LLM dựng từ composition
   (`pre_translate_paragraph`, `il_translator.py:954+`, `text = translate_input.unicode`), `unicode` stale
   chỉ dùng cho đếm token.

**Bằng chứng sống (artifact 7.2 còn nguyên trong `/tmp/bdprobe`)**:
- Dump `wd72c/page14_numbered_list_source/paragraph_finder.json`: đúng **4 paragraph** có
  `unicode=''`, `render_order=None` — `'12. Stovetop burners'`, `'24. Stainless steel saucepans…'`,
  `'32. Cutting boards'`, `'34. Cups for water'` — chính là 4 paragraph 7.2 tạo ra (cặp 11+12, 23+24,
  31+32, 33+34 ghi ở CHANGELOG 7.2).
- PDF output live `live72/page14_numbered_list_source.no_watermark.vi.mono.pdf` (đọc text bằng PyMuPDF):
  `11. Lò nướng…` (Việt) → **`12. Stovetop burners` (Anh)** → `13. Khay nướng…` (Việt); tương tự
  **`24. Stainless steel saucepans, heavy`**, **`32. Cutting boards`**, **`34. Cups for water`** giữ nguyên
  tiếng Anh, mọi mục lân cận đều Việt.
- Dump `wd74c/p74_77/paragraph_finder.json`: **10 paragraph** `unicode=''` = câu hỏi **#3, #5, #7,
  #9–15** — **trùng khớp từng số** với danh sách CHANGELOG 7.2 "bị babeldoc fallback về giữ nguyên
  tiếng Anh (#3, #5, #7, #9-15)".

⇒ CHANGELOG 7.2 mục "Quan sát thêm" **chẩn đoán sai**: không phải LLM trả kết quả xấu (`:828` fallback),
mà là shim **tự làm paragraph vô hình** với translator. Gate R6-03 của 7.2 ("35/35 mục xuống dòng
đúng") đo **cấu trúc dòng**, không đo **"mục đã được dịch chưa"** — đúng loại lỗ hổng Protocol 6 R6-03
cảnh báo (tin cấu trúc, không đọc nội dung cuối). Trên production hiện nay, **mọi mục numbered-list từ
mục thứ 2 của mỗi cụm bị dính** đang ra tiếng Anh.

**Fix** (1 dòng + 1 dòng, ngoài phạm vi Ca C, **hotfix riêng qua Reviewer trước 7.4**):
`self.update_paragraph_data(new_paragraph, update_unicode=True)` và
`self.update_paragraph_data(paragraph, update_unicode=True)` ở `sitecustomize.py:216/227`, cộng
`new_paragraph.render_order = paragraph.render_order` (Y10-b). Hoặc triệt để hơn: dời 7.2 sang cùng
hook `process_independent_paragraphs` như TOC-1 để `:293-294`/`:310` tự lo — nhưng TL đã lý luận đúng
rằng không mở lại 7.2 trong cùng task; tôi đồng ý, **hotfix tối thiểu trước, dời hook sau**.
Golden-fixture test của 7.2 **phải thêm assertion** `unicode != ""` và `render_order is not None` cho
paragraph mới — đúng tinh thần R6-02 (assert giá trị truyền sang bước sau, không chỉ số nhóm). Cùng
assertion đó là **bắt buộc** cho test 7.4-c.

#### Z7. Phát hiện khác ngoài 3 câu hỏi

- **(a) Quy ước "số trang ở dòng ĐẦU của mục xuống dòng" — Bo Friberg, ngược với giả định Y2-4.**
  PyMuPDF rawdict idx 6: `'Chapter 8   Tea Cakes, Pound Cakes, Muffins, and Other '` y=385–395,
  `'383'` y=386.5–394.5 (**cùng dòng**), `'Quick Breads'` y=397–407 (dòng sau); IL cũng vậy
  (`'Chapter 10 Basic Chocolate Work and Decorating 451 | Techniques'`, `'…Bavarian 755 | Creams'`).
  Bước 3 của Y4 ("tách NGAY SAU dòng có số") sẽ **xé dòng nối `Techniques`/`Creams` sang mục kế tiếp**
  nếu 2 mục như vậy nằm chung 1 paragraph 3 dòng (`m/L = 2/3` ⇒ kích hoạt). Trên trang này chưa xảy
  ra chỉ vì layout model tách từng mục thành paragraph riêng — nhưng đây là sách thứ 2 trong chính
  `data/uploads/` dùng quy ước ngược, không thể coi là ngoại lệ. **Đề xuất luật nối dòng**: dòng không
  đánh dấu đứng **ngay sau** dòng đánh dấu, có `x` đầu dòng **thụt vào** hơn dòng đánh dấu (Friberg:
  284 vs 230) ⇒ thuộc group **trước**; ngược lại (Figoni `'Flour and Dough Additives and'` cùng x với
  `'Treatments 72'`; LCB `'Pâte sucrée—Sweet Shorcrust'` cùng x với các mục) ⇒ thuộc group **sau** như
  hiện tại. Đã kiểm luật này bằng tay trên 3 sách — `[CHƯA VERIFY]` với sách khác; 7.4-a phải có 1
  fixture Friberg.
- **(b) Recall trên LCB không phải 100%**: 84 dòng mục có số trang trên 2 trang Contents; sau TOC-1 còn
  **2 cặp dính** (332+336, 348+350 — 2 dòng tỷ lệ 0.43/0.66 ở Z3). Ngoài ra babeldoc gốc (nhánh
  short-line `:891-895`, flag production `--split-short-lines 0.8`) đã cắt sẵn nhiều mục xuống dòng
  thành nửa-mục nằm ở 2 paragraph khác nhau (`'…Sweet Shorcrust'` cuối para 82, `'Pastry 326'` đầu para
  83; para 84 = `'Dough 340 | Les Crèmes et Meringues—'`, `m = 1` ⇒ TOC-1 không chạm) — không phải lỗi
  TOC-1, nhưng Y9 nên ghi "đã thấy khớp trên 2 đầu sách" thành **"Figoni 20/20, LCB ~82/84"**.
- **(c) `str.isdigit()` nhận cả chữ số trên (`'²'.isdigit() == True`)** — chú thích cuối dòng
  (`'…flour²'`) có khe 0 nên không kích hoạt, nhưng nên dùng **ASCII `0-9`** cho `k` để khỏi phụ thuộc
  khe. Nhỏ, sửa khi implement.
- **(d) Không có gì ở tầng IL để TOC-1 dựa vào cho Friberg**: số trang là paragraph riêng (font 8pt,
  x=526) ⇒ Ca C trên sách kiểu này nằm ở tầng **layout/paragraph grouping**, ngoài tầm TOC-1. Ghi vào
  Y9 như một biên rõ ràng ("số trang tách thành paragraph riêng ⇒ không xử lý").
- **(e) FP-7 (index) verify thật**: LCB Subject Index, 16 paragraph nhiều dòng, **0** kích hoạt (khe sau
  dấu phẩy ≈ khoảng trắng từ). Y12 có thể chuyển FP-7 sang ✅ Verified với fixture `lcb_index`.

#### Z8. Khuyến nghị

**Tiếp tục sang spike 7.4-a — CÓ**, với thứ tự và sửa đổi sau:

0. **Trước 7.4 (P0, task riêng, qua Reviewer)**: hotfix 7.2 theo Z6 (`update_unicode=True` cho cả 2
   paragraph + copy `render_order`), re-run live E2E 7.2 với gate mới **"0 mục còn tiếng Anh"** (đếm
   residue bằng regex chữ Anh/không dấu trên text output), sửa lại đoạn "Quan sát thêm" của CHANGELOG
   7.2 cho đúng nguyên nhân. Nếu bỏ qua bước này, TOC-1 sẽ kế thừa cùng lỗi nếu Dev copy nguyên
   `_split_numbered_list_paragraphs_on_page`.
1. **Giữ**: hook `process_independent_paragraphs` (Y6), ngưỡng 0.8 theo `visual_bbox`, `m ≥ 2`,
   `m/L ≥ 0.6`, monotonic **cứng**, không hỗ trợ La Mã, TOC-1b tắt.
2. **Thêm**: (i) guard bỏ qua paragraph có tâm trong box layout `table` (Z3); (ii) luật dòng nối theo
   thụt đầu dòng (Z7-a); (iii) `k` chỉ đếm ASCII digit (Z7-c); (iv) log 1 dòng mỗi khi cổng monotonic
   hoặc cổng `m/L` chặn một paragraph có `m ≥ 2` — để 7.4-e có số liệu thay vì tin lý thuyết.
3. **Fixture 7.4-a phải gồm** (tất cả đã có lệnh tái tạo ở Z1): Figoni Contents p7+p8, **LCB Contents
   p6+p7** (2 cột, recall ≠ 100%, oracle: 82/84), **Friberg Contents** (quy ước ngược, oracle: 0 tách
   sai + `Techniques`/`Creams` không bị xé nếu dựng ca tổng hợp), Figoni p25 công thức (FP-4 oracle: 0),
   LCB index p408 (FP-7 oracle: 0). Không cần trang references riêng — cơ chế giống index.
4. **Gate 7.4-d (R6-03) phải đo 2 thứ, không chỉ 1**: số block/ranh giới mục (như Y11) **và** số mục
   còn tiếng Anh trong output (Z6 chứng minh gate thứ 2 mới bắt được lỗi thật).
5. **Sửa văn bản Y7/Y12**: bỏ mô tả "khe an toàn rộng 0.64 vs 1.0", thay bằng phân bố thật (Z3); hạ
   trọng số bằng chứng "0 FP/4657 block PyMuPDF" xuống mức "không dùng làm bằng chứng"; sửa `:247`
   thành `:245`; sửa lập luận `xobj_id is not None` (Z2).

**Bảng trạng thái verify của riêng section này (R5-01)**

| Claim | Trạng thái |
|---|---|
| FP-4 không kích hoạt trên 3 trang công thức Figoni (ô bảng = paragraph 1 dòng) | ✅ Verified — dump IL mới, Z1 |
| FP-7 không kích hoạt trên LCB index | ✅ Verified — dump IL mới |
| TOC-1 tái mô phỏng khớp 20/20, 66 điểm tách | ✅ Verified — script riêng trên dump 7.3 |
| LCB Contents: 11 paragraph kích hoạt, 64 điểm tách, 2/84 mục sót, monotonic 11/11 | ✅ Verified — dump IL mới |
| Friberg: số trang ở dòng đầu mục xuống dòng | ✅ Verified — rawdict y + dump IL |
| 7.2 tạo paragraph `unicode=''` ⇒ translator bỏ qua ⇒ giữ tiếng Anh | ✅ Verified — source (`sitecustomize.py:227`, `il_translator_llm_only.py:556-568`, `translation_config.py:187`) + dump `wd72c`/`wd74c` + PDF `live72` |
| `xobj_id = 0` (không phải `None`) cho nội dung chính | ✅ Verified — 9 dump |
| `fix_overlapping_paragraphs` no-op trên TOC Figoni (khe 2.85–2.95pt) | ✅ Verified — đo box theo `visual_bbox` kể cả dummy space |
| Luật dòng nối theo thụt đầu dòng đúng cho sách ngoài 3 cuốn đã xem | ⚠️ `[CHƯA VERIFY]` |
| Bảng công thức không bị layout model nhận là `table` (nhãn `plain text`) có kích hoạt TOC-1 không | ⚠️ `[CHƯA VERIFY]` — chưa có mẫu |
| Giá trị chống FP thực tế của cổng monotonic | ⚠️ Chưa chứng minh — chưa từng chặn gì trên dữ liệu |

---

### Bug #7 Ca C — Quyết định cuối sau phản biện Domain Expert + kế hoạch spike 7.4-a (Tech Lead, 2026-09-08)

> **ĐÂY LÀ QUYẾT ĐỊNH CUỐI ĐỂ GIAO DEV.** Section này **thay thế** phần thiết kế Y4/Y7/Y10/Y11 của
> mục "Bug #7 Ca C — Đề xuất thiết kế fix mục lục" (Y0–Y13 giữ nguyên làm hồ sơ điều tra). Nơi nào
> mâu thuẫn, **section này thắng**. Không còn bước "chờ duyệt thêm" — Protocol 2 đã qua ở vòng
> trước; việc tiếp theo là Dev chạy spike 7.4-a theo AA8.
>
> Viết theo đúng khuôn mẫu "Bug #7/#8 — Final Decision sau phản biện Domain Expert" (X0–X10): trả
> lời **từng** điểm phản biện, rồi chốt.

#### AA0. Phán quyết một dòng

Domain Expert **đúng ở 9/10 điểm**, gồm cả điểm quan trọng nhất (Z6 — bug `unicode=""` của 7.2, đã
hotfix ở `a31ac42`). Tôi **KHÔNG ĐỒNG Ý đúng 1 điểm**: đề xuất Z8-2(i) *"guard bỏ qua paragraph có
tâm nằm trong box layout `table`"*. Tôi đã tự đo và guard đó **giết 5/11 paragraph mục lục + 24/64
điểm tách của Le Cordon Bleu** (trang Contents thứ 2 của LCB **bị chính layout model gán nhãn
`table`**), trong khi **không cứu được gì** trên cả 3 trang công thức bánh (ở đó TOC-1 vốn đã kích
hoạt 0 lần, và **không paragraph nhiều dòng nào** có tâm trong box `table`). Thay bằng một guard
khác **rẻ hơn, mạnh hơn, không mất recall**: **deny-list theo `paragraph.layout_label`** — bằng
chứng ở AA3.

Thiết kế chốt là **TOC-1 v2** (AA4/AA5/AA6). Oracle cuối cùng, tự đo lại trong task này trên **12 bộ
dump IL thật**: **31 paragraph kích hoạt / 130 điểm tách** trên 4 trang mục lục, **0 kích hoạt** trên
**8 trang không phải mục lục** (3 trang công thức/bảng, 1 trang index, 4 trang văn xuôi/list).

#### AA1. Tôi đã tự verify lại những gì trong task này (Protocol 5 R5-01)

**Không kế thừa số liệu của ai.** Tôi viết script riêng (`toc1_v2.py`, không dùng `toc1_sim.py` của
Expert, không dùng script của vòng Y) và chạy trên dump IL thật:

| Việc | Kết quả |
|---|---|
| Tái tạo số liệu của Expert trên LCB | ✅ **Khớp tuyệt đối**: 11 paragraph kích hoạt, 64 điểm tách (6 fire/40 cut ở p0 + 5 fire/24 cut ở p1), monotonic 11/11 |
| Tái tạo số liệu của vòng Y trên Figoni | ✅ **Khớp tuyệt đối**: p7 = 8 fire/28 cut, p8 = 12 fire/38 cut ⇒ **20 paragraph / 66 điểm tách** |
| `paragraph_finder.py:245` là `page.pdf_paragraph = paragraphs` | ✅ Đọc trực tiếp — **Expert đúng**, Y12 ghi nhầm `:247` |
| `_same_layout_and_xobj` (`:382-391`) có đòi `xobj_id is not None` | ✅ Source đúng như Y1 ghi, **nhưng suy luận của Y1 sai**: đo trên dump thật, `xobj_id` chỉ nhận **`-1`** (101 paragraph rỗng) và **`0`** (56 paragraph nội dung) trên `figoni_p25_recipe` — **không bao giờ `None`** ⇒ guard đó **không chặn gì**. Expert đúng; Expert ghi "`= 0`", chính xác hơn là **`0` hoặc `-1`, không bao giờ `None`** |
| `page.page_layout` có `class_name` + `box` + `id` để làm guard bảng | ✅ Verified — `figoni_p25_recipe` có 101 entry: `fallback_line`×82, `abandon`×9, `title`×4, `plain text`×3, **`table`×3** |
| Guard `table` theo hình học có mất recall không | ✅ **Verified — CÓ, mất nặng** (AA3) |
| Nhãn của **mọi** paragraph kích hoạt TOC-1 | ✅ **31/31 đều là `'plain text'`** — không có `title`, `abandon`, `table`, `fallback_line` nào |
| Slug in ấn `abandon` lọt luật mức dòng | ✅ Verified — LCB `'57131_fm_i_xv.indd 5'` ratio **0.82**, Figoni `'c04.indd 62'` ~0.92 (Expert). Chỉ thoát vì là paragraph **1 dòng** |
| Độ nhạy ngưỡng `TOC_GAP_RATIO` | ✅ Quét 0.5 → 1.0 trên **12 dump**: FP **luôn = 0**, recall chỉ đổi 131 → 128 điểm tách. **Ngưỡng KHÔNG phải bộ lọc chính** (AA2/Z3) |
| Luật dòng nối theo thụt đầu (Z7-a) có phải no-op trên dữ liệu hiện có | ✅ Verified — **6 ranh giới "dòng đánh dấu → dòng không đánh dấu"** trong toàn bộ paragraph kích hoạt, delta thụt đầu dòng = **−13.0, −1.1, +0.0, +0.0, +0.0, +0.1 pt** ⇒ với ngưỡng 1.0 em, **no-op tuyệt đối** |
| Hotfix Z6 đã ship chưa | ✅ Commit `a31ac42` — `update_unicode=True` cho **cả 2** lời gọi. ⚠️ **`render_order` KHÔNG được copy** (grep `render_order` trong `src/babeldoc_shim/sitecustomize.py` = 0 hit) ⇒ nợ Y10-b **vẫn còn nguyên** |

**Nguồn dữ liệu (còn sống, đã kiểm tra hôm nay 2026-09-08)** — 6 dump mới của Expert **và** PDF nguồn
đã trích sẵn, nằm tại
`/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/2d559074-2821-4566-91ff-969cf281d898/scratchpad/`
(`pdfs/*.pdf`, `wd/<tên>/<tên>/paragraph_finder.json`, `run_all.sh` để tái tạo). Cộng 6 dump cũ ở
`/tmp/bdprobe/wd_toc*`, `/tmp/bdprobe/wd74c`, `/tmp/bdprobe/wd72c`, `/tmp/bdprobe/wd_p20`,
`/tmp/bdprobe/wd_p22`. **Đây vẫn là artifact tạm** — nhiệm vụ số 1 của 7.4-a là commit golden fixture
(AA8 bước 1).

#### AA2. Trả lời từng điểm phản biện của Domain Expert

| # | Điểm Expert nêu | Phán quyết | Lý do |
|---|---|---|---|
| Z2-a | Y12 ghi `:247`, đúng là `:245` | ✅ **ĐỒNG Ý** | Tự đọc lại source. Đính chính ở AA11 |
| Z2-b / Z5-a | Lập luận "guard `xobj_id is not None` chặn `merge_alternating_line_number_paragraphs`" là **SAI** | ✅ **ĐỒNG Ý** | Tự đo: `xobj_id ∈ {0, −1}`, không bao giờ `None`. **Kết luận "không bị gộp lại" vẫn đứng**, nhưng nhờ `_is_ascii_digit_or_space_paragraph` (paragraph TOC-1 luôn có chữ) + `layout_id` phải trùng + TOC-1 chèn liền kề nên không có paragraph thuần số chen giữa. **Dev bị CẤM** viết test/comment dựa vào guard `xobj_id` |
| Z3-a | FP-4 (bảng công thức) **không kích hoạt** vì layout model đã tách mỗi ô thành paragraph `fallback_line` 1 dòng | ✅ **ĐỒNG Ý** — tự đo lại 3 trang, xác nhận 0 kích hoạt. Đây là rủi ro `[UNVERIFIED]` lớn nhất của Y12, **nay đóng lại** ở mức "3 trang công thức thật của cuốn chính" | Bổ sung của tôi: trên cả 3 trang, **số paragraph nhiều dòng có tâm trong box `table` = 0** — tức FP-4 không những không xảy ra, mà còn **không thể** được cứu bởi guard `table` |
| Z3-b | Nếu cột công thức có bị tách từng dòng thì đó là **cải thiện**, không phải hỏng | ✅ **ĐỒNG Ý** | Đúng bản chất Ca C. Rủi ro duy nhất còn lại là `unit_count`/mode-scale (X7) — giữ ràng buộc thứ tự 7.4 trước 8.1 |
| Z3-c | **Đề xuất guard `table` theo hình học** | ❌ **KHÔNG ĐỒNG Ý — BÁC BỎ** | Chi tiết bằng chứng ở **AA3**. Thay bằng deny-list `layout_label` |
| Z3-d | Mô tả "khe an toàn rộng (TOC 1.0 vs văn xuôi 0.64)" là **sai/gây hiểu nhầm** | ✅ **ĐỒNG Ý** | Tự đo thêm: quét ngưỡng 0.5→1.0 trên 12 dump cho FP = 0 ở **mọi** ngưỡng, recall chỉ đổi 131→128. Ngưỡng **không** là bộ lọc; **cổng cố kết paragraph mới là**. Giữ 0.8 vì đó là ngưỡng đã có nhiều dữ liệu nhất, **không** vì "khe an toàn". Đính chính ở AA11 |
| Z3-e | "0 FP / 4657 block PyMuPDF" **gần như không có trọng lượng bằng chứng** (phép quét đó không phát hiện nổi chính mục lục) | ✅ **ĐỒNG Ý HOÀN TOÀN** | Rút khỏi mọi lập luận. Bằng chứng FP hợp lệ **chỉ còn** 12 bộ dump IL. Đính chính ở AA11 |
| Z4 | Giữ cổng monotonic làm **điều kiện cứng**; rủi ro "gom chéo cột" là lý thuyết | ✅ **ĐỒNG Ý** | Tự xác nhận 31/31 paragraph kích hoạt đều monotonic, **0** paragraph bị cổng này chặn. Chấp nhận Z8-2(iv): **log 1 dòng mỗi lần cổng chặn** để 7.4-e có số liệu thật thay vì lý thuyết |
| Z5-c | Hook sớm còn được `update_paragraph_data(..., update_unicode=True)` ở `:293-294` — **TL bỏ sót, và đây là lý do mạnh nhất** | ✅ **ĐỒNG Ý, và nâng lên lý do #1** | Chính là cơ chế gây Bug Z6 cho 7.2. Hook `process_independent_paragraphs` khiến TOC-1 **miễn nhiễm** với lớp lỗi đó **theo thiết kế**, không phải nhờ nhớ gọi đúng cờ. Cập nhật thứ tự lý do ở AA6 |
| Z5-b | `fix_overlapping_paragraphs` (`:302`) chỉ sửa `box`, no-op trên Figoni (khe 2.85–2.95pt), nhưng là **khác biệt hành vi thật** so với hook 7.2 | ✅ **ĐỒNG Ý** | Đưa vào gate đo của 7.4-e (AA8 bước 6) |
| Z6 | 7.2 ship với bug `unicode=""` ⇒ paragraph tách ra **không được dịch** | ✅ **ĐỒNG Ý — phát hiện đúng và quan trọng nhất của cả vòng phản biện** | Đã hotfix `a31ac42`, Reviewer APPROVE, live 0/35 + 0/40 mục còn tiếng Anh. **Điều kiện tiên quyết Z8-0 coi như ĐÃ THOẢ.** ⚠️ Phần `render_order` của Z8-0 **chưa làm** — xem AA10-b |
| Z7-a | Bo Friberg đặt số trang ở **dòng ĐẦU** của mục xuống dòng ⇒ cần luật dòng nối theo thụt đầu dòng | ✅ **ĐỒNG Ý CÓ ĐIỀU KIỆN — nhận vào thiết kế** | Tự đo: trên **toàn bộ** 6 ranh giới "đánh dấu → không đánh dấu" của 31 paragraph kích hoạt, thụt đầu dòng = −13.0 … +0.1 pt ⇒ với ngưỡng **1.0 × font_size** luật này là **no-op tuyệt đối** trên dữ liệu hiện có (Friberg: 284 vs 230 = **6.75 em**, cách ngưỡng rất xa). Nhận vì rẻ + hướng thất bại an toàn; **điều kiện**: spike phải chứng minh nó là no-op (gate AA9-4) |
| Z7-b | Recall LCB là ~82/84, không phải 100% | ✅ **ĐỒNG Ý** | Sửa Y9 (AA11). Ghi thành chỉ tiêu gate riêng cho LCB |
| Z7-c | Dùng ASCII `0-9` thay `str.isdigit()` (`'²'.isdigit()` là True) | ✅ **ĐỒNG Ý** | Vào spec AA4 bước 2 |
| Z7-d | Friberg: số trang là paragraph **riêng** ⇒ Ca C của sách kiểu này nằm ngoài tầm TOC-1 | ✅ **ĐỒNG Ý** | Ghi thành **biên thiết kế tường minh** (AA4, bảng biên). Tự xác nhận: TOC-1 v2 kích hoạt **0** trên `friberg_toc` — đúng như dự đoán, và đây là **kết quả mong đợi**, không phải FN cần sửa |
| Z7-e | FP-7 (index) đã verify thật trên LCB index | ✅ **ĐỒNG Ý** | Chuyển FP-7 sang ✅ Verified (AA12) |
| Z8-4 | Gate 7.4-d phải đo **2** thứ: ranh giới mục **và** số mục còn tiếng Anh | ✅ **ĐỒNG Ý — bắt buộc** | Vào gate AA9-6. Chính là bài học R6-03 từ Z6 |

#### AA3. Điểm KHÔNG ĐỒNG Ý — bác bỏ guard `table` theo hình học (Z8-2 mục i)

Expert đề xuất: *"bỏ qua paragraph có tâm nằm trong box layout `table`"*. Tôi đã cài đúng luật đó vào
mô phỏng và đo trên **cùng** bộ dump Expert dùng:

| Dump | Không guard | **Có guard `table` hình học** |
|---|---|---|
| `lcb_toc` trang 0 | 6 fire / 40 cut | 6 fire / 40 cut |
| **`lcb_toc` trang 1** | **5 fire / 24 cut** | **0 fire / 0 cut** ❌ |
| `figoni_p7_toc` | 8 fire / 28 cut | 8 fire / 28 cut |
| `figoni_p8_toc` | 12 fire / 38 cut | 12 fire / 38 cut |
| `figoni_p25_recipe`, `figoni_p45_recipe`, `figoni_p7_tables` (3 trang công thức/bảng) | 0 / 0 | 0 / 0 (**không cứu được gì**) |
| `lcb_index`, `friberg_toc` | 0 / 0 | 0 / 0 |

**Nguyên nhân**: layout model của babeldoc gán **1 box `class_name="table"`** phủ gần trọn trang
Contents thứ 2 của Le Cordon Bleu (mục lục 2 cột **trông giống bảng**) — **8/8** paragraph nhiều dòng
của trang đó có tâm nằm trong box ấy. Guard sẽ **xoá 37.5% tác dụng của fix trên chính cuốn sách thứ 2
dùng để chứng minh tính tổng quát**.

**Và guard đó không thể cứu FP-4 ngay cả về nguyên tắc**: trên cả 3 trang công thức/bảng, số paragraph
**nhiều dòng** có tâm trong box `table` = **0** (đo thật). Lý do chính là điều Expert đã chỉ ra ở Z3:
trong vùng bảng, mỗi ô thành **paragraph 1 dòng** `fallback_line` ⇒ `L < 2` ⇒ TOC-1 không xét. Còn ca
FP-4 thật sự đáng sợ — **bảng công thức không kẻ khung, bị gán nhãn `plain text`** (Expert tự đánh dấu
`[CHƯA VERIFY]`) — thì **theo định nghĩa không có box `table`** nên guard cũng vô hiệu. ⇒ Guard này là
**toàn chi phí, không lợi ích**.

**Thay bằng: deny-list theo `paragraph.layout_label`** (rẻ hơn, không phụ thuộc hình học, đo được):

- Bằng chứng recall: **31/31** paragraph kích hoạt trên 4 trang mục lục đều có `layout_label ==
  'plain text'` ⇒ deny-list **không mất một điểm tách nào** (đã chạy: 20/66 Figoni + 11/64 LCB giữ
  nguyên sau khi bật deny-list).
- Bằng chứng phòng thủ: lớp nội dung **có tỷ lệ khe cao nhất** trong toàn bộ dữ liệu mà **không phải**
  mục lục là **slug nhà in nhãn `abandon`** (`'57131_fm_i_xv.indd 5'` = 0.82; Figoni `'c04.indd 62'` ≈
  0.92). Hôm nay chúng chỉ thoát nhờ là paragraph 1 dòng — **một sự may mắn, không phải một luật**.
  Deny-list biến may mắn đó thành luật.

Nếu sau này có bằng chứng thật về FP trong vùng bảng, mở lại — **nhưng lúc đó phải là luật khác**, vì
guard hình học đã chứng minh là chọn nhầm trục.

Để không mất dấu: TOC-1 v2 **vẫn tính** cờ "tâm paragraph nằm trong box `table`" và **chỉ ghi log**
(`toc_split: fired_inside_table_box=N`), không dùng để chặn. 7.4-a/7.4-e báo cáo con số này.

#### AA4. TOC-1 v2 — thiết kế CHỐT (thay thế Y4)

Toàn bộ quyết định nằm trong module thuần Python `src/babeldoc_shim/toc_split.py` (không import
babeldoc), dùng chung bởi `sitecustomize.py` và test — đúng khuôn `numbered_list_split.py` của 7.2
(R6-02: test phải gọi **đúng** logic production).

**Bước 0 — cổng paragraph (MỚI, thay guard `table` của Expert)**
Bỏ qua ngay nếu `paragraph.layout_label` (chuẩn hoá lower/strip) thuộc **deny-list**:
`abandon`, `header`, `footer`, `page_header`, `page_footer`, `table`, `table_cell`, `wired_table_cell`,
`wireless_table_cell`, `table_cell_hybrid`, `table_text`, `table_caption`, `table_footnote`, `figure`,
`figure_caption`, `figure_text`, `formula`, `isolate_formula`, `formula_caption`.
Bỏ qua nếu số composition `L < 2`.
(Tên nhãn lấy từ tập hợp lệ trong `utils/layout_helper.py:655-690` và `:789-845` của babeldoc 0.6.4 —
đã đọc thật.)

**Bước 1 — chuẩn bị ký tự của một dòng**
Lấy `composition.pdf_line.pdf_character`, **bỏ mọi ký tự `.isspace()`** (gồm dummy space do
`add_space_dummy_chars` chèn, `paragraph_finder.py:279`), rồi **tự sort theo `visual_bbox.box.x`** —
bắt buộc, vì cả 4 lời gọi sort của babeldoc đều bị comment (`:305,696,738,772`, X4-4). Bỏ qua dòng có
< 2 ký tự.

**Bước 2 — đánh dấu "đuôi mục TOC"** (tất cả điều kiện phải đúng)
1. `k` = độ dài dãy **ASCII `0-9`** liền cuối (**không** dùng `str.isdigit()` — Z7-c). Loại nếu
   `k == 0`, `k > TOC_MAX_DIGITS`, hoặc `k == len(chars)` (cả dòng là số ⇒ folio/ô bảng).
2. Phần thân (`chars[:-k]`) phải chứa **≥ 1 cụm ≥ 2 chữ cái ASCII** (`[A-Za-z]{2,}`).
3. `1 ≤ n ≤ 9999` với `n` = giá trị dãy số.
4. `size = chars[-k-1].pdf_style.font_size`; bỏ qua nếu `size <= 0`.
5. `gap = chars[-k].visual_bbox.box.x − chars[-k-1].visual_bbox.box.x2`
   (**hệ đo bắt buộc: `visual_bbox`** — chốt theo Z3, KHÔNG dùng advance-width của PyMuPDF).
6. `ratio = gap / size ≥ TOC_GAP_RATIO`.

**Bước 3 — cổng cố kết ở mức paragraph** (lớp chống FP **chính**, không phải ngưỡng ở bước 2)
`m` = số dòng đánh dấu, `L` = số composition. Chỉ tách khi **cả ba**:
`m ≥ TOC_MIN_TAIL_LINES` **và** `m / L ≥ TOC_MIN_TAIL_FRACTION` **và** dãy `n` **không giảm**
(cho phép bằng nhau). Khi cổng `m/L` hoặc monotonic chặn một paragraph có `m ≥ 2`, **ghi log 1 dòng**
(Z8-2 iv).

**Bước 4 — điểm tách + luật dòng nối (MỚI, Z7-a)**
Với mỗi dòng đánh dấu ở chỉ số `i`: đặt `j = i`; **trong khi** composition `j+1` tồn tại, là `pdf_line`
**không** được đánh dấu, và `min_x(dòng j+1) ≥ min_x(dòng i) + TOC_CONT_INDENT_EM × size(dòng i)`
⇒ `j += 1` (dòng nối kiểu Bo Friberg thuộc **group trước**). Ranh giới nằm **ngay sau** composition `j`;
bỏ nếu `j == L-1`.
Composition không phải `pdf_line` (`pdf_formula`, `pdf_character`) không bao giờ được đánh dấu và dính
vào group liền trước — giống hệt 7.2.

**Bước 5 — thực thi**
Cắt `pdf_paragraph_composition` theo group. Group đầu **giữ nguyên object paragraph gốc**; mỗi group sau
tạo `PdfParagraph` theo **đúng nguyên mẫu babeldoc `paragraph_finder.py:868-888`**: `box=Box(0,0,0,0)`,
`unicode=""`, `debug_id=generate_base58_id()`, copy `layout_label` + `layout_id`, rồi
`paragraphs.insert(...)`. **KHÔNG cần** tự gọi `update_paragraph_data(update_unicode=True)` và **KHÔNG
cần** tự gán `render_order` — hook ở AA6 nằm **trước** `:293-294` và `:310` nên babeldoc tự làm cả hai.
Đây chính là điểm khiến TOC-1 miễn nhiễm với bug Z6 **theo thiết kế**.

**Biên thiết kế tường minh (cố ý KHÔNG xử lý)**

| Dạng | Xử lý |
|---|---|
| Số trang cuối dòng, khe rộng, cùng paragraph (Figoni, LCB) | ✅ Ca chính |
| Dot leader ≥ 20 chấm | ✅ babeldoc gốc đã lo (`:864-866`) |
| Dot leader < 20 chấm | ❌ TOC-1b **TẮT** ở v1 (`TOC_DOT_LEADER_FALLBACK = False`) |
| Số trang La Mã (`"Preface vii"`) | ❌ Cố ý không hỗ trợ (Y9) |
| **Số trang nằm ở paragraph RIÊNG (Bo Friberg)** | ❌ **Ngoài tầm TOC-1** — lỗi ở tầng layout/grouping. `friberg_toc` kích hoạt 0 là **đúng**, không phải FN (Z7-d) |
| Mục bị `--split-short-lines` cắt sẵn sang 2 paragraph (LCB) | ❌ Ngoài tầm — nguồn của 2/84 mục sót (Z7-b) |

#### AA5. Tham số cuối

| Tham số | Giá trị chốt | Căn cứ |
|---|---|---|
| `TOC_GAP_RATIO` | **0.8** (theo `visual_bbox`) | Quét 0.5→1.0 trên 12 dump: FP = 0 ở mọi mức, recall 131→128. Giữ 0.8 vì có nhiều dữ liệu nhất và chặn slug `abandon` 0.82 ở mức dòng. **Không phải "khe an toàn"** |
| `TOC_MIN_TAIL_LINES` | **2** | Tín hiệu chống FP mạnh nhất (Y7 + Z3 đều đồng ý) |
| `TOC_MIN_TAIL_FRACTION` | **0.6** | 31/31 paragraph mục lục thoả |
| `TOC_MIN_BODY_ALPHA_RUNS` | **1** (cụm ≥ 2 chữ cái ASCII) | Loại ô bảng thuần số, `"4.0"`, folio |
| `TOC_MAX_DIGITS` | **4** | Số trang sách ≤ 9999 |
| `TOC_REQUIRE_NON_DECREASING` | **True** (cứng) | Z4. Log mỗi lần chặn |
| `TOC_CONT_INDENT_EM` | **1.0** | Đo thật: ranh giới thật ≤ 0.1pt; Friberg 6.75 em. Biên rất rộng |
| `TOC_DOT_LEADER_FALLBACK` | **False** | Chưa có dữ liệu |
| `TOC_LAYOUT_LABEL_DENY` | danh sách ở AA4 bước 0 | AA3 |
| Cờ runtime | `BABELDOC_SHIM_TOC_SPLIT`, `Settings.babeldoc_toc_split_enabled` — **mặc định `False` ở lần ship đầu**, bật sau khi QA live xanh | Giữ nguyên Y10-a: kill-switch RIÊNG, độc lập với 7.1/7.2 |

#### AA6. Điểm hook cuối

**Giữ nguyên đề xuất Y6**: bọc `ParagraphFinder.process_independent_paragraphs(paragraphs,
median_width)` (`paragraph_finder.py:287`) — chạy hàm gốc trước, rồi chạy TOC-1 v2 trên **cùng list
`paragraphs`** (mutate in-place; `page.pdf_paragraph` trỏ cùng object list, gán ở **`:245`**).

Lý do, **đã xếp lại theo phản biện Z5-c**:

1. **(Mới, mạnh nhất)** `:293-294` gọi `update_paragraph_data(paragraph, update_unicode=True)` cho
   **mọi** paragraph ⇒ paragraph TOC-1 tạo ra **luôn có `unicode` đúng** ⇒ **miễn nhiễm với đúng lớp
   bug đã làm hỏng 7.2** (Z6: `unicode=""` ⇒ `il_translator_llm_only.py:556-568` bỏ qua ⇒ không dịch).
   Đây là **an toàn theo cấu trúc**, không phải theo trí nhớ của người viết code.
2. `_set_paragraph_render_order` (`:310`) chạy sau ⇒ paragraph mới có `render_order` thật (tránh nợ
   Y10-b của 7.2).
3. `add_debug_info` (`:307`) vẽ debug rect cho paragraph mới — phục vụ chính việc đo của 7.4.
4. Đúng tầng ngữ nghĩa: nhánh mục lục dot-leader của babeldoc cũng nằm trong hàm này.

**Bề mặt tương tác đã trace hết (Y6 + Z5, không còn ẩn số)**: `merge_alternating_line_number_paragraphs`
(`:290-291`) không gộp lại được (lý do đúng: `_is_ascii_digit_or_space_paragraph` + `layout_id`, **không
phải** `xobj_id`); `fix_overlapping_paragraphs` (`:302`) chỉ sửa `box`, đo được là no-op trên Figoni
(khe dọc 2.85–2.95pt) nhưng **có thể cắt ~1pt** với sách leading chặt ⇒ đưa vào 7.4-e; patch 7.2 (bọc
`process`, chạy sau) không xung đột vì mục TOC không có marker đầu dòng.

**Không di dời 7.2 sang hook này trong 7.4** — giữ nguyên quyết định Y6. Ghi tech debt (AA10-b).

#### AA7. Oracle cuối cùng — con số Dev phải tái tạo ĐÚNG ở 7.4-a

Đo bằng TOC-1 v2 đầy đủ (deny-list + luật dòng nối bật):

| Fixture | Loại | fire | cut points | Ghi chú oracle |
|---|---|---|---|---|
| `figoni_p7_toc` | TOC | **8** | **28** | 12 paragraph nhiều dòng; 4 không fire = tiêu đề chương 2 dòng |
| `figoni_p8_toc` | TOC | **12** | **38** | 18 paragraph nhiều dòng |
| `lcb_toc` (2 trang) | TOC 2 cột | **11** | **64** | p0: 6/40, p1: 5/24. `fired_inside_table_box = 5` (chỉ log) |
| `friberg_toc` | TOC quy ước ngược | **0** | **0** | **Đúng theo thiết kế** (AA4 biên) — không phải FN |
| `lcb_index` | FP-7 | **0** | **0** | |
| `figoni_p25_recipe` | **FP-4** | **0** | **0** | |
| `figoni_p45_recipe` | **FP-4** | **0** | **0** | |
| `figoni_p7_tables` | FP-3/FP-4 | **0** | **0** | |
| `p74_77` (4 trang) | hồi quy 7.1 | **0** | **0** | |
| `page14_numbered_list_source` | hồi quy 7.2 | **0** | **0** | |
| `figoni_p20`, `figoni_p22` | bảng + caption | **0** | **0** | |
| **Tổng** | | **31 / 130** | | **0 kích hoạt trên 8 trang không phải mục lục** |

#### AA8. Kế hoạch spike 7.4-a — giao Dev ngay

**Nguyên tắc**: đây là **spike theo R5-02**. Sản phẩm là **bằng chứng + fixture**, KHÔNG phải feature.

**Bước 1 — Bảo toàn bằng chứng (làm ĐẦU TIÊN, trước mọi thứ khác)**
Artifact đang nằm ở `/tmp` và scratchpad phiên khác, **sẽ mất**. Đã kiểm tra còn sống hôm nay
2026-09-08. Gzip và commit **8 file** vào `tests/fixtures/babeldoc/` (đọc bằng `gzip.open(path,"rt")`,
đúng khuôn `paragraph_finder_p74_77_dump.json.gz` đã có):

| File nguồn | Tên fixture đề xuất | gz |
|---|---|---|
| `<SP>/wd/lcb_toc/lcb_toc/paragraph_finder.json` | `toc_lcb_contents_p6_p7_dump.json.gz` | 222KB |
| `<SP>/wd/friberg_toc/friberg_toc/paragraph_finder.json` | `toc_friberg_contents_dump.json.gz` | 53KB |
| `<SP>/wd/lcb_index/lcb_index/paragraph_finder.json` | `toc_lcb_index_dump.json.gz` | 192KB |
| `<SP>/wd/figoni_p25_recipe/.../paragraph_finder.json` | `toc_figoni_p25_recipe_dump.json.gz` | 127KB |
| `<SP>/wd/figoni_p45_recipe/.../paragraph_finder.json` | `toc_figoni_p45_recipe_dump.json.gz` | 165KB |
| `<SP>/wd/figoni_p7_tables/.../paragraph_finder.json` | `toc_figoni_tables_dump.json.gz` | 185KB |
| `/tmp/bdprobe/wd_toc/figoni_p7_toc/paragraph_finder.json` | `toc_figoni_contents_p7_dump.json.gz` | 104KB |
| `/tmp/bdprobe/wd_toc2/figoni_p8_toc/paragraph_finder.json` | `toc_figoni_contents_p8_dump.json.gz` | 133KB |

`<SP>` = `/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/2d559074-2821-4566-91ff-969cf281d898/scratchpad`.
Tổng ≈ **1.2 MB** — chấp nhận được. Cũng copy **6 PDF nguồn** ở `<SP>/pdfs/` vào
`tests/fixtures/babeldoc/toc_sources/` (tổng ~1.1MB) và cập nhật `tests/fixtures/babeldoc/README.md`
với lệnh tái tạo (`<SP>/run_all.sh`, đã có sẵn, dùng đúng flag production của `BabeldocRunner` + LLM
port chết ⇒ **0 token**).

**Nếu file nguồn đã bị xoá**: tái tạo bằng `run_all.sh` — trang cần trích bằng `pymupdf.insert_pdf` từ
`data/uploads/`: Figoni bản đầy đủ idx **40** (`figoni_p25_recipe`), idx **60** (`figoni_p45_recipe`),
idx **22** (`figoni_p7_tables`); Le Cordon Bleu idx **6–7** (`lcb_toc`), idx **408** (`lcb_index`);
Bo Friberg idx **6** (`friberg_toc`). **KHÔNG được tự viết tay mock** (Protocol 5 mục 3).

**Bước 2 — Viết `toc_split.py` ở mức spike**
Đúng spec AA4 + tham số AA5. Thuần Python, không import babeldoc, nhận **dict đã parse từ dump JSON**
(hoặc object IL — cùng tên field) để chạy được offline. **Chưa** wiring vào `sitecustomize.py`.

**Bước 3 — Chạy trên 8 fixture, báo cáo bảng AA7**
Báo cáo **từng fixture**: `fire`, `cut points`, và 3 counter mới: `blocked_by_monotonic`,
`blocked_by_fraction`, `fired_inside_table_box`.

**Bước 4 — Đo riêng luật dòng nối (Z7-a)**
In **mọi** ranh giới "dòng đánh dấu → dòng không đánh dấu" trong các paragraph kích hoạt, kèm delta
thụt đầu dòng. **Kỳ vọng: 6 ranh giới, delta ∈ [−13.0, +0.1] pt ⇒ luật là no-op** (kết quả đo của Tech
Lead). Nếu Dev đo ra khác ⇒ dừng, escalate.

**Bước 5 — Chứng minh hook mutate in-place (mục `[UNVERIFIED]` cuối cùng của Y12)**
Chạy **1** lần babeldoc thật với `sitecustomize.py` đã bọc `process_independent_paragraphs` bằng một
patch **rỗng nhưng có instrument** (chỉ đếm + chèn 1 paragraph đánh dấu tổng hợp), trên
`figoni_p7_toc.pdf`, LLM port chết, `--debug`. Đọc dump ra và xác nhận: (a) paragraph chèn thêm **có mặt**
trong `page.pdf_paragraph`, (b) nó có `unicode != ""`, (c) nó có `render_order is not None`.
**Đây là bằng chứng sống cho AA6 lý do 1 và 2** — bắt buộc, vì đó chính là cơ chế bảo vệ khỏi bug Z6.

**Bước 6 — Báo cáo**
Ghi kết quả vào `docs/CHANGELOG.md` (**đọc file hiện có, APPEND section mới vào cuối, KHÔNG xoá/ghi đè
nội dung cũ** — Protocol 7 R7-03). Kèm bảng đối chiếu với AA7.

**Ngoài phạm vi 7.4-a (làm ở 7.4-b trở đi, chỉ khi spike PASS)**: `sitecustomize.py` patch thứ 3, wiring
`config.py` / `babeldoc_runner.py` / `job_orchestrator.py`, unit test đầy đủ, live E2E, đo hồi quy 11
trang, Reviewer.

#### AA9. Gate PASS/FAIL của 7.4-a

**PASS khi ĐỦ 6 điều**:

1. **Recall Figoni**: `figoni_p7_toc` = **8 fire / 28 cut** và `figoni_p8_toc` = **12 fire / 38 cut**
   (tổng **20 / 66**) — **khớp chính xác**, không xê dịch.
2. **Recall LCB**: **11 fire / 64 cut**, monotonic 11/11. Chấp nhận **≥ 80/84** mục được tách đúng
   (oracle Expert: 82/84; 2 mục sót do `--split-short-lines` cắt sẵn, **không** tính là fail).
3. **FP = 0 tuyệt đối** trên **8** fixture không phải mục lục (`friberg_toc`, `lcb_index`,
   `figoni_p25_recipe`, `figoni_p45_recipe`, `figoni_p7_tables`, `p74_77`, `page14_...`,
   `figoni_p20`+`p22`). **Bất kỳ kích hoạt nào ở đây = FAIL, không có ngưỡng "chấp nhận được"**.
4. **Luật dòng nối là no-op**: 0 điểm tách bị dịch chuyển so với khi tắt luật đó (bước 4).
5. **Bước 5 xanh**: paragraph chèn qua hook có `unicode != ""` **và** `render_order is not None`.
6. **8 fixture + 6 PDF nguồn đã commit** vào `tests/fixtures/babeldoc/`, README cập nhật.

**FAIL ⇒ DỪNG, escalate cho Tech Lead** (không tự chỉnh tham số, không tự đổi thiết kế):

| Triệu chứng | Hành động |
|---|---|
| **Bất kỳ FP nào**, đặc biệt trên `figoni_p25_recipe`/`p45`/`p7_tables` (**FP-4**) | Dừng ngay. Báo cáo **paragraph nào, dòng nào, ratio bao nhiêu, `layout_label` gì**. Tech Lead quyết định — **có thể** mở lại hướng guard bảng theo trục khác |
| Recall lệch oracle AA7 | Dừng. Nhiều khả năng khác hệ đo (`visual_bbox` vs `box`) hoặc quên sort theo x hoặc quên bỏ dummy space |
| Luật dòng nối làm dịch điểm tách | Dừng — nghĩa là ngưỡng 1.0 em sai với dữ liệu thật |
| Bước 5 cho `unicode == ""` hoặc `render_order is None` | **Dừng — nghiêm trọng**: giả định nền của AA6 sai, TOC-1 sẽ tái diễn bug Z6. Tech Lead phải thiết kế lại điểm hook |
| Fixture nguồn đã mất và tái tạo ra số khác | Dừng, báo cáo cả 2 bộ số |

Escalate bằng cách báo cho **PM**, PM chuyển **Tech Lead**. Không escalate thẳng sang tự sửa
Architecture.md.

#### AA10. Nhắc lại ràng buộc quy trình

**(a) ĐÂY VẪN LÀ SPIKE (Protocol 5 R5-02).** Dev **CHƯA ĐƯỢC** viết code production đầy đủ cho tới khi
spike PASS gate AA9: **không** tạo patch thứ 3 trong `src/babeldoc_shim/sitecustomize.py` (trừ patch
instrument tạm của bước 5, **không commit**), **không** wiring
`src/core/config.py` / `src/services/babeldoc_runner.py` / `src/core/job_orchestrator.py`, **không**
viết bộ test đầy đủ 7.4-c. Sản phẩm commit của 7.4-a chỉ gồm: **fixture + `toc_split.py` mức spike +
script đo + entry CHANGELOG**.

**(b) Nợ kỹ thuật vẫn mở, KHÔNG thuộc 7.4** — hotfix `a31ac42` đã sửa `unicode=""` nhưng **chưa** copy
`render_order` (`grep render_order src/babeldoc_shim/sitecustomize.py` = 0 hit). Paragraph do **7.2**
tạo vẫn có `render_order = None` ⇒ `pdf_creater.py:52-55` ép về `9999999999999999` ⇒ ký tự bị vẽ **sau
cùng** trong content stream (Z2, Expert đã trace hạ nguồn). Không crash, chưa thấy triệu chứng.
**Task riêng, ưu tiên thấp.** TOC-1 **không** thừa hưởng lỗi này (AA6 lý do 2).

**(c) Ràng buộc thứ tự (giữ nguyên Y8/X7)**: 7.4 **phải xong trước** bước **8.1**. TOC-1 tăng số
paragraph ⇒ đổi `unit_count` ⇒ đổi mode-scale **xuyên trang** (`typesetting.py:892-935`). Nếu 8.1 đã
đo histogram trước, **số đo đó hết hạn**.

**(d) Gate 7.4-d (làm sau, ghi sẵn để không quên)**: phải đo **2** thứ — ranh giới mục **và** **số mục
còn tiếng Anh** trong PDF output (Z8-4). Bài học Z6: gate chỉ đo cấu trúc đã bỏ lọt một bug production
suốt 1 vòng release.

#### AA11. Đính chính các phát biểu cũ (Y-section)

| Chỗ | Sai | Đúng |
|---|---|---|
| Y12 | "`:247` gán cùng object list" | **`:245`** — `page.pdf_paragraph = paragraphs` |
| Y1, Y6 | "`_same_layout_and_xobj` còn đòi cả hai `xobj_id is not None` ⇒ không gộp" | Source đúng nhưng **suy luận sai**: `xobj_id ∈ {0, −1}`, không bao giờ `None`. Lý do thật: `_is_ascii_digit_or_space_paragraph` + `layout_id` phải trùng + TOC-1 chèn liền kề |
| Y7, Y12 | "khe an toàn rộng: TOC 1.0 vs văn xuôi tệ nhất 0.64" | **Bỏ.** Đo trên `visual_bbox`: TOC Figoni 1.05–1.21, TOC LCB **tràn xuống 0.43**; slug `abandon` **0.82–0.93**. Ngưỡng 0.5→1.0 cho FP = 0 như nhau ⇒ **ngưỡng không phải bộ lọc; cổng cố kết paragraph mới là** |
| Y0, Y8 | "quét toàn sách PyMuPDF: 0 FP / 4657 block" là điểm mạnh | **Rút hoàn toàn.** Phép quét đó không phát hiện nổi chính mục lục (Figoni 0/152 block; LCB 2/184 dòng) ⇒ **không dùng làm bằng chứng** |
| Y9 | "đã thấy khớp trên 2 đầu sách" | **Figoni 20/20 paragraph; LCB ~82/84 mục** (2 mục sót do `--split-short-lines` cắt sẵn) |
| Y4 bước 2 | `str.isdigit()` | **ASCII `0-9`** (`'²'.isdigit()` là `True`) |
| Y4 bước 3 | "tách NGAY SAU mọi dòng đánh dấu" | Thêm **luật dòng nối theo thụt đầu dòng** (AA4 bước 4) cho quy ước kiểu Bo Friberg |
| Y7 FP-4 | "⚠️ chưa đo được — rủi ro thật" | ✅ **Đã đo: 0 kích hoạt** trên 3 trang công thức/bảng thật. Cơ chế bảo vệ là **layout model tách ô thành paragraph 1 dòng**, không phải luật của TOC-1 |
| Y11 bước 7.4-a | Bảng mô tả chung | **Thay bằng AA8 + AA9** |
| Z8-2 (i) | Guard `table` theo hình học | **BÁC BỎ** — thay bằng deny-list `layout_label` (AA3) |

#### AA12. Bảng trạng thái verify của section này (Protocol 5 R5-01)

| Claim | Trạng thái |
|---|---|
| Oracle AA7 (31 fire / 130 cut; 0 FP trên 8 fixture không phải TOC) | ✅ **Verified** — script riêng của Tech Lead trên 12 dump IL thật, trong task này |
| Tái tạo được số của Expert (LCB 11/64) và của vòng Y (Figoni 20/66) | ✅ **Verified** — replication độc lập, khớp tuyệt đối |
| Guard `table` hình học làm mất 5 fire / 24 cut trên `lcb_toc` p1 | ✅ **Verified** — đo trực tiếp, có/không guard |
| Guard `table` hình học **không** cứu được FP-4 (0 paragraph nhiều dòng có tâm trong box `table` trên 3 trang công thức) | ✅ **Verified** |
| 31/31 paragraph kích hoạt có `layout_label == 'plain text'` ⇒ deny-list mất 0 recall | ✅ **Verified** |
| Slug nhà in nhãn `abandon` lọt luật mức dòng (0.82–0.93), chỉ thoát vì là paragraph 1 dòng | ✅ **Verified** — LCB `'57131_fm_i_xv.indd 5'` = 0.82 |
| `TOC_GAP_RATIO` 0.5→1.0 đều cho FP = 0 | ✅ **Verified** — quét 6 mức trên 12 dump |
| Luật dòng nối (1.0 em) là no-op trên dữ liệu hiện có | ✅ **Verified** — 6/6 ranh giới, delta ≤ +0.1pt |
| `page.page_layout[].class_name/box/id` tồn tại, có `"table"` | ✅ **Verified** — dump `figoni_p25_recipe` |
| `xobj_id ∈ {0, −1}`, không bao giờ `None` | ✅ **Verified** — dump thật |
| `paragraph_finder.py:245/:287/:293-294/:302/:307/:310` đúng như mô tả | ✅ **Verified** — đọc source 0.6.4 đã cài, trong task này |
| Danh sách nhãn layout hợp lệ (`layout_helper.py:655-690`, `:789-845`) | ✅ **Verified** — đọc source |
| Hotfix `a31ac42` có `update_unicode=True`, **không** có copy `render_order` | ✅ **Verified** — `git show` + grep |
| Hook `process_independent_paragraphs` mutate in-place, paragraph mới nhận `unicode` + `render_order` | ⚠️ **`[UNVERIFIED]`** — **gate cứng của 7.4-a bước 5**. Đây là mục `[UNVERIFIED]` duy nhất còn lại chặn implement |
| Bảng công thức **không kẻ khung** (nhãn `plain text`) có kích hoạt TOC-1 không | ⚠️ **`[CHƯA VERIFY]`** — chưa có mẫu trong 6 đầu sách. Rủi ro tồn đọng, theo dõi ở 7.4-d/7.4-e; **không chặn** 7.4-a |
| `fix_overlapping_paragraphs` cắt box với sách leading chặt | ⚠️ **`[CHƯA VERIFY]`** — no-op trên Figoni (khe 2.85–2.95pt); đo ở 7.4-e |
| Biên độ TOC-1 làm đổi mode-scale của Bug #8 | ⚠️ **Verified về cơ chế, chưa đo biên độ** — ràng buộc thứ tự AA10-c |

---

### Bug #7 Ca C — Đóng vòng: implement + QA + bật default (2026-09-08)

Cập nhật ngắn (không sửa bảng AA12 ở trên, chỉ đính chính trạng thái mới nhất tại đây theo đúng
tinh thần "section sau thắng khi mâu thuẫn"):

- **Gate 7.4-a bước 5 (hook mutate in-place, dòng `[UNVERIFIED]` duy nhất chặn implement ở AA12)**:
  ✅ **Đã verify sống** trong spike — paragraph probe chèn qua hook có `unicode != ""` và
  `render_order is not None`. Xem `docs/CHANGELOG.md` "Spike 7.4-a".
- **7.4-b→e (implement, test, live E2E, hồi quy)**: hoàn tất, Reviewer APPROVE (`docs/review-report.md`,
  2 lần review: spike + implement đầy đủ). Commit `0aea37b` (spike) → `2c47a03` (implement).
- **QA Vòng 8** (`docs/test-report.md`): PASS — tự chạy lại độc lập qua cả `BabeldocRunner` trực
  tiếp lẫn `JobOrchestrator.run_job()` đầy đủ (DB thật, DeepSeek thật), xác nhận điều kiện AA5
  "bật sau khi QA live xanh" đã thoả.
- **Quyết định**: `Settings.babeldoc_toc_split_enabled` đổi default `False` → **`True`** (PM chốt
  dựa trên khuyến nghị QA — đây là quyết định cơ học đã được AA5 định sẵn tiêu chí từ trước, không
  phát sinh câu hỏi thiết kế mới cần Tech Lead/Domain Expert trao đổi thêm).
- **Nợ kỹ thuật còn mở, KHÔNG chặn release này** (giữ nguyên như AA10-b/AA12, chỉ nhắc lại):
  `render_order` của paragraph do **7.2** tạo vẫn chưa được copy (khác TOC-1 v2 — miễn nhiễm theo
  thiết kế); `fix_overlapping_paragraphs` trên sách leading chặt và bảng công thức không kẻ khung
  vẫn ở mức `[CHƯA VERIFY]` — theo dõi tiếp khi có dữ liệu production thật, không phải điều kiện
  chặn bật default.
- **Ràng buộc AA10-c vẫn còn hiệu lực**: chưa bắt đầu Bug #8 (đo histogram mode-scale, bước 8.1)
  cho tới khi Ca C ổn định trên production thật với default mới — TOC-1 đổi `unit_count` sẽ làm
  hết hạn mọi số đo mode-scale đo trước thời điểm này.

---

## US-16 v2 — Mở rộng phạm vi sang ảnh `/FlateDecode` (2026-09-08)

**Tác giả**: Tech Lead — thiết kế, KHÔNG implement.
**Trạng thái**: ⏸ **Chờ user duyệt (Protocol 2)** — đây là thay đổi phạm vi của business rule đã
chốt (BR-IMGCOMP-02), cùng loại tình huống với S8 của US-16 v1. Không giao Dev trước khi duyệt.
**Quan hệ với US-16 v1 (S1–S10)**: v1 **vẫn còn hiệu lực toàn bộ**, v2 chỉ **mở rộng bước 3 của
S6** (điều kiện lọc filter) và **sửa 1 lỗi tiềm ẩn của S6 bước 8** (`/Decode`, xem V4.4). Mọi
guard, data lineage, vị trí gắn code, cách save của v1 **giữ nguyên không đổi**.

### V1. Kết luận ngắn

Job thật `78674af9-ce15-4d39-bba5-7f8d1e2804fe` (30 trang, 46.87 MB, `status=completed`) chạy
`compress_pdf_images()` **thành công nhưng re-encode 0 ảnh**. Nguyên nhân: file này có **0 xref
`Filter: null`** — 85% dung lượng nằm ở **57 ảnh `/FlateDecode`**, và
`src/postprocess/image_compress.py:81-84` coi *mọi* filter khác `null` là "đã nén rồi, bỏ qua".

`/FlateDecode` là zlib **lossless** — với ảnh chụp nó gần như không nén được gì (đo được: có ảnh
Flate còn **to hơn** kích thước bitmap thô, xref 1144: 10,074,126 bytes cho 1681×1800×4 =
12,103,200 pixel bytes). Coi nó "tương đương đã nén như JPEG" là một suy diễn sai, và là suy diễn
**do code tự mở rộng ra**, không có trong câu chữ của BR-IMGCOMP-02.

Sửa: cho phép re-encode cả `/FlateDecode`, giữ nguyên mọi guard cũ + thêm 3 guard mới.
**Đo thật trên chính file đó: 46.87 MB → 25.19 MB (−46.3%), 1.5 giây, text giống hệt từng trang,
sai khác pixel trung bình 0.0613/255.**

### V2. Nguồn xác thực (Protocol 5 R5-01 / Protocol 1 mở rộng)

Toàn bộ số liệu trong section này do Tech Lead **tự chạy lại từ đầu**, không kế thừa từ brief của
PM — kể cả những con số PM đã báo là đã verify (đúng theo kỷ luật "không nhận claim về hành vi tool
bên ngoài mà không tự chạy"). Kết quả trùng khớp với PM ở mọi chỉ số PM đã đo, và **phát hiện thêm
4 contract mà brief chưa có** (V2.2) — trong đó 2 cái sẽ làm implementation sai nếu không biết.

**Môi trường**: `.venv/bin/python` (Python 3.14, darwin), PyMuPDF **1.28.2**
(`1.28.2 ('1.28.2', '1.28.2', None)`) — cùng version với US-16 v1, nên bảng signature ở S1 vẫn
còn hiệu lực, không verify lại.

**Dữ liệu đo**: `data/outputs/78674af9-ce15-4d39-bba5-7f8d1e2804fe/translated_vi.pdf`
(49,146,122 bytes = 46.87 MB, 30 trang) + 5 job output thật khác (V3.3) + fixture hiện có
`tests/fixtures/babeldoc/job3594a7a3_chunk0_sample_mono.pdf`. Không dùng file dựng tay.

#### V2.1. Xác nhận lại hiện trạng (không chỉ đọc code)

Chạy **đúng logic đang ship** (`Filter != "null"` → skip) trên bản copy của file thật:

```
variant=cur counts={'scanned': 99, 'recompressed': 0, 'skip_filter': 99, ...}
size: 46.87 MB -> 46.87 MB
```

`recompressed=0` — xác nhận bằng chạy thật, không phải suy luận từ đọc code.

#### V2.2. Contract PyMuPDF mới verify được (4 cái, đều ảnh hưởng trực tiếp tới code)

| # | Contract | Bằng chứng chạy thật | Hệ quả thiết kế |
|---|---|---|---|
| C1 | `Pixmap.colorspace.name` **KHÔNG** trả `"DeviceCMYK"` cho ảnh ICCBased — trả chuỗi mô tả: `'ICCBased(CMYK,Artifex CMYK SWOP Profile)'`, `'ICCBased(Gray,Artifex Software sGray ICC Profile)'`, `'Separation(DeviceCMYK,Black)'` | in trực tiếp `pix.colorspace` của xref 1144/1062/889 | Guard dạng `name in {DeviceGray,DeviceRGB,DeviceCMYK}` **loại nhầm 19/19 ảnh cần nén**. Đây **là lỗi đã thực sự mắc phải** trong lúc spike: lần chạy đầu ra `recompressed=0, skip_cs=19`. Phải chấp nhận thêm tiền tố `ICCBased(` |
| C2 | `Pixmap.tobytes("jpeg")` **raise** `FzErrorArgument: code=4: pixmap must be Grayscale, RGB, or CMYK to save as JPEG` với colorspace `Separation` (dù `pix.n == 1`) | 29 xref 1×1 trong chính file thật đều raise | Không có guard colorspace thì 29 xref này rơi vào `except Exception` chung → **29 stack trace `logger.warning(exc_info=True)` cho 1 job 30 trang**, trông như lỗi thật. Cần guard tường minh + đếm riêng |
| C3 | `update_stream(xref, jb, new=1, compress=0)` **tự xoá `/Filter` VÀ `/DecodeParms`** khỏi object dict | in `xref_object()` trước/sau: trước có `/Filter /FlateDecode`, sau **không còn**; inject `/DecodeParms <</Predictor 15…>>` rồi gọi update_stream → `xref_get_key` trả `('null','null')` | **Không cần** thêm bước xoá `/DecodeParms` — PyMuPDF đã lo. Ghi lại để Dev/Reviewer khỏi "sửa cho chắc" |
| C4 | `update_stream` **KHÔNG** xoá `/Decode`; và `Pixmap(doc, xref)` **CÓ áp dụng** `/Decode` | inject `/Decode [1 0]` → samples đổi từ `ffff…` sang `0000…` (`Pixmap APPLIES /Decode: True`); sau `update_stream` key `/Decode [1 0]` vẫn còn nguyên | **Bắt buộc xoá `/Decode`** khi ghi đè: pixel đã được áp dụng Decode 1 lần rồi, để lại key sẽ áp dụng **lần thứ hai** → ảnh âm bản. Xem V4.4 — đây là **lỗi tiềm ẩn có sẵn trong code đang ship**, không phải lỗi do v2 tạo ra |

Contract phụ (verify kèm, dùng để viết guard):

- `xref_set_key(xref, key, "null")` = **xoá key theo ngữ nghĩa PDF**: object dict vẫn hiển thị
  `/DecodeParms null` nhưng `xref_get_key` trả `('null','null')`, và null object ≡ vắng mặt theo
  spec PDF. Đây là cách xoá key duy nhất verify được ở 1.28.2.
- Trên 99 xref ảnh của file thật: `/Decode` xuất hiện ở **62 xref** nhưng **đều là identity**
  (`[0 1]` ×46, `[0 1 0 1 0 1 0 1]` ×16); `/DecodeParms <</ColorTransform 0>>` ở 41 xref DCT.
  Nghĩa là bug C4 **hiện chưa phát tác trên dữ liệu đã có** — nhưng chỉ vì may, không vì code đúng.

### V3. Số liệu đo trên dữ liệu thật

#### V3.1. Phân bố filter của file sự cố (30 trang, 46.87 MB)

| Filter | Số xref | Stream bytes |
|---|---|---|
| `/FlateDecode` | **57** | **28.72 MB** |
| `/DCTDecode` | 42 | 11.12 MB |
| `null` (raw) | **0** | 0 |
| **Tổng ảnh** | 99 | 39.84 MB (**85%** của 46.87 MB) |

#### V3.2. Bên trong 57 ảnh `/FlateDecode`

| Nhóm | Số xref | Bytes | Đặc điểm (đã đo) |
|---|---|---|---|
| ≥ 1 MB | 5 | 23.53 MB | ảnh chụp CMYK, `ICCBased`, bpc=8 |
| 100 KB – 1 MB | 12 | 5.05 MB | ảnh chụp CMYK + 3 ảnh xám `ICCBased(Gray)` |
| 4 KB – 100 KB | 2 | 0.14 MB | — |
| 100 B – 4 KB | **0** | 0 | **không có ảnh nào rơi vào vùng này** |
| < 100 B | 38 | ~0.0004 MB | 1×1 px: 29 `Separation(DeviceCMYK,Black)` (9–11 B) + 9 `DeviceCMYK` (14–55 B) |

Toàn bộ 57 ảnh: `BitsPerComponent = 8`, `/SMask` = 0 (không có), `/ImageMask` vắng mặt.
**Khoảng trống 100 B – 4 KB rỗng hoàn toàn** — đây là căn cứ chọn ngưỡng ở V5 (ngưỡng đặt ở đâu
trong khoảng 100 B–40 KB cũng cho **cùng một kết quả** trên file này, tức kết quả không nhạy cảm
với việc chọn con số).

#### V3.3. Khảo sát rộng — 6 job output thật (chống kết luận từ 1 mẫu, đúng bài học S3)

| Job | Trang | Size | `null` | `/FlateDecode` | `/DCTDecode` | `/CCITTFax` |
|---|---|---|---|---|---|---|
| `78674af9` (sự cố) | 30 | 46.87 MB | 0 | **57 — 28.72 MB** | 42 — 11.12 MB | 0 |
| `136645f9` | 418 | **520.14 MB** | 0 | 393 — 0.08 MB | **1110 — 437.69 MB** | 0 |
| `40cb4746` (đã qua US-16 v1) | 415 | 18.44 MB | 0 | 0 | 454 — 7.56 MB | 6 |
| `4c9834bf` | 298 | 6.19 MB | 0 | 13 — 1.32 MB | 0 | 1 |
| `803fce52` | 25 | 28.06 MB | **9 — 20.93 MB** | 0 | 13 — 0.11 MB | 1 |
| `f18f796c` | 1040 | 35.97 MB | 0 | 3 — 0.28 MB | 288 — 6.00 MB | 357 |

Ba kết luận rút ra, đều quan trọng cho phạm vi thiết kế:

1. **Cả `null` lẫn `/FlateDecode` đều xuất hiện thật** (`803fce52` có `null`, `78674af9` có Flate)
   → v2 phải xử lý **cả hai**, không được thay `null` bằng `Flate`.
2. **`/FlateDecode` không phải hiện tượng cá biệt của 1 file**: 4/6 job có, nhưng chỉ 1 job có ở
   mức gây hại (28.72 MB) — nên lợi ích của v2 **phụ thuộc tài liệu nguồn**, không phải cải thiện
   đều cho mọi job. Không được hứa với user rằng mọi file sẽ nhỏ đi ~46%.
3. **v2 KHÔNG cứu được job lớn nhất trong kho** (`136645f9`, 520 MB): 437 MB ở đó **đã là JPEG
   sẵn**, đúng nhóm mà BR-IMGCOMP-02 cố ý không đụng để tránh nén chồng. Xem V9.2 — việc đó là
   một bài toán khác (downsample), **không** thiết kế trong v2.

### V4. Vì sao phải sửa business rule, không chỉ sửa code

#### V4.1. Câu chữ gốc vs. code

BR-IMGCOMP-02 (`docs/PRD.md:242`) viết: *"Chỉ re-encode ảnh đang ở dạng raw/uncompressed
(`Filter: null`); ảnh đã là JPEG (`DCTDecode`) giữ nguyên, không nén chồng lần 2."*

Business rule **chỉ nói về 2 trạng thái**: raw và JPEG. Code (và S6 bước 3 của v1) diễn giải thành
**"mọi filter ≠ null đều bỏ qua"** — một tập rộng hơn hẳn, bao gồm `/FlateDecode`, thứ **không
phải JPEG và không được bảo vệ bởi lý do "không nén chồng"** (Flate là lossless, re-encode sang
JPEG lần đầu không phải nén chồng).

#### V4.2. Vì sao lỗ hổng này không bị phát hiện ở v1

Spike v1 (S2) đo trên `3594a7a3` — file đó có **đúng 3 loại**: `null` (357), `DCTDecode` (156),
`CCITTFaxDecode` (25) — tổng 538, khớp 100% số xref. **Không có một xref `/FlateDecode` nào.**
Nên nhánh `Flate → skip` chưa từng được kiểm chứng trên dữ liệu thật; nó đúng theo câu chữ code
nhưng chưa bao giờ được đối chiếu với thực tế. Đây là biến thể của cùng một bài học: *test/spike
chỉ chứng minh code khớp với dữ liệu đã có, không chứng minh giả định đúng cho dữ liệu chưa gặp*.

#### V4.3. Bằng chứng "Flate ≠ đã nén hiệu quả"

Re-encode thật 19 ảnh Flate ≥ 4 KB sang JPEG q85:

| xref | Flate bytes | JPEG q85 | Còn lại | Kích thước |
|---|---|---|---|---|
| 1144 | 10,074,126 | 2,212,526 | 22% | 1681×1800 CMYK |
| 983 | 10,067,072 | 2,206,540 | 22% | 1681×1800 CMYK |
| 882 | 2,456,262 | 1,184,711 | 48% | 1039×1245 CMYK |
| 986 | 1,075,212 | 158,001 | **15%** | 233×1711 CMYK |
| 155 | 606,195 | 266,739 | 44% | 455×545 CMYK |
| 1062 | 122,668 | 47,682 | 39% | 702×403 **Gray** |
| … (19 ảnh) | **28.72 MB** | **7.04 MB** | **24.5%** | — |

Không ảnh nào bị guard nở file (`len(jpeg) >= raw`) chặn — tức **không ảnh nào trong nhóm này là
đồ hoạ phẳng mà JPEG sẽ làm to ra**.

#### V4.4. Lỗi tiềm ẩn `/Decode` — có sẵn trong code đang ship

Theo C4 (V2.2): `Pixmap(doc, xref)` áp dụng `/Decode`, còn `update_stream` không xoá nó. Với ảnh
`Filter: null` **có `/Decode` không phải identity** (ví dụ `[1 0]`), code **hiện tại** sẽ ghi JPEG
đã-áp-Decode rồi để nguyên key `/Decode [1 0]` → viewer áp lần hai → **ảnh âm bản**. Chưa phát tác
vì cả 2 file production đã đo đều chỉ có `/Decode` identity. v2 sửa luôn (V5 bước 9) — sửa này
**độc lập với việc user có duyệt mở rộng phạm vi Flate hay không**, và nên làm kể cả khi user chọn
giữ nguyên scope cũ.

### V5. Thuật toán v2 (spec cho Dev — KHÔNG phải code để copy)

Thay đổi so với S6 nằm ở **bước 3** (điều kiện lọc), **bước 4b/4c/4d** (3 guard mới) và **bước 9**
(xoá `/Decode`). Các bước còn lại giữ nguyên y hệt v1.

Thứ tự guard được sắp **rẻ → đắt** có chủ đích: mọi phép loại trừ đọc key đều chạy **trước** khi
dựng `Pixmap` (thao tác tốn RAM/CPU nhất — với ảnh 1681×1800 CMYK là ~12 MB bộ nhớ mỗi ảnh).

1. Mở `pdf_path`, ghi `size_before`. (như v1)
2. Gom xref duy nhất qua `get_page_images(pno, full=True)`; `info[0]`=xref, `info[1]`=smask. (như v1)
3. **[ĐỔI] Điều kiện được phép re-encode**: `Filter` là `null` **HOẶC** chứa `FlateDecode`.
   - Đọc `doc.xref_get_key(xref, "Filter")` → `(type, value)`.
   - `type == "null"` → eligible (ảnh raw, đúng như v1).
   - `type == "name"` và `value == "/FlateDecode"` → eligible.
   - `type == "array"` (ví dụ `[ /ASCII85Decode /FlateDecode ]`) → eligible **nếu** `"FlateDecode"`
     xuất hiện trong chuỗi value **và** không xuất hiện filter nén ảnh nào khác
     (`DCTDecode`, `JPXDecode`, `JBIG2Decode`, `CCITTFaxDecode`). Ghi chú: dạng array **chưa có mẫu
     thật** trong 6 job đã khảo sát (Reviewer US-16 v1 cũng đã nêu điểm này) → nhánh này là
     ⚠️ **`[UNVERIFIED]` — không chặn Dev** vì hành vi mặc định khi không match là *bỏ qua* (an toàn).
   - Mọi thứ khác (`/DCTDecode`, `/CCITTFaxDecode`, `/JPXDecode`, `/JBIG2Decode`, `/RunLengthDecode`…)
     → `images_skipped_already_compressed += 1`, bỏ qua. **BR-IMGCOMP-02 phần "không nén chồng JPEG"
     giữ nguyên 100%.**
4. **Guard** (thứ tự bắt buộc):
   - **4a (như v1)** `/ImageMask == true` → skip `unsupported`; `info[1] != 0` (có `/SMask`) →
     skip `unsupported`. *Lưu ý: bản thân object smask không nằm trong `get_page_images()` nên
     không bao giờ bị hàm này chạm tới — đã kiểm chứng ở v1, nhắc lại để Reviewer khỏi nghi.*
   - **4b [MỚI] Ngưỡng kích thước**: `len(doc.xref_stream_raw(xref)) < min_recompress_bytes`
     (mặc định **4096**) → skip, đếm vào **`images_skipped_small`** (field mới).
     *Lý do*: JPEG có sàn ~700 byte (đo thật: ảnh 1×1 → 698–763 byte), nên dưới vài KB không thể
     có lợi ích thật; guard này **không phải guard đúng-sai** (guard nở file ở bước 8 mới là guard
     đúng-sai) mà là guard **chi phí + nhiễu log**: nó loại 38/57 xref trước khi dựng Pixmap và
     nhờ đó tránh luôn 29 exception của C2. Đo: khoảng 100 B–4 KB rỗng hoàn toàn (V3.2) nên ngưỡng
     này không cắt nhầm ảnh thật nào.
   - **4c [MỚI] Bit depth**: `BitsPerComponent != 8` → skip `unsupported`.
     *Lý do*: ảnh 1-bit (bilevel — bản scan đen trắng, line art) là nhóm mà JPEG **vừa hỏng chất
     lượng vừa thường làm file to ra**; Flate/CCITT/JBIG2 mới là codec đúng cho chúng. Đây là guard
     bảo vệ chính cho đường `pdf_scan` (V8.2).
   - **4d [MỚI] Colorspace**: dựng `pix = Pixmap(doc, xref)` (và `Pixmap(pix, 0)` nếu `pix.alpha`),
     rồi chấp nhận **chỉ khi** `pix.n ∈ {1, 3, 4}` **và** `pix.colorspace.name` thuộc
     `{"DeviceGray", "DeviceRGB", "DeviceCMYK"}` **hoặc** bắt đầu bằng `"ICCBased("`.
     Ngược lại (`Separation(...)`, `Indexed(...)`, `DeviceN(...)`, `Lab`, `None`) → skip, đếm vào
     **`images_skipped_colorspace`** (field mới), log mức **`debug`** chứ không `warning` — đây là
     đường đi bình thường, không phải sự cố.
     ⚠️ **Không được viết guard là `name in {DeviceGray, DeviceRGB, DeviceCMYK}` cho gọn** — xem C1:
     làm vậy loại nhầm 19/19 ảnh cần nén và hàm lại im lặng không làm gì, đúng bằng bug đang sửa.
5. `jb = pix.tobytes("jpeg", jpg_quality=jpeg_quality)`. (như v1)
6. **Guard nở file (như v1)**: `len(jb) >= raw_size` → skip, `images_skipped_larger += 1`.
   Đây vẫn là **guard đúng-sai duy nhất cần thiết** cho câu hỏi "ảnh này có phải ảnh chụp không" —
   PM nói đúng ở điểm này: không cần heuristic "photographic hay không", vì icon/đồ hoạ phẳng mà
   JPEG làm to ra sẽ tự bị loại ở đây. Đo thật: 0/19 ảnh bị guard này chặn trên file sự cố.
7. Ghi đè stream + key (như v1): `update_stream(xref, jb, new=1, compress=0)`;
   `Filter → /DCTDecode`; `BitsPerComponent → 8`;
   `ColorSpace →` `/DeviceCMYK` | `/DeviceRGB` | `/DeviceGray` theo `pix.n`; `Width`/`Height`.
8. **[MỚI] Dọn `/Decode`**: nếu `doc.xref_get_key(xref, "Decode")[0] != "null"` →
   `doc.xref_set_key(xref, "Decode", "null")`. **Chỉ set khi key tồn tại** — set vô điều kiện sẽ
   thêm `/Decode null` vào mọi object và làm fixture hiện có lệch 12 byte không cần thiết (đã đo:
   606,629 → 606,641 byte trên `job3594a7a3_chunk0_sample_mono.pdf`).
   Không cần đụng `/DecodeParms` (C3 — `update_stream` đã xoá).
9. `doc.save(tmp, garbage=4, deflate=True)` → `close()` → `os.replace(tmp, pdf_path)`. (như v1)

**Chữ ký hàm** (mở rộng tối thiểu, giữ nguyên tinh thần S5 — tham số chỉ để test tham số hoá được,
**không** phải điểm cấu hình `.env`/UI, BR-IMGCOMP-03 giữ nguyên):

```python
async def compress_pdf_images(
    pdf_path: str | Path, *, jpeg_quality: int = 85, min_recompress_bytes: int = 4096
) -> ImageCompressStats
```

`ImageCompressStats` thêm 2 field: `images_skipped_small`, `images_skipped_colorspace`
(giữ nguyên toàn bộ field cũ — đây là dataclass chỉ dùng cho log/test, không ghi DB, không lên UI).

### V6. Data lineage (Protocol 6 R6-01) — **không đổi so với S5**

Nhắc lại tường minh để Reviewer trace tay được mà không phải mở lại v1:

| | |
|---|---|
| **Artifact vào** | `merged_path` = `self._output_dir / job.id / "translated_vi.pdf"` (`src/core/job_orchestrator.py:488`), chính biến vừa truyền cho `merge_chunk_pdfs(chunks, merged_path)` (`:490`) và có thể đã được `overlay_rotated_text(output_pdf_path=merged_path)` sửa tại chỗ (`:528-537`). **KHÔNG** phải `job.file_path`, **KHÔNG** phải `chunk.output_path`. |
| **Artifact ra** | Ghi đè in-place chính `merged_path` (tmp + `os.replace`). |
| **Ai gọi / thứ tự** | `run_job()` `:573-574`, trong cùng khối `try`, **sau** guard BR-OCR-03 (`:495-499`), **sau** overlay chữ xoay (RK-3), **trước** `job.output_path = str(merged_path)` (`:592`) và **trước** `create_bilingual_pdf(merged_path, file_path, bilingual_path)` (`:597`). |
| **Điều kiện gọi** | `if self._settings.pdf_translate_engine == "babeldoc":` — BR-IMGCOMP-01 **giữ nguyên**, nhánh `pdf2zh` không đổi một dòng hành vi nào. |

### V7. Kết quả verify chạy thật (đúng khuôn S7 — R6-03: kiểm tra nội dung, không tin status)

Chạy thuật toán V5 đầy đủ trên **bản copy** của file production 46.87 MB (file gốc không bị đụng):

| Chỉ số | Trước | Sau |
|---|---|---|
| Kích thước | 46.87 MB | **25.19 MB (−46.3%)** |
| Stream bytes của 19 ảnh Flate | 28.72 MB | **7.04 MB** |
| Số trang | 30 | **30** |
| Tổng ký tự text | 59,193 | **59,193 — giống hệt từng trang (30/30)** |
| Ảnh xử lý | — | 19 re-encode, 42 skip (đã nén), 38 skip (nhỏ), **0 lỗi**, 0 bị guard nở file |
| Thời gian chạy | — | **1.5 giây** |

**Kiểm chứng thị giác bằng pixel** (render trước/sau toàn bộ 30 trang, so từng pixel):

```
worst pages by mean abs pixel diff: (0.720, p17), (0.579, p29), (0.214, p22), (0.101, p26)
mean over all 30 pages: 0.0613 / 255      max single-pixel diff: 46 (p22)
```

**Không có hiện tượng đảo màu CMYK** (nếu có, mean diff sẽ ở mức ~130–250/255 — đây chính là mức
tôi đo được khi decode JPEG CMYK *đứng riêng ngoài PDF*, một cái bẫy đo lường: phải so **trang đã
render**, không so pixmap giải mã trực tiếp).

**Xem tận mắt** (R6-03): trang 22 chứa ảnh khắc nét (engraving) **xám, nhiều nét gạch mảnh** —
đúng nhóm nhạy cảm nhất với ringing của JPEG. Render 200 dpi trước/sau và nhìn trực tiếp:
**không phân biệt được bằng mắt**; sai khác tập trung ở rìa nét gạch, đỉnh 46/255.

**Hồi quy trên fixture đang có** (`job3594a7a3_chunk0_sample_mono.pdf`, 5 ảnh: 1 `null` + 3 DCT +
1 CCITT): thuật toán v2 cho **kết quả y hệt v1** — `recompressed=1, skip_filter=4`, 7.08 MB →
0.58 MB. Tức **v2 không làm đổi hành vi trên dữ liệu mà v1 đã xử lý đúng**; test hiện có phải vẫn
xanh không sửa gì (trừ khi test assert kích thước file theo byte tuyệt đối).

### V8. Các quyết định thiết kế đã cân nhắc (và phương án bị loại)

#### V8.1. Có cần heuristic "ảnh chụp hay đồ hoạ phẳng" không? → **KHÔNG**

Đã thử đo thống kê số màu duy nhất / tỉ lệ màu áp đảo cho từng ảnh để phân loại. Kết luận: **không
cần** — guard nở file (bước 6) đã xử lý đúng lớp rủi ro đó bằng *kết quả thật* thay vì bằng *dự
đoán*, và đo được 0/19 ảnh bị nó chặn. Thêm heuristic = thêm ngưỡng phải tune, thêm đường code
không test được bằng dữ liệu thật. PM đề xuất hướng này và tôi xác nhận: giữ nguyên guard cũ.

#### V8.2. Có nên loại trừ ảnh xám (grayscale) để bảo vệ bản scan văn bản? → **KHÔNG, nhưng có phương án lùi**

Đã đo cả 2 biến thể trên cùng file thật:

| Biến thể | Kết quả | Sai khác pixel |
|---|---|---|
| **(A)** re-encode cả Gray/RGB/CMYK (khuyến nghị) | 46.87 → **25.19 MB** | mean 0.0613/255 |
| **(B)** bỏ qua ảnh 1 kênh (grayscale) | 46.87 → 25.34 MB | mean 0.0486/255 |

Chênh lệch chỉ **0.15 MB (0.3%)** — nghĩa là cả hai đều chấp nhận được về dung lượng. Chọn (A) vì:

- Rủi ro thật của grayscale không nằm ở "ảnh xám" mà ở **ảnh 1-bit bilevel** (scan đen trắng) —
  nhóm đó đã bị guard 4c (`BitsPerComponent != 8`) chặn tuyệt đối, không phụ thuộc quyết định này.
- Với ảnh xám 8-bit thật (engraving nhiều nét mảnh — trường hợp xấu nhất có trong dữ liệu), đã
  **nhìn tận mắt ở 200 dpi**: không phân biệt được (V7).
- Đường `pdf_scan` **hưởng lợi nhiều hơn chứ không thiệt**: OCR bridge (`src/preprocess/searchable_pdf.py`)
  **không chèn ảnh mới** — nó vẽ whiteout + text vô hình lên chính trang scan gốc, nên ảnh trang
  giữ nguyên codec của file nguồn. Scan 8-bit lưu Flate là đúng nhóm phình to nhất mà v2 cứu được.
- Nếu sau này gặp job scan bị giảm chất lượng thật: lùi về (B) chỉ là **thêm 1 điều kiện `pix.n == 1`
  vào guard 4d** — không phải viết lại thiết kế. Ghi sẵn ở đây để khỏi phải điều tra lại.

#### V8.3. Vì sao không nâng `jpeg_quality` cho ảnh xám? → giữ **q85 cố định**

BR-IMGCOMP-03 chốt q85 cố định. Chất lượng đo được ở q85 đã đạt (V7), nên thêm một hằng số thứ hai
theo kênh màu là độ phức tạp **không có số liệu nào biện minh**. Không làm.

### V9. Phát hiện phụ (ngoài phạm vi v2 — cần PM/user quyết định riêng)

#### V9.1. `create_bilingual_pdf()` đang save KHÔNG nén — **đúng lỗi S8, ở một file khác**

`src/postprocess/bilingual_merge.py:22` gọi `output_doc.save(output_path)` **trần** —
`deflate=False, garbage=0` mặc định. Bước này chạy **sau** `compress_pdf_images()` nên nó **thổi
phồng lại** chính file vừa được nén.

Đo thật trên output song ngữ có sẵn (`4c9834bf`, 596 trang):

| Xử lý | Kích thước |
|---|---|
| Hiện tại (`save()` trần) | **86.97 MB** |
| Chỉ đổi thành `save(garbage=4, deflate=True)` | **7.40 MB (−91.5%)**, mất 1.0 giây |

Đáng chú ý: file này chỉ có 2.65 MB là ảnh — tức ~84 MB là **content stream/font không nén**, không
phải vấn đề ảnh. Bản dịch đơn ngữ của cùng job chỉ 6.19 MB, nghĩa là bước song ngữ **một mình** làm
file to gấp 14 lần. Job `f18f796c` còn cực đoan hơn: đơn ngữ 35.97 MB → song ngữ **433.86 MB**.

**Điểm cần PM/user quyết định** (Tech Lead **không tự quyết**, đúng tiền lệ S8 — đây là sửa hành vi
nằm ngoài US-16, chạm code path dùng chung cho **cả `pdf2zh` lẫn `babeldoc`**):

- **(A) Ngoài scope lần này**: giữ nguyên, ghi backlog. File song ngữ tiếp tục lớn bất thường.
- **(B) Sửa kèm v2** (khuyến nghị của tôi nếu user quan tâm dung lượng — mà theo bối cảnh thì đúng
  là đang quan tâm): đổi 1 dòng `bilingual_merge.py:22` → `save(output_path, garbage=4, deflate=True)`.
  Rủi ro thấp hơn hẳn trường hợp `chunk_merge.py` ở S8 (file này **không** dính Bug #7/#8, không có
  golden test bám sát), nhưng vẫn là thay đổi ảnh hưởng **cả 2 engine** nên vẫn cần user duyệt.

#### V9.2. Job 520 MB toàn ảnh JPEG — **v2 không cứu được**, backlog riêng

`136645f9`: 520.14 MB, trong đó **437.69 MB là 1110 ảnh `/DCTDecode`** (đã là JPEG, trung bình
394 KB/ảnh). BR-IMGCOMP-02 cố ý không đụng nhóm này. Muốn giảm phải **downsample theo kích thước
hiển thị thật trên trang** (ảnh 300+ dpi đặt vào khung nhỏ) hoặc re-encode JPEG→JPEG chấp nhận nén
chồng — cả hai đều là bài toán mới, cần spike đo riêng. **Chưa thiết kế, chỉ ghi nhận.** Cần nói rõ
với user: sau v2, những job dạng này **vẫn sẽ lớn**.

### V10. Yêu cầu test + fixture (Protocol 5 R5-03 / Protocol 6 R6-02, R6-03)

#### V10.1. Fixture vàng mới — **CÓ, cần thiết**

Fixture hiện có (`job3594a7a3_chunk0_sample_mono.pdf`) **không có ảnh `/FlateDecode` nào** (1 null
+ 3 DCT + 1 CCITT) → không thể test đường mới. Nếu Dev/QA viết fixture tay theo mô tả này, đó đúng
là loại "mock tự nhất quán với giả định" mà Protocol 5 cấm.

**Cách tạo (đã tự chạy thử để chắc chắn khả thi — Dev chỉ việc lặp lại):**

```
Nguồn: data/outputs/78674af9-ce15-4d39-bba5-7f8d1e2804fe/translated_vi.pdf
Trích trang 22 và 25 (0-based) bằng insert_pdf, save(garbage=4, deflate=True)
Đích:  tests/fixtures/babeldoc/job78674af9_flate_sample.pdf
```

Đã kiểm chứng kết quả của cách trích này:

| Chỉ số | Giá trị đo |
|---|---|
| Kích thước fixture | **1.66 MB** |
| Thành phần | 1 ảnh `FlateDecode` **Gray** ICC (122 KB, engraving), 1 ảnh `FlateDecode` **CMYK** ICC (835 KB, ảnh chụp), 1 ảnh `DCTDecode` Gray (phải giữ nguyên byte) |
| Chạy thuật toán v2 | 1.66 MB → **0.85 MB**, `recompressed=2, skip_filter=1`, 0 lỗi |
| Chạy thuật toán v1 (hiện tại) | **0 ảnh re-encode** — tức fixture này *thất bại* với code cũ và *pass* với code mới, đúng yêu cầu của một regression fixture |
| Ảnh trong fixture có byte y hệt file gốc? | **có** — `save(deflate=True)` không đụng stream ảnh đã có filter (đã hash SHA-256 đối chiếu 60/60 xref) |

Bắt buộc ghi xuất xứ vào `tests/fixtures/babeldoc/README.md` (job id, số trang gốc, ngày trích,
lệnh trích) theo đúng nếp các fixture hiện có.

**Tuỳ chọn (PM quyết theo khẩu vị dung lượng repo)**: thêm **trang 13** vào fixture sẽ phủ thêm 29
ảnh `Separation(DeviceCMYK,Black)` 1×1 + 17 DCT Separation — tức dữ liệu thật cho **guard 4d** và
**guard 4b**. Giá phải trả: fixture tăng **1.66 MB → 8.70 MB** (font subsetting chỉ giảm được
0.24 MB, đã thử). **Khuyến nghị: KHÔNG thêm** — thay vào đó test guard 4d/4b bằng cách gọi hàm với
`min_recompress_bytes=0` trên fixture nhỏ (xem V10.2 mục 5), và ghi nhận rằng nhánh
`images_skipped_colorspace` với ảnh **lớn** không có mẫu thật (`[UNVERIFIED]`, hành vi mong đợi là
"không làm gì" nên an toàn theo mặc định).

#### V10.2. Danh sách test bắt buộc

1. **Đường mới, nội dung không chỉ status (R6-03)**: chạy `compress_pdf_images` thật trên fixture
   mới → `page_count` không đổi (2), **text từng trang giống hệt trước/sau**, file nhỏ đi, và
   `stats.images_recompressed == 2`. Assert **giá trị cụ thể**, không chỉ "chạy không lỗi".
2. **Guard không nén chồng (giữ từ v1)**: ảnh `DCTDecode` trong fixture mới phải có stream
   **byte-identical** trước/sau (SHA-256).
3. **Hồi quy v1**: giữ nguyên toàn bộ test hiện có trên
   `job3594a7a3_chunk0_sample_mono.pdf` — phải xanh **không sửa assertion** (đã đo: kết quả v2
   trùng v1 trên fixture đó, xem V7).
4. **`/Decode` (V4.4)**: lấy fixture mới, inject `/Decode [1 0]` vào 1 xref Flate rồi chạy hàm →
   sau khi chạy `xref_get_key(xref, "Decode")` phải trả `('null','null')`. Đây là test cho một lỗi
   **chưa từng phát tác**, nên bắt buộc phải có test mới giữ được nó đã sửa.
5. **Guard ngưỡng nhỏ + colorspace**: gọi `compress_pdf_images(..., min_recompress_bytes=0)` trên
   fixture mới → không được raise, và số ảnh re-encode không tăng thêm ngoài dự kiến. (Nếu PM chọn
   thêm trang 13 vào fixture thì test này assert luôn `images_skipped_colorspace == 29`.)
6. **Data lineage (R6-02, giữ từ S9)**: `compress_pdf_images.assert_called_with(merged_path, ...)`
   đúng path mà `merge_chunk_pdfs` vừa ghi; và nhánh `pdf2zh` khẳng định **không** được gọi.
7. **Thứ tự (giữ từ S9)**: job có output rỗng chữ phải `failed` bằng thông báo của guard BR-OCR-03,
   không phải lỗi nén.
8. **R5-03 / R6-03 gate**: QA phải chạy **1 job thật xuyên suốt** (babeldoc, file có ảnh Flate) và
   **mở file output kiểm tra nội dung** — không chấp nhận chỉ đọc `status=completed`. Có thể tái sử
   dụng chính file 46.87 MB làm đối chứng "trước".

### V11. Trạng thái verify

| Hạng mục | Trạng thái |
|---|---|
| Hiện trạng "re-encode 0 ảnh" trên job sự cố | ✅ Verified — chạy lại logic đang ship, `recompressed=0` |
| Phân bố filter 6 job output thật | ✅ Verified — đo trực tiếp từng file |
| Flate ảnh chụp nén được 12–48% | ✅ Verified — re-encode thật 19/19 ảnh |
| Kết quả cuối 46.87 → 25.19 MB | ✅ Verified end-to-end trên bản copy file thật |
| Bảo toàn text / số trang | ✅ Verified — 59,193 ký tự giống hệt, 30/30 trang |
| Bảo toàn màu (không đảo CMYK) | ✅ Verified — pixel-diff 0.0613/255 + xem ảnh render thật |
| C1 `colorspace.name` của ICCBased | ✅ Verified — và đã thực sự mắc bẫy này 1 lần khi spike |
| C2 `tobytes("jpeg")` raise với Separation | ✅ Verified — 29 xref thật |
| C3 `update_stream` xoá `/Filter` + `/DecodeParms` | ✅ Verified — in object dict trước/sau |
| C4 `Pixmap` áp dụng `/Decode`, `update_stream` không xoá | ✅ Verified — samples `ffff…` vs `0000…` |
| Hồi quy trên fixture v1 | ✅ Verified — kết quả trùng v1 |
| Fixture mới khả thi ở 1.66 MB | ✅ Verified — đã trích thử và chạy cả v1 lẫn v2 lên nó |
| `Filter` dạng **array** (`[/ASCII85Decode /FlateDecode]`) | ⚠️ **`[UNVERIFIED]`** — 0 mẫu thật trong 6 job. Không chặn Dev (không match ⇒ bỏ qua ⇒ an toàn) |
| Guard 4d với ảnh **lớn** colorspace lạ (Indexed/DeviceN/Lab) | ⚠️ **`[UNVERIFIED]`** — chỉ có mẫu 1×1. Hành vi mong đợi: bỏ qua |
| Ảnh có `/SMask` hoặc `/ImageMask` | ⚠️ **`[UNVERIFIED]`** (kế thừa S10) — vẫn 0 mẫu thật sau khi khảo sát thêm 5 job |
| **Sửa BR-IMGCOMP-02 (mở rộng phạm vi)** | ⏸ **Chờ user duyệt — Protocol 2** |
| **V9.1 `bilingual_merge.py` save không nén** | ⏸ **Chờ PM/user quyết định (A)/(B)** — không chặn phần còn lại của v2 |
| V9.2 job 520 MB toàn DCT | ⏸ Backlog, chưa thiết kế |

## US-16 v2 — Phản biện của Domain Expert (2026-09-08)

**Người viết**: Domain Expert (Fable) — chuyên PDF internals / image compression / color management.
**Vai trò**: CHỈ phản biện độc lập thiết kế "US-16 v2" của Tech Lead ở trên. **Không sửa code trong
`src/`, không quyết định thay PM/user** ở các điểm Protocol 2.
**Kỷ luật**: mọi số liệu của Tech Lead đều được **tự chạy lại từ đầu** trên bản copy của dữ liệu
thật (không đụng file production), bằng script tạm viết riêng (không kế thừa script của Tech Lead).
Không có claim nào dưới đây là "tôi nghĩ" — mỗi kết luận đi kèm số đo tự chạy hoặc nguồn tự đọc.

**Môi trường**: `.venv/bin/python` (Python 3.14), PyMuPDF **1.28.2** (cùng bản Tech Lead dùng).
Renderer độc lập: **macOS Quartz** qua `/usr/bin/sips` (150 dpi) — đây là engine của Preview.app,
hoàn toàn không dùng MuPDF. Chrome/pdfium: **không thử được** (Browser pane từ chối mở PDF local),
đánh dấu `[UNVERIFIED]` ở X8. `numpy` không có trong venv → pixel-diff tính bằng pure Python trên
`Pixmap.samples` (chậm hơn nhưng cùng kết quả). Dữ liệu: đúng 6 job output Tech Lead đã khảo sát
(V3.3) + file sự cố `78674af9` + fixture `job3594a7a3_chunk0_sample_mono.pdf`.

### X0. Kết luận ngắn

**Số liệu của Tech Lead đúng toàn bộ** (X1 — 100% tái hiện được, kể cả thứ tự 4 trang lệch pixel
nhiều nhất). **Nhưng thiết kế V5 chưa đủ chín để trình user** vì 3 lỗi mà cách đo của Tech Lead
**không thể nhìn thấy** — hai trong số đó là lỗi có sẵn trong code v1 đang ship, cùng loại với
lỗi `/Decode` (C4) mà chính Tech Lead đã tìm ra:

1. **Guard 4d không bắt được `Indexed`** (X2): `Pixmap(doc, xref)` **tự expand** Indexed sang base
   colorspace, nên `pix.colorspace.name` trả `'DeviceCMYK'`, không bao giờ trả `'Indexed(...)'`.
   Chạy thật: 2 ảnh Indexed lọt qua guard và bị JPEG hoá. BR-IMGCOMP-02c hứa "Indexed giữ nguyên"
   nhưng V5 không thực hiện được lời hứa đó.
2. **Ghi đè `/ColorSpace` làm mất ICC profile → lệch màu thật trên macOS Preview** (X3): đo bằng
   Quartz, trang 17 lệch **6.98/255**, trang 29 lệch **5.55/255**; giữ nguyên `/ColorSpace` → còn
   **0.97 / 0.76**. MuPDF cho **0.00** với cùng thay đổi — tức phép đo "0.0613/255" ở V7 mù hoàn
   toàn với lỗi này. Lỗi có sẵn trong v1 (`image_compress.py:120-122`).
3. **`/Mask` color-key không có guard** (X4): `Pixmap` trả `alpha=1`, code drop alpha, `update_stream`
   **giữ nguyên** key `/Mask` → mask áp lên sample JPEG đã đổi. Guard 4a (`info[1]`) không thấy
   `/Mask`. Lỗi có sẵn trong v1; 0 mẫu thật trong kho — `[UNVERIFIED]` trên production, nhưng cơ chế
   đã chứng minh bằng inject.

Ngoài ra 2 chỗ **kết luận đúng nhưng lý do sai**, cần sửa câu chữ trước khi Dev đọc: ngưỡng 4 KB
(X5) và cơ chế phình file song ngữ V9.1 (X6 — là **font bị nhân bản 65 lần**, không phải "không
nén"; `deflate=True` đơn thuần cho **0 byte** lợi ích, `garbage=4` mới là tham số quyết định).

**Khuyến nghị cuối (X9)**: Tech Lead sửa V5 ở 3 điểm blocking (4d, bước 7, thêm guard `/Mask`) + sửa
câu chữ 4b và V9.1, rồi mới trình user. Không cần đo lại từ đầu — mọi số đo còn lại đứng vững.

### X1. Đối chiếu số liệu Tech Lead — tất cả tái hiện được

| Claim Tech Lead | Tự chạy lại | Trạng thái |
|---|---|---|
| V2.1 logic đang ship → `recompressed=0` trên file sự cố | Đọc code `image_compress.py:81-84` + khảo sát: file có **0** xref `Filter: null` → đúng 0 | ✅ |
| V3.1 57 Flate / 42 DCT / 0 null; 28.72 MB / 11.12 MB | 57 / 42 / 0; 30.12 MB (= 28.72 **MiB**) / 11.66 MB (= 11.12 MiB). *Tech Lead ghi "MB" nhưng là MiB — nhất quán trong toàn section, không ảnh hưởng kết luận* | ✅ |
| V3.2 phân bố kích thước 57 ảnh Flate; 100 B–4 KB rỗng **trên file này** | 4 ≥1M + 13 100K–1M + 1 50–100K + 1 4–50K + 38 <100 B; đúng, khoảng 100 B–4 KB rỗng *trên file này* (nhưng xem X5) | ✅ (file này) |
| V3.3 bảng 6 job | Đo lại từng file: khớp **toàn bộ** số xref và bytes (sau quy đổi MiB) | ✅ |
| V4.3 JPEG q85 của 19 ảnh: 28.72 → 7.04 MiB, từng dòng 1144/983/882/986/155/1062 | Khớp **từng byte** (vd 1144: 10,074,126 → 2,212,526) | ✅ |
| C1 `colorspace.name` = `'ICCBased(CMYK,Artifex CMYK SWOP Profile)'` | Tái hiện đúng chuỗi; xref 889 = `'Separation(DeviceCMYK,Black)'` | ✅ |
| C2 `tobytes("jpeg")` raise `FzErrorArgument code=4` với Separation | Tái hiện | ✅ |
| C3 `update_stream` xoá `/Filter` + `/DecodeParms` | Inject `/DecodeParms` → sau update_stream: `('null','null')`, object dict không còn key | ✅ |
| C4 `Pixmap` áp `/Decode`; `update_stream` giữ `/Decode` | Inject `[1 0 1 0 1 0 1 0]` → 64 sample đầu đảo đúng (`a+b==255`); sau update_stream key vẫn còn | ✅ |
| `xref_set_key(x, "Decode", "null")` = xoá theo ngữ nghĩa PDF | `xref_get_key` → `('null','null')`; sau `save(garbage=4)` + reload object vẫn ghi `/Decode null` nhưng vẫn `('null','null')`; Quartz render đúng (X7.1) | ✅ |
| V7 46.87 → 25.19 MiB, 1.5 s, 19/42/38/0, 59,193 ký tự, 30/30 trang | 46.87 → 25.19 MiB, **1.4 s**, 19 re-encode / 42 skip filter / 38 skip nhỏ / 0 lỗi / 0 nở file; 59,193 = 59,193, 30/30 trang text giống hệt | ✅ |
| V7 pixel-diff MuPDF, 4 trang xấu nhất p17 > p29 > p22 > p26 | 100 dpi: mean 0.0409 (Tech Lead 0.0613 — khác dpi), thứ tự **đúng y hệt** p17 (0.53) > p29 (0.45) > p22 (0.07) > p26 (0.04) | ✅ |
| V7 DCT giữ nguyên byte | SHA-256 theo **nội dung** (xref bị `garbage=4` đánh số lại — không so theo xref được): 42 hash gốc ⊆ 61 hash sau | ✅ |
| V8.2 biến thể (B) bỏ ảnh xám → 25.34 MiB | 25.34 MiB, 16 re-encode, 3 skip | ✅ |
| V9.1 song ngữ 86.97 → 7.40 MiB, 1.0 s | 86.97 → 7.40 MiB, 1.0 s; f18f796c 413.76 → **42.31 MiB**; text 596/596 giống; pixel-diff 6 trang ngẫu nhiên = **0.0** | ✅ số — ❌ **cơ chế** (X6) |
| V10.1 fixture trang 22+25 = 1.66 MiB, 3 ảnh, v2 → 0.85 MiB `recompressed=2, skip_filter=1` | 1.66 MiB; Flate ICC CMYK 656×659 (835 KB) + Flate ICC Gray 702×403 (122 KB) + DCT Gray 316×82; v2 → 0.85 MiB, 2/1/0 lỗi | ✅ |
| V10.1 thêm trang 13 → ~8.7 MB | 9.91 MiB (không subset font) — cùng kết luận: quá to | ✅ |
| Filter dạng array `[UNVERIFIED]` | Inject thử: `xref_get_key` trả `('array', '[/FlateDecode]')` và `('array', '[/ASCIIHexDecode/FlateDecode]')` — **không có khoảng trắng giữa các name**. Substring check như V5 bước 3 hoạt động; `value.split()` sẽ sai. `Pixmap(doc, xref)` decode được `[/FlateDecode]` | ✅ hành vi API (vẫn 0 mẫu thật) |

### X2. KHÔNG ĐỒNG Ý #1 — Guard 4d (colorspace) không bắt được `Indexed`

**Claim V5 bước 4d**: skip khi `pix.colorspace.name` là `Separation(...)`, `Indexed(...)`,
`DeviceN(...)`, `Lab`, `None`.

**Phản chứng (chạy thật)**: job `136645f9` (Tech Lead có khảo sát ở V3.3 nhưng chỉ đếm filter, không
đếm colorspace) có **277 ảnh `/FlateDecode` colorspace `[/Indexed /DeviceCMYK hival …]`** — mẫu
thật cho đúng cái Tech Lead ghi `[UNVERIFIED] chỉ có mẫu 1×1`. Với 3 xref Indexed điển hình
(3691 209×188, 3071 80×112, 3132 46×56):

```
Pixmap(doc, 3691): n=4 alpha=0 colorspace.name='DeviceCMYK'   ← KHÔNG phải 'Indexed(...)'
tobytes("jpeg") → OK, 4267 byte
```

MuPDF **expand Indexed sang base colorspace ngay khi dựng Pixmap** (`fz_get_pixmap_from_image` →
`fz_convert_indexed_pixmap_to_base`), khác với Separation (giữ nguyên, n=1). Hệ quả: nhánh
`Indexed(...)` trong guard 4d là **dead code** — không bao giờ match.

Chạy thuật toán V5 với `min_recompress_bytes=0` trên `136645f9` để bóc riêng guard 4d:

```
scanned=1503 recompressed=2 skip_filter=1110 skip_larger=347 skip_cs=44 errors=0
→ 2 ảnh được re-encode: CẢ HAI đều là Indexed (1079 B và 1291 B), lọt guard với tên 'DeviceCMYK'
→ skip_cs=44: toàn bộ là Separation — guard chỉ bắt được đúng cái Tech Lead đã thấy trong file sự cố
```

Trên dữ liệu hiện có hậu quả = 0 (cả 277 ảnh đều < 4 KB nên guard 4b chặn trước). Nhưng **BR-IMGCOMP-02c
hứa với user "ảnh `Indexed` giữ nguyên"** và V5 không giữ được lời hứa đó với ảnh Indexed ≥ 4 KB —
đúng nhóm biểu đồ/bảng dạng palette ≤ 256 màu mà JPEG làm hỏng (viền màu bết, chữ nhỏ nhoè), và
guard nở file **không** bảo vệ được vì JPEG của ảnh palette thường vẫn nhỏ hơn Flate.

**Cách sửa (đã verify công cụ)**: `get_page_images(pno, full=True)` trả **`info[4]` = bpc (int, đã
resolve indirect ref)** và **`info[5]` = tên họ colorspace lấy từ PDF dict**, đo trên 2 file thật:

| `info[5]` quan sát được | Ở file | Ghi chú |
|---|---|---|
| `'DeviceGray'`, `'DeviceRGB'`, `'DeviceCMYK'` | cả 2 | |
| `'ICCBased'` | cả 2 | không kèm N — vẫn cần `pix.n ∈ {1,3,4}` sau khi dựng Pixmap |
| `'Indexed'` | `136645f9` (277 Flate) | **đây là cái cần bắt** |
| `'Separation'` (alt `'DeviceCMYK'` ở `info[6]`) | cả 2 | |
| `'DeviceN'` (alt `'DeviceCMYK'`) | cả 2 (chỉ trên DCT) | |

⇒ Guard 4d nên là **allowlist trên `info[5]` ∈ {DeviceGray, DeviceRGB, DeviceCMYK, ICCBased}, chạy
TRƯỚC khi dựng Pixmap** (rẻ hơn, đúng tinh thần "rẻ → đắt" của V5), rồi giữ kiểm tra
`pix.n ∈ {1,3,4}` + `pix.colorspace.name` như lớp thứ hai. Cách này cũng loại luôn 29+44 ảnh
Separation **trước** Pixmap thay vì sau. `CalRGB`/`CalGray`/`Lab`/`Pattern`: `[UNVERIFIED]` (0 mẫu),
allowlist mặc định bỏ qua = an toàn. Tương tự nên đọc bpc từ `info[4]` thay vì
`xref_get_key(xref, "BitsPerComponent")[1] != "8"` — cái sau trả `('xref', 'N 0 R')` nếu key là
indirect ref và sẽ skip nhầm trong im lặng (hiếm, nhưng miễn phí để tránh).

### X3. PHÁT HIỆN MỚI #1 — Ghi đè `/ColorSpace` làm mất ICC profile → lệch màu trên macOS Preview

**Vấn đề**: V5 bước 7 (kế thừa v1 `image_compress.py:120-122`) ghi
`ColorSpace → /DeviceCMYK | /DeviceRGB | /DeviceGray theo pix.n`. Với ảnh gốc `[/ICCBased …]`
(19/19 ảnh cần nén của file sự cố, 3/3 của `f18f796c`), thao tác này **vứt ICC profile**. Với MuPDF
điều đó vô hại vì DeviceCMYK mặc định của MuPDF *chính là* profile "Artifex CMYK SWOP" đang nhúng
trong file (đã đọc tag `desc` của ICC stream 157: `Artifex CMYK SWOP Profile`, 1064: `Artifex
Software sGray ICC Profile`). Nhưng viewer khác map `DeviceCMYK` sang profile mặc định của **họ**
(Quartz: "Generic CMYK Profile") → màu đổi.

**Đo bằng Quartz (`sips`, 150 dpi, cùng trang render 2 lần, so từng pixel)**:

| So sánh (Quartz) | Trang 17 (2 ảnh CMYK lớn) | Trang 29 (ảnh táo/gỗ) | Cùng phép so bằng MuPDF |
|---|---|---|---|
| Gốc vs v2 như V5 (ghi `/DeviceCMYK`) | **6.98/255**, max 102 | **5.55/255**, max 56 | 0.53 / 0.45 |
| Gốc vs v2 **giữ nguyên `/ColorSpace`** (ICCBased) | **0.97/255**, max 88 | **0.76/255**, max 45 | 0.53 / 0.45 (**y hệt**) |
| **Control**: chỉ đổi ICC→`/DeviceCMYK`, giữ Flate, **không JPEG** | — | **4.38/255**, max 25 | **0.00 / 0** |

Hàng control là bằng chứng quyết định: **JPEG không phải nguyên nhân**, riêng việc đổi
`/ColorSpace` đã gây 4.38/255 trên Quartz và **0.00 trên MuPDF**. Tức mọi số "pixel-diff" ở V7 và
V8.2, dù đúng, **không có năng lực phát hiện** loại lỗi này — cùng bản chất với bài học C4: đo bằng
chính thư viện tạo ra kết quả thì chỉ chứng minh nhất quán với chính nó.

Về mức độ: 5–7/255 là lệch tông/độ bão hoà **thấy được khi đặt cạnh nhau nhưng không "sai màu" rõ
rệt** (đã crop vùng táo xanh/gỗ nâu render Quartz 3 biến thể và nhìn: khác biệt tinh tế). Không phải
lỗi đảo màu. Nhưng sửa **hoàn toàn miễn phí**: với allowlist ở X2, `Pixmap(doc, xref)` luôn ở đúng
colorspace gốc với cùng số kênh, nên **không cần ghi `/ColorSpace` nữa** — chỉ bỏ dòng đó. Biến thể
giữ ICC: 25.19 MiB (**bằng hệt**), 19 re-encode, 0 lỗi. `[/ICCBased N]` + `/DCTDecode` là tổ hợp
chuẩn (Adobe vẫn xuất như vậy).

Lưu ý thêm: (i) `f18f796c` nhúng **`sRGB IEC61966-2.1` thật** (không phải profile Artifex mặc định)
— nên vấn đề không chỉ giới hạn ở "profile mặc định của MuPDF"; (ii) đây là lỗi **có sẵn trong v1**
với mọi ảnh `Filter: null` gốc ICCBased, độc lập với việc duyệt mở rộng Flate — cùng trạng thái với
`/Decode` ở V4.4; (iii) v1 trước đây cũng chỉ kiểm CMYK bằng MuPDF (Architecture.md dòng 241, 272 —
"render ra PNG và xem tận mắt" bằng PyMuPDF), tức **đây là lần đầu output CMYK JPEG của
`compress_pdf_images` được render bằng viewer không phải MuPDF**. Kết quả tốt: Quartz **không đảo
màu** (nếu đảo, mean đã ở mức 100+), APP14 `transform=0` được hiểu đúng.

### X4. PHÁT HIỆN MỚI #2 — Ảnh có `/Mask` (color-key) không có guard, v1 lẫn v2

Guard 4a chỉ nhìn `/SMask` (qua `info[1]`) và `/ImageMask`. Key **`/Mask`** có 2 dạng: array
color-key (`/Mask [min max …]` — sample trong dải này trong suốt) và ref tới stencil mask. Inject
`/Mask [200 255]` vào xref 1062 (Gray 702×403) trên bản copy:

```
Pixmap(doc, 1062): n=2 alpha=1                 ← MuPDF áp color-key thành alpha
get_page_images(...)[1] (smask) = 0            ← guard 4a KHÔNG thấy
sau Pixmap(pix, 0) + update_stream(...):  dict còn nguyên  /Mask[200 255]  (và /Interpolate true)
```

Hệ quả nếu xảy ra thật: alpha bị vứt, JPEG ghi đè, nhưng `/Mask [200 255]` vẫn áp lên **sample JPEG
đã đổi giá trị** → vùng trong suốt bị lốm đốm/mất, hoặc vùng không trong suốt bị trong suốt. Khảo
sát 6 job: **0 xref có `/Mask`** → `[UNVERIFIED]` trên production, cùng hạng với `/SMask` ở S10.
Sửa rẻ: thêm vào 4a `if doc.xref_get_key(xref, "Mask")[0] != "null" → skip unsupported` (bắt cả
array lẫn ref), và đổi `if pix.alpha: pix = Pixmap(pix, 0)` thành **skip** — trong luồng này alpha
chỉ có thể đến từ SMask/color-key, drop alpha luôn là mất thông tin.

### X5. KHÔNG ĐỒNG Ý #2 — Lý do của ngưỡng 4 KB sai, con số vẫn đúng

V5 4b: *"Đo: khoảng 100 B–4 KB rỗng hoàn toàn (V3.2) nên ngưỡng này không cắt nhầm ảnh thật nào."*
Đó là tính chất của **1 file**. Khảo sát lại 6 job theo bucket:

| Job | Flate < 100 B | **100 B–4 KB** | 4–50 KB | 50–100 KB | 100 KB–1 MB | ≥ 1 MB |
|---|---|---|---|---|---|---|
| `78674af9` | 38 | **0** | 1 | 1 | 13 | 4 |
| `136645f9` | 207 | **186** | 0 | 0 | 0 | 0 |
| `4c9834bf` | 0 | 0 | 1 (4,678 B RGB 274×24) | 5 | 7 | 0 |
| `f18f796c` | 0 | 0 | 1 | 1 | 1 | 0 |

Khoảng 100 B–4 KB **không rỗng** trong kho (186 icon Indexed 46×56 … 209×188). Lý do đúng để giữ
4096 là số đo khác: tổng bytes Flate < 4 KB toàn kho = **0.08 MiB** (431 ảnh); chạy `136645f9` với
ngưỡng 0 → 347 ảnh bị guard nở file chặn, 44 skip colorspace, **chỉ 2 ảnh qua được, tiết kiệm 194
byte** — đổi lấy 393 lần dựng Pixmap. Ngưỡng 4096 đúng chỗ, nhưng câu lý giải trong V5 cần thay bằng
số này để Dev/Reviewer sau không tin nhầm rằng "không có ảnh nào ở đó".

### X6. KHÔNG ĐỒNG Ý #3 — V9.1 chẩn đoán sai cơ chế; cách sửa vẫn đúng nhưng phải ghi đúng lý do

V9.1 viết: *"~84 MB là content stream/font không nén"* và đề xuất `save(garbage=4, deflate=True)`.
Kiểm kê stream của `bilingual_vi_en.pdf` (`4c9834bf`, 596 trang, 86.97 MiB):

| Loại stream | Filter | Số stream | Bytes |
|---|---|---|---|
| font (`/Length1`) | **`/FlateDecode`** (đã nén) | **592** | **71.08 MiB** |
| content/khác | `/FlateDecode` | 2,598 | 7.96 MiB |
| image | `/FlateDecode` | 26 | 2.65 MiB |

Toàn bộ đã Flate. Đếm hash nội dung 592 font stream → **chỉ 9 nội dung duy nhất** (0.31 MiB); bản
đơn ngữ `translated_vi.pdf` của cùng job có đúng **9** font stream. Tức `create_bilingual_pdf()` gọi
`insert_pdf` **từng trang một** (`bilingual_merge.py:18-20`) và mỗi lần gọi chép lại 9 font của
bản VI → 9 × ~65 = 592 bản sao. (File EN nguồn 2.64 MiB không có font nhúng `/Length1` nào — toàn bộ
nhân bản đến từ phía VI.)

Bằng chứng tách 2 tham số:

| Cách save | Kết quả |
|---|---|
| `save(output, deflate=True)` — **chỉ deflate** | **86.97 MiB — 0 byte lợi ích** |
| `save(output, garbage=4, deflate=True)` | 7.40 MiB (font stream còn lại: 9) |

⇒ **`garbage=4` (dedupe stream trùng) là tham số làm việc; `deflate=True` vô nghĩa ở đây.** Đề xuất
(B) của Tech Lead vẫn cho đúng kết quả, nhưng nếu Architecture.md ghi lý do "không nén" thì một
Dev/Reviewer "tối giản" thành `deflate=True` sẽ mất **toàn bộ** lợi ích mà test kích thước tương đối
vẫn có thể pass (file không to *hơn*). Cần sửa câu chữ V9.1 trước khi giao.

Về rủi ro của (B): cùng pattern đã verify ở S8; tự đo thêm: text 596/596 trang giống hệt, pixel-diff
72 dpi trên 6 trang ngẫu nhiên = **0.0/255 tuyệt đối** (dedupe stream byte-identical không thể đổi
glyph); `f18f796c` 413.76 → 42.31 MiB. Tôi **không quyết định (A)/(B)** — chỉ xác nhận (B) an toàn
về mặt kỹ thuật và nêu rõ tham số nào mới là thứ cần giữ. Vẫn là Protocol 2 vì chạm cả 2 engine.

### X7. ĐỒNG Ý — có bổ sung cách verify

**X7.1 Sửa `/Decode` (V4.4, V5 bước 8) — ĐỒNG Ý, đã chứng minh bằng số.** Inject `/Decode
[1 0 1 0 1 0 1 0]` vào xref 1144 (trang 29) trên bản copy, tạo 3 file: *inj* (gốc đã inject — đây là
"sự thật" viewer phải hiển thị), *v2-fixed* (V5 đầy đủ), *v1-nofix* (re-encode nhưng giữ `/Decode`
như code đang ship):

| So với *inj* | MuPDF (72 dpi) | Quartz (100 dpi) | Nhìn tận mắt (Quartz) |
|---|---|---|---|
| *v2-fixed* | **0.46/255**, max 18 | 10.23/255 (gồm phần lệch ICC ở X3) | ảnh tối/đảo **giống inj** |
| *v1-nofix* | **42.28/255**, max 193 | 25.10/255, max 140 | ảnh **sáng bình thường** = đảo 2 lần |

Cả 2 renderer cùng kết luận. Quartz hiểu `/Decode null` là "không có" (nếu không, ảnh đã mất hoặc
lệch ~40). Đề nghị test V10.2 #4 assert thêm **mức pixel** (render trang sau khi sửa ≈ render gốc
đã inject, trong ngưỡng nhiễu JPEG) chứ không chỉ `xref_get_key == ('null','null')` — vì lỗi này
chưa từng phát tác, assertion ở tầng key không đủ chứng minh viewer hiển thị đúng.

**X7.2 Mở rộng phạm vi sang `/FlateDecode` — ĐỒNG Ý.** Lập luận V4.1 đúng: Flate là lossless, không
thuộc lý do "không nén chồng". Số liệu X1. Lợi ích phụ thuộc tài liệu (V3.3 kết luận 2) — tự đo thêm
2 job Tech Lead chưa chạy V5 lên: `4c9834bf` 6.19 → **5.16 MiB** (13 ảnh DeviceGray/RGB), `f18f796c`
35.97 → **35.73 MiB** (3 ảnh sRGB); text 298/298 và 1040/1040 trang giống hệt.

**X7.3 V8.1 không cần heuristic "ảnh chụp hay đồ hoạ" — ĐỒNG Ý, kèm cảnh báo phạm vi.** Tôi tìm
phản ví dụ bằng tỉ lệ nén Flate (`bytes_flate / (w×h×n)` — đồ hoạ phẳng thường < 0.1): xref 985
(**0.063**), 1146 (0.107), 172/197/206 (~0.3), 3 ảnh `f18f796c` (0.17–0.22). Render 400 dpi
trước/sau và nhìn từng cái: **đều là ảnh chụp** có nền trắng/giấy lớn (collage mở chương, phác thảo
bút chì trên giấy, ảnh phới lồng) — không phân biệt được. Guard nở file đủ **cho 35 ảnh đã gặp**.
Không có mẫu đồ hoạ phẳng > 4 KB nào trong kho → khả năng "biểu đồ/bảng dinh dưỡng dạng ảnh bị
JPEG hoá nhưng vẫn nhỏ hơn Flate" vẫn là `[UNVERIFIED]`, không phải đã loại trừ. Đề nghị **rẻ**: log
`debug` tỉ lệ này cho mỗi ảnh re-encode để QA/Reviewer soi được outlier ở job thật, không thêm
ngưỡng.

**X7.4 V8.2 giữ ảnh xám 8-bit — ĐỒNG Ý.** 12 ảnh DeviceGray của `4c9834bf` (ảnh SEM/ruột bánh, tỉ lệ
Flate 0.3–0.63) nhìn 400 dpi không phân biệt; (B) tái hiện 25.34 MiB.

**X7.5 Guard 4c bpc ≠ 8 — ĐỒNG Ý về logic**; kho không có ảnh Flate nào bpc ≠ 8 (cả 6 job đều 8) →
`[UNVERIFIED]` trên dữ liệu thật, an toàn theo mặc định. Đọc từ `info[4]` (X2).

**X7.6 Fixture 22+25 — ĐỒNG Ý là cần và đúng cỡ**, nhưng nó **chỉ phủ 1 job, 1 producer, 1 ICC
profile**, không phủ DeviceGray thuần, không phủ Indexed. Đo 2 ứng viên bổ sung: trang 99 của
`4c9834bf` = **0.48 MiB**, 1 ảnh Flate `DeviceGray` 800×523 (job khác, colorspace dạng name, v2 →
0.31 MiB) — đáng thêm; trang 168 của `136645f9` = 1.15 MiB, 5 ảnh Indexed + Separation (mẫu thật
cho guard 4d với `min_recompress_bytes=0`) — tuỳ PM cân dung lượng. Không thêm trang 13/17 (9.9 /
14 MiB).

### X8. Điểm nhỏ và `[UNVERIFIED]` còn lại

- **`/LZWDecode`, `/RunLengthDecode`**: cũng lossless như Flate; V5 bước 3 gộp vào "đã nén, bỏ
  qua" và đếm vào `images_skipped_already_compressed` — sai về ngữ nghĩa (không phải "nén chồng")
  nhưng an toàn. 0 mẫu trong kho. Đề nghị ít nhất ghi rõ trong V5 là **cố ý loại, `[UNVERIFIED]`**,
  thay vì im lặng; đưa vào eligibility là việc 1 dòng nếu sau này gặp.
- **pdfium (Chrome) / Acrobat**: `[UNVERIFIED]` — không có công cụ trên máy này. Đề nghị QA (V10.2
  #8) mở file output bằng **Chrome và Preview** ít nhất 1 lần, nhìn trang có ảnh CMYK lớn (p17/p29
  của file sự cố) để loại trừ đảo màu — Quartz đã pass, pdfium chưa.
- **Bẫy đo lường (đồng ý với V7)**: JPEG CMYK MuPDF ghi có APP14 `transform=0`, dữ liệu **thẳng**
  (không theo quy ước Adobe đảo); `Pixmap(jpeg_bytes)` standalone của chính MuPDF đọc lại ra
  `ffff…` từ `0000…` (tự đảo). Ai dùng `extract_image`/`pdfimages` rồi mở file JPEG rời sẽ thấy âm
  bản và báo bug giả. Ghi vào docstring để khỏi điều tra lại.
- Kết quả 4 trang lệch nhiều nhất giống hệt Tech Lead → phép đo pixel-diff của Tech Lead làm đúng,
  chỉ thiếu renderer thứ hai.

### X9. Khuyến nghị cuối — CHƯA sẵn sàng trình user; cần Tech Lead sửa 5 điểm (không cần đo lại)

**Blocking (sửa V5 rồi mới trình — mỗi điểm ≤ 5 dòng code, đều đã verify công cụ ở trên):**

1. **4d**: allowlist `info[5] ∈ {DeviceGray, DeviceRGB, DeviceCMYK, ICCBased}` chạy **trước**
   Pixmap; giữ `pix.n ∈ {1,3,4}` làm lớp hai. Bỏ nhánh `Indexed(...)` chết. (X2)
2. **Bước 7**: **không ghi `/ColorSpace`** (bỏ `_COLORSPACE_BY_CHANNELS`), giữ ICC profile gốc. Ghi rõ
   đây là sửa lỗi có sẵn của v1, độc lập với duyệt scope — cùng hạng với `/Decode`. (X3)
3. **4a**: thêm guard `/Mask` (array hoặc ref) và đổi drop-alpha thành skip. (X4)
4. **V9.1**: viết lại cơ chế = font nhân bản do `insert_pdf` từng trang; `garbage=4` là tham số quyết
   định, `deflate=True` đơn thuần = 0 lợi ích. (X6) — vẫn để PM/user chọn (A)/(B).
5. **4b**: thay câu lý giải "khoảng 100 B–4 KB rỗng" bằng số đo toàn kho (0.08 MiB, 194 byte). (X5)

**Non-blocking (đề nghị, PM quyết):** đọc bpc từ `info[4]`; test `/Decode` assert mức pixel; test
mới cho ICC (`info[5]` của ảnh re-encode vẫn `'ICCBased'`), `/Mask` (inject → ảnh vẫn Flate,
đếm `unsupported`), Indexed (`min_recompress_bytes=0` → `images_skipped_colorspace` tăng đúng số);
fixture bổ sung `4c9834bf` p99 (0.48 MiB); QA mở Chrome + Preview; log tỉ lệ Flate; ghi chú LZW.

**Sau 5 sửa trên**, tôi đánh giá thiết kế **đủ chín** để trình user theo Protocol 2 — số liệu lợi
ích (−46.3% trên file sự cố, lợi ích phụ thuộc tài liệu) và các guard còn lại đều đứng vững qua
verify độc lập, và cả 3 lỗi mới đều là lỗi có sẵn của v1 mà v2 là dịp sửa rẻ nhất.

### X10. Cách tái lập (script tạm ở scratchpad phiên làm việc, không lưu vào repo)

Mọi phép đo dùng bản **copy** trong scratchpad; file production không bị mở ở chế độ ghi. Các bước
tái lập chính (đủ để Tech Lead/QA lặp lại, không cần script của tôi):

1. *Khảo sát*: với mỗi `data/outputs/*/translated_vi.pdf`, gom xref qua `get_page_images(full=True)`,
   đọc `Filter`/`BitsPerComponent`/`ColorSpace`/`Mask`/`Decode` bằng `xref_get_key`, bucket theo
   `len(xref_stream_raw)`; `info[5]` cho họ colorspace.
2. *Thuật toán V5* viết lại độc lập theo đúng text (có cờ `keep_icc`, `min_bytes`, biến thể B);
   so DCT bằng **set SHA-256 nội dung** (không theo xref).
3. *Render độc lập*: `insert_pdf` 1 trang → PDF riêng → `sips -s format png -s dpiWidth 150 -s
   dpiHeight 150 in.pdf --out out.png`; so `Pixmap(png).samples` từng byte (mean/max |Δ|).
4. *Control ICC*: chỉ `xref_set_key(x, "ColorSpace", "/DeviceCMYK")` trên 3 xref trang 29, không đổi
   stream → render Quartz và MuPDF.
5. *Inject*: `xref_set_key(x, "Decode", "[1 0 1 0 1 0 1 0]")` / `"Mask", "[200 255]"` /
   `"Filter", "[/ASCIIHexDecode/FlateDecode]"` trên bản copy rồi quan sát `Pixmap`, `update_stream`.
6. *Song ngữ*: kiểm kê stream theo `/Length1`, hash nội dung; `save(deflate=True)` và
   `save(garbage=4, deflate=True)` riêng rẽ.

## US-16 v2 — Final Decision sau phản biện Domain Expert (2026-09-08)

**Tác giả**: Tech Lead — thiết kế, KHÔNG implement.
**Trạng thái**: ⏸ **Chờ user duyệt (Protocol 2)** — xem W10 để biết chính xác 2 điều user cần quyết.
**Quan hệ tài liệu (đọc kỹ trước khi implement)**: mục này **thay thế (supersede)** các phần sau của
mục "US-16 v2" ở trên: **bước 4a, 4b, 4d, bước 7** của V5, và toàn bộ mục **V9.1**. Mọi phần khác
của US-16 v1 (S1–S10) và US-16 v2 (V1–V4, V6, V7, V8, V10, V11) **giữ nguyên hiệu lực**. Khi 2 mục
mâu thuẫn, **mục này thắng** — Dev đọc W6 (thuật toán hợp nhất) là đủ, không phải ghép tay V5 + sửa.

**Phán quyết tổng**: **chấp nhận cả 5 điểm** Domain Expert nêu ở X9. Không có điểm nào tôi bác bỏ.
Có **2 chỗ tôi làm khác cách Expert đề xuất** (W1 lớp hai, W8 mức độ bắt buộc của fixture Indexed) và
**1 phát hiện bổ sung** (W2.2 — điểm 1 và điểm 2 **ràng buộc nhau**, tách ra implement riêng sẽ tạo
lỗi nặng hơn hiện trạng). Cả 3 đều là "làm chặt hơn", không phải bất đồng về kết luận.

### W0. Nguồn xác thực của riêng mục này (R5-01)

Tôi **không đo lại** các số liệu lớn: Domain Expert đã tái hiện độc lập 100% bảng số của tôi (X1)
bằng script riêng **và** renderer khác hẳn (macOS Quartz qua `sips`, không dùng MuPDF) — lặp lại
lần thứ ba không tạo thêm thông tin, chỉ tốn thời gian. Cái tôi tự chạy hôm nay là **đúng phần
contract PyMuPDF mà 3 điểm blocking dựa vào**, trên file nhỏ (46.87 MB):

```
PyMuPDF 1.28.2 / Python 3.14 — data/outputs/78674af9-.../translated_vi.pdf, quét cả 30 trang
get_page_images(pno, full=True) -> tuple 10 phần tử
info[4] = 8            (int, KHÔNG phải str — dùng trực tiếp, không cần xref_get_key)
info[5] = 'DeviceRGB' | 'DeviceCMYK' | 'ICCBased' | 'Separation' | 'DeviceN' | 'DeviceGray'
info[6] = ''  với DeviceX/ICCBased;  'DeviceCMYK'  với Separation/DeviceN (alternate space)
Phân bố 99 xref: DeviceCMYK 24, ICCBased 22, Separation 46, DeviceN 3, DeviceGray 3, DeviceRGB 1
xref_get_key(xref, "Mask") -> ('null','null') khi key vắng mặt   (5/5 xref thử)
Pixmap(doc, 172).colorspace.name -> 'ICCBased(CMYK,Artifex CMYK SWOP Profile)'   (xác nhận lại C1)
```

Hai điều đáng ghi: (i) tổng **99 xref** khớp chính xác V3.1 → dữ liệu tôi đang đọc đúng là file
Expert và tôi đã dùng; (ii) `info[5]` trả **tên trần** (`'ICCBased'`), **không** kèm dấu ngoặc như
`Pixmap.colorspace.name` — nên guard mới **không dính bẫy C1** (không cần xử lý tiền tố `ICCBased(`).

Ba claim tôi **không tự chạy lại**, kế thừa nguyên trạng từ phản biện đã verify của Expert, ghi rõ
để Reviewer biết ranh giới: đo màu bằng Quartz (X3), 277 ảnh Indexed của `136645f9` (X2), kiểm kê
592 font stream của file song ngữ (X6).

### W1. Điểm 1 — Guard colorspace: allowlist trên `info[5]`, chạy TRƯỚC khi dựng Pixmap

**Đồng ý với X2.** Nhánh `Indexed(...)` trong V5 bước 4d là **dead code** đúng như Expert chứng minh:
MuPDF expand Indexed sang base colorspace ngay khi dựng Pixmap, nên `pix.colorspace.name` trả
`'DeviceCMYK'` — không bao giờ trả `'Indexed(...)'`. Guard viết theo tên Pixmap **không thể** thực
hiện lời hứa "Indexed giữ nguyên" của BR-IMGCOMP-02c.

**Spec chốt**:

- Vòng gom xref (V5 bước 2) không chỉ lưu smask nữa, mà lưu **bộ ba** lấy từ cùng một `info`:
  `meta_by_xref[info[0]] = (smask=info[1], bpc=info[4], cs_family=info[5])`, **first sighting wins**
  (cùng lý do đã ghi ở v1: `info` mô tả chính object xref, không phải chỗ đặt trên trang).
- Hằng số mới: `_ELIGIBLE_CS_FAMILIES = {"DeviceGray", "DeviceRGB", "DeviceCMYK", "ICCBased"}`.
- **Guard 4d (mới)**: `cs_family not in _ELIGIBLE_CS_FAMILIES` → `images_skipped_colorspace += 1`,
  log `debug`, `continue` — **trước** mọi lời gọi `Pixmap`. Loại được `Indexed`, `Separation`,
  `DeviceN`, `Lab`, `Pattern`, `CalRGB`, `CalGray`, và cả `''` (không có `/ColorSpace`).
- **Guard 4c (mới, đổi nguồn dữ liệu)**: đọc bpc từ `meta.bpc` (int) thay vì
  `xref_get_key(xref, "BitsPerComponent")`. Lý do Expert nêu (indirect ref trả `('xref','N 0 R')` →
  skip nhầm trong im lặng) là đúng, và `info[4]` đã resolve sẵn — miễn phí, dùng luôn.

**Chỗ tôi làm khác Expert (lớp hai)**: Expert đề xuất giữ `pix.n ∈ {1,3,4}` **và**
`pix.colorspace.name` làm lớp hai. Tôi **bỏ hẳn `pix.colorspace.name` khỏi vai trò guard** và thay
lớp hai bằng **kiểm tra nhất quán số kênh**:

| `cs_family` | `pix.n` bắt buộc |
|---|---|
| `DeviceGray` | 1 |
| `DeviceRGB` | 3 |
| `DeviceCMYK` | 4 |
| `ICCBased` | ∈ {1, 3, 4} (dict không ghi `N` trong `info[5]`) |

Sai → `images_skipped_colorspace += 1`, log `debug`, không ghi gì. Lý do bỏ `colorspace.name`:
(a) sau allowlist nó **không loại thêm được gì** — chính nó là thứ mù với Indexed (X2) nên không
phải lớp phòng thủ thật; (b) giữ nó lại buộc phải viết đúng cái special-case tiền tố `"ICCBased("`
đã **thực sự gây bug một lần** lúc spike (C1) — giữ một biểu thức đã từng sai làm "lớp hai" cho một
guard đã đúng là thêm rủi ro chứ không thêm an toàn. Kiểm tra `pix.n` vs `cs_family` thì **chính
xác** và là đúng bất biến mà bước ghi kết quả (W2) phụ thuộc vào.

### W2. Điểm 2 — Không ghi đè `/ColorSpace` nữa

**Đồng ý với X3.** Bằng chứng quyết định là hàng "control" của Expert: chỉ đổi `[/ICCBased …]` →
`/DeviceCMYK`, **giữ nguyên Flate, không đụng JPEG** → Quartz lệch **4.38/255**, MuPDF lệch
**0.00**. Nghĩa là toàn bộ phép đo pixel-diff của tôi ở V7/V8.2 — dù đúng — **không có năng lực
nhìn thấy lỗi này**, đúng bản chất bài học C4 (đo bằng chính thư viện tạo ra kết quả).

**W2.1. Spec chốt**: xoá hằng `_COLORSPACE_BY_CHANNELS` và xoá dòng
`doc.xref_set_key(xref, "ColorSpace", ...)` (`image_compress.py:120-122`). **Không thay bằng gì cả.**
`Pixmap(doc, xref)` luôn giải mã ở đúng colorspace gốc với đúng số kênh, JPEG ghi ra cũng đúng số
kênh đó (đã ràng buộc bằng lớp hai ở W1) → `/ColorSpace` cũ tiếp tục mô tả đúng stream mới, và ICC
profile gốc được giữ. `[/ICCBased N]` + `/DCTDecode` là tổ hợp chuẩn. Đo của Expert: biến thể giữ ICC
cho **25.19 MiB — bằng hệt** biến thể ghi đè, tức sửa này **miễn phí về dung lượng**.

Các key còn lại ở bước 7 **giữ nguyên**: `Filter → /DCTDecode`, `BitsPerComponent → 8`,
`Width`/`Height` theo `pix`.

**W2.2. [BỔ SUNG CỦA TECH LEAD — không có trong X9] Điểm 1 và điểm 2 ràng buộc nhau, phải vào cùng
một commit.** Đây là điều tôi cho là rủi ro implement lớn nhất của cả đợt này:

- **Hôm nay** (v1 đang ship): ảnh `Indexed` lọt guard → JPEG hoá → nhưng code **ghi đè**
  `/ColorSpace = /DeviceCMYK` theo `pix.n=4`, nên object vẫn **tự nhất quán**. Hậu quả chỉ là "ảnh
  palette bị JPEG hoá" — xấu, mất chất lượng, nhưng **hiển thị được**.
- **Nếu Dev làm điểm 2 mà quên điểm 1**: stream thành JPEG CMYK 4 kênh trong khi `/ColorSpace` vẫn
  là `[/Indexed /DeviceCMYK hival lookup]` — mỗi sample được viewer hiểu là **1 chỉ số bảng màu**.
  Đây là **PDF hỏng**, nặng hơn hẳn hiện trạng.
- Chiều ngược lại (điểm 1 mà không có điểm 2) thì vô hại, chỉ là chưa sửa lệch màu.

⇒ **Ràng buộc bắt buộc cho Dev**: dòng ghi `/ColorSpace` **chỉ được xoá sau khi** allowlist `info[5]`
đã có mặt trong cùng thay đổi, **và** test W8-#9 (mẫu Indexed thật) xanh. Reviewer kiểm tra đúng thứ
tự này (R6-04 áp cho chuỗi guard→ghi trong cùng một hàm).
⚠️ Cơ chế hỏng ở gạch đầu dòng thứ hai là **suy ra** từ số đo đã verify của Expert (X2:
`Pixmap(doc, 3691)` → `n=4`, `colorspace.name='DeviceCMYK'` trên ảnh `[/Indexed /DeviceCMYK …]`) —
**tôi không tự dựng file hỏng để chạy thử**. Không cần dựng: thiết kế cấm nhánh đó xảy ra, và test
W8-#9 khẳng định điều cấm đó có hiệu lực.

**W2.3. Phạm vi**: sửa này là **sửa lỗi có sẵn của v1**, **độc lập** với quyết định mở rộng scope
sang Flate (W10-a) — v1 hôm nay đã vứt ICC profile với mọi ảnh `Filter: null` gốc ICCBased. Cùng
hạng với sửa `/Decode` (V4.4): nên làm kể cả khi user từ chối mở rộng scope. Lưu ý W2.2 vẫn áp dụng
nguyên vẹn trong kịch bản đó.

### W3. Điểm 3 — Guard `/Mask`, và alpha thì skip chứ không drop

**Đồng ý với X4.** Guard 4a hiện chỉ nhìn `/SMask` (qua `info[1]`) và `/ImageMask`; key **`/Mask`**
(cả dạng array color-key lẫn ref tới stencil) không ai thấy, và `update_stream` giữ nguyên key đó →
mask áp lên sample JPEG **đã đổi giá trị**. Cùng loại lỗi im lặng với `/Decode`.

**Spec chốt — bổ sung vào nhóm guard 4a**:

- `mask_type, _ = doc.xref_get_key(xref, "Mask")`; `mask_type != "null"` → `images_skipped_unsupported
  += 1`, log `warning` (hiếm, đáng nhìn thấy), `continue`. Bắt cả `('array', '[200 255]')` lẫn
  `('xref', 'N 0 R')` chỉ bằng việc so với `"null"` — cú pháp này tôi đã tự xác nhận hôm nay (W0).
- Đổi `if pix.alpha: pix = fitz.Pixmap(pix, 0)` (`image_compress.py:108-109`) thành
  **`if pix.alpha: → images_skipped_unsupported += 1, log warning, continue`**. Lý do: trong luồng
  này alpha chỉ có thể đến từ `/SMask` (đã guard) hoặc `/Mask` color-key (vừa guard) — nếu vẫn còn
  alpha thì nghĩa là có một nguồn ta **chưa hiểu**, và drop nó vừa mất thông tin vừa để lại key sinh
  ra nó trong dict. Skip là lựa chọn duy nhất an toàn.
- 3 guard mask này **không phụ thuộc** quyết định W10-a: chúng là sửa lỗi của v1.

`[UNVERIFIED]` giữ nguyên: 0 mẫu `/Mask` và 0 mẫu `/SMask` thật trong cả 6 job. Hành vi mặc định khi
không có mẫu là **bỏ qua** ⇒ an toàn.

### W4. Điểm 4 — Viết lại cơ chế phình file song ngữ (thay thế V9.1)

**Đồng ý với X6 — chẩn đoán cũ của tôi sai, kết luận cũ đúng vì lý do khác.** V9.1 viết "~84 MB là
content stream/font **không nén**" là sai. Kiểm kê của Expert:

| Loại stream trong `bilingual_vi_en.pdf` (`4c9834bf`, 596 trang, 86.97 MiB) | Filter | Số stream | Bytes |
|---|---|---|---|
| font (`/Length1`) | **`/FlateDecode` — đã nén sẵn** | **592** | **71.08 MiB** |
| content/khác | `/FlateDecode` | 2,598 | 7.96 MiB |
| image | `/FlateDecode` | 26 | 2.65 MiB |

**Cơ chế đúng**: `create_bilingual_pdf()` gọi `insert_pdf` **từng trang một**
(`src/postprocess/bilingual_merge.py:18-21`, vì phải xen kẽ VI/EN). Mỗi lời gọi chép lại bộ font của
bản VI → 592 font stream nhưng chỉ **9 nội dung duy nhất** (0.31 MiB); bản đơn ngữ cùng job có đúng
9. Không có gì "chưa nén" cả — có **9 font bị nhân bản ~65 lần**.

**Hệ quả bắt buộc phải ghi rõ trước khi giao Dev**:

| Cách save | Kết quả đo |
|---|---|
| `save(output_path, deflate=True)` — chỉ deflate | **86.97 MiB — 0 byte lợi ích** |
| `save(output_path, garbage=4, deflate=True)` | **7.40 MiB** (font stream còn 9) |

⇒ **`garbage=4` (garbage-collect object trùng) là tham số làm việc; `deflate=True` một mình vô
nghĩa ở đây.** Nếu Architecture ghi lý do là "không nén", một Dev/Reviewer "tối giản hoá" thành
`deflate=True` sẽ mất **toàn bộ** lợi ích mà một test kiểu "file không to hơn" vẫn pass. Vì vậy nếu
user chọn (B), **test bắt buộc phải assert số font stream (`/Length1`) sau khi save ≤ 10**, không
chỉ assert kích thước — assertion ở tầng kích thước không phân biệt được 2 tham số này.

Rủi ro của (B): Expert đo độc lập — text 596/596 trang giống hệt, **pixel-diff 6 trang ngẫu nhiên =
0.0/255 tuyệt đối** (dedupe stream byte-identical không thể đổi glyph), `f18f796c` 413.76 → 42.31
MiB. Cùng pattern đã verify ở S8.

Một phương án (C) — bỏ `insert_pdf` từng trang, chèn nguyên 2 tài liệu rồi `move_page()` để xen kẽ —
sẽ chặn nhân bản **từ gốc** thay vì dọn sau. Tôi **không đề xuất**: nhiều code hơn, đụng đúng vòng
lặp đang chạy đúng, và không có số đo nào cho thấy nó hơn (B) về kết quả cuối. Ghi lại để khỏi phải
nghĩ lại. Quyết định (A)/(B) vẫn thuộc user (W10-b) vì chạm code path dùng chung cho **cả 2 engine**.

### W5. Điểm 5 — Sửa câu lý giải ngưỡng 4 KB (con số 4096 giữ nguyên)

**Đồng ý với X5.** Câu cũ ở V5 bước 4b — *"khoảng 100 B–4 KB rỗng hoàn toàn nên ngưỡng này không cắt
nhầm ảnh thật nào"* — là tính chất của **đúng 1 file**, và **sai trên kho**: `136645f9` có **186 ảnh
Flate** nằm trong khoảng đó (icon Indexed 46×56 … 209×188).

**Câu thay thế (Dev/Reviewer đọc cái này, không đọc câu cũ)**: ngưỡng 4096 giữ nguyên vì
**tổng dung lượng toàn bộ ảnh Flate < 4 KB trên cả 6 job chỉ ~0.08 MiB (431 ảnh)** — hạ ngưỡng
không đáng công. Đo cụ thể: chạy `136645f9` với `min_recompress_bytes=0` → 347 ảnh bị guard nở file
chặn, 44 skip colorspace, **chỉ 2 ảnh qua được và tiết kiệm tổng cộng 194 byte**, đổi lấy 393 lần
dựng Pixmap. Đây là guard **chi phí + nhiễu log**, không phải guard đúng-sai (guard đúng-sai là guard
nở file ở bước 8). Nó cũng là thứ tránh cho ta 29 exception của C2 trên file sự cố.

### W6. Thuật toán V5-final (hợp nhất — Dev implement theo mục này, không ghép tay)

Thứ tự vẫn là **rẻ → đắt**: mọi phép loại trừ đọc key/metadata chạy **trước** khi dựng `Pixmap`.
Sau W1, **toàn bộ** guard trừ guard nở file đều nằm trước Pixmap.

1. Mở `pdf_path`, ghi `size_before`. *(như v1)*
2. Gom metadata theo xref qua `get_page_images(pno, full=True)`, first sighting wins:
   `meta_by_xref[info[0]] = (smask=info[1], bpc=info[4], cs_family=info[5])`. **[ĐỔI — W1]**
   `images_scanned = len(meta_by_xref)`.
3. **Eligibility filter** *(như V5 bước 3, không đổi)*: `xref_get_key(xref, "Filter")` →
   `type == "null"` **hoặc** `('name', '/FlateDecode')` → eligible; `type == "array"` chứa
   `"FlateDecode"` và không chứa `DCTDecode`/`JPXDecode`/`JBIG2Decode`/`CCITTFaxDecode` → eligible
   (⚠️ `[UNVERIFIED]`, 0 mẫu thật; Expert xác nhận value trả về **không có khoảng trắng giữa các
   name** → phải dùng **substring check**, `value.split()` sẽ sai). Còn lại →
   `images_skipped_already_compressed += 1`, `continue`.
   *Ghi chú cố ý (X8)*: `/LZWDecode`, `/RunLengthDecode` cũng lossless như Flate nhưng **cố ý không
   đưa vào eligibility** (0 mẫu trong kho, `[UNVERIFIED]`) — ghi comment trong code để lần sau khỏi
   tưởng là bỏ sót; thêm vào là việc 1 dòng nếu gặp mẫu thật.
4. **Guard mask/alpha** **[ĐỔI — W3]**: `/ImageMask == true` → skip `unsupported`;
   `meta.smask != 0` → skip `unsupported`; **`xref_get_key(xref,"Mask")[0] != "null"` → skip
   `unsupported`**. Cả 3 log `warning`.
5. **Guard kích thước** *(giữ nguyên hành vi, sửa lý do — W5)*:
   `len(doc.xref_stream_raw(xref)) < min_recompress_bytes` (mặc định 4096) →
   `images_skipped_small += 1`, log `debug`.
6. **Guard bit depth** **[ĐỔI nguồn — W1]**: `meta.bpc != 8` → skip `unsupported`.
7. **Guard colorspace** **[ĐỔI — W1]**: `meta.cs_family not in _ELIGIBLE_CS_FAMILIES` →
   `images_skipped_colorspace += 1`, log `debug`, `continue`. **Trước Pixmap.**
8. Dựng `pix = fitz.Pixmap(doc, xref)`. **`if pix.alpha:` → skip `unsupported`** (không drop — W3).
   **Lớp hai**: `pix.n` không khớp bảng W1 → `images_skipped_colorspace += 1`, log `debug`, `continue`.
9. `jb = pix.tobytes("jpeg", jpg_quality=jpeg_quality)`. Log `debug` kèm **tỉ lệ nén Flate gốc**
   `raw_size / (pix.width * pix.height * pix.n)` (đề nghị X7.3 — để QA soi outlier đồ hoạ phẳng ở
   job thật mà không phải thêm ngưỡng nào).
10. **Guard nở file** *(như v1 — guard đúng-sai duy nhất)*: `len(jb) >= raw_size` →
    `images_skipped_larger += 1`, `continue`.
11. Ghi kết quả **[ĐỔI — W2]**: `update_stream(xref, jb, new=1, compress=0)`;
    `Filter → /DCTDecode`; `BitsPerComponent → 8`; `Width`/`Height` theo `pix`.
    **KHÔNG ghi `/ColorSpace`** — giữ nguyên key gốc (ICC profile). Không cần đụng `/DecodeParms`
    (C3: `update_stream` đã xoá).
12. **Dọn `/Decode`** *(như V5 bước 8)*: **chỉ khi** `xref_get_key(xref,"Decode")[0] != "null"` →
    `xref_set_key(xref, "Decode", "null")`. Set vô điều kiện làm fixture cũ lệch 12 byte vô ích.
13. `doc.save(tmp, garbage=4, deflate=True)` → `close()` → `os.replace(tmp, pdf_path)`. *(như v1)*

### W7. Chữ ký hàm và stats

```python
async def compress_pdf_images(
    pdf_path: str | Path, *, jpeg_quality: int = 85, min_recompress_bytes: int = 4096
) -> ImageCompressStats
```

Không đổi so với V5. `ImageCompressStats` thêm đúng **2 field**: `images_skipped_small`,
`images_skipped_colorspace` (giữ toàn bộ field cũ). Dataclass này chỉ dùng cho log/test — **không**
ghi DB, **không** lên UI. `min_recompress_bytes` là tham số để test tham số hoá được, **không** phải
điểm cấu hình `.env`/UI (BR-IMGCOMP-03 giữ nguyên).

### W8. Test bắt buộc — cập nhật so với V10.2

Giữ nguyên **V10.2 #1–#8**. Bổ sung/nâng cấp:

| # | Test | Mức |
|---|---|---|
| 9 | **Indexed thật bị skip**: fixture mới từ `136645f9` **trang 168** (1.15 MiB, 5 ảnh Indexed + Separation). Gọi với `min_recompress_bytes=0` → `images_skipped_colorspace` tăng đúng số ảnh Indexed+Separation, `images_recompressed == 0`, và `xref_get_key(xref,"ColorSpace")` của các ảnh đó **không đổi**. | **BẮT BUỘC — blocking** |
| 10 | **ICC được giữ**: sau khi chạy trên fixture `78674af9` p22+p25, ảnh đã re-encode phải có `info[5] == 'ICCBased'` và `xref_get_key(xref,"ColorSpace")` **giống hệt trước khi chạy**; `xref_get_key(xref,"Filter") == ('name','/DCTDecode')`. | **BẮT BUỘC** |
| 11 | **`/Mask` inject**: inject `/Mask [200 255]` vào 1 xref Flate → sau khi chạy, `Filter` vẫn `/FlateDecode` (không đụng), stream byte-identical, `images_skipped_unsupported` tăng 1. | **BẮT BUỘC** |
| 12 | **`/Decode` mức pixel** (nâng cấp V10.2 #4 theo X7.1): ngoài assert `xref_get_key == ('null','null')`, render trang sau khi sửa và so với file gốc-đã-inject, sai khác trong ngưỡng nhiễu JPEG (Expert đo: 0.46/255 khi đúng vs **42.28/255** khi sai) — vì lỗi này chưa từng phát tác, assertion ở tầng key không chứng minh viewer hiển thị đúng. | **BẮT BUỘC** |
| 13 | Fixture bổ sung `4c9834bf` **trang 99** (0.48 MiB, 1 ảnh Flate `DeviceGray` **name-form**, job khác, producer khác, ICC khác) — phủ nhánh `cs_family == 'DeviceGray'` mà fixture chính không có. | Nên có |

**Chỗ tôi làm khác Expert**: Expert xếp fixture Indexed (trang 168) là *non-blocking, tuỳ PM cân
dung lượng*. Tôi **nâng lên blocking**, vì sau W2.2 nó không còn là "test cho một guard phụ" — nó là
**bằng chứng duy nhất bằng dữ liệu thật** rằng điều kiện tiên quyết của việc bỏ ghi `/ColorSpace` có
hiệu lực. Nếu PM không chấp nhận thêm 1.15 MiB vào repo, thì phương án lùi **không phải** bỏ test mà
là **giữ nguyên dòng ghi `/ColorSpace`** (tức bỏ luôn điểm 2) — hai thứ đi cùng nhau, không tách.

Ràng buộc Protocol 5/6 giữ nguyên: fixture **phải trích từ file production thật** (không dựng tay),
ghi xuất xứ vào `tests/fixtures/babeldoc/README.md` (job id, số trang gốc, ngày trích, lệnh trích).

### W9. Trạng thái verify sau phản biện

| Hạng mục | Trạng thái |
|---|---|
| Toàn bộ số liệu V1–V8 của Tech Lead | ✅ Verified **2 lần độc lập** (Tech Lead + Domain Expert, script riêng, dữ liệu thật) |
| `info[4]`=bpc int, `info[5]`=họ colorspace trần, `xref_get_key("Mask")` khi vắng | ✅ Verified — Tech Lead tự chạy hôm nay trên file 46.87 MB (W0) |
| Indexed lọt guard cũ (`Pixmap` expand sang base) | ✅ Verified — Expert, 277 ảnh thật ở `136645f9` |
| Ghi đè `/ColorSpace` gây lệch màu trên viewer khác MuPDF | ✅ Verified — Quartz 4.38–6.98/255, control tách riêng khỏi JPEG |
| `/Mask` không có guard, `Pixmap` trả alpha=1 | ✅ Verified cơ chế bằng inject — ⚠️ `[UNVERIFIED]` trên production (0 mẫu/6 job) |
| `garbage=4` mới là tham số quyết định của V9.1, `deflate=True` = 0 byte | ✅ Verified — Expert đo tách 2 tham số |
| Ngưỡng 4096: lý do đúng = 0.08 MiB toàn kho | ✅ Verified — bucket 6 job |
| PDF hỏng nếu bỏ ghi `/ColorSpace` mà thiếu allowlist (W2.2) | ⚠️ **Suy ra** từ X2 đã verify — chặn bằng thiết kế + test W8-#9, không dựng file hỏng để chạy |
| `Filter` dạng array; bpc ≠ 8; colorspace lạ cỡ lớn; `/SMask` | ⚠️ `[UNVERIFIED]` (kế thừa) — mặc định "bỏ qua" ⇒ an toàn |
| pdfium (Chrome) / Acrobat render output CMYK | ⚠️ `[UNVERIFIED]` — QA mở bằng **Chrome + Preview** ít nhất 1 lần ở gate V10.2 #8 |
| **Mở rộng BR-IMGCOMP-02 sang Flate** | ⏸ **Chờ user duyệt — Protocol 2 (W10-a)** |
| **`bilingual_merge.py` (A)/(B)** | ⏸ **Chờ user quyết — Protocol 2 (W10-b)** |
| Thiết kế đã đủ chín để trình user | ✅ Theo đánh giá X9 của Domain Expert, sau 5 sửa ở W1–W5 |

### W10. Hai điều user cần quyết (Protocol 2) — và những gì KHÔNG phụ thuộc vào chúng

**(a) Có duyệt mở rộng BR-IMGCOMP-02 sang ảnh `/FlateDecode` không?**
Được gì: file sự cố 46.87 → 25.19 MB (−46.3%), text/số trang giữ nguyên 100%. Mất gì: ảnh Flate ≥ 4 KB
trở thành JPEG q85 (lossy, **không đảo ngược được** trên file output). Lợi ích **phụ thuộc tài liệu
nguồn**, không đều: `4c9834bf` 6.19 → 5.16 MB, `f18f796c` 35.97 → 35.73 MB (gần như không đổi).
Job 520 MB (`136645f9`) **v2 không cứu được** — 437 MB ở đó đã là JPEG sẵn (V9.2, bài toán khác).

**(b) `bilingual_merge.py`: (A) để backlog hay (B) sửa kèm lần này?**
(B) = đổi `bilingual_merge.py:22` thành `save(output_path, garbage=4, deflate=True)`. Đo: 86.97 →
7.40 MB (−91.5%), 1.0 s; `f18f796c` 413.76 → 42.31 MB. Expert xác nhận **an toàn**: text 596/596
trang giống hệt, **pixel-diff 0.0/255 tuyệt đối**. Vẫn cần user duyệt vì chạm code path dùng chung
cho **cả `pdf2zh` lẫn `babeldoc`** (đúng tiền lệ S8, nơi user đã cố ý từ chối mở rộng sang pdf2zh).

**KHÔNG phụ thuộc (a) hay (b) — là sửa lỗi tiềm ẩn của code đang ship, nên làm trong mọi kịch bản**:
xoá `/Decode` (V4.4), không ghi đè `/ColorSpace` + allowlist `info[5]` đi kèm (W2, **cặp không tách
rời** — W2.2), guard `/Mask` và skip-khi-có-alpha (W3). Nếu user từ chối (a), 4 sửa này vẫn áp dụng
cho nhánh `Filter: null` hiện hành, và W6 rút gọn về đúng bước 3 cũ (`type == "null"`).

---

## Bug #9 — `font_shrink_page()` phá output của babeldoc: tắt hẳn cho engine `babeldoc` (2026-09-08)

**Trạng thái**: hướng khắc phục P0 **ĐÃ QUA Protocol 2** — user duyệt trực tiếp qua PM
(2026-09-08) đúng đề xuất của Domain Expert (chạy model Fable): *tắt hẳn `font_shrink_page()` cho
output của engine `babeldoc`, giữ nguyên cho `pdf2zh`*. Mục này KHÔNG điều tra lại root cause (đã
xong), chỉ chốt **thiết kế cụ thể** để giao Dev.

### B9.1. Nguồn xác thực (Protocol 5 R5-01 / Protocol 1 mở rộng)

Bảng dưới phân biệt rạch ròi 3 mức: (i) Tech Lead **tự đọc source trong repo này** lúc viết mục
này; (ii) **Domain Expert đo/đọc thật** và báo cáo lại cho PM (Tech Lead **chưa** tự chạy lại);
(iii) đã nằm sẵn trong tài liệu handoff đã qua review.

| # | Claim | Mức | Nguồn |
|---|---|---|---|
| B9-01 | Chỉ có **đúng 1** call site của `font_shrink_page()` trong toàn bộ `src/` — `job_orchestrator.py:1292`, bên trong `_process_chunk()`, chạy cho **mọi** trang của **mọi** chunk, **không** phân biệt engine | (i) tự verify | `grep -rn "font_shrink" src/` → chỉ 1 lời gọi; đọc `src/core/job_orchestrator.py:1289-1308` |
| B9-02 | `_process_chunk()` gọi engine qua `self._translator_runner.translate_pages(...)`, engine được chọn ở **1 chỗ duy nhất** là property `_translator_runner` (§6.14.7) | (i) tự verify | `src/core/job_orchestrator.py:264-282` |
| B9-03 | `_redraw_span()` gọi `page.add_redact_annot(span_bbox, fill=(1,1,1))` rồi `page.apply_redactions()` **ngay lập tức, cho từng span một** — nên khi xử lý dòng N+1, vùng redact của nó xoá luôn glyph mà dòng N vừa được `insert_text()` vẽ vào, nếu 2 bbox giao nhau dù chỉ vài phần mười pt | (i) tự verify (cơ chế đọc được thẳng từ code) | `src/postprocess/font_shrink.py:332-333` |
| B9-04 | `font_shrink_page()` được thiết kế **cho pdf2zh**: pdf2zh vẽ bản dịch vào đúng vị trí/cỡ chữ của bản gốc EN, không tự fit lại theo bề ngang box | (i) tự verify | docstring `src/postprocess/font_shrink.py:36-51` ("Real overflow happens when pdf2zh draws the (longer) Vietnamese translation at a page position sized for the (shorter) original English text") |
| B9-05 | babeldoc (`IL/midend/typesetting.py`, bản 0.6.4) **tự bóp cỡ chữ tới tối thiểu 10%** để vừa khung, và **bỏ hẳn đoạn** nếu vẫn không vừa — **không bao giờ** vẽ tràn ra ngoài box | (ii) Domain Expert đọc source thật 2026-09-08 — **Tech Lead CHƯA tự đọc lại** | báo cáo Domain Expert (Fable) gửi PM, 2026-09-08 |
| B9-06 | Trên output babeldoc, `font_shrink_page` bị kích hoạt bởi **sai số đo float vặt vãnh** (median excess đo được = **0.00%**), tức nó redraw mà không hề sửa được gì | (ii) Domain Expert đo thật | như trên |
| B9-07 | **Mất chữ thật**: trang 26 của chính cuốn Le Cordon Bleu, **4 dòng nội dung biến mất** sau bước redraw dòng kế tiếp (đúng cơ chế B9-03; pitch dòng babeldoc = `font_size × 1.3` nhưng bbox glyph Noto Serif cao hơn → 2 bbox dòng kề nhau giao ~0.5pt) | (ii) Domain Expert verify sống | như trên |
| B9-08 | Đo trên chunk 0 thật (40 trang, babeldoc + DeepSeek thật): **126** cặp overlap trước fix Bug #8 → **66** sau fix Bug #8 (mới chỉ sửa toạ độ, CHƯA tắt `font_shrink`) | (iii) đã có trong doc | `docs/test-report.md` mục "Bug #8 — R5-03/R6-03 live E2E trên chunk 0 thật", bảng dòng 2146-2149 |
| B9-09 | Phần lớn 66 cặp còn lại là **nhiễu đo** (dải giao < 2pt giữa 2 dòng kề nhau, sinh ra do chính `font_shrink` tách dòng thành block riêng); overlap **thật** chỉ còn **11**, toàn bộ nằm ở ảnh minh hoạ/bìa, **không** phải văn xuôi | (ii) Domain Expert đo lại 2026-09-08 | báo cáo Domain Expert — đây là **hiệu chỉnh** cách đọc số 66 ở B9-08, không mâu thuẫn với nó |

> **Lưu ý cho Dev (R5-02)**: B9-05/B9-06/B9-07/B9-09 là claim **chưa được Tech Lead tự verify lại**.
> Dev **không cần** spike lại để implement thiết kế này — vì thiết kế chỉ *bỏ đi* một bước xử lý,
> không *thêm* phụ thuộc mới nào vào contract của babeldoc. Nhưng nếu sau này có ai muốn **bật lại**
> `font_shrink` cho babeldoc, hoặc muốn implement khoảng trống ở B9.7 (đọc `paragraph.scale`),
> **bắt buộc** phải tự verify B9-05 từ source babeldoc thật trước.

### B9.2. Root cause (tóm tắt — không điều tra lại)

Ba tầng độc lập cộng lại:

1. **babeldoc không cần bước co-font của app** (B9-05). Nó tự typeset lại toàn bộ và tự đảm bảo
   không vẽ tràn ra ngoài box. Đây là khác biệt bản chất so với pdf2zh (B9-04) — pdf2zh giữ nguyên
   layout gốc nên tràn khung là chuyện *phải* xử lý ở tầng app.
2. **`font_shrink_page()` vẫn chạy cho babeldoc** chỉ vì `_process_chunk()` dùng **chung 1 đường
   ống** cho cả 2 engine (§6.14.7 — nguyên tắc "không rẽ nhánh `if engine ==` rải rác trong thân
   hàm", đặt ra để tránh tái diễn Bug #5). Nguyên tắc đó **đúng và giữ nguyên**; cái sai là ở chỗ
   §6.14.7 chỉ nói về *lời gọi engine*, còn bước post-processing phía sau thì mặc nhiên được coi là
   trung lập với engine — **nó không trung lập**.
3. **Chạy `font_shrink` trên output babeldoc là thao tác thuần rủi ro, lợi ích bằng 0**: nó không
   sửa được gì (B9-06: median excess 0.00% — nó chỉ đang phản ứng với sai số float), nhưng vẫn
   `redact` + `insert_text` lại thật → gây ra Bug #8 (lệch toạ độ MediaBox/CropBox — **đã fix**) VÀ
   **mất chữ thật** (B9-07 + cơ chế B9-03 — **chưa fix, chính là Bug #9**), đồng thời tạo ra phần
   lớn "overlap" giả trong số đo (B9-09).

### B9.3. Thiết kế — thuộc tính năng lực trên runner, KHÔNG rẽ nhánh theo tên engine

**Nguyên tắc**: `_process_chunk()` hỏi **năng lực của runner**, không hỏi **tên engine**. Đây là
mở rộng đúng tinh thần §6.14.7 chứ không phải ngoại lệ của nó: vẫn chỉ có **một** chỗ trong pipeline
biết engine nào đang chạy (property `_translator_runner`), phần thân hàm chỉ đọc một thuộc tính
boolean từ runner đã được chọn.

**Tên thuộc tính đã chốt: `needs_font_shrink`.** Lý do chọn tên này (đã cân nhắc `applies_own_fit`
/ `draws_at_source_layout`):
- Nó trả lời **đúng câu hỏi mà call site đang hỏi**, không bắt người đọc suy luận thêm một bước.
- Khớp precedent naming đã có sẵn trong chính pipeline này: `Pdf2zhService.supports_custom_prompt`
  (dùng ở `src/services/pdf2zh_runner.py:136`) — capability boolean, đặt tên theo *cái mà caller
  cần biết*, không theo *cơ chế nội bộ của tool*.
- Kiểu khai báo: **`ClassVar[bool]`** (class attribute, không phải instance attribute / không phải
  `@property`). Đây là sự thật cố định của engine, không phụ thuộc tham số khởi tạo; khai báo ở cấp
  class để đọc được mà không cần instance và để `ruff`/type-checker soi được.

```python
# src/services/pdf2zh_runner.py — trong `class Pdf2zhRunner`, ngay sau docstring
    #: Bug #9 (Architecture.md "Bug #9"). pdf2zh vẽ bản dịch VÀO ĐÚNG vị trí và
    #: cỡ chữ của bản gốc EN, không tự fit lại theo bề ngang box — nên bước
    #: `font_shrink_page()` của app (BR-FONT-02/US-05) là bắt buộc ở đây.
    needs_font_shrink: ClassVar[bool] = True
```

```python
# src/services/babeldoc_runner.py — trong `class BabeldocRunner`, ngay sau docstring
    #: Bug #9 (Architecture.md "Bug #9"). babeldoc tự typeset lại và tự bóp cỡ
    #: chữ (tới tối thiểu 10%) để vừa box, bỏ hẳn đoạn nếu vẫn không vừa —
    #: KHÔNG BAO GIỜ vẽ tràn ra ngoài box. Chạy thêm `font_shrink_page()` trên
    #: output của nó không sửa được gì (median excess đo được = 0.00%, nó chỉ
    #: phản ứng với sai số float) nhưng vẫn redact + insert_text lại thật —
    #: gây Bug #8 (lệch toạ độ, đã fix) và XOÁ MẤT CHỮ THẬT (Bug #9).
    needs_font_shrink: ClassVar[bool] = False
```

Cả 2 file cần thêm `from typing import ClassVar` (hiện chưa import `typing`).

### B9.4. Vị trí sửa chính xác trong `job_orchestrator.py`

**(a) Thêm property đọc năng lực — đặt NGAY SAU `_translator_runner` (hiện kết thúc ở dòng 282):**

```python
    @property
    def _needs_font_shrink(self) -> bool:
        """Bug #9 — hỏi NĂNG LỰC của engine đã chọn, không hỏi TÊN engine.
        Cùng kỷ luật §6.14.7: chỉ `_translator_runner` biết engine nào đang
        chạy; thân `_process_chunk()` chỉ đọc 1 boolean.

        `isinstance` guard là CÓ CHỦ ĐÍCH, không phải phòng thủ thừa: production
        luôn trả về `bool` thật (ClassVar trên cả 2 runner), nên nhánh raise chỉ
        với tới được từ test dùng `AsyncMock(spec=...Runner)` — mock KHÔNG copy
        GIÁ TRỊ của class attribute, chỉ copy TÊN, nên `mock.needs_font_shrink`
        là 1 child Mock TRUTHY. Không có guard này, một test babeldoc quên set
        thuộc tính sẽ âm thầm chạy nhánh pdf2zh và vẫn PASS — đúng loại
        "mock tự nhất quán với chính nó" mà Protocol 5/6 sinh ra để chặn.
        """
        value = self._translator_runner.needs_font_shrink
        if not isinstance(value, bool):
            raise TypeError(
                f"{type(self._translator_runner).__name__}.needs_font_shrink phải là bool, "
                f"nhận được {value!r}. Nếu đây là test dùng AsyncMock(spec=...), phải set "
                "tường minh `runner.needs_font_shrink = True/False` cho đúng nhánh đang test "
                "(Architecture.md Bug #9 B9.4)."
            )
        return value
```

**(b) Bọc đúng khối `font_shrink` hiện tại (`job_orchestrator.py:1289-1293`):**

```python
        overflow_entries: list[OverflowEntry] = []
        # Bug #9 (Architecture.md "Bug #9", Protocol 2 2026-09-08): CHỈ engine
        # nào tự nó không fit text vào box mới cần bước này. Với babeldoc, mở
        # file ra redact + insert_text lại là thao tác thuần rủi ro: không sửa
        # được gì mà xoá mất chữ thật.
        if self._needs_font_shrink:
            with fitz.open(chunk.output_path) as doc:
                for page in doc:
                    await font_shrink_page(page, overflow_entries, font_path=self._noto_font_path)
                doc.saveIncr()

        for entry in overflow_entries:
            ...  # GIỮ NGUYÊN, không sửa 1 ký tự nào (dòng 1295-1308 hiện tại)
```

**Tổng phạm vi sửa `src/`**: 3 file, không file nào khác.

| File | Vị trí (theo bản hiện tại) | Việc |
|---|---|---|
| `src/services/pdf2zh_runner.py` | dòng 82 (giữa docstring class `Pdf2zhRunner` kết thúc ở 81 và `def __init__` ở 83) | thêm `needs_font_shrink: ClassVar[bool] = True` + import `ClassVar` |
| `src/services/babeldoc_runner.py` | dòng 220 (giữa docstring class `BabeldocRunner` kết thúc ở 219 và `def __init__` ở 221) | thêm `needs_font_shrink: ClassVar[bool] = False` + import `ClassVar` |
| `src/core/job_orchestrator.py` | sau dòng 282 | thêm property `_needs_font_shrink` |
| `src/core/job_orchestrator.py` | dòng 1289-1293 | bọc khối `with fitz.open(...)` trong `if self._needs_font_shrink:` |

**KHÔNG sửa**: `src/postprocess/font_shrink.py` (module giữ nguyên 100% — nó vẫn là đường đúng cho
pdf2zh), `src/models/overflow.py`, schema DB, `src/core/config.py`.

### B9.5. `overflow_entries` khi `needs_font_shrink=False` — giữ list rỗng, KHÔNG bỏ code

**Quyết định: giữ nguyên khai báo `overflow_entries: list[OverflowEntry] = []` ở ngoài `if`, và
giữ nguyên vòng lặp ghi `OverflowReport` phía sau — không đụng vào.** Khi tắt, list rỗng, vòng lặp
chạy 0 lần, 0 row được ghi.

Lý do (đây là phương án **ít xáo trộn nhất**, đúng yêu cầu):
1. **Diff nhỏ nhất có thể**: đúng 1 dòng `if` + thụt lề 4 dòng. Phương án gộp cả khối ghi DB vào
   trong `if` phải di chuyển 14 dòng code — nhiều cơ hội sai hơn, và toàn bộ 14 dòng đó là đường
   **đang chạy đúng** cho pdf2zh.
2. **Không đụng vào đường persistence của pdf2zh**: đây chính là cách hỏng kiểu Bug #5 (sửa nhánh
   này làm gãy nhánh kia mà không ai thấy vì test mỗi nhánh tự nhất quán).
3. **Chừa sẵn chỗ cho khoảng trống B9.7**: nếu sau này lấy được tín hiệu overflow từ chính babeldoc
   (`paragraph.scale`), chỗ nạp vào `overflow_entries` đã có sẵn, không phải dựng lại đường ghi DB.
4. Chi phí runtime của việc giữ lại: cấp phát 1 list rỗng + 1 vòng lặp 0 vòng — bằng 0 trên thực tế.

### B9.6. Yêu cầu test cho Dev (R6-02 — assert giá trị, không chỉ assert "đã gọi")

Bắt buộc, vì bug này thuộc đúng loại "hai mock tự nhất quán với nhau":

1. **T9-1 (nhánh babeldoc — không đụng file)**: chạy `_process_chunk()`/`run_job()` với
   `pdf_translate_engine="babeldoc"` trên 1 PDF thật do PyMuPDF sinh; assert **file
   `chunk.output_path` byte-identical trước/sau bước post-processing** (so `hashlib.sha256` hoặc
   `st_mtime` + size), VÀ `SELECT COUNT(*) FROM overflow_reports WHERE job_id=...` **== 0**.
   Assert nội dung/giá trị, không dùng `assert_called()`.
2. **T9-2 (nhánh pdf2zh — hồi quy, không được đổi hành vi)**: cùng input, `pdf_translate_engine=
   "pdf2zh"`; assert bước font_shrink **vẫn chạy** (file bị sửa / `OverflowReport` vẫn được ghi khi
   có span tràn thật). Đây là test chống việc fix này vô tình tắt cả 2 engine.
3. **T9-3 (guard)**: `AsyncMock(spec=BabeldocRunner)` không set `needs_font_shrink` → `pytest.raises(TypeError)`.
   Test này bảo vệ chính cơ chế bảo vệ.
4. **Sửa 7 chỗ tạo mock runner hiện có** (đây là toàn bộ, đã grep — không có chỗ nào khác):
   `tests/integration/test_job_cancel.py:76`, `tests/integration/test_job_orchestrator_concurrency.py:66`,
   `tests/integration/test_job_orchestrator.py:86`, `:379`, `:441` (`spec=Pdf2zhRunner` → set
   `= True`), `tests/integration/test_job_orchestrator.py:504`, `:1001`
   (`spec=BabeldocRunner` → set `= False`). Mỗi chỗ thêm đúng 1 dòng
   `runner.needs_font_shrink = True/False`.

**Live E2E (R6-03)**: chạy lại đúng chunk 0 (40 trang đầu Le Cordon Bleu, babeldoc + DeepSeek thật)
mà QA đã dùng cho Bug #8, rồi **mở file output ra kiểm tra nội dung** (không tin `status`):
(a) trang 26 phải có **đủ 4 dòng** mà B9-07 báo là biến mất; (b) đếm lại overlap bằng đúng script
`ov3.py` (area giao > 200pt², `block[6]==0`) — kỳ vọng tụt mạnh khỏi mốc 66 về gần 11 (B9-09).
Không đặt ngưỡng cứng "phải bằng 11": 11 cặp còn lại thuộc root cause khác (babeldoc typesetting
không reflow, xem mục "Root Cause Analysis: Text Overlap, Content-Loss & Reading-Order", 2026-09-07)
và **không** nằm trong phạm vi Bug #9.

### B9.7. Khoảng trống đã biết trước — CHẤP NHẬN, để dành cho tương lai

Tắt `font_shrink_page()` cho babeldoc đồng nghĩa **nhánh babeldoc không còn ghi `OverflowReport`
nào nữa** — kể cả khi bản thân babeldoc âm thầm **bỏ hẳn 1 đoạn** vì không vừa box dù đã bóp còn
10% (B9-05). BA/QA sẽ mất cờ cảnh báo "trang này cần soi tay" cho nhánh babeldoc.

Đây là khoảng trống **đã biết trước và được chấp nhận có ý thức**, KHÔNG vá trong task này:

- Cờ đó vốn đã **gần như vô giá trị** trên babeldoc: nó được sinh ra từ phép đo của
  `font_shrink_page` trên một trang mà chính babeldoc đã fit xong, tức đo trên sai số float
  (B9-06) — dữ liệu đúng nhưng vô nghĩa, tệ hơn là kèm theo tác hại xoá chữ.
- Hướng vá đúng trong tương lai (đề xuất của Domain Expert, **chưa thiết kế**): đọc
  `paragraph.scale` từ debug output riêng của babeldoc → nếu `scale` chạm sàn (hoặc đoạn bị drop
  hẳn) thì ghi 1 `OverflowReport`/`layout_qa_finding`. Việc này cần Protocol 5 R5-01 đầy đủ cho
  format debug output của babeldoc (**chưa ai verify**) nên **không** gộp vào P0 này.
- Nơi đặt tự nhiên cho tín hiệu đó khi làm: cùng đường `persist_findings()` mà overlay chữ xoay
  đang dùng (`job_orchestrator.py:593-609`), chứ không nhất thiết là bảng `overflow_reports`.

**Hệ quả cần PM/BA biết**: acceptance criteria US-05/BR-FONT-02 (co font chống tràn khung) từ nay
**chỉ còn hiệu lực trên đường `pdf2zh`**. Trên đường `babeldoc` (đang là **default** từ 2026-09-05),
chống tràn khung là trách nhiệm của chính babeldoc, app không can thiệp và không đo. Cần cập nhật
PRD ở lượt review PRD gần nhất — **không** phải việc của Dev trong task này.

### B9.8. Rollback

**Không thêm feature flag mới** cho bước này (cân nhắc rồi, cố ý bỏ). Lý do: một flag chỉ có ý
nghĩa khi cả 2 trạng thái đều là lựa chọn hợp lệ; ở đây trạng thái "bật" đã được chứng minh là
**phá dữ liệu** (xoá chữ thật, B9-07) chứ không phải "đánh đổi". Thêm flag = thêm một đường cấu
hình dẫn thẳng tới bug đã biết, cộng thêm surface cho `SETTINGS_DB_OVERRIDABLE_FIELDS`.

Đường rollback thực tế nếu cần: (a) `PDF_TRANSLATE_ENGINE=pdf2zh` + restart — flag **đã có sẵn**
từ §6.14.7, đưa toàn bộ pipeline về đường v1.1.1; hoặc (b) revert đúng 1 hằng số
`BabeldocRunner.needs_font_shrink` về `True` (1 dòng, 1 commit).

---

## Bug #10 — babeldoc cắt ngang từ tiếng Việt giữa chừng (`_get_width_before_next_break_point` đếm đôi bề rộng ký tự hiện tại) — thiết kế bản vá (Tech Lead, 2026-09-09)

**Trạng thái**: THIẾT KẾ — chưa implement. Đây là **lỗi thật của chính babeldoc 0.6.4 upstream**,
không phải lỗi code của project. Vá bằng shim monkeypatch qua `src/babeldoc_shim/sitecustomize.py`,
đúng khuôn mẫu đã dùng cho Bug #7 (7.1/7.2/7.4-b).

**Nguồn phát hiện**: Domain Expert (Fable) trong lúc điều tra Bug #8/#9. Toàn bộ root cause dưới đây
đã được Tech Lead **tự đọc lại source thật để verify** (Protocol 5 R5-01) — brief của Expert được coi
là giả thuyết cần kiểm chứng, không phải sự thật. Kết quả: root cause khớp; có **4 điểm cần đính
chính/bổ sung** so với brief, ghi ở BA10.4.

---

### BA10.1. Nguồn xác thực (Protocol 5 R5-01)

| Mục | Nguồn |
|---|---|
| Tool | `babeldoc` **0.6.4**, cài qua `uv tool` |
| Đường dẫn source đã đọc | `~/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/format/pdf/document_il/midend/typesetting.py` (1682 dòng) |
| Xác nhận version | thư mục `babeldoc-0.6.4.dist-info` cạnh package |
| Cách verify | Đọc trực tiếp file bằng `Read`/`sed` (không qua trí nhớ, không qua WebFetch bản upstream) |
| Ngày verify | 2026-09-09 |

**CẢNH BÁO có thật, Dev phải biết**: trên máy này tồn tại **hai** bản babeldoc khác nhau:
- `~/.local/share/uv/tools/babeldoc/.../babeldoc/format/pdf/document_il/midend/typesetting.py` — bản
  0.6.4 **app đang thực sự dùng** (`BabeldocRunner._executable = "babeldoc"`). ĐÂY là bản cần vá.
- `~/.local/share/uv/tools/pdf2zh/.../babeldoc/document_il/midend/typesetting.py` — bản babeldoc **cũ
  hơn, bundle bên trong tool `pdf2zh`** (đường module KHÁC: không có `format/pdf/`). Bản này chỉ chạy
  khi `PDF_TRANSLATE_ENGINE=pdf2zh`. **KHÔNG thuộc phạm vi Bug #10** — shim gate theo
  `babeldoc.__version__ == "0.6.4"` và theo tên module đầy đủ `babeldoc.format.pdf...`, nên tự động
  không đụng tới bản trong pdf2zh. Không mở rộng phạm vi sang đó trong task này.

---

### BA10.2. Root cause — đã tự verify bằng đọc code thật

#### BA10.2-a. Hàm lookahead ĐÃ CỘNG bề rộng của chính unit hiện tại

`typesetting.py:1285-1298` (trích nguyên văn bản đã cài):

```python
    def _get_width_before_next_break_point(
        self, typesetting_units: list[TypesettingUnit], scale: float
    ) -> float:
        if not typesetting_units:
            return 0
        if typesetting_units[0].can_break_line:
            return 0

        total_width = 0
        for unit in typesetting_units:          # <-- BẮT ĐẦU TỪ units[0] = unit HIỆN TẠI
            if unit.can_break_line:
                return total_width * scale
            total_width += unit.width           # <-- cộng cả w(unit hiện tại)
        return total_width * scale
```

Vòng lặp bắt đầu từ `typesetting_units[0]`. Ngay trước đó đã có guard `if typesetting_units[0].
can_break_line: return 0`, nên khi vào được vòng lặp thì `units[0]` chắc chắn KHÔNG phải break point
⇒ lần lặp đầu tiên luôn chạy `total_width += units[0].width`. Kết luận:

> giá trị trả về = `w(unit_hiện_tại) + w(unit kế) + ... ` cho tới (không kể) break point kế tiếp.

#### BA10.2-b. Chỗ gọi CỘNG THÊM `unit_width` một lần nữa

`typesetting.py:1366` và `:1399-1417` (trong `_layout_typesetting_units`):

```python
            unit_width = unit.width * scale                       # :1366
            ...
            if use_english_line_break:                            # :1399
                width_before_next_break_point = self._get_width_before_next_break_point(
                    typesetting_units[i:], scale                  # :1400-1402  <-- lát cắt BẮT ĐẦU tại i
                )
            else:
                width_before_next_break_point = 0

            # 如果当前行放不下这个元素，换行
            if not unit.is_hung_punctuation and (                 # :1407
                (current_x + unit_width > box.x2)                 # :1408  (A) chốt chặn cứng
                or (
                    use_english_line_break
                    and current_x + unit_width + width_before_next_break_point > box.x2   # :1411 (B) LỖI
                )
                or (
                    unit.is_cannot_appear_in_line_end_punctuation
                    and current_x + unit_width * 2 > box.x2       # :1415  (C) không liên quan
                )
            ):
```

Lát cắt truyền vào là `typesetting_units[i:]` — tức **bao gồm chính unit thứ `i`**. Vì vậy biểu thức
(B) ở `:1411` khai triển ra là:

```
current_x + w(uᵢ) + [ w(uᵢ) + w(uᵢ₊₁) + ... + w(u_{k-1}) ]      với u_k là break point kế tiếp
= current_x + 2·w(uᵢ) + w(phần còn lại của từ)
```

Đúng ra phải là `current_x + w(uᵢ) + w(phần còn lại của từ)` — tức chính xác bằng
`current_x + width_before_next_break_point` (vì hàm đã bao gồm `w(uᵢ)` rồi). **Xác nhận toàn bộ mô tả
root cause của Expert, kể cả số dòng (1285-1298 và 1407-1417) đều đúng nguyên văn.**

#### BA10.2-c. Hệ quả: wrap xảy ra SAI CHỖ, cắt giữa từ

Phần dư `+w(uᵢ)` **phụ thuộc vào bề rộng của chính ký tự đang xét**, nên ngưỡng không nhất quán giữa
các ký tự trong cùng một từ:
- ký tự hẹp (`t`, w≈3.17pt) → phần dư nhỏ → vượt qua được (B) → được đặt ở cuối dòng;
- ký tự rộng ngay sau (`r`, w≈4.24pt) → phần dư lớn hơn → (B) kích hoạt → **xuống dòng giữa từ**.

Kết quả quan sát được: `"trung thành"` → `"t"` cuối dòng + `"rung thành"` đầu dòng sau; các case khác
Expert đo được: `"khâu c|huẩn bị"`, `"liên tục c|ho"`. Quy mô Expert đo: 31 ca / 1.664 dòng trên 40
trang raw babeldoc (phía tiếng Anh gốc: 7/1.801 — nhiễu nền).

#### BA10.2-d. Tại sao upstream không phát hiện: `LINE_BREAK_REGEX` KHÔNG chứa dải CJK

`typesetting.py:31-88` định nghĩa `LINE_BREAK_REGEX`; `calc_can_break_line` (`:213-219`) trả về
`False` khi regex match. Các dải có trong regex gồm `a-zA-Z0-9`, Latin-1 Supplement, Latin Extended
A/B/**Additional (`Ḁ-ỿ`)**, **Combining Diacritical Marks (`̀-ͯ`)**, Cyrillic,
Greek, Thai, Khmer, Myanmar... — **KHÔNG có dải Hán/Kana nào**.

⇒ Với tiếng Trung/Nhật (thị trường chính của babeldoc), MỌI ký tự đều `can_break_line == True` ⇒
guard `:1290-1291` trả `0` ⇒ số hạng lỗi ở (B) **triệt tiêu hoàn toàn**, bug **vô hình**.
⇒ Với tiếng Việt, chữ có dấu nằm đúng trong `Ḁ-ỿ` + `̀-ͯ` ⇒ cả từ là một chuỗi
`can_break_line == False` dài ⇒ bug lộ ra dày đặc.

Đây là cơ chế **cấu trúc**, mạnh hơn cách diễn đạt của Expert ("lộ rõ hơn ở tiếng Việt vì nhiều từ có
dấu/âm tiết dài") — xem đính chính BA10.4-3.

---

### BA10.3. Bản vá — thiết kế chốt

#### BA10.3-a. Điểm vá: vá HÀM lookahead, KHÔNG vá chỗ gọi

Hai cách sửa tương đương về số học:
1. Bỏ `w(uᵢ)` khỏi giá trị trả về của `_get_width_before_next_break_point` (hàm 14 dòng), hoặc
2. Bỏ `unit_width` khỏi biểu thức `:1411` — nhưng phải thay thế **cả hàm
   `_layout_typesetting_units` dài 167 dòng** (`:1300-1466`) vì không có điểm hook nhỏ hơn.

**Chốt cách (1)** — patch tối thiểu, đúng nguyên tắc "ưu tiên patch nhỏ, dễ review":
- Đã grep toàn bộ package babeldoc đã cài: `_get_width_before_next_break_point` có **đúng 1 chỗ gọi**
  (`typesetting.py:1400`) và **1 chỗ định nghĩa** (`:1285`) — không có consumer nào khác, nên đổi ngữ
  nghĩa của nó là an toàn tuyệt đối trong phạm vi package.
- Cách (2) phải copy 167 dòng logic layout (line-skip, mixed CJK/Latin spacing, box expansion...) vào
  shim — rủi ro sai sót và chi phí re-verify khi upgrade cao hơn hẳn, **loại**.

#### BA10.3-b. Hàm thay thế

Đặt thuật toán thuần (không phụ thuộc babeldoc) tại **module mới `src/babeldoc_shim/word_wrap.py`**
để test gọi đúng logic production (Protocol 6 R6-02 — không được chép tay thuật toán sang test):

```python
# src/babeldoc_shim/word_wrap.py  (module MỚI, thuật toán thuần)
def width_before_next_break_point(
    units: Sequence[tuple[float, bool]],   # [(width, can_break_line), ...] bắt đầu TẠI unit hiện tại
    scale: float,
) -> float:
    """Bề rộng phần CÒN LẠI của từ, KHÔNG kể unit hiện tại (Bug #10)."""
    if not units:
        return 0.0
    if units[0][1]:              # unit hiện tại tự nó là break point -> giữ nguyên hành vi gốc
        return 0.0
    total = 0.0
    for width, can_break in units[1:]:     # <-- KHÁC BẢN GỐC: bỏ qua units[0]
        if can_break:
            break
        total += width
    return total * scale
```

Wrapper trong `sitecustomize.py` chỉ làm nhiệm vụ bóc field từ object babeldoc thật rồi ủy thác:

```python
def _build_patched_get_width_before_next_break_point(typesetting_module):
    from word_wrap import width_before_next_break_point       # import tên trần: PYTHONPATH trỏ
                                                              # THẲNG vào src/babeldoc_shim/
    def patched(self, typesetting_units, scale):
        return width_before_next_break_point(
            [(u.width, u.can_break_line) for u in typesetting_units], scale
        )
    return patched
```

**Lưu ý hiệu năng (bắt buộc cân nhắc khi implement)**: hàm gốc **thoát sớm** tại break point đầu
tiên, còn list-comprehension ở trên **duyệt toàn bộ lát cắt `typesetting_units[i:]`** (O(n) cho mọi
`i` ⇒ O(n²) trên paragraph dài). Hàm này nằm trong vòng lặp layout chạy lại cho **mọi giá trị scale**
thử nghiệm ⇒ nguy cơ chậm thật, không phải lo xa. **Yêu cầu Dev**: hoặc (a) truyền generator/iterator
lười thay vì list đã materialize, hoặc (b) để wrapper tự duyệt và thoát sớm rồi chỉ ủy thác phép cộng
— miễn là thuật toán vẫn nằm ở `word_wrap.py` và test gọi đúng nó. Dev đo thời gian dịch 1 trang
trước/sau patch trong spike (BA10.5-G4) để chứng minh không hồi quy hiệu năng.

#### BA10.3-c. Vì sao bản vá KHÔNG thể gây tràn dòng (tự verify bằng đọc code)

Ba tính chất, đọc thẳng từ source:

1. **Chốt chặn cứng bên phải KHÔNG bị đụng tới.** Nhánh (A) `:1408` `current_x + unit_width > box.x2`
   là một mệnh đề `or` **độc lập**, không dùng `width_before_next_break_point`, và patch không sửa
   `_layout_typesetting_units`. Vì vậy sau vá, mọi unit được đặt vẫn thoả `current_x + unit_width <=
   box.x2` y hệt trước vá ⇒ **không unit nào có thể bị đặt vượt quá `box.x2`**. Đây là tính chất
   quan trọng nhất, và nó là tính chất **cấu trúc** (nhánh (A) còn nguyên), không phải suy luận số học.
2. **Số dòng không thể TĂNG.** Patch làm vế trái của (B) **nhỏ đi đúng `unit_width >= 0`** ⇒ (B) là
   một vị từ **yếu hơn theo từng điểm**: "sau vá wrap" ⟹ "trước vá cũng wrap". Với thuật toán greedy
   đơn điệu theo `current_x` này, vị từ yếu hơn không bao giờ sinh thêm dòng. Đã kiểm chứng thêm bằng
   mô phỏng thuần: 20.000 trường hợp ngẫu nhiên (độ dài từ/bề rộng ký tự ngẫu nhiên) — **0 trường hợp
   nào bản vá cho ra nhiều dòng hơn bản gốc**.
3. **`all_units_fit` chỉ tuỳ thuộc số dòng.** `:1440-1444` đặt `all_units_fit = False` khi và chỉ khi
   `current_y < box.y` sau một lần xuống dòng ⇒ ít dòng hơn (hoặc bằng) ⇒ `all_units_fit` chỉ có thể
   giữ nguyên hoặc chuyển `False → True`, không bao giờ ngược lại.

Từ (2)+(3): trong `_find_optimal_scale_and_layout` (`:973-1002`) vòng `while scale >= min_scale` sẽ
**dừng sớm hơn hoặc bằng** ⇒ scale được chọn **lớn hơn hoặc bằng** trước vá. Xem hệ quả ở BA10.4-4.

---

### BA10.4. Khác biệt so với báo cáo của Expert (bắt buộc ghi theo Protocol 5 R5-01)

| # | Expert nói | Tech Lead verify | Kết luận |
|---|---|---|---|
| 1 | Số dòng `~1285-1298` (hàm) và `~1407-1417` (điều kiện wrap), công thức sai `cx + 2·w(uᵢ) + w(phần còn lại)` | Đúng **nguyên văn**, cả số dòng lẫn công thức | ✅ XÁC NHẬN |
| 2 | "dòng có thể chứa thêm **tối đa 1 ký tự** khi từ vừa khít" | **KHÔNG chính xác** — xem dưới | ⚠️ ĐÍNH CHÍNH |
| 3 | Bug "lộ rõ hơn ở tiếng Việt vì nhiều từ có dấu/âm tiết dài" | Cơ chế thật mạnh hơn: `LINE_BREAK_REGEX` (`:31-88`) không chứa dải CJK ⇒ với zh/ja số hạng lỗi **triệt tiêu bằng 0**, bug **vô hình hoàn toàn**, không phải "ít lộ hơn" | ⚠️ BỔ SUNG |
| 4 | (không đề cập) | Bản vá có **tác dụng phụ nhìn thấy được**: một số paragraph sẽ render **font TO HƠN** trước | ⚠️ BỔ SUNG QUAN TRỌNG |

**Đính chính #2 chi tiết** — vì `can_break_line` là `False` cho toàn bộ chữ cái nhưng `True` cho dấu
cách, "phần còn lại tới break point kế tiếp" chính là **phần đuôi còn lại của TỪ hiện tại**, không
phải một ký tự. Trong ca `"trung thành"`: tại `t`, biểu thức đúng là `cx + w("t") + w("rung") =
cx + w("trung") = 587.06 <= 590.91` ⇒ đặt `t`; tại `r`, `cx' + w("r") + w("ung") = cx + w("trung")`
= vẫn 587.06 ⇒ đặt tiếp; và cứ thế **cả từ `"trung"` ở lại trên dòng**. Chỗ xuống dòng thật sẽ rơi
vào **dấu cách** ngay sau đó (`can_break_line == True` ⇒ lookahead = 0 ⇒ chỉ còn nhánh (A)).

⇒ Phát biểu đúng: **một dòng có thể nhận thêm phần đuôi còn lại của MỘT từ (có thể vài ký tự), không
phải đúng 1 ký tự.** Điều này KHÔNG làm yếu tính chất an toàn, vì tính chất an toàn đến từ nhánh (A)
còn nguyên (BA10.3-c điểm 1), không đến từ "chỉ thêm 1 ký tự".

**Bổ sung #4 chi tiết** — theo BA10.3-c điểm (2)+(3), `all_units_fit` có thể chuyển `False → True` ở
một `scale` **lớn hơn**, nên `_get_optimal_scale` sẽ trả về scale lớn hơn cho một số paragraph.
**Hệ quả nhìn thấy được: chữ ở các paragraph đó TO HƠN sau khi vá.** Đây là **cải thiện**, không phải
hồi quy (mọi scale được chấp nhận đều đã qua `all_units_fit`, vẫn nằm trong box). QA **phải biết
trước** điều này để không mở bug mới khi thấy diff cỡ chữ giữa 2 lần chạy A/B.

---

### BA10.5. Yêu cầu spike TRƯỚC KHI implement đầy đủ (Protocol 5 R5-02) — BẮT BUỘC

Đây là lần đầu project vá vào `typesetting.py` (3 patch Bug #7 đều nằm ở `paragraph_finder.py`), tức
hành vi **chưa từng được project verify sống**. Dev **KHÔNG** được viết implementation + test đầy đủ
trước khi spike xanh.

**Phương pháp A/B bắt buộc — tận dụng translation cache của babeldoc**: babeldoc cache kết quả dịch
(`--ignore-cache` để tắt). Chạy lần 1 **KHÔNG patch** (nạp cache), rồi lần 2 **CÓ patch** trên đúng
input đó **KHÔNG** truyền `--ignore-cache` ⇒ văn bản tiếng Việt **giống hệt nhau** giữa 2 lần, mọi
khác biệt còn lại **thuần tuý là layout**. Không làm thế này thì LLM trả về text khác nhau và mọi
phép so sánh trước/sau đều vô nghĩa.

| Gate | Nội dung | Tiêu chí PASS |
|---|---|---|
| **G1** (đích) | Chạy trên fixture 1 trang (BA10.6), so sánh raw babeldoc trước/sau patch | Trước: có ít nhất 1 ca cắt giữa từ (kỳ vọng `"trung thành"` bị tách). Sau: ca đó **không còn bị tách** |
| **G2** (tràn ngang) | Trích bbox mọi text block bằng `pymupdf` trên toàn bộ trang test + trang đối chứng | `max(block.x1)` sau vá **KHÔNG lớn hơn** trước vá quá 0.5pt trên bất kỳ trang nào |
| **G3** (số dòng) | Đếm số dòng text mỗi trang, trước vs sau | Sau vá `<=` trước vá trên **MỌI** trang. Nếu có trang nào TĂNG ⇒ giả thuyết đơn điệu ở BA10.3-c sai ⇒ **escalate Tech Lead ngay**, không tự sửa |
| **G4** (hiệu năng) | Đo wall-clock 1 trang, trước vs sau (cache đã nóng cho cả 2) | Không chậm hơn quá 20%. Nếu chậm hơn ⇒ áp dụng tối ưu thoát-sớm ở BA10.3-b |
| **G5** (không mất chữ) | So tổng độ dài text trích được | Sau vá `>=` trước vá (không được mất ký tự nào) |

**Trang đối chứng cho G2/G3/G5** (trang KHÔNG có bug này từ trước, để bắt hồi quy ngược) — tái dùng
fixture đã có, **không tạo mới**: `tests/fixtures/babeldoc/page14_numbered_list_source.pdf`,
`tests/fixtures/babeldoc/toc_sources/lcb_toc.pdf`, `tests/fixtures/babeldoc/toc_sources/figoni_p25_recipe.pdf`.

---

### BA10.6. Golden fixture (Protocol 5 mục 3)

**Fixture nguồn — TẠO MỚI (bắt buộc, không tái dùng được cái nào đang có)**:

```
tests/fixtures/babeldoc/bug10_sources/lcb_p39_loyal.pdf
```

Trích **đúng 1 trang, page index 39 (0-based)** từ
`data/uploads/7ff56932-0c9e-403e-9555-4b4059c60b59_Le-Cordon-Bleu-Patisserie-and-Baking-Foundations (1).pdf`
(418 trang, 277MB — **KHÔNG commit file gốc**):

```python
import pymupdf
src = pymupdf.open("data/uploads/7ff56932-...-Foundations (1).pdf")
out = pymupdf.open(); out.insert_pdf(src, from_page=39, to_page=39)
out.save("tests/fixtures/babeldoc/bug10_sources/lcb_p39_loyal.pdf")
```

**Tech Lead đã tự xác nhận trang này đúng là trang có case của Expert**: text trang 39 (0-based) chứa
`"...recognizes motivated and loyal employees by sending them to do a "stage"..."` — `"loyal
employees"` chính là nguồn của `"nhân viên trung thành"` mà Expert quan sát thấy bị cắt thành
`"t|rung thành"`. Trang này cũng là "Chapter 2 / trang in số 24" — dùng để đối chiếu bằng mắt.

**Fixture unit-level — TẠO MỚI trong lúc spike**:

```
tests/fixtures/babeldoc/bug10_wrap/lcb_p39_trung_thanh_units.json
```

Trong spike, dump từ **lần chạy babeldoc THẬT** chuỗi `[(unit.width, unit.can_break_line), ...]` của
paragraph chứa `"trung thành"`, kèm `current_x` tại điểm bắt đầu từ đó, `box.x2` và `scale`. Test đơn
vị cho `word_wrap.width_before_next_break_point` **phải nạp từ file này**, KHÔNG được gõ tay số liệu
tự nghĩ ra (Protocol 5 mục 3: mock viết tay theo giả định = test tự xác nhận giả định).

Assertion bắt buộc của test đó (R6-02 — assert **giá trị cụ thể**, không phải "đã gọi"):
- với dữ liệu golden, biểu thức `current_x + unit_width + width_before_next_break_point(...)` tại ký
  tự `'r'` phải `<= box.x2` (sau vá), trong khi công thức gốc (đếm đôi) cho `> box.x2` — tức test
  **chứng minh được chính xác điểm khác biệt hành vi**, không chỉ "hàm chạy không lỗi".

---

### BA10.7. Vị trí sửa trong `src/babeldoc_shim/sitecustomize.py` — cơ chế gate GIỮ NGUYÊN

**KHÔNG tạo cơ chế gate mới.** Tái dùng nguyên `_EXPECTED_BABELDOC_VERSION = "0.6.4"` +
`_install_hook_if_version_matches()` đang có. Danh sách thay đổi tối thiểu (số dòng theo bản hiện tại,
603 dòng):

| Vị trí hiện tại | Thay đổi |
|---|---|
| `:137` `_TARGET_MODULE_NAME` | Đổi tên thành `_PARAGRAPH_FINDER_MODULE_NAME`; **thêm** `_TYPESETTING_MODULE_NAME = "babeldoc.format.pdf.document_il.midend.typesetting"` |
| `:144-147` (cạnh `_toc_split_enabled`) | Thêm `_word_wrap_fix_enabled()` đọc `BABELDOC_SHIM_WORD_WRAP_FIX`, **mặc định `"1"` (BẬT)** |
| mới, cạnh `:427` | Thêm `_build_patched_get_width_before_next_break_point(typesetting_module)` (code ở BA10.3-b) |
| `:462` `_apply_patch` | Đổi tên → `_apply_paragraph_finder_patch`; **thêm** `_apply_typesetting_patch(module)` riêng: check `hasattr(Typesetting, "_get_width_before_next_break_point")` rồi mới gán, log `logger.warning` riêng |
| `:508` `_PatchingLoader` | Tham số hoá: `__init__(self, wrapped_loader, apply_patch, label)`; `exec_module` gọi `self._apply_patch(module)` trong try/except như cũ, log kèm `label` |
| `:533` `_ParagraphFinderPatchFinder` | Đổi tên → `_ModulePatchFinder(target_fullname, apply_patch, label)` (logic `find_spec` giữ **nguyên xi**, kể cả cờ `_resolving` và thủ thuật gỡ/chèn lại `sys.meta_path`) |
| `:597` | Cài **hai** finder: một cho `paragraph_finder`, một cho `typesetting`. Nhánh fallback `if ... in sys.modules` (`:583-595`) áp dụng riêng cho từng module |

**Ràng buộc thiết kế bắt buộc**:

1. **Rollback ĐỘC LẬP.** Patch typesetting phải nằm trong `try/except` **riêng** với 3 patch
   `paragraph_finder`. Nếu babeldoc đổi cấu trúc `typesetting.py`, 3 patch Bug #7 vẫn phải chạy bình
   thường, và ngược lại. (Khác với 3 patch Bug #7 — chúng cố ý rollback CHUNG vì cùng một class.)
   Vì là 2 module / 2 loader riêng nên tính chất này có sẵn — **không được gộp lại cho "gọn"**.
2. **KHÔNG có phụ thuộc thứ tự** giữa Bug #10 và 7.1/7.2/7.4-b. `paragraph_finder` chạy ở giai đoạn
   tách đoạn/dòng, `typesetting` chạy sau ở giai đoạn dàn trang; bản vá Bug #10 không quan tâm đoạn
   được tách thế nào. (Khác 7.1→7.2 vốn **bắt buộc** đúng thứ tự.)
3. **Tên module `word_wrap.py` phải không đụng hàng.** `PYTHONPATH` trỏ thẳng vào
   `src/babeldoc_shim/` nên mọi file `.py` ở đó thành **module top-level** trong subprocess babeldoc,
   có thể che khuất module cùng tên của stdlib/thư viện. Dev phải xác nhận `word_wrap` không tồn tại
   trong venv babeldoc. **Tech Lead đã tự kiểm tra 2026-09-09**: `ls ~/.local/share/uv/tools/babeldoc/
   lib/python3.12/site-packages/ | grep -i word_wrap` → **0 kết quả**, và `python3 -c "import
   word_wrap"` → `ModuleNotFoundError` ⇒ tên `word_wrap` **an toàn, không đụng hàng**. Rủi ro này có
   sẵn từ Bug #7 (`line_split`, `toc_split`) — nếu Dev đổi sang tên khác thì phải tự kiểm tra lại.

---

### BA10.8. Feature flag & wiring

Theo đúng mẫu 3 flag đang có (`babeldoc_line_split_shim_enabled` / `..._numbered_list_split_enabled` /
`..._toc_split_enabled`):

| Tầng | Thêm |
|---|---|
| `src/core/config.py` (cạnh `:240`) | `babeldoc_word_wrap_fix_enabled: bool = True` + comment nêu rõ đây là **fix số học đúng/sai**, không phải heuristic |
| `src/services/babeldoc_runner.py` `__init__` | tham số `word_wrap_fix_enabled: bool = False` (giữ default `False` cho khởi tạo trực tiếp trong test, **giống hệt** `toc_split_enabled`) → `self._word_wrap_fix_enabled` |
| `src/services/babeldoc_runner.py` `:378` | trong block `if self._line_split_shim_enabled:` thêm `env["BABELDOC_SHIM_WORD_WRAP_FIX"] = "1" if self._word_wrap_fix_enabled else "0"` |
| `src/core/job_orchestrator.py` `:275-281` | truyền `word_wrap_fix_enabled=self._settings.babeldoc_word_wrap_fix_enabled` |

**Mặc định BẬT (`Settings` = `True`)** — khác TOC-1 v2 (từng mặc định TẮT). Lý do: đây không phải
heuristic đoán ý đồ layout mà là **sửa một phép cộng thừa**, có tính chất an toàn cấu trúc chứng minh
được (BA10.3-c) và không có "false positive" theo nghĩa của heuristic. **Nhưng**: Dev **không được**
đặt default `True` trong cùng commit với spike chưa xanh — thứ tự bắt buộc là spike (BA10.5) xanh →
Reviewer → mới bật.

**Đường rollback**: `BABELDOC_SHIM_WORD_WRAP_FIX=0` / `babeldoc_word_wrap_fix_enabled=False` — tắt
riêng Bug #10, **không** đụng 7.1/7.2/7.4-b.

---

### BA10.9. Phạm vi test yêu cầu cho Dev

1. **Unit test thuần** `tests/test_babeldoc_word_wrap.py` — gọi `word_wrap.width_before_next_break_point`
   trên golden fixture BA10.6, assert đúng điểm khác biệt hành vi (đã nêu chi tiết ở BA10.6). Kèm case
   biên: list rỗng; `units[0].can_break_line == True` (phải trả `0.0`, **giữ nguyên hành vi gốc**); từ
   dài không có break point nào tới hết list; `scale != 1.0`.
2. **Test wiring** trong `tests/test_babeldoc_runner.py` — assert `env["BABELDOC_SHIM_WORD_WRAP_FIX"]`
   nhận đúng `"1"`/`"0"` theo cờ, và **không** xuất hiện khi `line_split_shim_enabled=False`.
3. **Test shim** trong `tests/test_babeldoc_shim_unicode_regression.py` (hoặc file mới cùng phong
   cách) — dựng class giả có `_get_width_before_next_break_point`, chạy `_apply_typesetting_patch`,
   assert đã bị thay; và assert khi class **thiếu** method đó thì raise `AttributeError` (đường
   fail-safe) mà **không** ảnh hưởng tới các patch `paragraph_finder`.
4. **Live E2E (Protocol 6 R6-03, QA gate)** — 1 lần chạy xuyên suốt trên fixture BA10.6 qua
   `JobOrchestrator` đầy đủ (không chỉ `BabeldocRunner`), **mở file PDF output ra kiểm tra nội dung
   thật**: `"trung thành"` (hoặc case tương đương thực tế quan sát được trong lần chạy đó) xuất hiện
   **liền mạch trên cùng một dòng**. Không được chỉ tin `status == "completed"`.

---

### BA10.10. Việc KHÔNG làm trong task này

- **Không** report bug lên upstream babeldoc trong phạm vi task này (Expert đã xác nhận nhánh `main`
  còn nguyên lỗi, chưa có issue nào mô tả đúng bản chất — issue #615 là chuyện khác). Nếu muốn làm,
  đó là task riêng do người quyết định, không phải Dev.
- **Không** đụng bản babeldoc bundle trong tool `pdf2zh` (BA10.1).
- **Không** gộp chung với 11 cặp overlap còn tồn của Bug #9 / mục "Root Cause Analysis: Text Overlap"
  (2026-09-07) — đó là root cause khác (babeldoc không reflow), không liên quan.

---

## Bug #EPUB-3 — Quét job mồ côi (orphan) lúc server startup (Tech Lead, 2026-09-10)

### E3.1. Vấn đề & phạm vi

Background task chạy job (`_schedule_background(_run_job_background(job.id))`,
`src/api/routes/jobs.py:650` và `:766`) là `asyncio.Task` sống trong CHÍNH process uvicorn. Process
chết (crash, deploy, `--reload` reload khi sửa code) → task chết theo, không có `except` nào chạy,
row `jobs` giữ nguyên trạng thái đang chạy VĨNH VIỄN. UI (`web/js/app.js:488`) poll mỗi 3s cho tới
khi status thuộc `TERMINAL_STATUSES` → job kẹt hiển thị "đang dịch" vô thời hạn.

**Không phải bug riêng EPUB** — không có chỗ nào trong đường đi này phụ thuộc `file_type`. Ảnh
hưởng mọi `file_type` (pdf_digital, pdf_scan, epub) và cả `job_type=parse_only` (status `parsing`,
có thể chạy tới ~25 phút).

Gốc rễ: `lifespan()` (`src/api/main.py:80-83`) hiện chỉ có `await init_db()` — **đã đọc code thật,
xác nhận đúng như mô tả**, không có bước quét nào lúc startup.

### E3.2. Tập trạng thái — đọc từ code thật, không suy đoán

`Job.status` là `str` tự do (không phải Enum). Danh sách giá trị thật, gộp từ 3 nguồn:

| Nguồn | Giá trị |
|---|---|
| Comment `src/models/job.py:32-34` | `created`, `queued`, `chunking`, `translating`, `post_processing`, `merging`, `completed`, `failed`, `cancelled`, `cost_capped` |
| Gán thật trong `src/core/job_orchestrator.py` | `translating` (:568, :890), `merging` (:687, :1084), **`parsing`** (:1230, :1469), `completed`, `failed`, `cancelled`, `cost_capped` |
| `src/api/routes/jobs.py` | `queued` (:646 create, :757 retry) |

**Phát hiện 1 (bất ngờ)**: `parsing` **thiếu trong comment liệt kê của `src/models/job.py`** nhưng
được gán thật 2 chỗ trong orchestrator và đã có trong `_ACTIVE_JOB_STATUSES`
(`src/api/routes/jobs.py:832`) + `web/js/app.js:24`. Comment model bị lỗi thời — Dev phải cập nhật
comment đó trong task này (thêm `parsing`), nếu không lần sau lại có người liệt kê thiếu.

**Phát hiện 2**: `chunking` và `post_processing` **KHÔNG BAO GIỜ được gán cho `Job`** ở code hiện
tại (grep toàn `src/`: `post_processing` chỉ gán cho `Chunk` tại `:1884`; `chunking` không xuất
hiện ở vế gán nào). Chúng vẫn nằm trong `_ACTIVE_JOB_STATUSES` như dự phòng. Giữ nguyên trong tập
orphan bên dưới — chi phí bằng 0, và bảo vệ sẵn nếu tương lai có ai dùng lại.

Tập trạng thái cuối (terminal) đã có sẵn tên trong code:
`_TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled", "cost_capped"}`
(`src/api/routes/jobs.py:249`).

### E3.3. Chốt: danh sách trạng thái coi là orphan

```
_ORPHAN_JOB_STATUSES = {
    "created", "queued", "chunking", "parsing",
    "translating", "post_processing", "merging",
}
```

Đúng bằng `_ACTIVE_JOB_STATUSES` (`src/api/routes/jobs.py:821-833`) hiện tại. **Nhưng KHÔNG import
lại set đó** — hai set này trùng giá trị vì trùng ngữ cảnh ("job chưa kết thúc"), không phải vì
cùng một business rule; ghép chúng lại tạo coupling ngầm giữa "cấm xoá job đang chạy" và "quét
orphan lúc startup". Khai báo riêng, kèm comment trỏ chéo sang nhau.

Bao gồm `created`: row ở `created` chỉ sống giữa 2 lần commit trong CÙNG 1 request `POST /api/jobs`
(`src/api/routes/jobs.py:638` → `:646`). Còn `created` sau khi process khởi động lại = request đó
đã chết giữa chừng, KHÔNG có background task nào sẽ nhặt nó lên → là orphan thật.

**Giả định (ghi rõ theo yêu cầu)**: single-process, single-worker. Xác nhận bằng
`.claude/launch.json` — `uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`,
KHÔNG có `--workers`, mặc định uvicorn = 1 worker. Không tìm thấy cấu hình gunicorn/systemd
`--workers > 1` nào trong repo. Do đó: mọi job ở trạng thái "đang chạy" tại thời điểm 1 process MỚI
chạy `lifespan()` chắc chắn là orphan (process cũ phải chết thì mới có process mới) → không có
false positive, không cần lock/transaction chống race.

Với `--reload` ở dev: job thật đang chạy + Dev sửa code → job đó CHÍNH LÀ orphan (task async chết
theo process cũ). Mark failed là ĐÚNG, không phải false positive. Đây là hành vi mong muốn, không
phải tác dụng phụ cần giảm nhẹ.

**Nếu sau này chuyển sang multi-worker** (`--workers N`, hoặc nhiều container cùng 1 SQLite/DB):
thiết kế này SAI ngay lập tức (worker B startup sẽ giết job đang chạy thật của worker A). Lúc đó
phải đổi sang cơ chế heartbeat (`job.heartbeat_at` cập nhật mỗi chunk, quét job có heartbeat cũ hơn
N phút) hoặc owner-token theo process. Ghi lại đây làm điều kiện tiên quyết — ai đổi sang
multi-worker PHẢI đọc lại mục này.

### E3.4. Chốt: hành động — dùng lại `failed`, KHÔNG thêm status mới

Cân nhắc `orphaned` như 1 status thứ 11: **bị loại**. Lý do cụ thể, không phải "cho đơn giản":

- Mỗi status mới phải được thêm ĐỒNG THỜI vào ít nhất 5 chỗ rời rạc:
  `_TERMINAL_JOB_STATUSES`, `_RETRYABLE_STATUSES`, `_ACTIVE_JOB_STATUSES` (loại trừ),
  `TERMINAL_STATUSES`/`ACTIVE_STATUSES` trong `web/js/app.js:16-44`, filter dropdown
  `web/history.html`, cộng mọi nhánh hiển thị badge. Lịch sử repo cho thấy đúng kiểu bỏ sót này đã
  xảy ra 1 lần (S15-12: quên `parsing` trong danh sách JS) — thêm status thứ 11 là tái tạo lại
  đúng rủi ro đó để đổi lấy 1 sắc thái ngữ nghĩa.
- `failed` đã có sẵn toàn bộ hạ tầng: retry được, `finished_at` được tính vào "thời gian dịch"
  (BR-HIST-01), xoá được, hiện badge đỏ, đếm vào `Batch.failed_files`.
- Thông tin "đây là do restart, không phải lỗi dịch" nằm ở `error_message` — vốn đã LUÔN hiển thị
  cạnh status trong UI khi job failed, và câu chữ dưới đây nói thẳng nguyên nhân. Đủ bù đắp.

Với mỗi job orphan tìm được, ghi:

```python
job.status = "failed"
job.error_message = (
    "Job bi gian doan do server khoi dong lai (restart/crash) trong luc dang chay. "
    "Cac chunk da dich xong duoc giu nguyen — bam Retry de chay tiep tu cho dang do."
)
job.finished_at = job.finished_at or datetime.now(UTC)
job.updated_at = datetime.now(UTC)
```

Quy ước câu chữ (khớp code hiện có): `error_message` trong `src/core/job_orchestrator.py:634-638`
và `:1006-1010` viết tiếng Việt **KHÔNG dấu**, cấu trúc "chuyện gì xảy ra — dữ liệu cũ còn nguyên —
làm gì tiếp theo". Câu trên giữ đúng 3 phần đó. **Không đổi sang tiếng Việt có dấu** trong task này
(sẽ lệch với mọi message khác).

`finished_at` bắt buộc gán (US-19/BR-HIST-01/02, §6.17.2): thiếu nó, `_to_detail()`
(`src/api/routes/jobs.py:265-268`) trả `duration_seconds=None` cho job đã ở trạng thái cuối. Dùng
`or` để không đè giá trị cũ nếu vì lý do nào đó đã có.

**KHÔNG đụng tới**: `progress`, `current_chunk`, `total_chunks`, `actual_cost` — giữ nguyên để user
thấy job đã chạy tới đâu trước khi chết. **KHÔNG đụng `Chunk.status`** — xem E3.5.

**KHÔNG quét `Batch`**: `Batch.status` KHÔNG phải chỉ báo tiến độ của user (không hiển thị ở
`web/js/app.js`, không có endpoint list batch), và `created` là trạng thái vĩnh viễn HỢP LỆ của mọi
Batch row sinh ra cho job đơn lẻ (`src/api/routes/jobs.py:478` — mỗi job standalone vẫn tạo 1 Batch
row nhưng `run_batch()` không bao giờ chạy cho nó). Quét batch sẽ mark failed hàng loạt row bình
thường. Ngoài phạm vi task này.

### E3.5. Chunk còn dở — không cần xử lý, đã verify

Resume (BR-CHUNK-05) chỉ skip chunk có `status == "completed"`:
`if chunk.status != "completed":` (`src/core/job_orchestrator.py:578` cho PDF, `:916` cho EPUB), và
bước merge chỉ lấy chunk `completed` CÓ `output_path` (`:1090`). Chunk bị bỏ dở ở `translating`/
`post_processing` sẽ tự được chạy lại ở lần retry, và `_process_chunk()` gán đè
`chunk.status = "translating"` (`:1744`) ngay khi bắt đầu. **Không cần reset Chunk.status về
`pending`** — thêm bước đó là code thừa không đổi hành vi.

### E3.6. Retry sau khi mark orphan — KHÔNG cần sửa gì (đã đọc code xác nhận)

`_RETRYABLE_STATUSES = {"failed", "cancelled", "cost_capped"}` (`src/api/routes/jobs.py:711`) đã
chứa `failed` → job orphan bấm Retry được ngay, **không phải sửa endpoint**. Đường đi retry
(`src/api/routes/jobs.py:714-768`) làm đúng những gì job orphan cần:

1. `job_type == "translate"` → qua lại cost gate (đúng thiết kế §6.11.4 Lớp 3); `parse_only` bỏ qua
   gate (S15-11).
2. `job.status = "queued"`, `job.error_message = None` (xoá câu orphan), `cancel_requested = False`.
3. `_schedule_background(_run_job_background(job.id))` → `run_job()` tự resume từ chunk chưa
   `completed` (BR-CHUNK-05) — **không dịch lại từ đầu**, đúng tinh thần yêu cầu. Với PDF scan,
   `ocr_bridge_path` đã lưu trong DB nên bước OCR cũng không chạy lại.

Lưu ý duy nhất cho Dev: `finished_at` KHÔNG bị reset khi retry (code hiện tại không reset) — hành
vi này đã tồn tại cho mọi retry từ trước, không phải hồi quy do task này, KHÔNG sửa ở đây.

### E3.7. Vị trí code chính xác

**File mới `src/core/job_recovery.py`** (không nhét logic vào `main.py`: để test gọi thẳng hàm với
1 session in-memory, không phải dựng `TestClient` + đè engine global):

```python
_ORPHAN_JOB_STATUSES = {...}  # E3.3

async def fail_orphaned_jobs(session: AsyncSession) -> int:
    """Tra ve so job da mark. Idempotent: chay lai lan 2 tra ve 0."""
```

Thân hàm: `select(Job).where(col(Job.status).in_(_ORPHAN_JOB_STATUSES))` qua SQLModel/AsyncSession
(**không raw SQL** — raw SQL bỏ qua model, dễ lệch tên cột như các migration đã phải xử lý ở
`src/models/database.py`), gán 4 field ở E3.4, `session.add(job)` từng row, `await session.commit()`
MỘT LẦN sau vòng lặp. Ghi log tổng kết:
`logger.warning("Startup: da danh dau %d job mo coi thanh failed (server restart)", count)` — dùng
logger `logging.getLogger(__name__)` (module nằm dưới `src.` nên tự nhận handler từ
`_configure_logging()`).

**`src/api/main.py::lifespan()`** — chèn NGAY SAU `init_db()`, TRƯỚC `yield`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    # Bug #EPUB-3 (Architecture.md §E3): phai chay SAU init_db() (bang/cot
    # phai ton tai truoc khi query) va TRUOC yield (xong truoc khi nhan
    # request dau tien -> khong co race voi job moi tao).
    async with get_session_factory()() as session:
        await fail_orphaned_jobs(session)
    yield
```

Thứ tự bắt buộc: sau `init_db()` (cần bảng + cột đã migrate), trước `yield` (uvicorn chỉ nhận
request sau khi lifespan startup xong → không có job mới nào được tạo song song → không cần
transaction/lock đặc biệt; giả định single-worker ở E3.3).

Không broadcast WebSocket: lúc startup chưa có client nào kết nối, và UI đang mở sẽ nhận qua
polling 3s (`web/js/app.js:488`) trong vòng ≤ 3 giây sau khi server sống lại.

### E3.8. Test bắt buộc (Protocol 6 R6-02 — assert giá trị, không chỉ "đã gọi")

`tests/integration/test_orphan_job_recovery.py`, dùng lại fixture `session` từ
`tests/integration/test_job_orchestrator.py` (pattern y hệt
`tests/integration/test_job_history_finished_at.py`):

1. **Mark đúng tập orphan**: tạo 7 Job, mỗi job 1 status trong `_ORPHAN_JOB_STATUSES`; gọi
   `fail_orphaned_jobs(session)`; assert trả về `7`, và MỌI job có `status == "failed"`,
   `error_message` chứa `"khoi dong lai"`, `finished_at is not None`.
2. **Không đụng trạng thái cuối**: tạo 4 Job ở `completed`/`failed`/`cancelled`/`cost_capped`, mỗi
   job có `error_message` riêng đặt trước; gọi hàm; assert trả về `0` và `error_message` +
   `finished_at` của cả 4 **không đổi** (so sánh giá trị cụ thể, không chỉ `status`).
3. **Giữ nguyên tiến độ**: 1 job `translating` với `progress=0.6`, `current_chunk=3`,
   `total_chunks=5`, `actual_cost=1.23`; sau khi mark, assert 4 giá trị đó **y nguyên**.
4. **Idempotent**: gọi `fail_orphaned_jobs()` 2 lần liên tiếp; lần 2 trả về `0`, và `finished_at`
   của job đã mark ở lần 1 **không bị ghi đè** (assert bằng giá trị đọc được sau lần 1).
5. **Retry được sau khi mark orphan** (đây là assertion nối 2 bước, R6-02): job `translating` →
   `fail_orphaned_jobs()` → gọi `POST /api/jobs/{id}/retry` (hoặc gọi thẳng `retry_job()` với
   session, như `tests/integration/test_job_cancel.py` đang làm) → assert **không** raise
   `HTTPException 400`, và `job.status == "queued"`, `job.error_message is None`,
   `job.cancel_requested is False`.
6. **Chunk completed sống sót qua orphan → retry không dịch lại**: job `translating` có 3 Chunk
   (`completed`, `translating`, `pending`); sau `fail_orphaned_jobs()`, assert `Chunk.status` của
   cả 3 **không đổi** (chứng minh E3.5: hàm không đụng chunk, chunk `completed` vẫn được skip khi
   resume).

Test 5 và 6 là 2 test quan trọng nhất — chúng nối "mark orphan" với "retry resume được", đúng loại
liên kết giữa 2 bước mà Protocol 6 tồn tại để bảo vệ.

### E3.9. Việc KHÔNG làm trong task này

- Không thêm status `orphaned` (lý do E3.4).
- Không quét/sửa `Batch` (lý do E3.4).
- Không thêm heartbeat/owner-token (chỉ cần khi multi-worker — E3.3).
- Không tự động retry job orphan lúc startup (auto-resume): job orphan có thể là job đang tốn tiền
  API; tự chạy lại khi server khởi động = tiêu tiền không có người bấm nút. User bấm Retry.
- Không đổi `error_message` của các nhánh khác sang tiếng Việt có dấu.

## Final Decision: Hiếu trả lời 3 open_questions HOI-01/02/03 + duyệt lại baseline C1/C2 (2026-09-11)

Theo Protocol B (CLARIFY trước, WRITE sau) — cả 3 câu hỏi được PM gộp hỏi một lượt
(`open_questions[]` trong `project_state.json`), Hiếu trả lời trực tiếp trong chat, cả 3 đều
**trùng với mặc định đề xuất**:

- **HOI-01** (cấp API key thật CLAUDE/GEMINI để verify spike rate-limit AIMD?) → **Chưa cấp API
  thật.** Giữ nguyên `[UNVERIFIED]` cho nhánh Claude/Gemini (Architecture.md §6.12.6) — không chặn
  release, DeepSeek/Ollama vẫn là nhánh đã verify dùng cho job thật.
- **HOI-02** (Bug #6: overlay chữ xoay không kích hoạt cho nhánh `pdf_scan` + `babeldoc` — thiết kế
  lại hay chấp nhận giới hạn?) → **Chưa có kế hoạch dùng PDF scan** ở thời điểm hiện tại → chấp
  nhận là giới hạn đã biết của nhánh `pdf_scan` (đã ghi trong PRD.md US-04 "Known limitation Bug #6
  Phase 1"), không mở thêm vòng Dev↔QA để redesign. Nếu sau này có nhu cầu dùng `pdf_scan` thật,
  cần mở lại open_question mới thay vì coi quyết định này là vĩnh viễn.
- **HOI-03** (US-22 EPUB: JSON malformed từ DeepSeek, chọn hướng nào trong 4 phương án ở
  escalation-log.md?) → **Phương án 1**: giảm `EPUB_REQUEST_CHAR_BUDGET` và đo thật trước khi đầu
  tư đổi format request/response.

**Hệ quả**: không có thay đổi code nào cần thiết ngay từ 3 quyết định này — cả 3 đều xác nhận giữ
nguyên hành vi/giới hạn hiện tại, không phải giao việc mới cho Dev. Phương án 1 của HOI-03 (giảm
`EPUB_REQUEST_CHAR_BUDGET`) cần một task đo đạc + điều chỉnh cấu hình riêng, PM sẽ tạo `steps[]`
mới khi bắt tay vào, không tính là đã "làm" chỉ vì đã chọn phương án.

**Đồng thời**, Hiếu duyệt lại baseline cho 2 checkpoint đang `stale` (Protocol C / mở rộng Protocol
2): `docs/PRD.md` và `docs/Architecture.md` ở đúng nội dung hiện tại (2026-09-11) được chốt làm
**Version 2.0** — xem `checkpoints[]` trong `project_state.json` để biết `approved_commit` sau khi
đổi được commit.

---

## BL-04 — Phát hiện babeldoc tự bỏ đoạn: verify lại R5-05 + Final Decision (Tech Lead, 2026-09-11)

**Hợp đồng hiện hành nằm ở `docs/Architecture.md` §6.22** (mục này chỉ ghi *vì sao*, không lặp lại
spec — Protocol C.1). Backlog gốc: `BL-04` trong `project_state.json` → `backlog[]`, phát sinh từ
B9.7 ("khoảng trống đã biết trước — CHẤP NHẬN").

### BL4.1. Việc đầu tiên phải làm là gỡ một nghi vấn version — và nó hoá ra là báo động giả

PM gắn nhãn `[CHƯA VERIFY]` cho một quan sát: trên máy có `babeldoc-0.2.33.dist-info`, khác con số
**0.6.4** mà B9-05 trích dẫn. Ba giả thuyết PM nêu: (a) gõ nhầm lúc ghi design-log, (b) máy đang
chạy bản cũ hơn lúc research, (c) 2 version hành vi khác nhau thật.

Đáp án là **(d) — không có trong danh sách**: máy này có **hai bản babeldoc cài song song, độc lập**.

- `babeldoc` executable → `/Users/hieutt/.local/share/uv/tools/babeldoc/` → **0.6.4**. Đây là bản
  engine `babeldoc` của app thật sự chạy (`BabeldocRunner(executable="babeldoc")`).
- `babeldoc 0.2.33` nằm **bên trong tool env của pdf2zh**, là dependency bắc cầu của
  `pdf2zh v1.9.11`. pdf2zh chỉ dùng nó khi được truyền flag `--babeldoc`; `Pdf2zhRunner` không bao
  giờ truyền flag đó. Bản 0.2.33 là **code chết** với pipeline này.

Chi tiết chuỗi truy vết (5 bước, có lệnh và file:dòng) ở Architecture.md §6.22.1 bảng V-1…V-5.

**Bài học đáng giữ**: nghi vấn version của PM là **đúng quy trình** dù kết luận là báo động giả.
Chi phí để bác bỏ nó: ~10 phút. Chi phí nếu nó đúng mà không ai kiểm: toàn bộ §6.22 xây trên source
của một bản không chạy. Đây đúng là thứ R5-05 sinh ra để mua.

**Một đính chính thật sự có ích rơi ra từ đây**: B9-05 ghi nguồn là `IL/midend/typesetting.py`.
Đường dẫn đó **không tồn tại** trong 0.6.4 — bản 0.6.4 là
`babeldoc/format/pdf/document_il/midend/typesetting.py`, còn layout `babeldoc/document_il/midend/`
(không có tầng `format/pdf/`) lại đúng là layout của **0.2.33**. Không suy ra được là B9-05 đã đọc
nhầm cây source (nội dung kết luận của nó verify lại vẫn đúng, xem BL4.2) — nhiều khả năng chỉ là
ghi tắt đường dẫn. Nhưng đúng bằng cách ghi tắt kiểu này mà một trích dẫn nguồn mất khả năng kiểm
chứng lại. **Trích dẫn nguồn phải là đường dẫn dán được vào `sed -n`, không phải đường dẫn gợi
nhớ.**

### BL4.2. Verify lại B9-05: khớp, nhưng cơ chế "drop" khác với hình dung — và chính chỗ khác đó là lời giải

Đọc lại trực tiếp `typesetting.py` (1.682 dòng) của đúng bản 0.6.4. Cả 3 vế của B9-05 đều **đúng**
(bảng đối chiếu từng vế ở §6.22.2). Nhưng B9-05 mô tả drop như một hành động — "bỏ hẳn đoạn". Thực
tế **không có lệnh drop nào cả**:

`render_paragraph()` **xoá trắng** `paragraph.pdf_paragraph_composition = []` *trước* khi typeset
lại (`typesetting.py:1277`), rồi chỉ ghi nội dung trở lại khi tìm được scale mà mọi unit vừa khung
(`:986-1002`). Không scale nào vừa → composition **ở nguyên trạng thái rỗng**. Đoạn văn không bị
"bỏ" — nó bị **quên ghi lại**.

Khác biệt này nghe như chuyện chữ nghĩa, nhưng nó quyết định toàn bộ thiết kế: một hành động "drop"
thì phải đi tìm chỗ babeldoc gọi hàm drop (không có). Một **trạng thái** "composition rỗng nhưng
`unicode` vẫn còn bản dịch" thì quan sát được ở bất kỳ điểm nào sau typesetting — và hoá ra chính
babeldoc cũng đang kiểm tra đúng trạng thái đó ở `pdf_creater.py:831`.

Hai điều nữa B9-05 không nêu, ghi lại để lần sau khỏi đọc lại:
- Trước khi bỏ cuộc, babeldoc còn **nới rộng chính cái box** (xuống dưới, rồi sang phải) vào vùng đã
  kiểm tra là trống, và cập nhật `paragraph.box` theo (`:1020-1056`). Nên "không vẽ ra ngoài box"
  đúng theo nghĩa "box cuối cùng", không phải "box ban đầu".
- Vòng giảm scale **chỉ chạy quá một vòng khi `paragraph.debug_id` khác rỗng** (`:1008-1009`). Suýt
  kết luận nhầm rằng toàn bộ cơ chế bóp font là code chết ngoài chế độ debug — phải đi kiểm
  `paragraph_finder.py:500` mới thấy `debug_id=generate_base58_id()` được gán cho **mọi** paragraph,
  không phụ thuộc `--debug`. Đây là loại giả định mà nếu tin theo tên biến (`debug_id` → "chỉ có khi
  debug") thì sai hoàn toàn.

### BL4.3. Có tín hiệu quan sát được — hai tín hiệu, và lý do không chọn cái dễ thấy hơn

Câu hỏi Bước 2 có đáp án **CÓ**. Nhưng hai ứng viên không ngang nhau:

**Tín hiệu 1 — log stdout.** `pdf_creater.py:832` gọi `logger.error("Unable to export paragraphs
that have not yet been formatted: {paragraph}")` đúng khi trạng thái ở BL4.2 xảy ra. Đã đo thật
(chạy bằng interpreter của chính tool env babeldoc, dựng lại `basicConfig` + logger name thật, tách
2 luồng): ra **stdout**, stderr 0 byte — cùng đường với tín hiệu rate-limit mà 6.12/6.14.3 đã dùng.

Nhưng đo tiếp thì lộ giới hạn: ở 80 cột, rich bẻ dòng **cắt cả giữa token**, xé câu sentinel thành
`Unable to` / `export paragraphs that have not yet` / `been formatted:`. Neo theo cụm từ sẽ hỏng —
đúng lý do 6.14.3 chọn neo `RATE_LIMIT_LINE_RE` vào **một token duy nhất**. Ở `COLUMNS=200` (giá
trị `BabeldocRunner` **đã set sẵn** từ trước, `babeldoc_runner.py:374`) thì cụm sentinel nằm trọn
một dòng, nhưng `repr(paragraph)` phía sau vẫn wrap và vẫn cắt giữa từ tiếng Việt. Và quan trọng
nhất: **log không chứa số trang**.

Còn một cạm bẫy nữa chỉ lộ ra khi đọc `main.py`: `speed_up_logs()` (`:944`) thay handler bằng
`QueueHandler` trên một `EvictQueue(1000)` **tự vứt bản ghi khi đầy** (`:895-903`). Nghĩa là đếm
theo stdout có thể **thấp hơn thực tế** khi log dồn — một cơ chế đo im lặng bỏ sót chính thứ nó
được giao đo.

**Tín hiệu 2 — shim.** Repo này đã có `src/babeldoc_shim/sitecustomize.py` (744 dòng, dựng cho Bug
#7 và Bug #10): meta-path finder + loader bọc từng module, version gate `0.6.4`, fail-safe rollback
độc lập từng patch. Bọc `PDFCreater.create_render_units_for_page` cho ta **object `page`** — tức số
trang — cùng toàn bộ `paragraph` nguyên vẹn, có cấu trúc, không qua rich.

**Chốt: shim làm nguồn chính, stdout làm nguồn đối chiếu.** Không bỏ hẳn stdout: khi hai con số lệch
nhau, cái lệch đó là cảnh báo về **chính cơ chế đo** (§6.22.6), và đó là thứ Bug #5 đã dạy — một
đường ống không tự kiểm tra thì hỏng im lặng.

**Điều tự đặt giới hạn cho mình**: patch mới **chỉ đọc, không sửa** hành vi typeset — khác hẳn 4
patch hiện có. Ghi thành ràng buộc thiết kế trong §6.22.4 chứ không chỉ là ý định: nếu
implementation cần sửa dữ liệu mới lấy được tín hiệu thì thiết kế sai, dừng và escalate. Bug #9 xảy
ra chính vì một bước "vô hại" hoá ra có ghi.

### BL4.4. Không tái dùng bảng `overflow_reports` — dù đề bài mở đường cho việc đó

Cân nhắc rồi và **bác**. 5/9 field của `OverflowReport` babeldoc không cho biết:
`font_size_original`, `font_size_final`, `scaling_applied`, `still_overflow`, `block_index`. Riêng
`scaling_applied` là chỗ bẫy nhất: có vẻ ánh xạ được sang `paragraph.scale`, nhưng `paragraph.scale`
**chỉ được gán khi apply thành công** (`typesetting.py:989`) — nên ở đúng ca drop nó luôn là `None`.
Ghi `None` vào thì cột vô nghĩa; ghi `0.1` (đoán rằng nó đã bóp tới sàn) thì **bịa số đo**.

Và `still_overflow` thì sai ngữ nghĩa ở mức khái niệm: babeldoc **không tràn**, nó **bỏ**. Nhét dữ
liệu của một hiện tượng vào lược đồ của hiện tượng khác chỉ để khỏi tạo bảng mới là cách tạo ra dữ
liệu *trông như đã đo*.

Chọn `layout_qa_findings` + `persist_findings()` — đúng "nơi đặt tự nhiên" mà B9.7 đã dự đoán từ
2026-09-08, `detail` là JSON tự do nên chứa được đúng những gì đo được, không hơn không kém, và
**không cần migration**.

Hệ quả kèm theo, ghi để khỏi tưởng là bug: `OverflowReport.page_number` đang là **0-based**
(`font_shrink.py:194` dùng `page.number` của PyMuPDF) còn `LayoutQaFinding.page_number` là
**1-based** (`layout_qa.py:403`). Thiết kế này theo 1-based cho khớp bảng nó ghi vào. Thống nhất 2
bảng là việc riêng, đụng dữ liệu lịch sử nhánh pdf2zh — **không** gộp vào đây.

### BL4.5. Ba trạng thái, không phải hai

Điểm dễ hỏng nhất của cả thiết kế, tách riêng để không bị đọc lướt: khi không có record nào, có
**hai** khả năng hoàn toàn khác nhau — *"đã đo, không có đoạn nào bị bỏ"* và *"không đo được"*
(shim tắt, version babeldoc khác 0.6.4, patch fail). Gộp hai cái đó thành "0 drop" là tái tạo lại
Bug #5 ở quy mô nhỏ: hệ thống báo tin tốt trong khi thực ra nó đang mù.

Vì vậy shim ghi một dòng `header` ngay khi patch áp thành công, và trạng thái thiếu header sinh ra
finding riêng `babeldoc_drop_report_unavailable` (`severity="major"`). Ba trạng thái, đối xử khác
nhau — bảng ở §6.22.6.

### BL4.6. Trạng thái verify và điều CHƯA có bằng chứng

| Claim | Mức | Nguồn |
|---|---|---|
| babeldoc engine của app = 0.6.4; 0.2.33 không bao giờ chạy | tự verify | §6.22.1 V-1…V-5 (lệnh + file:dòng) |
| Cơ chế drop = composition rỗng, không có lệnh drop | tự verify (đọc source 0.6.4) | `typesetting.py:1277`, `:986-1002`, `:1064-1076` |
| `logger.error` ở `pdf_creater.py:832` đúng là điều kiện drop | tự verify | `pdf_creater.py:814-836` |
| Log ra **stdout**, không phải stderr | **đo thật** | chạy probe bằng interpreter tool env babeldoc, tách 2 luồng: stderr = 0 byte |
| Rich bẻ dòng cắt giữa token ở 80 cột; sentinel nguyên vẹn ở `COLUMNS=200` | **đo thật** | cùng probe, chạy 3 bề rộng (mặc định / 200 / 400) |
| `page.page_number` = chỉ số 0-based của tài liệu **gốc** tại thời điểm hook | tự verify | `pdf_creater.py:1708` (`pdf[page.page_number].xref`) + thứ tự `:1465-1466` chạy **trước** `:1489-1502` (xoá trang) |
| Hook chạy đúng 1 lần/trang, bản dual không render lại | tự verify | `pdf_creater.py:1465-1466`, `:1559-1574` |
| **Tồn tại một đoạn bị drop thật trong tài liệu đang dùng** | ⚠️ **CHƯA VERIFY** | chưa chạy babeldoc E2E; mọi kết luận trên đều từ đọc source + đo log, **chưa từ một ca drop quan sát được** |

Dòng cuối là giới hạn thật của hạng mục này, không phải thủ tục. Nếu E2E (§6.22.9) không tạo được
ca drop nào, **không** kết luận là thiết kế sai — nhưng phải trình Hiếu quyết giữa: dựng tài liệu ép
drop (khung hẹp + câu dài), hay đóng BL-04 ở mức *"cơ chế đã có, chưa quan sát được ca thật"*.
Không tự chọn hộ.

### BL4.7. Final Decision

1. **BL-04 là khả thi — KHÔNG đóng ở trạng thái "không khả thi".** babeldoc có tín hiệu quan sát
   được, ở hai mức độ tin cậy khác nhau.
2. **Nguồn chính**: shim observer bọc `PDFCreater.create_render_units_for_page`, ghi JSONL sidecar.
   **Nguồn đối chiếu**: đếm sentinel trên stdout. Lệch nhau → finding riêng.
3. **Ghi vào `layout_qa_findings`** (`check_type="babeldoc_paragraph_drop"`), **không** vào
   `overflow_reports`.
4. **Không đụng một dòng nào** vào quyết định Bug #9: `needs_font_shrink` giữ nguyên, khối
   `OverflowReport` hiện có giữ nguyên (audit R8-01 đầy đủ ở §6.22.7).
5. **Capability mới** `reports_own_paragraph_drops: ClassVar[bool]` trên từng runner (R8-03), có
   guard `isinstance(..., bool)` như `_needs_font_shrink` — vì `AsyncMock(spec=...)` copy TÊN chứ
   không copy GIÁ TRỊ, thiếu guard thì test chạy nhầm nhánh mà vẫn PASS.
6. **Gate release**: golden file cho test **phải sinh từ lần chạy thật**, không viết tay (Protocol 5
   mục 3). Live E2E mở PDF ra đối chiếu bằng mắt, không chỉ tin số đếm (R6-03).

---

## BL-04 — Final Decision LẦN 2, sau REJECT của Domain Expert (Tech Lead, 2026-09-11)

**Bối cảnh**: Domain Expert (Protocol D, lượt 1/2) đã tự đọc lại source babeldoc 0.6.4 **độc lập**
— không tin lại trích dẫn của tôi — và xác nhận cơ chế cốt lõi (composition bị xoá trắng,
`all_units_fit`, `paragraph.scale is None` ở ca drop, hook chạy đúng 1 lần/trang) là **ĐÚNG**, nhưng
**REJECT** thiết kế với 4 điểm blocking F1–F4 + 5 điểm nên-sửa F5–F9 + 1 điểm đổi mục tiêu E2E.
Note đầy đủ: `docs/expert-notes/domain-expert-20260911-bl04-babeldoc-overflow.md`.

Đây là **lượt sửa 2/2** theo giới hạn Protocol D. Hợp đồng hiện hành đã cập nhật tại
`docs/Architecture.md` §6.22 (Protocol C.1 — mục này chỉ ghi *vì sao*, không lặp lại spec).

**Nguyên tắc tôi tự áp cho lượt này**: tôi **không** kế thừa trích dẫn của Domain Expert như sự thật
(đúng như DE đã không kế thừa của tôi). Mọi file:dòng dưới đây tôi đã tự mở lại. Chỗ nào tôi đo thêm
ra số khác hoặc sắc thái khác, tôi ghi rõ.

### BL4.8. F1 — Chồng lấn chunk: từ "lỗi tôi không nhìn thấy" thành "tính chất của hệ, phải khoá lại"

**Đã tự verify lại, không tin lại**: `chunking.py:75` (`start = end - overlap + 1`) và `:60-61`
(`overlap_start = start`, `overlap_end = start + overlap - 1`) ⇒ chunk chồng nhau 2 trang.
`chunk_merge.py:85-91` (`actual_start = chunk.overlap_end + 1`) ⇒ bản render 2 trang đầu của mọi
chunk sau chunk đầu **bị vứt**. `typesetting.py:919-935` tôi đọc trực tiếp: `all_paragraphs` gom từ
**mọi trang của `document` trong chính lần gọi đó**, `statistics.multimode(all_scales)`, rồi hạ mọi
`optimal_scale > mode_scale` xuống mode. DE đúng cả 3 vế.

**Vì sao tôi trượt điểm này ở lượt 1**: §6.22.7 (audit Protocol 8) của tôi CÓ liệt kê
`merge_chunk_pdfs` — và tôi đã trả lời **"không liên quan"**, với lý do "số trang trong report đã là
số trang tài liệu nguồn". Lý do đó **đúng về đơn vị đo** nhưng trả lời nhầm câu hỏi: R8-01 hỏi *"bước
cũ này giải quyết vấn đề gì, biến thể mới có vấn đề đó không"*, còn tôi trả lời *"bước cũ có làm sai
đơn vị đo của tôi không"*. `merge_chunk_pdfs` tồn tại để **vứt bỏ trang chồng lấn** — và đó chính là
vấn đề của tôi. Tôi đã chạy đúng thủ tục R8-01 mà vẫn ra kết luận sai vì trả lời sai câu hỏi. Ghi
lại đây vì đó là chế độ hỏng của Protocol 8 mà bối cảnh Bug #9 chưa mô tả: **không chỉ "quên liệt kê
bước cũ", mà còn "liệt kê rồi nhưng trả lời một câu hỏi dễ hơn"**.

**Quyết định**: giữ kết quả của chunk **đứng trước** (chunk có bản render sống sót vào file cuối),
loại mọi record `page_number < overlap_end + 1` của chunk `N > 0`.

**Điều tôi bổ sung thêm mà DE chưa nêu — và nó là thứ khiến quyết định này an toàn**: lọc như vậy
**không tạo lỗ hổng quan sát**, vì các dải sống sót **phủ kín và rời nhau** trên `[1, total_pages]`,
và mỗi chunk quan sát cả dải `[page_start, page_end]` ⊇ dải sống sót của chính nó. Nên mọi trang vật
lý của file cuối vẫn được đo **đúng một lần, bởi đúng lần chạy đã tạo ra trang đó**. Không có điều
này thì "lọc bớt record" nghe như tự bịt mắt; có nó thì đây là phép chọn đúng vật thể để đo. Đã viết
vào §6.22.5.1.

**Hàm dùng chung `surviving_page_range()`** đặt tại `src/core/chunking.py` (nơi định nghĩa luật chồng
lấn), dùng structural typing (`Protocol`) để hợp cả `ChunkPlan` lẫn `models.Chunk` mà **không** kéo
import model vào `core/chunking.py`.

**Một bất biến DE không nêu, tôi phát hiện khi đọc call site**: `chunk_merge` phân biệt chunk đầu
bằng `position` (chỉ số trong list đã sort), còn `_process_chunk` chỉ có `chunk.chunk_index`. Hai thứ
này **chỉ trùng nhau khi merge được gọi với đủ chunk**. Hiện tại đúng (`job_orchestrator.py:693`
truyền nguyên `chunks`), nhưng đó là phụ thuộc vào code khác ⇒ tôi **không** ép hàm chung tự suy
`is_first` từ `overlap_end is not None` (làm vậy sẽ âm thầm đổi hành vi merge trong ca chunk 0 vắng
mặt, hướng **mất trang**), mà giữ `is_first_in_merge` làm tham số tường minh **cộng** một
`logger.warning` trong `merge_chunk_pdfs` khi `position != chunk.chunk_index`. Bất biến được **kiểm**
chứ không được giả định.

**KHÔNG sửa lỗi cùng loại ở nhánh pdf2zh** (`job_orchestrator.py:1901` cũng đếm 2 lần trên ~20
trang/cuốn). DE nói "gần như miễn phí nếu đã tách hàm chung" — đúng về chi phí code, nhưng §6.22.7 đã
chốt "không đụng một dòng nào vào nhánh pdf2zh/Bug #9", và đổi số row `overflow_reports` là đổi dữ
liệu lịch sử + kéo theo test hồi quy của một hạng mục khác. → backlog **BL-07**.

### BL4.9. F2 — `header` chứng minh "patch đã cài", không chứng minh "đã quan sát"

DE đúng, và đúng ở chỗ đau: tôi đã tự nhận trạng thái 3 ("không đo được") là *"điểm dễ sai nhất của
cả thiết kế"* rồi lại xây nó trên một bằng chứng chứng minh nhầm thứ. Header được ghi trong
`_PatchingLoader.exec_module` — **lúc import module**, trước khi render trang nào.

**Đã sửa**: shim ghi thêm 1 record `type="page"` cho **mỗi** trang đi qua hook; runner đối chiếu
`observed_pages` với `expected_pages`; ba trạng thái thành **bốn** (thêm `babeldoc_drop_report_incomplete`,
`severity="major"`). Parser không giả định vị trí/số lượng dòng `header`, và đếm
`malformed_line_count`.

Ta biết trước `expected_pages` là **con số xác định, kiểm được** — không phải suy đoán: `create_il()`
lọc `docs.page` theo `should_translate_page(page.page_number + 1)` (`il_creater.py:1347-1353`, tôi đã
tự mở lại), và runner luôn truyền `page_range=f"{chunk.page_start}-{chunk.page_end}"`
(`job_orchestrator.py:1806`).

**Tôi thêm một thứ DE không nêu**: `page.dropped_count` làm **checksum chéo trong chính file** — số
record `drop` của mỗi trang phải khớp con số trang đó tự khai. Một dòng bị xé/mất khi ghi sẽ lộ ra ở
`detail["checksum_mismatch_pages"]` thay vì âm thầm làm giảm số finding. Chi phí: 1 field.

**Về đa process**: tôi đã tự verify lại thay vì chép nhận định của DE. `main.py:951` đặt
`spawn`; `pdf_creater.py` chỉ tạo process con tại `subset_fonts_in_subprocess` (`:1220`, gọi ở `:1216`
nhánh debug và `:1479`) — bước đó không render paragraph. Vòng render `:1465-1466` chạy ở process
chính ⇒ **chỉ process chính ghi `page`/`drop`**, nhưng **có thể nhiều dòng `header`**. Đã viết vào
§6.22.4 ("Ai ghi file này") kèm `pid` trong header.

### BL4.10. F3 — Thiết kế này chỉ phủ 1 trong ≥3 kênh mất chữ. Đây là điểm nặng nhất.

DE **đo thật**, không suy đoán: trang 19 mất `'History of Pâtisserie in France'`, trang 31 mất
`'A Life and Career in the Pastry Kitchen'`, 52/418 trang có chữ dọc, ký tự dọc 2.303 → 1.327. Tôi tự
mở `il_creater.py` và xác nhận cơ chế: `:969-970` (`aw_font_id is None` → `return`) và `:972-974`
(góc ngoài `[-0.1,0.1] ∪ [89.9,90.1]` → `return`). Ký tự bị loại ở đây **không bao giờ** thành
`PdfCharacter` ⇒ không thuộc paragraph nào ⇒ hook của tôi mù hoàn toàn, và sentinel ở
`pdf_creater.py:831` cũng không kêu.

**Tôi kiểm thêm một vế DE không kiểm, và nó làm vấn đề nặng hơn chứ không nhẹ đi**: có thể phản bác
rằng "kênh (2) đã có `overlay_rotated_text` lo". Tôi đã tự tra: `babeldoc_rotated_text_overlay` mặc
định `True` (`config.py:208`), `.env` **không** override, và bước overlay có từ commit `b9c8952`
ngày **2026-09-07** — tức **trước** job `1ee1fdee` (2026-09-09). Vậy overlay **đã bật và đã chạy**,
mà trang 19/31 vẫn mất chữ **và** `layout_qa_findings` của job đó = **0 row**. ⇒ kênh (2) hiện
**không** được phủ kín, và khi không phủ được nó cũng **không** luôn để lại cờ. Phản bác đó chết.

**Đã sửa (phần bắt buộc)**:
- Đổi tên: `babeldoc_paragraph_drop` → **`babeldoc_paragraph_drop_unfit`**, **cộng** bắt buộc
  `detail["cause"] = "typeset_unfit"` (tên có thể bị ai đó đổi, `cause` khoá ngữ nghĩa lại).
- Đổi tiêu đề §6.22 + thêm khối trích dẫn phạm vi ngay dưới tiêu đề.
- §6.22.6.1 mới: bảng 3 kênh có nguồn xác thực từng dòng + toàn bộ số liệu đo của DE.
- **Ràng buộc hình thức**: hệ thống **không được phép** phát ra chuỗi "0 drop" trần. Định dạng bắt
  buộc luôn kèm mẫu số (`observed=42/42`) **và** câu PHAM VI. Đây là chỗ tôi cứng rắn hơn đề xuất
  của DE: DE đề nghị "thêm 1 đoạn văn vào §6.22.6"; một đoạn văn trong tài liệu 7.900 dòng không
  ngăn được ai đọc log thấy `drops=0` rồi kết luận "sạch". Ràng buộc phải nằm trong **định dạng
  output**, không chỉ trong tài liệu.

**Phần (b) — đếm ký tự bị loại ở `on_lt_char`: QUYẾT ĐỊNH KHÔNG LÀM trong BL-04.** Lý do, theo đúng
R8-02 (deny-by-default) chứ không phải để né việc — tôi đã khảo sát 3 cách và bác từng cách **có
nguồn**:

1. *Patch `on_lt_char` và tự tính lại `get_rotation_angle`*: phải **chép predicate của babeldoc**
   (2 khoảng + hằng số) thành nguồn sự thật thứ hai, đặt trên hàm **nóng nhất của parser** (~100k lời
   gọi cho 1 chunk 42 trang). Project này đã có 2 vết sẹo từ đúng khuôn "hai bản sao rồi lệch nhau"
   (Bug #5, Bug #9).
2. *Đếm theo kết quả (`len(_page_valid_chars_buffer)` trước/sau)*: tôi đã đọc `_collect_valid_char`
   (`il_creater.py:1122-1157`) — nó **còn tự loại thêm** theo `unicodedata.category ∈ {Cc,Cs,Co,Cn}`,
   chuỗi chứa `"(cid:"`, và `font_mapper.has_char()`. Những ca đó **không** phải mất chữ do góc xoay.
   Counter không tách được 2 nguyên nhân = counter sẽ bị bỏ qua sau vài lần báo động giả — đúng chế
   độ hỏng mà chính F1 cảnh báo.
3. *Đếm ký tự IL tại hook đang có*: **sai điểm đo** — hook chạy **sau** dịch, ký tự ở đó là bản VI,
   không so được với nguồn EN.

Thay vì để backlog rỗng, tôi ghi luôn **ứng viên thiết kế đã khảo sát** vào BL-08:
`ILCreater.on_page_end` (`il_creater.py:641-664`) — **1 lời gọi/trang**, đọc `_page_valid_chars_buffer`
trước khi nó bị clear, so với số ký tự trang nguồn qua PyMuPDF. Kèm **điều kiện tiên quyết**: phải
**đo trước** biên độ nhiễu (pdfminer vs PyMuPDF, cộng nhiễu `_collect_valid_char`) rồi mới đặt
ngưỡng. Cấm đặt ngưỡng từ suy đoán.

⚠️ **Rủi ro còn lại tôi KHÔNG che**: sau BL-04, một chunk vẫn có thể mất chữ qua kênh (2)/(3) mà hệ
thống **không** phát ra cảnh báo nào của riêng kênh đó. Thứ BL-04 mua được là hệ thống **không còn
nói dối rằng nó đã kiểm hết** — mọi con số đều đi kèm phạm vi. Đó là một mức bảo đảm yếu hơn "phát
hiện mọi mất chữ", và tôi ghi rõ mức đó thay vì để người đọc tự suy.

### BL4.11. F4 — Không ai đọc `layout_qa_findings`. Câu "đã có UI/QA đọc" là tôi viết sai.

Tôi đã tự chạy lại `grep -rln "LayoutQaFinding\|layout_qa_finding" src/ web/ scripts/ tests/`: 3
writer (`rotated_text_overlay.py`, `layout_qa.py`, `mineru_det_probe.py`), phần còn lại là model/
export/test. **0 route trong `src/api/`, 0 file trong `web/`.** DE đúng, tôi sai. Câu đó lọt vào
Architecture.md vì tôi suy từ *"bảng này sinh ra cho QA soi tay"* (đúng ý định) sang *"đã có UI/QA
đọc"* (sai sự thật) — đúng loại claim mà 6 tháng sau có người sẽ dựa vào mà không kiểm lại.

**Quyết định — chọn (a) + mở (b) thành backlog, KHÔNG chọn (c)**:
- BL-04 **giao** đường đọc tối thiểu: log R-1 (1 dòng/chunk, `WARNING` khi có drop hoặc trạng thái
  3/4), log R-2 (1 dòng/job tại Bước 10 trước `job.status = "completed"`), và câu SQL dán được cho QA
  trong `test-report.md`.
- BL-04 **không giao** route API / badge UI / cột mới trong `JobDetail` → backlog **BL-09** (đã ghi
  sẵn điểm sửa: `jobs.py:702-717`, `_to_detail()` hiện là hàm thuần từ 1 row `Job` nên phải thêm 1
  query).
- **Giới hạn đã biết, ghi thẳng vào hợp đồng**: cảnh báo chỉ tới được **người đọc log server**, chưa
  tới được người dùng qua UI.

Tôi không chọn (c) ("ghi DB rồi thôi, chỉ cần trung thực") vì số liệu của DE làm (c) mất giá trị:
**1 row/cuốn 418 trang**. Đúng như DE nhận xét ở D4 — *chính vì hiếm* mà không ai soi tay ra được, và
*chính vì hiếm* mà khi nó xảy ra thì không cơ chế nào khác bắt. Một cờ hiếm nằm trong bảng không có
reader thì thực tế bằng 0 row.

### BL4.12. F5–F9 — điểm nên-sửa: nhận 5/5, không bỏ điểm nào

| # | Nội dung | Xử lý |
|---|---|---|
| F5 | Mismatch sentinel phải **một chiều** (EvictQueue làm sentinel ≤ structured theo thiết kế) + nói rõ 2 con số **không độc lập** (cùng call site: `logger.error` ở `pdf_creater.py:831` nằm trong `render_paragraph_to_char`, được gọi từ chính `create_render_units_for_page` ở `:852`) | **Nhận**. Đổi `!=` → `>`; ghi rõ giới hạn + số liệu "1 ca drop/418 trang ⇒ phép đối chiếu này gần như luôn `0 == 0`, đừng đầu tư thêm" |
| F6 | Severity phải đăng ký ở `_SEVERITY_BY_CHECK`, không hardcode; danh sách `check_type` của tôi **thiếu 2** giá trị | **Nhận**. Tôi tự mở `layout_qa.py:76-84`: đúng là 7 khoá, tôi liệt kê 5 — thiếu `rotated_text_overlay_flag` và `rotated_text_scan_unsupported`, mà cái đầu lại là giá trị **duy nhất** đang thực sự có trong DB. Đã đính chính + thêm 3 khoá mới của BL-04 vào chính dict đó + thêm test `test_severity_from_registry` |
| F7 | Lý do "400 ký tự cho ghi nguyên tử `O_APPEND`" **sai kỹ thuật** | **Nhận, và tự đo lại thay vì chép con số của DE**: DE ghi `PIPE_BUF` "512B"; tôi chạy `os.pathconf(".", "PC_PIPE_BUF")` trên chính máy này → **512** (Darwin). Đúng. 400 ký tự VI với `ensure_ascii=False` ~1.200 byte ⇒ vượt xa. Chọn phương án 1 của DE: **bỏ lý do sai, giữ 400 với lý do thật** ("đủ để QA nhận ra đoạn, giữ file nhỏ"), và ghi rõ 400 **không** phải bất biến kỹ thuật |
| F8 | `optimal_scale == 0.1` là **marker chẩn đoán** | **Nhận**. Tự verify lại `typesetting.py:1076` (trả `min_scale` khi không fit) + `:929-935` (chỉ **hạ** giá trị lớn hơn mode ⇒ 0.1 sống sót). Đã viết vào cột "Ghi chú" của schema: `== 0.1` ⇒ "đã biết không fit từ bước preprocess"; khác 0.1 ⇒ "từng fit ở preprocess nhưng drop ở lần typeset thật" |
| F9 | Bước dedupe giải quyết vấn đề không tồn tại, và chỉ có thể gây hại (`generate_base58_id(length=5)` có thể trùng ⇒ gộp nhầm) | **Nhận, bỏ hẳn dedupe.** Ghi rõ trong schema rằng `debug_id` **không** phải khoá dedupe (ngẫu nhiên mỗi lần chạy ⇒ vô dụng xuyên chunk; 5 ký tự ⇒ có thể gộp nhầm trong cùng trang). Thứ cần khử là chồng lấn — đã có bộ lọc F1 |
| A9 | Sidecar **phải** nằm trong `chunk_output_dir` vì `_call_translator` `rmtree` mỗi attempt | **Nhận**, và tôi tự verify lại `job_orchestrator.py:1801-1802`. Đã nâng từ "phụ thuộc tình cờ" thành **ràng buộc ghi trong hợp đồng** (§6.22.4 "Vị trí file") + thêm 1 dòng vào bảng audit R8-01 §6.22.7 |

### BL4.13. Gate E2E: đổi mục tiêu từ chunk 0 sang **trang 230 / chunk 5 (`--pages 199-240`)**

Đây là đóng góp có giá trị cao nhất của lượt phản biện, và nó **bác một giả định của tôi bằng dữ
liệu**: tôi đề xuất chunk 0 vì đó là chunk QA đã quen dùng cho Bug #8/#9 — tức tôi chọn theo *tiện*,
không theo *có ca drop hay không*. DE đo cả 418 trang và cho thấy chunk 0 **không có ca drop kiểu (1)
nào** (ứng viên `src > 300` ký tự, tỉ lệ `< 0.75`: **0**). Gate đó sẽ ra "0 drop" và **không chứng
minh được gì** — một gate xanh vô nghĩa còn tệ hơn không có gate, vì nó tạo niềm tin sai.

Ca thật: **trang 230**, sidebar EN 614 ký tự trong khung 271 × 243 pt, font 12 pt, tỉ lệ ký tự ngang
2318 → 1440 = **0.62** (6 trang "mất nhiều nhất" còn lại của cả cuốn đều 0.84–0.88 và đã kiểm là
không block nào vắng mặt — đó là co ngót dịch bình thường). Bằng chứng là **đọc toàn văn** output
trang 230, không phải heuristic.

**Bẫy đã viết vào §6.22.9 bằng chữ đỏ**: KHÔNG được cắt 2-3 trang quanh 230 cho rẻ. `preprocess_document`
ép scale theo mode của **toàn bộ tập trang trong chính lần gọi đó** ⇒ tập trang khác ⇒ ca drop có thể
biến mất. Phải chạy đúng `--pages 199-240` (42 trang). Đây cũng chính là lý do kỹ thuật của F1 — cùng
một cơ chế, hai hệ quả khác nhau.

Assertion gate: `observed_pages == set(range(199,241))` · có record `page_number_1based == 230` ·
`text_excerpt` là bản dịch VI của đoạn feuilletage · **mở PDF trang 230 xác nhận đoạn đó thật sự
vắng** (R6-03) · **không** có finding nào ở trang 199-200 (chứng minh bộ lọc F1 chạy trên dữ liệu
thật) · dòng log R-1 đúng định dạng có `observed=42/42` + câu PHAM VI.

Số test unit/integration: 5 → **10** (thêm `test_drop_report_incomplete`,
`test_overlap_pages_filtered`, `test_surviving_range_shared`, `test_sentinel_mismatch_one_way`,
`test_severity_from_registry`).

### BL4.14. Final Decision lần 2 — thay thế BL4.7 ở các điểm mâu thuẫn

1. Giữ nguyên mọi kết luận của BL4.7 **trừ** các điểm dưới.
2. `check_type` chính đổi thành **`babeldoc_paragraph_drop_unfit`** + bắt buộc
   `detail["cause"] = "typeset_unfit"`; severity **tra từ `_SEVERITY_BY_CHECK`**, không hardcode.
3. **Bốn** trạng thái, không phải ba (thêm `babeldoc_drop_report_incomplete`); bằng chứng "đã quan
   sát" là record `type="page"`, **không** phải dòng `header`.
4. **Bắt buộc lọc dải trang sống sót** bằng `surviving_page_range()` dùng chung với
   `merge_chunk_pdfs`; **bỏ hẳn** dedupe theo `debug_id`.
5. Schema sidecar lên **`babeldoc_drop_report/v2`**; sidecar **phải** nằm trong `chunk_output_dir`.
6. Mismatch sentinel **một chiều** (`>`), có ghi rõ giới hạn của phép đối chiếu.
7. BL-04 giao **đường đọc tối thiểu bằng log** (R-1/R-2/R-3); **không** giao UI. Giới hạn này ghi
   thẳng vào hợp đồng.
8. Gate E2E: **trang 230 / chunk 5 / `--pages 199-240`**, không phải chunk 0.
9. Backlog mở mới: **BL-07** (lỗi chồng lấn cùng loại ở nhánh pdf2zh), **BL-08** (đo kênh (2)/(3) —
   chữ bị lọc ở `on_lt_char`, kèm ứng viên thiết kế `ILCreater.on_page_end` và điều kiện tiên quyết
   phải đo nhiễu trước), **BL-09** (surfacing finding lên API/UI).

**Điều tôi KHÔNG tự tin đã giải quyết triệt để, nói thẳng thay vì mập mờ** (đây là lượt 2/2 theo
Protocol D, nên phần này là để PM quyết chứ không phải để tôi tự trấn an):

- **F3 chỉ được giải quyết ở vế "trung thực", không ở vế "phủ kín"**. Sau BL-04, mất chữ qua kênh
  (2)/(3) vẫn có thể xảy ra mà không có cảnh báo riêng nào — bằng chứng sống là trang 19/31 của job
  `1ee1fdee`. Tôi đã cân nhắc và **chủ động từ chối** làm counter trong BL-04 (lý do ở BL4.10). Nếu
  Hiếu/PM đánh giá rủi ro "mất tiêu đề chương mà không ai biết" là không chấp nhận được ở mức hiện
  tại, thì **BL-08 phải được ưu tiên ngay sau BL-04**, chứ không phải nằm chờ trong backlog. Đó là
  quyết định về khẩu vị rủi ro, không phải quyết định kỹ thuật — tôi không tự quyết hộ.
- **F1 đúng về logic nhưng chưa được kiểm trên dữ liệu thật** — assertion số 5 của gate E2E (không có
  finding ở trang 199-200) là lần đầu tiên nó được kiểm sống. Trước đó nó vẫn là lập luận.
- `docs/Architecture.md` sau lượt này là **7.911 dòng**, sát trần ngân sách 8.000 của Protocol C.3.
  Lượt sửa tiếp theo chạm §6.22 gần như chắc chắn sẽ vượt trần ⇒ PM nên lên lịch rotate/tách trước,
  đừng để validator cảnh báo rồi mới xử lý.

---

### BL4.15. Sửa theo điều kiện Domain Expert xác nhận lần 2 (X1/X6/X7, kèm cả X2–X5/X8)

**Bối cảnh**: Domain Expert APPROVE thiết kế BL-04 ở lượt **2/2 Protocol D** (note đầy đủ:
`docs/expert-notes/domain-expert-20260911-bl04-babeldoc-overflow.md`, section "Xác nhận lần 2"),
**có điều kiện**. Mục này ghi những gì đã sửa. **Đây KHÔNG phải vòng phản biện mới** — không có
thiết kế nào bị lật, không gọi lại expert (đã dùng hết 2/2 lượt cho checkpoint này). Toàn bộ là
sửa tài liệu; **0 dòng code**.

Tôi **không kế thừa trích dẫn của Domain Expert**: mọi địa chỉ file:line dưới đây đã tự đọc lại
source thật ngày 2026-09-11 (gốc babeldoc 0.6.4:
`/Users/hieutt/.local/share/uv/tools/babeldoc/lib/python3.12/site-packages/babeldoc/`; gốc app:
repo này). Đúng nguyên tắc Domain Expert đã dùng ở lượt 2 — và nó lại có ích: nhờ tự grep tôi thấy
`grep -rn "run_layout_qa_gate" src/` thực ra trả về **1 dòng** (chính định nghĩa hàm), không phải
"0 kết quả" như note ghi; kết luận *dead code, 0 call site* thì đúng, chỉ câu chữ cần chính xác hơn
— đã viết lại theo bản tự đo.

#### X1 (bắt buộc) — `ILCreater` không chạy trong luồng dịch. Sai địa chỉ, đúng kết luận.

**Tự verify lại, khớp 100% với Domain Expert**: `high_level.py:902-910` parse bằng
`new_parser/native_parse.py`, và `native_parse.py:53, 57` dựng sink là **`ActiveILCreater`**
(`document_il/frontend/il_creater_active.py`). `grep -rn "ILCreater\|legacy_parse" <BD>` (bỏ
`ActiveILCreater`): `ILCreater` + `legacy_parse.start_parse_il` chỉ còn **một** người dùng thật là
`format/pdf/parse_only.py:5-6, 29` — entry point tách biệt, không nằm trên đường dịch. Phần còn lại
là khai báo `Protocol` (`pdfinterp.py:50`) và `converter.py`, mà `converter.py` cũng chỉ được
`legacy_parse` dùng.

**Kết luận kỹ thuật của §6.22 KHÔNG đổi** — `ActiveILCreater.project_native_char`
(`il_creater_active.py:1292-1300`) có predicate **y hệt** bản legacy (`aw_font_id is None` → return;
`rotation_angle` ngoài `[-0.1, 0.1] ∪ [89.9, 90.1]` → return). Nghĩa là kênh (2)/(3) vẫn nằm ngoài
tầm đo của §6.22, F2/F3 vẫn đứng. Chỉ **địa chỉ** sai.

Đây đúng là loại sai mà nhìn vào thì thấy vô hại (không bug hôm nay — BL-04 chỉ patch
`pdf_creater`, không đụng frontend) nhưng cái giá nằm ở **tương lai gần**: §6.22.6.1 đã ghi sẵn ứng
viên BL-08 là `ILCreater.on_page_end`. Người nhận BL-08 sẽ tin dòng đó và patch thẳng, được một
**no-op im lặng** — không lỗi, không log, và kết luận ngược hẳn sự thật: *"đo rồi, không ký tự nào
bị lọc"*. Cùng khuôn Bug #9 (hành động theo một trích dẫn không còn đúng ngữ cảnh), khác mỗi chỗ nó
chưa kịp xảy ra. Nên phải sửa **trước** khi Dev/người làm BL-08 bắt đầu.

Đã sửa **6 nhóm trích dẫn** trong §6.22 + **1 ngoài §6.22**:

| Vị trí | Cũ (dead) | Mới (luồng dịch thật) |
|---|---|---|
| §6.22 hộp "Phạm vi" | `ILCreater.on_lt_char` | `ActiveILCreater.project_native_char` |
| §6.22.6 trạng thái 3 | `il_creater.py:1347-1353` | `il_creater_active.py:239-245` |
| §6.22.6.1 kênh (2) | `il_creater.py:972-974` | `il_creater_active.py:1295-1297` |
| §6.22.6.1 kênh (3) | `il_creater.py:969-970` | `il_creater_active.py:1293-1294` |
| §6.22.6.1 bảng bác bỏ | `_collect_valid_char` `il_creater.py:1122-1157` | `il_creater_active.py:1439-1466` |
| §6.22.6.1 ứng viên BL-08 | `ILCreater.on_page_end` `il_creater.py:641-664` | **`ActiveILCreater.on_page_end`** `il_creater_active.py:386-407` (buffer: `:230`, `:384`, clear `:407`) |
| §6.22.7 bảng audit R8-01 | `il_creater.py:972-974` | `il_creater_active.py:1295-1297` |
| **§6.14.6 (ngoài §6.22)**, mục "Pin version" babeldoc (`Architecture.md:3687-3697`) | `il_creater.py:968-974` | `il_creater_active.py:1292-1300` |

Dòng cuối bảng nằm **ngoài** phạm vi việc được giao. Tôi vẫn sửa: đó là **cùng một trích dẫn sai,
cùng một cơ chế hỏng**, và để lại nó thì lần sau ai grep `il_creater.py` vẫn ra một địa chỉ dead
được trình bày như sự thật đã verify. Sửa 1 dòng rẻ hơn nhiều lần giải thích sau này.

Thêm vào §6.22.1 một khối **self-correction R5-05** tường minh (không phải một dòng nhét cuối mục):
ghi rõ luồng dịch dùng `_active`, `ILCreater` chỉ thuộc `parse_only.py`, và **luật**: *mọi trích dẫn
frontend trong §6.22 phải trỏ vào bản `_active`*. Kèm ghi chú **midend KHÔNG bị ảnh hưởng**
(`high_level.py:971` `ParagraphFinder(...).process(docs)`, `:1038` `Typesetting(...)`) để không ai
hoảng đi audit lại patch Bug #7/#10 của shim.

Một điểm nhỏ nhưng đáng ghi: lập luận "patch `on_lt_char` là hàm nóng nhất của parser" ở bảng bác bỏ
vẫn **đúng về bản chất** nhưng sai tên hàm — ở `ActiveILCreater`, `on_lt_char` (`:1423-1427`) chỉ là
**vỏ**, chỗ chạy mỗi ký tự là `project_native_char` (`:1292`). Đã sửa cả tên hàm và ghi rõ "vỏ vs
chỗ thật" ngay dưới bảng kênh, vì đây chính là loại chi tiết khiến người sau patch nhầm chỗ.

⚠️ **Lệch còn lại, cố ý không sửa**: note lượt 1 của Domain Expert
(`docs/expert-notes/domain-expert-20260911-...`, phần trước dòng 430) vẫn mang trích dẫn
`il_creater.py` cũ. Đó là **nhật ký của một vai khác**, R7-03 cấm sửa/ghi đè nội dung cũ, và chính
Domain Expert đã tự ghi nhận lỗi này ở section "Xác nhận lần 2" ngay trong cùng file. Hợp đồng hiện
hành (§6.22) là nguồn phải đúng — và giờ nó đúng.

#### X6 (bắt buộc) — BL-08 không được nằm chờ vô thời hạn

Thêm **§6.22.6.1.a** vào Architecture.md (mục mới, nằm trong hợp đồng chứ không chỉ trong nhật ký —
Protocol C.1), chốt 3 điều:

1. **Quy mô kênh (2) LỚN HƠN kênh (1) mà BL-04 đang vá**: ~976 ký tự dọc mất trên 52/418 trang
   (2.303 → 1.327), **gồm 2 tiêu đề chương thật** (trang 19, 31) — so với 614 ký tự / 1 đoạn của
   kênh (1). Con số này là bằng chứng **mới của lượt 2**, lượt 1 chưa có.
2. BL-04 vẫn đi trước (kênh (1) hiện **không có cơ chế nào**, kênh (2) có overlay phủ một phần),
   nhưng **sau BL-04, BL-08 là hạng mục ưu tiên cao nhất còn lại của mảng mất-chữ**. Xếp **ngay
   sau BL-04**. Đẩy lùi → **phải ghi lý do vào design-log**.
3. Điểm khởi đầu đã có sẵn: `run_layout_qa_gate()` (`src/services/layout_qa.py:386`) chứa
   `_check_rotated_text_prescan()` (`:278-310`) quét **file gốc**, bắt mọi dòng chữ xoay kèm bbox +
   text, có test — nhưng là **dead code**: `grep -rn "run_layout_qa_gate" src/ web/ scripts/` trả về
   đúng **1 dòng, chính định nghĩa hàm**, **0 call site**; người gọi duy nhất là
   `tests/test_layout_qa.py:30`. Đó là lý do **thứ hai** (ngoài "overlay không phủ hết") khiến job
   `1ee1fdee` có 0 row `layout_qa_findings` — bộ dò tồn tại nhưng không nằm trên đường chạy.

Và cảnh báo đi kèm, viết thành **cấm** chứ không phải gợi ý: **không được bật nguyên trạng hàm đó**,
kể cả trong BL-08. Trên cuốn này nó sinh **≥52 finding `blocker`/cuốn** cho *mọi* dòng chữ xoay, kể
cả dòng overlay đã khôi phục thành công — đúng loại báo động giả có hệ thống mà QA sẽ học cách bỏ
qua, tức làm hỏng luôn giá trị của cơ chế. Việc thật của BL-08 là biến *"có chữ xoay"* thành *"chữ
xoay **bị mất**"* (đối chiếu gốc ↔ dịch) rồi mới đặt ngưỡng, **sau khi** đo nhiễu.

(Phần `backlog[]` của `project_state.json` do PM cập nhật — tôi chỉ chịu trách nhiệm phần hợp đồng.)

#### X7 (bắt buộc) — R-2 đếm thiếu khi job resume: đổi sang `SELECT COUNT` trên DB

Đây là điểm tôi **sai rõ ràng**, không phải "cách khác cũng được". Tôi viết R-2 là *"đếm từ list đã
map, **không** query lại DB"* với ý tránh chi phí DB. Ba sự thật (tự đọc lại source, khớp Domain
Expert) làm yêu cầu đó sai hướng:

- `_process_chunk()` trả `None` (`job_orchestrator.py:1733-1743`) ⇒ muốn đếm in-memory phải **thêm
  một accumulator mới**, tức thêm một sợi lineage chỉ để phục vụ một dòng log. Bản thân điều đó đã
  là mùi.
- Vòng Bước 7 (`job_orchestrator.py:576-577`) **bỏ qua** chunk đã xong: `if chunk.status != "completed":`.
- ⇒ Job **resume sau crash**: chunk hoàn tất ở lần chạy trước **đã ghi finding vào DB** nhưng không
  đi qua `_process_chunk()` lần này ⇒ accumulator rỗng cho chúng ⇒ R-2 in con số **nhỏ hơn sự thật**,
  ở đúng kịch bản rủi ro cao nhất.

Vì sao đây là hướng sai **tệ nhất có thể**, không phải sai vặt: theo F4 đã chốt, BL-04 **không** giao
UI/API — R-2 là **mặt hiển thị duy nhất** của cả hạng mục. Một mặt hiển thị duy nhất mà báo ít hơn
sự thật tạo ra **an toàn giả**, đúng hình dạng Bug #5 ("status = completed" nhưng output rỗng). Nếu
phải chọn một hướng sai, phải chọn hướng **báo thừa**.

Đã chọn phương án (i) của Domain Expert: **1 câu `SELECT COUNT(...)`** trên `layout_qa_findings` theo
`job_id` + `check_type LIKE 'babeldoc_%'`, chạy **đúng 1 lần/job** tại Bước 10 ngay trước
`job.status = "completed"` (`job_orchestrator.py:807`). Chi phí thực tế bằng không, và nó dùng
**cùng một nguồn sự thật** với câu SQL R-3 đã giao QA — một nguồn, không hai. Viết shape query thẳng
vào §6.22.6.2 kèm ghi chú Dev cần thêm import `func`/`col` (`job_orchestrator.py:31` hiện chỉ
`from sqlmodel import select`) và `LayoutQaFinding` (`src/models/layout_qa.py:11`).

Giữ lại phương án (ii) làm **đường lùi có kỷ luật**, không phải lựa chọn ngang hàng: nếu Dev không
làm được query, **cấm** giữ nhãn "tổng của job" cho con số của riêng lần chạy — bắt buộc đổi tên
trường thành `unfit_drops_this_run=` + `skipped_completed_chunks=K` **và escalate**. Điều không chấp
nhận được là giữ nguyên câu chữ hứa một đằng giao một nẻo.

Thêm test **11** (`test_r2_counts_from_db_on_resume`) vào §6.22.9: chunk 0 đã completed với 3 finding
sẵn trong DB + chunk 1 sinh 1 finding → R-2 phải báo **4**, không phải 1. Test này là cái khoá: ai
đổi ngược về accumulator thì nó đỏ.

#### X2–X5, X8 (nên sửa) — làm **cả 5**

Không có điểm nào bị bỏ. Lý do làm hết: cả 5 đều là sửa câu chữ/spec, rẻ, và mỗi điểm bỏ lại đều có
một đường dẫn cụ thể tới việc Dev hoặc QA đốt công vô ích.

- **X2** — `_ChunkLike.page_start/page_end` đổi `int` → **`int | None`** cho khớp
  `src/models/chunk.py:23-24` (nullable từ 6.20.7 vì EPUB dùng `unit_start`/`unit_end`), + bắt buộc
  **`raise ValueError` tường minh** khi gặp `None`. Hôm nay chưa có bug runtime (EPUB rẽ sang
  `run_epub_job()` tại `job_orchestrator.py:457`, không đi qua `_process_chunk`/`merge_chunk_pdfs`)
  — nhưng khai `int` là **khai sai sự thật** trong hợp đồng, và `None + 1` nổ `TypeError` ở chỗ khác
  thì mất dấu nguyên nhân.
- **X3** — nói rõ hàm chung sở hữu **đúng quy tắc `start`**; phần kẹp `end` theo
  `chunk_doc.page_count` (`chunk_merge.py:95-107`, 2 nhánh full-document/chunk-scoped của Bug #7 vs
  Bug #8) **ở lại** `chunk_merge.py` vì nó phụ thuộc file thật, hàm thuần không biết được. Thêm bảng
  2 quy tắc + lệnh **giữ nguyên guard `overlap_* is not None`** (bỏ guard = đổi hành vi
  `merge_chunk_pdfs`, trái cam kết "giữ nguyên hành vi"). Viết lại **test 5**: assert `start` trả về
  bằng `actual_start` mà `merge_chunk_pdfs` tính, **không** assert bằng số trang thực sự
  `insert_pdf` vào file merge — hai con số có thể khác nhau một cách **hợp lệ**, và câu chữ cũ dễ
  dẫn QA tới một test đỏ oan.
- **X4** — thêm hẳn 1 dòng vào bảng "Chỉ chạy đúng 1 lần / trang" (§6.22.4): bất biến này còn phụ
  thuộc **`--watermark-output-mode ≠ both`**. Tự verify: `high_level.py:1023-1029` gọi
  `generate_first_page_with_watermark()` khi mode là `Both`, hàm đó dựng **PDFCreater thứ hai** và
  gọi `write()` lần nữa (`:1097-1103`) ⇒ trang đầu mỗi chunk có **2 record `page`**. Hôm nay an toàn
  vì `babeldoc_runner.py:350-351` hardcode `no_watermark`. Giá trị của việc ghi: biến một **phụ
  thuộc tình cờ** thành **ràng buộc có tên** — ai đổi cờ sẽ gặp checksum/trạng thái 3 kêu, nhưng kêu
  **sai nguyên nhân**, và sẽ mất nhiều giờ nếu hợp đồng không nói.
- **X5** — `checksum_mismatch_pages` trước đây **không có chỗ đi** khi `observed == expected`: nó chỉ
  nằm trong `detail` của finding trạng thái 3, mà trạng thái 3 lại chỉ kích hoạt khi thiếu trang. Ca
  đáng lo nhất của checksum là **ngược lại** (đủ trang nhưng một dòng `drop` bị xé ⇒
  `dropped_count=3` mà chỉ có 2 dòng) — khi đó hệ thống rơi về trạng thái 2 với **số finding ít hơn
  sự thật**, đúng loại "giảm âm thầm" mà chính checksum sinh ra để chặn. Đã: mở rộng điều kiện
  trạng thái 3 thành `observed != expected` **HOẶC** `checksum_mismatch_pages` khác rỗng; đổi tên
  trạng thái 3 thành "**KHÔNG TRỌN VẸN**" (thiếu trang *hoặc* lệch checksum); siết điều kiện trạng
  thái 1/2 thành "trọn vẹn"; và đưa `checksum_mismatch=M` vào **định dạng log R-1 bắt buộc** để con
  số không biến mất khỏi mọi mặt hiển thị. Thêm test **12**
  (`test_checksum_mismatch_triggers_incomplete`).
- **X8** — hai chỗ, cả hai đều thuộc loại "không ghi thì QA chạy xong mới biết mình đo nhầm vật":
  (1) thêm **assertion 0 (tiền điều kiện)** `job.chunk_size_used == 40` **và** chunk đang đo có
  `page_start == 199 and page_end == 240`. `chunk_size_used` là **thích ứng**
  (`COLD_START_CHUNK_SIZE = 20` / `WARM_CHUNK_SIZE = 40`, `job_orchestrator.py:112-113`, chọn tại
  `:550-561`); hiện đang warm (`concurrency_state`: `consecutive_successes=95,
  observation_count=133`) nên sẽ ra 40, **nhưng một lần fail đưa `consecutive_successes` về 0** ⇒
  chunk_size 20 ⇒ chunk 5 thành `99-120`, trang 230 rơi sang chunk khác, tập trang đổi ⇒ dính đúng
  cái bẫy mode-scale mà chính §6.22.9 cảnh báo. Một dòng assert cứu trọn một vòng chạy thật (tốn
  tiền dịch thật).
  (2) ghi thẳng **harness**: E2E là **integration test gọi thẳng `_process_chunk()`** với
  `BabeldocRunner` thật + DB thật + `Chunk` thật (`chunk_index=5, page_start=199, page_end=240,
  overlap_start=199, overlap_end=200`) — **không** qua `run_job()`, **không** chạy CLI. Đây là tầng
  duy nhất mà 3 nhóm assertion (runner thật / bộ lọc trong `_process_chunk` / log R-1) **và** lời hứa
  "42 trang thay vì 418" cùng thoả. Kèm tuyên bố **KHÔNG phủ**: log R-2 (nằm ở `run_job()` Bước 10)
  và `merge_chunk_pdfs()` — phải nói ra thay vì để QA tự suy là đã phủ, đó chính là loại im lặng đã
  sinh ra Bug #5.

#### Trạng thái sau BL4.15

- §6.22 **sẵn sàng cho Dev implement**. Không còn mục `⚠️ ASSUMED`/`[UNVERIFIED]` nào trong §6.22.
  Phần "chưa verify" còn lại vẫn đúng như BL4.13 đã nêu và **không đổi**: bản thân cơ chế đo (shim +
  sidecar) chưa chạy end-to-end lần nào — đó là việc của gate E2E.
- **Không có thay đổi code nào** trong lượt này ⇒ không kích hoạt Protocol 7 (Reviewer gate).
- ⚠️ **Ngân sách Protocol C.3 đã VƯỢT**: `docs/Architecture.md` từ 7.911 → **8.105 dòng**, trần là
  8.000. BL4.14 đã dự báo đúng ("lượt sửa tiếp theo chạm §6.22 gần như chắc chắn sẽ vượt trần"). Đây
  là cảnh báo **không chặn**, nhưng Protocol C.3 cấm ngó lơ qua nhiều lượt: PM cần lên lịch
  rotate/tách (ứng viên rõ nhất là tách phần nhật ký còn sót trong §6.22 — các khối "Đính chính
  (…)" — sang design-log, giữ §6.22 là hợp đồng thuần).

---

## BL-10 — Chi phí đo thật cho nhánh PDF/babeldoc (Tech Lead, 2026-09-11)

**Hợp đồng tương ứng: `docs/Architecture.md` §6.23 (mới) + §4.2 bảng `chunks` + §6.6.6/§6.6.7 (cập
nhật cross-ref).** Mục này là *vì sao*, không phải hợp đồng.

### Vấn đề

Từ Increment 1, mọi job PDF báo chi phí bằng `estimate_chunk_cost()` — số học trên độ dài text, sai
số công bố ±30–50% — và `jobs.cost_source` **luôn** `'estimated'`. Sự cố $6.50 (§6.11) đã cho thấy
cái giá của việc không có số thật: RC-4 chính là *"số ước lượng bị báo cáo nhầm là số đo thật"*.
Metering proxy (§6.6.6 v1.1) được thiết kế từ lâu nhưng vẫn hoãn vì phải dựng thêm 1 HTTP server
per-chunk.

### Phát hiện làm đổi bài toán

babeldoc 0.6.4 **đã tự đếm token thật** từ `response.usage` (kể cả `prompt_cache_hit_tokens`) và in
ra stdout 4 dòng tổng kết cuối mỗi tiến trình (`main.py:772-784`). App **đã capture stdout** đó và
đã parse nó 2 lần rồi (`RATE_LIMIT_LINE_RE`, `drop_sentinel_count`). Và vì `_process_chunk()` spawn
**1 subprocess babeldoc cho mỗi chunk**, tổng token in ra ứng 1-1 với chunk — tức là đạt được đúng
thứ metering proxy hứa, **không cần proxy**, chỉ cần 1 regex.

### Những chỗ suýt sai (ghi lại để không ai "đơn giản hoá" lại về sau)

1. **`re.IGNORECASE` là bẫy chết người ở đây.** babeldoc in cả `Prompt tokens:` lẫn `Cache hit
   prompt tokens:`. Bật IGNORECASE thì pattern thứ nhất khớp bên trong dòng thứ hai ⇒ `prompt_tokens`
   nhận nhầm số cache-hit, và sai này **im lặng** (vẫn ra một con số hợp lý). Hợp đồng cấm tường
   minh.
2. **`Term extraction tokens:` KHÔNG được cộng.** `main.py:524` cho `term_extraction_translator =
   translator` khi app không truyền 3 flag `--openai-term-extraction-*` ⇒ token term-extraction đã
   nằm trong `Total tokens`. Cộng thêm = đếm 2 lần. Đây là loại lỗi chỉ lộ ra khi đọc source, không
   lộ ra khi nhìn log.
3. **Brief đề xuất 1 field `real_tokens_used: int`** — tôi đổi thành dataclass 4 số vì giá input ≠
   giá output. Chỉ có `total` thì buộc phải **đoán tỷ lệ split**, tức là nhét một ước lượng vào bên
   trong thứ được dán nhãn `'metered'` — đúng bản chất RC-4 mà §6.11 tồn tại để chặn. Tốn thêm 3
   dòng regex, đổi lại nhãn `metered` không nói dối.
4. **`0` vs `None`.** Cache của babeldoc có thể làm `Total tokens: 0` — đó là **số đo thật** (0 lời
   gọi API), khác hẳn "không parse được". Vì vậy sentinel phải là `None`, không được là `0`. Tiền lệ
   đã có ở §6.20 (`actual_cost=0.0` + `metered`).
5. **`chunks.cost_source` phải là cột thật, không suy từ engine của job.** Một job có thể có chunk
   metered lẫn chunk fallback estimated (parse trượt giữa chừng). Nếu chỉ lưu ở cấp job thì con số
   trộn lẫn sẽ được dán một nhãn duy nhất — lại đúng RC-4. Luật gộp chốt: **trộn ⇒ `'estimated'`**
   (một tổng chứa số ước lượng thì bản thân nó là ước lượng). Không tạo giá trị thứ ba `'partial'`
   vì phải đổi hợp đồng ở 3 tầng để mô tả một trạng thái hiếm.
6. **Nhánh EPUB suýt bị hồi quy ngầm.** EPUB đã `job.cost_source='metered'` từ §6.20 nhưng
   `chunks` chưa có cột này. Nếu chỉ thêm cột với default `'estimated'` mà không ghi cho EPUB, thì
   những chunk **duy nhất trong dự án đã đo thật từ trước** lại mang nhãn ước lượng. Đã đưa 1 dòng
   `chunk.cost_source = "metered"` cho `_process_epub_chunk()` vào spec.

### Audit Protocol 8 (R8-01) — kết quả

Liệt kê đủ 7 bước hiện có trong `_process_chunk()` (§6.23.6). Bước bị audit "bắt" chính là bước
**CŨ**: `estimate_chunk_cost()` tồn tại vì *pdf2zh không xuất token* — lý do đó **không còn đúng với
babeldoc**. Đây đúng khuôn Bug #9 (`font_shrink_page` tồn tại vì pdf2zh vẽ tràn, không đúng với
babeldoc), chỉ khác là lần này bắt được **trước** khi có sự cố. Không bước nào rơi vào "chưa rõ" ⇒
không SKIP thêm bước nào (R8-02). Hiện thực bằng capability `reports_token_usage` trên runner
(R8-03), cùng khuôn `needs_font_shrink` / `reports_own_paragraph_drops`, **kèm guard
`isinstance(bool)`** — không có guard thì `AsyncMock(spec=...)` cho truthy và test chạy nhầm nhánh
mà vẫn PASS.

### Ranh giới bằng chứng

- **Verified trực tiếp phiên này** (đọc source bản đã cài + chạy thật): T1–T11 ở §6.23.1, gồm 1 lần
  dựng lại đúng cấu hình logging của babeldoc (`main.py:918-920`) và capture `repr()` của output
  non-tty để chốt định dạng dòng.
- **⚠️ ASSUMED, đã gắn nhãn trong §6.23.1**: (a) dòng `Total tokens:` xuất hiện trong một lần chạy
  **end-to-end thật qua pipeline app** — chưa chạy (tốn API key/thời gian ngoài phạm vi thiết kế),
  R5-02 giao cho Dev làm spike trước khi viết regex; (b) `total == prompt + completion` với DeepSeek
  — thiết kế **không phụ thuộc** vào đẳng thức này, chỉ log WARNING khi lệch.

### Cố ý KHÔNG làm trong lượt này

- **Không sửa bảng giá** `deepseek_provider.py:17-24` (quyết định của Hiếu). Hệ quả trung thực đã
  ghi thành giới hạn đã biết: `'metered'` ở vòng này nghĩa là *"token là số đo thật"*, **không**
  nghĩa *"số tiền chắc chắn đúng"*.
- **Không chiết khấu cache-hit** (đã parse, chưa dùng) ⇒ tính cao hơn thực tế — chiều sai an toàn
  theo §6.11.6.
- **Không đếm token của attempt retry thất bại** ⇒ metered là under-count khi có retry. Ghi rõ thay
  vì để QA tự phát hiện rồi báo là bug.
- Không đưa token vào `BabeldocError`/`BabeldocTimeoutError`: chunk fail không có `api_cost` để ghi.

### Trạng thái

- §6.23 **chưa implement** — chờ Human Checkpoint 2. Không có thay đổi code nào trong lượt này ⇒
  không kích hoạt Protocol 7.
- ⚠️ **Ngân sách Protocol C.3 tiếp tục vượt**: `Architecture.md` 8.105 → **8.477 dòng** (trần
  8.000). §6.23 được viết ở dạng hợp đồng thuần (phần "vì sao" nằm ở chính mục này của design-log),
  nhưng tổng vẫn tăng. PM cần lên lịch rotate như BL4.15 đã nêu.

---

## Bug #EPUB-5 — koboSpan KHÔNG phải nguyên nhân runaway; nguyên nhân thật là phép đo (Tech Lead, 2026-09-11)

**Hợp đồng tương ứng**: `docs/Architecture.md` §6.20.15 (K-1..K-5), cùng 2 sửa tại chỗ ở §6.20.6
(hộp "⚠️ SỬA 2026-09-11") và §6.20.13.3b (hộp "⚠️ ĐÃ ĐO").

### 1. Giả thuyết được giao — và kết quả: BỊ BÁC BỎ

Brief của PM nêu giả thuyết (đã tự gắn nhãn `[CHƯA VERIFY]`, đúng Protocol 1 mở rộng): file EPUB
export từ Kobo có markup `koboSpan` dày đặc; pipeline gửi nguyên inner-HTML cho LLM nên payload thật
lớn hơn nhiều budget đo bằng `_plain_char_len()`, và đó là nguyên nhân runaway.

**Hai nửa của giả thuyết có số phận khác nhau:**

| Nửa | Kết luận |
|---|---|
| "Payload gửi đi chứa nguyên koboSpan, budget lại đo bằng text thuần" | **ĐÚNG, đã verify** (`job_orchestrator.py:2372` + `epub_document.py:786` + `chunking.py:268`) |
| "…và đó là nguyên nhân runaway" | **SAI — bị bác bỏ bằng test đối chứng** |

### 2. Test đối chứng đã bác bỏ giả thuyết

3 job EPUB đều `failed` vì R-b, cùng provider `deepseek-v4-flash`:

| Job | Sách | koboSpan | inner-HTML / text thuần | % request bị gắn runaway | max ratio |
|---|---|---|---|---|---|
| `781b59b0` | Sourdough Culture (Kobo) | **1.963/1.963 unit**, 7.616 thẻ | **2,29×** | **68,2%** (45/66) | 7,57× |
| `88e897af` | Sourdough Discard Recipes | **0** | 1,14× | 63,2% (148/234) | 25,57× |
| `f21c1555` | Sourdough by Science | **0** | 1,21× | 67,2% (334/497) | 32,21× |

Hai cuốn **không có một thẻ koboSpan nào**, markup ratio sát đúng giả định `1.15`, vẫn runaway với
tỉ lệ **không phân biệt được** với cuốn Kobo — và **đuôi phân bố còn tệ hơn nhiều** (p99 ~20× vs
7,6×). Cuốn Kobo thực ra là cuốn *nhẹ* nhất, vì `payload_chars` phình lên nằm ở **mẫu số** của
`runaway_ratio` nên markup rác lại **che bớt** triệu chứng.

Nếu chỉ nhìn 1 job (đúng như brief ban đầu) thì tương quan trông hoàn hảo. Đây là ca sách giáo khoa
"correlation ≠ causation" mà R5-01 tồn tại để chặn: **giả thuyết trông rất thuyết phục, nhưng nhóm
đối chứng đã nằm sẵn trong `data/processing/` và chưa ai mở ra**.

### 3. Nguyên nhân thật

`epub_expected_output_tokens(payload_chars) = payload_chars × 1,16 / 2,0` mô hình hoá **số token của
bản dịch tiếng Việt**. Còn `output_tokens` mà nó bị đem so sánh là
`response.usage.completion_tokens` (`openai_provider.py:116`).

`deepseek-v4-flash` **bật thinking mặc định, effort mặc định `high`** (doc chính thức đã fetch:
<https://api-docs.deepseek.com/guides/thinking_mode/> — *"Thinking mode is enabled by default, with
the default effort being `high`"*). App **không** truyền tham số tắt, và chỉ đọc
`message.content` (bỏ `reasoning_content`). Nên `completion_tokens` ≈ *token thinking + token trả
lời*, trong khi công thức chỉ mô hình hoá vế sau.

**Bằng chứng định lượng độc lập** (không dựa vào doc): ghép `units.json` (bản dịch thật đã nhận) với
`requests.jsonl` (token thật) trên 55 chunk / 3 sách cho **0,23–0,66 ký tự trả về / 1 output token**,
median ~**0,32**. Tiếng Việt NFC tệ nhất cũng chỉ ~3 byte/ký tự, nên ngay cả tokenizer byte-fallback
thuần cũng không thể xuống dưới ~0,33 — và con số 0,25 quan sát được nằm **dưới** giới hạn vật lý đó.
Kết luận: phần lớn `completion_tokens` **không phải nội dung trả về**. Khớp chính xác với S6.

Đối chiếu thêm: `max_tokens = 8192`, max quan sát = **8.099**, **0 request** chạm trần ⇒ không có
truncation. Các response "runaway" không hề bị cắt cụt — chúng chỉ *được đo sai*.

### 4. Vì sao lỗi này giết job (cơ chế, không phải triệu chứng)

`job_orchestrator.py:2398` — `if runaway and missing_ids: raise EpubRequestRunawayError`. Nhánh này
đứng **TRƯỚC** toàn bộ thang cứu hộ (C-1 retry từng-id `:2452`, retry nguyên request `:2470`, Lớp B
salvage, Lớp C fallback).

Với `runaway` gần như luôn `True` (65,4% request, và 100% các request lớn), R-b thoái hoá thành
**"abort cả chunk khi thiếu BẤT KỲ id nào"**. Mọi lớp dung sai xây suốt §6.20.14 (Lớp A/B/C, 3 vòng
Protocol 3, Bug #EPUB-B2-1…B2-5) trở thành **code chết cho provider này** — chúng chưa bao giờ có
cơ hội chạy. Đó là lý do 4/7 chunk của job `781b` phải retry thủ công nhiều lần mới qua: mỗi lần là
một lần R-b bắn nhầm, không phải một lần model hỏng thật.

### 5. Điều §6.20.13.3b đã tự dự đoán — và không ai quay lại kiểm

Chính §6.20.13.3b (viết 2026-09-09) đã ghi: *"Nếu max ratio thật của lần chạy lành mạnh > 1,5 →
ngưỡng 3,0 quá sát, phải nâng và ghi lại. Đây chính là bước 'đo thêm trước khi tự tin vào con số'
của R5-02."* Log `requests.jsonl` đã được implement đúng như yêu cầu và **đã chứa sẵn dữ liệu bác bỏ
ngưỡng** từ lần chạy live đầu tiên. Bước "đọc lại log rồi cập nhật hằng số" thì không có ai sở hữu:
nó không phải task của Dev (đã code xong), không phải của QA (job `failed`, không tới mục đo), không
phải của Tech Lead (không được dispatch lại).

**Bài học quy trình**: một chỉ thị dạng *"lần chạy live đầu tiên phải đo X rồi hiệu chỉnh"* đặt trong
Architecture.md **không có chủ sở hữu** thì không bao giờ được thực thi. Nó cần là một mục
`backlog[]`/`open_questions[]` trong `project_state.json` có người chịu trách nhiệm, hoặc một
assertion trong code (như K-4 đã làm cho `EPUB_INLINE_MARKUP_FACTOR`). Đề xuất PM đưa vào backlog
như một luật chung, không chỉ cho ca này.

### 6. Vì sao K-1 (bóc koboSpan) vẫn đáng làm, dù không sửa được bug

Không phải để sửa runaway — mà vì nó là **một lỗi thật khác, độc lập**:

- `EPUB_INLINE_MARKUP_FACTOR = 1.15` (chốt tại §6.20.6 FD X5(b), đo trên **đúng 1 cuốn**) bị cuốn
  Kobo làm sai **2×** ⇒ cost gate ước **thấp** ⇒ vi phạm §6.11.6 ("được ước cao, CẤM ước thấp") ở
  đúng lớp bảo vệ tài chính. Đây là cùng khuôn lỗi mà FD X5(b) từng bắt Expert vì ước thấp 9% — lần
  này là 100%.
- **50,5% payload là rác**, trả tiền cả chiều vào lẫn chiều ra (model tái tạo y hệt koboSpan trong
  bản dịch — xem `units.json` chunk_0).
- Bóc xong đưa tỉ lệ về **1,13×**, tức **khôi phục tính đúng đắn của hằng số 1.15 hiện có** thay vì
  phải nâng nó lên 2,3 cho mọi EPUB (nâng như thế sẽ ước cao vô lý cho 2 cuốn còn lại).

### 7. Điểm suýt sai khi thiết kế K-1 (ghi lại để không tái diễn)

Phản xạ đầu tiên là bóc markup ở **chỗ build payload** (`job_orchestrator.py:2372`) — nơi vấn đề lộ
ra. Đó sẽ là một Bug #5 mới: `write_translated()` mở **lại zip gốc** và đếm "slot" text trên node
**chưa bóc** (`_apply_translation_untrusted_structure` → `_text_runs_under`), còn bản dịch trả về đã
sạch span ⇒ lệch số slot ⇒ rơi vào nhánh *"Known limitation"*, dồn hết bản dịch vào slot dài nhất và
**giữ nguyên tiếng Anh** ở các slot còn lại. Đo thật: **85/1.963 unit** đi qua nhánh untrusted,
**64** trong đó multi-slot ⇒ 64 unit dịch sót *âm thầm* (BR-EPUB-05 vẫn pass vì 64/1963 = 3,3% < khe
hở 10%).

Đặt phép bóc ở `_parse_xhtml()` — điểm vào **duy nhất** dùng chung bởi `load()`,
`write_translated()`, `count_bb_vi_pairs()`, `to_markdown()` — làm cả 4 đường đọc cùng nhìn một cây.
Số slot/unit giảm từ median 4,0 (max 16) xuống median 1,0 (max 12) ⇒ nhánh rủi ro *an toàn hơn*
hiện trạng. Đây đúng tinh thần R6-01: chọn chỗ sửa theo **lineage**, không theo chỗ triệu chứng lộ ra.

Đã kiểm 0/7.616 `id="kobo.*"` được `href`/`idref`/`src` nào tham chiếu ⇒ bóc an toàn, không phá
`page-list`/nav. Giữ nguyên `<span epub:type="pagebreak">` (khác class, **id của nó CÓ được tham
chiếu**).

### 8. Cố ý KHÔNG làm trong lượt này

- **Không sửa `CHARS_PER_TOKEN_VI` ngay**, dù đã biết nó sai ~6×: số đo hiện tại nhiễm token
  thinking. Hiệu chỉnh bây giờ = khoá cứng cái sai vào hằng số. Xếp thành K-4, sau K-2/K-3 (R8-02
  deny-by-default áp cho chính con số).
- **Không nâng `EPUB_RUNAWAY_OUTPUT_FACTOR`** — nâng ngưỡng là chữa triệu chứng của một phép đo sai
  đơn vị. Sửa tử số (`answer_tokens`) trước, đo lại, rồi mới bàn ngưỡng.
- **Không tổng quát hoá K-1 thành "bóc mọi span rỗng nghĩa"** — chưa đo trên EPUB khác, R8-02.
- **Không đổi signature `provider.translate()`** — ràng buộc kiến trúc từ X4 (§6.20.12), 5 provider
  dùng chung. K-3 hiện thực bằng capability trên class (R8-03), không rẽ nhánh theo tên provider.
- **Không tự chạy job lại để xác minh** — phạm vi lượt này là thiết kế; và spike K-2 phải do Dev làm
  theo R5-02 (capture golden file), không phải Tech Lead làm hộ rồi mô tả lại.

### 9. Trạng thái

- §6.20.15 **chưa implement**. K-2/K-3 mang nhãn ⚠️ ASSUMED ⇒ **chặn Dev implement đúng 2 mục đó**
  cho tới khi spike R5-02 xong; K-1 và K-5 **không** bị chặn.
- Không có thay đổi code nào trong lượt này ⇒ không kích hoạt Protocol 7.
- ⚠️ **Ngân sách Protocol C.3 tiếp tục vượt**: `Architecture.md` 8.477 → ~8.640 dòng (trần 8.000);
  `design-log.md` 6.413 → ~6.520 (trần 8.000). Phần "vì sao" đã dồn hết sang design-log, nhưng
  Architecture.md vẫn tăng. PM cần lên lịch rotate.

---

## Final Decision: Hiếu trả lời HOI-04/HOI-05 (Bug #EPUB-5) — 2026-09-11

**Hợp đồng tương ứng**: `docs/Architecture.md` §6.20.15 (bảng "Trạng thái quyết định", K-1, K-3).
RCA đầy đủ: mục *"Bug #EPUB-5 — koboSpan KHÔNG phải nguyên nhân runaway; nguyên nhân thật là phép
đo (Tech Lead, 2026-09-11)"* ngay phía trên.

Theo Protocol B (CLARIFY trước, WRITE sau) — 2 câu hỏi do Tech Lead nêu sau khi điều tra Bug
#EPUB-5, PM gộp hỏi một lượt (`open_questions[]` HOI-04/HOI-05), Hiếu trả lời trực tiếp qua
`AskUserQuestion` trong chat 2026-09-11. **Cả hai đều trùng với mặc định đề xuất.**

### HOI-04 — Tắt thinking mode của DeepSeek cho nhánh EPUB (K-3)

*Câu hỏi*: tắt thinking mode của `deepseek-v4-flash` cho nhánh EPUB
(`Settings.epub_disable_thinking = True`, §6.20.15 K-3) để `output_tokens` không còn lẫn token suy
luận gây runaway giả?

*Trả lời*: **TẮT thinking cho nhánh EPUB** (= mặc định đề xuất). Hiếu chấp nhận đánh đổi đã nêu:
chi phí output giảm mạnh, chất lượng dịch **câu khó** có thể giảm nhẹ. Cơ sở: dịch câu là tác vụ
không cần CoT, còn effort `high` mặc định (S6, doc chính thức DeepSeek đã fetch) đang chiếm phần
lớn chi phí output và là nguyên nhân trực tiếp làm R-b abort nhầm 65,4% request.

### HOI-05 — Chấp nhận bóc `id="kobo.*"` khỏi output EPUB (K-1)

*Câu hỏi*: chấp nhận việc unwrap `koboSpan` làm biến mất `id="kobo.*"` trong file EPUB đầu ra?
Hệ quả đã đo: **0/7.616** id được `href`/`idref`/`src` nào tham chiếu (S8), chỉ ảnh hưởng tính năng
phân trang lại của riêng máy đọc Kobo.

*Trả lời*: **CHẤP NHẬN bóc** (= mặc định đề xuất). Không id nào bị tham chiếu ⇒ không phá
`nav`/`ncx`/`page-list`, không vi phạm BR-EPUB-01; đổi lại bỏ được **50,5% payload rác** và khôi
phục tính đúng đắn của `EPUB_INLINE_MARKUP_FACTOR = 1.15` thay vì phải nâng hằng số này lên 2,3 cho
mọi EPUB (nâng như vậy sẽ ước cao vô lý cho 2 cuốn không-Kobo).

### Ranh giới của 2 quyết định này — điểm QUAN TRỌNG nhất của mục này

Quyết định của Hiếu là **"làm cái gì"** (chấp nhận đánh đổi nghiệp vụ), **KHÔNG PHẢI** "đã verify
cơ chế kỹ thuật hoạt động đúng như mô tả". Cụ thể:

| Mục | Được duyệt phần nào | Vẫn ⚠️ ASSUMED phần nào |
|---|---|---|
| K-1 | Toàn bộ (hướng + hệ quả mất id) | — (mọi claim có nguồn xác thực S1–S4, S8) |
| K-2 | Không hỏi Hiếu (quyết định kỹ thuật thuần) | `usage.completion_tokens_details.reasoning_tokens` có mặt & khác 0 trên response sống |
| K-3 | **Hướng**: tắt thinking, `epub_disable_thinking=True` mặc định | **Cơ chế**: `extra_body={"thinking": {"type": "disabled"}}` được endpoint DeepSeek chấp nhận (không 400) |

⇒ **R5-02 vẫn chặn Dev implement K-2 và K-3** cho tới khi spike xong (gọi thật 1 request EPUB, in
`response.usage.model_dump()`, lưu golden file `tests/fixtures/epub_llm/deepseek_v4flash_usage.json`
theo R5-03). Không được gỡ nhãn ⚠️ ASSUMED chỉ vì hướng xử lý đã được duyệt — đây đúng là loại
nhầm lẫn "đã quyết = đã verify" mà Protocol 5 tồn tại để chặn.

### Hệ quả

- §6.20.15 được cập nhật tại chỗ: thêm bảng "Trạng thái quyết định", đánh dấu K-1/K-3 **ĐÃ CHỐT**,
  giữ nguyên toàn bộ nội dung kỹ thuật và **giữ nguyên** 2 hộp ⚠️ ASSUMED ở K-2/K-3.
- Thứ tự implement (§6.20.15 *"Thứ tự implement bắt buộc"*) **không đổi**: spike → K-5 → K-2 → K-3
  → chạy live 1 cuốn → K-1 (song song được) → K-4.
- Không có thay đổi code nào trong lượt này ⇒ không kích hoạt Protocol 7.
- HOI-06 (luật quy trình "chỉ thị ⚠️ ASSUMED phải có mục `backlog[]` kèm owner") cũng đã được Hiếu
  chốt cùng lượt, nhưng PM ghi trực tiếp vào `CLAUDE.md` project (R5-06) — không thuộc phạm vi
  thiết kế kỹ thuật của mục này.

## Bug #EPUB-5 — K-1..K-5 implement + live E2E (2026-09-11, Dev) — phát hiện MỚI, chưa fix: guard OCF `mimetype ZIP_STORED` fail trên EPUB thật

Sau khi implement K-5 → K-2 → K-3 (theo đúng thứ tự bắt buộc, spike R5-02 xanh cả 2 câu — xem
`tests/fixtures/epub_llm/deepseek_v4flash_usage.json`), chạy live E2E job thật
(`bfc0ac24-0664-4932-96da-1ac99c1abc10`) trên `Sourdough Culture...epub` (66 chunk, KHÔNG kèm K-1):
**66/66 chunk `completed`, 784 request, 0 abort vì R-b, 0/784 request rò rỉ `reasoning_tokens`**
(K-3 hoạt động đúng trên toàn bộ sách thật) — gate G-2 (Architecture.md §6.20.15) đạt cho chính
phần dịch. Số đo đầy đủ (`chars_per_answer_token`, `runaway_ratio`) đã ghi vào §6.20.15 mục K-4.

**Phát hiện MỚI, KHÔNG thuộc phạm vi Bug #EPUB-5, KHÔNG được fix trong lượt này**: job cuối cùng
báo `status="failed"` ở bước MERGE (sau khi cả 66 chunk đã dịch xong), lỗi:
`"'<path>...epub': entry 'mimetype' khong o dang ZIP_STORED"` — đây là 1 guard OCF-compliance CÓ
SẴN TỪ TRƯỚC trong `EpubDocument.write_translated()` (`src/services/epub_document.py`), kiểm
`infolist[0].compress_type == zipfile.ZIP_STORED`. Verify trực tiếp: file nguồn
`data/uploads/4a752f64-...Sourdough Culture...epub` có entry `mimetype` với
`compress_type=8` (`ZIP_DEFLATED`), KHÔNG phải `0` (`ZIP_STORED`) — vi phạm OCF spec (đa số trình
đọc EPUB bỏ qua vi phạm này, nhưng app hiện từ chối ghi đè lên file không tuân thủ). Bug này tồn
tại ĐỘC LẬP với K-1..K-5 (không do đợt sửa này gây ra — guard này có từ trước), chỉ mới LỘ RA vì đây
là lần đầu tiên 1 job EPUB thật chạy hết toàn bộ 66 chunk tới bước merge mà không bị Bug #EPUB-5
chặn giữa chừng. Không sửa ở đây (ngoài phạm vi brief S4) — báo lại PM/Tech Lead để quyết định có
nên nới guard này (chấp nhận EPUB có `mimetype` compressed nhưng vẫn well-formed OCF về mặt khác)
hay giữ nguyên strict và coi đây là giới hạn đã biết.

---

## S5 — Verify claim "browser tự nhớ thư mục tải lần trước" (Tech Lead, 2026-09-12)

Hiếu chọn phương án "không code logic mới" cho yêu cầu chọn thư mục tải: chỉ thêm UI hint, để browser
lo phần chọn + nhớ thư mục. PM đưa claim "bật tuỳ chọn hỏi-nơi-lưu thì browser sẽ nhớ thư mục lần
trước" vào brief mà chưa verify → Protocol 5 R5-01 buộc Tech Lead verify trước khi nó lan xuống Dev.

Kết quả: claim **ĐÚNG cho cả Chrome và Firefox**, verify bằng source thật (không phải kiến thức chung,
cũng không phải forum — kết quả WebSearch ban đầu chỉ trả về forum/blog, không đủ theo R5-01):
- Chromium `download_target_determiner.cc:333-336` (chọn thư mục khởi tạo = `SaveFilePath()`, kèm
  comment "always prefer the last directory that the user selected") và `:757` (ghi lại thư mục vừa chọn).
  Đáng chú ý: `DownloadFilePicker::FileSelected` KHÔNG ghi pref — việc ghi nằm ở target determiner, nên
  tra nhầm file sẽ ra kết luận ngược ("Chrome không nhớ").
- Firefox `HelperAppDlg.sys.mjs:356-365` + `:399`; `DownloadLastDir.sys.mjs:86-91` cho thấy
  `browser.download.lastDir.savePerSite` mặc định `true` → nhớ **theo site**, không phải toàn cục.

Điểm phải cẩn thận trong wording: (a) nhãn Firefox đã đổi thành "Ask where to save files before
downloading" (`preferences.ftl:617-618`), wording cũ "Always ask you where to save files" là sai với bản
hiện tại; (b) private/incognito không lưu lastDir (`DownloadLastDir.sys.mjs:54-61`) → hint không được
hứa tuyệt đối. Hợp đồng ghi tại Architecture.md §6.24.

---

## BL-12 — RCA: job EPUB thật fail ở bước MERGE CUỐI vì guard OCF `mimetype ZIP_STORED` (Tech Lead, 2026-09-16)

Hợp đồng kết quả: **Architecture.md §6.25** (đọc ở đó nếu chỉ cần biết hệ thống PHẢI làm gì).
Mục này là nhật ký: bằng chứng, phản biện, quyết định.

### 1. Hiện tượng

Job `bfc0ac24-0664-4932-96da-1ac99c1abc10` (`Sourdough Culture …epub`, 66 chunk, 784 request,
$0,588) dịch **thành công 66/66 chunk** — gate G-2 §6.20.15 đạt, xác nhận Bug #EPUB-5 đã hết — rồi
`status="failed"` ở bước cuối với `error_message`:

```
'<path>…Sourdough Culture….epub': entry 'mimetype' khong o dang ZIP_STORED
```

Tiền đã trả, không có file output. Job `781b59b0` của Hiếu bị chặn theo.

### 2. Truy vết — "bước MERGE CUỐI" nằm ở đâu

- `src/core/job_orchestrator.py:1412-1424` — `merged_path = self._output_dir / job.id / "translated_vi.epub"`,
  rồi `doc.write_translated(translations, merged_path, …)`, bọc trong `try/except Exception` →
  `job.status = "failed"; job.error_message = str(exc)` (`:1425-1431`). Đây là nơi lỗi trồi lên.
- Chỗ raise thật: `src/services/epub_document.py:984-991`, **bên trong** `write_translated()`:

```python
infolist = src_zf.infolist()
if not infolist or infolist[0].filename != "mimetype":
    raise EpubParseError(...)                       # :985-989
if infolist[0].compress_type != zipfile.ZIP_STORED:
    raise EpubParseError(f"'{self.path}': entry 'mimetype' khong o dang ZIP_STORED")  # :990-991
```

Nguồn gốc guard: commit `b5dad5e` *"US-22 EPUB — Bước 1/3: EpubDocument parser"*
(`git log -S "khong o dang ZIP_STORED"`) — tức guard **có từ trước** Bug #EPUB-5, không do đợt
K-1..K-5 sinh ra. Nó chỉ chưa bao giờ chạy tới vì trước đó chưa job EPUB thật nào đi hết 66 chunk.

### 3. Root cause — HAI lỗi chồng lên nhau, phải tách bạch

**(a) Lỗi ở dữ liệu vào (có thật, đã verify trực tiếp)**: file nguồn
`data/uploads/4a752f64-…_Sourdough Culture … (z-library.sk, 1lib.sk, z-lib.sk).epub` có entry
`mimetype` **là entry đầu tiên, nội dung đúng `b"application/epub+zip"`, nhưng bị nén DEFLATED**.
Đọc thẳng byte local header: `PK\x03\x04`, `method = 8`, `extra len = 0`, `name = b"mimetype"`;
`infolist()[0].compress_type = 8`, `file_size = 20`, `compress_size = 22` — *nén xong to hơn bản gốc
2 byte*, minh hoạ đúng vì sao OCF bắt STORED. Toàn bộ 63/63 entry đều DEFLATED ⇒ file đã bị re-zip
lại bằng công cụ không biết luật OCF. Vi phạm đúng 1 trong 3 câu MUST của EPUB 3.3 §4.3
(fetch thật, trích nguyên văn ở Architecture.md §6.25.1).

**(b) Lỗi ở thiết kế của chính app (đây mới là root cause thực sự của BL-12)**: app đặt một kiểm
tra thuộc về **chất lượng file OUTPUT** vào đúng bước cuối cùng, dưới dạng **reject** thay vì
**repair**, và **sau** toàn bộ chi phí LLM. Ba sai lầm ghép lại:

1. **Sai chỗ**: `load()` (chạy ở pre-flight cost estimate, `job_orchestrator.py:1143` và
   `cost_gate.py:167`) KHÔNG kiểm gì về `mimetype`; chỉ `write_translated()` kiểm. Tức điều kiện
   tiên quyết để job có thể hoàn tất lại được kiểm ở *bước cuối cùng*. Không có lý do kỹ thuật nào
   — thông tin cần kiểm (`infolist()[0]`) đã sẵn sàng ngay giây đầu tiên mở file.
2. **Sai hành động**: app tự ghi zip output bằng `zipfile`, tức **tự quyết định** thứ tự entry và
   `compress_type` của output. Nó hoàn toàn có thể ép `mimetype` lên đầu + STORED và tạo ra file
   output *tuân thủ hơn cả input*. Từ chối làm việc chỉ vì input không tuân thủ là nhầm lẫn giữa
   "hợp đồng của file tôi ghi ra" và "điều kiện nhập học của file tôi đọc vào".
3. **Sai mức nghiêm khắc**: chính `ebooklib 0.20.0` mà app đang dùng để ĐỌC file đó **đọc được bình
   thường** (`epub.read_epub(<file vi phạm>)` → `spine = 22`). App nghiêm khắc hơn thư viện đọc của
   chính nó, trong khi phần nghiêm khắc đó không mua lại được lợi ích nào cho output.

### 4. Phản biện các phương án (và vì sao loại)

| Phương án | Loại/chọn | Lý do |
|---|---|---|
| **A. Nới guard**: bỏ hẳn 2 nhánh kiểm, ghi output với `compress_type` copy y nguyên input | **LOẠI** | Input DEFLATED ⇒ output cũng DEFLATED (dòng `new_info.compress_type = info.compress_type`, `:1001`) ⇒ app **sinh ra** file vi phạm OCF. Đổi 1 lỗi ồn ào lấy 1 lỗi im lặng |
| **B. Giữ strict, coi là giới hạn đã biết**, báo lỗi rõ hơn | **LOẠI** | Vẫn fail sau khi đã tiêu $0,588. Và "giới hạn đã biết" ở đây nghĩa là từ chối cả một lớp nguồn file phổ biến (z-library/Kobo) vì 20 byte metadata |
| **C. Chuẩn hoá (re-zip) file gốc tại chỗ trong `data/uploads/` trước khi dịch** | **LOẠI** | Sửa file gốc của user = mất bản gốc, khó rollback, và đụng file đang được job/batch khác tham chiếu. Không cần: app đã ghi file mới ở bước merge rồi |
| **D. Normalize khi GHI output + chỉ reject sớm thứ không sửa được** | **CHỌN** | Xem §6.25.2. Output luôn hợp lệ OCF; input vi phạm kiểu sửa được thì sửa; input hỏng kiểu không sửa được (thiếu `mimetype`/sai nội dung) reject ở `load()` ⇒ HTTP 400 **trước** cost gate (`api/routes/jobs.py:376-380` đã map sẵn) |

Ranh giới "sửa được / không sửa được" theo **deny-by-default (R8-02)**: app ĐƯỢC sửa thứ nó tự
quyết định được (thứ tự entry, `compress_type`, extra field); KHÔNG được **chế ra** entry `mimetype`
khi file thiếu hẳn — đó là đoán media-type thay user, và một file zip không có `mimetype` rất có
thể không phải EPUB.

### 5. Spike verify (không suy đoán — R5-01/R5-02)

Chạy thật trên CPython 3.14.7 của `.venv`:

1. Re-zip file vi phạm, ép `mimetype` → `ZIP_STORED`, giữ nguyên thứ tự + `compress_type` 62 entry
   còn lại ⇒ `zipfile.testzip() is None`; `unzip -lv` báo `20 Stored 20 0% … mimetype`; local header
   `method = 0`, `extra len = 0`; `ebooklib.epub.read_epub()` đọc lại đúng `spine = 22`.
2. Đọc source `zipfile` bản đã cài: `_open_to_write()` gán **đè** `zinfo.flag_bits = _MASK_UTF_FILENAME`
   vô điều kiện (`zipfile/__init__.py:1824`), và `writestr()` luôn đi qua `open(zinfo, "w")`
   (`:2037-2038`) ⇒ dòng `new_info.flag_bits = info.flag_bits` (`epub_document.py:1005`) là **dead
   code**. Phát hiện phụ, nhưng đáng xoá: nó tạo ảo giác đang bảo toàn cờ zip của input, trong khi
   nếu Python *có* tôn trọng nó thì việc copy bit 3 (data descriptor) từ 1 input lạ sẽ sinh zip lệch.

### 6. Phạm vi — chung, không cá biệt

8 EPUB thật trong `data/uploads/`: **1 vi phạm (12,5%)**, đúng file của job `bfc0ac24` (bảng đo ở
§6.25.5). File vi phạm mang dấu vết Kobo (`META-INF/com.kobobooks.display-options.xml`, markup
`koboSpan` — cùng file đã dẫn tới K-1 ở §6.20). Nguồn sách qua đường z-library/Kobo bị re-zip toàn
bộ là chuyện thường ⇒ **chắc chắn tái diễn**. Đây không phải sự cố 1 lần.

### 7. Thiệt hại không thu hồi được

Job `bfc0ac24` và `781b59b0` **đã bị xoá khỏi DB** (`select count(*) from jobs/chunks where id like
'bfc0ac24%'` → `0`/`0`; không còn `data/processing/bfc0ac24*`). Cơ chế resume BR-CHUNK-05
(`job_orchestrator.py:1383-1391`, chỉ tái dùng chunk `status="completed"` **còn `output_path`**)
KHÔNG cứu được nữa ⇒ chạy lại sẽ **trả tiền lần hai** (~$0,6/cuốn). Đây là lý do BL-12 phải sửa
theo hướng *fail sớm*, không chỉ *fail rõ ràng hơn*.

### 8. Việc chưa làm / còn treo

- ⚠️ **[UNVERIFIED]** hành vi reading system thật (Apple Books, Calibre, Kobo, Kindle Previewer)
  với `mimetype` bị nén — chưa đo. Không chặn thiết kế (§6.25.2 làm output luôn tuân thủ), nhưng
  chặn mọi claim kiểu "reader nào cũng bỏ qua vi phạm này". Chưa cài `epubcheck` (`which epubcheck`
  → không có) ⇒ chưa có kiểm định OCF độc lập cho output của app. Đề xuất thành backlog riêng.
- Chưa implement — cần Hiếu chốt 2 câu CLARIFY dưới đây trước (Protocol B).

### 9. CLARIFY cho Hiếu (Protocol B — hỏi 1 lượt, đã có mặc định đề xuất)

- **BL-12-Q1** — chọn phương án D (normalize khi ghi + reject sớm) hay giữ strict (B)?
  *Phát sinh từ*: §4 bảng phương án. *Chặn*: toàn bộ implement BL-12 ⇒ chặn `ready_for_release`
  của S4. **Mặc định đề xuất: D.**
- **BL-12-Q2** — với EPUB **thiếu hẳn** `mimetype` hoặc nội dung khác `application/epub+zip`: reject
  sớm (HTTP 400) hay tự chế entry `mimetype` chuẩn rồi dịch tiếp? *Phát sinh từ*: ranh giới
  sửa-được/không-sửa-được ở §4. *Chặn*: nhánh L1 của §6.25.2. **Mặc định đề xuất: reject sớm**
  (deny-by-default R8-02).

### 10. Final Decision (Hiếu, 2026-09-16, qua PM/AskUserQuestion)

- **BL-12-Q1: chọn Phương án D** (= mặc định) — normalize `mimetype` → `ZIP_STORED` khi GHI output;
  chỉ reject sớm ở `load()` thứ không sửa được.
- **BL-12-Q2: reject sớm** (= mặc định) khi EPUB thiếu hẳn `mimetype`/sai content-type — không tự
  chế entry.

Cả 2 câu chọn đúng mặc định Tech Lead đề xuất ⇒ không cần viết lại §6.25 của Architecture.md. Dev
implement thẳng theo §6.25 + Final Decision này. Backlog mới cần thêm (theo mục 8 ở trên, R5-06):
đo hành vi reading system thật (Apple Books/Calibre/Kobo/Kindle Previewer) với `mimetype` bị nén +
cài `epubcheck` để kiểm định output — chưa có owner, PM thêm vào `backlog[]`.
