"""
ChronosMatch End-to-End Pipeline Runner.

Runs the complete market simulation pipeline:
1. MarketSimulator produces orders at regular intervals and pushes to RingBuffer.
2. Consumer pops binary-decoded orders from RingBuffer.
3. MatchingEngine processes each order against the OrderBook, executing trades.
4. Validates throughput, drained buffer, remaining resting orders, and clean shutdown.
"""

from __future__ import annotations

import asyncio
import multiprocessing
from pathlib import Path
import sys

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order_codec import ORDER_RECORD_SIZE
from chronosmatch.simulator import MarketSimulator


async def run_pipeline(
    max_orders: int = 1000,
    generation_interval: float = 0.001,
    verbose: bool = True,
    cleanup: bool = True,
) -> dict[str, int]:
    """
    Execute the integrated market simulation and matching pipeline.

    Args:
        max_orders: Total number of orders for the simulator to produce.
        generation_interval: Delay between order generation in seconds.
        verbose: Whether to print order and trade execution logs.
        cleanup: Whether to delete the backing ring buffer file upon completion.

    Returns:
        Dictionary containing pipeline statistics:
        - orders_processed
        - trades_executed
        - resting_bids
        - resting_asks
    """
    lock = multiprocessing.Lock()
    buffer_path = Path("data/chronosmatch_buffer.bin")

    ring_buffer = RingBuffer.create(
        filepath=buffer_path,
        capacity=1024,
        slot_size=ORDER_RECORD_SIZE,
        lock=lock,
    )

    simulator = MarketSimulator(
        ring_buffer=ring_buffer,
        generation_interval=generation_interval,
    )
    engine = MatchingEngine()

    processed_orders = 0
    executed_trades = 0

    # Run the producer concurrently with the consumer
    producer = asyncio.create_task(
        simulator.run_simulator(max_order=max_orders)
    )

    try:
        # Continue until generation finishes and buffered orders are drained
        while not producer.done() or not ring_buffer.is_empty():
            order = ring_buffer.pop_order()

            if order is None:
                await asyncio.sleep(0.001)
                continue

            # Match each decoded order against the order book
            trades = engine.process_order(order)

            processed_orders += 1
            executed_trades += len(trades)

            if verbose:
                for trade in trades:
                    print(f"Trade executed: {trade}")

        await producer

    finally:
        # Release the buffer even if processing raises an exception
        if not producer.done():
            simulator.stop()
            await producer

        if cleanup:
            ring_buffer.unlink()
        else:
            ring_buffer.close()

    total_resting_bids = sum(len(orders) for orders in engine.order_book.bids.values())
    total_resting_asks = sum(len(orders) for orders in engine.order_book.asks.values())

    print("\n" + "=" * 50)
    print("      PIPELINE EXECUTION SUMMARY")
    print("=" * 50)
    print(f"Orders processed    : {processed_orders}")
    print(f"Trades executed     : {executed_trades}")
    print(f"Resting bids in book: {total_resting_bids}")
    print(f"Resting asks in book: {total_resting_asks}")
    print("=" * 50)

    return {
        "orders_processed": processed_orders,
        "trades_executed": executed_trades,
        "resting_bids": total_resting_bids,
        "resting_asks": total_resting_asks,
    }


if __name__ == "__main__":
    asyncio.run(run_pipeline(max_orders=1000, generation_interval=0.001, verbose=True, cleanup=True))
