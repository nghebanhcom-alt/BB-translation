# RichHandler-wrapped `RateLimitError` line — verified output, NOT a real DeepSeek 429

`stdout.txt` in this directory is copied VERBATIM from `docs/Architecture.md` section 6.12.2
(the second code block, right under "Sai ca khi da doc dung stream. Khi stdout khong phai TTY,
rich wrap o 80 cot..."). That output is real — the Tech Lead ran `rich.logging.RichHandler`
directly (Architecture.md 6.12.1 S9-S11: `~/.local/share/uv/tools/pdf2zh/bin/python -c "..."`
piped through a non-TTY stdout, `wc -c` verified) — but it is a **synthetic** log line the Tech
Lead generated on purpose to verify how `rich` wraps text at 80 columns, NOT output captured
from a real `openai.RateLimitError` raised by a live DeepSeek 429 response.

## Why this exists instead of a real 429 golden file

Protocol 5 mục 3 (CLAUDE.md) forbids hand-writing a `"RateLimitError..."` fixture string from
assumption. The team tried twice to capture a REAL DeepSeek 429 golden file and both attempts
came back INCONCLUSIVE (never triggered a real rate limit) — see:

- `tests/fixtures/pdf2zh/deepseek_ratelimit/README.md` (3 real `pdf2zh` runs at
  `--thread` 64/128/256, all 200 OK)
- `tests/fixtures/pdf2zh/deepseek_ratelimit/direct_sdk_spike.md` (direct `openai` SDK spike,
  300→2600 concurrent requests, only ever saw `APITimeoutError`, never `RateLimitError`)

Since a real 429 golden file does not exist yet, this fixture uses the one piece of REAL
(not hand-typed) `RichHandler` output the project already has on record — the exact wrapped
shape a `RateLimitError` warning takes when it does occur — captured from an actual run
rather than typed from memory. It is used ONLY to exercise `RATE_LIMIT_LINE_RE` / the AIMD
rate-limit counting path in unit tests, never to claim DeepSeek's 429 behavior itself has
been verified.

## Explicit label (do not remove)

Any test consuming `stdout.txt` from this directory must say, in a comment next to the
constant that loads it:

> Noi dung nay la output that cua RichHandler khi log dong RateLimitError (verified 6.12.2
> S9-S11), KHONG phai tu 1 lan 429 that cua DeepSeek — golden file that cho truong hop do
> van dang INCONCLUSIVE (xem tests/fixtures/pdf2zh/deepseek_ratelimit/).
