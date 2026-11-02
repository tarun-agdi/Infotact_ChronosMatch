
# cython: language_level=3

"""
Cython matching engine for ChronosMatch.

Uses price-time priority:
1. Best opposing price first.
2. FIFO order within each price level.
3. Supports partial and complete fills.
"""

from .order import Order, OrderSide
from .trade import Trade


def match_order(object order_book, object order):
    """
    Process one incoming order and return executed trades.

    The order_book is the existing Python OrderBook instance.
    """

    if not isinstance(order, Order):
        raise TypeError("order must be an Order instance")

    cdef bint is_buy = order.side == OrderSide.BUY
    cdef long long remaining_qty = order.quantity
    cdef long long order_price = order.price
    cdef long long matched_qty
    cdef long long resting_remaining

    cdef object opposing_book
    cdef object prices
    cdef object price
    cdef object resting_orders
    cdef object resting_order
    cdef object trades = []

    cdef Py_ssize_t index

    if order.side not in (OrderSide.BUY, OrderSide.SELL):
        raise ValueError("Invalid order side")

    # Select the opposing side of the book.
    if is_buy:
        opposing_book = order_book.asks
    else:
        opposing_book = order_book.bids

    # No opposing orders available.
    if not opposing_book:
        order_book.add_order(order)
        return trades

    # Sort prices according to price-time priority.
    prices = sorted(opposing_book.keys(), reverse=not is_buy)

    for price in prices:

        if remaining_qty <= 0:
            break

        # Stop when the price is no longer executable.
        if is_buy and price > order_price:
            break

        if not is_buy and price < order_price:
            break

        # FIFO queue at this price level.
        resting_orders = opposing_book[price]
        index = 0

        while index < len(resting_orders) and remaining_qty > 0:

            resting_order = resting_orders[index]

            matched_qty = min(
                remaining_qty,
                resting_order.quantity
            )

            # Create the execution record.
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
                    timestamp_ns=order.timestamp_ns
                )
            )

            remaining_qty -= matched_qty

            resting_remaining = (
                resting_order.quantity - matched_qty
            )

            # Remove completely filled resting order.
            if resting_remaining == 0:
                resting_orders.pop(index)

            else:
                # Order is immutable, so create a replacement.
                resting_orders[index] = Order(
                    order_id=resting_order.order_id,
                    price=resting_order.price,
                    quantity=resting_remaining,
                    side=resting_order.side,
                    timestamp_ns=resting_order.timestamp_ns
                )

                index += 1

        # Remove empty price levels.
        if not resting_orders:
            del opposing_book[price]

    # Add any unfilled incoming quantity to the book.
    if remaining_qty > 0:

        remaining_order = Order(
            order_id=order.order_id,
            price=order.price,
            quantity=remaining_qty,
            side=order.side,
            timestamp_ns=order.timestamp_ns
        )

        order_book.add_order(remaining_order)

    return trades
