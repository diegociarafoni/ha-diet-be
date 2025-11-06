import pytest
from custom_components.diet.profiles import sync_profiles_from_ha


@pytest.mark.asyncio
async def test_sync_profiles_creates_entries_and_acl(hass, diet_db, fake_users_three, monkeypatch):
    db, _ = diet_db

    async def _fake_get_users():
        return fake_users_three

    monkeypatch.setattr(hass.auth, "async_get_users", _fake_get_users)

    count = await sync_profiles_from_ha(hass, db, prune_missing=False, include_system=False)
    assert count == 3

    # Verifica profili
    async with db.conn.execute("SELECT ha_user_id, display_name FROM diet_profiles ORDER BY ha_user_id") as c:
        rows = [r async for r in c]
    assert len(rows) == 3
    assert rows[0][1] == "Compagna" or rows[1][1] == "Compagna"

    # Mappa profile_id per ACL check
    async with db.conn.execute("SELECT id, ha_user_id FROM diet_profiles") as c:
        pid_by_uid = {r[1]: r[0] async for r in c}

    pids = list(pid_by_uid.values())
    # Per ogni coppia owner!=subject deve esserci ACL (can_read=1, can_write=0)
    for owner in pids:
        for subject in pids:
            if owner == subject:
                continue
            async with db.conn.execute(
                "SELECT can_read, can_write FROM profile_acl WHERE owner_profile_id=? AND subject_profile_id=?",
                (owner, subject),
            ) as c:
                row = await c.fetchone()
            assert row is not None, f"ACL mancante {owner}->{subject}"
            assert row[0] == 1 and row[1] == 0
