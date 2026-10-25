"""Async client for openCook's household-scoped CRDT sync API."""

from __future__ import annotations

import asyncio
import json
import math
import time
from typing import Any
from uuid import uuid4

from aiohttp import ClientError, ClientSession, ClientTimeout
from yarl import URL

from .models import ShoppingItem, project_items
from .protocol import (
    ClockDriftError,
    Hlc,
    HlcClock,
    Merkle,
    merkle_from_dict,
    merkle_insert,
    merkle_to_dict,
)


class OpenCookError(Exception):
    """An unreachable server or an incompatible sync response."""


class OpenCookAuthError(OpenCookError):
    """The household credential was rejected."""


class OpenCookItemNotFound(OpenCookError):
    """The requested item was deleted on another device."""


def normalize_url(value: str) -> str:
    """Require an explicit HTTP URL; do not accept secrets embedded in URLs."""
    url = URL(value.strip())
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.user is not None
        or url.query_string
        or url.fragment
    ):
        raise ValueError("Enter an http:// or https:// server URL without credentials")
    # Accessing port also validates invalid and out-of-range port strings.
    _ = url.port
    return str(url).rstrip("/")


class OpenCookClient:
    """Retain only shopping fields, plus timestamps for the household Merkle trie.

    Initial load reconstructs the list from the full log. Subsequent polls transfer
    only the divergent tail. Nothing is written to the server during validation.
    The lock serializes polls and actions; only explicitly edited fields are sent.
    """

    def __init__(
        self, session: ClientSession, url: str, code: str, node: str | None = None
    ) -> None:
        self._session = session
        self.url = normalize_url(url)
        self._code = code.strip()
        self._clock = HlcClock(node or f"ha-{uuid4()}")
        self._lock = asyncio.Lock()
        self.household_name = ""
        self._reset_required = True
        self._clear_projection()

    def _clear_projection(self) -> None:
        self._merkle = Merkle()
        self._timestamps: set[str] = set()
        self._fields: dict[tuple[str, str], tuple[Any, str]] = {}

    @property
    def items(self) -> tuple[ShoppingItem, ...]:
        rows: dict[str, dict[str, Any]] = {}
        for (uid, column), (value, _) in self._fields.items():
            rows.setdefault(uid, {})[column] = value
        return project_items(rows)

    async def _exchange(self, messages: list[dict]) -> dict:
        try:
            async with self._session.post(
                f"{self.url}/sync",
                headers={"X-Household-Code": self._code},
                json={"merkle": merkle_to_dict(self._merkle), "messages": messages},
                timeout=ClientTimeout(total=30),
                allow_redirects=False,
            ) as response:
                if response.status in {401, 403, 404}:
                    raise OpenCookAuthError("The server rejected the household invite code")
                if response.status != 200:
                    raise OpenCookError(f"openCook returned HTTP {response.status}")
                body = await response.json()
                if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
                    raise ValueError("Missing sync messages")
                if not isinstance(body.get("merkle"), dict):
                    raise ValueError("Missing sync Merkle trie")
                return body
        except (ClientError, TimeoutError) as err:
            # aiohttp errors can include URLs/headers; do not expose credentials.
            raise OpenCookError("Cannot communicate with the openCook server") from err
        except (ValueError, TypeError) as err:
            raise OpenCookError("Invalid openCook sync response") from err

    def _apply(self, messages: list[dict]) -> None:
        latest: str | None = None
        for message in messages:
            timestamp = message["timestamp"]
            for key in ("timestamp", "dataset", "row_id", "column", "value"):
                if not isinstance(message[key], str):
                    raise ValueError("Invalid message field")
            if timestamp in self._timestamps:
                continue
            # Parse before acknowledging; malformed data must never advance the trie.
            stamp = Hlc.parse(timestamp)
            if (
                stamp.pack() != timestamp
                or not 0 <= stamp.millis <= 999999999999999
                or not 0 <= stamp.counter <= 65535
                or not stamp.node
            ):
                raise ValueError("Invalid sync timestamp")
            if message["dataset"] == "shopping":
                value = json.loads(message["value"])
                column = message["column"]
                if column in {"text", "unit"} and value is not None and not isinstance(value, str):
                    raise ValueError("Invalid shopping text")
                if column in {"quantity", "position"} and value is not None:
                    if type(value) not in {int, float} or not math.isfinite(value):
                        raise ValueError("Invalid shopping number")
                if column in {"checked", "_deleted"} and not isinstance(value, bool):
                    raise ValueError("Invalid shopping flag")
                key = (message["row_id"], message["column"])
                if key not in self._fields or timestamp > self._fields[key][1]:
                    self._fields[key] = (value, timestamp)
            merkle_insert(self._merkle, timestamp)
            self._timestamps.add(timestamp)
            latest = max(latest or timestamp, timestamp)
        # Receive only the maximum remote clock once per batch, avoiding artificial
        # counter overflow when an initial log has many messages in one millisecond.
        if latest is not None:
            self._clock.recv(Hlc.parse(latest), int(time.time() * 1000))

    async def _sync_locked(self, messages: list[dict] | None = None) -> tuple[ShoppingItem, ...]:
        if self._reset_required:
            self._clear_projection()
        try:
            body = await self._exchange(messages or [])
            self._apply(body["messages"])
            self._apply(messages or [])
            server = merkle_from_dict(body["merkle"])
            if self._merkle.hash != server.hash:
                # A server restore/reset removed messages we previously knew. Rebuild
                # from the server, without uploading old local data or resurrecting it.
                self._clear_projection()
                body = await self._exchange([])
                self._apply(body["messages"])
                if self._merkle.hash != merkle_from_dict(body["merkle"]).hash:
                    raise ValueError("Sync did not converge")
            self.household_name = str(body.get("household_name") or "openCook")
            items = self.items
        except (
            KeyError,
            ValueError,
            TypeError,
            OverflowError,
            RecursionError,
            ClockDriftError,
        ) as err:
            self._reset_required = True
            raise OpenCookError("Incompatible openCook shopping-list data") from err
        except OpenCookError:
            self._reset_required = True
            raise
        self._reset_required = False
        return items

    async def async_sync(self) -> tuple[ShoppingItem, ...]:
        async with self._lock:
            return await self._sync_locked()

    def _messages(self, uid: str, fields: dict[str, Any]) -> list[dict]:
        return [
            {
                "timestamp": self._clock.send(int(time.time() * 1000)).pack(),
                "dataset": "shopping",
                "row_id": uid,
                "column": column,
                "value": json.dumps(value, ensure_ascii=False, allow_nan=False),
            }
            for column, value in fields.items()
        ]

    async def async_create(self, text: str, checked: bool = False) -> tuple[ShoppingItem, ...]:
        if not text.strip():
            raise OpenCookError("The item name must not be empty")
        async with self._lock:
            await self._sync_locked()
            fields = {
                "text": text.strip(),
                "quantity": None,
                "unit": None,
                "checked": checked,
                "position": int(time.time() * 1000) % 2147483647,
                "sourceRecipeId": None,
                "sourceDate": None,
                "manual": True,
                "sourceRecipeIds": None,
                "_deleted": False,
            }
            return await self._sync_locked(self._messages(str(uuid4()), fields))

    async def async_update(
        self, uid: str, *, text: str | None = None, checked: bool | None = None
    ) -> tuple[ShoppingItem, ...]:
        if text is not None and not text.strip():
            raise OpenCookError("The item name must not be empty")
        async with self._lock:
            await self._sync_locked()
            current = next((item for item in self.items if item.uid == uid), None)
            if current is None:
                raise OpenCookItemNotFound("This item no longer exists; refresh the list")
            fields = {}
            if text is not None and text.strip() != current.text:
                fields["text"] = text.strip()
            if checked is not None and checked != current.checked:
                fields["checked"] = checked
            if not fields:
                return self.items
            return await self._sync_locked(self._messages(uid, fields))

    async def async_delete(self, uids: list[str]) -> tuple[ShoppingItem, ...]:
        async with self._lock:
            await self._sync_locked()
            live = {item.uid for item in self.items}
            messages = [
                message
                for uid in dict.fromkeys(uids)
                if uid in live
                for message in self._messages(uid, {"_deleted": True})
            ]
            if not messages:
                return self.items
            return await self._sync_locked(messages)
