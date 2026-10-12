import sys
import os
import asyncio

base_dir = os.path.dirname(os.path.abspath(__file__))
site_packages = os.path.join(base_dir, ".venv", "Lib", "site-packages")

sys.path.insert(0, site_packages)
sys.path.insert(0, base_dir)

# Enforce local SQLite file
db_file = os.path.join(base_dir, "timewise_dev.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"
os.environ["DATABASE_SYNC_URL"] = f"sqlite:///{db_file}"

from app.db.base import Base
from app.db.session import engine, AsyncSessionLocal
from app.db.seed import seed_demo_data
from app.db.seed_scheduling import seed_scheduling_entities

async def main():
    print(f"Initializing database at: {db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        print("Seeding core demo data...")
        await seed_demo_data(session)
        print("Seeding scheduling entities & master timetable...")
        await seed_scheduling_entities(session)
        await session.commit()
    
    print("Database initialization and seeding complete!")

if __name__ == "__main__":
    asyncio.run(main())
