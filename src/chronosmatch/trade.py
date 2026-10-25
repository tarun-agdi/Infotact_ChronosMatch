"""
Trade execution event model for ChronosMatch.

Represents an executed trade when an incoming order matches a resting order.
"""

from dataclasses import dataclass

from .order import _validate_non_negative_int, _validate_positive_int


@dataclass(frozen=True, slots=True) #dataclass automatically generates methods such as __init__(), frozen=True prevents changing fields after creation
class Trade:
    """
    Immutable representation of an executed trade.

    Attributes:
        buy_order_id: Order ID of the buyer.
        sell_order_id: Order ID of the seller.
        price: Execution price in fixed-point integer units.
        quantity: Executed quantity as a positive integer.
        timestamp_ns: Ingress/execution timestamp in nanoseconds.
    """
    buy_order_id: int
    sell_order_id: int
    price: int
    quantity: int
    timestamp_ns: int

    def __post_init__(self) -> None: #Instead of writing validation logic from scratch, this reuses a helper from order.py
        """Validate trade fields upon creation."""
        _validate_positive_int(self.buy_order_id, "buy_order_id")
        _validate_positive_int(self.sell_order_id, "sell_order_id")
        _validate_positive_int(self.price, "price")
        _validate_positive_int(self.quantity, "quantity")
        _validate_non_negative_int(self.timestamp_ns, "timestamp_ns")
        #Order IDs, price and quantity must be positive. The timestamp can be zero.
