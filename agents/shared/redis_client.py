"""Async Redis client for agent communication."""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Coroutine

import redis.asyncio as redis
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client with auto-reconnection and pub/sub support."""

    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._client: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._subscriptions: dict[str, Callable] = {}
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 30.0
        self._running = False

    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self._client = redis.from_url(self.url, decode_responses=True)
            await self._client.ping()
            self._reconnect_delay = 1.0
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self) -> None:
        """Close Redis connection."""
        self._running = False
        if self._pubsub:
            await self._pubsub.close()
        if self._client:
            await self._client.close()
        logger.info("Redis connection closed")

    async def _ensure_connected(self) -> None:
        """Ensure Redis connection is active."""
        if self._client is None:
            await self.connect()
        try:
            await self._client.ping()
        except Exception:
            await self._reconnect()

    async def _reconnect(self) -> None:
        """Reconnect to Redis with exponential backoff."""
        while True:
            try:
                logger.info(f"Reconnecting to Redis in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                await self.connect()

                # Resubscribe to channels
                if self._subscriptions and self._pubsub:
                    for channel in self._subscriptions:
                        await self._pubsub.subscribe(channel)
                return
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )

    async def publish(self, channel: str, message: BaseModel | dict) -> None:
        """Publish a message to a channel."""
        await self._ensure_connected()

        if isinstance(message, BaseModel):
            data = message.model_dump_json()
        else:
            data = json.dumps(message, default=str)

        await self._client.publish(channel, data)
        logger.debug(f"Published to {channel}")

    async def subscribe(
        self,
        channel: str,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to a channel with a handler."""
        await self._ensure_connected()

        if self._pubsub is None:
            self._pubsub = self._client.pubsub()

        self._subscriptions[channel] = handler
        await self._pubsub.subscribe(channel)
        logger.info(f"Subscribed to {channel}")

    async def start_listening(self) -> None:
        """Start listening for messages on subscribed channels."""
        if self._pubsub is None:
            logger.warning("No subscriptions, nothing to listen to")
            return

        self._running = True
        logger.info("Started listening for messages")

        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    channel = message["channel"]
                    if channel in self._subscriptions:
                        try:
                            data = json.loads(message["data"])
                            await self._subscriptions[channel](data)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse message: {e}")
                        except Exception as e:
                            logger.error(f"Handler error for {channel}: {e}")
            except redis.ConnectionError:
                logger.error("Lost Redis connection")
                await self._reconnect()
            except Exception as e:
                logger.error(f"Listener error: {e}")
                await asyncio.sleep(1)

    async def wait_for(
        self,
        channel: str,
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float = 60.0,
    ) -> dict[str, Any] | None:
        """Wait for a specific message matching the predicate."""
        await self._ensure_connected()

        if self._pubsub is None:
            self._pubsub = self._client.pubsub()

        await self._pubsub.subscribe(channel)
        result = None

        try:
            start_time = asyncio.get_event_loop().time()
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    break

                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=min(1.0, timeout - elapsed)
                )
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        if predicate(data):
                            result = data
                            break
                    except json.JSONDecodeError:
                        continue
        finally:
            await self._pubsub.unsubscribe(channel)

        return result
