"""
Unit tests for Whale Order Detection in ChronosMatch.
"""

import pytest

from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook
from chronosmatch.trade import Trade
from chronosmatch.whale_detector import WhaleDetector, WhaleOrder, detect_whale


class TestWhaleDetector:
    """Test suite for detect_whale and WhaleDetector."""

    def test_empty_trades_returns_none(self):
        order = Order(order_id=1, price=1000, quantity=10, side=OrderSide.BUY, timestamp_ns=100)
        assert detect_whale(order, []) is None
        assert WhaleDetector.detect(order, []) is None

    def test_single_trade_returns_none(self):
        order = Order(order_id=1, price=1000, quantity=10, side=OrderSide.BUY, timestamp_ns=100)
        trades = [
            Trade(buy_order_id=1, sell_order_id=2, price=950, quantity=10, timestamp_ns=100)
        ]
        assert detect_whale(order, trades) is None

    def test_multiple_trades_at_same_price_returns_none(self):
        """Verifies distinct price levels count, not the number of Trade records."""
        order = Order(order_id=1, price=1000, quantity=20, side=OrderSide.BUY, timestamp_ns=100)
        trades = [
            Trade(buy_order_id=1, sell_order_id=2, price=950, quantity=10, timestamp_ns=100),
            Trade(buy_order_id=1, sell_order_id=3, price=950, quantity=5, timestamp_ns=100),
            Trade(buy_order_id=1, sell_order_id=4, price=950, quantity=5, timestamp_ns=100),
        ]
        # 3 trades, but all at price 950 (1 distinct level)
        assert detect_whale(order, trades) is None

    def test_two_distinct_prices_full_fill(self):
        order = Order(order_id=10, price=1050, quantity=15, side=OrderSide.BUY, timestamp_ns=500)
        trades = [
            Trade(buy_order_id=10, sell_order_id=2, price=1000, quantity=10, timestamp_ns=500),
            Trade(buy_order_id=10, sell_order_id=3, price=1020, quantity=5, timestamp_ns=500),
        ]
        whale = detect_whale(order, trades)

        assert whale is not None
        assert isinstance(whale, WhaleOrder)
        assert whale.order_id == 10
        assert whale.side == OrderSide.BUY
        assert whale.levels_swept == 2
        assert whale.execution_prices == (1000, 1020)
        assert whale.total_quantity == 15
        assert len(whale.trades) == 2
        assert whale.timestamp_ns == 500
        assert whale.is_partial is False

    def test_two_distinct_prices_partial_fill(self):
        """Partially filled orders executing across at least two levels must be detected."""
        order = Order(order_id=11, price=1050, quantity=25, side=OrderSide.BUY, timestamp_ns=600)
        trades = [
            Trade(buy_order_id=11, sell_order_id=2, price=1000, quantity=10, timestamp_ns=600),
            Trade(buy_order_id=11, sell_order_id=3, price=1020, quantity=5, timestamp_ns=600),
        ]
        # Executed 15 out of 25 quantity
        whale = detect_whale(order, trades)

        assert whale is not None
        assert whale.order_id == 11
        assert whale.levels_swept == 2
        assert whale.total_quantity == 15
        assert whale.is_partial is True

    def test_three_distinct_prices_sweep(self):
        order = Order(order_id=20, price=500, quantity=30, side=OrderSide.BUY, timestamp_ns=1000)
        trades = [
            Trade(buy_order_id=20, sell_order_id=1, price=450, quantity=10, timestamp_ns=1000),
            Trade(buy_order_id=20, sell_order_id=2, price=460, quantity=10, timestamp_ns=1000),
            Trade(buy_order_id=20, sell_order_id=3, price=470, quantity=10, timestamp_ns=1000),
        ]
        whale = detect_whale(order, trades)

        assert whale is not None
        assert whale.levels_swept == 3
        assert whale.execution_prices == (450, 460, 470)
        assert whale.total_quantity == 30
        assert whale.is_partial is False

    def test_sell_order_whale_detection(self):
        order = Order(order_id=30, price=900, quantity=15, side=OrderSide.SELL, timestamp_ns=2000)
        trades = [
            Trade(buy_order_id=5, sell_order_id=30, price=950, quantity=8, timestamp_ns=2000),
            Trade(buy_order_id=6, sell_order_id=30, price=920, quantity=7, timestamp_ns=2000),
        ]
        whale = detect_whale(order, trades)

        assert whale is not None
        assert whale.order_id == 30
        assert whale.side == OrderSide.SELL
        assert whale.levels_swept == 2
        assert whale.execution_prices == (920, 950)  # Sorted order
        assert whale.total_quantity == 15
        assert whale.is_partial is False

    def test_whale_order_immutability(self):
        order = Order(order_id=40, price=1000, quantity=10, side=OrderSide.BUY, timestamp_ns=3000)
        trades = [
            Trade(buy_order_id=40, sell_order_id=1, price=900, quantity=5, timestamp_ns=3000),
            Trade(buy_order_id=40, sell_order_id=2, price=950, quantity=5, timestamp_ns=3000),
        ]
        whale = detect_whale(order, trades)
        assert whale is not None
        with pytest.raises((AttributeError, TypeError)):
            whale.order_id = 999  # frozen dataclass prevents mutation

    def test_invalid_order_type_raises_type_error(self):
        with pytest.raises(TypeError, match="order must be an instance of Order"):
            detect_whale("not_an_order", [])

    def test_integration_with_matching_engine_sweep(self):
        """End-to-end test with real MatchingEngine processing."""
        engine = MatchingEngine(use_cython=False)
        book = engine.order_book

        # Pre-populate book with 2 asks at different prices
        book.add_order(Order(order_id=1, price=100, quantity=10, side=OrderSide.SELL, timestamp_ns=10))
        book.add_order(Order(order_id=2, price=105, quantity=10, side=OrderSide.SELL, timestamp_ns=20))

        # Incoming BUY crosses both price levels
        incoming_buy = Order(order_id=99, price=110, quantity=15, side=OrderSide.BUY, timestamp_ns=50)
        trades = engine.process_order(incoming_buy)

        assert len(trades) == 2
        whale = detect_whale(incoming_buy, trades)

        assert whale is not None
        assert whale.order_id == 99
        assert whale.side == OrderSide.BUY
        assert whale.levels_swept == 2
        assert whale.execution_prices == (100, 105)
        assert whale.total_quantity == 15
        assert whale.is_partial is False

