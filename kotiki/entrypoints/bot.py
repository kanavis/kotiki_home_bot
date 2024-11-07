import argparse
import asyncio
import logging
from pathlib import Path

from kotiki.api_client.client import FastAPIClient
from kotiki.commands.bot_commands import BotCommands
from kotiki.core.bot import create_bot
from kotiki.core.log import setup_logging
from kotiki.core.models.config import parse_config

log = logging.getLogger("kotiki.entrypoints.bot")


async def bot_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--config-file", type=Path, default=Path("config.yml"))

    args = parser.parse_args()
    setup_logging(debug=args.debug, quiet=False)
    config = parse_config(config_path=args.config_file)

    sensors_api = FastAPIClient(config.sensors_api)
    bot = create_bot(config)
    await bot.delete_webhook()
    bot_commands = BotCommands(config=config, sensors_api=sensors_api)
    log.info("Starting bot")
    await bot_commands.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("Killed")
