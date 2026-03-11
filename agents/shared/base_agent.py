"""Base agent class with common functionality for all agents."""

import asyncio
import logging
import os
import signal
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from .llm_client import LLMClient
from .memory_client import MemoryClient
from .models import (
    ActivityLevel,
    ActivityReport,
    Plan,
    Result,
    ValidationRequest,
    ValidationResponse,
)
from .redis_client import RedisClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all NEXUS agents."""

    # Channel names
    CHANNEL_PLANS = "nexus:plans"
    CHANNEL_RESULTS = "nexus:results"
    CHANNEL_VALIDATIONS = "nexus:validations"
    CHANNEL_APPROVALS = "nexus:approvals"
    CHANNEL_ACTIVITY = "nexus:activity"

    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.redis = RedisClient()
        self.llm = LLMClient()
        self.memory = MemoryClient()
        self._running = False
        self._pending_validations: dict[str, asyncio.Event] = {}
        self._validation_responses: dict[str, ValidationResponse] = {}

    @abstractmethod
    async def execute(self, plan: Plan) -> Result:
        """Execute a plan and return the result.

        This method must be implemented by each agent.

        Args:
            plan: The plan to execute with action and params.

        Returns:
            Result indicating success/failure and any output data.
        """
        pass

    async def start(self) -> None:
        """Start the agent and begin listening for plans."""
        logger.info(f"Starting {self.agent_type}")

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Connect to Redis
        await self.redis.connect()

        # Subscribe to agent-specific plan channel
        plan_channel = f"{self.CHANNEL_PLANS}:{self.agent_type}"
        await self.redis.subscribe(plan_channel, self._handle_plan)

        # Subscribe to approval responses
        await self.redis.subscribe(self.CHANNEL_APPROVALS, self._handle_approval)

        self._running = True
        await self.report_activity("started", f"{self.agent_type} started")

        # Start listening
        await self.redis.start_listening()

    async def stop(self) -> None:
        """Stop the agent gracefully."""
        logger.info(f"Stopping {self.agent_type}")
        self._running = False
        await self.report_activity("stopped", f"{self.agent_type} stopped")
        await self.redis.close()
        await self.memory.close()

    async def _handle_plan(self, data: dict[str, Any]) -> None:
        """Handle incoming plan messages."""
        try:
            plan = Plan(**data)
            logger.info(f"Received plan: {plan.action}")

            await self.report_activity(
                plan.action,
                f"Executing: {plan.action}",
                {"plan_id": plan.id},
            )

            # Execute the plan
            result = await self.execute(plan)

            # Publish result
            await self.redis.publish(self.CHANNEL_RESULTS, result)

            if result.success:
                await self.report_activity(
                    plan.action,
                    f"Completed: {plan.action}",
                    {"plan_id": plan.id},
                )
            else:
                await self.report_activity(
                    plan.action,
                    f"Failed: {plan.action} - {result.error}",
                    {"plan_id": plan.id},
                    level=ActivityLevel.ERROR,
                )

        except Exception as e:
            logger.exception(f"Error handling plan: {e}")
            await self.report_activity(
                "error",
                f"Error: {str(e)}",
                level=ActivityLevel.ERROR,
            )

    async def _handle_approval(self, data: dict[str, Any]) -> None:
        """Handle validation approval/rejection responses."""
        try:
            response = ValidationResponse(**data)
            validation_id = response.validation_id

            if validation_id in self._pending_validations:
                self._validation_responses[validation_id] = response
                self._pending_validations[validation_id].set()
        except Exception as e:
            logger.error(f"Error handling approval: {e}")

    async def request_validation(
        self,
        plan_id: str,
        action: str,
        description: str,
        data: dict[str, Any] | None = None,
        timeout_minutes: int = 60,
    ) -> ValidationResponse | None:
        """Request human validation for an action.

        Args:
            plan_id: The plan this validation is for.
            action: The action being validated.
            description: Human-readable description of what needs approval.
            data: Optional data to show the user.
            timeout_minutes: How long to wait for approval.

        Returns:
            ValidationResponse if approved/rejected, None if timeout.
        """
        validation_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)

        request = ValidationRequest(
            id=validation_id,
            plan_id=plan_id,
            agent_type=self.agent_type,
            action=action,
            description=description,
            data=data,
            expires_at=expires_at,
        )

        # Setup event for waiting
        event = asyncio.Event()
        self._pending_validations[validation_id] = event

        try:
            # Publish validation request
            await self.redis.publish(self.CHANNEL_VALIDATIONS, request)
            await self.report_activity(
                action,
                f"Waiting for approval: {description}",
                {"validation_id": validation_id},
                level=ActivityLevel.WARNING,
            )

            # Wait for response
            try:
                await asyncio.wait_for(
                    event.wait(), timeout=timeout_minutes * 60
                )
                return self._validation_responses.get(validation_id)
            except asyncio.TimeoutError:
                logger.warning(f"Validation {validation_id} timed out")
                return None

        finally:
            self._pending_validations.pop(validation_id, None)
            self._validation_responses.pop(validation_id, None)

    async def report_activity(
        self,
        action: str,
        message: str,
        data: dict[str, Any] | None = None,
        level: ActivityLevel = ActivityLevel.INFO,
    ) -> None:
        """Report activity to the coordinator for the activity feed.

        Args:
            action: The action being performed.
            message: Human-readable message.
            data: Optional additional data.
            level: Activity level (info, warning, error).
        """
        report = ActivityReport(
            agent_type=self.agent_type,
            action=action,
            message=message,
            data=data,
            level=level,
        )

        try:
            await self.redis.publish(self.CHANNEL_ACTIVITY, report)
        except Exception as e:
            logger.error(f"Failed to report activity: {e}")
