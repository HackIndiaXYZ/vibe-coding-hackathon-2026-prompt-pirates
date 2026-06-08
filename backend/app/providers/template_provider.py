"""
Template provider — serves responses from YAML templates.
Zero external dependencies. Works with no API keys.
"""
from __future__ import annotations

from typing import List, Optional

from app.providers.base import BaseLLMProvider, LLMResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TemplateProvider(BaseLLMProvider):
    """
    Dummy LLM provider used in TEMPLATE mode.
    complete() is never called in template mode — TemplateService handles it.
    embed() uses local sentence-transformers if available, else returns zeros.
    """

    def __init__(self):
        self._embed_model = None
        self._embed_tried = False

    @property
    def name(self) -> str:
        return "template"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        # Should not be called in template mode — but return a safe fallback
        logger.warning("TemplateProvider.complete() called — returning empty response.")
        return LLMResponse(
            content="[Template mode: no LLM response available]",
            provider=self.name,
            model="none",
        )

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Try sentence-transformers; fall back to zero vectors."""
        if not self._embed_tried:
            self._embed_tried = True
            try:
                from sentence_transformers import SentenceTransformer
                from app.core.settings import settings
                self._embed_model = SentenceTransformer(settings.EMBEDDING_MODEL)
                logger.info("Template provider: loaded local embedding model.")
            except Exception as e:
                logger.warning(f"Template provider: local embeddings unavailable ({e}).")

        if self._embed_model is not None:
            import asyncio
            loop = asyncio.get_event_loop()
            vectors = await loop.run_in_executor(
                None, lambda: self._embed_model.encode(texts, convert_to_numpy=True)
            )
            return [v.tolist() for v in vectors]

        # Last resort: zero vectors (384-dim matches MiniLM)
        return [[0.0] * 384 for _ in texts]

    async def health_check(self) -> bool:
        return True
