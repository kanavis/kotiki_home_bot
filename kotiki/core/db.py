from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from kotiki.core.models.config import Config, PgConfig, SqliteConfig


class DB:
    def __init__(self, config: Config):
        self.config = config
        if isinstance(config.db, PgConfig):
            dsn = "postgresql+asyncpg://{}:{}@{}/{}".format(
                config.db.user, config.db.password, config.db.host, config.db.db_name,
            )
        elif isinstance(config.db, SqliteConfig):
            dsn = "sqlite+aiosqlite:///{}".format(config.db.path)
        else:
            raise RuntimeError("Unsupported db type: {}".format(config))

        self.engine = create_async_engine(dsn)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

    def session(self) -> AsyncSession:
        return self.session_factory()


def create_db(config: Config) -> DB:
    return DB(config)
