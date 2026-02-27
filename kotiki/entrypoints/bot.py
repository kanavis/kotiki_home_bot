import argparse
import asyncio
import logging
from pathlib import Path

import uvicorn

from kotiki.api.bot_api import app as bot_api_app, configure as configure_bot_api, cctl_manager
from kotiki.core.api_client import FastAPIClient
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

    configure_bot_api(api_secret=config.api_secret)

    sensors_api = FastAPIClient(config.sensors_api)
    bot = create_bot(config)
    await bot.delete_webhook()
    bot_commands = BotCommands(config=config, sensors_api=sensors_api)

    async def on_unsolicited_error(client_id: str, error_data: dict) -> None:
        msg = error_data.get("error", str(error_data))
        text = f"cctl {client_id} error: {msg}"
        for contact in config.contacts.values():
            if contact.send_errors:
                try:
                    await bot.send_message(chat_id=contact.id, text=text)
                except Exception as e:
                    log.warning("Failed to send error to contact %s: %s", contact.id, e)

    cctl_manager.set_on_unsolicited_error(on_unsolicited_error)

    uvicorn_config = uvicorn.Config(
        bot_api_app, host=config.api_ip, port=config.api_port, log_level="info"
    )
    server = uvicorn.Server(uvicorn_config)
    api_task = asyncio.create_task(server.serve())
    log.info("Bot API listening on %s:%s", config.api_ip, config.api_port)

    try:
        log.info("Starting bot")
        await bot_commands.start_polling(bot)
    finally:
        api_task.cancel()
        try:
            await api_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("Killed")
