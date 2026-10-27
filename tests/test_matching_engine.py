
import pytest

from chronosmatch.order import Order, OrderSide
from chronosmatch.matching_engine import MatchingEngine


def make_order(order_id, price, quantity, side, timestamp):
    return Order(
        order_id=order_id,
        price=price,
        quantity=quantity,
        side=side,
        timestamp_ns=timestamp,
    )


def test_non_crossing_order_is_added_to_book():
    engine = MatchingEngine()

    sell = make_order(1, 105, 10, OrderSide.SELL, 1)
    trades = engine.process_order(sell)

    assert trades == []
    assert engine.order_book.asks[105][0].order_id == 1


def test_best_price_has_priority():
    engine = MatchingEngine()

    engine.process_order(make_order(1, 105, 5, OrderSide.SELL, 1))
    engine.process_order(make_order(2, 100, 5, OrderSide.SELL, 2))

    trades = engine.process_order(
        make_order(3, 110, 5, OrderSide.BUY, 3)
    )

    assert len(trades) == 1
    assert trades[0].sell_order_id == 2
    assert trades[0].price == 100
    assert trades[0].quantity == 5


def test_fifo_priority_at_same_price():
    engine = MatchingEngine()

    engine.process_order(make_order(1, 100, 5, OrderSide.SELL, 1))
    engine.process_order(make_order(2, 100, 5, OrderSide.SELL, 2))

    trades = engine.process_order(
        make_order(3, 100, 5, OrderSide.BUY, 3)
    )

    assert len(trades) == 1
    assert trades[0].sell_order_id == 1


def test_partial_fill_preserves_remaining_quantity():
    engine = MatchingEngine()

    engine.process_order(make_order(1, 100, 10, OrderSide.SELL, 1))

    trades = engine.process_order(
        make_order(2, 100, 4, OrderSide.BUY, 2)
    )

    assert len(trades) == 1
    assert trades[0].quantity == 4

    remaining = engine.order_book.asks[100]
    assert len(remaining) == 1
    assert remaining[0].order_id == 1
    assert remaining[0].quantity == 6
