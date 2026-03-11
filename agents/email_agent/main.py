"""Entry point for email agent."""

import asyncio
import logging
import sys

from agent import EmailAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


async def main():
    agent = EmailAgent()
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
