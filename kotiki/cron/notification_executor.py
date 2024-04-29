import logging

from aiogram import Bot
from aiogram.exceptions import AiogramError
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception_type

from kotiki.core.interfaces import CronRunner
from kotiki.core.models.config import Config
from kotiki.core.models.db import Notification
from kotiki.core.managers.notifications_manager import NotificationsManager

log = logging.getLogger(__name__)


bot_retry = retry(
    retry=retry_if_exception_type(AiogramError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(),
    before_sleep=before_sleep_log(log, logging.WARNING),
)


class NotificationExecutor(CronRunner):
    def __init__(self, config: Config, bot: Bot, manager: NotificationsManager):
        self._config = config
        self._bot = bot
        self._manager = manager

    @bot_retry
    async def _delete(self, notification: Notification):
        await self._manager.delete(notification)

    @bot_retry
    async def _send(self, notification: Notification):
        await self._bot.send_message(notification.chat_id, notification.message)
        try:
            await self._delete(notification)
        except Exception:
            log.exception(f"Error deleting notification: {notification}")

    async def run(self):
        async for notification in self._manager.generate_actual():
            log.debug(f"Executing notification: {notification}")
            try:
                await self._send(notification)
            except Exception:
                log.exception(f"Exception sending notification: {notification}")
