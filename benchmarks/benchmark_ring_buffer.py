"""
Benchmark script for the ChronosMatch shared-memory RingBuffer.

This script measures real-world throughput and latency across three distinct scenarios:
1. Raw Buffer: 100,000 write/read cycles using 33-byte payloads.
2. Order-Level: 100,000 orders serialized, pushed, popped, and deserialized.
3. Multiprocess IPC: 50,000 orders transferred concurrently between separate producer
   and consumer processes via the shared multiprocessing.Lock.

Metrics:
- Elapsed Time: Total wall-clock time taken by the timed measurement using time.perf_counter().
- Throughput: Number of operations/orders completed per second.
- Average Latency: Average time taken per operation/order in microseconds (μs).
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
import platform
import sys
import tempfile
import time
from typing import Final

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_codec import ORDER_RECORD_SIZE

BUFFER_CAPACITY: Final[int] = 1024
RAW_CYCLES: Final[int] = 100_000
ORDER_COUNT: Final[int] = 100_000
IPC_ORDER_COUNT: Final[int] = 50_000
WARMUP_CYCLES: Final[int] = 5_000


# ---------------------------------------------------------------------------
# Multiprocessing Worker Functions (must be top-level for Windows spawn)
# ---------------------------------------------------------------------------

def _ipc_producer_worker(
    filepath: str,
    lock: multiprocessing.synchronize.Lock,
    count: int,
    ready_event: multiprocessing.Event,
    start_event: multiprocessing.Event,
    error_queue: multiprocessing.Queue,
) -> None:
    """Producer process pushing sequential orders into the shared RingBuffer."""
    try:
        rb = RingBuffer.open(filepath, lock=lock)
    except Exception as exc:
        error_queue.put(f"Producer failed to open RingBuffer: {exc}")
        return

    ready_event.set()
    start_event.wait()

    try:
        for i in range(1, count + 1):
            order = Order(
                order_id=i,
                price=25000,
                quantity=10,
                side=OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL,
                timestamp_ns=1_700_000_000_000_000_000 + i,
            )
            # Push order, yielding if the buffer is temporarily full
            while not rb.push_order(order):
                time.sleep(0)
    except Exception as exc:
        error_queue.put(f"Producer exception at order {i}: {exc}")
    finally:
        rb.close()


def _ipc_consumer_worker(
    filepath: str,
    lock: multiprocessing.synchronize.Lock,
    count: int,
    ready_event: multiprocessing.Event,
    start_event: multiprocessing.Event,
    error_queue: multiprocessing.Queue,
) -> None:
    """Consumer process reading and validating sequential orders from the shared RingBuffer."""
    try:
        rb = RingBuffer.open(filepath, lock=lock)
    except Exception as exc:
        error_queue.put(f"Consumer failed to open RingBuffer: {exc}")
        return

    ready_event.set()
    start_event.wait()

    received = 0
    expected_order_id = 1

    try:
        while received < count:
            order = rb.pop_order()
            if order is None:
                # Buffer empty, yield briefly to let producer push
                time.sleep(0)
                continue

            if order.order_id != expected_order_id:
                error_queue.put(
                    f"Consumer sequence error: expected order_id {expected_order_id}, got {order.order_id}"
                )
                return

            received += 1
            expected_order_id += 1

        error_queue.put(None)  # Success signal
    except Exception as exc:
        error_queue.put(f"Consumer exception after {received} orders: {exc}")
    finally:
        rb.close()


# ---------------------------------------------------------------------------
# Benchmark Scenarios
# ---------------------------------------------------------------------------

def run_raw_buffer_benchmark(temp_dir: Path) -> dict[str, float]:
    """
    Benchmark raw 33-byte slot write and read performance in a single process.
    """
    backing_file = temp_dir / "raw_bench.bin"
    shared_lock = multiprocessing.Lock()
    payload = b"X" * ORDER_RECORD_SIZE

    rb = RingBuffer.create(
        backing_file, capacity=BUFFER_CAPACITY, slot_size=ORDER_RECORD_SIZE, lock=shared_lock
    )

    try:
        # Warm-up phase (unmeasured)
        for _ in range(WARMUP_CYCLES):
            rb.write(payload)
            rb.read()

        # Timed measurement: 100,000 write/read round trips
        start_time = time.perf_counter()
        for _ in range(RAW_CYCLES):
            if not rb.write(payload):
                raise RuntimeError("Unexpected write failure in raw benchmark")
            rec = rb.read()
            if rec != payload:
                raise RuntimeError("Payload mismatch in raw benchmark")
        end_time = time.perf_counter()

    finally:
        rb.unlink()

    elapsed = end_time - start_time
    total_ops = RAW_CYCLES * 2  # 1 write + 1 read per cycle
    cycle_throughput = RAW_CYCLES / elapsed
    op_throughput = total_ops / elapsed
    latency_us_per_cycle = (elapsed * 1_000_000) / RAW_CYCLES
    latency_us_per_op = (elapsed * 1_000_000) / total_ops

    return {
        "elapsed": elapsed,
        "cycles": RAW_CYCLES,
        "total_ops": total_ops,
        "cycle_throughput": cycle_throughput,
        "op_throughput": op_throughput,
        "latency_us_cycle": latency_us_per_cycle,
        "latency_us_op": latency_us_per_op,
    }


def run_order_benchmark(temp_dir: Path) -> dict[str, float]:
    """
    Benchmark end-to-end Order serialization, push, pop, and deserialization.
    """
    backing_file = temp_dir / "order_bench.bin"
    shared_lock = multiprocessing.Lock()

    rb = RingBuffer.create(
        backing_file, capacity=BUFFER_CAPACITY, slot_size=ORDER_RECORD_SIZE, lock=shared_lock
    )

    sample_order = Order(
        order_id=1,
        price=25000,
        quantity=50,
        side=OrderSide.BUY,
        timestamp_ns=1_700_000_000_123_456_789,
    )

    try:
        # Warm-up phase (unmeasured)
        for _ in range(WARMUP_CYCLES):
            rb.push_order(sample_order)
            rb.pop_order()

        # Timed measurement: 100,000 orders
        start_time = time.perf_counter()
        for i in range(1, ORDER_COUNT + 1):
            order = Order(
                order_id=i,
                price=25000,
                quantity=10,
                side=OrderSide.BUY,
                timestamp_ns=1_700_000_000_000_000_000 + i,
            )
            if not rb.push_order(order):
                raise RuntimeError(f"Unexpected push_order failure at order {i}")
            popped = rb.pop_order()
            if popped is None or popped.order_id != i:
                raise RuntimeError(f"Order verification failure at order {i}")
        end_time = time.perf_counter()

    finally:
        rb.unlink()

    elapsed = end_time - start_time
    throughput = ORDER_COUNT / elapsed
    latency_us = (elapsed * 1_000_000) / ORDER_COUNT

    return {
        "elapsed": elapsed,
        "orders": ORDER_COUNT,
        "throughput": throughput,
        "latency_us": latency_us,
    }


def run_ipc_multiprocess_benchmark(temp_dir: Path) -> dict[str, float]:
    """
    Benchmark cross-process order transfer between Producer and Consumer processes.
    """
    backing_file = temp_dir / "ipc_bench.bin"
    shared_lock = multiprocessing.Lock()

    # Pre-create the ring buffer backing file
    rb = RingBuffer.create(
        backing_file, capacity=BUFFER_CAPACITY, slot_size=ORDER_RECORD_SIZE, lock=shared_lock
    )
    rb.close()

    producer_ready = multiprocessing.Event()
    consumer_ready = multiprocessing.Event()
    start_event = multiprocessing.Event()
    error_queue: multiprocessing.Queue = multiprocessing.Queue()

    producer = multiprocessing.Process(
        target=_ipc_producer_worker,
        args=(
            str(backing_file),
            shared_lock,
            IPC_ORDER_COUNT,
            producer_ready,
            start_event,
            error_queue,
        ),
    )
    consumer = multiprocessing.Process(
        target=_ipc_consumer_worker,
        args=(
            str(backing_file),
            shared_lock,
            IPC_ORDER_COUNT,
            consumer_ready,
            start_event,
            error_queue,
        ),
    )

    try:
        consumer.start()
        producer.start()

        # Wait until both processes are running and ready
        if not producer_ready.wait(timeout=10):
            raise TimeoutError("Producer process failed to signal ready")
        if not consumer_ready.wait(timeout=10):
            raise TimeoutError("Consumer process failed to signal ready")

        # Start timing and release workers simultaneously
        start_time = time.perf_counter()
        start_event.set()

        producer.join(timeout=30)
        consumer.join(timeout=30)
        end_time = time.perf_counter()

        if producer.is_alive():
            producer.terminate()
            raise TimeoutError("Producer process timed out during run")
        if consumer.is_alive():
            consumer.terminate()
            raise TimeoutError("Consumer process timed out during run")

        # Check for any reported errors
        err = error_queue.get_nowait() if not error_queue.empty() else None
        if err is not None:
            raise RuntimeError(f"IPC Error: {err}")

    finally:
        if backing_file.exists():
            try:
                backing_file.unlink()
            except OSError:
                pass

    elapsed = end_time - start_time
    throughput = IPC_ORDER_COUNT / elapsed
    latency_us = (elapsed * 1_000_000) / IPC_ORDER_COUNT

    return {
        "elapsed": elapsed,
        "orders": IPC_ORDER_COUNT,
        "throughput": throughput,
        "latency_us": latency_us,
    }


# ---------------------------------------------------------------------------
# Main Execution & Reporting
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("             CHRONOSMATCH RING BUFFER BENCHMARK SUITE")
    print("=" * 70)
    print(f"  Operating System  : {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"  Python Version    : {platform.python_version()} ({platform.python_implementation()})")
    print(f"  Buffer Capacity   : {BUFFER_CAPACITY:,} slots (slot size = {ORDER_RECORD_SIZE} bytes)")
    print(f"  Synchronization   : multiprocessing.Lock (lock-based)")
    print("=" * 70)
    print()

    with tempfile.TemporaryDirectory() as tmp_str:
        temp_dir = Path(tmp_str)

        # Scenario 1: Raw Buffer
        print(f"[*] Running Scenario 1: Raw Buffer ({RAW_CYCLES:,} write/read cycles)...")
        raw_res = run_raw_buffer_benchmark(temp_dir)
        print(f"    Elapsed Time   : {raw_res['elapsed']:.4f} s")
        print(f"    Total Ops      : {int(raw_res['total_ops']):,} operations (write + read)")
        print(f"    Throughput     : {raw_res['op_throughput']:,.0f} ops/sec  ({raw_res['cycle_throughput']:,.0f} cycles/sec)")
        print(f"    Avg Latency    : {raw_res['latency_us_op']:.2f} us / op  ({raw_res['latency_us_cycle']:.2f} us / cycle)")
        print()

        # Scenario 2: End-to-End Order
        print(f"[*] Running Scenario 2: Order-Level ({ORDER_COUNT:,} encode->push->pop->decode)...")
        order_res = run_order_benchmark(temp_dir)
        print(f"    Elapsed Time   : {order_res['elapsed']:.4f} s")
        print(f"    Orders Processed: {int(order_res['orders']):,}")
        print(f"    Throughput     : {order_res['throughput']:,.0f} orders/sec")
        print(f"    Avg Latency    : {order_res['latency_us']:.2f} us / order")
        print()

        # Scenario 3: Multiprocess IPC
        print(f"[*] Running Scenario 3: Multiprocess IPC ({IPC_ORDER_COUNT:,} orders Producer -> Consumer)...")
        ipc_res = run_ipc_multiprocess_benchmark(temp_dir)
        print(f"    Elapsed Time   : {ipc_res['elapsed']:.4f} s")
        print(f"    Orders Transferred: {int(ipc_res['orders']):,}")
        print(f"    Throughput     : {ipc_res['throughput']:,.0f} orders/sec")
        print(f"    Avg Latency    : {ipc_res['latency_us']:.2f} us / order")
        print()

    print("=" * 70)
    print("  Benchmark finished successfully. All orders verified.")
    print("=" * 70)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
