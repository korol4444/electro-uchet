from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, PLATFORMS
from .coordinator import ElectricityCoordinator

type ElectroUchetConfigEntry = ConfigEntry[ElectricityCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ElectroUchetConfigEntry) -> bool:
    coordinator = ElectricityCoordinator(hass, entry)
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    entry.async_on_unload(
        async_track_state_change_event(
            hass, [entry.data["source_entity"]], coordinator.async_source_changed
        )
    )
    entry.async_on_unload(coordinator.async_register_midnight_reset())
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElectroUchetConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ElectroUchetConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
