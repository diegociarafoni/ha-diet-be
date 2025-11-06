import json
import pytest
from datetime import date, timedelta

from custom_components.diet.websocket import async_register_ws
from custom_components.diet.db import DietDb


@pytest.mark.asyncio
async def test_ws_capabilities_and_reads_acl(hass, hass_ws_client, hass_admin_user, diet_db):
    """
    Verifica:
    - diet/get_capabilities: il profilo del client WS ha can_write=True su se stesso e can_read sugli altri se ACL presente.
    - diet/get_day e diet/get_week rispettano l'ACL (forbidden se manca).
    """
    db, _ = diet_db

    # Registra WS handler dell'integrazione
    await async_register_ws(hass, db, coord=None)

    # Crea profili diet: uno per l'admin user connesso, uno per "altro"
    admin_uid = hass_admin_user.id
    await db.conn.execute(
        "INSERT INTO diet_profiles(ha_user_id,display_name,created_at) VALUES(?,?,datetime('now'))",
        (admin_uid, "Admin"),
    )
    await db.conn.execute(
        "INSERT INTO diet_profiles(ha_user_id,display_name,created_at) VALUES(?,?,datetime('now'))",
        ("user-other", "Altra Persona"),
    )
    # Recupera gli id interni
    async with db.conn.execute("SELECT id, ha_user_id FROM diet_profiles") as c:
        rows = [r async for r in c]
    pid_by_uid = {uid: pid for (pid, uid) in rows}
    pid_admin = pid_by_uid[admin_uid]
    pid_other = pid_by_uid["user-other"]

    # ACL: consenti lettura dell'altro profilo (read-only)
    await db.conn.execute(
        "INSERT INTO profile_acl(owner_profile_id,subject_profile_id,can_read,can_write) VALUES(?,?,1,0)",
        (pid_other, pid_admin),
    )
    await db.conn.commit()

    # Connessione WS come admin user
    client = await hass_ws_client(hass)

    # ---- capabilities
    await client.send_json({"id": 1, "type": "diet/get_capabilities"})
    resp = await client.receive_json()
    assert resp["success"] is True
    data = resp["result"]
    assert data["subject_profile_id"] == pid_admin
    profs = {p["profile_id"]: p for p in data["profiles"]}
    assert profs[pid_admin]["can_write"] is True
    assert profs[pid_admin]["can_read"] is True
    assert profs[pid_other]["can_read"] is True
    assert profs[pid_other]["can_write"] is False

    # ---- get_day consentito (other -> admin può leggere per ACL)
    today = date.today().isoformat()
    await client.send_json(
        {"id": 2, "type": "diet/get_day", "owner_profile_id": pid_other, "date": today}
    )
    resp2 = await client.receive_json()
    assert resp2["success"] is True
    assert resp2["result"]["date"] == today
    assert "meals" in resp2["result"]

    # ---- get_week con normalizzazione al lunedì
    anyday = date.today().isoformat()
    await client.send_json(
        {"id": 3, "type": "diet/get_week",
            "owner_profile_id": pid_other, "start_date": anyday}
    )
    resp3 = await client.receive_json()
    assert resp3["success"] is True
    week = resp3["result"]
    assert "start" in week and "days" in week
    assert len(week["days"]) == 7

    # ---- ACL: profilo senza ACL -> forbidden
    # Crea un terzo profilo senza ACL
    await db.conn.execute(
        "INSERT INTO diet_profiles(ha_user_id,display_name,created_at) VALUES(?,?,datetime('now'))",
        ("user-noacl", "Sconosciuto"),
    )
    await db.conn.commit()
    async with db.conn.execute(
        "SELECT id FROM diet_profiles WHERE ha_user_id=?", ("user-noacl",)
    ) as c:
        pid_noacl = (await c.fetchone())[0]

    await client.send_json(
        {"id": 4, "type": "diet/get_day", "owner_profile_id": pid_noacl, "date": today}
    )
    resp4 = await client.receive_json()
    assert resp4["success"] is False
    assert resp4["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_ws_next_meals_minimal(hass, hass_ws_client, hass_admin_user, diet_db):
    """
    Verifica diet/get_next_meals:
    - ritorna struttura valida con pranzo/cena per il profilo del client,
    - pesca 'planned' se non ci sono scelte registrate.
    """
    db, _ = diet_db
    await async_register_ws(hass, db, coord=None)

    admin_uid = hass_admin_user.id
    # profilo admin
    await db.conn.execute(
        "INSERT INTO diet_profiles(ha_user_id,display_name,created_at) VALUES(?,?,datetime('now'))",
        (admin_uid, "Admin"),
    )
    async with db.conn.execute(
        "SELECT id FROM diet_profiles WHERE ha_user_id=?", (admin_uid,)
    ) as c:
        pid_admin = (await c.fetchone())[0]

    # Crea un template condiviso attivo con pranzo e cena "proposti" per oggi
    await db.conn.execute(
        "INSERT INTO week_templates(profile_id,name,description,is_active,created_at,updated_at) "
        "VALUES (NULL,'Condiviso','Base',1,datetime('now'),datetime('now'))"
    )
    async with db.conn.execute("SELECT id FROM week_templates WHERE is_active=1") as c:
        tpl_id = (await c.fetchone())[0]

    # Inserisci proposte per il dow odierno
    from datetime import datetime as _dt
    dow = _dt.today().weekday()
    for meal_type, title in (("lunch", "Insalata di pollo"), ("dinner", "Salmone e patate")):
        await db.conn.execute(
            "INSERT INTO template_meals(template_id,dow,meal_type,title,required,default_source) "
            "VALUES (?,?,?,?,?,?)",
            (tpl_id, dow, meal_type, title, 1, "proposed"),
        )
    # Applica il template per questa settimana al profilo admin
    from custom_components.diet.repository import DietRepo

    repo = DietRepo(db)
    monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    await repo.apply_week_template(pid_admin, monday, tpl_id)

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 10,
            "type": "diet/get_next_meals",
            "owner_profile_ids": [pid_admin],
            "horizon_hours": 24,
        }
    )
    resp = await client.receive_json()
    assert resp["success"] is True
    payload = resp["result"]
    assert "profiles" in payload and len(payload["profiles"]) == 1
    upcoming = payload["profiles"][0]["upcoming"]
    # Dovremmo avere entries per lunch e dinner (planned, perchè non abbiamo marcato chosen)
    types = {m["type"] for m in upcoming}
    assert {"lunch", "dinner"}.issubset(types)
    for m in upcoming:
        assert m["status"] in {"planned", "proposed",
                               "alternative", "free", "skipped"}
