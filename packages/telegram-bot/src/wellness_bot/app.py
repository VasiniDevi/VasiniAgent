"""Main application entry point."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from wellness_bot.config import BotConfig
from wellness_bot.handlers import WellnessBot, router, set_bot_instance
from wellness_bot.scheduler import CheckInScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    config = BotConfig()  # type: ignore[call-arg]  # pydantic-settings loads from env

    # Telegram bot
    bot = Bot(token=config.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    # Wellness bot (core logic)
    wellness = WellnessBot(config)
    await wellness.setup()
    set_bot_instance(wellness)

    # Proactive scheduler
    assert wellness.store is not None
    scheduler = CheckInScheduler(
        bot=bot,
        store=wellness.store,
        default_interval_hours=config.checkin_interval_hours,
        quiet_start=config.quiet_hours_start,
        quiet_end=config.quiet_hours_end,
    )
    scheduler.start()

    logger.info("Wellness bot started. Polling...")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await wellness.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
