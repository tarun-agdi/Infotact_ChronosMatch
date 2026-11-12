
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
from chronosmatch.trade_store import TradeStore
from chronosmatch.trade_writer import TradeWriter

from src.chronosmatch.dashboard import CursesDashboard


async def run_pipeline(dashboard):

    # 1. Initialize the shared ring buffer
    lock = multiprocessing.Lock()

    ring_buffer = RingBuffer.create(
        filepath=Path("data/chronosmatch_buffer.bin"),
        capacity=1024,
        slot_size=ORDER_RECORD_SIZE,
        lock=lock,
    )

    # 2. Initialize the simulator and matching engine
    simulator = MarketSimulator(
        ring_buffer=ring_buffer,
        generation_interval=0.001,
    )

    engine = MatchingEngine()

    # 3. Initialize trade persistence components
    trade_store = TradeStore(
        db_path="data/trades.db"
    )

    trade_writer = TradeWriter(
        trade_store=trade_store,
        batch_size=100,
    )

    processed_orders = 0
    executed_trades = 0

    producer = None

    try:
        # 4. Start the asynchronous trade writer
        trade_writer.start()

        # 5. Start the order producer
        producer = asyncio.create_task(
            simulator.run_simulator(max_order=1000)
        )

        dashboard.update(status="RUNNING")

        # 6. Consume orders and process them
        while not producer.done() or not ring_buffer.is_empty():

            key = dashboard.get_key()

            if key in (ord("q"), ord("Q"), 3):
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

                # 7. Send executed trades to the background writer
                for trade in trades:

                    trade_writer.enqueue(trade)

                    # Update dashboard
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

            # Keep terminal responsive
            dashboard.refresh()
            await asyncio.sleep(0.05)

        # 8. Wait for the producer to finish
        await producer

        dashboard.update(status="COMPLETED")
        dashboard.refresh()

        # 9. Keep final results visible until user exits
        while True:

            key = dashboard.get_key()

            if key in (ord("q"), ord("Q"), 3):
                break

            dashboard.refresh()
            await asyncio.sleep(0.1)

    finally:

        # 10. Stop the producer
        simulator.stop()

        if producer is not None:
            if not producer.done():
                await producer
            else:
                # Retrieve any producer exception
                await producer

        # 11. Flush pending trades and stop the writer
        await trade_writer.stop()

        # 12. Close database and ring buffer
        trade_store.close()
        ring_buffer.close()


def main(stdscr):

    dashboard = CursesDashboard(stdscr)

    asyncio.run(run_pipeline(dashboard))


if __name__ == "__main__":
    curses.wrapper(main)
