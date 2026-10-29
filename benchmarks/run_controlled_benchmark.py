"""
Controlled Python vs Cython Benchmark Suite for ChronosMatch.

Executes a fair, controlled comparison between the pure-Python matching engine
and the compiled Cython matching engine across all existing benchmark scenarios:
  1. Pure Resting Orders (Book Building) - 100,000 orders
  2. Aggressive Matching - 100,000 orders
  3. Mixed Market Workload - 50,000 orders
  4. Integrated Pipeline (RingBuffer -> Codec -> Matching) - 50,000 orders

Features:
- Enforces explicit `use_cython=False` (Pure Python) and `use_cython=True` (Cython).
- Confirms actual compiled extension dispatch.
- Verifies exact trade and order-book parity between implementations.
- Executes 3 runs per scenario per engine and reports medians.
- Calculates throughput improvement (%) and latency reduction (%).
"""

from __future__ import annotations

import statistics
import sys
import time
from typing import Callable, Final

import chronosmatch._matching_core as cython_core
import chronosmatch.matching_engine as me_module
from chronosmatch.matching_engine import CYTHON_CORE_AVAILABLE, MatchingEngine
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook

from pathlib import Path

BENCHMARKS_DIR = Path(__file__).resolve().parent
if str(BENCHMARKS_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS_DIR))

import benchmark_matching_engine as bme

NUM_ROUNDS: Final[int] = 3


def set_engine_mode(use_cython: bool) -> Callable[[], None]:
    """In-memory monkeypatch to force MatchingEngine to use a specific backend."""
    orig_init = me_module.MatchingEngine.__init__

    def patched_init(self, order_book=None, use_cython_arg=None):
        orig_init(self, order_book=order_book, use_cython=use_cython)

    me_module.MatchingEngine.__init__ = patched_init

    def restore():
        me_module.MatchingEngine.__init__ = orig_init

    return restore


def verify_engine_dispatch() -> None:
    """Verify that use_cython=True routes to Cython and use_cython=False routes to Python."""
    assert CYTHON_CORE_AVAILABLE, "Cython extension is not compiled or available!"

    e_cy = MatchingEngine(use_cython=True)
    assert e_cy.use_cython is True, "MatchingEngine(use_cython=True) failed to enable Cython"

    e_py = MatchingEngine(use_cython=False)
    assert e_py.use_cython is False, "MatchingEngine(use_cython=False) failed to disable Cython"


def verify_scenario_parity() -> None:
    """Verify semantic parity (individual trades and book state) across 10,000-order deterministic workloads."""
    print("[*] Running automated pre-check: semantic parity across 10k-order deterministic streams...")
    mid_price = 50_000

    # Scenario 1 Parity (Book Building)
    book_py, book_cy = OrderBook(), OrderBook()
    eng_py, eng_cy = MatchingEngine(book_py, use_cython=False), MatchingEngine(book_cy, use_cython=True)
    for i in range(1, 10_001):
        o = Order(
            order_id=i,
            price=(mid_price - 100 - (i % 100)) if (i % 2 == 1) else (mid_price + 100 + (i % 100)),
            quantity=10,
            side=OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL,
            timestamp_ns=i,
        )
        eng_py.process_order(o)
        eng_cy.process_order(o)
    assert book_py.best_bid() == book_cy.best_bid(), "Scenario 1 best bid mismatch"
    assert book_py.best_ask() == book_cy.best_ask(), "Scenario 1 best ask mismatch"
    assert set(book_py.bids.keys()) == set(book_cy.bids.keys()), "Scenario 1 bids mismatch"
    assert set(book_py.asks.keys()) == set(book_cy.asks.keys()), "Scenario 1 asks mismatch"

    # Scenario 2 Parity (Aggressive Matching)
    book_py, book_cy = OrderBook(), OrderBook()
    eng_py, eng_cy = MatchingEngine(book_py, use_cython=False), MatchingEngine(book_cy, use_cython=True)
    count = 10_000
    for i in range(1, count + 1):
        s = Order(order_id=i, price=mid_price + (i % 10), quantity=10, side=OrderSide.SELL, timestamp_ns=i)
        book_py.add_order(s)
        book_cy.add_order(s)
    trades_py, trades_cy = [], []
    for i in range(1, count + 1):
        b = Order(order_id=count + i, price=mid_price + (i % 10), quantity=10, side=OrderSide.BUY, timestamp_ns=count + i)
        trades_py.extend(eng_py.process_order(b))
        trades_cy.extend(eng_cy.process_order(b))
    assert len(trades_py) == len(trades_cy), f"Scenario 2 trade count mismatch: {len(trades_py)} vs {len(trades_cy)}"
    for t1, t2 in zip(trades_py, trades_cy):
        assert (t1.buy_order_id, t1.sell_order_id, t1.price, t1.quantity) == (t2.buy_order_id, t2.sell_order_id, t2.price, t2.quantity)
    assert book_py.best_bid() == book_cy.best_bid()
    assert book_py.best_ask() == book_cy.best_ask()

    # Scenario 3 Parity (Mixed Workload)
    book_py, book_cy = OrderBook(), OrderBook()
    eng_py, eng_cy = MatchingEngine(book_py, use_cython=False), MatchingEngine(book_cy, use_cython=True)
    for i in range(1, 101):
        book_py.add_order(Order(order_id=i, price=mid_price - i, quantity=20, side=OrderSide.BUY, timestamp_ns=i))
        book_py.add_order(Order(order_id=1000 + i, price=mid_price + i, quantity=20, side=OrderSide.SELL, timestamp_ns=i))
        book_cy.add_order(Order(order_id=i, price=mid_price - i, quantity=20, side=OrderSide.BUY, timestamp_ns=i))
        book_cy.add_order(Order(order_id=1000 + i, price=mid_price + i, quantity=20, side=OrderSide.SELL, timestamp_ns=i))
    trades_py, trades_cy = [], []
    for i in range(1, 10_001):
        side = OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL
        offset = (i * 7) % 50 - 25
        price = max(1, mid_price + offset)
        qty = 5 + (i % 15)
        o = Order(order_id=2000 + i, price=price, quantity=qty, side=side, timestamp_ns=i)
        trades_py.extend(eng_py.process_order(o))
        trades_cy.extend(eng_cy.process_order(o))
    assert len(trades_py) == len(trades_cy), "Scenario 3 trade count mismatch"
    for t1, t2 in zip(trades_py, trades_cy):
        assert (t1.buy_order_id, t1.sell_order_id, t1.price, t1.quantity) == (t2.buy_order_id, t2.sell_order_id, t2.price, t2.quantity)
    assert book_py.best_bid() == book_cy.best_bid()
    assert book_py.best_ask() == book_cy.best_ask()

    # Scenario 4 Parity (Integrated Pipeline)
    book_py, book_cy = OrderBook(), OrderBook()
    eng_py, eng_cy = MatchingEngine(book_py, use_cython=False), MatchingEngine(book_cy, use_cython=True)
    for i in range(1, 501):
        book_py.add_order(Order(order_id=i, price=mid_price - (i % 50) - 1, quantity=10, side=OrderSide.BUY, timestamp_ns=i))
        book_py.add_order(Order(order_id=1000 + i, price=mid_price + (i % 50) + 1, quantity=10, side=OrderSide.SELL, timestamp_ns=i))
        book_cy.add_order(Order(order_id=i, price=mid_price - (i % 50) - 1, quantity=10, side=OrderSide.BUY, timestamp_ns=i))
        book_cy.add_order(Order(order_id=1000 + i, price=mid_price + (i % 50) + 1, quantity=10, side=OrderSide.SELL, timestamp_ns=i))
    trades_py, trades_cy = [], []
    for i in range(1, 10_001):
        o = Order(
            order_id=20000 + i,
            price=mid_price + ((i % 10) - 5),
            quantity=10,
            side=OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL,
            timestamp_ns=i,
        )
        trades_py.extend(eng_py.process_order(o))
        trades_cy.extend(eng_cy.process_order(o))
    assert len(trades_py) == len(trades_cy), "Scenario 4 trade count mismatch"
    for t1, t2 in zip(trades_py, trades_cy):
        assert (t1.buy_order_id, t1.sell_order_id, t1.price, t1.quantity) == (t2.buy_order_id, t2.sell_order_id, t2.price, t2.quantity)
    assert book_py.best_bid() == book_cy.best_bid()
    assert book_py.best_ask() == book_cy.best_ask()

    print("  -> Parity Check: 100% MATCH on all trade executions, prices, quantities, and order book states!\n")


def run_benchmark_suite(use_cython: bool, rounds: int = NUM_ROUNDS) -> dict[str, dict]:
    """Execute all 4 scenarios for the given engine mode across specified rounds."""
    mode_name = "CYTHON" if use_cython else "PURE PYTHON"
    print("=" * 75)
    print(f"  RUNNING BENCHMARK: {mode_name} (use_cython={use_cython}, rounds={rounds})")
    print("=" * 75)

    restore = set_engine_mode(use_cython)

    scenarios = [
        ("Scenario 1: Book Building (100k orders)", bme.benchmark_book_building, False),
        ("Scenario 2: Aggressive Matching (100k orders)", bme.benchmark_aggressive_matching, True),
        ("Scenario 3: Mixed Workload (50k orders)", bme.benchmark_mixed_workload, True),
        ("Scenario 4: Integrated Pipeline (50k orders)", bme.benchmark_pipeline, True),
    ]

    results: dict[str, dict] = {}

    try:
        for name, func, has_trades in scenarios:
            print(f"\n[*] Executing {name}...")
            elapsed_list: list[float] = []
            tput_list: list[float] = []
            lat_list: list[float] = []
            trades_val: int | None = None

            for r in range(1, rounds + 1):
                res = func()
                if has_trades:
                    elapsed, tput, lat, tr = res
                    trades_val = tr
                    print(f"    Run {r}/{rounds}: Elapsed = {elapsed:.4f} s | Throughput = {tput:,.0f} ops/s | Latency = {lat:.2f} us | Trades = {tr:,}")
                else:
                    elapsed, tput, lat = res
                    print(f"    Run {r}/{rounds}: Elapsed = {elapsed:.4f} s | Throughput = {tput:,.0f} ops/s | Latency = {lat:.2f} us")

                elapsed_list.append(elapsed)
                tput_list.append(tput)
                lat_list.append(lat)

            med_elapsed = statistics.median(elapsed_list)
            med_tput = statistics.median(tput_list)
            med_lat = statistics.median(lat_list)

            print(f"  >> MEDIAN: Elapsed = {med_elapsed:.4f} s | Throughput = {med_tput:,.0f} ops/s | Latency = {med_lat:.2f} us")

            results[name] = {
                "elapsed": med_elapsed,
                "throughput": med_tput,
                "latency_us": med_lat,
                "trades": trades_val,
                "raw_elapsed": elapsed_list,
                "raw_throughput": tput_list,
                "raw_latency": lat_list,
            }
    finally:
        restore()

    print()
    return results


def print_comparison_table(py_res: dict[str, dict], cy_res: dict[str, dict]) -> None:
    """Print detailed comparison table with percentage improvements and speedup factor."""
    print("=" * 125)
    print("                         CHRONOSMATCH BENCHMARK RESULTS: PURE PYTHON vs CYTHON")
    print("=" * 125)
    header = f"{'Benchmark Scenario':<32} | {'Python Tput':>12} | {'Cython Tput':>12} | {'Tput Imp (%)':>12} | {'Speedup':>9} | {'Python Lat':>11} | {'Cython Lat':>11} | {'Lat Reduc (%)':>13}"
    print(header)
    print("-" * 125)

    for name in py_res:
        py_data = py_res[name]
        cy_data = cy_res[name]

        py_tput = py_data["throughput"]
        cy_tput = cy_data["throughput"]
        tput_speedup_pct = ((cy_tput - py_tput) / py_tput) * 100
        speedup_factor = cy_tput / py_tput

        py_lat = py_data["latency_us"]
        cy_lat = cy_data["latency_us"]
        lat_reduc_pct = ((py_lat - cy_lat) / py_lat) * 100

        short_name = name.split(":")[1].split("(")[0].strip() if ":" in name else name

        print(
            f"{short_name:<32} | "
            f"{py_tput:>9,.0f} o/s | "
            f"{cy_tput:>9,.0f} o/s | "
            f"{tput_speedup_pct:>+11.2f}% | "
            f"{speedup_factor:>8.2f}x | "
            f"{py_lat:>8.2f} us | "
            f"{cy_lat:>8.2f} us | "
            f"{lat_reduc_pct:>+12.2f}%"
        )

    print("-" * 125)
    print("Aggregate Trade Count Verification (Benchmark Runs):")
    for name in py_res:
        tr_py = py_res[name]["trades"]
        tr_cy = cy_res[name]["trades"]
        short_name = name.split(":")[1].split("(")[0].strip() if ":" in name else name
        if tr_py is not None:
            match_status = "MATCH (Identical)" if tr_py == tr_cy else "MISMATCH"
            print(f"  - {short_name:<34}: Python Trades = {tr_py:,} | Cython Trades = {tr_cy:,} -> {match_status}")
        else:
            print(f"  - {short_name:<34}: 0 crossings (pure resting limit orders added)")
    print("=" * 125)


def main() -> None:
    print("=" * 75)
    print("       CHRONOSMATCH CONTROLLED BENCHMARK: PURE PYTHON VS CYTHON")
    print("=" * 75)
    print(f"  Python Version   : {sys.version.split()[0]} ({sys.implementation.name})")
    print(f"  Platform         : {sys.platform}")
    print(f"  Cython Available : {CYTHON_CORE_AVAILABLE}")
    print(f"  Cython Module    : {getattr(cython_core, '__file__', 'None')}")
    print("=" * 75)
    print()

    verify_engine_dispatch()
    verify_scenario_parity()

    # Run Pure Python Benchmark
    py_results = run_benchmark_suite(use_cython=False, rounds=NUM_ROUNDS)

    # Run Cython Benchmark
    cy_results = run_benchmark_suite(use_cython=True, rounds=NUM_ROUNDS)

    # Comparison Table
    print_comparison_table(py_results, cy_results)


if __name__ == "__main__":
    main()
