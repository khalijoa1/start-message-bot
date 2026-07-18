"""Database engine/session. Auto-seeds a default "start" screen on first
boot - the same resilience pattern used in the VVIP membership bot - so
/start always has something to show even before the operator has
customised anything, instead of depending on an admin step happening
first.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    import models  # noqa: F401 - registers models on Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session() as s:
        existing = (
            await s.execute(select(models.Screen).where(models.Screen.key == "start"))
        ).scalars().first()
        if not existing:
            s.add(models.Screen(
                key="start",
                name="Start Message",
                text=(
                    "\U0001F44B Welcome!\n\n"
                    "This is the default start message - the operator hasn't "
                    "customised it yet."
                ),
            ))
            await s.commit()


def session() -> AsyncSession:
    return async_session_factory()
