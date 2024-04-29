from datetime import datetime

import yarl
from sqlalchemy import delete, select

from kotiki.core.db import DB
from kotiki.core.models.db import SiteWatchSuspension


class SuspensionChecker:
    def __init__(self, suspensions: list[SiteWatchSuspension]):
        self.suspensions = suspensions
        self._hash = {self._make_key(s.target, s.url, s.value, s.watch_type) for s in suspensions}

    def _make_key(self, target: str, url: str, value: str, watch_type: str):
        return target, url, value, watch_type

    def is_suspended(self, target: str, url: yarl.URL, value: str, watch_type: str) -> bool:
        return self._make_key(target, str(url), value, watch_type) in self._hash


class SiteWatcherManager:
    def __init__(self, db: DB):
        self.db = db

    async def get_suspensions(self) -> SuspensionChecker:
        async with self.db.session() as session:
            stmt = delete(SiteWatchSuspension).where(SiteWatchSuspension.suspended_until <= datetime.now())
            await session.execute(stmt)
            await session.commit()

            stmt = select(SiteWatchSuspension)
            result = await session.execute(stmt)
            return SuspensionChecker(suspensions=list(result.scalars()))

    async def suspend(self, suspension: SiteWatchSuspension):
        async with self.db.session() as session:
            session.add(suspension)
            await session.commit()
