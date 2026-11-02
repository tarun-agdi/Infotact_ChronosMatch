
"""
ChronosMatch - Monitoring and Verification Module

Responsibilities:
1. Track order and trade statistics.
2. Measure execution latency.
3. Verify trade correctness.
4. Monitor order-book consistency.
5. Generate monitoring reports.
"""

from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Optional

from .order import Order
from .trade import Trade


@dataclass
class TestMonitor:
    """Monitors matching-engine correctness and performance."""

    total_orders: int = 0
    total_trades: int = 0
    total_filled_quantity: int = 0

    valid_trades: int = 0
    invalid_trades: int = 0

    latencies_ns: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    _start_time: Optional[int] = None

    # --------------------------------------------------
    # Performance Monitoring
    # --------------------------------------------------

    def start_timer(self) -> None:
        """Start measuring execution time."""
        self._start_time = perf_counter_ns()

    def stop_timer(self) -> int:
        """Stop timer and record elapsed time in nanoseconds."""
        if self._start_time is None:
            raise RuntimeError("Timer was not started.")

        elapsed = perf_counter_ns() - self._start_time

        self.latencies_ns.append(elapsed)
        self._start_time = None

        return elapsed

    # --------------------------------------------------
    # Order Monitoring
    # --------------------------------------------------

    def record_order(self, order: Order) -> None:
        """Record an incoming order."""

        if order.quantity <= 0:
            self.errors.append(
                f"Invalid order quantity: {order.quantity}"
            )
            return

        self.total_orders += 1

    # --------------------------------------------------
    # Trade Verification
    # --------------------------------------------------

    def verify_trade(self, trade: Trade) -> bool:
        """
        Perform basic trade validation.

        Checks:
        - Positive execution price.
        - Positive execution quantity.
        - Valid buy and sell order references.
        """

        checks = [
            getattr(trade, "price", 0) > 0,
            getattr(trade, "quantity", 0) > 0,
            getattr(trade, "buy_order_id", None) is not None,
            getattr(trade, "sell_order_id", None) is not None,
        ]

        if all(checks):
            self.valid_trades += 1
            self.total_trades += 1
            self.total_filled_quantity += trade.quantity
            return True

        self.invalid_trades += 1
        self.errors.append(f"Invalid trade detected: {trade}")

        return False

    # --------------------------------------------------
    # Performance Statistics
    # --------------------------------------------------

    def get_latency_stats(self) -> dict:
        """Return latency statistics in nanoseconds."""

        if not self.latencies_ns:
            return {
                "min_ns": 0,
                "max_ns": 0,
                "avg_ns": 0,
            }

        return {
            "min_ns": min(self.latencies_ns),
            "max_ns": max(self.latencies_ns),
            "avg_ns": sum(self.latencies_ns) / len(self.latencies_ns),
        }

    # --------------------------------------------------
    # Monitoring Report
    # --------------------------------------------------

    def get_report(self) -> dict:
        """Return a summary of monitoring statistics."""

        return {
            "total_orders": self.total_orders,
            "total_trades": self.total_trades,
            "valid_trades": self.valid_trades,
            "invalid_trades": self.invalid_trades,
            "total_filled_quantity": self.total_filled_quantity,
            "latency": self.get_latency_stats(),
            "errors": self.errors.copy(),
        }

    def print_report(self) -> None:
        """Print monitoring report."""

        report = self.get_report()

        print("\n========== CHRONOSMATCH MONITOR ==========")

        print(f"Total Orders       : {report['total_orders']}")
        print(f"Total Trades       : {report['total_trades']}")
        print(f"Valid Trades       : {report['valid_trades']}")
        print(f"Invalid Trades     : {report['invalid_trades']}")
        print(f"Filled Quantity    : {report['total_filled_quantity']}")

        print("\nLatency Statistics:")
        print(f"Minimum            : {report['latency']['min_ns']} ns")
        print(f"Maximum            : {report['latency']['max_ns']} ns")
        print(f"Average            : {report['latency']['avg_ns']:.2f} ns")

        print(f"\nErrors             : {len(report['errors'])}")

        for error in report["errors"]:
            print(f" - {error}")

        print("==========================================\n")
