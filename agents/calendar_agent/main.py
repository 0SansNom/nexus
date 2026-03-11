"""Entry point for calendar agent."""

import asyncio
import logging
import sys

from agent import CalendarAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


async def main():
    agent = CalendarAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
