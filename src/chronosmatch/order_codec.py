"""
Binary serialization and deserialization for ChronosMatch orders.

This module converts high-level Order objects into compact, fixed-size binary records
and reconstructs Order objects from raw bytes using Python's standard-library `struct`
module.

Binary Record Layout:
---------------------
Format string: ">QQQBQ" (Big-Endian, standard size, packed without padding)

Field          | Struct Code | C Type             | Size (Bytes) | Range / Constraints
----------------------------------------------------------------------------------------
order_id       | Q           | uint64 (unsigned)  | 8            | 1 to 2^64 - 1
price          | Q           | uint64 (unsigned)  | 8            | 1 to 2^64 - 1 (in paise)
quantity       | Q           | uint64 (unsigned)  | 8            | 1 to 2^64 - 1
side           | B           | uint8  (unsigned)  | 1            | 1 (BUY) or 2 (SELL)
timestamp_ns   | Q           | uint64 (unsigned)  | 8            | 0 to 2^64 - 1 (nanoseconds)
----------------------------------------------------------------------------------------
Total Size: 33 bytes.
"""

from __future__ import annotations

import struct
from typing import Final

from .order import Order, OrderSide

# Format specification:
# '>' specifies standard big-endian byte order (most significant byte first).
# 'Q' specifies an unsigned 8-byte (64-bit) integer.
# 'B' specifies an unsigned 1-byte (8-bit) integer.
ORDER_RECORD_FORMAT: Final[str] = ">QQQBQ"

# Pre-compiled Struct instance for fast, reusable packing and unpacking.
ORDER_STRUCT: Final[struct.Struct] = struct.Struct(ORDER_RECORD_FORMAT)

# Exact size in bytes for an encoded Order record (33 bytes).
ORDER_RECORD_SIZE: Final[int] = ORDER_STRUCT.size

# Numeric bounds for 64-bit and 8-bit unsigned integers.
UINT64_MAX: Final[int] = (1 << 64) - 1
UINT64_MIN: Final[int] = 0
UINT8_MAX: Final[int] = 255
UINT8_MIN: Final[int] = 0


def encode_order(order: Order) -> bytes: #-> bytes: means the function returns a bytes object
    """
    Serialize an Order object into a fixed-size 33-byte binary record.

    Args:
        order: The Order instance to serialize.

    Returns:
        A bytes object of length 33 containing the packed binary representation.

    Raises:
        TypeError: If order is not an instance of Order.
        ValueError: If any numeric field is out of range for its binary representation.
    """
    if not isinstance(order, Order): #isinstance(order, Order) checks whether the supplied value is an instance of the Order class.
        raise TypeError(f"order must be an instance of Order, got {type(order).__name__}")

    # Guard against Python arbitrary-precision integers exceeding 64-bit unsigned bounds
    # or falling below valid Order thresholds.
    for name, value, minimum in [
    ("order_id", order.order_id, 1),
    ("price", order.price, 1),
    ("quantity", order.quantity, 1),
    ("timestamp_ns", order.timestamp_ns, 0),
]:
        if value < minimum or value > UINT64_MAX:
            raise ValueError(f"{name} out of range: {value}")

    if not isinstance(order.side, OrderSide):
        raise TypeError(
            f"side must be an instance of OrderSide, got {type(order.side).__name__}"
        )

    return ORDER_STRUCT.pack(
        order.order_id,
        order.price,
        order.quantity,
        int(order.side),
        order.timestamp_ns,
    )


def decode_order(data: bytes | bytearray | memoryview) -> Order:
    """
    Deserialize a 33-byte binary record into an Order object.

    Args:
        data: A bytes-like buffer of length exactly 33.

    Returns:
        The reconstructed, immutable Order instance.

    Raises:
        TypeError: If data is not a bytes-like object (bytes, bytearray, memoryview).
        ValueError: If data length is not 33 bytes, if the encoded side is invalid,
                    or if any unpacked field violates Order domain constraints.
    """
    if isinstance(data, bool) or not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"data must be a bytes-like object (bytes, bytearray, memoryview), got {type(data).__name__}"
        )

    if len(data) != ORDER_RECORD_SIZE:
        raise ValueError(
            f"Invalid record length: expected exactly {ORDER_RECORD_SIZE} bytes, got {len(data)}"
        )

    try:
        order_id, price, quantity, side_val, timestamp_ns = ORDER_STRUCT.unpack(data)
    except struct.error as err:
        raise ValueError(f"Failed to unpack binary order: {err}") from err

    try:
        side = OrderSide(side_val)
    except ValueError as err:
        raise ValueError(f"Invalid encoded order side value: {side_val}") from err

    # Construct the Order object.
    # Order.__post_init__ validates positive integers for order_id, price, quantity,
    # and non-negative integer for timestamp_ns.#this is already done ok 
    return Order(
        order_id=order_id,
        price=price,
        quantity=quantity,
        side=side,
        timestamp_ns=timestamp_ns,
    )

print("code running no errors found") #this is done to ensure a successful debugging 