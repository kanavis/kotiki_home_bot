from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Literal

import yaml

from kotiki.core.models.retort import base_retort


@dataclass
class Contact:
    id: str


@dataclass
class PgConfig:
    type: Literal["pg", "postgres", "postgresql"]
    host: str
    db_name: str
    user: str
    password: str


@dataclass
class SqliteConfig:
    type: Literal["sqlite", "sqlite3"]
    path: Path


@dataclass
class SiteWatcherConfig:
    request_timeout: float = 10.0
    suspension_time: timedelta = timedelta(days=1)


@dataclass
class Alias:
    alias: str
    command: str
    arg: str | None = None


@dataclass
class Config:
    bot_token: str
    contacts: dict[str, Contact]

    db: PgConfig | SqliteConfig
    sensors_api: str

    site_watcher: SiteWatcherConfig = field(default_factory=SiteWatcherConfig)

    aliases: list[Alias] = field(default_factory=list)

    def is_known(self, chat_id: str) -> bool:
        for contact in self.contacts.values():
            if contact.id == chat_id:
                return True
        return False


retort = base_retort


def parse_config(config_path: Path) -> Config:
    with open(config_path, "r", encoding="utf-8") as f:
        return retort.load(yaml.safe_load(f), Config)
