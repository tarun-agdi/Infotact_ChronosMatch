"""
Benchmark and Profiling Suite for ChronosMatch Matching Engine and Order Book.

Measures throughput, latency, and profiles representative workloads using the
existing pure-Python MatchingEngine, OrderBook, Order, and RingBuffer interfaces.

Scenarios:
1. Pure Resting Orders (Book Building): 100,000 non-crossing orders.
2. Aggressive Matching: 100,000 crossing orders executing against resting liquidity.
3. Mixed Market Workload: 50,000 alternating realistic orders around a mid-price.
4. End-to-End Pipeline: 50,000 orders pushed via RingBuffer -> popped -> decoded -> matched.

Run with:
    python benchmarks/benchmark_matching_engine.py
or with profiling:
    python benchmarks/benchmark_matching_engine.py --profile
"""

from __future__ import annotations

import argparse
import cProfile
import io
import multiprocessing
from pathlib import Path
import pstats
import sys
import tempfile
import time
from typing import Final

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.matching_engine import MatchingEngine
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook
from chronosmatch.order_codec import ORDER_RECORD_SIZE

WARMUP_OPS: Final[int] = 5_000
BOOK_BUILD_COUNT: Final[int] = 100_000
CROSSING_COUNT: Final[int] = 100_000
MIXED_COUNT: Final[int] = 50_000
PIPELINE_COUNT: Final[int] = 50_000


def benchmark_book_building(count: int = BOOK_BUILD_COUNT) -> tuple[float, float, float]:
    """
    Benchmark pure resting limit orders (non-crossing).
    Tests add_order, is_crossing, and dict level creation.
    """
    engine = MatchingEngine()
    mid_price = 50_000

    # Warmup
    for i in range(1, WARMUP_OPS + 1):
        if i % 2 == 1:
            order = Order(order_id=i, price=mid_price - 100 - (i % 50), quantity=10, side=OrderSide.BUY, timestamp_ns=i)
        else:
            order = Order(order_id=i, price=mid_price + 100 + (i % 50), quantity=10, side=OrderSide.SELL, timestamp_ns=i)
        engine.process_order(order)

    # Fresh engine for timed run
    engine = MatchingEngine()
    orders = [
        Order(
            order_id=i,
            price=(mid_price - 100 - (i % 100)) if (i % 2 == 1) else (mid_price + 100 + (i % 100)),
            quantity=10,
            side=OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL,
            timestamp_ns=i,
        )
        for i in range(1, count + 1)
    ]

    t0 = time.perf_counter()
    for order in orders:
        engine.process_order(order)
    elapsed = time.perf_counter() - t0

    throughput = count / elapsed
    avg_latency_us = (elapsed / count) * 1_000_000
    return elapsed, throughput, avg_latency_us


def benchmark_aggressive_matching(count: int = CROSSING_COUNT) -> tuple[float, float, float, int]:
    """
    Benchmark matching against resting liquidity.
    Pre-populates the book with sell orders, then matches incoming buy orders.
    """
    engine = MatchingEngine()
    mid_price = 50_000

    # Pre-populate book with resting sells
    for i in range(1, count + 1):
        sell_order = Order(
            order_id=i,
            price=mid_price + (i % 10),
            quantity=10,
            side=OrderSide.SELL,
            timestamp_ns=i,
        )
        engine.order_book.add_order(sell_order)

    # Prepare crossing buy orders that execute immediately
    buy_orders = [
        Order(
            order_id=count + i,
            price=mid_price + (i % 10),
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=count + i,
        )
        for i in range(1, count + 1)
    ]

    t0 = time.perf_counter()
    total_trades = 0
    for order in buy_orders:
        trades = engine.process_order(order)
        total_trades += len(trades)
    elapsed = time.perf_counter() - t0

    throughput = count / elapsed
    avg_latency_us = (elapsed / count) * 1_000_000
    return elapsed, throughput, avg_latency_us, total_trades


def benchmark_mixed_workload(count: int = MIXED_COUNT) -> tuple[float, float, float, int]:
    """
    Simulate realistic trading stream:
    - 50% resting passive orders (narrowing or widening spread)
    - 50% crossing aggressive orders (executing against book)
    """
    engine = MatchingEngine()
    mid_price = 50_000

    # Seed initial book
    for i in range(1, 101):
        engine.order_book.add_order(Order(order_id=i, price=mid_price - i, quantity=20, side=OrderSide.BUY, timestamp_ns=i))
        engine.order_book.add_order(Order(order_id=1000 + i, price=mid_price + i, quantity=20, side=OrderSide.SELL, timestamp_ns=i))

    orders = []
    for i in range(1, count + 1):
        # Deterministic pseudo-random pattern
        side = OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL
        offset = (i * 7) % 50 - 25  # ranges from -25 to +24 relative to mid_price
        price = max(1, mid_price + offset)
        qty = 5 + (i % 15)
        orders.append(Order(order_id=2000 + i, price=price, quantity=qty, side=side, timestamp_ns=i))

    t0 = time.perf_counter()
    total_trades = 0
    for order in orders:
        trades = engine.process_order(order)
        total_trades += len(trades)
    elapsed = time.perf_counter() - t0

    throughput = count / elapsed
    avg_latency_us = (elapsed / count) * 1_000_000
    return elapsed, throughput, avg_latency_us, total_trades


def benchmark_pipeline(count: int = PIPELINE_COUNT) -> tuple[float, float, float, int]:
    """
    Benchmark complete integrated pipeline:
    Order -> RingBuffer.push_order -> RingBuffer.pop_order -> MatchingEngine.process_order
    """
    lock = multiprocessing.Lock()
    temp_dir = tempfile.TemporaryDirectory()
    filepath = Path(temp_dir.name) / "pipeline_bench.mmap"

    rb = RingBuffer.create(filepath, capacity=1024, slot_size=ORDER_RECORD_SIZE, lock=lock)
    engine = MatchingEngine()
    mid_price = 50_000

    # Seed some resting orders in engine
    for i in range(1, 501):
        engine.order_book.add_order(Order(order_id=i, price=mid_price - (i % 50) - 1, quantity=10, side=OrderSide.BUY, timestamp_ns=i))
        engine.order_book.add_order(Order(order_id=1000 + i, price=mid_price + (i % 50) + 1, quantity=10, side=OrderSide.SELL, timestamp_ns=i))

    orders = [
        Order(
            order_id=20000 + i,
            price=mid_price + ((i % 10) - 5),
            quantity=10,
            side=OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL,
            timestamp_ns=i,
        )
        for i in range(1, count + 1)
    ]

    total_trades = 0
    t0 = time.perf_counter()
    for order in orders:
        rb.push_order(order)
        popped = rb.pop_order()
        if popped is not None:
            trades = engine.process_order(popped)
            total_trades += len(trades)
    elapsed = time.perf_counter() - t0

    rb.unlink()
    temp_dir.cleanup()

    throughput = count / elapsed
    avg_latency_us = (elapsed / count) * 1_000_000
    return elapsed, throughput, avg_latency_us, total_trades


def profile_workload() -> None:
    """Run cProfile on the mixed workload to identify exact bottlenecks."""
    print("\n" + "=" * 70)
    print("PROFILING ANALYSIS (cProfile: 50,000 mixed orders)")
    print("=" * 70)

    profiler = cProfile.Profile()
    profiler.enable()
    benchmark_mixed_workload(count=50_000)
    profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats(30)
    print(stream.getvalue())

    print("-" * 70)
    print("TOP TIME CONSUMERS BY TOTAL SELF TIME (SortKey.TIME):")
    print("-" * 70)
    stream_time = io.StringIO()
    stats_time = pstats.Stats(profiler, stream=stream_time).sort_stats(pstats.SortKey.TIME)
    stats_time.print_stats(25)
    print(stream_time.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser(description="ChronosMatch Matching Engine Benchmark")
    parser.add_argument("--profile", action="store_true", help="Run cProfile on the representative workload")
    args = parser.parse_args()

    print("=" * 70)
    print("       CHRONOSMATCH MATCHING ENGINE PYTHON BASELINE BENCHMARK")
    print("=" * 70)
    print(f"  Python Version : {sys.version.split()[0]} ({sys.implementation.name})")
    print(f"  Platform       : {sys.platform}")
    print("=" * 70)

    print("\n[*] Scenario 1: Pure Resting Orders (Book Building - 100,000 orders)...")
    elapsed, tput, lat = benchmark_book_building()
    print(f"    Elapsed Time   : {elapsed:.4f} s")
    print(f"    Throughput     : {tput:,.0f} orders/sec")
    print(f"    Avg Latency    : {lat:.2f} us / order")

    print("\n[*] Scenario 2: Aggressive Matching (100,000 orders crossing resting liquidity)...")
    elapsed, tput, lat, trades = benchmark_aggressive_matching()
    print(f"    Elapsed Time   : {elapsed:.4f} s")
    print(f"    Total Trades   : {trades:,}")
    print(f"    Throughput     : {tput:,.0f} orders/sec")
    print(f"    Avg Latency    : {lat:.2f} us / order")

    print("\n[*] Scenario 3: Mixed Realistic Workload (50,000 orders around mid-price)...")
    elapsed, tput, lat, trades = benchmark_mixed_workload()
    print(f"    Elapsed Time   : {elapsed:.4f} s")
    print(f"    Total Trades   : {trades:,}")
    print(f"    Throughput     : {tput:,.0f} orders/sec")
    print(f"    Avg Latency    : {lat:.2f} us / order")

    print("\n[*] Scenario 4: Integrated Pipeline (RingBuffer -> Codec -> Matching - 50,000 orders)...")
    elapsed, tput, lat, trades = benchmark_pipeline()
    print(f"    Elapsed Time   : {elapsed:.4f} s")
    print(f"    Total Trades   : {trades:,}")
    print(f"    Throughput     : {tput:,.0f} orders/sec")
    print(f"    Avg Latency    : {lat:.2f} us / order")

    if args.profile:
        profile_workload()


if __name__ == "__main__":
    main()
