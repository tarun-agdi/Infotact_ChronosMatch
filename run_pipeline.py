
import asyncio
import multiprocessing
from pathlib import Path

from src.chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order_codec import ORDER_RECORD_SIZE
from chronosmatch.simulator import MarketSimulator


async def run_pipeline() -> None:
    # Initialize shared IPC and matching components
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

    # Run the producer concurrently with the consumer
    producer = asyncio.create_task(
        simulator.run_simulator(max_order=1000)
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

            for trade in trades:
                print(f"Trade executed: {trade}")

        await producer

    finally:
        # Release the buffer even if processing raises an exception
        if not producer.done():
            simulator.stop()
            await producer

        ring_buffer.close()

    print(f"Orders processed: {processed_orders}")
    print(f"Trades executed: {executed_trades}")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
