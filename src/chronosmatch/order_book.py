"""
Limit Order Book for ChronosMatch.

Stores buy and sell orders organized by price.
Matching logic will be implemented separately.
"""

from chronosmatch.order import Order, OrderSide


class OrderBook:
    """Stores buy and sell orders for the matching engine."""

    def __init__(self) -> None:
        self.bids: dict[int, list[Order]] = {}
        self.asks: dict[int, list[Order]] = {}