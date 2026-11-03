
import statistics
import sys
import time
from pathlib import Path

import chronosmatch.matching_engine as me
import chronosmatch.matching_engine_cy as cy
from chronosmatch.matching_engine import MatchingEngine, CYTHON_CORE_AVAILABLE
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook

sys.path.insert(0, str(Path(__file__).resolve().parent))

import benchmark_matching_engine as bm


ROUNDS = 3


def verify_engine():
    if not CYTHON_CORE_AVAILABLE:
        raise RuntimeError("Cython extension is not available")

    py_engine = MatchingEngine(use_cython=False)
    cy_engine = MatchingEngine(use_cython=True)

    assert not py_engine.use_cython
    assert cy_engine.use_cython


def verify_parity():
    mid_price = 50000

    book_py = OrderBook()
    book_cy = OrderBook()

    engine_py = MatchingEngine(book_py, use_cython=False)
    engine_cy = MatchingEngine(book_cy, use_cython=True)

    for i in range(1, 10001):
        order = Order(
            order_id=i,
            price=mid_price + (i % 10),
            quantity=10,
            side=OrderSide.SELL if i % 2 == 0 else OrderSide.BUY,
            timestamp_ns=i
        )

        engine_py.process_order(order)
        engine_cy.process_order(order)

    assert book_py.best_bid() == book_cy.best_bid()
    assert book_py.best_ask() == book_cy.best_ask()


def run_benchmarks(use_cython):
    original_init = me.MatchingEngine.__init__

    def patched_init(self, order_book=None, use_cython_arg=None):
        original_init(
            self,
            order_book=order_book,
            use_cython=use_cython
        )

    me.MatchingEngine.__init__ = patched_init

    scenarios = [
        ("Book Building", bm.benchmark_book_building, False),
        ("Aggressive Matching", bm.benchmark_aggressive_matching, True),
        ("Mixed Workload", bm.benchmark_mixed_workload, True),
        ("Integrated Pipeline", bm.benchmark_pipeline, True)
    ]

    results = {}

    try:
        for name, function, has_trades in scenarios:
            elapsed_times = []
            throughputs = []
            latencies = []
            trades = None

            for _ in range(ROUNDS):
                result = function()

                if has_trades:
                    elapsed, throughput, latency, trades = result
                else:
                    elapsed, throughput, latency = result

                elapsed_times.append(elapsed)
                throughputs.append(throughput)
                latencies.append(latency)

            results[name] = {
                "elapsed": statistics.median(elapsed_times),
                "throughput": statistics.median(throughputs),
                "latency": statistics.median(latencies),
                "trades": trades
            }

    finally:
        me.MatchingEngine.__init__ = original_init

    return results


def show_results(py_results, cy_results):
    print("\nPYTHON VS CYTHON RESULTS\n")

    print(
        f"{'Scenario':<25}"
        f"{'Python':>15}"
        f"{'Cython':>15}"
        f"{'Speedup':>12}"
        f"{'Latency Reduction':>20}"
    )

    for name in py_results:
        py = py_results[name]
        cy_result = cy_results[name]

        speedup = (
            cy_result["throughput"] / py["throughput"]
        )

        improvement = (
            (py["latency"] - cy_result["latency"])
            / py["latency"]
        ) * 100

        print(
            f"{name:<25}"
            f"{py['throughput']:>15,.0f}"
            f"{cy_result['throughput']:>15,.0f}"
            f"{speedup:>11.2f}x"
            f"{improvement:>18.2f}%"
        )

        if py["trades"] is not None:
            print(
                f"Trades: Python={py['trades']}, "
                f"Cython={cy_result['trades']}"
            )


def main():
    print("CHRONOSMATCH BENCHMARK")
    print("Python version:", sys.version.split()[0])
    print("Cython available:", CYTHON_CORE_AVAILABLE)

    verify_engine()
    verify_parity()

    print("\nRunning Python benchmarks...")
    py_results = run_benchmarks(False)

    print("\nRunning Cython benchmarks...")
    cy_results = run_benchmarks(True)

    show_results(py_results, cy_results)


if __name__ == "__main__":
    main()
