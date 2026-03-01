"""Multi-provider LLM client.

``LLMClient`` centralises API-key management and provides a single
``generate`` method that the rest of the codebase calls.  Supports
OpenAI, Anthropic (Claude), MiniMax, Kimi (Moonshot), and Qwen
(DashScope).  MiniMax, Kimi, and Qwen use OpenAI-compatible APIs;
only Anthropic requires its own SDK.

If no API key is configured the ``available`` property returns ``False``
and all downstream code gracefully falls back to template-based output.
"""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from bio_search.config import Settings

logger = logging.getLogger(__name__)

PROVIDER_DEFAULTS: dict[str, dict[str, str | None]] = {
    "openai": {"base_url": None, "model": "gpt-4o-mini"},
    "anthropic": {"base_url": None, "model": "claude-sonnet-4-20250514"},
    "minimax": {"base_url": "https://api.minimax.chat/v1", "model": "abab6.5s-chat"},
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-turbo",
    },
}

SUPPORTED_PROVIDERS = list(PROVIDER_DEFAULTS.keys())


class LLMClient:
    """Multi-provider LLM API client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._provider = self.settings.llm_provider.lower()

        if self._provider not in PROVIDER_DEFAULTS:
            logger.warning(
                "Unknown LLM provider %r, falling back to 'openai'",
                self._provider,
            )
            self._provider = "openai"

        defaults = PROVIDER_DEFAULTS[self._provider]
        self._default_model: str = self.settings.llm_model or defaults["model"]  # type: ignore[assignment]

        # Resolve API key: llm_api_key takes precedence, fall back to
        # openai_api_key when provider is openai (backward compat).
        api_key = self.settings.llm_api_key
        if not api_key and self._provider == "openai":
            api_key = self.settings.openai_api_key

        if not api_key:
            self.client = None
            return

        if self._provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic

                self.client = AsyncAnthropic(api_key=api_key)
            except ImportError:
                logger.error(
                    "anthropic package not installed. "
                    "Install it with: pip install 'bio-search[anthropic]'"
                )
                self.client = None
        else:
            # OpenAI-compatible providers (openai, minimax, kimi, qwen)
            base_url = self.settings.llm_base_url or defaults["base_url"]
            kwargs: dict = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = AsyncOpenAI(**kwargs)

    @property
    def provider(self) -> str:
        """Return the configured provider name."""
        return self._provider

    @property
    def default_model(self) -> str:
        """Return the default model for the configured provider."""
        return self._default_model

    @property
    def available(self) -> bool:
        """Return ``True`` when a valid API key has been configured."""
        return self.client is not None

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Send a chat-completion request and return the assistant text.

        Raises:
            RuntimeError: If no LLM API key is configured.
        """
        if not self.available:
            raise RuntimeError("LLM API key not configured")

        model = model or self._default_model

        if self._provider == "anthropic":
            return await self._generate_anthropic(
                prompt, system=system, model=model,
                temperature=temperature, max_tokens=max_tokens,
            )

        return await self._generate_openai(
            prompt, system=system, model=model,
            temperature=temperature, max_tokens=max_tokens,
        )

    async def _generate_openai(
        self,
        prompt: str,
        system: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """OpenAI-compatible chat completion (works for openai, minimax, kimi, qwen)."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def _generate_anthropic(
        self,
        prompt: str,
        system: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Anthropic Messages API completion."""
        kwargs: dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system

        response = await self.client.messages.create(**kwargs)
        return response.content[0].text
