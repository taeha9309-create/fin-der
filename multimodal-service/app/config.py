"""Environment-backed settings for the multimodal service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    prompt_version: str
    max_screenshot_bytes: int
    max_html_bytes: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview"),
            prompt_version=os.getenv("MULTIMODAL_PROMPT_VERSION", "mm_prompt_v1"),
            max_screenshot_bytes=int(os.getenv("MAX_SCREENSHOT_BYTES", str(10 * 1024 * 1024))),
            max_html_bytes=int(os.getenv("MAX_HTML_BYTES", str(2 * 1024 * 1024))),
        )


settings = Settings.from_env()
