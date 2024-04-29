import logging
from typing import Optional, AsyncIterable

from sqlalchemy import select

from kotiki.core.db import DB
from kotiki.core.models.db import Notification

log = logging.getLogger(__name__)


class NotificationsManager:
    def __init__(self, db: DB):
        self.db = db

    async def add(self, notification: Notification) -> int:
        log.debug("Adding notification {}: '{}'".format(notification.chat_id, notification.message))
        async with self.db.session() as session:
            session.add(notification)
            await session.commit()
            log.debug("Added notification {}: '{}'. Id={}".format(
                notification.message, notification.chat_id, notification.id,
            ))
            return notification.id

    async def get_next(self) -> Optional[Notification]:
        async with self.db.session() as session:
            stmt = select(Notification).order_by(Notification.created_at).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def generate_actual(self) -> AsyncIterable[Notification]:
        while True:
            notification = await self.get_next()
            if notification is None:
                break
            yield notification

    async def delete(self, notification: Notification):
        async with self.db.session() as session:
            await session.delete(notification)
            await session.commit()
