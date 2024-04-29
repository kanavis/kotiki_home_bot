from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

Base = declarative_base()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    chat_id: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SiteWatchSuspension(Base):
    __tablename__ = 'site_watch_suspensions'

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    target: Mapped[str]
    url: Mapped[str]
    watch_type: Mapped[str]
    value: Mapped[str]
    suspended_until: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
