"""End-to-end contract tests against unmodified openCook sync/household routes."""

import asyncio
import json

import pytest
from aiohttp import web

from custom_components.opencook.api import (
    OpenCookAuthError,
    OpenCookClient,
    OpenCookError,
    OpenCookItemNotFound,
    normalize_url,
)
from custom_components.opencook.protocol import Hlc


def make_client(server, node="ha-test"):
    return OpenCookClient(server["session"], server["url"], server["code"], node)


async def push_phone(server, uid, fields, millis=2000000000000):
    """Encode fields exactly as ShoppingMessageEncoder.kt does, including future clocks."""
    messages = [
        {
            "timestamp": Hlc(millis, index, "phone").pack(),
            "dataset": "shopping",
            "row_id": uid,
            "column": column,
            "value": json.dumps(value),
        }
        for index, (column, value) in enumerate(fields.items())
    ]
    async with server["session"].post(
        f"{server['url']}/sync",
        headers={"X-Household-Code": server["code"]},
        json={"merkle": {}, "messages": messages},
    ) as response:
        assert response.status == 200


async def test_round_trip_preserves_quantity_and_recipe_provenance(upstream_server):
    server = upstream_server
    await push_phone(
        server,
        "rice",
        {
            "text": "Rice",
            "quantity": 500,
            "unit": "g",
            "checked": False,
            "sourceRecipeId": "recipe-1",
            "manual": False,
            "_deleted": False,
        },
    )
    client = make_client(server)
    assert (await client.async_sync())[0].description == "500 g"
    await client.async_update("rice", checked=True)
    await client.async_update("rice", text="Basmati rice")
    fields = client._fields
    assert fields[("rice", "sourceRecipeId")][0] == "recipe-1"
    assert fields[("rice", "quantity")][0] == 500
    assert fields[("rice", "manual")][0] is False
    second_phone = make_client(server, "phone-2")
    items = await second_phone.async_sync()
    assert items[0].text == "Basmati rice"
    assert items[0].checked
    await client.async_delete(["rice"])
    assert await second_phone.async_sync() == ()


async def test_create_multiple_clients_and_idempotent_poll(upstream_server):
    client = make_client(upstream_server)
    items = await client.async_create("Milk")
    uid = items[0].uid
    assert client._fields[(uid, "manual")][0] is True
    assert not items[0].checked
    count = len(client._timestamps)
    assert count == 10
    assert await client.async_sync() == items
    assert len(client._timestamps) == count
    other = make_client(upstream_server, "other")
    assert await other.async_sync() == items
    await other.async_update(uid, checked=True)
    assert (await client.async_sync())[0].checked
    await other.async_delete([uid, uid])
    assert await client.async_sync() == ()


async def test_deleted_on_phone_is_not_resurrected_by_ha(upstream_server):
    client = make_client(upstream_server)
    items = await client.async_create("Bread")
    uid = items[0].uid
    await push_phone(upstream_server, uid, {"_deleted": True})
    with pytest.raises(OpenCookItemNotFound):
        await client.async_update(uid, checked=True)
    assert client.items == ()


async def test_parallel_actions_are_serialized(upstream_server):
    client = make_client(upstream_server)
    await asyncio.gather(*(client.async_create(f"Item {n}") for n in range(5)))
    assert len(await client.async_sync()) == 5
    assert len(client._timestamps) == 50


async def test_household_isolation_and_invalid_code(upstream_server):
    server = upstream_server
    await make_client(server).async_create("Private groceries")
    household = server["api"].post("/households", json={"name": "Other"}).json()
    other = OpenCookClient(server["session"], server["url"], household["invite_code"])
    assert await other.async_sync() == ()
    invalid = OpenCookClient(server["session"], server["url"], "wrong-code")
    with pytest.raises(OpenCookAuthError):
        await invalid.async_sync()


async def test_server_reset_drops_stale_projection(upstream_server):
    from app.api.sync import _merkle_cache
    from app.models import SyncMessage
    from sqlalchemy import delete

    client = make_client(upstream_server)
    await client.async_create("Old list")
    with upstream_server["engine"].begin() as connection:
        connection.execute(delete(SyncMessage))
    _merkle_cache.clear()
    assert await client.async_sync() == ()
    await client.async_create("New list")
    assert [item.text for item in await client.async_sync()] == ["New list"]


async def test_failed_action_is_reported_and_later_poll_recovers(upstream_server, monkeypatch):
    client = make_client(upstream_server)
    uid = (await client.async_create("Eggs"))[0].uid
    exchange = client._exchange

    async def fail(messages):
        if messages:
            raise OpenCookError("Offline")
        return await exchange(messages)

    monkeypatch.setattr(client, "_exchange", fail)
    with pytest.raises(OpenCookError, match="Offline"):
        await client.async_update(uid, checked=True)
    monkeypatch.setattr(client, "_exchange", exchange)
    assert not (await client.async_sync())[0].checked


@pytest.mark.parametrize(
    "value",
    [
        "homeassistant:8000",
        "ftp://example.com",
        "http://a:b@host",
        "http://host?q=secret",
        "http://host/#secret",
    ],
)
def test_invalid_urls(value):
    with pytest.raises(ValueError):
        normalize_url(value)


def test_url_normalization():
    assert normalize_url(" HTTP://HOMEASSISTANT.LOCAL:8000/ ") == "http://homeassistant.local:8000"
    assert normalize_url("https://host/opencook/") == "https://host/opencook"


async def test_unexpected_server_response_is_not_acknowledged(socket_enabled, aiohttp_server):
    from aiohttp import ClientSession

    responses = [
        {"merkle": {}, "messages": [{"broken": True}]},
        {"merkle": {"hash": 0}, "messages": [], "household_name": "Kitchen"},
    ]

    async def handle(request):
        return web.json_response(responses.pop(0))

    app = web.Application()
    app.router.add_post("/sync", handle)
    server = await aiohttp_server(app)
    async with ClientSession() as session:
        client = OpenCookClient(session, str(server.make_url("/")), "code")
        with pytest.raises(OpenCookError):
            await client.async_sync()
        assert await client.async_sync() == ()
