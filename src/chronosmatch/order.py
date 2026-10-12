"""
Order data model for ChronosMatch.

This module defines the fundamental Order and OrderSide abstractions used
throughout the trading engine.

Design considerations for low-latency systems:
- Integer prices: Prices are represented as integers using fixed-point units
  (e.g., paise where 1 INR = 100 paise, or tick units) rather than floating-point
  numbers to eliminate IEEE 754 precision issues, rounding errors, and non-deterministic
  pricing bugs.
- Immutability (frozen=True): Prevents in-flight mutation of order records across
  pipeline stages, ensuring thread safety and deterministic matching.
- Memory efficiency (slots=True): Eliminates per-instance __dict__ overhead,
  reducing memory footprint and improving CPU cache locality.
- Explicit timestamps: Timestamps are not generated automatically inside the model
  to decouple creation from the clock source, allowing deterministic event-replay,
  backtesting, and precise capture of exchange ingress timestamps.
"""

from dataclasses import dataclass
from enum import IntEnum


class OrderSide(IntEnum):
    """
    Side of an order in the book.

    Uses IntEnum for memory efficiency, fast register-level comparisons,
    and direct compatibility with binary serialization and C/Cython structures.
    """
    BUY = 1
    SELL = 2


def _validate_positive_int(value: object, field_name: str) -> None:
    """Validate that value is an integer strictly greater than zero."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer (> 0), got {value}")


def _validate_non_negative_int(value: object, field_name: str) -> None:
    """Validate that value is an integer greater than or equal to zero."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer (>= 0), got {value}")


@dataclass(frozen=True, slots=True)
class Order:
    """
    Immutable representation of an order.

    Attributes:
        order_id: Unique positive integer identifier for the order.
        price: Price in fixed-point integer units (e.g., paise).
        quantity: Order quantity as a positive integer.
        side: OrderSide.BUY or OrderSide.SELL.
        timestamp_ns: Ingress/sequencing timestamp in nanoseconds (non-negative integer).
    """
    order_id: int
    price: int
    quantity: int
    side: OrderSide
    timestamp_ns: int

    def __post_init__(self) -> None:
        """Validate order attributes upon creation."""
        _validate_positive_int(self.order_id, "order_id")
        _validate_positive_int(self.price, "price")
        _validate_positive_int(self.quantity, "quantity")

        if not isinstance(self.side, OrderSide):
            raise TypeError(
                f"side must be an instance of OrderSide, got {type(self.side).__name__}"
            )

        _validate_non_negative_int(self.timestamp_ns, "timestamp_ns")
