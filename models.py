"""Content model: a Screen is one "page" the bot can show (the root screen,
key="start", is what /start renders); a Button belongs to a Screen and
either opens a URL directly or points at another Screen to show when
tapped. No ORM relationships are declared on purpose - both models are
small and every access pattern here is a plain, explicit query (see
handlers/start.py and handlers/admin.py), which sidesteps any risk of
ambiguous-foreign-key configuration since Button has two FKs into Screen
(screen_id and target_screen_id).
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class MediaType(str, enum.Enum):
    NONE = "none"
    PHOTO = "photo"
    VIDEO = "video"


class ButtonAction(str, enum.Enum):
    URL = "url"
    SCREEN = "screen"


class Screen(Base):
    __tablename__ = "screens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text, default="")
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, name="media_type"), default=MediaType.NONE)
    media_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Button(Base):
    __tablename__ = "buttons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screen_id: Mapped[int] = mapped_column(ForeignKey("screens.id"), index=True)
    label: Mapped[str] = mapped_column(String(64))
    action: Mapped[ButtonAction] = mapped_column(Enum(ButtonAction, name="button_action"))
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    target_screen_id: Mapped[int | None] = mapped_column(ForeignKey("screens.id"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
