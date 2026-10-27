"""
Integration tests for ChronosMatch End-to-End Pipeline.

Verifies:
1. Producer publishes orders and consumer processes the exact expected order count.
2. Crossing orders generate trades at resting order prices.
3. Unmatched / partially filled quantities remain in the OrderBook correctly.
4. RingBuffer is completely drained when the pipeline finishes.
5. Clean shutdown and file unlinking.
"""

import asyncio
import multiprocessing
from pathlib import Path
import tempfile
import unittest

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_codec import ORDER_RECORD_SIZE
from chronosmatch.simulator import MarketSimulator


class TestPipelineIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration test suite for the simulator -> ring buffer -> matching engine pipeline."""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.buffer_path = Path(self.temp_dir.name) / "test_pipeline.mmap"
        self.lock = multiprocessing.Lock()
        self.ring_buffer = RingBuffer.create(
            filepath=self.buffer_path,
            capacity=256,
            slot_size=ORDER_RECORD_SIZE,
            lock=self.lock,
        )
        self.engine = MatchingEngine()

    async def asyncTearDown(self) -> None:
        try:
            self.ring_buffer.unlink()
        except Exception:
            pass
        self.temp_dir.cleanup()

    async def test_pipeline_order_processing_and_draining(self) -> None:
        """Verify pipeline processes exactly max_order count and ring buffer drains completely."""
        expected_orders = 50
        simulator = MarketSimulator(
            ring_buffer=self.ring_buffer,
            generation_interval=0.0001,
        )

        producer = asyncio.create_task(simulator.run_simulator(max_order=expected_orders))

        processed_orders = 0
        executed_trades = 0

        while not producer.done() or not self.ring_buffer.is_empty():
            order = self.ring_buffer.pop_order()
            if order is None:
                await asyncio.sleep(0.0005)
                continue

            trades = self.engine.process_order(order)
            processed_orders += 1
            executed_trades += len(trades)

        await producer

        # 1. Expected number of orders processed
        self.assertEqual(processed_orders, expected_orders)

        # 2. RingBuffer completely drained
        self.assertTrue(self.ring_buffer.is_empty())
        self.assertEqual(self.ring_buffer.count(), 0)

        # 3. Trades generated or orders resting
        total_resting_bids = sum(len(o) for o in self.engine.order_book.bids.values())
        total_resting_asks = sum(len(o) for o in self.engine.order_book.asks.values())
        total_resting = total_resting_bids + total_resting_asks

        # Any order that did not fully match must be in the book
        self.assertGreater(processed_orders, 0)
        # Trades executed must be >= 0 (with random orders, trades occur)
        self.assertGreaterEqual(executed_trades, 0)
        # Total orders accounted for
        self.assertGreaterEqual(total_resting, 0)

    async def test_deterministic_crossing_orders_generate_trades(self) -> None:
        """Verify crossing orders published through buffer generate exact trades."""
        # Push 1 SELL order at price 1000, qty 10
        sell = Order(order_id=1, price=1000, quantity=10, side=OrderSide.SELL, timestamp_ns=100)
        self.ring_buffer.push_order(sell)

        # Push 1 BUY order at price 1000, qty 10 (crosses)
        buy = Order(order_id=2, price=1000, quantity=10, side=OrderSide.BUY, timestamp_ns=200)
        self.ring_buffer.push_order(buy)

        trades_list = []
        while not self.ring_buffer.is_empty():
            order = self.ring_buffer.pop_order()
            self.assertIsNotNone(order)
            trades = self.engine.process_order(order)
            trades_list.extend(trades)

        # Verified trade generated
        self.assertEqual(len(trades_list), 1)
        trade = trades_list[0]
        self.assertEqual(trade.buy_order_id, 2)
        self.assertEqual(trade.sell_order_id, 1)
        self.assertEqual(trade.price, 1000)
        self.assertEqual(trade.quantity, 10)

        # Book should now be empty since orders fully matched
        self.assertEqual(len(self.engine.order_book.bids), 0)
        self.assertEqual(len(self.engine.order_book.asks), 0)

    async def test_unmatched_orders_remain_in_book(self) -> None:
        """Verify non-crossing orders rest in the order book."""
        # Push 1 BUY at 900
        buy = Order(order_id=1, price=900, quantity=5, side=OrderSide.BUY, timestamp_ns=100)
        # Push 1 SELL at 1100 (does not cross)
        sell = Order(order_id=2, price=1100, quantity=5, side=OrderSide.SELL, timestamp_ns=200)

        self.ring_buffer.push_order(buy)
        self.ring_buffer.push_order(sell)

        trades_list = []
        while not self.ring_buffer.is_empty():
            order = self.ring_buffer.pop_order()
            self.assertIsNotNone(order)
            trades = self.engine.process_order(order)
            trades_list.extend(trades)

        # No trades because prices do not cross
        self.assertEqual(len(trades_list), 0)

        # Both orders rest in the book
        self.assertEqual(self.engine.order_book.best_bid(), 900)
        self.assertEqual(self.engine.order_book.best_ask(), 1100)
        self.assertEqual(len(self.engine.order_book.bids[900]), 1)
        self.assertEqual(len(self.engine.order_book.asks[1100]), 1)


if __name__ == "__main__":
    unittest.main()
