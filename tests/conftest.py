"""Fixtures for the real upstream API and Home Assistant's test harness."""

import json
import os
import sys
from pathlib import Path

import pytest
from aiohttp import ClientSession, web

pytest_plugins = ("pytest_homeassistant_custom_component",)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "upstream" / "opencook" / "server"))
os.environ["OPENCOOK_DATA_DIR"] = str(ROOT / ".test-data")


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow HA to load this repository's integration."""
    yield


@pytest.fixture
async def upstream_server(socket_enabled, unused_tcp_port):
    """Serve actual upstream sync/household routes over HTTP against an isolated DB."""
    from app.api import households, sync
    from app.db import get_session
    from app.models import Base
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sync._merkle_cache.clear()

    def get_test_session():
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.include_router(households.router)
    app.include_router(sync.router)
    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as api:
        household = api.post("/households", json={"name": "Our kitchen"}).json()

        async def handle(request):
            result = api.request(
                request.method,
                request.path,
                content=await request.read(),
                headers={
                    "Content-Type": "application/json",
                    "X-Household-Code": request.headers.get("X-Household-Code", ""),
                },
            )
            return web.Response(
                status=result.status_code, body=result.content, content_type="application/json"
            )

        application = web.Application()
        application.router.add_route("*", "/{path:.*}", handle)
        runner = web.AppRunner(application)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
        async with ClientSession() as session:
            yield {
                "url": f"http://127.0.0.1:{unused_tcp_port}",
                "code": household["invite_code"],
                "session": session,
                "engine": engine,
                "api": api,
            }
        await runner.cleanup()
    engine.dispose()


@pytest.fixture
def vectors():
    return json.loads((ROOT / "tests/fixtures/sync-vectors.json").read_text())
