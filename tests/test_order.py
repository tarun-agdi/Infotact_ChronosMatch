"""
Unit tests for the Order and OrderSide models.
"""

from dataclasses import FrozenInstanceError
import unittest

from chronosmatch.order import Order, OrderSide


class TestOrderModel(unittest.TestCase):
    """Test suite verifying Order behavior, validation, and immutability."""

    def test_create_valid_buy_order(self) -> None:
        """Verify that a valid BUY order is created with correct attributes."""
        order = Order(
            order_id=1,
            price=15000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1_700_000_000_000_000_000,
        )
        self.assertEqual(order.order_id, 1)
        self.assertEqual(order.price, 15000)
        self.assertEqual(order.quantity, 10)
        self.assertEqual(order.side, OrderSide.BUY)
        self.assertEqual(order.timestamp_ns, 1_700_000_000_000_000_000)

    def test_create_valid_sell_order(self) -> None:
        """Verify that a valid SELL order is created with correct attributes."""
        order = Order(
            order_id=2,
            price=15050,
            quantity=5,
            side=OrderSide.SELL,
            timestamp_ns=1_700_000_000_000_000_500,
        )
        self.assertEqual(order.order_id, 2)
        self.assertEqual(order.price, 15050)
        self.assertEqual(order.quantity, 5)
        self.assertEqual(order.side, OrderSide.SELL)
        self.assertEqual(order.timestamp_ns, 1_700_000_000_000_000_500)

    def test_timestamp_zero_is_valid(self) -> None:
        """Verify that a non-negative timestamp of 0 is valid."""
        order = Order(
            order_id=10,
            price=100,
            quantity=1,
            side=OrderSide.BUY,
            timestamp_ns=0,
        )
        self.assertEqual(order.timestamp_ns, 0)

    def test_order_side_values(self) -> None:
        """Verify enum integer values for OrderSide."""
        self.assertEqual(OrderSide.BUY, 1)
        self.assertEqual(OrderSide.SELL, 2)

    def test_reject_invalid_order_id(self) -> None:
        """Verify rejection of non-positive or non-integer order_id."""
        with self.assertRaises(ValueError):
            Order(order_id=0, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=100)

        with self.assertRaises(ValueError):
            Order(order_id=-1, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=100)

        with self.assertRaises(TypeError):
            Order(order_id="1", price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1.5, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

    def test_reject_invalid_price(self) -> None:
        """Verify rejection of non-positive or non-integer price."""
        with self.assertRaises(ValueError):
            Order(order_id=1, price=0, quantity=1, side=OrderSide.BUY, timestamp_ns=100)

        with self.assertRaises(ValueError):
            Order(order_id=1, price=-50, quantity=1, side=OrderSide.BUY, timestamp_ns=100)

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100.5, quantity=1, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1, price="100", quantity=1, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

    def test_reject_invalid_quantity(self) -> None:
        """Verify rejection of non-positive or non-integer quantity."""
        with self.assertRaises(ValueError):
            Order(order_id=1, price=100, quantity=0, side=OrderSide.BUY, timestamp_ns=100)

        with self.assertRaises(ValueError):
            Order(order_id=1, price=100, quantity=-10, side=OrderSide.BUY, timestamp_ns=100)

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity=1.0, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity="10", side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

    def test_reject_invalid_side(self) -> None:
        """Verify rejection of invalid side types and values."""
        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity=1, side="BUY", timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity=1, side=1, timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity=1, side=None, timestamp_ns=100)  # type: ignore[arg-type]

    def test_reject_invalid_timestamp(self) -> None:
        """Verify rejection of negative or non-integer timestamp_ns."""
        with self.assertRaises(ValueError):
            Order(order_id=1, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=-1)

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=100.5)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns="100")  # type: ignore[arg-type]

    def test_reject_booleans_in_integer_fields(self) -> None:
        """Verify that bool (subclass of int) is rejected in all integer fields."""
        with self.assertRaises(TypeError):
            Order(order_id=True, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=False, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1, price=True, quantity=1, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity=True, side=OrderSide.BUY, timestamp_ns=100)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Order(order_id=1, price=100, quantity=1, side=OrderSide.BUY, timestamp_ns=True)  # type: ignore[arg-type]

    def test_order_immutability(self) -> None:
        """Verify that Order attributes cannot be modified after creation."""
        order = Order(
            order_id=1,
            price=15000,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=1_000,
        )

        with self.assertRaises(FrozenInstanceError):
            order.price = 20000  # type: ignore[misc]

        with self.assertRaises(FrozenInstanceError):
            order.quantity = 5  # type: ignore[misc]

        with self.assertRaises(FrozenInstanceError):
            order.side = OrderSide.SELL  # type: ignore[misc]

        with self.assertRaises(FrozenInstanceError):
            order.order_id = 999  # type: ignore[misc]

        with self.assertRaises(FrozenInstanceError):
            order.timestamp_ns = 2_000  # type: ignore[misc]

    def test_order_equality_and_hash(self) -> None:
        """Verify that identical orders compare equal and can be hashed."""
        order1 = Order(1, 15000, 10, OrderSide.BUY, 1_000)
        order2 = Order(1, 15000, 10, OrderSide.BUY, 1_000)
        order3 = Order(2, 15000, 10, OrderSide.BUY, 1_000)

        self.assertEqual(order1, order2)
        self.assertNotEqual(order1, order3)
        self.assertEqual(hash(order1), hash(order2))


if __name__ == "__main__":
    unittest.main()
