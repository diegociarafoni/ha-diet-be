from __future__ import annotations
from homeassistant.core import HomeAssistant


async def get_profile_id_by_ha_user(hass: HomeAssistant, db, ha_user_id: str) -> int | None:
    """Ritorna il profile_id associato all'utente HA, se presente."""
    async with db.conn.execute(
        "SELECT id FROM diet_profiles WHERE ha_user_id=?",
        (ha_user_id,),
    ) as c:
        row = await c.fetchone()
    return row[0] if row else None


async def ensure_profile(hass: HomeAssistant, db, ha_user_id: str, display_name: str | None = None) -> int:
    """Crea (se mancante) e ritorna il profile_id per l'utente HA."""
    pid = await get_profile_id_by_ha_user(hass, db, ha_user_id)
    if pid is not None:
        return pid
    dn = display_name or ha_user_id
    await db.conn.execute(
        "INSERT INTO diet_profiles(ha_user_id,display_name,created_at) "
        "VALUES(?,?,datetime('now'))",
        (ha_user_id, dn),
    )
    await db.conn.commit()
    async with db.conn.execute(
        "SELECT id FROM diet_profiles WHERE ha_user_id=?",
        (ha_user_id,),
    ) as c2:
        r2 = await c2.fetchone()
    return r2[0]


async def check_acl_read(db, owner_profile_id: int, subject_profile_id: int) -> bool:
    """Controlla permesso di lettura: consentito se self o ACL can_read=1."""
    if owner_profile_id == subject_profile_id:
        return True
    async with db.conn.execute(
        "SELECT can_read FROM profile_acl WHERE owner_profile_id=? AND subject_profile_id=?",
        (owner_profile_id, subject_profile_id),
    ) as c:
        r = await c.fetchone()
    return bool(r and r[0])


async def check_acl_write(db, owner_profile_id: int, subject_profile_id: int) -> bool:
    """Controlla permesso di scrittura: consentito se self o ACL can_write=1."""
    if owner_profile_id == subject_profile_id:
        return True
    async with db.conn.execute(
        "SELECT can_write FROM profile_acl WHERE owner_profile_id=? AND subject_profile_id=?",
        (owner_profile_id, subject_profile_id),
    ) as c:
        r = await c.fetchone()
    return bool(r and r[0])
