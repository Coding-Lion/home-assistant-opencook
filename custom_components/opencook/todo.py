"""The household shopping list as a native Home Assistant to-do entity."""

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import OpenCookError
from .coordinator import OpenCookCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([OpenCookShoppingList(entry.runtime_data, entry)])


class OpenCookShoppingList(CoordinatorEntity[OpenCookCoordinator], TodoListEntity):
    """Preserve UUIDs, structured quantities, and recipe provenance across edits."""

    _attr_has_entity_name = True
    _attr_name = "Shopping list"
    _attr_icon = "mdi:cart"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: OpenCookCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_shopping"
        self._attr_name = f"{coordinator.client.household_name} shopping list"

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=item.uid,
                summary=item.text,
                description=item.description,
                status=TodoItemStatus.COMPLETED if item.checked else TodoItemStatus.NEEDS_ACTION,
            )
            for item in self.coordinator.data or ()
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        try:
            items = await self.coordinator.client.async_create(
                item.summary or "", item.status == TodoItemStatus.COMPLETED
            )
        except OpenCookError as err:
            raise HomeAssistantError(str(err)) from err
        self.coordinator.async_set_updated_data(items)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.uid is None:
            raise HomeAssistantError("The shopping item has no ID")
        # HA passes a complete cached TodoItem, even for a checkbox action. Find
        # changed fields before refreshing, so concurrent phone edits survive.
        cached = next((entry for entry in self.todo_items if entry.uid == item.uid), None)
        text = item.summary if cached is None or item.summary != cached.summary else None
        status = item.status if cached is None or item.status != cached.status else None
        try:
            items = await self.coordinator.client.async_update(
                item.uid,
                text=text,
                checked=None if status is None else status == TodoItemStatus.COMPLETED,
            )
        except OpenCookError as err:
            raise HomeAssistantError(str(err)) from err
        self.coordinator.async_set_updated_data(items)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        try:
            items = await self.coordinator.client.async_delete(uids)
        except OpenCookError as err:
            raise HomeAssistantError(str(err)) from err
        self.coordinator.async_set_updated_data(items)
