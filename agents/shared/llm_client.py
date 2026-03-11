"""LLM client for agent reasoning and text generation."""

import os
from typing import Any

import anthropic


class LLMClient:
    """Client for interacting with Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929")
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate a completion from the LLM."""
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "",
            messages=messages,
            temperature=temperature,
        )

        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""

    async def summarize(self, text: str, max_length: int = 200) -> str:
        """Summarize text."""
        prompt = f"""Summarize the following text in {max_length} characters or less.
Be concise and capture the key points.

Text:
{text}

Summary:"""
        return await self.complete(prompt, max_tokens=512, temperature=0.3)

    async def extract_action_items(self, text: str) -> list[str]:
        """Extract action items from text."""
        prompt = f"""Extract action items from the following text.
Return each action item on a new line, starting with "- ".
If there are no action items, respond with "None".

Text:
{text}

Action items:"""
        response = await self.complete(prompt, max_tokens=512, temperature=0.3)
        lines = response.strip().split("\n")
        items = [line.strip("- ").strip() for line in lines if line.strip().startswith("-")]
        return items

    async def draft_reply(
        self,
        original_message: str,
        context: str | None = None,
        tone: str = "professional",
    ) -> str:
        """Draft a reply to a message."""
        system = f"""You are drafting an email reply. Use a {tone} tone.
Be concise and helpful. Do not include a subject line."""

        context_text = f"\nContext: {context}" if context else ""
        prompt = f"""Draft a reply to this email:{context_text}

Original email:
{original_message}

Reply:"""
        return await self.complete(prompt, system=system, max_tokens=1024)

    async def classify(
        self,
        text: str,
        categories: list[str],
    ) -> tuple[str, float]:
        """Classify text into one of the categories."""
        categories_str = ", ".join(categories)
        prompt = f"""Classify the following text into one of these categories: {categories_str}

Text:
{text}

Respond with just the category name, nothing else.

Category:"""
        response = await self.complete(prompt, max_tokens=50, temperature=0.1)
        category = response.strip()

        # Simple confidence heuristic
        confidence = 0.9 if category in categories else 0.5

        return category, confidence
