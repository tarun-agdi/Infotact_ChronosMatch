"""
Web-based Operations Console for ChronosMatch.

Provides a non-blocking WebDashboard adapter, FastAPI REST API, and WebSocket
broadcaster for real-time engine monitoring, order book snapshots, and whale alerts.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any, Sequence

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from chronosmatch.matching_engine import CYTHON_CORE_AVAILABLE, MatchingEngine
from chronosmatch.order import OrderSide
from chronosmatch.whale_detector import WhaleOrder

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


class WebDashboard:
    """Dashboard adapter that collects metrics and streams them via WebSocket."""

    def __init__(self, engine: MatchingEngine | None = None) -> None:
        self.orders = 0
        self.trades = 0
        self.whales = 0
        self.status = "STARTING"
        self.latency_us: float | None = None
        self.best_bid: int | None = None
        self.best_ask: int | None = None
        self.start_time = time.monotonic()

        self.last_rate_time = time.monotonic()
        self.last_rate_orders = 0
        self.orders_per_sec = 0.0

        self.recent_trades: deque[dict[str, Any]] = deque(maxlen=50)
        self.recent_whales: deque[dict[str, Any]] = deque(maxlen=50)
        self.active_connections: list[WebSocket] = []
        self.stopping = False
        self.engine = engine

    def update(
        self,
        orders: int | None = None,
        trades: int | None = None,
        status: str | None = None,
        latency_us: float | None = None,
        best_bid: int | None = None,
        best_ask: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Update metrics in memory. Lightweight assignment without I/O."""
        if orders is not None:
            self.orders = max(0, orders)
        if trades is not None:
            self.trades = max(0, trades)
        if status is not None:
            self.status = status
        if latency_us is not None:
            self.latency_us = latency_us
        if best_bid is not None or "best_bid" in kwargs:
            self.best_bid = best_bid
        if best_ask is not None or "best_ask" in kwargs:
            self.best_ask = best_ask

    def add_trade(self, trade: dict[str, Any] | Any) -> None:
        """Record trade execution in reverse-chronological order."""
        if isinstance(trade, dict):
            entry = {
                "time": trade.get("time", datetime.now().strftime("%H:%M:%S")),
                "symbol": trade.get("symbol", "N/A"),
                "side": trade.get("side", "MATCH"),
                "price": trade.get("price", 0),
                "quantity": trade.get("quantity", trade.get("qty", 0)),
                "type": "TRADE",
            }
        else:
            entry = {"text": str(trade), "type": "TRADE"}
        self.recent_trades.appendleft(entry)

    def add_whale(self, whale: WhaleOrder) -> None:
        """Record detected whale alert with full execution breakdown."""
        self.whales += 1
        side_label = "BUY" if whale.side == OrderSide.BUY else "SELL"
        ts_str = datetime.fromtimestamp(whale.timestamp_ns / 1_000_000_000).strftime("%H:%M:%S")

        trade_breakdown = [
            {
                "buy_order_id": t.buy_order_id,
                "sell_order_id": t.sell_order_id,
                "price": t.price,
                "quantity": t.quantity,
            }
            for t in whale.trades
        ]

        whale_data = {
            "order_id": whale.order_id,
            "side": side_label,
            "levels_swept": whale.levels_swept,
            "execution_prices": list(whale.execution_prices),
            "total_quantity": whale.total_quantity,
            "timestamp": ts_str,
            "timestamp_ns": whale.timestamp_ns,
            "is_partial": whale.is_partial,
            "trade_count": len(whale.trades),
            "trades": trade_breakdown,
        }
        self.recent_whales.appendleft(whale_data)

        # Distinguishable feed item
        self.recent_trades.appendleft({
            "time": ts_str,
            "symbol": f"#{whale.order_id}",
            "side": side_label,
            "price": f"{min(whale.execution_prices)}-{max(whale.execution_prices)}",
            "quantity": whale.total_quantity,
            "type": "WHALE_ALERT",
            "details": f"Swept {whale.levels_swept} levels ({'Partial' if whale.is_partial else 'Full'})",
        })

    def get_key(self) -> int:
        """Non-blocking keyboard check for pipeline runner."""
        return 3 if self.stopping else -1

    def refresh(self) -> None:
        """Update throughput rate calculations."""
        now = time.monotonic()
        elapsed = now - self.last_rate_time
        if elapsed >= 1.0:
            new_orders = max(0, self.orders - self.last_rate_orders)
            self.orders_per_sec = new_orders / elapsed
            self.last_rate_orders = self.orders
            self.last_rate_time = now

    def get_snapshot(self) -> dict[str, Any]:
        """Produce the comprehensive operational snapshot."""
        self.refresh()
        spread = (
            (self.best_ask - self.best_bid)
            if (self.best_bid is not None and self.best_ask is not None)
            else None
        )

        cython_active = bool(
            self.engine and getattr(self.engine, "use_cython", False) and CYTHON_CORE_AVAILABLE
        )

        bids_levels = 0
        asks_levels = 0
        if self.engine and hasattr(self.engine, "order_book"):
            bids_levels = len(self.engine.order_book.bids)
            asks_levels = len(self.engine.order_book.asks)

        return {
            "engine_overview": {
                "orders": self.orders,
                "trades": self.trades,
                "orders_per_sec": round(self.orders_per_sec, 1),
                "latency_us": round(self.latency_us, 2) if self.latency_us is not None else None,
                "uptime_seconds": int(time.monotonic() - self.start_time),
                "status": self.status,
            },
            "market_snapshot": {
                "best_bid": self.best_bid,
                "best_ask": self.best_ask,
                "spread": spread,
                "bids_levels": bids_levels,
                "asks_levels": asks_levels,
            },
            "whale_metrics": {
                "total_whales": self.whales,
                "recent_whales": list(self.recent_whales),
            },
            "recent_activity": list(self.recent_trades),
            "engine_health": {
                "matching_engine": self.status,
                "order_book": "ACTIVE" if (bids_levels > 0 or asks_levels > 0 or self.orders > 0) else "READY",
                "cython_mode": cython_active,
                "cython_available": CYTHON_CORE_AVAILABLE,
            },
        }

    async def broadcast_loop(self, interval: float = 0.1) -> None:
        """Periodically broadcast snapshots over WebSocket to active clients."""
        while not self.stopping:
            await asyncio.sleep(interval)
            if not self.active_connections:
                continue

            payload = json.dumps(self.get_snapshot())
            to_remove: list[WebSocket] = []
            for ws in self.active_connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    to_remove.append(ws)

            for ws in to_remove:
                if ws in self.active_connections:
                    self.active_connections.remove(ws)


# Global dashboard instance for FastAPI routing
dashboard_instance = WebDashboard()

app = FastAPI(title="ChronosMatch Operations Console")

if (WEB_DIR).exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/", response_class=FileResponse)
async def get_index() -> FileResponse:
    index_path = WEB_DIR / "index.html"
    return FileResponse(index_path)


@app.get("/api/health")
async def get_health() -> JSONResponse:
    snapshot = dashboard_instance.get_snapshot()
    return JSONResponse(snapshot["engine_health"])


@app.get("/api/snapshot")
async def get_snapshot() -> JSONResponse:
    return JSONResponse(dashboard_instance.get_snapshot())


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await websocket.accept()
    dashboard_instance.active_connections.append(websocket)
    try:
        # Send initial snapshot immediately
        await websocket.send_text(json.dumps(dashboard_instance.get_snapshot()))
        while True:
            # Keep connection open; clients can send ping or commands
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in dashboard_instance.active_connections:
            dashboard_instance.active_connections.remove(websocket)


def start_web_pipeline(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run pipeline and web dashboard concurrently on the same asyncio loop."""
    import uvicorn
    from run_pipeline import run_pipeline

    async def _runner() -> None:
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)

        # Run pipeline, uvicorn server, and broadcast loop concurrently
        pipeline_task = asyncio.create_task(run_pipeline(dashboard_instance))
        server_task = asyncio.create_task(server.serve())
        broadcast_task = asyncio.create_task(dashboard_instance.broadcast_loop())

        print(f"\n=======================================================")
        print(f" ChronosMatch Operations Console Active")
        print(f" Access URL: http://{host}:{port}")
        print(f" Mode      : Pipeline + WebSocket Telemetry")
        print(f"=======================================================\n")

        await asyncio.gather(pipeline_task, server_task, broadcast_task, return_exceptions=True)

    asyncio.run(_runner())

