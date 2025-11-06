from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any
from .const import MEAL_TYPES


class DietRepo:
    """Repository: operazioni di dominio su SQLite."""

    def __init__(self, db):
        self.db = db

    # -------------------------------
    # TEMPLATE E PIANIFICAZIONE
    # -------------------------------
    async def get_active_template_id(self, profile_id: int | None = None) -> int | None:
        """Ritorna il template attivo per profilo o condiviso."""
        if profile_id is not None:
            async with self.db.conn.execute(
                "SELECT id FROM week_templates WHERE profile_id=? AND is_active=1",
                (profile_id,),
            ) as c:
                r = await c.fetchone()
                if r:
                    return r[0]
        async with self.db.conn.execute(
            "SELECT id FROM week_templates WHERE profile_id IS NULL AND is_active=1"
        ) as c:
            r = await c.fetchone()
        return r[0] if r else None

    async def apply_week_template(self, profile_id: int, start_monday: str, template_id: int):
        """Crea plan_days e pre-popola FREE/SKIP da default_source."""
        start = datetime.fromisoformat(start_monday)

        for i in range(7):
            date_str = (start + timedelta(days=i)).date().isoformat()

            await self.db.conn.execute(
                """
                INSERT OR IGNORE INTO plan_days
                (date, profile_id, template_id, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                (date_str, profile_id, template_id),
            )

            dow = (start.weekday() + i) % 7

            for mt in MEAL_TYPES:
                async with self.db.conn.execute(
                    """
                    SELECT id, title, default_source
                    FROM template_meals
                    WHERE template_id=? AND dow=? AND meal_type=?
                    """,
                    (template_id, dow, mt),
                ) as c:
                    t = await c.fetchone()

                if not t:
                    continue

                _, title, default_source = t

                if default_source == "free":
                    await self.db.conn.execute(
                        """
                        INSERT INTO day_meals
                        (profile_id,date,meal_type,chosen_source,chosen_title,ts)
                        VALUES (?,?,?,?,?,datetime('now'))
                        """,
                        (profile_id, date_str, mt, "free", f"FREE – {mt}"),
                    )
                    await self.db.conn.execute(
                        """
                        INSERT INTO free_meals
                        (profile_id,date,meal_type,notes,ts)
                        VALUES (?,?,?,?,datetime('now'))
                        """,
                        (profile_id, date_str, mt, ""),
                    )

                elif default_source == "skipped":
                    await self.db.conn.execute(
                        """
                        INSERT INTO day_meals
                        (profile_id,date,meal_type,chosen_source,chosen_title,ts)
                        VALUES (?,?,?,?,?,datetime('now'))
                        """,
                        (profile_id, date_str, mt, "skipped", f"SKIP – {mt}"),
                    )

        await self.db.conn.commit()

    # -------------------------------
    # OPERAZIONI GIORNALIERE
    # -------------------------------
    async def set_snack(self, profile_id: int, iso_date: str, period: str, done: bool):
        """Aggiorna o crea lo stato di uno spuntino."""
        await self.db.conn.execute(
            """
            INSERT INTO snacks(profile_id,date,period,done,ts)
            VALUES (?,?,?,?,datetime('now'))
            ON CONFLICT(profile_id,date,period)
            DO UPDATE SET done=excluded.done, ts=datetime('now')
            """,
            (profile_id, iso_date, period, 1 if done else 0),
        )
        await self.db.conn.commit()

    async def set_hunger(self, profile_id: int, iso_date: str, score: int):
        """Aggiorna il livello di fame giornaliero (1–5)."""
        await self.db.conn.execute(
            """
            UPDATE plan_days
            SET hunger=?, updated_at=datetime('now')
            WHERE profile_id=? AND date=?
            """,
            (score, profile_id, iso_date),
        )
        await self.db.conn.commit()

    async def free_meals_used_in_week(self, profile_id: int, iso_date: str) -> int:
        """Conta quanti pasti free risultano in settimana ISO del giorno indicato."""
        query = """
        SELECT COUNT(*)
        FROM free_meals
        WHERE profile_id=?
          AND date BETWEEN date(?, 'weekday 1', '-6 days')
                        AND date(?, 'weekday 1')
        """
        async with self.db.conn.execute(query, (profile_id, iso_date, iso_date)) as c:
            r = await c.fetchone()
        return int(r[0]) if r and r[0] is not None else 0

    async def set_choice(
        self,
        profile_id: int,
        iso_date: str,
        meal_type: str,
        source: str,
        title: str,
        notes: str | None = None,
    ):
        """Registra la scelta effettiva del pasto (proposto, alternativa, free, skip)."""
        await self.db.conn.execute(
            """
            INSERT INTO day_meals
            (profile_id,date,meal_type,chosen_source,chosen_title,notes,ts)
            VALUES (?,?,?,?,?,?,datetime('now'))
            """,
            (profile_id, iso_date, meal_type, source, title, notes or ""),
        )

        if source == "free":
            await self.db.conn.execute(
                """
                INSERT INTO free_meals
                (profile_id,date,meal_type,notes,ts)
                VALUES (?,?,?,?,datetime('now'))
                """,
                (profile_id, iso_date, meal_type, notes or ""),
            )

        await self.db.conn.commit()

    # -------------------------------
    # LETTURE (GIORNO / SETTIMANA)
    # -------------------------------
    async def get_template_meal(self, template_id: int, dow: int, meal_type: str):
        async with self.db.conn.execute(
            """
            SELECT id,title,proposed_items,calories
            FROM template_meals
            WHERE template_id=? AND dow=? AND meal_type=?
            """,
            (template_id, dow, meal_type),
        ) as c:
            return await c.fetchone()

    async def get_template_alternatives(self, template_meal_id: int) -> list[dict]:
        q = """
        SELECT id,title,items,calories
        FROM template_meal_alternatives
        WHERE template_meal_id=?
        """
        out = []
        async with self.db.conn.execute(q, (template_meal_id,)) as c:
            async for r in c:
                out.append(
                    {
                        "id": r[0],
                        "title": r[1],
                        "items": r[2],
                        "calories": r[3],
                    }
                )
        return out

    async def get_day(self, profile_id: int, iso_date: str) -> dict[str, Any]:
        """Ritorna i dati completi di un giorno."""
        async with self.db.conn.execute(
            "SELECT template_id,hunger,notes FROM plan_days WHERE profile_id=? AND date=?",
            (profile_id, iso_date),
        ) as c:
            pd = await c.fetchone()

        if not pd:
            return {
                "date": iso_date,
                "meals": [],
                "snacks": {"am": {"done": False}, "pm": {"done": False}},
                "hunger": None,
            }

        template_id, hunger, notes = pd
        dow = datetime.fromisoformat(iso_date).weekday()

        # Spuntini
        snacks = {"am": {"done": False}, "pm": {"done": False}}
        async with self.db.conn.execute(
            "SELECT period,done,ts FROM snacks WHERE profile_id=? AND date=?",
            (profile_id, iso_date),
        ) as c:
            async for r in c:
                snacks[r[0]] = {"done": bool(r[1]), "ts": r[2]}

        # Pasti
        meals = []
        for mt in MEAL_TYPES:
            async with self.db.conn.execute(
                """
                SELECT chosen_source,chosen_title,notes,ts
                FROM day_meals
                WHERE profile_id=? AND date=? AND meal_type=?
                """,
                (profile_id, iso_date, mt),
            ) as c:
                chosen = await c.fetchone()

            tm = await self.get_template_meal(template_id, dow, mt)
            alts = await self.get_template_alternatives(tm[0]) if tm else []

            meals.append(
                {
                    "meal_type": mt,
                    "proposed": {"title": tm[1], "items": tm[2]} if tm else None,
                    "alternatives": alts,
                    "chosen": {
                        "source": chosen[0],
                        "title": chosen[1],
                        "notes": chosen[2],
                        "ts": chosen[3],
                    }
                    if chosen
                    else None,
                }
            )

        return {"date": iso_date, "hunger": hunger, "notes": notes, "snacks": snacks, "meals": meals}

    async def get_week(self, profile_id: int, start_monday: str) -> list[dict]:
        """Ritorna i dati dei 7 giorni della settimana."""
        start = datetime.fromisoformat(start_monday)
        days = []
        for i in range(7):
            date = (start + timedelta(days=i)).date().isoformat()
            days.append(await self.get_day(profile_id, date))
        return days

    # -------------------------------
    # SWAP
    # -------------------------------
    async def swap_meal(self, profile_id: int, date_from: str, date_to: str, meal_type: str) -> None:
        """Registra uno swap forward-only (audit)."""
        await self.db.conn.execute(
            """
            INSERT INTO swaps(profile_id,date_from,date_to,meal_type,ts)
            VALUES (?,?,?,?,datetime('now'))
            """,
            (profile_id, date_from, date_to, meal_type),
        )
        await self.db.conn.commit()
