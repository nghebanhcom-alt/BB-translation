# Spike: Claude (openailiked) rate-limit signal — R5-02, Architecture.md 6.12.6

## Ket qua: FAIL (khong phai PASS/FAIL "chuan" theo dinh nghia goc — xem "Root cause" duoi day)

## Thong tin lan chay

- Ngay: 2026-09-05
- pdf2zh: v1.9.11
- Model: `claude-haiku-4-5-20251001` (model RE NHAT theo yeu cau gioi han chi phi cua spike nay,
  KHONG dung `settings.claude_model` mac dinh `claude-sonnet-4-5-20250514`)
- Lenh: `pdf2zh <10-page sample> -s openailiked:claude-haiku-4-5-20251001 --thread 64` voi
  `COLUMNS=200`, `OPENAILIKED_BASE_URL=https://api.anthropic.com/v1/`,
  `OPENAILIKED_STREAM=false`, `OPENAILIKED_MAX_TOKENS=8192`
- Input: 10 trang cat tu trang 6-15 (0-index 5-14) cua
  "Figoni, Paula - How baking works... - libgen.li.pdf" (`data/uploads/`), luu tam thoi o
  scratchpad, KHONG ghi de file goc, da xoa sau khi xong.
- So lan thu: **1/3** (dung som — xem ly do duoi)
- Chi phi thuc te: **$0.00 USD** — moi request bi Anthropic tu choi o buoc xac thuc (HTTP 401)
  truoc khi model xu ly bat ky token nao, nen khong phat sinh billing.

## Quan sat

- `grep -c "401 Unauthorized" stdout.txt` = 1081 dong log HTTP.
- `grep -c "RateLimitError" stdout.txt stderr.txt` = 0/0 — khong co bat ky dong nao khop
  `RATE_LIMIT_LINE_RE`.
- Moi response tu `api.anthropic.com` co body:
  `{'error': {'code': 'authentication_error', 'message': 'Invalid Anthropic API Key', 'type': 'invalid_request_error', ...}}`
  qua lop `openailiked` (log tai `pdf2zh.converter`, `converter.py:357`).
- Khong co crash tien trinh; pdf2zh tu bat loi tung doan van va tiep tuc doan ke tiep (khong
  dung retry decorator cua S3 vi day khong phai `openai.RateLimitError`).

## Root cause — BLOCKER, khong phai ket luan ve rate-limit

`CLAUDE_API_KEY` trong `.env` cua may nay la **placeholder/khong hop le** (do dai 13 ky tu —
mot Anthropic API key that co dang `sk-ant-api03-...` dai ~100+ ky tu). Vi vay:

- Spike **chua bao gio cham toi** cau hoi can tra loi ("Anthropic OpenAI-compat 429 co duoc
  SDK `openai` phan loai dung thanh `openai.RateLimitError` hay khong" — 6.12.6). Moi request
  bi chan o buoc xac thuc, truoc ca khi co co hoi bi rate-limit.
- Day khong phai ket qua PASS (khong co dong RateLimitError) cung khong phai INCONCLUSIVE dung
  nghia (INCONCLUSIVE gia dinh request *hop le* nhung khong cham rate limit sau 3 lan thu tang
  thread — o day request khong hop le ngay tu dau, tang `--thread` len 128/256 se KHONG thay
  doi ket qua vi loi xay ra o tang xac thuc, truoc ca tang concurrency).
- Xep vao **FAIL** theo tinh chat "tra loi bat thuong" (buoc 5 cua spec 6.12.6: "process crash
  hoac tra loi bat thuong"): nhan duoc 401 hang loat thay vi 200/429 la bat thuong doi voi 1
  spike ky vong do that connectivity/rate-limit that.

## Hanh dong da thuc hien

- **KHONG** thu lai voi `--thread` 128/256: ket qua se giong het (loi xay ra truoc buoc gui
  payload dich, tang thread khong thay doi duong dan loi). Thu them chi ton thoi gian, khong
  sinh them thong tin — trai voi tinh than "toi da 3 lan" cua spec (spec gia dinh moi lan thu
  co the cho ket qua khac nhau).
- **KHONG** sua `docs/Architecture.md` (S6/6.12.1, 6.12.6, 6.12.10 giu nguyen `[UNVERIFIED]`).
- **KHONG** sua `ADAPTIVE_THREAD_FLOOR["claude"]` hay bo khoa AIMD trong
  `src/core/job_orchestrator.py` — Claude giu nguyen thread co dinh = 4.
- Escalate len Tech Lead / nguoi dung: can 1 `CLAUDE_API_KEY` **that, hop le** (co the dung
  key that voi han muc/budget rat thap, hoac 1 key test da het quota that de kiem tra dung
  hanh vi 429) de chay lai spike nay. Neu dung key that con quota, nen giu nguyen `--thread 64`
  va nguong chi phi $1 nhu thiet ke goc.

## File dinh kem

- `stdout.txt` — toan bo stdout that cua lan chay (3247 dong, khong sua).
- `stderr.txt` — toan bo stderr that cua lan chay (2 dong — tqdm progress bar + 1 canh bao
  resource_tracker khong lien quan).

KHONG chua gia tri `CLAUDE_API_KEY` that trong bat ky file nao o day — response 401 chi log
thong bao loi, khong echo lai key.
