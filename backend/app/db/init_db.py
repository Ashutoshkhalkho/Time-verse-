import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.seed import seed_demo_data
from app.db.session import engine as default_engine


async def init_and_seed(use_sqlite: bool = False):
    if use_sqlite or os.getenv("USE_SQLITE", "false").lower() == "true":
        db_path = os.path.abspath("timewise_dev.db")
        sqlite_url = f"sqlite+aiosqlite:///{db_path}"
        print(f"Using SQLite database: {sqlite_url}")
        target_engine = create_async_engine(sqlite_url, connect_args={"check_same_thread": False})
    else:
        target_engine = default_engine
        print(f"Connecting to database: {settings.DATABASE_URL}")

    session_maker = async_sessionmaker(
        bind=target_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    try:
        print("Creating database schema if not exists...")
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("Seeding synthetic demo records and test users...")
        async with session_maker() as session:
            roles_map = await seed_demo_data(session)
            print("\nDemo users successfully initialized:")
            for role, email in roles_map.items():
                print(f"  [{role:12s}] -> {email}")

            print("\nSeeding college scheduling data (rooms, timeslots, teachers, curriculum)...")
            from app.db.seed_scheduling import seed_scheduling_entities
            sched_counts = await seed_scheduling_entities(session)
            print("Scheduling entities seeded:")
            for entity, count in sched_counts.items():
                print(f"  [{entity:16s}] -> {count} items")

            print("\nSeeding DPMS Faculty Directory records...")
            from app.services.faculty_directory.faculty_service import FacultyDirectoryService
            fac_counts = await FacultyDirectoryService.seed_initial_records(session)
            print(f"Faculty directory seeded: {fac_counts}")
        print("\nDatabase initialization complete.")

    except Exception as exc:
        print(f"\n[ERROR] Database initialization failed: {exc}")
        if "ConnectionRefused" in str(exc) or "1225" in str(exc):
            print("\nTIP: PostgreSQL server is not running on localhost:5432.")
            print("1. To start PostgreSQL via Docker Compose: run 'docker compose up -d postgres'")
            print("2. Or to initialize a local SQLite dev database: run 'python -m app.db.init_db --sqlite'")
        sys.exit(1)
    finally:
        await target_engine.dispose()


if __name__ == "__main__":
    is_sqlite = "--sqlite" in sys.argv
    asyncio.run(init_and_seed(use_sqlite=is_sqlite))
