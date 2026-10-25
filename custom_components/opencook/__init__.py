"""Expose an openCook household's shopping list to Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpenCookClient
from .const import CONF_HOUSEHOLD_CODE, CONF_URL
from .coordinator import OpenCookCoordinator

PLATFORMS = [Platform.TODO]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Validate the connection before adding the to-do entity."""
    client = OpenCookClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_HOUSEHOLD_CODE],
        node=f"ha-{entry.entry_id}",
    )
    coordinator = OpenCookCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the entity and its coordinator listener."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
