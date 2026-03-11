"""Memory agent implementation."""

import logging
import uuid
from datetime import datetime
from typing import Any

from shared import BaseAgent, Plan, Result

from .chroma_store import ChromaStore

logger = logging.getLogger(__name__)


class MemoryAgent(BaseAgent):
    """Agent for managing semantic memory with vector search."""

    def __init__(self):
        super().__init__("memory_agent")
        self.chroma = ChromaStore()

    async def execute(self, plan: Plan) -> Result:
        """Execute a memory-related action."""
        action = plan.action
        params = plan.params

        try:
            match action:
                case "store":
                    return await self._store(plan, params)
                case "retrieve":
                    return await self._retrieve(plan, params)
                case "search":
                    return await self._search(plan, params)
                case "delete":
                    return await self._delete(plan, params)
                case "summarize_context":
                    return await self._summarize_context(plan, params)
                case _:
                    return Result(
                        plan_id=plan.id,
                        agent_type=self.agent_type,
                        success=False,
                        error=f"Unknown action: {action}",
                    )
        except Exception as e:
            logger.exception(f"Error executing {action}: {e}")
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error=str(e),
            )

    async def _store(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Store a memory entry."""
        content = params.get("content")
        key = params.get("key")
        category = params.get("category")
        tags = params.get("tags", [])

        if not content:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameter: content",
            )

        # Generate ID if not provided
        memory_id = key or str(uuid.uuid4())

        metadata = {
            "category": category or "general",
            "tags": ",".join(tags) if tags else "",
            "created_at": datetime.utcnow().isoformat(),
            "source": params.get("source", "user"),
        }

        success = self.chroma.store(memory_id, content, metadata)

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=success,
            result={"id": memory_id} if success else None,
            error="Failed to store memory" if not success else None,
        )

    async def _retrieve(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Retrieve a specific memory entry."""
        key = params.get("key")

        if not key:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameter: key",
            )

        entry = self.chroma.retrieve(key)

        if not entry:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error=f"Memory not found: {key}",
            )

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=True,
            result={
                "id": entry.id,
                "content": entry.content,
                "metadata": entry.metadata,
            },
        )

    async def _search(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Search for similar memory entries."""
        query = params.get("query")
        limit = params.get("limit", 5)
        category = params.get("category")

        if not query:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameter: query",
            )

        where = None
        if category:
            where = {"category": category}

        entries = self.chroma.search(query, n_results=limit, where=where)

        results = [
            {
                "id": e.id,
                "content": e.content,
                "metadata": e.metadata,
                "relevance": 1 - (e.distance or 0),  # Convert distance to similarity
            }
            for e in entries
        ]

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=True,
            result={
                "count": len(results),
                "results": results,
            },
        )

    async def _delete(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Delete a memory entry."""
        key = params.get("key")

        if not key:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameter: key",
            )

        success = self.chroma.delete(key)

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=success,
            result={"deleted": key} if success else None,
            error="Failed to delete memory" if not success else None,
        )

    async def _summarize_context(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Search memories and summarize relevant context."""
        query = params.get("query")
        limit = params.get("limit", 10)

        if not query:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameter: query",
            )

        # Search for relevant memories
        entries = self.chroma.search(query, n_results=limit)

        if not entries:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=True,
                result={
                    "summary": "No relevant memories found.",
                    "sources": [],
                },
            )

        # Build context from memories
        context_parts = []
        for e in entries:
            context_parts.append(f"- {e.content}")

        context = "\n".join(context_parts)

        # Use LLM to summarize
        prompt = f"""Based on these memory entries, provide a relevant summary for the query: "{query}"

Memory entries:
{context}

Summary:"""

        summary = await self.llm.complete(prompt, max_tokens=512)

        sources = [{"id": e.id, "relevance": 1 - (e.distance or 0)} for e in entries]

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=True,
            result={
                "summary": summary,
                "sources": sources,
            },
        )
