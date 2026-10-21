"""
Unit tests for the Limit Order Book.
"""

import unittest

from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook


class TestOrderBook(unittest.TestCase):
    """Test suite verifying OrderBook order insertion, price level grouping, and FIFO order."""

    def setUp(self) -> None:
        """Initialize a fresh OrderBook instance before each test."""
        self.book = OrderBook()

    def test_add_single_buy_order(self) -> None:
        """Verify that adding a BUY order places it into bids under its price key."""
        buy_order = Order(
            order_id=1,
            price=15000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1_000_000_000,
        )
        self.book.add_order(buy_order)

        self.assertIn(15000, self.book.bids)
        self.assertEqual(len(self.book.bids[15000]), 1)
        self.assertIs(self.book.bids[15000][0], buy_order)
        self.assertEqual(len(self.book.asks), 0)

    def test_add_single_sell_order(self) -> None:
        """Verify that adding a SELL order places it into asks under its price key."""
        sell_order = Order(
            order_id=2,
            price=15050,
            quantity=5,
            side=OrderSide.SELL,
            timestamp_ns=1_000_000_100,
        )
        self.book.add_order(sell_order)

        self.assertIn(15050, self.book.asks)
        self.assertEqual(len(self.book.asks[15050]), 1)
        self.assertIs(self.book.asks[15050][0], sell_order)
        self.assertEqual(len(self.book.bids), 0)

    def test_multiple_orders_same_price_preserve_fifo_order(self) -> None:
        """Verify that multiple orders at the same price level preserve FIFO insertion order."""
        order1 = Order(
            order_id=1,
            price=10000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1_000_000_001,
        )
        order2 = Order(
            order_id=2,
            price=10000,
            quantity=20,
            side=OrderSide.BUY,
            timestamp_ns=1_000_000_002,
        )
        order3 = Order(
            order_id=3,
            price=10000,
            quantity=15,
            side=OrderSide.BUY,
            timestamp_ns=1_000_000_003,
        )

        self.book.add_order(order1)
        self.book.add_order(order2)
        self.book.add_order(order3)

        self.assertEqual(len(self.book.bids[10000]), 3)
        self.assertIs(self.book.bids[10000][0], order1)
        self.assertIs(self.book.bids[10000][1], order2)
        self.assertIs(self.book.bids[10000][2], order3)

    def test_multiple_sell_orders_same_price_preserve_fifo_order(self) -> None:
        """Verify FIFO ordering for multiple SELL orders at the same price."""
        sell1 = Order(
            order_id=10,
            price=20000,
            quantity=5,
            side=OrderSide.SELL,
            timestamp_ns=100,
        )
        sell2 = Order(
            order_id=11,
            price=20000,
            quantity=8,
            side=OrderSide.SELL,
            timestamp_ns=200,
        )

        self.book.add_order(sell1)
        self.book.add_order(sell2)

        self.assertEqual(len(self.book.asks[20000]), 2)
        self.assertIs(self.book.asks[20000][0], sell1)
        self.assertIs(self.book.asks[20000][1], sell2)

    def test_orders_at_different_prices_stored_under_correct_keys(self) -> None:
        """Verify that orders at distinct price levels are separated into correct dictionary keys."""
        buy_low = Order(
            order_id=1,
            price=9900,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1_000,
        )
        buy_high = Order(
            order_id=2,
            price=10000,
            quantity=15,
            side=OrderSide.BUY,
            timestamp_ns=1_001,
        )
        sell_low = Order(
            order_id=3,
            price=10100,
            quantity=20,
            side=OrderSide.SELL,
            timestamp_ns=1_002,
        )
        sell_high = Order(
            order_id=4,
            price=10200,
            quantity=25,
            side=OrderSide.SELL,
            timestamp_ns=1_003,
        )

        self.book.add_order(buy_low)
        self.book.add_order(buy_high)
        self.book.add_order(sell_low)
        self.book.add_order(sell_high)

        self.assertEqual(sorted(self.book.bids.keys()), [9900, 10000])
        self.assertEqual(sorted(self.book.asks.keys()), [10100, 10200])
        self.assertEqual(self.book.bids[9900], [buy_low])
        self.assertEqual(self.book.bids[10000], [buy_high])
        self.assertEqual(self.book.asks[10100], [sell_low])
        self.assertEqual(self.book.asks[10200], [sell_high])

    def test_bids_and_asks_remain_isolated(self) -> None:
        """Verify that BUY and SELL orders at the same price stay separated in bids and asks."""
        buy_order = Order(
            order_id=1,
            price=10000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1_000,
        )
        sell_order = Order(
            order_id=2,
            price=10000,
            quantity=10,
            side=OrderSide.SELL,
            timestamp_ns=1_001,
        )

        self.book.add_order(buy_order)
        self.book.add_order(sell_order)

        self.assertIn(10000, self.book.bids)
        self.assertIn(10000, self.book.asks)
        self.assertEqual(self.book.bids[10000], [buy_order])
        self.assertEqual(self.book.asks[10000], [sell_order])

    def test_reject_invalid_order_type(self) -> None:
        """Verify that non-Order objects raise TypeError."""
        with self.assertRaises(TypeError):
            self.book.add_order("not_an_order")  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            self.book.add_order(None)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            self.book.add_order(12345)  # type: ignore[arg-type]

    def test_best_bid_and_best_ask_empty_book(self) -> None:
        """Verify that best_bid() and best_ask() return None when the order book is empty."""
        self.assertIsNone(self.book.best_bid())
        self.assertIsNone(self.book.best_ask())

    def test_best_bid_unsorted_insertion(self) -> None:
        """Verify that best_bid() returns the highest bid price regardless of insertion order."""
        prices = [10000, 10500, 9500, 10200]
        for i, price in enumerate(prices, start=1):
            self.book.add_order(
                Order(
                    order_id=i,
                    price=price,
                    quantity=10,
                    side=OrderSide.BUY,
                    timestamp_ns=i * 1000,
                )
            )

        self.assertEqual(self.book.best_bid(), 10500)

    def test_best_ask_unsorted_insertion(self) -> None:
        """Verify that best_ask() returns the lowest ask price regardless of insertion order."""
        prices = [11000, 10800, 11500, 10900]
        for i, price in enumerate(prices, start=1):
            self.book.add_order(
                Order(
                    order_id=i,
                    price=price,
                    quantity=10,
                    side=OrderSide.SELL,
                    timestamp_ns=i * 1000,
                )
            )

        self.assertEqual(self.book.best_ask(), 10800)

    def test_empty_side_isolation(self) -> None:
        """Verify that having orders on only one side does not affect the other side."""
        buy_order = Order(
            order_id=1,
            price=15000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1000,
        )
        self.book.add_order(buy_order)

        self.assertEqual(self.book.best_bid(), 15000)
        self.assertIsNone(self.book.best_ask())

        book_with_only_asks = OrderBook()
        sell_order = Order(
            order_id=2,
            price=15100,
            quantity=5,
            side=OrderSide.SELL,
            timestamp_ns=2000,
        )
        book_with_only_asks.add_order(sell_order)

        self.assertIsNone(book_with_only_asks.best_bid())
        self.assertEqual(book_with_only_asks.best_ask(), 15100)

    def test_best_bid_and_best_ask_do_not_modify_order_book(self) -> None:
        """Verify that calling best_bid() and best_ask() does not mutate the order book."""
        buy_order = Order(
            order_id=1,
            price=10000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1000,
        )
        sell_order = Order(
            order_id=2,
            price=10200,
            quantity=20,
            side=OrderSide.SELL,
            timestamp_ns=2000,
        )
        self.book.add_order(buy_order)
        self.book.add_order(sell_order)

        bids_snapshot = dict(self.book.bids)
        asks_snapshot = dict(self.book.asks)

        # Call multiple times
        for _ in range(3):
            self.assertEqual(self.book.best_bid(), 10000)
            self.assertEqual(self.book.best_ask(), 10200)

        self.assertEqual(self.book.bids, bids_snapshot)
        self.assertEqual(self.book.asks, asks_snapshot)
        self.assertEqual(len(self.book.bids[10000]), 1)
        self.assertEqual(len(self.book.asks[10200]), 1)

    def test_remove_order_from_bids(self) -> None:
        """Verify that removing a BUY order removes it from bids and deletes the price level when empty."""
        buy_order = Order(
            order_id=1,
            price=15000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1_000,
        )
        self.book.add_order(buy_order)
        self.assertIn(15000, self.book.bids)

        self.book.remove_order(1)
        self.assertNotIn(15000, self.book.bids)
        self.assertEqual(len(self.book.bids), 0)
        self.assertIsNone(self.book.best_bid())

    def test_remove_order_from_asks(self) -> None:
        """Verify that removing a SELL order removes it from asks and deletes the price level when empty."""
        sell_order = Order(
            order_id=2,
            price=15050,
            quantity=5,
            side=OrderSide.SELL,
            timestamp_ns=1_100,
        )
        self.book.add_order(sell_order)
        self.assertIn(15050, self.book.asks)

        self.book.remove_order(2)
        self.assertNotIn(15050, self.book.asks)
        self.assertEqual(len(self.book.asks), 0)
        self.assertIsNone(self.book.best_ask())

    def test_remove_order_preserves_fifo_order_at_same_price(self) -> None:
        """Verify removing an order from a price level preserves the FIFO order of other orders."""
        order1 = Order(
            order_id=10,
            price=10000,
            quantity=5,
            side=OrderSide.BUY,
            timestamp_ns=100,
        )
        order2 = Order(
            order_id=20,
            price=10000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=200,
        )
        order3 = Order(
            order_id=30,
            price=10000,
            quantity=15,
            side=OrderSide.BUY,
            timestamp_ns=300,
        )
        self.book.add_order(order1)
        self.book.add_order(order2)
        self.book.add_order(order3)

        # Remove the middle order (order2)
        self.book.remove_order(20)
        self.assertEqual(len(self.book.bids[10000]), 2)
        self.assertIs(self.book.bids[10000][0], order1)
        self.assertIs(self.book.bids[10000][1], order3)

        # Remove the first order (order1)
        self.book.remove_order(10)
        self.assertEqual(len(self.book.bids[10000]), 1)
        self.assertIs(self.book.bids[10000][0], order3)

    def test_remove_order_cleans_up_empty_price_level_only(self) -> None:
        """Verify that a price level is deleted only when all orders at that price are removed."""
        order1 = Order(
            order_id=1,
            price=10000,
            quantity=5,
            side=OrderSide.BUY,
            timestamp_ns=100,
        )
        order2 = Order(
            order_id=2,
            price=10000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=200,
        )
        order3 = Order(
            order_id=3,
            price=9900,
            quantity=15,
            side=OrderSide.BUY,
            timestamp_ns=300,
        )
        self.book.add_order(order1)
        self.book.add_order(order2)
        self.book.add_order(order3)

        # Remove order1: price 10000 should still exist with order2
        self.book.remove_order(1)
        self.assertIn(10000, self.book.bids)
        self.assertEqual(self.book.bids[10000], [order2])
        self.assertIn(9900, self.book.bids)

        # Remove order2: price 10000 should now be deleted
        self.book.remove_order(2)
        self.assertNotIn(10000, self.book.bids)
        self.assertIn(9900, self.book.bids)
        self.assertEqual(self.book.best_bid(), 9900)

    def test_remove_order_updates_best_bid_and_best_ask(self) -> None:
        """Verify that removing the best bid or ask order correctly updates the best price."""
        # Setup bids
        self.book.add_order(
            Order(order_id=1, price=10000, quantity=10, side=OrderSide.BUY, timestamp_ns=1)
        )
        self.book.add_order(
            Order(order_id=2, price=10500, quantity=5, side=OrderSide.BUY, timestamp_ns=2)
        )
        self.assertEqual(self.book.best_bid(), 10500)

        # Remove highest bid
        self.book.remove_order(2)
        self.assertEqual(self.book.best_bid(), 10000)

        # Remove remaining bid
        self.book.remove_order(1)
        self.assertIsNone(self.book.best_bid())

        # Setup asks
        self.book.add_order(
            Order(order_id=3, price=11000, quantity=10, side=OrderSide.SELL, timestamp_ns=3)
        )
        self.book.add_order(
            Order(order_id=4, price=11500, quantity=5, side=OrderSide.SELL, timestamp_ns=4)
        )
        self.assertEqual(self.book.best_ask(), 11000)

        # Remove lowest ask
        self.book.remove_order(3)
        self.assertEqual(self.book.best_ask(), 11500)

        # Remove remaining ask
        self.book.remove_order(4)
        self.assertIsNone(self.book.best_ask())

    def test_remove_nonexistent_order_does_nothing(self) -> None:
        """Verify that attempting to remove a non-existent order ID leaves the book untouched."""
        buy = Order(order_id=1, price=10000, quantity=10, side=OrderSide.BUY, timestamp_ns=1)
        sell = Order(order_id=2, price=10200, quantity=5, side=OrderSide.SELL, timestamp_ns=2)
        self.book.add_order(buy)
        self.book.add_order(sell)

        self.book.remove_order(999)

        self.assertEqual(self.book.best_bid(), 10000)
        self.assertEqual(self.book.best_ask(), 10200)
        self.assertEqual(self.book.bids[10000], [buy])
        self.assertEqual(self.book.asks[10200], [sell])

    def test_remove_order_validation(self) -> None:
        """Verify that invalid order_id types or non-positive values raise appropriate exceptions."""
        with self.assertRaises(TypeError):
            self.book.remove_order("invalid")  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            self.book.remove_order(None)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            self.book.remove_order(True)  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            self.book.remove_order(0)

        with self.assertRaises(ValueError):
            self.book.remove_order(-5)

    def test_price_time_priority(self) -> None:
        """Verify price-time priority: price priority first, FIFO priority at equal prices."""
        # Add 3 orders across 2 bid price levels
        bid_low_1 = Order(order_id=1, price=9900, quantity=10, side=OrderSide.BUY, timestamp_ns=100)
        bid_high_1 = Order(order_id=2, price=10000, quantity=5, side=OrderSide.BUY, timestamp_ns=200)
        bid_high_2 = Order(order_id=3, price=10000, quantity=8, side=OrderSide.BUY, timestamp_ns=300)

        self.book.add_order(bid_low_1)
        self.book.add_order(bid_high_1)
        self.book.add_order(bid_high_2)

        # 1. Price Priority: 10000 is prioritized over 9900
        self.assertEqual(self.book.best_bid(), 10000)

        # 2. Time Priority at 10000: bid_high_1 (arrival timestamp 200) is first at index 0
        self.assertIs(self.book.bids[10000][0], bid_high_1)
        self.assertIs(self.book.bids[10000][1], bid_high_2)

        # 3. When front order is removed, next in line takes priority
        self.book.remove_order(2)
        self.assertIs(self.book.bids[10000][0], bid_high_2)

        # 4. When price level 10000 is emptied, next best price level (9900) becomes best bid
        self.book.remove_order(3)
        self.assertEqual(self.book.best_bid(), 9900)
        self.assertIs(self.book.bids[9900][0], bid_low_1)
