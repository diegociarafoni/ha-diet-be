from __future__ import annotations
from typing import Dict, Tuple, List
from homeassistant.core import HomeAssistant


async def _existing_profiles(db) -> Dict[str, Tuple[int, str]]:
    """
    Ritorna mappa ha_user_id -> (profile_id, display_name) per i profili già presenti.
    """
    out: Dict[str, Tuple[int, str]] = {}
    async with db.conn.execute("SELECT id, ha_user_id, display_name FROM diet_profiles") as c:
        async for row in c:
            out[row[1]] = (row[0], row[2])
    return out


async def _ensure_profile(db, ha_user_id: str, display_name: str) -> int:
    """
    Inserisce o aggiorna un profilo e ritorna il profile_id.
    """
    # prova fetch
    async with db.conn.execute(
        "SELECT id, display_name FROM diet_profiles WHERE ha_user_id=?",
        (ha_user_id,),
    ) as c:
        row = await c.fetchone()

    if row:
        pid, current_name = row
        if current_name != display_name:
            await db.conn.execute(
                "UPDATE diet_profiles SET display_name=?, created_at=created_at WHERE id=?",
                (display_name, pid),
            )
        return pid

    # insert
    await db.conn.execute(
        "INSERT INTO diet_profiles(ha_user_id, display_name, created_at) "
        "VALUES(?,?, datetime('now'))",
        (ha_user_id, display_name),
    )
    async with db.conn.execute(
        "SELECT id FROM diet_profiles WHERE ha_user_id=?",
        (ha_user_id,),
    ) as c2:
        row2 = await c2.fetchone()
    return int(row2[0])


async def _prune_missing(db, present_ha_ids: List[str]) -> None:
    """
    (Opzionale) Rimuove profili che non hanno più un corrispondente utente HA.
    ATTENZIONE: questo cancella anche eventuali dati associati via FK (se attive).
    Valuta bene prima di abilitarlo in produzione.
    """
    # Qui ci limitiamo a non implementare la cancellazione hard per prudenza.
    return


async def _ensure_cross_read_acl(db, profile_ids: List[int]) -> None:
    """
    Imposta ACL di default: tra profili diversi => can_read=1, can_write=0.
    Non crea righe self->self (self handled a livello logico).
    """
    for owner in profile_ids:
        for subject in profile_ids:
            if owner == subject:
                continue
            # INSERT OR IGNORE; poi eventuale update per normalizzare flags
            await db.conn.execute(
                "INSERT OR IGNORE INTO profile_acl(owner_profile_id, subject_profile_id, can_read, can_write) "
                "VALUES(?, ?, 1, 0)",
                (owner, subject),
            )
            # Forza policy a (1,0) se già esiste ma diversa
            await db.conn.execute(
                "UPDATE profile_acl SET can_read=1, can_write=0 "
                "WHERE owner_profile_id=? AND subject_profile_id=?",
                (owner, subject),
            )


async def sync_profiles_from_ha(
    hass: HomeAssistant,
    db,
    *,
    prune_missing: bool = False,
    include_system: bool = False,
) -> int:
    """
    Sincronizza diet_profiles con gli utenti HA:
    - crea/aggiorna i profili per ogni utente HA attivo (non system, salvo include_system=True),
    - imposta ACL incrociate read-only tra profili diversi.

    Ritorna il numero di profili presenti dopo la sincronizzazione.
    """
    # 1) Leggi utenti da HA
    # Nota: .async_get_users() ritorna User objects con .id, .name, .is_active, .system_generated
    ha_users = await hass.auth.async_get_users()
    selected = [
        u for u in ha_users
        if u.is_active and (include_system or not u.system_generated)
    ]

    # 2) Snapshot profili esistenti
    existing = await _existing_profiles(db)

    # 3) Crea/aggiorna profili
    profile_ids: List[int] = []
    for u in selected:
        display = u.name or f"User {u.id[:8]}"
        pid = await _ensure_profile(db, u.id, display)
        profile_ids.append(pid)

    # 4) (Opzionale) pruning di profili orfani
    if prune_missing:
        await _prune_missing(db, [u.id for u in selected])

    # 5) ACL read-only incrociate
    await _ensure_cross_read_acl(db, profile_ids)

    await db.conn.commit()
    return len(profile_ids)
