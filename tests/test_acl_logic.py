import pytest
from custom_components.diet.util import check_acl_read, check_acl_write


@pytest.mark.asyncio
async def test_acl_self_is_allowed(diet_db):
    db, _ = diet_db
    # profilo fittizio
    await db.conn.execute(
        "INSERT INTO diet_profiles(ha_user_id,display_name,created_at) VALUES(?,?,datetime('now'))",
        ("user-1", "Diego"),
    )
    async with db.conn.execute("SELECT id FROM diet_profiles WHERE ha_user_id='user-1'") as c:
        pid = (await c.fetchone())[0]

    assert await check_acl_read(db, pid, pid) is True
    assert await check_acl_write(db, pid, pid) is True


@pytest.mark.asyncio
async def test_acl_cross_read_only(diet_db):
    db, _ = diet_db
    # due profili
    await db.conn.executemany(
        "INSERT INTO diet_profiles(ha_user_id,display_name,created_at) VALUES(?,?,datetime('now'))",
        [("user-1", "Diego"), ("user-2", "Compagna")],
    )
    await db.conn.executemany(
        "INSERT INTO profile_acl(owner_profile_id,subject_profile_id,can_read,can_write) VALUES(?,?,?,?)",
        # (owner, subject, read, write) -> lettura consentita, scrittura no
        [(1, 2, 1, 0), (2, 1, 1, 0)],
    )
    await db.conn.commit()

    assert await check_acl_read(db, 1, 2) is True
    assert await check_acl_write(db, 1, 2) is False
