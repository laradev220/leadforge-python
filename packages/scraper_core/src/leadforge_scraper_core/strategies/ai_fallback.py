"""AIFallbackStrategy — last-resort extraction using a cheap LLM.

Only invoked when:
  1. All other strategies returned None
  2. The page contains clear business signals (name, address, phone keywords)
  3. We have not exceeded the global AI fallback budget (≤5% of pages)

The budget is tracked via a Redis counter so it is shared across workers.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from leadforge_scraper_core.strategies.base import (
    ExtractionStrategy,
    StrategyResult,
)

# Global budget: track AI fallback invocations in Redis
_BUDGET_KEY = "scraper:ai_fallback_budget"
_BUDGET_TOTAL = 1000  # per-window
_BUDGET_WINDOW = 3600  # 1-hour window

# Business signal keywords that indicate the page is worth AI analysis
_BUSINESS_SIGNALS = [
    "business",
    "company",
    "office",
    "store",
    "shop",
    "restaurant",
    "service",
    "location",
    "contact us",
    "about us",
    "address",
    "phone",
    "director",
    "manager",
    "founder",
    "ceo",
]


class AIFallbackStrategy(ExtractionStrategy):
    """Last-resort strategy — uses GPT-4o mini to extract business data."""

    name = "ai_fallback"
    priority = 99  # lowest — runs last
    is_fallback = True

    # Minimal prompt for fast, cheap extraction
    _SYSTEM_PROMPT = (
        "You are a business data extraction assistant. Extract structured "
        "business information from the provided HTML page content. "
        "Return ONLY valid JSON with keys: name, phone, email, address, website, category. "
        "Use null for missing fields. Do not include any text outside the JSON."
    )

    _USER_PROMPT_TEMPLATE = (
        "Extract business information from this HTML page (first 8000 chars):\n\n{content}\n\n"
        'Return JSON only. Example: {{"name": "Acme Corp", "phone": "+1 555-1234", '
        '"email": null, "address": "123 Main St", "website": "https://acme.com", '
        '"category": "Restaurant"}}'
    )

    def can_handle(self, html: str) -> bool:
        """Only offer to handle pages with clear business signals."""
        lower = html.lower()
        signal_count = sum(1 for s in _BUSINESS_SIGNALS if s in lower)
        return signal_count >= 2

    async def extract(
        self,
        html: str,
        url: str,
        *,
        logger: Any = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> StrategyResult | None:
        """Call GPT-4o mini to extract business data from the page."""

        # Check global budget (enforced via Redis)
        budget_ok = await self._check_budget(logger)
        if not budget_ok:
            if logger:
                logger.info("ai_fallback.skipped_budget_exceeded", url=url)
            return None

        # Prepare content (first 8000 chars to save tokens)
        content = html[:8000]
        user_prompt = self._USER_PROMPT_TEMPLATE.format(content=content)

        try:
            response = await self._call_llm(user_prompt, http_client=http_client)
            if not response:
                return None

            import json

            data = json.loads(response)

            result = StrategyResult(strategy_name=self.name)
            result.name = data.get("name")
            result.phone = data.get("phone")
            result.email = data.get("email")
            result.address = data.get("address")
            result.website = data.get("website")
            result.category = data.get("category")
            result.confidence = 60  # AI is less reliable than structured data
            return result

        except json.JSONDecodeError as exc:
            if logger:
                logger.warning("ai_fallback.json_parse_failed", url=url, error=str(exc))
            return None
        except Exception as exc:
            if logger:
                logger.warning("ai_fallback.call_failed", url=url, error=str(exc))
            return None

    async def _check_budget(self, logger: Any) -> bool:
        """Check Redis budget counter, return False if exhausted."""
        try:
            import redis.asyncio as redis

            client = redis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                decode_responses=True,
            )
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            key = f"{_BUDGET_KEY}:{int(loop.time()) // _BUDGET_WINDOW}"
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, _BUDGET_WINDOW)
            await client.aclose()
            return count <= _BUDGET_TOTAL
        except Exception as exc:
            if logger:
                logger.warning("ai_fallback.budget_check_failed", error=str(exc))
            return True  # Allow on budget check failure (fail open)

    async def _call_llm(
        self,
        user_prompt: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> str | None:
        """Make the API call to OpenAI."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None

        client = http_client or httpx.AsyncClient(timeout=30.0)
        try:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": self._SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 300,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            return None
        finally:
            if not http_client:
                await client.aclose()
