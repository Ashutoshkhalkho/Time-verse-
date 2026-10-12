import sys
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
site_packages = os.path.join(base_dir, ".venv", "Lib", "site-packages")

sys.path.insert(0, site_packages)
sys.path.insert(0, base_dir)

db_path = os.path.join(base_dir, "timewise_dev.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
os.environ["DATABASE_SYNC_URL"] = f"sqlite:///{db_path}"

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
