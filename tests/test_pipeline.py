
import asyncio
import multiprocessing

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order_codec import ORDER_RECORD_SIZE
from chronosmatch.simulator import MarketSimulator


def test_simulator_to_matching_engine(tmp_path):
    # Use a temporary file so the test doesn't affect real project data
    ring_buffer = RingBuffer.create(
        filepath=tmp_path / "test_buffer.bin",
        capacity=8,
        slot_size=ORDER_RECORD_SIZE,
        lock=multiprocessing.Lock(),
    )

    simulator = MarketSimulator(
        ring_buffer=ring_buffer,
        generation_interval=0,
    )
    engine = MatchingEngine()

    async def scenario():
        producer = asyncio.create_task(
            simulator.run_simulator(max_order=5)
        )
        processed = 0

        # Consume orders until generation finishes and the buffer is empty
        while not producer.done() or not ring_buffer.is_empty():
            order = ring_buffer.pop_order()

            if order is None:
                await asyncio.sleep(0.001)
                continue

            engine.process_order(order)
            processed += 1

        await producer

        assert processed == 5

    try:
        asyncio.run(scenario())
    finally:
        ring_buffer.close()
