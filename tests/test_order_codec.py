"""
Unit tests for the binary Order serialization and deserialization codec.
"""

import struct
import unittest

from chronosmatch.order import Order, OrderSide
from chronosmatch.order_codec import (
    ORDER_RECORD_FORMAT,
    ORDER_RECORD_SIZE,
    UINT64_MAX,
    decode_order,
    encode_order,
)


class TestOrderCodec(unittest.TestCase):
    """Test suite verifying binary encoding, decoding, validation, and boundaries."""

    def setUp(self) -> None:
        self.sample_buy_order = Order(
            order_id=101,
            price=25000,
            quantity=50,
            side=OrderSide.BUY,
            timestamp_ns=1_700_000_000_123_456_789,
        )
        self.sample_sell_order = Order(
            order_id=102,
            price=25050,
            quantity=25,
            side=OrderSide.SELL,
            timestamp_ns=1_700_000_000_987_654_321,
        )

    def test_record_size_and_format_constants(self) -> None:
        """Verify that the record format produces a fixed 33-byte length."""
        self.assertEqual(ORDER_RECORD_SIZE, 33)
        self.assertEqual(struct.calcsize(ORDER_RECORD_FORMAT), 33)

    def test_encode_produces_fixed_byte_length(self) -> None:
        """Verify that encoding an Order produces bytes of exactly 33 bytes."""
        encoded_buy = encode_order(self.sample_buy_order)
        encoded_sell = encode_order(self.sample_sell_order)

        self.assertIsInstance(encoded_buy, bytes)
        self.assertIsInstance(encoded_sell, bytes)
        self.assertEqual(len(encoded_buy), 33)
        self.assertEqual(len(encoded_sell), 33)

    def test_roundtrip_buy_order_preserves_all_fields(self) -> None:
        """Verify that encoding and then decoding a BUY order preserves all fields."""
        encoded = encode_order(self.sample_buy_order)
        decoded = decode_order(encoded)

        self.assertEqual(decoded, self.sample_buy_order)
        self.assertEqual(decoded.order_id, self.sample_buy_order.order_id)
        self.assertEqual(decoded.price, self.sample_buy_order.price)
        self.assertEqual(decoded.quantity, self.sample_buy_order.quantity)
        self.assertEqual(decoded.side, OrderSide.BUY)
        self.assertEqual(decoded.timestamp_ns, self.sample_buy_order.timestamp_ns)

    def test_roundtrip_sell_order_preserves_all_fields(self) -> None:
        """Verify that encoding and then decoding a SELL order preserves all fields."""
        encoded = encode_order(self.sample_sell_order)
        decoded = decode_order(encoded)

        self.assertEqual(decoded, self.sample_sell_order)
        self.assertEqual(decoded.order_id, self.sample_sell_order.order_id)
        self.assertEqual(decoded.price, self.sample_sell_order.price)
        self.assertEqual(decoded.quantity, self.sample_sell_order.quantity)
        self.assertEqual(decoded.side, OrderSide.SELL)
        self.assertEqual(decoded.timestamp_ns, self.sample_sell_order.timestamp_ns)

    def test_roundtrip_zero_timestamp(self) -> None:
        """Verify that an order with timestamp_ns = 0 encodes and decodes properly."""
        order = Order(
            order_id=1,
            price=100,
            quantity=10,
            side=OrderSide.BUY,
            timestamp_ns=0,
        )
        decoded = decode_order(encode_order(order))
        self.assertEqual(decoded, order)
        self.assertEqual(decoded.timestamp_ns, 0)

    def test_boundary_values_minimum_positive_integers(self) -> None:
        """Verify handling of minimum allowed values (1 for positive ints, 0 for timestamp)."""
        min_order = Order(
            order_id=1,
            price=1,
            quantity=1,
            side=OrderSide.BUY,
            timestamp_ns=0,
        )
        decoded = decode_order(encode_order(min_order))
        self.assertEqual(decoded, min_order)

    def test_boundary_values_maximum_uint64(self) -> None:
        """Verify handling of maximum 64-bit unsigned integers (2^64 - 1)."""
        max_order = Order(
            order_id=UINT64_MAX,
            price=UINT64_MAX,
            quantity=UINT64_MAX,
            side=OrderSide.SELL,
            timestamp_ns=UINT64_MAX,
        )
        decoded = decode_order(encode_order(max_order))
        self.assertEqual(decoded, max_order)
        self.assertEqual(decoded.order_id, UINT64_MAX)
        self.assertEqual(decoded.price, UINT64_MAX)
        self.assertEqual(decoded.quantity, UINT64_MAX)
        self.assertEqual(decoded.timestamp_ns, UINT64_MAX)

    def test_decode_from_bytearray_and_memoryview(self) -> None:
        """Verify that decode_order accepts bytearray and memoryview buffers."""
        raw_bytes = encode_order(self.sample_buy_order)

        # Test with bytearray
        mutable_buffer = bytearray(raw_bytes)
        self.assertEqual(decode_order(mutable_buffer), self.sample_buy_order)

        # Test with memoryview
        view = memoryview(raw_bytes)
        self.assertEqual(decode_order(view), self.sample_buy_order)

    def test_manual_binary_layout_verification(self) -> None:
        """Verify exact byte structure, endianness, and field offsets."""
        order = Order(
            order_id=1,
            price=2,
            quantity=3,
            side=OrderSide.BUY,
            timestamp_ns=4,
        )
        encoded = encode_order(order)

        # In big-endian format:
        # Bytes  0-7:  order_id     = 1  -> 00 00 00 00 00 00 00 01
        # Bytes  8-15: price        = 2  -> 00 00 00 00 00 00 00 02
        # Bytes 16-23: quantity     = 3  -> 00 00 00 00 00 00 00 03
        # Byte  24:    side         = 1  -> 01
        # Bytes 25-32: timestamp_ns = 4  -> 00 00 00 00 00 00 00 04
        expected = (
            b"\x00\x00\x00\x00\x00\x00\x00\x01"
            b"\x00\x00\x00\x00\x00\x00\x00\x02"
            b"\x00\x00\x00\x00\x00\x00\x00\x03"
            b"\x01"
            b"\x00\x00\x00\x00\x00\x00\x00\x04"
        )
        self.assertEqual(encoded, expected)

    def test_encode_reject_invalid_type(self) -> None:
        """Verify that encoding non-Order objects raises TypeError."""
        invalid_inputs = [
            None,
            "order",
            123,
            {"order_id": 1, "price": 100, "quantity": 1, "side": 1, "timestamp_ns": 0},
            (1, 100, 1, 1, 0),
        ]
        for item in invalid_inputs:
            with self.assertRaises(TypeError):
                encode_order(item)  # type: ignore[arg-type]

    def test_encode_reject_out_of_range_integers(self) -> None:
        """Verify rejection when integers exceed the 64-bit unsigned limit (UINT64_MAX)."""
        overflow_val = UINT64_MAX + 1

        # order_id overflow
        with self.assertRaises(ValueError):
            encode_order(Order(overflow_val, 100, 10, OrderSide.BUY, 0))

        # price overflow
        with self.assertRaises(ValueError):
            encode_order(Order(1, overflow_val, 10, OrderSide.BUY, 0))

        # quantity overflow
        with self.assertRaises(ValueError):
            encode_order(Order(1, 100, overflow_val, OrderSide.BUY, 0))

        # timestamp_ns overflow
        with self.assertRaises(ValueError):
            encode_order(Order(1, 100, 10, OrderSide.BUY, overflow_val))

    def test_decode_reject_invalid_data_types(self) -> None:
        """Verify that passing non-bytes-like data to decode_order raises TypeError."""
        invalid_inputs = [
            None,
            "0" * 33,
            12345,
            True,
            False,
            [0] * 33,
        ]
        for item in invalid_inputs:
            with self.assertRaises(TypeError):
                decode_order(item)  # type: ignore[arg-type]

    def test_decode_reject_malformed_lengths(self) -> None:
        """Verify that byte buffers shorter or longer than 33 bytes raise ValueError."""
        valid_bytes = encode_order(self.sample_buy_order)

        # Empty bytes
        with self.assertRaises(ValueError):
            decode_order(b"")

        # Truncated (32 bytes)
        with self.assertRaises(ValueError):
            decode_order(valid_bytes[:-1])

        # Too short (10 bytes)
        with self.assertRaises(ValueError):
            decode_order(valid_bytes[:10])

        # Extra byte (34 bytes)
        with self.assertRaises(ValueError):
            decode_order(valid_bytes + b"\x00")

    def test_decode_reject_invalid_side_values(self) -> None:
        """Verify that byte records containing invalid side integers raise ValueError."""
        # Valid side values are 1 (BUY) and 2 (SELL).
        invalid_side_values = [0, 3, 4, 255]
        for bad_side in invalid_side_values:
            corrupted = struct.pack(
                ORDER_RECORD_FORMAT,
                100,
                15000,
                10,
                bad_side,
                1_000_000,
            )
            with self.assertRaises(ValueError) as ctx:
                decode_order(corrupted)
            self.assertIn("Invalid encoded order side value", str(ctx.exception))

    def test_decode_reject_unpacked_zero_fields_forbidden_by_order(self) -> None:
        """Verify that unpacked zeroes for positive-only fields raise ValueError."""
        # order_id = 0
        corrupted_order_id = struct.pack(
            ORDER_RECORD_FORMAT,
            0,
            15000,
            10,
            1,
            1_000_000,
        )
        with self.assertRaises(ValueError):
            decode_order(corrupted_order_id)

        # price = 0
        corrupted_price = struct.pack(
            ORDER_RECORD_FORMAT,
            100,
            0,
            10,
            1,
            1_000_000,
        )
        with self.assertRaises(ValueError):
            decode_order(corrupted_price)

        # quantity = 0
        corrupted_qty = struct.pack(
            ORDER_RECORD_FORMAT,
            100,
            15000,
            0,
            1,
            1_000_000,
        )
        with self.assertRaises(ValueError):
            decode_order(corrupted_qty)


if __name__ == "__main__":
    unittest.main()
