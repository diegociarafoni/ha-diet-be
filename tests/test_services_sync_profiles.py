import pytest
from custom_components.diet.services import async_register_services
from custom_components.diet.db import DietDb
# usa lo stesso tipo del conftest se preferisci
from custom_components.diet.profiles import _FakeUser


@pytest.mark.asyncio
async def test_service_sync_profiles_registers_acl(hass, diet_db, fake_users_three, monkeypatch):
    db, _ = diet_db

    # Registra i servizi dell'integrazione
    await async_register_services(hass, db, coord=None)

    async def _fake_get_users():
        return fake_users_three

    monkeypatch.setattr(hass.auth, "async_get_users", _fake_get_users)

    # Chiama il servizio
    await hass.services.async_call(
        "diet",
        "sync_profiles_from_ha",
        {"prune_missing": False, "include_system": False},
        blocking=True,
    )

    # Verifica profili creati
    async with db.conn.execute("SELECT COUNT(*) FROM diet_profiles") as c:
        count = (await c.fetchone())[0]
    assert count == 3

    # Verifica ACL incrociate
    async with db.conn.execute("SELECT COUNT(*) FROM profile_acl") as c:
        acl_count = (await c.fetchone())[0]
    # 3 profili -> 3*2 = 6 righe (owner->subject per tutte le coppie distinte)
    assert acl_count == 6
