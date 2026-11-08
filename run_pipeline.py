
import asyncio
import curses
import multiprocessing
import time
from datetime import datetime
from pathlib import Path

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order_codec import ORDER_RECORD_SIZE
from chronosmatch.simulator import MarketSimulator
from chronosmatch.dashboard import CursesDashboard
from chronosmatch.whale_detector import detect_whale


async def run_pipeline(dashboard):
    # Initialize the shared ring buffer
    lock = multiprocessing.Lock()
    ring_buffer = RingBuffer.create(
        filepath=Path("data/chronosmatch_buffer.bin"),
        capacity=1024,
        slot_size=ORDER_RECORD_SIZE,
        lock=lock,
    )

    simulator = MarketSimulator(
        ring_buffer=ring_buffer,
        generation_interval=0.001,
    )
    engine = MatchingEngine()
    if hasattr(dashboard, "engine"):
        dashboard.engine = engine

    processed_orders = 0
    executed_trades = 0
    stopping = False

    # Start the order producer
    producer = asyncio.create_task(
        simulator.run_simulator(max_order=1000)
    )
    dashboard.update(status="RUNNING")

    try:
        # Consume orders and update the dashboard
        while not producer.done() or not ring_buffer.is_empty():
            key = dashboard.get_key()

            if key in (ord("q"), ord("Q"), 3):
                stopping = True
                simulator.stop()
                dashboard.update(status="STOPPING")

            order = ring_buffer.pop_order()

            if order is not None:
                # Measure matching-engine processing time synchronously
                start_ns = time.perf_counter_ns()
                trades = engine.process_order(order)
                latency_us = (
                    time.perf_counter_ns() - start_ns
                ) / 1000

                processed_orders += 1
                executed_trades += len(trades)

                # Show actual executions in the trade table
                for trade in trades:
                    dashboard.add_trade({
                        "time": datetime.fromtimestamp(
                            trade.timestamp_ns / 1_000_000_000
                        ).strftime("%H:%M:%S"),
                        "symbol": (
                            f"{trade.buy_order_id}/"
                            f"{trade.sell_order_id}"
                        ),
                        "side": "MATCH",
                        "price": trade.price,
                        "quantity": trade.quantity,
                    })

                # Detect whale orders across swept price levels
                whale = detect_whale(order, trades)
                if whale is not None and hasattr(dashboard, "add_whale"):
                    dashboard.add_whale(whale)

                dashboard.update(
                    orders=processed_orders,
                    trades=executed_trades,
                    latency_us=latency_us,
                    best_bid=engine.order_book.best_bid(),
                    best_ask=engine.order_book.best_ask(),
                )

                # Periodically yield control cooperatively between order batches
                if processed_orders % 50 == 0:
                    dashboard.refresh()
                    await asyncio.sleep(0)
            else:
                dashboard.refresh()
                await asyncio.sleep(0.001)

        await producer

        dashboard.update(status="COMPLETED")
        dashboard.refresh()

        # Keep the final results visible until the user exits
        while True:
            key = dashboard.get_key()
            if key in (ord("q"), ord("Q"), 3):
                break
            dashboard.refresh()
            await asyncio.sleep(0.1)

    finally:
        # Stop the producer and release the ring buffer
        simulator.stop()

        if not producer.done():
            await producer

        ring_buffer.close()


def main(stdscr):
    # Start the curses interface and pipeline together
    dashboard = CursesDashboard(stdscr)
    asyncio.run(run_pipeline(dashboard))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ChronosMatch Pipeline Runner")
    parser.add_argument("--web", action="store_true", help="Launch browser-based operations console")
    parser.add_argument("--host", default="127.0.0.1", help="Host address for web console (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port for web console (default: 8000)")
    args = parser.parse_args()

    if args.web:
        from chronosmatch.web_dashboard import start_web_pipeline
        start_web_pipeline(host=args.host, port=args.port)
    else:
        curses.wrapper(main)
