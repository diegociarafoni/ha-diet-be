from __future__ import annotations
from typing import Any
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from .const import DOMAIN


class DietConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow minimale: una sola istanza, nessuna opzione."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        # Consente una sola configurazione
        existing = any(e.domain == DOMAIN for e in self._async_current_entries())
        if existing:
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Diet Manager", data={})

        return self.async_show_form(step_id="user", data_schema=None)


class DietOptionsFlowHandler(config_entries.OptionsFlow):
    """Opzioni non previste per ora (placeholder)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return self.async_create_entry(title="", data={})
