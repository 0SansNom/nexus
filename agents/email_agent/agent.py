"""Email agent implementation."""

import asyncio
import logging
from typing import Any

from shared import BaseAgent, Plan, Result

from .imap_client import IMAPClient
from .smtp_client import EmailDraft, SMTPClient

logger = logging.getLogger(__name__)


class EmailAgent(BaseAgent):
    """Agent for managing emails: reading, summarizing, replying, archiving."""

    def __init__(self):
        super().__init__("email_agent")
        self.imap = IMAPClient()
        self.smtp = SMTPClient()
        self._known_contacts: set[str] | None = None

    async def execute(self, plan: Plan) -> Result:
        """Execute an email-related action."""
        action = plan.action
        params = plan.params

        try:
            match action:
                case "read_and_summarize":
                    return await self._read_and_summarize(plan, params)
                case "reply":
                    return await self._reply(plan, params)
                case "archive":
                    return await self._archive(plan, params)
                case "create_filter":
                    return await self._create_filter(plan, params)
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

    async def _read_and_summarize(
        self, plan: Plan, params: dict[str, Any]
    ) -> Result:
        """Read emails and provide summaries."""
        folder = params.get("folder", "INBOX")
        limit = params.get("limit", 10)
        criteria = params.get("criteria", "UNSEEN")

        with self.imap as client:
            emails = client.fetch_many(folder, limit, criteria)

        if not emails:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=True,
                result={"count": 0, "emails": [], "summary": "No new emails."},
            )

        # Summarize each email in parallel
        async def summarize_email(email_msg):
            # Use LLM to summarize
            summary = await self.llm.summarize(
                f"Subject: {email_msg.subject}\n\n{email_msg.body_text[:2000]}"
            )
            return {
                "uid": email_msg.uid,
                "subject": email_msg.subject,
                "sender": email_msg.sender,
                "sender_email": email_msg.sender_email,
                "date": email_msg.date.isoformat(),
                "summary": summary,
                "has_attachments": len(email_msg.attachments) > 0,
            }

        summaries = await asyncio.gather(*[summarize_email(email) for email in emails])

        # Generate overall summary
        overall_prompt = f"""Summarize these {len(emails)} emails in 2-3 sentences:

{chr(10).join(f"- {s['subject']} from {s['sender']}: {s['summary']}" for s in summaries)}"""

        overall_summary = await self.llm.complete(overall_prompt, max_tokens=256)

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=True,
            result={
                "count": len(emails),
                "emails": summaries,
                "summary": overall_summary,
            },
        )

    async def _reply(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Draft and send a reply to an email."""
        uid = params.get("uid")
        folder = params.get("folder", "INBOX")
        message = params.get("message")
        tone = params.get("tone", "professional")

        if not uid:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameter: uid",
            )

        # Fetch the original email
        with self.imap as client:
            original = client.fetch(uid, folder)

        if not original:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error=f"Email not found: {uid}",
            )

        # Check if this is a known contact
        is_known = await self._is_known_contact(original.sender_email)

        # Draft the reply
        if message:
            reply_text = message
        else:
            reply_text = await self.llm.draft_reply(
                original.body_text[:3000], tone=tone
            )

        # Request validation if new contact
        if not is_known:
            validation = await self.request_validation(
                plan_id=plan.id,
                action="reply",
                description=f"Reply to new contact: {original.sender} <{original.sender_email}>",
                data={
                    "to": original.sender_email,
                    "subject": f"Re: {original.subject}",
                    "body": reply_text,
                    "original_subject": original.subject,
                    "original_from": original.sender,
                },
            )

            if not validation or not validation.approved:
                return Result(
                    plan_id=plan.id,
                    agent_type=self.agent_type,
                    success=False,
                    error="Reply rejected by user",
                )

            # Add to known contacts
            await self._add_known_contact(original.sender_email)

        # Send the reply
        draft = EmailDraft(
            to=[original.sender_email],
            subject=f"Re: {original.subject}",
            body_text=reply_text,
            in_reply_to=uid,
        )

        success = self.smtp.send(draft)

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=success,
            result={
                "to": original.sender_email,
                "subject": draft.subject,
            } if success else None,
            error="Failed to send email" if not success else None,
        )

    async def _archive(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Archive emails."""
        uids = params.get("uids", [])
        folder = params.get("folder", "INBOX")
        archive_folder = params.get("archive_folder", "Archive")

        if not uids:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="No email UIDs provided",
            )

        archived = []
        failed = []

        with self.imap as client:
            for uid in uids:
                if client.archive(uid, folder, archive_folder):
                    archived.append(uid)
                else:
                    failed.append(uid)

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=len(failed) == 0,
            result={
                "archived": archived,
                "failed": failed,
            },
            error=f"Failed to archive {len(failed)} emails" if failed else None,
        )

    async def _create_filter(self, plan: Plan, params: dict[str, Any]) -> Result:
        """Create an email filter rule (stored in memory)."""
        name = params.get("name")
        criteria = params.get("criteria", {})
        action = params.get("filter_action")

        if not name or not action:
            return Result(
                plan_id=plan.id,
                agent_type=self.agent_type,
                success=False,
                error="Missing required parameters: name, filter_action",
            )

        # Store filter in memory
        filter_data = {
            "name": name,
            "criteria": criteria,
            "action": action,
        }

        success = await self.memory.set(
            f"email_filter:{name}",
            str(filter_data),
            category="email_filters",
        )

        return Result(
            plan_id=plan.id,
            agent_type=self.agent_type,
            success=success,
            result={"filter": filter_data} if success else None,
            error="Failed to create filter" if not success else None,
        )

    async def _is_known_contact(self, email: str) -> bool:
        """Check if an email address is a known contact."""
        if self._known_contacts is None:
            # Load known contacts from memory
            contacts_str = await self.memory.get("known_contacts")
            if contacts_str:
                self._known_contacts = set(contacts_str.split(","))
            else:
                self._known_contacts = set()

        return email.lower() in self._known_contacts

    async def _add_known_contact(self, email: str) -> None:
        """Add an email to known contacts."""
        if self._known_contacts is None:
            self._known_contacts = set()

        self._known_contacts.add(email.lower())

        # Save to memory
        await self.memory.set(
            "known_contacts",
            ",".join(self._known_contacts),
            category="contacts",
        )
