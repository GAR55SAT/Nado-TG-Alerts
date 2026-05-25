from __future__ import annotations

import asyncio
import logging

from src.alerts.formatters import AlertMessage
from src.bot.telegram_app import TelegramBotApp
from src.config import get_settings
from src.monitors.service import MonitorService
from src.nado.client import NadoClient
from src.storage.state import StateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def monitor_loop(app: TelegramBotApp, monitor: MonitorService) -> None:
    settings = app.settings
    while True:
        try:
            await monitor.run_cycle()
            app.persist_state()
        except Exception:
            logger.exception("Monitor cycle failed")
        await asyncio.sleep(settings.poll_interval_seconds)


async def main() -> None:
    settings = get_settings()
    store = StateStore(settings.state_file)
    client = NadoClient(settings.archive_url, settings.gateway_url)
    bot_app = TelegramBotApp(settings, client, store)

    async def on_alert(message: AlertMessage) -> None:
        await bot_app.send_alert(message.text, message.chat_ids)

    monitor = MonitorService(client, settings, bot_app.state, on_alert)

    await bot_app.application.initialize()
    await bot_app.set_command_menu()
    await bot_app.application.start()
    await bot_app.application.updater.start_polling(drop_pending_updates=True)

    logger.info(
        "Nado TG Alerts started (%s, poll=%ss)",
        settings.nado_network,
        settings.poll_interval_seconds,
    )

    try:
        await monitor_loop(bot_app, monitor)
    finally:
        bot_app.persist_state()
        await bot_app.application.updater.stop()
        await bot_app.application.stop()
        await bot_app.application.shutdown()
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
