import asyncio
import os
import types
import pytest

from custom_components.diet.db import DietDb


@pytest.fixture
def event_loop():
    """Ensure a fresh event loop per test session (pytest-asyncio compat)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def diet_db(hass, tmp_path):
    """
    Apre un DB DietDb puntando a una .storage temporanea.
    Ritorna (db, storage_dir).
    """
    # Imposta la directory di config di HA su tmp
    storage_dir = tmp_path / "config" / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Monkeypatch hass.config.path per usare la nostra tmp dir
    orig_path = hass.config.path

    def _path(p: str):
        return str(tmp_path / "config" / p)

    hass.config.path = _path  # type: ignore[attr-defined]

    db = DietDb(hass)
    await db.async_open()

    try:
        yield db, storage_dir
    finally:
        await db.async_close()
        # ripristina
        hass.config.path = orig_path  # type: ignore[attr-defined]


class _FakeUser:
    def __init__(self, uid: str, name: str, active=True, system=False):
        self.id = uid
        self.name = name
        self.is_active = active
        self.system_generated = system


@pytest.fixture
def fake_users_three():
    """Tre utenti normali (non di sistema)."""
    return [
        _FakeUser("user-1", "Diego"),
        _FakeUser("user-2", "Compagna"),
        _FakeUser("user-3", "Tablet"),
    ]
