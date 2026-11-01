import pytest

from src.monitor import TestMonitor


@pytest.fixture
def monitor():
    return TestMonitor()


def test_initial_statistics(monitor):
    stats = monitor.get_statistics()

    assert stats["orders"] == 0
    assert stats["trades"] == 0


def test_order_count(monitor):
    monitor.record_order()

    stats = monitor.get_statistics()

    assert stats["orders"] == 1


def test_trade_count(monitor):
    monitor.record_trade()

    stats = monitor.get_statistics()

    assert stats["trades"] == 1


def test_error_tracking(monitor):
    monitor.record_error("Matching error")

    stats = monitor.get_statistics()

    assert stats["errors"] == 1

    class TestMonitor:

    def __init__(self):
        self.orders = 0
        self.trades = 0
        self.errors = 0

    def record_order(self):
        self.orders += 1

    def record_trade(self):
        self.trades += 1

    def record_error(self, message):
        self.errors += 1
        print(f"ERROR: {message}")

    def get_statistics(self):
        return {
            "orders": self.orders,
            "trades": self.trades,
            "errors": self.errors
        }