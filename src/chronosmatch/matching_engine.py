
"""
Matching engine for ChronosMatch.
"""

from .order import Order, OrderSide
from .order_book import OrderBook
from .trade import Trade

try:
    from chronosmatch.matching_engine_cy import match_order as _cython_match_order

    CYTHON_CORE_AVAILABLE = True
except ImportError:
    try:
        from .matching_engine_cy import match_order as _cython_match_order

        CYTHON_CORE_AVAILABLE = True
    except ImportError:
        _cython_match_order = None
        CYTHON_CORE_AVAILABLE = False


class MatchingEngine:
    """Match incoming orders using price-time priority."""

    def __init__(
        self,
        order_book: OrderBook | None = None,
        use_cython: bool = True,
    ) -> None:
        self.order_book = order_book if order_book is not None else OrderBook()
        self.use_cython = use_cython and CYTHON_CORE_AVAILABLE

    def is_crossing(self, order: Order) -> bool:
        """Return whether an order can match the best opposing price."""
        if not isinstance(order, Order):
            raise TypeError(
                f"order must be an Order instance, got {type(order).__name__}"
            )

        if order.side == OrderSide.BUY:
            best_price = self.order_book.best_ask()
            return best_price is not None and order.price >= best_price

        best_price = self.order_book.best_bid()
        return best_price is not None and order.price <= best_price

    def process_order(self, order: Order) -> list[Trade]:
        """Match an order, update the book, and return executed trades."""
        if not isinstance(order, Order):
            raise TypeError(
                f"order must be an Order instance, got {type(order).__name__}"
            )

        if self.use_cython and _cython_match_order is not None:
            return _cython_match_order(self.order_book, order)

        is_buy = order.side == OrderSide.BUY
        remaining_qty = order.quantity
        trades: list[Trade] = []

        opposing_book = (
            self.order_book.asks if is_buy else self.order_book.bids
        )

        if not self.is_crossing(order):
            self.order_book.add_order(order)
            return trades

        prices = sorted(
            opposing_book,
            reverse=not is_buy,
        )

        for price in prices:
            if remaining_qty == 0:
                break

            if (is_buy and price > order.price) or (
                not is_buy and price < order.price
            ):
                break

            resting_orders = opposing_book[price]
            index = 0

            while index < len(resting_orders) and remaining_qty > 0:
                resting_order = resting_orders[index]
                matched_qty = min(remaining_qty, resting_order.quantity)

                trades.append(
                    Trade(
                        buy_order_id=(
                            order.order_id if is_buy else resting_order.order_id
                        ),
                        sell_order_id=(
                            resting_order.order_id if is_buy else order.order_id
                        ),
                        price=resting_order.price,
                        quantity=matched_qty,
                        timestamp_ns=order.timestamp_ns,
                    )
                )

                remaining_qty -= matched_qty
                resting_remaining = resting_order.quantity - matched_qty

                if resting_remaining == 0:
                    resting_orders.pop(index)
                else:
                    resting_orders[index] = Order(
                        order_id=resting_order.order_id,
                        price=resting_order.price,
                        quantity=resting_remaining,
                        side=resting_order.side,
                        timestamp_ns=resting_order.timestamp_ns,
                    )
                    index += 1

            if not resting_orders:
                del opposing_book[price]

        if remaining_qty > 0:
            self.order_book.add_order(
                Order(
                    order_id=order.order_id,
                    price=order.price,
                    quantity=remaining_qty,
                    side=order.side,
                    timestamp_ns=order.timestamp_ns,
                )
            )

        return trades

    match = process_order
