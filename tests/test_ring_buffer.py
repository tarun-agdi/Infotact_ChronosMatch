"""
Unit tests for the shared-memory RingBuffer IPC module.
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
import struct
import tempfile
import unittest

from chronosmatch.ipc.ring_buffer import (
    HEADER_SIZE,
    MAGIC,
    RingBuffer,
    UINT64_MAX,
)
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_codec import ORDER_RECORD_SIZE


# Top-level helper functions for cross-process concurrency tests (required for Windows spawn)
def _concurrency_producer(
    filepath: str,
    lock: multiprocessing.synchronize.Lock,
    count: int,
) -> None:
    rb = RingBuffer.open(filepath, lock=lock)
    try:
        for i in range(1, count + 1):
            order = Order(
                order_id=i,
                price=1000 + i,
                quantity=10 + (i % 5),
                side=OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL,
                timestamp_ns=1_700_000_000_000_000_000 + i,
            )
            while not rb.push_order(order):
                pass  # Buffer full, spin until space is available
    finally:
        rb.close()


def _concurrency_consumer(
    filepath: str,
    lock: multiprocessing.synchronize.Lock,
    count: int,
    result_queue: multiprocessing.Queue,
) -> None:
    rb = RingBuffer.open(filepath, lock=lock)
    received_order_ids = []
    try:
        while len(received_order_ids) < count:
            order = rb.pop_order()
            if order is not None:
                received_order_ids.append(order.order_id)
        result_queue.put(received_order_ids)
    except Exception as exc:
        result_queue.put(exc)
    finally:
        rb.close()


class TestRingBuffer(unittest.TestCase):
    """Test suite verifying RingBuffer lifecycle, FIFO ordering, wraparound, and concurrency."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.test_file = self.temp_path / "test_ring_buffer.bin"
        self.shared_lock = multiprocessing.Lock()

    def tearDown(self) -> None:
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def test_require_shared_lock(self) -> None:
        """Verify that passing lock=None raises TypeError in create and open."""
        with self.assertRaises(TypeError):
            RingBuffer.create(self.test_file, capacity=10, lock=None)

        # Create valid buffer first
        rb = RingBuffer.create(self.test_file, capacity=10, lock=self.shared_lock)
        rb.close()

        with self.assertRaises(TypeError):
            RingBuffer.open(self.test_file, lock=None)

    def test_create_and_validate_header(self) -> None:
        """Verify initial header creation values and initial state."""
        with RingBuffer.create(
            self.test_file, capacity=8, slot_size=33, lock=self.shared_lock
        ) as rb:
            self.assertEqual(rb.capacity, 8)
            self.assertEqual(rb.slot_size, 33)
            self.assertTrue(rb.is_empty())
            self.assertFalse(rb.is_full())
            self.assertEqual(rb.count(), 0)
            self.assertEqual(rb.write_seq, 0)
            self.assertEqual(rb.read_seq, 0)

        # Verify physical file size
        expected_size = HEADER_SIZE + (8 * 33)
        self.assertEqual(self.test_file.stat().st_size, expected_size)

    def test_reject_invalid_creation_arguments(self) -> None:
        """Verify validation of capacity and slot_size during creation."""
        with self.assertRaises(ValueError):
            RingBuffer.create(self.test_file, capacity=0, lock=self.shared_lock)

        with self.assertRaises(ValueError):
            RingBuffer.create(self.test_file, capacity=-5, lock=self.shared_lock)

        with self.assertRaises(TypeError):
            RingBuffer.create(self.test_file, capacity="10", lock=self.shared_lock)  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            RingBuffer.create(self.test_file, capacity=10, slot_size=0, lock=self.shared_lock)

    def test_open_validates_existing_header(self) -> None:
        """Verify that RingBuffer.open successfully reconstructs existing buffer metadata."""
        rb_created = RingBuffer.create(
            self.test_file, capacity=16, slot_size=33, lock=self.shared_lock
        )
        test_payload = b"A" * 33
        self.assertTrue(rb_created.write(test_payload))
        rb_created.close()

        # Reopen
        with RingBuffer.open(self.test_file, lock=self.shared_lock) as rb_opened:
            self.assertEqual(rb_opened.capacity, 16)
            self.assertEqual(rb_opened.slot_size, 33)
            self.assertEqual(rb_opened.count(), 1)
            self.assertFalse(rb_opened.is_empty())
            self.assertEqual(rb_opened.read(), test_payload)
            self.assertTrue(rb_opened.is_empty())

    def test_open_rejects_missing_file(self) -> None:
        """Verify FileNotFoundError if attempting to open a non-existent file."""
        non_existent = self.temp_path / "does_not_exist.bin"
        with self.assertRaises(FileNotFoundError):
            RingBuffer.open(non_existent, lock=self.shared_lock)

    def test_open_rejects_corrupted_headers(self) -> None:
        """Verify rejection when magic, version, size, or sequences are invalid."""
        # 1. Truncated file smaller than HEADER_SIZE
        with open(self.test_file, "wb") as f:
            f.write(b"CMRB" + b"\x00" * 10)  # 14 bytes (< 64 bytes)
        with self.assertRaises(ValueError):
            RingBuffer.open(self.test_file, lock=self.shared_lock)

        # 2. Corrupt magic bytes
        with open(self.test_file, "wb") as f:
            bad_header = struct.pack(">4sIIIQQ32s", b"BADM", 1, 4, 33, 0, 0, b"\x00" * 32)
            f.write(bad_header + (b"\x00" * (4 * 33)))
        with self.assertRaises(ValueError) as ctx:
            RingBuffer.open(self.test_file, lock=self.shared_lock)
        self.assertIn("Invalid ring buffer magic", str(ctx.exception))

        # 3. Unsupported version
        with open(self.test_file, "wb") as f:
            bad_version_header = struct.pack(
                ">4sIIIQQ32s", MAGIC, 999, 4, 33, 0, 0, b"\x00" * 32
            )
            f.write(bad_version_header + (b"\x00" * (4 * 33)))
        with self.assertRaises(ValueError) as ctx:
            RingBuffer.open(self.test_file, lock=self.shared_lock)
        self.assertIn("Unsupported ring buffer version", str(ctx.exception))

        # 4. Inverted sequence counters (write_seq < read_seq)
        with open(self.test_file, "wb") as f:
            inverted_header = struct.pack(
                ">4sIIIQQ32s", MAGIC, 1, 4, 33, 2, 5, b"\x00" * 32
            )
            f.write(inverted_header + (b"\x00" * (4 * 33)))
        with self.assertRaises(ValueError) as ctx:
            RingBuffer.open(self.test_file, lock=self.shared_lock)
        self.assertIn("write_seq (2) < read_seq (5)", str(ctx.exception))

        # 5. File size mismatch (file truncated after header)
        with open(self.test_file, "wb") as f:
            valid_header = struct.pack(">4sIIIQQ32s", MAGIC, 1, 4, 33, 0, 0, b"\x00" * 32)
            f.write(valid_header + (b"\x00" * 10))  # Expected 4 * 33 = 132 bytes
        with self.assertRaises(ValueError) as ctx:
            RingBuffer.open(self.test_file, lock=self.shared_lock)
        self.assertIn("File size mismatch", str(ctx.exception))

    def test_write_and_read_single_slot(self) -> None:
        """Verify writing and reading a single slot produces an exact match."""
        slot_data = b"X" * 33
        with RingBuffer.create(
            self.test_file, capacity=4, slot_size=33, lock=self.shared_lock
        ) as rb:
            self.assertTrue(rb.write(slot_data))
            self.assertEqual(rb.count(), 1)
            self.assertFalse(rb.is_empty())
            self.assertFalse(rb.is_full())

            received = rb.read()
            self.assertEqual(received, slot_data)
            self.assertTrue(rb.is_empty())
            self.assertEqual(rb.count(), 0)

    def test_fifo_ordering_multiple_slots(self) -> None:
        """Verify multiple written records are retrieved in strict FIFO sequence."""
        capacity = 5
        records = [f"Record_{i:04d}".encode("ascii").ljust(33, b"\x00") for i in range(capacity)]

        with RingBuffer.create(
            self.test_file, capacity=capacity, slot_size=33, lock=self.shared_lock
        ) as rb:
            for rec in records:
                self.assertTrue(rb.write(rec))

            self.assertTrue(rb.is_full())
            self.assertEqual(rb.count(), capacity)

            for rec in records:
                self.assertEqual(rb.read(), rec)

            self.assertTrue(rb.is_empty())
            self.assertEqual(rb.count(), 0)

    def test_full_and_empty_boundaries(self) -> None:
        """Verify behavior when reading from an empty buffer or writing to a full buffer."""
        with RingBuffer.create(
            self.test_file, capacity=2, slot_size=33, lock=self.shared_lock
        ) as rb:
            # Empty read returns None
            self.assertIsNone(rb.read())

            rec1 = b"1" * 33
            rec2 = b"2" * 33
            rec3 = b"3" * 33

            self.assertTrue(rb.write(rec1))
            self.assertTrue(rb.write(rec2))
            self.assertTrue(rb.is_full())

            # Full write returns False without advancing write_seq
            self.assertFalse(rb.write(rec3))
            self.assertEqual(rb.write_seq, 2)
            self.assertEqual(rb.count(), 2)

            # Read one item: buffer now allows one write
            self.assertEqual(rb.read(), rec1)
            self.assertFalse(rb.is_full())
            self.assertEqual(rb.count(), 1)

            # Now write rec3 succeeds
            self.assertTrue(rb.write(rec3))
            self.assertTrue(rb.is_full())

            # Verify contents are rec2, rec3
            self.assertEqual(rb.read(), rec2)
            self.assertEqual(rb.read(), rec3)
            self.assertIsNone(rb.read())

    def test_wraparound_across_multiple_cycles(self) -> None:
        """Verify correct circular wraparound over many iterations with a small capacity."""
        capacity = 3
        iterations = 30  # 10 full loops around the ring
        with RingBuffer.create(
            self.test_file, capacity=capacity, slot_size=33, lock=self.shared_lock
        ) as rb:
            for i in range(iterations):
                payload = f"msg_{i:04d}".encode("ascii").ljust(33, b"\x00")
                self.assertTrue(rb.write(payload))
                received = rb.read()
                self.assertEqual(received, payload)

            self.assertEqual(rb.write_seq, iterations)
            self.assertEqual(rb.read_seq, iterations)
            self.assertTrue(rb.is_empty())

    def test_write_validation_types_and_lengths(self) -> None:
        """Verify type and length checks on write."""
        with RingBuffer.create(
            self.test_file, capacity=4, slot_size=33, lock=self.shared_lock
        ) as rb:
            # Bad types
            with self.assertRaises(TypeError):
                rb.write(None)  # type: ignore[arg-type]
            with self.assertRaises(TypeError):
                rb.write("not-bytes")  # type: ignore[arg-type]
            with self.assertRaises(TypeError):
                rb.write(12345)  # type: ignore[arg-type]

            # Short bytes (< 33 bytes)
            with self.assertRaises(ValueError):
                rb.write(b"short")

            # Long bytes (> 33 bytes)
            with self.assertRaises(ValueError):
                rb.write(b"A" * 34)

            # Accept bytearray and memoryview of correct length
            self.assertTrue(rb.write(bytearray(b"B" * 33)))
            self.assertEqual(rb.read(), b"B" * 33)

            view = memoryview(b"C" * 33)
            self.assertTrue(rb.write(view))
            self.assertEqual(rb.read(), b"C" * 33)

    def test_sequence_counter_64bit_overflow_validation(self) -> None:
        """Verify OverflowError is raised if sequence counters reach UINT64_MAX."""
        with RingBuffer.create(
            self.test_file, capacity=4, slot_size=33, lock=self.shared_lock
        ) as rb:
            # Artificially set write_seq to UINT64_MAX in header to simulate boundary
            assert rb._mmap is not None
            struct.pack_into(">Q", rb._mmap, 16, UINT64_MAX)
            struct.pack_into(">Q", rb._mmap, 24, UINT64_MAX - 1)

            with self.assertRaises(OverflowError) as ctx:
                rb.write(b"A" * 33)
            self.assertIn("write_seq has reached maximum 64-bit unsigned limit", str(ctx.exception))

            # Set read_seq to UINT64_MAX
            struct.pack_into(">Q", rb._mmap, 24, UINT64_MAX)
            with self.assertRaises(OverflowError) as ctx:
                rb.read()
            self.assertIn("read_seq has reached maximum 64-bit unsigned limit", str(ctx.exception))

    def test_order_codec_push_and_pop_integration(self) -> None:
        """Verify end-to-end integration with Order and order_codec."""
        orders = [
            Order(
                order_id=1,
                price=50000,
                quantity=100,
                side=OrderSide.BUY,
                timestamp_ns=1_700_000_000_100_000_000,
            ),
            Order(
                order_id=2,
                price=50050,
                quantity=200,
                side=OrderSide.SELL,
                timestamp_ns=1_700_000_000_200_000_000,
            ),
        ]

        with RingBuffer.create(
            self.test_file, capacity=4, slot_size=ORDER_RECORD_SIZE, lock=self.shared_lock
        ) as rb:
            for ord_item in orders:
                self.assertTrue(rb.push_order(ord_item))

            self.assertEqual(rb.count(), 2)

            popped_1 = rb.pop_order()
            self.assertEqual(popped_1, orders[0])

            popped_2 = rb.pop_order()
            self.assertEqual(popped_2, orders[1])

            self.assertIsNone(rb.pop_order())

    def test_push_order_rejects_non_order_type(self) -> None:
        """Verify TypeError if passing a non-Order object to push_order."""
        with RingBuffer.create(
            self.test_file, capacity=4, slot_size=ORDER_RECORD_SIZE, lock=self.shared_lock
        ) as rb:
            with self.assertRaises(TypeError):
                rb.push_order("invalid_order")  # type: ignore[arg-type]

    def test_lifecycle_closed_operations_and_unlink(self) -> None:
        """Verify that operations after close raise ValueError, and unlink removes file."""
        rb = RingBuffer.create(
            self.test_file, capacity=4, slot_size=33, lock=self.shared_lock
        )
        self.assertTrue(self.test_file.exists())
        rb.close()

        with self.assertRaises(ValueError):
            rb.write(b"A" * 33)

        with self.assertRaises(ValueError):
            rb.read()

        with self.assertRaises(ValueError):
            rb.is_empty()

        # Unlink test
        rb_unlink = RingBuffer.create(
            self.test_file, capacity=4, slot_size=33, lock=self.shared_lock
        )
        self.assertTrue(self.test_file.exists())
        rb_unlink.unlink()
        self.assertFalse(self.test_file.exists())

    def test_multiprocess_concurrency(self) -> None:
        """Verify cross-process concurrent producer and consumer via shared lock."""
        count = 100
        capacity = 16  # Force multiple wraparounds (100 orders into 16-slot buffer)

        rb = RingBuffer.create(
            self.test_file, capacity=capacity, slot_size=ORDER_RECORD_SIZE, lock=self.shared_lock
        )
        rb.close()

        result_queue: multiprocessing.Queue = multiprocessing.Queue()

        producer_process = multiprocessing.Process(
            target=_concurrency_producer,
            args=(str(self.test_file), self.shared_lock, count),
        )
        consumer_process = multiprocessing.Process(
            target=_concurrency_consumer,
            args=(str(self.test_file), self.shared_lock, count, result_queue),
        )

        consumer_process.start()
        producer_process.start()

        producer_process.join(timeout=10)
        consumer_process.join(timeout=10)

        self.assertFalse(producer_process.is_alive(), "Producer timed out")
        self.assertFalse(consumer_process.is_alive(), "Consumer timed out")

        results = result_queue.get(timeout=5)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), count)
        expected_ids = list(range(1, count + 1))
        self.assertEqual(results, expected_ids)


if __name__ == "__main__":
    unittest.main()
