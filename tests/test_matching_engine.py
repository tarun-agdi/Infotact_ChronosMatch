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


class TestMatchingEngineBookMutation(unittest.TestCase):
    """Test suite verifying OrderBook state updates after matching and order processing."""

    def setUp(self) -> None:
        self.book = OrderBook()
        self.engine = MatchingEngine(self.book)

    def test_full_fill_removes_resting_order_and_cleans_price_level(self) -> None:
        """A fully filled resting order is completely removed from the order book."""
        resting_sell = Order(
            order_id=101, price=10000, quantity=10, side=OrderSide.SELL, timestamp_ns=1000
        )
        self.book.add_order(resting_sell)
        self.assertEqual(self.book.best_ask(), 10000)

        incoming_buy = Order(
            order_id=201, price=10000, quantity=10, side=OrderSide.BUY, timestamp_ns=2000
        )
        trades = self.engine.process_order(incoming_buy)

        # Trade executed
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, 10)
        self.assertEqual(trades[0].price, 10000)

        # Resting order removed and price level cleaned up
        self.assertNotIn(10000, self.book.asks)
        self.assertIsNone(self.book.best_ask())

        # Incoming order was fully filled, so not added to bids
        self.assertEqual(len(self.book.bids), 0)
        self.assertIsNone(self.book.best_bid())

    def test_partial_fill_resting_order_retains_remaining_quantity(self) -> None:
        """A partially filled resting order retains only its unfilled quantity in the book."""
        resting_sell = Order(
            order_id=101, price=10000, quantity=10, side=OrderSide.SELL, timestamp_ns=1000
        )
        self.book.add_order(resting_sell)

        incoming_buy = Order(
            order_id=201, price=10000, quantity=4, side=OrderSide.BUY, timestamp_ns=2000
        )
        trades = self.engine.process_order(incoming_buy)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, 4)

        # Resting order retains remaining quantity of 6
        self.assertIn(10000, self.book.asks)
        self.assertEqual(len(self.book.asks[10000]), 1)
        resting_remaining = self.book.asks[10000][0]
        self.assertEqual(resting_remaining.order_id, 101)
        self.assertEqual(resting_remaining.quantity, 6)
        self.assertEqual(resting_remaining.price, 10000)
        self.assertEqual(self.book.best_ask(), 10000)

        # Incoming order is fully filled, not added to bids
        self.assertEqual(len(self.book.bids), 0)

    def test_partial_fill_preserves_fifo_priority_at_same_price(self) -> None:
        """Partial fill updates the resting order in place, preserving FIFO sequence."""
        sell1 = Order(order_id=1, price=10000, quantity=10, side=OrderSide.SELL, timestamp_ns=10)
        sell2 = Order(order_id=2, price=10000, quantity=10, side=OrderSide.SELL, timestamp_ns=20)
        self.book.add_order(sell1)
        self.book.add_order(sell2)

        incoming_buy = Order(order_id=3, price=10000, quantity=4, side=OrderSide.BUY, timestamp_ns=30)
        trades = self.engine.process_order(incoming_buy)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].sell_order_id, 1)

        # sell1 must still be at index 0 with quantity 6, sell2 at index 1 with quantity 10
        self.assertEqual(len(self.book.asks[10000]), 2)
        self.assertEqual(self.book.asks[10000][0].order_id, 1)
        self.assertEqual(self.book.asks[10000][0].quantity, 6)
        self.assertEqual(self.book.asks[10000][1].order_id, 2)
        self.assertEqual(self.book.asks[10000][1].quantity, 10)

    def test_unmatched_incoming_order_rests_in_book(self) -> None:
        """An incoming order that cannot cross is placed on the correct side of the book."""
        resting_sell = Order(
            order_id=101, price=10500, quantity=5, side=OrderSide.SELL, timestamp_ns=1000
        )
        self.book.add_order(resting_sell)

        incoming_buy = Order(
            order_id=201, price=10400, quantity=5, side=OrderSide.BUY, timestamp_ns=2000
        )
        trades = self.engine.process_order(incoming_buy)

        self.assertEqual(trades, [])
        # Incoming buy rests on bids
        self.assertIn(10400, self.book.bids)
        self.assertEqual(len(self.book.bids[10400]), 1)
        self.assertEqual(self.book.bids[10400][0].order_id, 201)
        self.assertEqual(self.book.best_bid(), 10400)
        self.assertEqual(self.book.best_ask(), 10500)

    def test_partially_filled_incoming_order_rests_remaining_quantity(self) -> None:
        """When an incoming order is partially filled, its remaining quantity rests in the book."""
        resting_sell = Order(
            order_id=101, price=10000, quantity=5, side=OrderSide.SELL, timestamp_ns=1000
        )
        self.book.add_order(resting_sell)

        incoming_buy = Order(
            order_id=201, price=10000, quantity=12, side=OrderSide.BUY, timestamp_ns=2000
        )
        trades = self.engine.process_order(incoming_buy)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, 5)

        # Resting sell fully filled and removed
        self.assertNotIn(10000, self.book.asks)
        self.assertIsNone(self.book.best_ask())

        # Incoming buy has 7 units remaining (12 - 5) resting in bids
        self.assertIn(10000, self.book.bids)
        self.assertEqual(len(self.book.bids[10000]), 1)
        remaining_buy = self.book.bids[10000][0]
        self.assertEqual(remaining_buy.order_id, 201)
        self.assertEqual(remaining_buy.quantity, 7)
        self.assertEqual(remaining_buy.price, 10000)
        self.assertEqual(self.book.best_bid(), 10000)

    def test_multiple_price_levels_sweep_and_book_update(self) -> None:
        """An incoming order sweeping multiple levels removes filled levels and updates partial levels."""
        sell_a = Order(order_id=1, price=100, quantity=5, side=OrderSide.SELL, timestamp_ns=10)
        sell_b = Order(order_id=2, price=102, quantity=5, side=OrderSide.SELL, timestamp_ns=20)
        sell_c = Order(order_id=3, price=105, quantity=10, side=OrderSide.SELL, timestamp_ns=30)
        self.book.add_order(sell_a)
        self.book.add_order(sell_b)
        self.book.add_order(sell_c)

        # Limit price 104 matches price 100 and 102, but cannot match 105
        # Total incoming quantity = 14: fills 5 @ 100, 5 @ 102, remaining 4 rests at 104
        incoming_buy = Order(order_id=10, price=104, quantity=14, side=OrderSide.BUY, timestamp_ns=50)
        trades = self.engine.process_order(incoming_buy)

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].quantity, 5)
        self.assertEqual(trades[0].price, 100)
        self.assertEqual(trades[1].quantity, 5)
        self.assertEqual(trades[1].price, 102)

        # Levels 100 and 102 are completely emptied
        self.assertNotIn(100, self.book.asks)
        self.assertNotIn(102, self.book.asks)

        # Level 105 was untouched
        self.assertIn(105, self.book.asks)
        self.assertEqual(self.book.asks[105][0].quantity, 10)
        self.assertEqual(self.book.best_ask(), 105)

        # Incoming buy remainder (4 units @ 104) rests in bids
        self.assertIn(104, self.book.bids)
        self.assertEqual(self.book.bids[104][0].quantity, 4)
        self.assertEqual(self.book.best_bid(), 104)

    def test_sell_side_symmetry_full_and_partial_fill(self) -> None:
        """An incoming SELL order correctly sweeps bids, mutates the book, and rests remainder."""
        buy_a = Order(order_id=1, price=105, quantity=8, side=OrderSide.BUY, timestamp_ns=10)
        buy_b = Order(order_id=2, price=100, quantity=10, side=OrderSide.BUY, timestamp_ns=20)
        self.book.add_order(buy_a)
        self.book.add_order(buy_b)

        # Incoming sell sweeps buy_a (8 @ 105) and partially fills buy_b (4 @ 100)
        incoming_sell = Order(order_id=3, price=95, quantity=12, side=OrderSide.SELL, timestamp_ns=30)
        trades = self.engine.process_order(incoming_sell)

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].buy_order_id, 1)
        self.assertEqual(trades[0].quantity, 8)
        self.assertEqual(trades[0].price, 105)

        self.assertEqual(trades[1].buy_order_id, 2)
        self.assertEqual(trades[1].quantity, 4)
        self.assertEqual(trades[1].price, 100)

        # buy_a is removed; level 105 deleted
        self.assertNotIn(105, self.book.bids)

        # buy_b has 6 units remaining (10 - 4)
        self.assertIn(100, self.book.bids)
        self.assertEqual(self.book.bids[100][0].quantity, 6)
        self.assertEqual(self.book.best_bid(), 100)

        # Incoming sell is fully matched (12 units)
        self.assertEqual(len(self.book.asks), 0)
        self.assertIsNone(self.book.best_ask())

    def test_match_alias_functions_identically(self) -> None:
        """Verify that engine.match aliases process_order and performs book mutation."""
        resting_sell = Order(order_id=1, price=100, quantity=5, side=OrderSide.SELL, timestamp_ns=1)
        self.book.add_order(resting_sell)

        incoming_buy = Order(order_id=2, price=100, quantity=5, side=OrderSide.BUY, timestamp_ns=2)
        trades = self.engine.match(incoming_buy)

        self.assertEqual(len(trades), 1)
        self.assertNotIn(100, self.book.asks)


if __name__ == "__main__":
    unittest.main()
