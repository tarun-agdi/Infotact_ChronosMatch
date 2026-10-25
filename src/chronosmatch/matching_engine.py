"""
Matching Engine for ChronosMatch.

Provides the core order matching interface, crossing checks, and trade creation.
"""

from ayman.src.order  import Order, OrderSide
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

#the code from here by is written by ayman and committed in the ayman branch and would be merged in the main at the end 


def process_order(self, order: Order) -> list[Trade]:
    """Match an incoming order and update the order book."""

    if not isinstance(order, Order):
        raise TypeError("order must be an Order instance")

    trades: list[Trade] = []
    remaining_qty = order.quantity
    is_buy = order.side == OrderSide.BUY

    # If the order cannot cross, add it to the book.
    if not self.is_crossing(order):
        self.order_book.add_order(order)
        return trades

    # Buyers match against asks from lowest to highest.
    # Sellers match against bids from highest to lowest.
    prices = (
        sorted(self.order_book.asks)
        if is_buy
        else sorted(self.order_book.bids, reverse=True)
    )

    for price in prices:
        # Stop when the next price is outside the incoming order's limit.
        if (is_buy and price > order.price) or (
            not is_buy and price < order.price
        ):
            break

        opposing_book = (
            self.order_book.asks if is_buy else self.order_book.bids
        )
        opposing_orders = opposing_book[price]

        # Use an index so removing a filled order doesn't skip the next one.
        index = 0

        while index < len(opposing_orders) and remaining_qty > 0:
            resting_order = opposing_orders[index]

            matched_qty = min(remaining_qty, resting_order.quantity)

            trades.append(
                Trade(
                    buy_order_id=(
                        order.order_id if is_buy
                        else resting_order.order_id
                    ),
                    sell_order_id=(
                        resting_order.order_id if is_buy
                        else order.order_id
                    ),
                    price=resting_order.price,
                    quantity=matched_qty,
                    timestamp_ns=order.timestamp_ns,
                )
            )

            remaining_qty -= matched_qty
            resting_remaining = resting_order.quantity - matched_qty

            if resting_remaining == 0:
                # Fully filled: remove the resting order.
                opposing_orders.pop(index)
            else:
                # Partially filled: replace it in the same position.
                # This preserves FIFO priority at this price.
                opposing_orders[index] = Order(
                    order_id=resting_order.order_id,
                    price=resting_order.price,
                    quantity=resting_remaining,
                    side=resting_order.side,
                    timestamp_ns=resting_order.timestamp_ns,
                )
                index += 1

        # Remove empty price levels.
        if not opposing_orders:
            del opposing_book[price]

        if remaining_qty == 0:
            break

    # Add any unfilled quantity of the incoming order to the book.
    if remaining_qty > 0:
        remaining_order = Order(
            order_id=order.order_id,
            price=order.price,
            quantity=remaining_qty,
            side=order.side,
            timestamp_ns=order.timestamp_ns,
        )
        self.order_book.add_order(remaining_order)

    return trades
