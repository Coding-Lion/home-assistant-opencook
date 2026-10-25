"""Shopping-list projection, independent of Home Assistant."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShoppingItem:
    """The subset of shopping fields exposed as a native to-do item."""

    uid: str
    text: str
    checked: bool
    position: int
    quantity: float | None = None
    unit: str | None = None

    @property
    def description(self) -> str | None:
        """Show structured quantities without changing the editable item name."""
        parts = []
        if self.quantity is not None:
            parts.append(f"{self.quantity:g}")
        if self.unit:
            parts.append(self.unit)
        return " ".join(parts) or None


def project_items(rows: dict[str, dict[str, Any]]) -> tuple[ShoppingItem, ...]:
    """Keep tombstones out of HA, retaining their clocks in the sync store."""
    return tuple(
        sorted(
            (
                ShoppingItem(
                    uid=uid,
                    text=fields["text"],
                    checked=fields.get("checked") is True,
                    position=int(fields.get("position") or 0),
                    quantity=fields.get("quantity"),
                    unit=fields.get("unit"),
                )
                for uid, fields in rows.items()
                if fields.get("_deleted") is not True and fields.get("text")
            ),
            key=lambda item: (item.position, item.uid),
        )
    )
