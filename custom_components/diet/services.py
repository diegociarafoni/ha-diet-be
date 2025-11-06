from __future__ import annotations
from datetime import timedelta
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    DEFAULTS,
    CONF_FREE_MEALS_PER_WEEK,
    CONF_FREE_LIMIT_MODE,
    MEAL_TYPES,
)
from .repository import DietRepo
from .util import get_profile_id_by_ha_user, check_acl_read, check_acl_write
from .profiles import sync_profiles_from_ha  # <-- NUOVO


# ---- Schemi di validazione ---------------------------------------------------

SCHEMA_OWNER = vol.Schema({vol.Required("owner_profile_id"): int})

SCHEMA_APPLY = SCHEMA_OWNER.extend(
    {
        vol.Required("start_date"): cv.date,
        vol.Optional("template_id"): int,
    }
)

SCHEMA_SWAP = SCHEMA_OWNER.extend(
    {
        vol.Required("date_from"): cv.date,
        vol.Required("date_to"): cv.date,
        vol.Required("meal_type"): vol.In(MEAL_TYPES),
    }
)

SCHEMA_SNACK = SCHEMA_OWNER.extend(
    {
        vol.Required("date"): cv.date,
        vol.Required("period"): vol.In(["am", "pm"]),
        vol.Required("done"): bool,
    }
)

SCHEMA_HUNGER = SCHEMA_OWNER.extend(
    {
        vol.Required("date"): cv.date,
        vol.Required("score"): vol.All(int, vol.Range(min=1, max=5)),
    }
)

SCHEMA_CHOICE = SCHEMA_OWNER.extend(
    {
        vol.Required("date"): cv.date,
        vol.Required("meal_type"): vol.In(MEAL_TYPES),
        vol.Required("source"): vol.In(["proposed", "alternative", "free", "skipped"]),
        vol.Optional("title"): str,          # consigliato: titolo breve
        # futuro: validare appartenenza al template
        vol.Optional("alternative_id"): int,
        vol.Optional("notes"): str,
    }
)

# NUOVO: servizio di sync profili da HA User Registry
SCHEMA_SYNC_PROFILES = vol.Schema(
    {
        # prudenza: di default NON rimuove profili orfani
        vol.Optional("prune_missing", default=False): bool,
        # di default esclude utenti di sistema
        vol.Optional("include_system", default=False): bool,
    }
)


# ---- Registrazione servizi ---------------------------------------------------

async def async_register_services(hass: HomeAssistant, db, coord) -> None:
    repo = DietRepo(db)

    async def _authorize(call: ServiceCall, owner_pid: int, write: bool = False) -> int:
        """Ritorna il subject_profile_id dell'utente chiamante e verifica i permessi."""
        subject_uid = call.context.user_id
        subject_pid = await get_profile_id_by_ha_user(hass, db, subject_uid)
        if subject_pid is None:
            raise ValueError("Profilo non registrato per l'utente corrente")
        allowed = await (check_acl_write(db, owner_pid, subject_pid) if write else check_acl_read(db, owner_pid, subject_pid))
        if not allowed:
            raise ValueError("Permesso negato")
        return subject_pid

    # ------------------ Servizi core dominio diet ------------------

    async def _apply(call: ServiceCall) -> None:
        data = SCHEMA_APPLY(call.data)
        owner_pid = data["owner_profile_id"]
        await _authorize(call, owner_pid, write=True)

        dt = data["start_date"]
        monday = (dt - timedelta(days=dt.weekday())).isoformat()

        tpl_id = data.get("template_id") or await repo.get_active_template_id(owner_pid)
        if tpl_id is None:
            raise ValueError("Nessun template attivo")

        await repo.apply_week_template(owner_pid, monday, tpl_id)

    async def _swap(call: ServiceCall) -> None:
        data = SCHEMA_SWAP(call.data)
        owner_pid = data["owner_profile_id"]
        await _authorize(call, owner_pid, write=True)

        dfrom, dto = data["date_from"], data["date_to"]
        if dto <= dfrom:
            raise ValueError(
                "Scambio consentito solo verso giorni successivi della stessa settimana")
        if dfrom.isocalendar()[1] != dto.isocalendar()[1]:
            raise ValueError("Lo scambio deve rimanere nella stessa settimana")

        await repo.swap_meal(owner_pid, dfrom.isoformat(), dto.isoformat(), data["meal_type"])

    async def _snack(call: ServiceCall) -> None:
        data = SCHEMA_SNACK(call.data)
        owner_pid = data["owner_profile_id"]
        await _authorize(call, owner_pid, write=True)
        await repo.set_snack(owner_pid, data["date"].isoformat(), data["period"], data["done"])

    async def _hunger(call: ServiceCall) -> None:
        data = SCHEMA_HUNGER(call.data)
        owner_pid = data["owner_profile_id"]
        await _authorize(call, owner_pid, write=True)
        await repo.set_hunger(owner_pid, data["date"].isoformat(), data["score"])

    async def _choice(call: ServiceCall) -> None:
        data = SCHEMA_CHOICE(call.data)
        owner_pid = data["owner_profile_id"]
        await _authorize(call, owner_pid, write=True)

        src = data["source"]
        title = data.get("title") or ""

        # Quota free: applica policy hard/soft
        if src == "free":
            used = await repo.free_meals_used_in_week(owner_pid, data["date"].isoformat())
            quota = DEFAULTS[CONF_FREE_MEALS_PER_WEEK]
            if used >= quota and DEFAULTS[CONF_FREE_LIMIT_MODE] == "hard":
                raise ValueError("Quota pasti free settimanale superata")

        await repo.set_choice(
            owner_pid,
            data["date"].isoformat(),
            data["meal_type"],
            src,
            title,
            data.get("notes"),
        )

    # ------------------ NUOVO: servizio di sincronizzazione profili ------------------

    async def _sync_profiles(call: ServiceCall) -> None:
        """Sincronizza diet_profiles con l'user registry di Home Assistant."""
        data = SCHEMA_SYNC_PROFILES(call.data)
        total = await sync_profiles_from_ha(
            hass,
            db,
            prune_missing=data["prune_missing"],
            include_system=data["include_system"],
        )
        # Nessun result richiesto dai servizi HA; log informativo
        hass.bus.async_fire(f"{DOMAIN}_profiles_synced", {"count": total})

    # Registrazione servizi
    hass.services.async_register(DOMAIN, "apply_week_template", _apply)
    hass.services.async_register(DOMAIN, "swap_meal", _swap)
    hass.services.async_register(DOMAIN, "set_snack", _snack)
    hass.services.async_register(DOMAIN, "set_hunger", _hunger)
    hass.services.async_register(DOMAIN, "set_choice", _choice)
    hass.services.async_register(
        DOMAIN, "sync_profiles_from_ha", _sync_profiles)  # <-- NUOVO
