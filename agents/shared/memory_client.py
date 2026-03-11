"""Client for interacting with the memory agent / coordinator memory API."""

import os
from typing import Any

import httpx


class MemoryClient:
    """Client for reading and writing to the shared memory store."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.getenv(
            "COORDINATOR_URL", "http://localhost:3000"
        )
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, key: str) -> str | None:
        """Get a memory value by key."""
        try:
            response = await self.client.get(f"/api/memory/{key}")
            if response.status_code == 200:
                data = response.json()
                return data.get("value")
            return None
        except Exception:
            return None

    async def set(self, key: str, value: str, category: str | None = None) -> bool:
        """Set a memory value."""
        try:
            payload = {"value": value}
            if category:
                payload["category"] = category

            response = await self.client.put(f"/api/memory/{key}", json=payload)
            return response.status_code == 200
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete a memory value."""
        try:
            response = await self.client.delete(f"/api/memory/{key}")
            return response.status_code == 204
        except Exception:
            return False

    async def list(self, category: str | None = None) -> list[dict[str, Any]]:
        """List all memory entries, optionally filtered by category."""
        try:
            params = {}
            if category:
                params["category"] = category

            response = await self.client.get("/api/memory", params=params)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception:
            return []

    async def search(self, query: str) -> list[dict[str, Any]]:
        """Search memory entries by value content."""
        entries = await self.list()
        query_lower = query.lower()
        return [
            entry
            for entry in entries
            if query_lower in entry.get("value", "").lower()
            or query_lower in entry.get("key", "").lower()
        ]
