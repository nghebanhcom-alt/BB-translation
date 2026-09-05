"""Rate-limit signal detection + AIMD concurrency logic (Architecture.md 6.12.2-6.12.5).

Pure logic only — no I/O, no DB, no subprocess. `classify_chunk_outcome` and
`next_thread_count` are consumed by `job_orchestrator.py` (wiring is a
separate task per Architecture.md 6.12.10 step 3; NOT done here).
"""

import re
from enum import Enum

#: For rich, the "RateLimitError" fragment always sits at the start of the
#: message and is never wrapped/cut (verified Architecture.md 6.12.1 S10/S11).
#: Anchor only on this token, NOT on the full phrase "RateLimitError, retrying"
#: — that phrase has been split across lines when COLUMNS < 120.
RATE_LIMIT_LINE_RE = re.compile(r"RateLimitError", re.MULTILINE)


class ChunkOutcome(Enum):
    """Classification of one pdf2zh chunk run (Architecture.md 6.12.4 table)."""

    SUCCESS = "success"
    SLOW_SUCCESS = "slow_success"
    RATE_LIMITED = "rate_limited"
    TIMEOUT_SIGNALLED = "timeout_signalled"
    TIMEOUT_SILENT = "timeout_silent"
    ERROR = "error"


#: Starting `--thread` value per provider when `(provider, model)` has no
#: `ConcurrencyState` history yet (Architecture.md 6.12.5). `gemini` stays at
#: the conservative default because its real 429 behaviour through the
#: OpenAI-compat layer is unverified (6.12.6 spike INCONCLUSIVE — no
#: GEMINI_API_KEY configured) and it still runs live AIMD ramp-up, where a
#: wrong floor compounds fastest right when confidence is lowest.
#: `claude` = 8 is a user risk-acceptance override (2026-09-06), NOT a
#: verified value — the 6.12.6 spike for Claude also did not pass (blocked by
#: an invalid `CLAUDE_API_KEY` placeholder, 0 real signal observed). Safe to
#: accept here specifically because AIMD stays disabled for claude (thread
#: never ramps past this fixed value), and `chunk_size` cold-start (6.12.7)
#: still gates the first 3 chunks at 20 pages regardless of this floor,
#: bounding the blast radius of an unverified value. Revert to 4 (or verify
#: properly per 6.12.6) once a real `CLAUDE_API_KEY` is available.
ADAPTIVE_THREAD_FLOOR: dict[str, int] = {
    "deepseek": 8,
    "openai": 8,
    "gemini": 4,
    "claude": 8,
}

#: Hard ceiling shared by every provider (Architecture.md 6.12.5). Not derived
#: from provider quotas (all far higher) but from BB-Translation's own cost
#: accumulator + memory budget: `max_concurrent_files=3` * 32 = 96 in-flight
#: requests app-wide is the accepted "overshoot" of the running cost check.
ADAPTIVE_THREAD_CEILING = 32

#: So lan 429 that ma SDK `openai` (dung ben trong babeldoc) nuot ngam truoc
#: khi tenacity thay duoc exception va log ra 1 dong "RateLimitError"
#: (Architecture.md 6.14.5). Do that, khong phai suy dien: ep 40 lan 429 that
#: qua CLI babeldoc that -> dem duoc 12 dong log (6.14.1 B10/B11), ty le
#: 40/12 = 3.33 khop `1 + DEFAULT_MAX_RETRIES = 3` (B3). Hien khong dung truc
#: tiep trong `next_thread_count()` (thuat toan AIMD giu nguyen) — day la con
#: so tham chieu cho `BABELDOC_THREAD_FLOOR` va cho QA/Tech Lead tune tiep sau
#: 6.14.6, KHONG phai he so nhan vao `rate_limit_hits` o dau do trong code.
BABELDOC_RATE_LIMIT_UNDERCOUNT_FACTOR = 3

#: Floor rieng cho engine babeldoc = ceil(floor_pdf2zh / 2) (Architecture.md
#: 6.14.5 muc 2) — "danh doi dung 1 vong quan sat" de bu cho do nhay tin hieu
#: bi mat do SDK openai tu nuot ~3 lan 429 truoc khi tenacity thay duoc
#: (BABELDOC_RATE_LIMIT_UNDERCOUNT_FACTOR). KHONG dùng `floor / 3` — he so 3
#: do luong so 429 bi nuot, khong phai so luong an toan de chia thread.
#: ⚠️ ASSUMED can tune lai bang du lieu that o QA gate 6.14.6 (server gia
#: 429 100% la truong hop cuc doan, khac rate-limit that rai rac cua provider).
BABELDOC_THREAD_FLOOR: dict[str, int] = {
    "deepseek": 4,
    "openai": 4,
    "gemini": 2,
    "claude": 4,
}


def classify_chunk_outcome(
    *,
    exit_code: int | None,
    rate_limit_hits: int,
    duration_seconds: float,
    timeout_seconds: float,
) -> ChunkOutcome:
    """Classify one chunk's result per the Architecture.md 6.12.4 table.

    `exit_code=None` means the chunk timed out (`Pdf2zhTimeoutError` carries
    no exit code — the process was killed, not exited) and takes precedence
    over `duration_seconds`, which is meaningless past a timeout.
    """
    timed_out = exit_code is None

    if timed_out:
        return (
            ChunkOutcome.TIMEOUT_SIGNALLED if rate_limit_hits >= 1 else ChunkOutcome.TIMEOUT_SILENT
        )

    if rate_limit_hits >= 1:
        return ChunkOutcome.RATE_LIMITED

    if exit_code != 0:
        return ChunkOutcome.ERROR

    # exit_code == 0 and rate_limit_hits == 0: success or slow_success hinges
    # on the 0.75 * timeout safety margin (6.12.4) — right at the boundary
    # still counts as success, only strictly past it is "sat mep vuc".
    if duration_seconds <= 0.75 * timeout_seconds:
        return ChunkOutcome.SUCCESS
    return ChunkOutcome.SLOW_SUCCESS


def next_thread_count(outcome: ChunkOutcome, current_thread: int, floor: int) -> int:
    """Apply the AIMD delta for `outcome` and clamp to [floor, ceiling].

    +2 additive increase on success (not +1: an observation here costs a
    whole 10-40 minute chunk, +1 would need 12 chunks to reach the ceiling
    from floor 8 — never converges within a book; not multiplicative: a
    x1.5+ jump near the ceiling risks overshooting the real breaking point
    in one step, defeating the reason AIMD picks additive increase).
    x0.5 multiplicative decrease on a real overload signal (classic AIMD
    beta=0.5: reaches floor from ceiling in log2(32/8)=2 steps, fast enough
    to not burn dozens of retries). Everything else HOLDs — see the table
    in Architecture.md 6.12.4 for why (silent timeout / plain error must
    not be treated as a concurrency signal).
    """
    if outcome is ChunkOutcome.SUCCESS:
        delta = 2
    elif outcome in (ChunkOutcome.RATE_LIMITED, ChunkOutcome.TIMEOUT_SIGNALLED):
        return max(floor, current_thread // 2)
    else:
        delta = 0

    return min(ADAPTIVE_THREAD_CEILING, current_thread + delta)
