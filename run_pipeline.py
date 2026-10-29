
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
from src.chronosmatch.dashboard import CursesDashboard


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
                # Measure matching-engine processing time
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

                dashboard.update(
                    orders=processed_orders,
                    trades=executed_trades,
                    latency_us=latency_us,
                )
            else:
                await asyncio.sleep(0.001)

            # Keep the terminal responsive
            dashboard.refresh()
            await asyncio.sleep(0.05)

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
    curses.wrapper(main)
