"""Load the real integration in Home Assistant, including config flows and actions."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.todo import TodoItem, TodoItemStatus
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.opencook.api import OpenCookAuthError, OpenCookClient, OpenCookError
from custom_components.opencook.const import CONF_HOUSEHOLD_CODE, CONF_URL, DOMAIN
from custom_components.opencook.models import ShoppingItem
from custom_components.opencook.todo import OpenCookShoppingList


@pytest.fixture
def mock_client():
    with patch("custom_components.opencook.config_flow.OpenCookClient") as factory:
        factory.return_value.household_name = "Our kitchen"
        factory.return_value.async_sync = AsyncMock(return_value=())
        yield factory.return_value


async def test_config_flow_and_duplicate(hass, mock_client):
    data = {CONF_URL: "http://homeassistant.local:8000/", CONF_HOUSEHOLD_CODE: "invite-code"}
    with patch("custom_components.opencook.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=data
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Our kitchen"
    assert result["data"][CONF_URL] == "http://homeassistant.local:8000"
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=data
    )
    assert duplicate["type"] == FlowResultType.ABORT
    assert duplicate["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [(OpenCookAuthError(), "invalid_auth"), (OpenCookError(), "cannot_connect")],
)
async def test_flow_errors(hass, mock_client, error, expected):
    mock_client.async_sync.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: "http://host:8000", CONF_HOUSEHOLD_CODE: "bad"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_flow_invalid_url(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_URL: "host:8000", CONF_HOUSEHOLD_CODE: "code"},
    )
    assert result["errors"] == {"base": "invalid_url"}


async def test_setup_actions_and_unload(hass, upstream_server):
    """Use real HTTP, config-entry setup, entity mapping, HA services and unloading."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Our kitchen",
        unique_id="household-1",
        data={CONF_URL: upstream_server["url"], CONF_HOUSEHOLD_CODE: upstream_server["code"]},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    todo_states = hass.states.async_all("todo")
    assert len(todo_states) == 1
    entity_id = todo_states[0].entity_id
    assert todo_states[0].state == "0"
    await hass.services.async_call(
        "todo", "add_item", {"entity_id": entity_id, "item": "Coffee"}, blocking=True
    )
    assert hass.states.get(entity_id).state == "1"
    items = entry.runtime_data.data
    uid = items[0].uid
    phone = OpenCookClient(
        upstream_server["session"], upstream_server["url"], upstream_server["code"], "phone"
    )
    # The phone renames while HA still holds "Coffee". A checkbox click must
    # not copy HA's stale name over the newer phone field.
    await phone.async_update(uid, text="Espresso")
    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": entity_id, "item": uid, "status": "completed"},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == "0"
    assert entry.runtime_data.data[0].checked
    assert entry.runtime_data.data[0].text == "Espresso"
    # Likewise a rename must preserve a phone's newer checkbox change.
    await phone.async_update(uid, checked=False)
    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": entity_id, "item": uid, "rename": "Ground coffee"},
        blocking=True,
    )
    assert entry.runtime_data.data[0].text == "Ground coffee"
    assert not entry.runtime_data.data[0].checked
    await hass.services.async_call(
        "todo", "remove_item", {"entity_id": entity_id, "item": uid}, blocking=True
    )
    assert entry.runtime_data.data == ()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"


async def test_setup_retries_unreachable_server(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: "http://host:8000", CONF_HOUSEHOLD_CODE: "code"}
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.opencook.api.OpenCookClient.async_sync",
        side_effect=OpenCookError("Offline"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state.value == "setup_retry"


async def test_reauthentication(hass, mock_client):
    from hashlib import sha256

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=sha256(b"old-code").hexdigest(),
        data={CONF_URL: "http://host:8000", CONF_HOUSEHOLD_CODE: "old-code"},
    )
    entry.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data
    )
    assert flow["step_id"] == "reauth_confirm"
    with patch("homeassistant.config_entries.ConfigEntries.async_reload", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {CONF_URL: "http://new-host:8000", CONF_HOUSEHOLD_CODE: "new-code"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert entry.data[CONF_HOUSEHOLD_CODE] == "new-code"


async def test_entity_quantities_partial_updates_and_action_failure(hass):
    from custom_components.opencook.coordinator import OpenCookCoordinator

    entry = MockConfigEntry(domain=DOMAIN, unique_id="test")
    client = AsyncMock()
    client.household_name = "Kitchen"
    coordinator = OpenCookCoordinator(hass, entry, client)
    coordinator.async_set_updated_data((ShoppingItem("rice", "Rice", False, 0, 500, "g"),))
    entity = OpenCookShoppingList(coordinator, entry)
    assert entity.todo_items[0].description == "500 g"
    client.async_update.return_value = ()
    await entity.async_update_todo_item(TodoItem(uid="rice", status=TodoItemStatus.COMPLETED))
    client.async_update.assert_awaited_once_with("rice", text=None, checked=True)
    client.async_create.side_effect = OpenCookError("Offline")
    with pytest.raises(HomeAssistantError, match="Offline"):
        await entity.async_create_todo_item(TodoItem(summary="Milk"))
    client.async_sync.side_effect = OpenCookAuthError()
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
