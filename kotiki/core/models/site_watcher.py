from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
import yarl

from kotiki.core.models.config import Config
from kotiki.core.models.retort import base_retort


class WatchType(Enum):
    TEXT = "text"


@dataclass
class WatchURL:
    url: yarl.URL
    value: str
    watch_type: WatchType = WatchType.TEXT
    comment: Optional[str] = None


@dataclass
class WatchTarget:
    name: str
    contacts: list[str]
    urls: list[WatchURL]
    suspension_time: Optional[timedelta] = None
    log_dir: Optional[Path] = None


@dataclass
class WatcherConfig:
    targets: list[WatchTarget]


retort = base_retort


def parse_watch_config(config_path: Path, config: Config) -> WatcherConfig:
    with open(config_path, "r", encoding="utf-8") as f:
        result = retort.load(yaml.safe_load(f), WatcherConfig)

    for target in result.targets:
        for contact in target.contacts:
            if contact not in config.contacts:
                raise ValueError("Target {} contact {} not found in config".format(target.name, contact))

    return result
