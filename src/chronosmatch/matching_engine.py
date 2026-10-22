"""
Matching Engine for ChronosMatch.

Provides the core order matching interface, crossing checks, and trade creation.
"""

from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook
from chronosmatch.trade import Trade


class MatchingEngine:
    """
    In-memory matching engine operating on an OrderBook.

    Person A responsibilities:
    - Order crossing checks against best opposing book quotes.
    - Initial matching loop visiting eligible resting orders.
    - Generating Trade records executed at resting order prices.

    Person B responsibilities (boundaries):
    - Updating/removing resting orders in the book upon fill.
    - Inserting remaining/unfilled incoming quantities into the book.
    """

    def __init__(self, order_book: OrderBook | None = None) -> None:
        """Initialize the matching engine with an optional existing OrderBook."""
        self.order_book = order_book if order_book is not None else OrderBook()

    def is_crossing(self, order: Order) -> bool:
        """
        Determine whether an incoming order crosses the best opposing order in the book.

        - A BUY order crosses when its limit price >= best ask.
        - A SELL order crosses when its limit price <= best bid.

        Args:
            order: The incoming Order to evaluate.

        Returns:
            True if the order crosses the opposing spread; False otherwise.
        """
        if not isinstance(order, Order):
            raise TypeError(f"order must be an instance of Order, got {type(order).__name__}")

        if order.side == OrderSide.BUY:
            best_ask = self.order_book.best_ask()
            return best_ask is not None and order.price >= best_ask

        best_bid = self.order_book.best_bid()
        return best_bid is not None and order.price <= best_bid

    def process_order(self, order: Order) -> list[Trade]:
        """
        Process an incoming order against the order book.

        If the order crosses the book, visits eligible opposing orders in price-time
        priority, generates Trade records at resting prices, and returns them.
        If the order does not cross, returns an empty list.

        Args:
            order: The incoming Order instance.

        Returns:
            List of generated Trade records.
        """
        if not isinstance(order, Order):
            raise TypeError(f"order must be an instance of Order, got {type(order).__name__}")

        trades: list[Trade] = []
        if not self.is_crossing(order):
            # Uncrossed orders: Person B handles resting/remaining quantity placement.
            return trades

        remaining_qty = order.quantity
        is_buy = order.side == OrderSide.BUY

        # Price priority: BUY matches lowest asks first; SELL matches highest bids first.
        prices = (
            sorted(self.order_book.asks.keys())
            if is_buy
            else sorted(self.order_book.bids.keys(), reverse=True)
        )

        for price in prices:
            if (is_buy and price > order.price) or (not is_buy and price < order.price):
                break

            opposing_orders = self.order_book.asks[price] if is_buy else self.order_book.bids[price]
            for resting_order in opposing_orders:
                if remaining_qty == 0:
                    break

                matched_qty = min(remaining_qty, resting_order.quantity)
                trades.append(
                    Trade(
                        buy_order_id=order.order_id if is_buy else resting_order.order_id,
                        sell_order_id=resting_order.order_id if is_buy else order.order_id,
                        price=resting_order.price,
                        quantity=matched_qty,
                        timestamp_ns=order.timestamp_ns,
                    )
                )
                remaining_qty -= matched_qty

            if remaining_qty == 0:
                break

        return trades

    match = process_order  #This is a Python alias. It means you can call either: engine.process_order(order) (or) engine.match(order)
