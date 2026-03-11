"""Calendar agent implementation."""

import logging
from datetime import datetime, timedelta
from typing import Any

from shared import BaseAgent, Plan, Result

from .google_calendar import GoogleCalendarClient

logger = logging.getLogger(__name__)


class CalendarAgent(BaseAgent):
    """Agent for managing calendar events."""

    def __init__(self):
        super().__init__("calendar_agent")
        self.calendar = GoogleCalendarClient()

    async def execute(self, plan: Plan) -> Result:
        """Execute a calendar-related action."""
        action = plan.action
        params = plan.params

        try:
            match action:
                case "list_events":
                    return await self._list_events(plan, params)
                case "create_event":
                    return await self._create_event(plan, params)
                case "update_event":
                    return await self._update_event(plan, params)
                case "delete_event":
                    return await self._delete_event(plan, params)
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

    async def _list_events(self, plan: Plan, params: dict[str, Any]) -> Result:
        """List calendar events."""
        days_ahead = params.get("days_ahead", 7)
        max_results = params.get("max_results", 10)

        time_min = datetime.utcnow()
        time_max = time_min + timedelta(days=days_ahead)

        events = self.calendar.list_events(
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )

        events_data = [
            {
                "id": e.id,
                "title": e.title,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "location": e.location,
                "attendees": e.attendees,
                "is_all_day": e.is_all_day,
            }
            for e in events
        ]

        # Generate summary using LLM
        if events:
            events_text = "\n".join(
                f"- {e['title']} on {e['start'][:10]}" for e in events_data
            )
            summary = await self.llm.complete(
                f"Briefly summarize this schedule in 1-2 sentences:\n{events_text}",
                max_tokens=128,
            )
        else:
            summary = "No upcoming events."

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=True,
            result={
                "count": len(events),
                "events": events_data,
                "summary": summary,
            },
        )

    async def _create_event(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Create a calendar event."""
        title = params.get("title")
        start = params.get("start")
        end = params.get("end")
        description = params.get("description")
        location = params.get("location")
        attendees = params.get("attendees", [])

        if not title or not start or not end:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameters: title, start, end",
            )

        # Parse datetime strings
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        # Request validation if there are attendees
        if attendees:
            validation = await self.request_validation(
                plan_id=plan.id,
                action="create_event",
                description=f"Create event '{title}' with {len(attendees)} attendees",
                data={
                    "title": title,
                    "start": start,
                    "end": end,
                    "attendees": attendees,
                },
            )

            if not validation or not validation.approved:
                return Result(
                    plan_id=plan.id,
                    agent_type=self.agent_type,
                    success=False,
                    error="Event creation rejected by user",
                )

        event = self.calendar.create_event(
            title=title,
            start=start_dt,
            end=end_dt,
            description=description,
            location=location,
            attendees=attendees,
        )

        if not event:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Failed to create event",
            )

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=True,
            result={
                "id": event.id,
                "title": event.title,
                "start": event.start.isoformat(),
                "end": event.end.isoformat(),
            },
        )

    async def _update_event(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Update a calendar event."""
        event_id = params.get("event_id")

        if not event_id:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameter: event_id",
            )

        title = params.get("title")
        start = params.get("start")
        end = params.get("end")
        description = params.get("description")
        location = params.get("location")

        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None

        event = self.calendar.update_event(
            event_id=event_id,
            title=title,
            start=start_dt,
            end=end_dt,
            description=description,
            location=location,
        )

        if not event:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Failed to update event",
            )

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=True,
            result={
                "id": event.id,
                "title": event.title,
            },
        )

    async def _delete_event(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Delete a calendar event."""
        event_id = params.get("event_id")

        if not event_id:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameter: event_id",
            )

        # Get event details for validation
        event = self.calendar.get_event(event_id)
        if event:
            validation = await self.request_validation(
                plan_id=plan.id,
                action="delete_event",
                description=f"Delete event '{event.title}'",
                data={
                    "id": event.id,
                    "title": event.title,
                    "start": event.start.isoformat(),
                },
            )

            if not validation or not validation.approved:
                return Result(
                    plan_id=plan.id,
                    agent_type=self.agent_type,
                    success=False,
                    error="Event deletion rejected by user",
                )

        success = self.calendar.delete_event(event_id)

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=success,
            result={"deleted": event_id} if success else None,
            error="Failed to delete event" if not success else None,
        )
