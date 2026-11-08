"""
Unit and integration tests for ChronosMatch Web Dashboard and Operations Console.
"""

from datetime import datetime
import pytest
from starlette.testclient import TestClient

from chronosmatch.matching_engine import CYTHON_CORE_AVAILABLE, MatchingEngine
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook
from chronosmatch.trade import Trade
from chronosmatch.web_dashboard import WebDashboard, app, dashboard_instance
from chronosmatch.whale_detector import WhaleOrder


class TestWebDashboard:
    """Tests for WebDashboard state tracking and telemetry aggregation."""

    def test_dashboard_initialization(self):
        dash = WebDashboard()
        assert dash.orders == 0
        assert dash.trades == 0
        assert dash.whales == 0
        assert dash.status == "STARTING"
        assert dash.latency_us is None
        assert dash.best_bid is None
        assert dash.best_ask is None

    def test_dashboard_update_metrics(self):
        dash = WebDashboard()
        dash.update(
            orders=150,
            trades=75,
            status="RUNNING",
            latency_us=4.25,
            best_bid=10500,
            best_ask=10550,
        )
        assert dash.orders == 150
        assert dash.trades == 75
        assert dash.status == "RUNNING"
        assert dash.latency_us == 4.25
        assert dash.best_bid == 10500
        assert dash.best_ask == 10550

    def test_add_trade_recording(self):
        dash = WebDashboard()
        trade = {
            "time": "12:00:00",
            "symbol": "10/20",
            "side": "MATCH",
            "price": 10000,
            "quantity": 5,
        }
        dash.add_trade(trade)
        assert len(dash.recent_trades) == 1
        assert dash.recent_trades[0]["symbol"] == "10/20"
        assert dash.recent_trades[0]["type"] == "TRADE"

    def test_add_whale_recording_and_breakdown(self):
        dash = WebDashboard()
        t1 = Trade(buy_order_id=1, sell_order_id=2, price=100, quantity=10, timestamp_ns=1000)
        t2 = Trade(buy_order_id=1, sell_order_id=3, price=105, quantity=5, timestamp_ns=1000)
        whale = WhaleOrder(
            order_id=1,
            side=OrderSide.BUY,
            levels_swept=2,
            execution_prices=(100, 105),
            total_quantity=15,
            trades=(t1, t2),
            timestamp_ns=1000,
            is_partial=False,
        )

        dash.add_whale(whale)
        assert dash.whales == 1
        assert len(dash.recent_whales) == 1
        w_record = dash.recent_whales[0]
        assert w_record["order_id"] == 1
        assert w_record["side"] == "BUY"
        assert w_record["levels_swept"] == 2
        assert w_record["total_quantity"] == 15
        assert w_record["is_partial"] is False
        assert len(w_record["trades"]) == 2

        # Verify activity stream received distinguishable event
        assert len(dash.recent_trades) == 1
        assert dash.recent_trades[0]["type"] == "WHALE_ALERT"

    def test_get_snapshot_structure_and_health(self):
        book = OrderBook()
        book.add_order(Order(order_id=1, price=100, quantity=10, side=OrderSide.BUY, timestamp_ns=10))
        book.add_order(Order(order_id=2, price=105, quantity=10, side=OrderSide.SELL, timestamp_ns=20))
        engine = MatchingEngine(order_book=book, use_cython=True)

        dash = WebDashboard(engine=engine)
        dash.update(
            orders=50,
            trades=10,
            status="RUNNING",
            latency_us=2.5,
            best_bid=book.best_bid(),
            best_ask=book.best_ask(),
        )

        snapshot = dash.get_snapshot()

        # 1. Engine Overview
        assert "engine_overview" in snapshot
        assert snapshot["engine_overview"]["orders"] == 50
        assert snapshot["engine_overview"]["trades"] == 10
        assert snapshot["engine_overview"]["latency_us"] == 2.5
        assert snapshot["engine_overview"]["status"] == "RUNNING"

        # 2. Market Snapshot
        assert "market_snapshot" in snapshot
        assert snapshot["market_snapshot"]["best_bid"] == 100
        assert snapshot["market_snapshot"]["best_ask"] == 105
        assert snapshot["market_snapshot"]["spread"] == 5

        # 3. Whale Metrics
        assert "whale_metrics" in snapshot
        assert "total_whales" in snapshot["whale_metrics"]

        # 4. Recent Activity
        assert "recent_activity" in snapshot
        assert isinstance(snapshot["recent_activity"], list)

        # 5. Engine Health
        assert "engine_health" in snapshot
        health = snapshot["engine_health"]
        assert health["matching_engine"] == "RUNNING"
        assert health["order_book"] == "ACTIVE"
        assert health["cython_available"] == CYTHON_CORE_AVAILABLE
        assert health["cython_mode"] == (CYTHON_CORE_AVAILABLE and engine.use_cython)


class TestFastAPIRoutes:
    """Integration tests for FastAPI endpoints."""

    def test_api_health_endpoint(self):
        client = TestClient(app)
        res = client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert "matching_engine" in body
        assert "cython_mode" in body

    def test_api_snapshot_endpoint(self):
        client = TestClient(app)
        res = client.get("/api/snapshot")
        assert res.status_code == 200
        body = res.json()
        assert "engine_overview" in body
        assert "market_snapshot" in body
        assert "whale_metrics" in body
        assert "recent_activity" in body
        assert "engine_health" in body

    def test_index_page_serves_html(self):
        client = TestClient(app)
        res = client.get("/")
        assert res.status_code == 200
        assert "ChronosMatch" in res.text
        assert "root" in res.text

