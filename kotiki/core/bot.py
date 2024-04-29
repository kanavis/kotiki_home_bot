from aiogram import Bot

from kotiki.core.models.config import Config


def create_bot(config: Config) -> Bot:
    return Bot(token=config.bot_token)
