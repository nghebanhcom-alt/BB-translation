"""Ollama local provider — REST API via `httpx` (Architecture.md section 6.6).

Local + free, so cost is always $0. No auth concept for a local Ollama
server, so `AuthenticationError` is never raised here; a permanent 4xx (not
429) response maps to `TranslationProviderError`, and HTTP 429 (if the local
server is proxied/rate-limited) maps to `RateLimitError`.

Y6 fix (Architecture.md 6.20.12, US-22 buoc 2/3): truoc day MOI loi transport
(`httpx.HTTPError` — bao gom ca timeout, connection refused, DNS...) VA moi
status 5xx deu bi map thanh `TranslationProviderError` (permanent),
`with_retry()` khong bao gio thu lai — dung loai loi ha tang binh thuong ma
Y6 noi toi ("1 loi 502 lam job failed"), ap dung ca cho Ollama du day la
server local (van co the tam thoi qua tai/khoi dong lai).
"""

import httpx

from src.services.translation import RateLimitError, TranslationProviderError, TranslationResult


class OllamaProvider:
    """Calls the Ollama REST API (`/api/generate`) on `OLLAMA_ENDPOINT`."""

    provider_name = "ollama"

    def __init__(
        self,
        endpoint: str,
        model: str = "gemma2:27b",
        max_tokens: int = 8192,
        temperature: float = 0.3,
        timeout_seconds: float = 300.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds

    async def translate(
        self,
        text: str,
        glossary_prompt: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        prompt = (
            f"{glossary_prompt}\n\n"
            f"Translate from {source_lang} to {target_lang}:\n\n{text}"
        )

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{self._endpoint}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": self._temperature,
                            "num_predict": self._max_tokens,
                        },
                    },
                )
            except httpx.TimeoutException as exc:
                raise TimeoutError(f"Ollama request timed out: {exc}") from exc
            except httpx.HTTPError as exc:
                # Con lai sau khi TimeoutException da bat rieng o tren: loi
                # ket noi/transport (ConnectError, RemoteProtocolError...).
                raise ConnectionError(f"Ollama request failed: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError(f"Ollama rate limit exceeded: {response.text}")
        if response.status_code >= 500:
            # Y6: loi ha tang binh thuong o may chu (local hoac proxy) —
            # transient, khong phai permanent nhu 1 4xx khac.
            raise ConnectionError(
                f"Ollama server error (5xx) — status {response.status_code}: {response.text}"
            )
        if response.status_code != 200:
            raise TranslationProviderError(
                f"Ollama returned status {response.status_code}: {response.text}"
            )

        payload = response.json()
        translated_text = payload.get("response", "")
        input_tokens = payload.get("prompt_eval_count", 0) or 0
        output_tokens = payload.get("eval_count", 0) or 0

        return TranslationResult(
            text=translated_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self.estimate_cost(input_tokens, output_tokens),
            provider_name="ollama",
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return 0.0
