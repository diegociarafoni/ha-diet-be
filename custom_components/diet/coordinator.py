from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .db import DietDb


class DietCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, db: DietDb):
        super().__init__(hass, name="diet", update_interval=None)
        self.db = db

    async def async_initialize(self):
        return
