# Phản biện Domain Expert — US-20 "Các từ mới" (Architecture.md §6.18)

- **Người viết**: Domain Expert (ngành bánh + xử lý văn bản), phản biện độc lập theo pattern "Bug #7 Ca C" / "US-16 v2".
- **Ngày**: 2026-09-08
- **Đối tượng**: `docs/Architecture.md` §6.18.1–6.18.7 (Tech Lead), đối chiếu PRD US-20 + BR-TERM-01..04 (§4.11), `docs/ba-analysis.md` §6.5.
- **Nguyên tắc**: mọi kết luận dưới đây đều có số đo trên **dữ liệu thật của user** (2 cuốn sách đã dịch + 1 bản OCR MinerU + 114 glossary entry thật trong `data/bb_translation.db`), không suy đoán. Chỗ nào chưa đo được, gắn `[CHƯA VERIFY]`.

---

## 0. Tóm tắt kết luận

**Khung bài toán của Tech Lead là ĐÚNG và tôi đồng ý** (§6.18.1: đây là danh sách cho người duyệt → ưu tiên recall, rule-based $0 mặc định, LLM chỉ khi bấm; §6.18.5 lineage; §6.18.6 cô lập lỗi). **Nhưng phần thực thi (§6.18.2) khi áp lên sách bánh thật thì hỏng ở 3 tầng, và tầng nào cũng đo được:**

| # | Kết luận | Bằng chứng ngắn | Mức |
|---|---|---|---|
| A | **Tokenizer `[A-Za-z][A-Za-z'-]*` không sống nổi với PDF thật.** Top-40 của cuốn Figoni theo đúng spec có `avor` (#1, x638), `rst` (x147), `emulsi ers` (x99) — mảnh vỡ ligature; `flour` chỉ còn x190 vì 993 lần khác nằm dưới dạng `ﬂ our`; `baker's` **không bao giờ** xuất hiện (0 nháy ASCII / 287 nháy cong `’`); `pâte à choux` bị băm thành `p te choux`; 121 ứng viên có gạch nối ngắt dòng (`choco- late`, `ingre- dients`). | §2 | **BÁC BỎ — phải viết lại bước 1** |
| B | **Bộ lọc `en_common.txt` ~3000 từ + xếp hạng theo tần suất cho ra danh sách không phải thuật ngữ.** Với list phổ thông tiêu biểu (google-10000 top-3000), `flour` (hạng 9751), `sugar`, `butter`, `egg`, `oven` **KHÔNG** bị lọc (ngược ví dụ Tech Lead), trong khi `proof` (2933), `score` (1154), `cream`, `rest`, `shape`, `roll`, `turn`, `cup` **BỊ** lọc — đúng loại từ EC-06. Kiểm định recall bằng chính glossary user đã curate: 60 term có trong sách Figoni ≥3 lần → chỉ **1/60** lọt top-40 (Cauvain: 5/29). Median tần suất của term user curate là **13 lần**, còn ngưỡng cắt top-40 là **≥172 lần**. Không biến thể xếp hạng nào tôi thử (tần suất, keyness, đặc thù thuần) vượt 5/60 — vì **cắt cứng 40 mới là đòn bẩy sai**, không phải công thức điểm. | §3, §4, §5 | **BÁC BỎ cách cắt top-40; SỬA bộ lọc** |
| C | **Lọc trùng glossary bằng `.lower()` nguyên chuỗi `term_en` bỏ sót 23/114 (20%) entry thật** (`knead / kneading`, `bloom (chocolate)`, `pound (lb)`, `tempering (sugar)`…) — đo được `tempering` x32, `pound` x112, `ounce` x92, `bloom` x56 vẫn lọt vào "Chờ duyệt". Số nhiều cũng lọt: `meringues` x14, `crusts` x17, `mousses` x12 dù `meringue`/`crust`/`mousse` đã có. **Phát hiện ngoài phạm vi**: `GlossaryManager._count_occurrences()` đang ship có cùng điểm mù → 23 entry đó hiện **không bao giờ được inject vào prompt dịch** khi lọc theo tài liệu (§6.6.5). | §6 | **SỬA + báo bug riêng** |
| D | Lineage §6.18.5 đúng hướng, nhưng nhánh `parse_only`/EPUB đọc Markdown/HTML thô: trên bản OCR MinerU thật, top-4 là `td td td` x110, `td tr tr`, `tr tr td`, `td td tr` (thẻ bảng HTML), `jpg` x16. | §7 | **SỬA (bổ sung bước làm sạch)** |
| E | Các quyết định còn lại của §6.18 (cô lập lỗi sau `run_job`, xoá thủ công thay vì tin cascade, không cộng vào `job.actual_cost`, gộp 40 term/1 request LLM, không blacklist toàn cục theo user chốt, bắt buộc golden file) — **ĐỒNG Ý**, có lý do ở §8. | §8 | Giữ |

**Đề xuất "Final Decision"** ở §9: 8 điểm, trong đó 6 điểm Tech Lead có thể tự chốt (kỹ thuật), 2 điểm cần PM hỏi user (đổi "trần 40" thành "pool + phân trang"; và cân nhắc lại phạm vi BR-TERM-04 với số đo: **17/40 dòng top-40 của 2 cuốn sách khác nhau trùng nhau y hệt** — user sẽ bấm "Bỏ qua" cùng một bộ `dough/flour/sugar/…` ở mọi cuốn).

---

## 1. Phương pháp và dữ liệu

| Nguồn | Mô tả | Cách lấy |
|---|---|---|
| **Figoni** — *How Baking Works* (Wiley 2008), 415 trang, born-digital | 1.149.727 ký tự, 169.846 token | `_extract_full_text()` thật của `src/core/job_orchestrator.py:131` trên `data/uploads/50342382-…libgen.li.pdf` — đúng hàm §6.18.5 chỉ định cho `pdf_digital` |
| **Cauvain & Young** — *Baking Problems Solved* (Woodhead 2001), 298 trang, Anh-Anh | 520.914 ký tự, 83.033 token | cùng hàm, `data/uploads/bff337c4-…Baking problems solved….pdf` (job `4c9834bf`) |
| **OCR MinerU** — Figoni 25 trang đầu | 54.184 byte Markdown | `data/mineru-output/2f463f1c-…/ocr/*.md` (output MinerU thật, job cũ) |
| **Glossary thật** | 114 entry | `sqlite3 data/bb_translation.db "select term_en …"` |
| **Danh sách phổ thông** | google-10000-english (first20hours), cắt top-3000 / top-10000 | Tech Lead chưa ship `data/wordlists/en_common.txt` và không nêu nguồn → tôi dùng list tiêu biểu nhất mà một Dev sẽ chọn. Nếu Tech Lead dùng list khác, **các từ ở §3.1 cần đo lại**, nhưng kết luận §4–§5 không phụ thuộc list. |
| **Tần suất nền tiếng Anh** (chỉ dùng cho thử nghiệm xếp hạng §5.3) | Norvig `count_1w.txt`, 333.333 từ, 588 tỷ token | `https://norvig.com/ngrams/count_1w.txt` |

**Mô phỏng**: tôi cài lại **đúng từng bước** §6.18.2 (tokenizer regex như spec, n-gram 1–3 không vượt câu, không stopword ở 2 đầu, 4 bộ lọc, khử lồng nhau 80%, điểm `count × (1 + 0.5(n−1))`, cắt 40, `min_occurrences=3`) thành script `sim_618.py` (scratchpad phiên này: `/private/tmp/claude-501/-Users-hieutt-Vibe-Code-Baking-tools-BB-Translation/bb6eecef-c929-4946-84d5-375bde5e3612/scratchpad/sim_618.py`, có cờ bật/tắt từng sửa đổi để so sánh). Chỗ spec mập mờ tôi chạy **cả hai cách đọc** (xem §4.3).

**Thước đo chính — recall so với glossary user tự curate**: coi glossary hiện có là rỗng, chạy trích xuất, rồi hỏi: *trong số term user ĐÃ tự tay thêm vào glossary mà xuất hiện ≥3 lần trong sách, bao nhiêu term lọt vào top-N?* Đây là ground truth tốt nhất có sẵn: nó phản ánh đúng gu "thuật ngữ chuyên môn" của chính user (YA-4.7), không phải của tôi. Tech Lead đã yêu cầu golden file (§6.18.2) — tôi đề nghị **đây chính là golden metric**.

---

## 2. Điểm A (tiền đề) — Tokenizer không chịu được PDF thật

Spec bước 1: tokenize theo `[A-Za-z][A-Za-z'-]*`, "giữ dấu nháy đơn cho baker's". Đo trên text thật:

| Hiện tượng | Figoni | Cauvain | Hậu quả với spec |
|---|---|---|---|
| Nháy cong `’` / nháy ASCII `'` | **287 / 0** | **258 / 0** | `baker’s` (93 lần) → token `baker` + `s` → ví dụ "`baker's percentage` giữ lại" của §6.18.1 **không bao giờ xảy ra** trên PDF thật. (Bản OCR MinerU lại xuất nháy ASCII → `baker's percentages` x15 tìm thấy — 2 nhánh pipeline cho kết quả khác nhau cùng 1 từ.) |
| Ligature `ﬁ`/`ﬂ` + **một ký tự khoảng trắng thật** trong PDF | `ﬁ` 1480, `ﬂ` 2151; `ﬂ our` **993**, `ﬂ avor` 638, `ﬁ ne` 196, `ﬁ rst` 149 | 0 | `flour` mất 993/1183 lần đếm; `avor` x638 thành **#1 top-40**; 98 ứng viên là mảnh vỡ (`avor`, `rst`, `nal`, `ber`, `dietary ber`, `chocolate avor`). Tôi đã kiểm tra bằng `page.get_text("rawdict")`: ký tự sau glyph `ﬂ` là `' '` có bbox riêng (font Palatino-Light) → **bỏ flag `TEXT_PRESERVE_LIGATURES` của PyMuPDF không sửa được** (ra `fl our`), phải ghép ở tầng text. |
| Gạch nối ngắt dòng `xxx-\n` | 884 | 38 | 121 ứng viên dạng `pro-` x25, `com-` x17, `choco- late` x11, `ingre- dients` x10, `mono- and diglycerides` x14 |
| Chữ có dấu tiếng Pháp | 135 token: `éclair` 27, `crème` 16, `pâte` 15, `baumé` 15, `fraîche` 7, `brûlée` 4, `brisée` 2 | ít | Regex `[A-Za-z]` băm `pâte à choux` → `p te choux` (đã thấy trong output), `crème` → `cr`+`me` → bị rule "<3 ký tự" xoá. **Đây đúng nhóm YA-4.7 nói "rất nhiều thuật ngữ là tiếng Pháp/Ý"** — spec hiện tại xoá sạch nhóm này. |
| HTML/Markdown (nhánh `parse_only`, EPUB) | — | — | Xem §7: `td td td` x110 #1. |

**Kết luận A**: bước 1 phải viết lại thành một bước **chuẩn hoá + tokenize** riêng, có test bằng chính các chuỗi trên. Danh sách chuẩn hoá tối thiểu (tôi đã chạy và đo là đủ trên 2 cuốn):

1. `unicodedata.normalize("NFKC")` (ﬁ→fi, ﬂ→fl, ﬃ→ffi).
2. `’`/`‘` → `'`.
3. Ghép mảnh ligature: token đứng lẻ thuộc `{fi, fl, ffi, ffl, ff}` + khoảng trắng + chữ thường → nối (`fl our`→`flour`); token kết thúc bằng `fi/fl` + khoảng trắng + mảnh chữ thường → nối (`emulsifi ers`→`emulsifiers`). Sau bước này `flour` = x1040 (#1 của Figoni) — đúng thực tế.
4. Khử gạch nối ngắt dòng: `(?<=[a-z])-\n\s*(?=[a-z])` → `""`.
5. Strip HTML tag + markdown image/heading trước khi tách câu (cho `document.md`, EPUB `full_text()`).
6. Tokenizer chấp nhận chữ Latin có dấu: `[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ']*(?:-[A-Za-zÀ-ÿ']+)*` (giữ `pre-ferment`, `high-ratio`, `pâte`, `crème`).
7. Tách câu **ghi rõ** trên bộ dấu `[.!?;:,()\[\]"“”—•|]` — spec chỉ nói "theo dấu câu"; nếu Dev chỉ tách theo `.!?`, n-gram sẽ vượt dấu phẩy (`flour, water` → `flour water`).

---

## 3. Điểm 1 — Danh sách từ phổ thông vs thuật ngữ ngành bánh

### 3.1. Hạng thật của từ ngành bánh trong list phổ thông (google-10000)

| Từ | Hạng | Với ngưỡng 3000 | Nghĩa trong bánh |
|---|---|---|---|
| `water` | 333 | **bị lọc** | — |
| `oil` | 977 | bị lọc | — |
| `score` | 1154 | **bị lọc** | rạch bánh mì (EC-06) |
| `rest` | 1539 | **bị lọc** | nghỉ bột (bench rest) |
| `roll` | 2574 | bị lọc | cán bột / bánh cuộn |
| `rise` | 2681 | bị lọc | nở |
| `proof` | 2933 | **bị lọc** | ủ bột (EC-06) |
| `cream` | 2966 | **bị lọc** | đánh bông bơ đường (creaming) |
| `shape` | 2987 | bị lọc | tạo hình |
| `salt` | 3021 | giữ | — |
| `sugar` | 3354 | **giữ** | — |
| `milk` | 3537 | giữ | — |
| `cake` | 4200 | giữ | — |
| `bread` | 4870 | giữ | — |
| `egg` | 5101 | giữ | — |
| `oven` | 6151 | giữ | — |
| `butter` | 6235 | giữ | — |
| `fold` | 6356 | giữ (may) | gấp bột (EC-06) |
| `bench` | 6626 | giữ | bàn thợ (bench scraper, bench rest) |
| `yeast` | 8725 | giữ | — |
| `baking` | 9127 | giữ | — |
| `flour` | **9751** | **giữ** | — |
| `dough`, `crumb`, `batter`, `bake` | **không có trong 10.000** | giữ | — |

→ **Ví dụ minh hoạ của §6.18.1 ("`flour` bị loại") sai với list tiêu biểu.** Và hướng sai là hướng xấu nhất: từ generic nhất của ngành (`flour`, `sugar`, `egg`, `butter`, `oven`) được giữ và **chiếm trọn top-40**, trong khi các từ "trông phổ thông nhưng là thuật ngữ" (`proof`, `score`, `cream`, `rest`, `turn`, `cup`) bị xoá.

### 3.2. Term glossary thật bị bộ lọc "mọi token phổ thông" giết

Chạy với glossary coi là rỗng:

- Figoni: `room temperature` (x95), `cup` (x42), `turn` (x40), **`proof box` (x10)** → 4/60 term user đã curate bị xoá trước khi xếp hạng. `proof box` là ca EC-06 kinh điển: cả `proof` lẫn `box` đều "phổ thông".
- Cauvain: `turn` (x11), `cup` (x9) → 2/29.
- Nếu tăng list lên 10.000 từ (để lọc được `flour`/`sugar`): số term glossary bị giết tăng lên **12/58** (Figoni) — tệ hơn. Tức **không có cỡ list nào đúng**: list càng lớn càng giết thuật ngữ EC-06, list càng nhỏ càng để lọt từ generic. Bộ lọc nhị phân "phổ thông / không" là **công cụ sai** cho ngành này.

### 3.3. Từ có nghĩa chuyên ngành bánh mà một list phổ thông chắc chắn chứa

Với con mắt nghề, đây là các từ tiếng Anh thường gặp nhưng mang nghĩa kỹ thuật riêng trong bánh (mà `en_common.txt` cỡ nào cũng sẽ chứa, và do đó sẽ xoá khi đứng 1 mình): `proof/proofing/prove/proving`, `fold/folding/turn/turns` (cán lớp), `score/scoring`, `crumb`, `crust`, `rest/resting`, `bench`, `shape/shaping`, `bloom` (chocolate/gelatin), `sponge` (bột cái / bánh bông lan), `starter`, `rope` (bệnh dây trong bánh mì), `retard/retarding`, `dock/docking`, `cream/creaming`, `whip/whipping`, `sheet/sheeting`, `roll/rolling`, `spring` (oven spring), `peak/peaks` (soft/stiff), `ribbon` (ribbon stage), `stage`, `seize` (chocolate seizes), `temper/tempering`, `blind` (blind bake), `wash` (egg wash), `crimp/crimping`, `ball/crack/thread` (sugar stages), `set/setting`, `curdle/split/break` (emulsion), `slack/tight` (dough), `window/windowpane`, `stretch`, `shaggy/tacky`, `feed/discard` (starter), `float/poke test`, `deflate/knock back/punch`, `scald`, `sift/sifting`, `dust/dusting`, `glaze`, `seal`, `cut in/rub in`, `develop/developed` (gluten), `hydrate/hydration`, `bulk`, `lame`, `couche`, `banneton`, `peel`, `deck`, `stone`, `steam`.

→ Bộ lọc phổ thông cần **danh sách ngoại lệ chuyên ngành** `data/wordlists/baking_sense_allowlist.txt` (≈80 từ, tôi có thể soạn bản đầy đủ nếu PM giao): token nằm trong allowlist **không bao giờ** bị coi là "phổ thông". Đây là cách rẻ nhất, $0, và đúng bản chất EC-06 mà PRD đã cảnh báo.

**Kết luận điểm 1**: giữ ý tưởng "lọc từ phổ thông" nhưng (a) chỉ áp cho **1-gram** (2/3-gram có ≥1 token không phổ thông vốn đã qua; 2/3-gram toàn token phổ thông xử lý bằng allowlist + độ kết dính, xem §4), (b) bắt buộc allowlist ngành bánh, (c) Tech Lead phải **ghi rõ nguồn list** trong Architecture.md (đúng tinh thần R5-01 dù không phải external tool — vì kết quả phụ thuộc hoàn toàn vào list nào).

---

## 4. Điểm 2 — N-gram: nhiễu tổ hợp và trùng con-cha

### 4.1. Đã đo được 5 loại nhiễu, spec chỉ xử lý 1

| Loại nhiễu | Ví dụ thật (Figoni, theo spec) | Spec §6.18.2 có xử lý? |
|---|---|---|
| **Stopword ở giữa 3-gram** | `exercises and experiments` x96 (#15), `batters and doughs` x71, `color and avor` x15, `fats and oils` x56 | Không — chỉ cấm stopword ở 2 đầu |
| **Số ít / số nhiều** | trong top-100 có **10 cặp**: `flour/flours`, `sugar/sugars`, `dough/doughs`, `egg/eggs`, `starch/starches`, `fruit/fruits`, `syrup/syrups`, `cake/cakes`, `batter/batters`, `ingredient/ingredients` → 20% slot top-100 bị lãng phí | Không |
| **Tên riêng / đầu mục sách** | Cauvain top-40: `cauvain` x178 (#13), `baking problems solved` x129 (#6), `blackie academic professional`, `chipping campden`, `cauvain and l`, `technology of breadmaking`, `fig` x68 → **6/40 slot**; Figoni: `exercises and experiments`, `united states`, `figure`, `table` | Không. Lọc theo tỷ lệ viết hoa giữa câu ≥80% giết được 221 (Figoni) / 102 (Cauvain) ứng viên loại này, không chạm term glossary nào trừ `Fahrenheit` (chấp nhận được). Acronym toàn hoa (`CCFRA`, `FMBRA`) cần rule riêng. |
| **Mảnh của term glossary đã có** (lỗi **thứ tự bước**) | Cauvain: `puff pastry` (x64) đã có trong glossary → bị xoá ở bước 3 → `puff` x70 **không còn n-gram dài nào để bị hấp thụ** ở bước 4 → nổi lên #35. Figoni: `powder` x216 (#30) sau khi `baking powder` bị xoá. | Không — bước 3 (lọc glossary) chạy **trước** bước 4 (khử lồng nhau) nên term glossary không tham gia hấp thụ. Sửa: n-gram glossary vẫn được **đếm** làm "n-gram dài đã giữ" ở bước 4, chỉ không được **xuất**. |
| **Cụm ghép chứa term glossary** ("khớp một phần") | 163/5122 ứng viên chứa 1 term glossary làm cụm con: `pound cake` x35 (từ `pound`), `chapter gluten` x13, `form gluten` x13, `ingredient pound ounce` x12, `ounce grams baker's` x11 | Tech Lead cố ý giữ (`chocolate ganache` khi có `ganache`). **Đồng ý về nguyên tắc** (`Swiss meringue`, `laminated dough`, `Italian meringue` đều là term riêng và user thật đã thêm cả cha lẫn con). Nhưng nhiễu dạng `chapter gluten`/`form gluten` là 3-gram cắt ngang cú pháp — bớt được bằng rule stopword-giữa + lọc tên riêng ở trên, không cần rule riêng. |

### 4.2. Trọng số `1 + 0.5(n−1)` không đủ để cụm nhiều từ nổi lên

- Glossary thật của user: **81/114 (71%) là cụm ≥2 từ**, 28 entry dạng `-ing`.
- Top-40 Figoni theo spec: **3/40** là cụm ≥2 từ (`baked goods`, `exercises and experiments`, `wheat flour`). Cauvain: 9/40 nhưng 6 trong đó là tên sách/tác giả.
- Lý do: 1-gram generic có count 300–1000; cụm 2 từ có giá trị (`gluten development` x71, `baking powder` x113, `active dry yeast` x18, `bulk fermentation` x15) chỉ đạt điểm 27–170. Hệ số 1.5×/2× không bù nổi chênh lệch 10×.

### 4.3. Rule khử lồng nhau (bước 4) mập mờ, 2 cách đọc cho 2 kết quả rất khác

Spec: *"bỏ n-gram ngắn nếu ≥80% số lần xuất hiện của nó nằm bên trong **1 n-gram dài hơn** đã giữ"*.

| Cách đọc | Số ứng viên bị hấp thụ (Figoni) | Hậu quả |
|---|---|---|
| "1 n-gram" = **một** n-gram dài duy nhất (max) | 616 | An toàn; `gluten` x447 giữ lại |
| "nằm bên trong n-gram dài hơn" = **tổng** mọi n-gram dài chứa nó (sum) | 856 | **Giết** `gluten` x447, `crumb` x139, `meringue` x116, `crust` x91, `pound`, `ounce` — đúng 6 term glossary 1-gram giá trị nhất, vì mỗi từ đó tham gia hàng chục cụm (`gluten strands`, `gluten proteins`, `gluten ball`…) cộng dồn vượt 80% |

Dev có thể cài theo cách 2 mà không sai spec. **Phải ghi rõ "max, không sum"** và thêm test golden cho `gluten`.

**Kết luận điểm 2**: bổ sung 4 rule (stopword-giữa trừ `of/à/de/en/au`, gộp số ít/số nhiều, lọc tên riêng/acronym, glossary tham gia hấp thụ) và chốt cách đọc bước 4. Với 2/3-gram, nếu Tech Lead muốn một tiêu chí thống kê thay cho hệ số cố định, độ đo chuẩn là **độ kết dính** (PMI / t-score) — tôi chưa đo, đề nghị đưa vào harness golden để so sánh, không chốt bằng suy đoán.

---

## 5. Điểm 3 — Ngưỡng: `max_suggested_terms_per_job = 40` và `min_occurrences = 3`

### 5.1. Tech Lead đã chốt con số, nhưng không có tiêu chí — và con số 40 đo ra là sai đòn bẩy

Số liệu quyết định (glossary coi là rỗng, spec + tokenizer đã sửa để công bằng):

| | Figoni (415 tr.) | Cauvain (298 tr.) |
|---|---|---|
| Term glossary user curate xuất hiện ≥3 lần | 60 | 29 |
| **Median tần suất** của các term đó | **13** | **11** |
| Tần suất thấp nhất lọt top-40 theo spec | ≥172 | ≥68 |
| Pool ứng viên sau 4 bộ lọc + khử lồng (min_occ=3) | 5.177 | 2.343 |
| **recall@40** (spec) | **1/60** | 5/29 |
| recall@100 | 8/60 | 6/29 |
| recall@300 | 11/60 | 9/29 |
| recall@500 | 18/60 | 14/29 |
| recall@1000 | 24/60 | 18/29 |
| recall@2000 | 38/60 | 25/29 |

Cùng bảng với xếp hạng "đặc thù × log(1+count)" + lọc tên riêng (biến thể tốt nhất tôi thử): recall@40 = 3/60, @300 = 19/60, @500 = 24/60, @1000 = 29/60, @2000 = 40/60. **Cải thiện có nhưng nhỏ; đường cong vẫn nói cùng một điều: term user muốn nằm rải rác từ hạng #11 đến #4438.**

Đọc ngược lại từ góc user: cắt 40 nghĩa là **user sẽ chỉ nhìn thấy `flour, sugar, flavor, chocolate, milk, dough, egg, baking, baked, cocoa, wheat, starch, butter, fruit, syrup, eggs, bread, cake, pastry, oven…`** — không có từ nào trong đó user từng thấy cần đưa vào glossary (glossary 114 entry hiện tại **không chứa** bất kỳ từ nào trong top-20 đó). Tính năng sẽ bị bỏ dùng sau cuốn đầu tiên — đúng kịch bản YA-4.2 của BA nhưng vì lý do khác.

### 5.2. `min_occurrences = 3`

- Figoni: 10 term glossary xuất hiện **đúng 2 lần**, 7 term 1 lần → mất 10/70 (14%) term "có mặt" chỉ vì ngưỡng.
- OCR 25 trang: chỉ 7 term ≥3 lần, **12 term xuất hiện đúng 1 lần** — với tài liệu ngắn (tạp chí, chương lẻ) ngưỡng 3 gần như xoá sạch.
- Ngược lại, luận điểm "lỗi OCR hiếm khi lặp 3 lần" (§6.18.7 mục 3) **sai với lỗi hệ thống**: `avor` x638, `rst` x147 — artifact trích xuất lặp hàng trăm lần. min_occ không phải phòng tuyến cho loại này; tokenizer (§2) mới là.

### 5.3. Đề xuất cách chốt

1. **Tách "trần lưu" khỏi "trần hiển thị"**: `extract_terms()` trả pool đã xếp hạng, lưu DB tới `max_suggested_terms_per_job = 500` (đo: recall@500 = 18–24/60 vs 1–3/60 ở 40; 500 dòng/job trong SQLite là không đáng kể — schema §6.18.3 không cần đổi). UI "Chờ duyệt" phân trang 40 dòng, có **sort** (tần suất / độ đặc thù / A→Z) và **lọc nhanh** (chỉ cụm ≥2 từ; chỉ dạng `-ing`; chỉ từ có dấu/ngoại lai) — 3 bộ lọc này bám đúng cấu trúc glossary thật (71% đa từ, 28 entry `-ing`, nhóm Pháp/Ý).
2. **`term_min_occurrences` theo độ dài tài liệu**: 3 nếu ≥100 trang (hoặc ≥50k token), 2 nếu dưới. Vẫn là 1 setting, thêm 1 setting `term_min_occurrences_short_doc = 2`.
3. **Golden metric = recall vs glossary user** (§1), chạy trên excerpt Figoni + Cauvain (fixture phải là trích đoạn, không nhúng nguyên sách vào repo). Mọi lần đổi ngưỡng/công thức sau này phải in ra bảng như §5.1. Script mô phỏng của tôi có thể làm hạt giống cho harness này.

---

## 6. Điểm 4 — Lọc trùng glossary (BR-TERM-02 / BR-GLOSS-02)

### 6.1. Case-insensitive: đúng ở tầng DB, sai ở tầng chuẩn hoá chuỗi

- DB có `idx_glossary_entries_term_nocase` (`COLLATE NOCASE`) và `_find_entry_in_scope()` dùng `func.lower(term_en) == term.lower()` → BR-GLOSS-02 **đúng** cho tra cứu 1 term.
- Nhưng §6.18.5 bước 3 định nghĩa `existing_terms = {term_en.lower()}` từ `GlossaryManager` — với glossary **thật** của user, **23/114 entry (20%)** có dạng `a / b` hoặc `x (ghi chú)`:
  `baking stone / pizza stone`, `bannetons / proofing basket`, `bloom (chocolate)`, `cocoa mass / cocoa liquor`, `Fahrenheit (°F)`, `fluid ounce (fl oz)`, `glaze / mirror glaze`, `knead / kneading`, `ounce (oz, khối lượng)`, `phyllo / filo dough`, `piping tip / nozzle`, `pound (lb)`, `proofer / proving drawer`, `retarding / cold retard`, `scaling (ingredients)`, `silicone mat / Silpat`, `Swiss meringue buttercream (SMBC)`, `tablespoon (tbsp)`, `teaspoon (tsp)`, `tempering (chocolate)`, `tempering (sugar)`, `turn (single/double/book fold)`, `whipping / whisking`.
  `.lower()` nguyên chuỗi **không bao giờ** bằng một n-gram. Đo trên Figoni với glossary thật: `pound` x112, `ounce` x92, `bloom` x56, `tempering` x32, `whipping` x40, `kneading` x15, `teaspoon` x11, `glaze` x8, `silpat`, `fahrenheit`, `knead`, `whisking`, `tablespoon` — **13 n-gram tương đương term đã có vẫn lọt vào "Chờ duyệt"**. Vi phạm trực tiếp AC thứ 2 của US-20.
- **Phạm vi**: §6.18.5 nói "liệt kê mọi `term_en` hiện có" — phải ghi rõ **global + project** (BR-GLOSS-06). `build_prompt_snippet()` đã có sẵn logic gộp 2 scope (`glossary_manager.py:151-158`) → tái dùng.

### 6.2. Số nhiều / số ít — nên coi là trùng, và hiện chưa

Với glossary thật áp vào, các n-gram sau vẫn được gợi ý: `crusts` x17, `meringues` x14, `mousses` x12, `glazes` x9, `fondants` x7, `folds` x3, `starters` x3 (Figoni); `meringues` x21 lọt top-40 Cauvain. Chiều ngược lại cũng có: glossary lưu `bannetons` (số nhiều), sách sẽ cho `banneton`.

Góc nghề: trong glossary bánh, số nhiều **không bao giờ** là term khác (`ganache`/`ganaches`, `éclair`/`éclairs`). Rủi ro của việc gộp là 0 vì gộp chỉ ảnh hưởng **việc ẩn gợi ý**, không ảnh hưởng dịch. → So khớp qua dạng chuẩn hoá nhẹ (strip `s`/`es`, `ies→y`) ở **cả hai phía** (glossary và ứng viên), và cũng dùng nó để gộp `flour/flours` trong chính pool (§4.1).

### 6.3. Phát hiện ngoài phạm vi — cùng điểm mù đang ship trong code dịch

`GlossaryManager._count_occurrences()` (`glossary_manager.py:22-26`) dùng `re.escape(term_en)` **thô** để lọc glossary theo tài liệu (§6.6.5, call site `prompt_builder.py:169-171`, full text từ `job_orchestrator.py:280`). Đo trên Figoni: chỉ **60/114** entry match; **23 entry dạng `/` `( )` ở trên match 0 lần** dù `tempering`, `pound`, `ounce`, `bloom`, `kneading`, `whipping` xuất hiện hàng chục lần → các entry này **không được inject vào prompt dịch**. Không thuộc US-20, nhưng cùng một fix: một hàm chung `glossary_match_forms(term_en) -> set[str]` (tách `/`, bỏ `( … )`, lowercase, chuẩn hoá số nhiều) dùng cho cả §6.6.5 lẫn §6.18. PM nên mở bug riêng.

---

## 7. Lineage (§6.18.5–6.18.6) — đồng ý, bổ sung 2 điều

- **Đồng ý** bảng nguồn `source_text` theo `file_type` và test R6-02 bắt buộc assert đúng `ocr_bridge_path`. Đây đúng bài học Bug #5.
- **Bổ sung 1 — nhánh Markdown**: `parse_only` đọc `document.md`; EPUB đọc `full_text()`. Bản OCR MinerU thật chứa `<table><tr><td>` (160 `<td>`, 53 `<tr>`) và `![](…jpg)` (16) → theo spec, top-4 là `td td td` x110, `td tr tr` x46, `tr tr td` x46, `td td tr` x42, `jpg` x16 (#22). Phải strip HTML/Markdown trước bước 1 (đã gộp vào §2 mục 5) và **fixture golden cho nhánh này phải chứa bảng HTML**.
- **Bổ sung 2 — nhánh `pdf_scan` `[CHƯA VERIFY]`**: DB hiện chỉ có 9 job `pdf_digital` completed, không còn `searchable.pdf` nào trên đĩa → tôi **chưa đo được** text layer của file cầu nối (`build_searchable_pdf()` dựng từ `middle.json`, không phải từ Markdown nên có thể sạch HTML, nhưng có thể mang lỗi OCR lặp kiểu `ganaehe`). Live E2E R6-03 của QA cho US-20 phải chạy 1 job `pdf_scan` thật và **mở danh sách gợi ý ra xem**, không chỉ tin có rows.

---

## 8. Những điểm Tech Lead làm đúng (đồng ý, kèm lý do)

| Quyết định | Vì sao đúng |
|---|---|
| Đổi khung: xếp hạng cho người duyệt, recall > precision, $0 mặc định (§6.18.1) | Đúng bản chất: chi phí false-positive = 1 cú bấm. Phản biện của tôi không bác khung này — chỉ chỉ ra cách thực thi hiện tại **không đạt recall** (1/60). |
| LLM gộp ≤40 term/1 request, hiện chi phí trước, đi qua `provider.translate()` để có token thật | Đúng Lớp 0 §6.11.4 và bài học $6.50. |
| **Không** cộng `translation_cost_usd` vào `job.actual_cost` | Đúng: trộn số đo thật vào tổng ước lượng phá ngữ nghĩa `cost_source`. |
| Chạy sau `run_job()` trả về, `try/except` riêng, không có đường nào đổi `job.status` | Đúng YA-4.5 / Protocol 6. |
| Thêm `suggested_terms` vào danh sách xoá thủ công, không tin `ON DELETE CASCADE` | Đúng — SQLite tắt FK mặc định; Tech Lead đã kiểm tra hành vi hiện tại của `DELETE /api/jobs/{id}`. |
| `promote` đi qua đúng `POST /api/glossary` để hưởng BR-GLOSS-07 | Đúng, tránh ghi đè âm thầm. |
| Bắt buộc golden file cho heuristic | Đúng — và §5.3 đề nghị metric cụ thể. |
| Tôn trọng BR-TERM-04 per-job như user chốt, chỉ ghi rủi ro | Đúng quy trình. §9 FD-8 bổ sung **số đo** để PM có căn cứ hỏi lại user, không tự đổi luật. |
| Gợi ý `(keep)` cho term gốc Pháp/Ý trong prompt LLM | Đúng BR-GLOSS-04 và YA-4.7. |

---

## 9. Final Decision (đề xuất — Tech Lead chốt FD-1..FD-6, PM/user chốt FD-7..FD-8)

**FD-1 — Viết lại bước 1 thành `normalize_source_text()` + tokenizer Unicode** theo 7 mục ở §2. Test đơn vị bắt buộc với đúng các chuỗi đo được: `ﬂ our`→`flour`, `emulsiﬁ ers`→`emulsifiers`, `baker’s`→`baker's`, `choco-\nlate`→`chocolate`, `pâte à choux` nguyên vẹn, `<td>flour</td>`→`flour`.

**FD-2 — Bộ lọc từ phổ thông**: chỉ áp cho 1-gram; ship kèm `baking_sense_allowlist.txt` (§3.3, Domain Expert soạn bản đầy đủ); Architecture.md ghi rõ **nguồn + version** của `en_common.txt`. Không tăng cỡ list để "lọc `flour`" — đo cho thấy tăng list giết thêm term EC-06 (§3.2).

**FD-3 — Thêm 4 rule làm sạch n-gram** (§4.1): (a) 3-gram có stopword giữa chỉ giữ khi token giữa ∈ `{of, à, de, en, au, aux}`; (b) gộp số ít/số nhiều trong pool và khi so glossary; (c) lọc tên riêng theo tỷ lệ viết hoa giữa câu ≥80% (cần ≥3 lần quan sát) + acronym toàn hoa; (d) term glossary tham gia làm "n-gram dài đã giữ" ở bước khử lồng nhau (sửa thứ tự bước 3/4).

**FD-4 — Chốt cách đọc bước 4**: ngưỡng 80% tính theo **một** n-gram dài duy nhất (max), không cộng dồn. Golden test: `gluten` x447 phải còn.

**FD-5 — Lọc trùng glossary**: hàm chung `glossary_match_forms(term_en)` (tách `/`, bỏ `(…)`, lowercase, chuẩn hoá số nhiều), dùng cho cả US-20 lẫn `_count_occurrences()`; `existing_terms` gộp scope global + project. Mở bug riêng cho §6.3.

**FD-6 — Ngưỡng**: `max_suggested_terms_per_job` = **500** là trần lưu; UI phân trang 40 + sort + 3 bộ lọc nhanh (§5.3); `term_min_occurrences` = 3 (≥100 trang) / 2 (<100 trang). Golden metric = recall vs glossary user trên excerpt Figoni + Cauvain, in bảng recall@40/100/300/500 mỗi lần đổi công thức. Công thức xếp hạng v1: giữ đơn giản (tần suất × trọng số n-gram như spec, hoặc biến thể "đặc thù × log(1+count)" nếu Tech Lead muốn — cải thiện đo được nhưng khiêm tốn, §5.1); **không** đầu tư ranking phức tạp trước khi có harness.

**FD-7 — (PM hỏi user) "Trần 40" → "pool + phân trang"**: đây là thay đổi hành vi so với PRD ("30–50 từ") nên cần user duyệt. Căn cứ: §5.1. Tuỳ chọn thêm, **không bắt buộc**: nút trả phí thứ hai "Lọc bằng LLM" chạy trên **pool** (không phải cả sách): pool Figoni 5.122 ứng viên ≈ 12k token input + ≈3k output. Giá DeepSeek fetch 2026-09-08 từ `api-docs.deepseek.com/quick_start/pricing` cho `deepseek-v4-flash` (model mặc định của `DeepSeekProvider`): input cache-miss $0.22–0.44/M, output $0.66–1.32/M → **≈ $0.005–0.01/cuốn** cho cả lọc + gợi ý bản dịch trong 1 request. `[CHƯA VERIFY]`: `Settings.deepseek_model` mặc định là `"deepseek-chat"` trong khi trang giá không còn liệt kê tên này — cần Tech Lead xác nhận alias trước khi ghi con số vào Architecture.md. Vẫn giữ nguyên BR-TERM-03 (mặc định $0).

**FD-8 — (PM hỏi user) Phạm vi BR-TERM-04, kèm số đo mới**: top-40 theo spec của Figoni và Cauvain (2 sách khác tác giả, khác nước, cách nhau 7 năm) **trùng nhau 17/40 dòng** (`dough, baking, flour, bread, cake, pastry, oven, sugar, baked, yeast, fruit, starch, ingredients, powder, flours, doughs, egg`). Với "Bỏ qua" per-job, user sẽ bấm bỏ cùng 17+ từ này ở **mọi** cuốn. Tech Lead đã nêu đúng đường lùi (`dismissed_terms(term_en)` toàn cục, §6.18.7 mục 1); đề nghị PM đưa con số này cho user quyết ngay từ v1 thay vì "sau 2-3 cuốn" — vì đây là 40% màn hình đầu tiên user nhìn thấy.

---

## Phụ lục A — Top-40 theo đúng spec §6.18.2 (glossary thật đã áp, cách đọc "max")

**Figoni**: sugar 887 · avor 638 · chocolate 581 · milk 556 · dough 554 · baked goods 360 · egg 535 · baking 517 · baked 510 · cocoa 445 · wheat 428 · starch 406 · butter 382 · fruit 363 · syrup 351 · eggs 344 · bread 332 · cake 287 · oven 277 · pastry 277 · fats 274 · ingredients 265 · yeast 259 · liquid 254 · gelatin 240 · proteins 238 · texture 226 · shortening 221 · powder 216 · grams 214 · vanilla 194 · doughs 193 · exercises and experiments 96 · flour 190 · formula 190 · nuts 178 · sugars 172 · appearance 171 · oils 171 · leavening 164.
→ Đánh giá nghề: đáng đưa vào glossary ≈ 3–4/40 (`shortening`, `leavening`, `gelatin`, có thể `baked goods`); 1 mảnh vỡ (`avor`); 10 cặp số ít/nhiều; 0 term trong glossary hiện tại của user thuộc top-20 này.

**Cauvain**: dough 531 · baking 520 · flour 389 · bread 313 · cake 309 · baking problems solved 129 · batter 228 · moisture 207 · pastry 203 · mixing 191 · cakes 187 · oven 183 · cauvain 178 · sugar 145 · baked 141 · yeast 132 · paste 126 · bakery 117 · carbon dioxide 69 · breadmaking 100 · fruit 99 · starch 97 · sponge 97 · formation 88 · bubbles 87 · ingredients 85 · gas retention 56 · powder 83 · blackie academic professional 41 · flours 81 · doughs 81 · filling 76 · moisture content 50 · chipping campden 49 · puff 70 · egg 70 · carbon dioxide gas 34 · fig 68 · technology of breadmaking 34 · cauvain and l 34.
→ Đáng glossary ≈ 3/40 (`gas retention`, `sponge`, `moisture content`); 6 slot tên sách/tác giả/nhà xuất bản; `puff` là mảnh của `puff pastry` đã có.

**OCR MinerU 25 trang**: td td td 110 · td tr tr 46 · tr tr td 46 · td td tr 42 · ingredients 50 · grams 45 · exercises and experiments 19 · flour 35 · bakeshop 32 · ounces 29 · bakers and pastry 14 · pastry chefs 17 · percentages 24 · discussion exercises 16 · experiments chapter 16 · baker's percentages 15 · formula 20 · tr td flour 10 · … · jpg 16 (#22).

## Phụ lục B — Hạng của 60 term glossary user trong pool Figoni (spec + tokenizer đã sửa, glossary coi là rỗng)

gluten #1(top40) · baking powder #43 · cocoa butter #44 · baking soda #45 · crumb #63 · meringue #84 · pound #89 · gluten development #99 · ounce #121 · crust #122 · bloom #250 · starch gelatinization #335 · whipping #370 · active dry yeast #433 · ganache #438 · fondant #445 · tempering #496 · puff pastry #649 · bulk fermentation #755 · pâte à choux #774 · crumb structure #822 · sponge cake #891 · instant yeast #990 · preferment #1088 · kneading #1206 · buttercream #1311 · mousse #1316 · oven spring #1329 · couverture chocolate #1345 · caramelization #1361 · swiss meringue #1566 · leavening agent #1576 · teaspoon #1599 · italian meringue #1723 · choux pastry #1728 · hydration #2188 · glaze #2241 · genoise #2653 · poolish #2652 · folding #2755 · levain #2937 · shaping #2961 · creaming method #2944 · soft peaks #2940 · rolling pin #3235 · piping #3940 · convection oven #4042 · dough hook #4098 · sourdough starter #4480 · tablespoon #4599 · fahrenheit #4866 · silpat #4880 · **bị bộ lọc phổ thông xoá**: room temperature (x95), cup (x42), turn (x40), proof box (x10) · **bị hấp thụ**: baker's percentage (x30, vào `grams baker's percentage`).

## Phụ lục C — Tái lập

```
# text thật (đã có trong scratchpad phiên này): figoni_full.txt, cauvain_full.txt, figoni_ocr_25p.md, glossary.txt
python3 sim_618.py full 3000 --strict                 # đúng spec, cách đọc "max"
python3 sim_618.py full 3000                          # đúng spec, cách đọc "sum"
python3 sim_618.py full 3000 --strict --norm --rows   # + tokenizer sửa (§2)
python3 sim_618.py full 3000 --strict --norm --key v2 --propn --rows   # + xếp hạng đặc thù + lọc tên riêng
python3 sim_618.py cauvain 3000 --strict --rows
python3 sim_618.py ocr 3000 --strict
```
