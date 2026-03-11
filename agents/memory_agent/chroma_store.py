"""ChromaDB store for semantic memory search."""

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A memory entry with embedding."""

    id: str
    content: str
    metadata: dict[str, Any]
    distance: float | None = None


class ChromaStore:
    """Vector store using ChromaDB for semantic memory search."""

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = "nexus_memory",
    ):
        self.persist_directory = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIR", "./data/chroma"
        )
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_collection(self):
        """Get or create the ChromaDB collection."""
        if self._collection is None:
            try:
                import chromadb
                from chromadb.config import Settings

                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(anonymized_telemetry=False),
                )
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except ImportError:
                logger.error("chromadb not installed")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB: {e}")
                return None

        return self._collection

    def store(
        self,
        id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Store a memory entry with automatic embedding."""
        collection = self._get_collection()
        if not collection:
            return False

        try:
            collection.upsert(
                ids=[id],
                documents=[content],
                metadatas=[metadata or {}],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return False

    def retrieve(self, id: str) -> MemoryEntry | None:
        """Retrieve a specific memory entry by ID."""
        collection = self._get_collection()
        if not collection:
            return None

        try:
            result = collection.get(ids=[id], include=["documents", "metadatas"])

            if not result["ids"]:
                return None

            return MemoryEntry(
                id=result["ids"][0],
                content=result["documents"][0],
                metadata=result["metadatas"][0] if result["metadatas"] else {},
            )
        except Exception as e:
            logger.error(f"Failed to retrieve memory: {e}")
            return None

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]:
        """Search for similar memory entries."""
        collection = self._get_collection()
        if not collection:
            return []

        try:
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            entries = []
            for i, id in enumerate(results["ids"][0]):
                entries.append(
                    MemoryEntry(
                        id=id,
                        content=results["documents"][0][i],
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        distance=results["distances"][0][i] if results["distances"] else None,
                    )
                )

            return entries
        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return []

    def delete(self, id: str) -> bool:
        """Delete a memory entry."""
        collection = self._get_collection()
        if not collection:
            return False

        try:
            collection.delete(ids=[id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        where: dict[str, Any] | None = None,
    ) -> list[MemoryEntry]:
        """List all memory entries."""
        collection = self._get_collection()
        if not collection:
            return []

        try:
            result = collection.get(
                limit=limit,
                offset=offset,
                where=where,
                include=["documents", "metadatas"],
            )

            entries = []
            for i, id in enumerate(result["ids"]):
                entries.append(
                    MemoryEntry(
                        id=id,
                        content=result["documents"][i],
                        metadata=result["metadatas"][i] if result["metadatas"] else {},
                    )
                )

            return entries
        except Exception as e:
            logger.error(f"Failed to list memories: {e}")
            return []

    def count(self) -> int:
        """Get total number of memory entries."""
        collection = self._get_collection()
        if not collection:
            return 0

        try:
            return collection.count()
        except Exception as e:
            logger.error(f"Failed to count memories: {e}")
            return 0
