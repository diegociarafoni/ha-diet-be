from __future__ import annotations
from datetime import datetime, timedelta

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .repository import DietRepo
from .util import get_profile_id_by_ha_user, check_acl_read


async def async_register_ws(hass: HomeAssistant, db, coord) -> None:
    """Registro dei comandi WebSocket per la UI."""

    repo = DietRepo(db)

    async def _subject_pid(connection) -> int | None:
        """Profile ID dell'utente HA connesso via WS."""
        uid = connection.user.id
        return await get_profile_id_by_ha_user(hass, db, uid)

    # ---------------------------------------------------------------------
    # CAPABILITIES
    # ---------------------------------------------------------------------
    @websocket_api.websocket_command({"type": "diet/get_capabilities"})
    @websocket_api.async_response
    async def ws_get_capabilities(hass, connection, msg):
        subject = await _subject_pid(connection)
        if subject is None:
            connection.send_result(
                msg["id"], {"subject_profile_id": None, "profiles": []})
            return

        profiles = []
        async with db.conn.execute("SELECT id,display_name FROM diet_profiles") as c:
            async for r in c:
                pid, name = r
                can_read = await check_acl_read(db, pid, subject)
                # policy: solo self in scrittura (di default)
                can_write = (pid == subject)
                profiles.append(
                    {
                        "profile_id": pid,
                        "display_name": name,
                        "can_read": bool(can_read),
                        "can_write": bool(can_write),
                    }
                )

        connection.send_result(
            msg["id"], {"subject_profile_id": subject, "profiles": profiles})

    # ---------------------------------------------------------------------
    # GET DAY
    # ---------------------------------------------------------------------
    @websocket_api.websocket_command(
        {
            "type": "diet/get_day",
            "owner_profile_id": int,
            "date": str,  # ISO YYYY-MM-DD
        }
    )
    @websocket_api.async_response
    async def ws_get_day(hass, connection, msg):
        subject = await _subject_pid(connection)
        owner = int(msg.get("owner_profile_id"))
        if not await check_acl_read(db, owner, subject):
            connection.send_error(msg["id"], "forbidden", "Permesso negato")
            return

        date = msg.get("date")
        res = await repo.get_day(owner, date)
        connection.send_result(msg["id"], res)

    # ---------------------------------------------------------------------
    # GET WEEK
    # ---------------------------------------------------------------------
    @websocket_api.websocket_command(
        {
            "type": "diet/get_week",
            "owner_profile_id": int,
            "start_date": str,  # qualsiasi giorno della settimana; sarà normalizzato al lunedì
        }
    )
    @websocket_api.async_response
    async def ws_get_week(hass, connection, msg):
        subject = await _subject_pid(connection)
        owner = int(msg.get("owner_profile_id"))
        if not await check_acl_read(db, owner, subject):
            connection.send_error(msg["id"], "forbidden", "Permesso negato")
            return

        dt = datetime.fromisoformat(msg.get("start_date"))
        monday = (dt - timedelta(days=dt.weekday())).date().isoformat()
        days = await repo.get_week(owner, monday)
        connection.send_result(msg["id"], {"start": monday, "days": days})

    # ---------------------------------------------------------------------
    # NEXT MEALS (vista comune pranzo/cena)
    # ---------------------------------------------------------------------
    @websocket_api.websocket_command(
        {
            "type": "diet/get_next_meals",
            "owner_profile_ids": list,  # [int, ...]
            "horizon_hours": int,       # default 36
        }
    )
    @websocket_api.async_response
    async def ws_get_next_meals(hass, connection, msg):
        subject = await _subject_pid(connection)
        owners = [int(x) for x in msg.get("owner_profile_ids", [])]
        now = datetime.now()
        horizon = now + timedelta(hours=int(msg.get("horizon_hours", 36)))

        payload = {
            "now": now.isoformat(timespec="seconds"),
            "horizon": horizon.isoformat(timespec="seconds"),
            "profiles": [],
        }

        for pid in owners:
            if not await check_acl_read(db, pid, subject):
                continue

            meals = []
            # oggi
            today = now.date().isoformat()
            day = await repo.get_day(pid, today)

            for mt in ("lunch", "dinner"):
                m = next((x for x in day["meals"]
                         if x["meal_type"] == mt), None)
                if m:
                    status = (m["chosen"]["source"] if m.get(
                        "chosen") else "planned")
                    title = (
                        m["chosen"]["title"]
                        if m.get("chosen")
                        else (m["proposed"]["title"] if m.get("proposed") else "")
                    )
                    meals.append({"type": mt, "date": today,
                                 "title": title, "status": status})

            payload["profiles"].append(
                {
                    "profile_id": pid,
                    "display_name": "",  # opzionale: popolare con join su diet_profiles
                    "upcoming": meals,
                }
            )

        connection.send_result(msg["id"], payload)

    # Registrazione comandi
    hass.components.websocket_api.async_register_command(ws_get_capabilities)
    hass.components.websocket_api.async_register_command(ws_get_day)
    hass.components.websocket_api.async_register_command(ws_get_week)
    hass.components.websocket_api.async_register_command(ws_get_next_meals)
