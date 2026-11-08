"""Unit tests for the CursesDashboard terminal monitor."""

from datetime import datetime
from chronosmatch.dashboard import CursesDashboard
from chronosmatch.matching_engine import CYTHON_CORE_AVAILABLE, MatchingEngine
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook
from chronosmatch.trade import Trade
from chronosmatch.whale_detector import WhaleOrder


class MockStdscr:
    def __init__(self, height=24, width=80):
        self.height = height
        self.width = width
        self.strings = []

    def nodelay(self, val):
        pass

    def keypad(self, val):
        pass

    def getmaxyx(self):
        return (self.height, self.width)

    def erase(self):
        self.strings.clear()

    def addstr(self, *args):
        self.strings.append(args)

    def refresh(self):
        pass

    def getch(self):
        return -1


def test_dashboard_initialization_and_update():
    mock = MockStdscr()
    dashboard = CursesDashboard(mock)

    assert dashboard.orders == 0
    assert dashboard.trades == 0
    assert dashboard.status == "STARTING"
    assert dashboard.best_bid is None
    assert dashboard.best_ask is None
    assert dashboard.whales == 0

    dashboard.update(
        orders=100,
        trades=40,
        status="RUNNING",
        latency_us=15.2,
        best_bid=10500,
        best_ask=10550,
    )
    assert dashboard.orders == 100
    assert dashboard.trades == 40
    assert dashboard.status == "RUNNING"
    assert dashboard.latency_us == 15.2
    assert dashboard.best_bid == 10500
    assert dashboard.best_ask == 10550


def test_dashboard_trade_recording():
    mock = MockStdscr()
    dashboard = CursesDashboard(mock)

    trade = {
        "time": "12:30:00",
        "symbol": "10/20",
        "side": "MATCH",
        "price": 50000,
        "quantity": 10,
    }
    dashboard.add_trade(trade)
    assert len(dashboard.recent_trades) == 1
    assert "10/20" in dashboard.recent_trades[0]


def test_dashboard_whale_alert_recording_and_rendering():
    mock = MockStdscr()
    dashboard = CursesDashboard(mock)

    t1 = Trade(buy_order_id=999, sell_order_id=10, price=100, quantity=50, timestamp_ns=1000)
    t2 = Trade(buy_order_id=999, sell_order_id=11, price=105, quantity=150, timestamp_ns=1000)
    whale = WhaleOrder(
        order_id=999,
        side=OrderSide.BUY,
        levels_swept=2,
        execution_prices=(100, 105),
        total_quantity=200,
        trades=(t1, t2),
        timestamp_ns=1000,
        is_partial=False,
    )

    dashboard.add_whale(whale)
    assert dashboard.whales == 1
    assert len(dashboard.recent_whales) == 1

    w_record = dashboard.recent_whales[0]
    assert w_record["order_id"] == 999
    assert w_record["side"] == "BUY"
    assert w_record["quantity"] == 200
    assert w_record["levels_swept"] == 2
    assert "[100, 105]" in w_record["prices"]

    dashboard.refresh()
    joined = " ".join(str(s) for s in mock.strings)
    assert "WHALE ALERTS" in joined
    assert "#999" in joined
    assert "BUY" in joined
    assert "200" in joined


def test_dashboard_market_snapshot_and_cython_health_rendering():
    mock = MockStdscr()
    book = OrderBook()
    book.add_order(Order(order_id=1, price=1000, quantity=10, side=OrderSide.BUY, timestamp_ns=10))
    book.add_order(Order(order_id=2, price=1020, quantity=10, side=OrderSide.SELL, timestamp_ns=20))
    engine = MatchingEngine(order_book=book, use_cython=True)

    dashboard = CursesDashboard(mock)
    dashboard.engine = engine
    dashboard.update(
        orders=50,
        trades=10,
        status="RUNNING",
        latency_us=4.25,
        best_bid=1000,
        best_ask=1020,
    )
    dashboard.refresh()

    joined = " ".join(str(s) for s in mock.strings)
    assert "ENGINE & PERFORMANCE" in joined
    assert "MARKET SNAPSHOT & WHALES" in joined
    assert "1,000" in joined  # Best Bid
    assert "1,020" in joined  # Best Ask
    assert "20" in joined     # Spread (1020 - 1000)

    if CYTHON_CORE_AVAILABLE:
        assert "CYTHON NATIVE" in joined
    else:
        assert "PYTHON FALLBACK" in joined


def test_dashboard_terminal_size_guard():
    small_mock = MockStdscr(height=15, width=60)
    dashboard = CursesDashboard(small_mock)
    dashboard.refresh()

    joined = " ".join(str(s) for s in small_mock.strings)
    assert "Terminal too small" in joined
