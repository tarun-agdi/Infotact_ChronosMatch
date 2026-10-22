"""
Unit tests for MatchingEngine (Person A scope).

Tests focus strictly on:
- Incoming-order crossing checks against the best opposing quotes.
- Minimal matching loop visiting eligible opposing orders and creating Trade records.
- Engine interface and parameter type validation.

Note: Person B owns tests for book mutation, partial-fill resting quantities,
and removing completed orders from the book.
"""

import unittest

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook
from chronosmatch.trade import Trade


class TestMatchingEnginePersonA(unittest.TestCase):
    """Test suite for Person A matching engine tasks."""

    def setUp(self) -> None:
        self.book = OrderBook()
        self.engine = MatchingEngine(self.book)

    def test_crossing_check_empty_book(self) -> None:
        """Neither BUY nor SELL crosses an empty order book."""
        buy = Order(order_id=1, price=10000, quantity=10, side=OrderSide.BUY, timestamp_ns=1)
        sell = Order(order_id=2, price=10000, quantity=10, side=OrderSide.SELL, timestamp_ns=2)

        self.assertFalse(self.engine.is_crossing(buy))
        self.assertFalse(self.engine.is_crossing(sell))

    def test_crossing_check_buy_order(self) -> None:
        """BUY order crosses if limit price >= best ask."""
        # Best ask = 10500
        self.book.add_order(
            Order(order_id=1, price=10500, quantity=5, side=OrderSide.SELL, timestamp_ns=10)
        )

        below_ask = Order(order_id=2, price=10400, quantity=5, side=OrderSide.BUY, timestamp_ns=20)
        equal_ask = Order(order_id=3, price=10500, quantity=5, side=OrderSide.BUY, timestamp_ns=30)
        above_ask = Order(order_id=4, price=10600, quantity=5, side=OrderSide.BUY, timestamp_ns=40)

        self.assertFalse(self.engine.is_crossing(below_ask))
        self.assertTrue(self.engine.is_crossing(equal_ask))
        self.assertTrue(self.engine.is_crossing(above_ask))

    def test_crossing_check_sell_order(self) -> None:
        """SELL order crosses if limit price <= best bid."""
        # Best bid = 10000
        self.book.add_order(
            Order(order_id=1, price=10000, quantity=5, side=OrderSide.BUY, timestamp_ns=10)
        )

        above_bid = Order(order_id=2, price=10100, quantity=5, side=OrderSide.SELL, timestamp_ns=20)
        equal_bid = Order(order_id=3, price=10000, quantity=5, side=OrderSide.SELL, timestamp_ns=30)
        below_bid = Order(order_id=4, price=9900, quantity=5, side=OrderSide.SELL, timestamp_ns=40)

        self.assertFalse(self.engine.is_crossing(above_bid))
        self.assertTrue(self.engine.is_crossing(equal_bid))
        self.assertTrue(self.engine.is_crossing(below_bid))

    def test_uncrossed_order_generates_no_trades(self) -> None:
        """Non-crossing order returns an empty trade list."""
        self.book.add_order(
            Order(order_id=1, price=10500, quantity=5, side=OrderSide.SELL, timestamp_ns=10)
        )
        incoming_buy = Order(order_id=2, price=10400, quantity=5, side=OrderSide.BUY, timestamp_ns=20)

        trades = self.engine.process_order(incoming_buy)
        self.assertEqual(trades, [])

    def test_incoming_buy_matches_resting_sell_at_resting_price(self) -> None:
        """Incoming BUY crossing resting SELL creates Trade at resting order price."""
        resting_sell = Order(
            order_id=101, price=10000, quantity=10, side=OrderSide.SELL, timestamp_ns=1000
        )
        self.book.add_order(resting_sell)

        incoming_buy = Order(
            order_id=201, price=10200, quantity=10, side=OrderSide.BUY, timestamp_ns=2000
        )

        trades = self.engine.process_order(incoming_buy)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade.buy_order_id, 201)
        self.assertEqual(trade.sell_order_id, 101)
        self.assertEqual(trade.price, 10000)  # Resting order's price
        self.assertEqual(trade.quantity, 10)
        self.assertEqual(trade.timestamp_ns, 2000)

    def test_incoming_sell_matches_resting_buy_at_resting_price(self) -> None:
        """Incoming SELL crossing resting BUY creates Trade at resting order price."""
        resting_buy = Order(
            order_id=101, price=10500, quantity=8, side=OrderSide.BUY, timestamp_ns=1000
        )
        self.book.add_order(resting_buy)

        incoming_sell = Order(
            order_id=202, price=10300, quantity=8, side=OrderSide.SELL, timestamp_ns=2500
        )

        trades = self.engine.process_order(incoming_sell)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade.buy_order_id, 101)
        self.assertEqual(trade.sell_order_id, 202)
        self.assertEqual(trade.price, 10500)  # Resting order's price
        self.assertEqual(trade.quantity, 8)
        self.assertEqual(trade.timestamp_ns, 2500)

    def test_incoming_order_matches_across_multiple_price_levels(self) -> None:
        """Incoming BUY order sweeps multiple eligible ask price levels in ascending order."""
        sell_a = Order(order_id=1, price=100, quantity=3, side=OrderSide.SELL, timestamp_ns=10)
        sell_b = Order(order_id=2, price=102, quantity=5, side=OrderSide.SELL, timestamp_ns=20)
        self.book.add_order(sell_a)
        self.book.add_order(sell_b)

        incoming_buy = Order(
            order_id=10, price=105, quantity=4, side=OrderSide.BUY, timestamp_ns=50
        )

        trades = self.engine.process_order(incoming_buy)

        self.assertEqual(len(trades), 2)

        self.assertEqual(trades[0].buy_order_id, 10)
        self.assertEqual(trades[0].sell_order_id, 1)
        self.assertEqual(trades[0].price, 100)
        self.assertEqual(trades[0].quantity, 3)
        self.assertEqual(trades[0].timestamp_ns, 50)

        self.assertEqual(trades[1].buy_order_id, 10)
        self.assertEqual(trades[1].sell_order_id, 2)
        self.assertEqual(trades[1].price, 102)
        self.assertEqual(trades[1].quantity, 1)
        self.assertEqual(trades[1].timestamp_ns, 50)

    def test_type_validation(self) -> None:
        """Invalid types passed to engine methods raise TypeError."""
        with self.assertRaises(TypeError):
            self.engine.is_crossing("not an order")  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            self.engine.process_order(None)  # type: ignore[arg-type]


class TestTradeModel(unittest.TestCase):
    """Test suite for Trade data model."""

    def test_trade_creation_and_attributes(self) -> None:
        trade = Trade(
            buy_order_id=1,
            sell_order_id=2,
            price=15000,
            quantity=10,
            timestamp_ns=100,
        )
        self.assertEqual(trade.buy_order_id, 1)
        self.assertEqual(trade.sell_order_id, 2)
        self.assertEqual(trade.price, 15000)
        self.assertEqual(trade.quantity, 10)
        self.assertEqual(trade.timestamp_ns, 100)

    def test_trade_immutability(self) -> None:
        trade = Trade(buy_order_id=1, sell_order_id=2, price=100, quantity=5, timestamp_ns=1)
        with self.assertRaises((AttributeError, TypeError)):
            trade.price = 200  # type: ignore[misc]

    def test_trade_validation(self) -> None:
        with self.assertRaises(ValueError):
            Trade(buy_order_id=0, sell_order_id=2, price=100, quantity=5, timestamp_ns=1)
        with self.assertRaises(ValueError):
            Trade(buy_order_id=1, sell_order_id=2, price=0, quantity=5, timestamp_ns=1)
        with self.assertRaises(ValueError):
            Trade(buy_order_id=1, sell_order_id=2, price=100, quantity=0, timestamp_ns=1)
        with self.assertRaises(ValueError):
            Trade(buy_order_id=1, sell_order_id=2, price=100, quantity=5, timestamp_ns=-1)


if __name__ == "__main__":
    unittest.main()
