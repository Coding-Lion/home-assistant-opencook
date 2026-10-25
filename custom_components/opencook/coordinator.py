"""Poll openCook and translate failures for Home Assistant."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenCookAuthError, OpenCookClient, OpenCookError
from .const import DOMAIN, POLL_SECONDS
from .models import ShoppingItem

_LOGGER = logging.getLogger(__name__)


class OpenCookCoordinator(DataUpdateCoordinator[tuple[ShoppingItem, ...]]):
    """Keep a household's shopping projection up to date."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: OpenCookClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=POLL_SECONDS),
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> tuple[ShoppingItem, ...]:
        try:
            return await self.client.async_sync()
        except OpenCookAuthError as err:
            raise ConfigEntryAuthFailed("The household invite code is no longer valid") from err
        except OpenCookError as err:
            raise UpdateFailed(str(err)) from err
