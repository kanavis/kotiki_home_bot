import argparse
import asyncio
import logging
from pathlib import Path

import aiohttp

from kotiki.core.bot import create_bot
from kotiki.core.db import create_db
from kotiki.core.interfaces import CronRunner
from kotiki.core.log import setup_logging
from kotiki.core.managers.notifications_manager import NotificationsManager
from kotiki.core.managers.site_watcher_manager import SiteWatcherManager
from kotiki.core.models.config import parse_config
from kotiki.core.models.site_watcher import parse_watch_config
from kotiki.cron.notification_executor import NotificationExecutor
from kotiki.cron.site_watcher import SiteWatcher

log = logging.getLogger("kotiki.entrypoints.cron")


async def cron_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--config-file", type=Path, default=Path("config.yml"))
    parser.add_argument(
        "--watch-config-file", type=Path, default=Path("site_watch.yml"),
    )

    args = parser.parse_args()

    setup_logging(debug=args.debug, quiet=args.quiet)
    config = parse_config(config_path=args.config_file)
    bot = create_bot(config=config)
    db = create_db(config=config)
    notifications_manager = NotificationsManager(db=db)
    site_watcher_manager = SiteWatcherManager(db=db)

    async with aiohttp.ClientSession() as session:
        executors: list[CronRunner] = []
        if args.watch_config_file:
            watcher_config = parse_watch_config(config_path=args.watch_config_file, config=config)
            executors.append(
                SiteWatcher(
                    config=config,
                    watcher_config=watcher_config,
                    bot=bot,
                    session=session,
                    manager=site_watcher_manager,
                    notifications_manager=notifications_manager,
                ),
            )

        executors.append(
            NotificationExecutor(config=config, bot=bot, manager=notifications_manager),
        )

        for executor in executors:
            try:
                await executor.run()
            except Exception:
                log.exception("Exception in executor {}".format(executor.__class__.__name__))


if __name__ == "__main__":
    try:
        asyncio.run(cron_main())
    except KeyboardInterrupt:
        print("Killed")
