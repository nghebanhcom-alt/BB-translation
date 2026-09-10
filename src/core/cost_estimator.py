"""Estimate translation job cost before running it (PRD R-01: "Hiển thị
estimated cost trước khi dịch") and per-chunk cost after the fact
(Architecture.md 6.6.6 — pdf2zh never reports real token usage, so both are
estimates, never metered numbers).

`estimate_job_cost()` below is the ORIGINAL (pre-6.11) pre-job heuristic —
kept only for backward compatibility (Architecture.md 6.11.4 Lop 1: "giu
nguyen ... de tuong thich nguoc neu cho nao dang goi"). It must NEVER be
wired into a real API path again: `AVG_INPUT_TOKENS_PER_PAGE=500` is the
root cause (RC-2) of the $6.50 real-money incident investigated in
Architecture.md 6.11 — it underestimated real cost by 8.4x because it has no
idea pdf2zh resends the whole prompt file per segment (F6, ~85% of real
cost). Every real call site must use `estimate_job_cost_v2()` instead.
"""

from dataclasses import dataclass

from src.services.translation import TranslationProvider

#: Heuristic average input tokens per page for a typical baking book/magazine
#: page (mixed prose + recipe tables). Not measured from real documents yet —
#: refine once actual job data is available.
#: DEPRECATED (Architecture.md 6.11.3 RC-2) — this constant is the root cause
#: of the $6.50 real-money incident (underestimated real cost 8.4x because it
#: has no idea pdf2zh resends the whole prompt file per segment). Do not use
#: it in any new code; see `estimate_job_cost_v2()` below.
AVG_INPUT_TOKENS_PER_PAGE = 500

#: BR-FONT-03: target VI translation length <= 130% of EN source length,
#: used here as an output/input token ratio heuristic.
OUTPUT_TO_INPUT_TOKEN_RATIO = 1.3

#: Architecture.md 6.6.6 default heuristic: ~4 EN characters per token.
CHARS_PER_TOKEN_EN = 4.0

#: Architecture.md 6.11.4 Lop 1 — measured directly from the real pdf2zh
#: cache backing the $6.50 incident (Architecture.md 6.11.2, S1;
#: tests/fixtures/pdf2zh/cost_golden_howbakingworks.json): Vietnamese output
#: (co dau) tokenizes at ~2.0 chars/token under cl100k_base, NOT 4.0 like
#: English — using the EN ratio for VI output is part of why the old
#: `estimate_chunk_cost()` output figure (before this incident) undercounted.
CHARS_PER_TOKEN_VI = 2.0

#: Architecture.md 6.11.4 Lop 1 — measured: 809,717 translated chars /
#: 699,103 source chars from the same real job (S1). Rounded UP slightly
#: from the raw 1.158 measurement so `estimate_job_cost_v2()` stays on the
#: safe (over-estimate) side of Architecture.md 6.11.6's golden-file bound —
#: an estimator that can underestimate real spend is exactly what caused the
#: incident this section exists to prevent.
VI_CHAR_EXPANSION = 1.16

#: Architecture.md 6.20.13.3b (fix C-3, Bug #EPUB-B2-1) — heuristic phat
#: hien 1 request LLM sinh output "runaway" (du/lap) so voi CHINH payload
#: cua request do. ⚠️ ASSUMED, chi co 1 diem du lieu (xem ly do chon o
#: Architecture.md 6.20.13.3b): muc ky vong = `payload_chars * VI_CHAR_EXPANSION
#: / CHARS_PER_TOKEN_VI`; tran vat ly `max_tokens=8192` -> ti le toi da 1
#: request day co the dat la ~4,7x, chon 3,0x de kich hoat TRUOC khi cham
#: tran ma van con bien so voi dao dong binh thuong (uoc luong von da CAO).
EPUB_RUNAWAY_OUTPUT_FACTOR = 3.0
#: Chong false-positive o payload nho (vd 1 request retry rieng le chi 1
#: unit ngan) — muc ky vong qua thap se lam moi dao dong nho bi bao runaway.
EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS = 1_500


def epub_expected_output_tokens(payload_chars: int) -> int:
    """Muc output token KY VONG cho 1 request EPUB voi payload dai
    `payload_chars` ky tu — CHIA SE cong thuc voi `is_runaway_output()` va
    voi caller can log ti le thuc (Architecture.md 6.20.13.3b: "dung DUNG 2
    hang so cua estimator ... khong duoc viet cong thuc thu hai")."""
    return int(payload_chars * VI_CHAR_EXPANSION / CHARS_PER_TOKEN_VI)


def is_runaway_output(payload_chars: int, output_tokens: int) -> bool:
    """True khi `output_tokens` vuot xa muc ky vong cho CHINH payload nay
    (Architecture.md 6.20.13.3b). Dung DUNG 2 hang so cua estimator
    (`VI_CHAR_EXPANSION`, `CHARS_PER_TOKEN_VI`) qua `epub_expected_output_tokens()`
    — khong duoc viet cong thuc thu hai.
    """
    expected = epub_expected_output_tokens(payload_chars)
    return output_tokens > max(
        EPUB_RUNAWAY_OUTPUT_FACTOR * expected, EPUB_RUNAWAY_OUTPUT_FLOOR_TOKENS
    )


@dataclass
class CostEstimate:
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    provider_name: str
    #: Always "estimated" in v1.0 — pdf2zh does not surface real token usage
    #: (Architecture.md 6.6.6). Kept as a field (not a bare constant) so callers
    #: writing this onto `Job.cost_source` don't have to know that fact themselves.
    cost_source: str = "estimated"


def estimate_job_cost(total_pages: int, provider: TranslationProvider) -> CostEstimate:
    """Heuristic cost estimate: ~500 input tokens/page, output ~130% of input
    (BR-FONT-03 conciseness target), priced via `provider.estimate_cost()`.

    Used pre-job (Settings "estimate cost" flow, Architecture.md 6.6.2 R3.1) —
    `provider` here is always the out-of-band `TranslationProvider`, never the
    pdf2zh render path.
    """
    if total_pages < 0:
        raise ValueError("total_pages must be >= 0")

    estimated_input_tokens = total_pages * AVG_INPUT_TOKENS_PER_PAGE
    estimated_output_tokens = int(estimated_input_tokens * OUTPUT_TO_INPUT_TOKEN_RATIO)
    estimated_cost_usd = provider.estimate_cost(estimated_input_tokens, estimated_output_tokens)

    provider_name = getattr(provider, "provider_name", provider.__class__.__name__)

    return CostEstimate(
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        provider_name=provider_name,
    )


def _estimate_input_tokens(
    source_text_chars: int, segment_count: int, prompt_overhead_chars: int
) -> int:
    """Shared core of the input-token formula (Architecture.md 6.11.3/6.11.4:
    `estimate_chunk_cost()` and `estimate_job_cost_v2()` "phai dung chung 1
    ham loi" — pdf2zh re-sends the whole prompt file for every segment
    (F6, ~85% of the real $6.50 incident's cost), so the overhead term is
    multiplied by `segment_count`, not added once.
    """
    return int(
        source_text_chars / CHARS_PER_TOKEN_EN
        + segment_count * prompt_overhead_chars / CHARS_PER_TOKEN_EN
    )


def estimate_chunk_cost(
    source_text: str,
    segment_count: int,
    prompt_overhead_chars: int,
    provider: TranslationProvider,
    vi_expansion: float = 1.3,
    vi_token_factor: float = 1.5,
) -> tuple[int, int, float]:
    """Post-render, per-chunk cost estimate (Architecture.md 6.6.6).

    pdf2zh calls the LLM itself and never reports token usage back to us, so
    this is a UOC LUONG (estimate) derived from text length, not a metered
    count — do not present it as an exact figure. `prompt_overhead_chars` is
    `len(prompt_file_content) - len("${text}")`: since pdf2zh re-sends the
    whole prompt file for every segment (Architecture.md 6.6.1 F6), that
    overhead is multiplied by `segment_count`, not added once.

    `provider` is used ONLY for `estimate_cost()` (pure arithmetic, no API
    call) — Architecture.md 6.6.2 R3.1, the same out-of-band role as
    `estimate_job_cost()`.

    Returns `(input_tokens, output_tokens, cost_usd)`.
    """
    input_tokens = _estimate_input_tokens(len(source_text), segment_count, prompt_overhead_chars)
    output_tokens = int(len(source_text) * vi_expansion * vi_token_factor / CHARS_PER_TOKEN_EN)
    cost_usd = provider.estimate_cost(input_tokens, output_tokens)
    return input_tokens, output_tokens, cost_usd


def estimate_job_cost_v2(
    source_text_chars: int,
    segment_count: int,
    prompt_overhead_chars: int,
    provider: TranslationProvider,
) -> CostEstimate:
    """Pre-job cost estimate (Architecture.md 6.11.4 Lop 1) — REPLACES
    `estimate_job_cost()` for every real call site (`POST /api/estimate`,
    `GET /api/jobs/{id}/cost-estimate`, the Lop 2 pre-flight gate). Shares
    the input-token formula with `estimate_chunk_cost()` via
    `_estimate_input_tokens()` (Architecture.md 6.11.4 point 3 — two parallel
    formulas is a Reviewer-reject condition), because the pre-job and
    post-render estimates diverging is exactly RC-2 of the $6.50 incident.

    `segment_count` MUST come from `_count_text_segments()` over the real
    page range (Architecture.md 6.11.5 data lineage step 3), never guessed
    from page count alone — that guess is what `estimate_job_cost()` did and
    is the root cause this function exists to fix.

    `prompt_overhead_chars` MUST be measured from a real prompt built with
    THIS document's filtered glossary (`build_prompt_text()`), never a
    constant — a full 80-entry glossary swells the prompt ~3.4x (Architecture.md
    6.11.3 RC-1), so a constant here would reintroduce the same underestimate
    this section exists to close.

    Verified against `tests/fixtures/pdf2zh/cost_golden_howbakingworks.json`
    (Architecture.md 6.11.6): must land in [1.0x, 1.6x] of the real token
    count from that incident — allowed to over-estimate, never to under.
    """
    if source_text_chars < 0:
        raise ValueError("source_text_chars must be >= 0")
    if segment_count < 0:
        raise ValueError("segment_count must be >= 0")

    input_tokens = _estimate_input_tokens(source_text_chars, segment_count, prompt_overhead_chars)
    output_tokens = int(source_text_chars * VI_CHAR_EXPANSION / CHARS_PER_TOKEN_VI)
    estimated_cost_usd = provider.estimate_cost(input_tokens, output_tokens)

    provider_name = getattr(provider, "provider_name", provider.__class__.__name__)

    return CostEstimate(
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        provider_name=provider_name,
    )
