from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, PLATFORMS
from .db import DietDb
from .coordinator import DietCoordinator
from .services import async_register_services
from .websocket import async_register_ws


async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    db = DietDb(hass)
    await db.async_open()
    coord = DietCoordinator(hass, db)
    await coord.async_initialize()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "db": db, "coordinator": coord}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass, db, coord)
    async_register_ws(hass, db, coord)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data:
        await data["db"].async_close()
    return unloaded
