from __future__ import annotations
import os
import aiosqlite
from homeassistant.core import HomeAssistant
from .const import DB_FILENAME

SCHEMA_VERSION = 5

# -------------------------------
# SCHEMA DI DATABASE (SQLite)
# -------------------------------
CREATE_BASE = [
    """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """,
    # Profili utenti HA
    """
    CREATE TABLE IF NOT EXISTS diet_profiles (
        id INTEGER PRIMARY KEY,
        ha_user_id TEXT NOT NULL,
        display_name TEXT NOT NULL,
        color TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(ha_user_id)
    );
    """,
    # ACL di lettura/scrittura tra profili
    """
    CREATE TABLE IF NOT EXISTS profile_acl (
        id INTEGER PRIMARY KEY,
        owner_profile_id INTEGER NOT NULL,
        subject_profile_id INTEGER NOT NULL,
        can_read INTEGER NOT NULL DEFAULT 1,
        can_write INTEGER NOT NULL DEFAULT 0,
        UNIQUE(owner_profile_id, subject_profile_id)
    );
    """,
    # Template settimanali
    """
    CREATE TABLE IF NOT EXISTS week_templates (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER, -- NULL => condiviso
        name TEXT NOT NULL,
        description TEXT,
        is_active INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    # Pasti nei template
    """
    CREATE TABLE IF NOT EXISTS template_meals (
        id INTEGER PRIMARY KEY,
        template_id INTEGER NOT NULL,
        dow INTEGER NOT NULL CHECK(dow BETWEEN 0 AND 6),
        meal_type TEXT NOT NULL CHECK(meal_type IN ('breakfast','lunch','dinner','snack_am','snack_pm')),
        title TEXT,
        proposed_label TEXT,
        proposed_items TEXT,
        calories INTEGER,
        required INTEGER NOT NULL,
        default_source TEXT CHECK(default_source IN ('proposed','free','skipped')) DEFAULT 'proposed',
        FOREIGN KEY(template_id) REFERENCES week_templates(id)
    );
    """,
    # Alternative per i pasti
    """
    CREATE TABLE IF NOT EXISTS template_meal_alternatives (
        id INTEGER PRIMARY KEY,
        template_meal_id INTEGER NOT NULL,
        title TEXT,
        label TEXT,
        items TEXT,
        calories INTEGER,
        FOREIGN KEY(template_meal_id) REFERENCES template_meals(id)
    );
    """,
    # Giorni pianificati
    """
    CREATE TABLE IF NOT EXISTS plan_days (
        date TEXT PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        template_id INTEGER NOT NULL,
        hunger INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    # Pasti scelti o completati
    """
    CREATE TABLE IF NOT EXISTS day_meals (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        meal_type TEXT NOT NULL CHECK(meal_type IN ('breakfast','lunch','dinner','snack_am','snack_pm')),
        chosen_source TEXT NOT NULL CHECK(chosen_source IN ('proposed','alternative','free','skipped')),
        chosen_title TEXT,
        chosen_label TEXT,
        chosen_items TEXT,
        notes TEXT,
        ts TEXT
    );
    """,
    # Storico swap
    """
    CREATE TABLE IF NOT EXISTS swaps (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        date_from TEXT NOT NULL,
        date_to TEXT NOT NULL,
        meal_type TEXT NOT NULL,
        ts TEXT NOT NULL
    );
    """,
    # Spuntini
    """
    CREATE TABLE IF NOT EXISTS snacks (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        period TEXT NOT NULL CHECK(period IN ('am','pm')),
        done INTEGER NOT NULL,
        ts TEXT,
        UNIQUE(profile_id, date, period)
    );
    """,
    # Pasti free
    """
    CREATE TABLE IF NOT EXISTS free_meals (
        id INTEGER PRIMARY KEY,
        profile_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        meal_type TEXT NOT NULL,
        notes TEXT,
        ts TEXT NOT NULL
    );
    """,
    # Indici
    """
    CREATE INDEX IF NOT EXISTS idx_plan_days_p ON plan_days(profile_id, date);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_day_meals_p ON day_meals(profile_id, date, meal_type);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_snacks_p ON snacks(profile_id, date, period);
    """,
]


class DietDb:
    """Gestione connessione SQLite + migrazioni."""

    def __init__(self, hass: HomeAssistant):
        self._hass = hass
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None
        return self._conn

    async def async_open(self):
        """Apre il database e applica le migrazioni."""
        path = os.path.join(self._hass.config.path(".storage"), DB_FILENAME)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._conn = await aiosqlite.connect(path)
        await self._conn.execute("PRAGMA foreign_keys = ON;")
        await self._migrate()

    async def _migrate(self):
        """Esegue la creazione o aggiornamento schema."""
        try:
            async with self._conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ) as c:
                row = await c.fetchone()
            current = int(row[0]) if row else 0
        except Exception:
            current = 0

        if current == 0:
            for stmt in CREATE_BASE:
                await self._conn.executescript(stmt)
            await self._conn.execute(
                "INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            await self._conn.commit()
            return

        # future migrations (incrementali)
        # while current < SCHEMA_VERSION:
        #     apply migration steps...

    async def async_close(self):
        """Chiude la connessione al DB."""
        if self._conn:
            await self._conn.close()
            self._conn = None
