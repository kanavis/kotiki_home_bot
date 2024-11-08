import logging

from aiogram import Dispatcher, html, Bot
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message

from kotiki.api_client.client import FastAPIClient
from kotiki.core.models.config import Config

log = logging.getLogger(__name__)


class BotCommands:
    def __init__(self, config: Config, sensors_api: FastAPIClient):
        self.config = config
        self.sensors_api = sensors_api
        self.dp = Dispatcher()
        self.dp.message(CommandStart())(self.command_start_handler)
        self.dp.message(Command("sensor"))(self.command_sensor_handler)

    async def start_polling(self, bot: Bot):
        await self.dp.start_polling(bot)

    async def command_start_handler(self, message: Message):
        await message.answer(f"Privet, {html.bold(message.from_user.full_name)}!", parse_mode=ParseMode.HTML)

    async def command_sensor_handler(self, message: Message, command: CommandObject):
        if not self.config.is_known(str(message.chat.id)):
            log.info("Command '{}' from unknown contact {} '{}'".format(
                message.text, message.chat.id, message.from_user.username,
            ))
            return
        log.info("Command '{}' for {} {}".format(
            message.text, message.chat.id, message.from_user.username,
        ))
        if command.args is None or " " in command.args:
            await message.answer("Wrong command: only one argument <sensor_name> supported")
            return
        try:
            data = await self.sensors_api.get("/sensors/{}".format(command.args))
        except Exception as e:
            log.exception("Getting data from sensors API")
            await message.answer(html.bold("Error: {}".format(e)), parse_mode=ParseMode.HTML)
        else:
            print(data)
            response = ["  {}: {}".format(name, value) for name, value in data["measurements"].items()]
            await message.answer("Sensor {} readings:\n{}".format(command.args, "\n".join(response)))
