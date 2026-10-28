"""
Parity test suite verifying equivalence between Python reference and Cython matching engine.

Runs identical deterministic inputs through both matching engines and asserts exact
equivalence of generated trades, trade prices, execution quantities, and resulting
order book states.
"""

import unittest

from chronosmatch.matching_engine import CYTHON_CORE_AVAILABLE, MatchingEngine
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_book import OrderBook


class TestMatchingEngineParity(unittest.TestCase):
    """Parity tests between Python reference and Cython matching engine."""

    def test_python_fallback_integrity(self) -> None:
        """Verify python fallback works and produces correct trades."""
        engine = MatchingEngine(OrderBook(), use_cython=False)
        self.assertFalse(engine.use_cython)

        engine.order_book.add_order(
            Order(order_id=1, price=100, quantity=10, side=OrderSide.SELL, timestamp_ns=100)
        )
        trades = engine.process_order(
            Order(order_id=2, price=105, quantity=4, side=OrderSide.BUY, timestamp_ns=200)
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, 4)
        self.assertEqual(trades[0].price, 100)
        self.assertEqual(engine.order_book.asks[100][0].quantity, 6)

    @unittest.skipUnless(
        CYTHON_CORE_AVAILABLE,
        "Cython matching core not compiled (requires 64-bit C/C++ compiler)",
    )
    def test_deterministic_parity_multi_order_stream(self) -> None:
        """Execute identical sequence on Python and Cython engines and assert exact equality."""
        book_py = OrderBook()
        engine_py = MatchingEngine(book_py, use_cython=False)

        book_cy = OrderBook()
        engine_cy = MatchingEngine(book_cy, use_cython=True)
        self.assertTrue(engine_cy.use_cython)

        mid_price = 50_000
        orders = []

        # Passive seed orders
        for i in range(1, 51):
            orders.append(
                Order(
                    order_id=i,
                    price=mid_price - i,
                    quantity=10 + (i % 5),
                    side=OrderSide.BUY,
                    timestamp_ns=i * 10,
                )
            )
            orders.append(
                Order(
                    order_id=100 + i,
                    price=mid_price + i,
                    quantity=10 + (i % 5),
                    side=OrderSide.SELL,
                    timestamp_ns=i * 10 + 5,
                )
            )

        # Sweeping and crossing orders
        for i in range(1, 101):
            side = OrderSide.BUY if (i % 2 == 1) else OrderSide.SELL
            offset = (i * 3) % 25 - 12
            price = mid_price + offset
            qty = 5 + (i % 8)
            orders.append(
                Order(
                    order_id=1000 + i,
                    price=price,
                    quantity=qty,
                    side=side,
                    timestamp_ns=1000 + i,
                )
            )

        for order in orders:
            trades_py = engine_py.process_order(order)
            trades_cy = engine_cy.process_order(order)

            self.assertEqual(
                len(trades_py),
                len(trades_cy),
                f"Trade count mismatch for order {order}",
            )
            for t_py, t_cy in zip(trades_py, trades_cy):
                self.assertEqual(t_py.buy_order_id, t_cy.buy_order_id)
                self.assertEqual(t_py.sell_order_id, t_cy.sell_order_id)
                self.assertEqual(t_py.price, t_cy.price)
                self.assertEqual(t_py.quantity, t_cy.quantity)
                self.assertEqual(t_py.timestamp_ns, t_cy.timestamp_ns)

            # Order book best quotes parity
            self.assertEqual(book_py.best_bid(), book_cy.best_bid())
            self.assertEqual(book_py.best_ask(), book_cy.best_ask())

        # Final order book states parity
        self.assertEqual(set(book_py.bids.keys()), set(book_cy.bids.keys()))
        self.assertEqual(set(book_py.asks.keys()), set(book_cy.asks.keys()))

        for price in book_py.bids:
            self.assertEqual(
                [(o.order_id, o.quantity) for o in book_py.bids[price]],
                [(o.order_id, o.quantity) for o in book_cy.bids[price]],
            )

        for price in book_py.asks:
            self.assertEqual(
                [(o.order_id, o.quantity) for o in book_py.asks[price]],
                [(o.order_id, o.quantity) for o in book_cy.asks[price]],
            )


if __name__ == "__main__":
    unittest.main()
