"""Unit tests for the CursesDashboard terminal monitor."""

from datetime import datetime
from chronosmatch.dashboard import CursesDashboard


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

    dashboard.update(orders=100, trades=40, status="RUNNING", latency_us=15.2)
    assert dashboard.orders == 100
    assert dashboard.trades == 40
    assert dashboard.status == "RUNNING"
    assert dashboard.latency_us == 15.2


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


def test_dashboard_render_and_refresh():
    mock = MockStdscr()
    dashboard = CursesDashboard(mock)
    dashboard.update(orders=50, trades=10, status="RUNNING")
    dashboard.refresh()

    # Verify rendering occurred
    assert len(mock.strings) > 0
    joined = " ".join(str(s) for s in mock.strings)
    assert "CHRONOSMATCH" in joined
    assert "RUNNING" in joined
