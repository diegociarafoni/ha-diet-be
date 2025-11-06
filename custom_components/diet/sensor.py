from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    """Crea i sensori per ciascun profilo presente nel DB."""
    db = hass.data[DOMAIN][entry.entry_id]["db"]

    profiles: list[tuple[int, str]] = []
    async with db.conn.execute("SELECT id, display_name FROM diet_profiles") as c:
        async for row in c:
            profiles.append((row[0], row[1]))

    entities: list[SensorEntity] = []
    for profile_id, display_name in profiles:
        entities.append(HungerAvgSensor(
            hass, entry.entry_id, profile_id, display_name))
        entities.append(SnacksCompletedTodaySensor(
            hass, entry.entry_id, profile_id, display_name))
        entities.append(FreeMealsUsedWeekSensor(
            hass, entry.entry_id, profile_id, display_name))

    async_add_entities(entities)


class BaseDietSensor(SensorEntity):
    """Base class con utilità comuni."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry_id: str, profile_id: int, display_name: str):
        self.hass = hass
        self._entry_id = entry_id
        self.profile_id = profile_id
        self.display_name = display_name

    @property
    def _db(self):
        return self.hass.data[DOMAIN][self._entry_id]["db"]


class HungerAvgSensor(BaseDietSensor):
    """Media mobile 7 giorni del punteggio di fame (1–5)."""

    @property
    def name(self) -> str:
        return f"Diet Hunger Score ({self.display_name})"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_hunger_avg_{self.profile_id}"

    async def async_update(self) -> None:
        q = """
        SELECT AVG(hunger)
        FROM plan_days
        WHERE profile_id=?
          AND date>=date('now','-6 days')
          AND hunger IS NOT NULL
        """
        async with self._db.conn.execute(q, (self.profile_id,)) as c:
            r = await c.fetchone()
        self._attr_native_value = round(
            r[0], 1) if r and r[0] is not None else None


class SnacksCompletedTodaySensor(BaseDietSensor):
    """Numero di spuntini (AM/PM) marcati come fatti oggi (0..2)."""

    @property
    def name(self) -> str:
        return f"Snacks Completed Today ({self.display_name})"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_snacks_today_{self.profile_id}"

    async def async_update(self) -> None:
        q = """
        SELECT COALESCE(SUM(done), 0)
        FROM snacks
        WHERE profile_id=?
          AND date=date('now')
        """
        async with self._db.conn.execute(q, (self.profile_id,)) as c:
            r = await c.fetchone()
        self._attr_native_value = int(r[0]) if r and r[0] is not None else 0


class FreeMealsUsedWeekSensor(BaseDietSensor):
    """Conteggio pasti FREE usati nella settimana corrente (lun-dom)."""

    @property
    def name(self) -> str:
        return f"Free Meals Used (Week) ({self.display_name})"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_free_meals_week_{self.profile_id}"

    async def async_update(self) -> None:
        q = """
        SELECT COUNT(*)
        FROM free_meals
        WHERE profile_id=?
          AND date BETWEEN date('now', 'weekday 1', '-6 days')
                        AND date('now', 'weekday 1')
        """
        async with self._db.conn.execute(q, (self.profile_id,)) as c:
            r = await c.fetchone()
        self._attr_native_value = int(r[0]) if r and r[0] is not None else 0
