# TIMEWISE Backend API

Intelligent Timetable Planning & Impact Management System Backend built with FastAPI, SQLAlchemy 2.0 (async), Google OR-Tools, and PostgreSQL.

## Development Setup

```bash
# In backend directory
uv sync
uv run pytest -v
uv run python app/db/init_db.py --sqlite
uv run uvicorn app.main:app --reload --port 8000
```
