# cython: language_level=3, boundscheck=False, wraparound=False
"""
Cython core matching implementation for ChronosMatch.

Provides the optimized matching loop while preserving full semantic parity
with the Python reference implementation.
"""

from chronosmatch.order import Order, OrderSide
from chronosmatch.trade import Trade


def match_order(object order_book, object order) -> list:
    """
    Match an incoming order against the order book using Cython-accelerated logic.

    Preserves exact price priority, FIFO, partial/full fill semantics, and
    order book updates.

    Args:
        order_book: The OrderBook instance.
        order: The incoming Order instance.

    Returns:
        List of generated Trade records.
    """
    if not isinstance(order, Order):
        raise TypeError(f"order must be an instance of Order, got {type(order).__name__}")

    cdef bint is_buy = (order.side == OrderSide.BUY)
    cdef long long order_price = order.price
    cdef long long remaining_qty = order.quantity
    cdef long long order_id = order.order_id
    cdef long long order_ts = order.timestamp_ns
    cdef long long price
    cdef long long matched_qty, resting_remaining
    cdef Py_ssize_t index

    # Crossing check
    if is_buy:
        best_ask = order_book.best_ask()
        if best_ask is None or order_price < best_ask:
            order_book.add_order(order)
            return []
    else:
        best_bid = order_book.best_bid()
        if best_bid is None or order_price > best_bid:
            order_book.add_order(order)
            return []

    # Buyers match against asks (lowest to highest)
    # Sellers match against bids (highest to lowest)
    cdef list prices = (
        sorted(order_book.asks.keys())
        if is_buy
        else sorted(order_book.bids.keys(), reverse=True)
    )

    cdef list trades = []
    cdef dict opposing_book = order_book.asks if is_buy else order_book.bids
    cdef list opposing_orders

    for price in prices:
        if (is_buy and price > order_price) or (not is_buy and price < order_price):
            break

        opposing_orders = opposing_book[price]
        index = 0

        while index < len(opposing_orders) and remaining_qty > 0:
            resting_order = opposing_orders[index]
            matched_qty = remaining_qty if remaining_qty < resting_order.quantity else resting_order.quantity

            trades.append(
                Trade(
                    buy_order_id=order_id if is_buy else resting_order.order_id,
                    sell_order_id=resting_order.order_id if is_buy else order_id,
                    price=resting_order.price,
                    quantity=matched_qty,
                    timestamp_ns=order_ts,
                )
            )

            remaining_qty -= matched_qty
            resting_remaining = resting_order.quantity - matched_qty

            if resting_remaining == 0:
                opposing_orders.pop(index)
            else:
                opposing_orders[index] = Order(
                    order_id=resting_order.order_id,
                    price=resting_order.price,
                    quantity=resting_remaining,
                    side=resting_order.side,
                    timestamp_ns=resting_order.timestamp_ns,
                )
                index += 1

        if not opposing_orders:
            del opposing_book[price]

        if remaining_qty == 0:
            break

    if remaining_qty > 0:
        order_book.add_order(
            Order(
                order_id=order_id,
                price=order_price,
                quantity=remaining_qty,
                side=order.side,
                timestamp_ns=order_ts,
            )
        )

    return trades
