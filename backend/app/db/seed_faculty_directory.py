import asyncio
import os
import sys

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
site_packages = os.path.join(base_dir, ".venv", "Lib", "site-packages")
sys.path.insert(0, site_packages)
sys.path.insert(0, base_dir)

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
import app.models  # Ensures all models including FacultyDirectoryMember are registered with Base
from app.services.faculty_directory.faculty_service import FacultyDirectoryService


async def run_seed():
    db_path = os.path.abspath(os.path.join(base_dir, "timewise_dev.db"))
    sqlite_url = f"sqlite+aiosqlite:///{db_path}"
    print(f"[Faculty Directory] Target DB: {sqlite_url}")

    engine = create_async_engine(sqlite_url, connect_args={"check_same_thread": False})

    print("[Faculty Directory] Creating schema if not exists...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    print("[Faculty Directory] Seeding 26 DPMS faculty records idempotently...")
    async with session_maker() as session:
        result = await FacultyDirectoryService.seed_initial_records(session)
        print(f"[Faculty Directory] Seed result: {result}")

    await engine.dispose()
    print("[Faculty Directory] Database operations complete successfully.")


if __name__ == "__main__":
    asyncio.run(run_seed())
