import pytest


@pytest.fixture(autouse=True)
async def _dispose_db_engine():
    """Each pytest-asyncio test runs in its own event loop. Dispose the global
    SQLAlchemy pool after every test so a connection created under a now-closed
    loop is never handed to the next test's loop."""
    yield
    from app.db.session import engine
    try:
        await engine.dispose()
    except Exception:
        pass