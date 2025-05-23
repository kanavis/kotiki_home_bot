import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiohttp
from aiogram import Bot
from aiohttp import ClientTimeout
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, retry_if_exception_type

from kotiki.core.interfaces import CronRunner
from kotiki.core.managers.site_watcher_manager import SiteWatcherManager
from kotiki.core.models.config import Config
from kotiki.core.models.db import Notification, SiteWatchSuspension
from kotiki.core.models.site_watcher import WatcherConfig, WatchURL, WatchType, WatchTarget
from kotiki.core.managers.notifications_manager import NotificationsManager
from kotiki.core.utils import coalesce, make_browser_headers

log = logging.getLogger(__name__)


class LocalException(Exception):
    pass


aiohttp_retry = retry(
    retry=retry_if_exception_type((aiohttp.ClientError, LocalException)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(),
    before_sleep=before_sleep_log(log, logging.WARNING),
)


class SiteWatcher(CronRunner):
    def __init__(
        self,
        config: Config,
        watcher_config: WatcherConfig,
        bot: Bot,
        session: aiohttp.ClientSession,
        manager: SiteWatcherManager,
        notifications_manager: NotificationsManager,
    ):
        self._config = config
        self._watcher_config = watcher_config
        self._bot = bot
        self._session = session
        self._manager = manager
        self._notifications_manager = notifications_manager

    async def _check_text(self, response: aiohttp.ClientResponse, value: str) -> Optional[str]:
        text = await response.text()
        if len(text) == 0:
            raise LocalException("No text in response, probably protection")

        if value not in text:
            return "Message '{}' is not in the site's text anymore".format(value)

        return None

    def _suspend_timedelta(self, target: WatchTarget) -> timedelta:
        return coalesce(target.suspension_time, self._config.site_watcher.suspension_time)

    @aiohttp_retry
    async def _suspend(self, target: WatchTarget, url_config: WatchURL):
        await self._manager.suspend(SiteWatchSuspension(
            target=target.name,
            url=str(url_config.url),
            watch_type=url_config.watch_type.value,
            value=url_config.value,
            suspended_until=datetime.now() + self._suspend_timedelta(target),
        ))

    async def _notify(self, target: WatchTarget, url_config: WatchURL, text: str):
        message = "{}: Site {}: {} since {}{}".format(
            target.name, url_config.url, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            " ({})".format(url_config.comment) if url_config.comment is not None else "",
        )
        for contact in target.contacts:
            await self._notifications_manager.add(Notification(
                chat_id=self._config.contacts[contact].id,
                message=message,
            ))
            try:
                await self._suspend(target, url_config)
            except Exception:
                log.exception("Exception trying to suspend watcher {} {}".format(target.name, url_config))

    @aiohttp_retry
    async def _check_url_inner(self, target: WatchTarget, url_config: WatchURL) -> tuple[Optional[str], str]:
        async with self._session.get(
            url_config.url,
            headers=make_browser_headers(),
            timeout=ClientTimeout(total=self._config.site_watcher.request_timeout),
            ssl=False,
        ) as response:
            if response.status > 499 or response.status < 400:
                response.raise_for_status()
            if url_config.watch_type == WatchType.TEXT:
                return await self._check_text(response, url_config.value), await response.text()
            else:
                raise RuntimeError("Unexpected watch type {}".format(url_config.watch_type))

    def _log_site_content(self, log_dir: Path, text: str, url_config: WatchURL):
        log_dir.mkdir(parents=True, exist_ok=True)
        n_try = 0
        while True:
            try_suffix = "-{}".format(n_try) if n_try else ""
            log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}{try_suffix}.log"
            if not log_file.exists():
                break
        with open(log_file, "w") as f:
            f.write("<!-- FROM {} -->\n\n".format(url_config.url))
            f.write(text)

    async def _check_url(self, target: WatchTarget, url_config: WatchURL):
        log.info(f"Checking site {url_config.url} for '{url_config.value}' {url_config.watch_type}")
        try:
            result, resp_text = await self._check_url_inner(target, url_config)
            if result is not None:
                log.info("Site {}: {}. Notifying".format(url_config.url, result))
                try:
                    if target.log_dir is not None:
                        self._log_site_content(target.log_dir, resp_text, url_config)
                except Exception:
                    log.exception("Exception while saving site {} content".format(url_config.url))
                await self._notify(target, url_config, result)
            else:
                log.debug("Site {}: no need to notify".format(url_config.url))
        except Exception:
            log.exception("Exception while checking url {}".format(url_config.url))

    async def run(self):
        suspensions = await self._manager.get_suspensions()
        async with asyncio.TaskGroup() as task_group:
            for target in self._watcher_config.targets:
                log.debug("Checking target {} {}".format(target.name, target.urls))
                if not target.contacts:
                    log.warning("No contacts configured for watch '{}'".format(target.name))
                for url_config in target.urls:
                    if not suspensions.is_suspended(
                        target.name, url_config.url, url_config.value, url_config.watch_type.value,
                    ):
                        task_group.create_task(self._check_url(target, url_config))
                    else:
                        log.debug("Site is suspended, not checking '{}'".format(target.name))

    def __str__(self):
        return "SiteWatcher {} targets".format(len(self._watcher_config.targets))
