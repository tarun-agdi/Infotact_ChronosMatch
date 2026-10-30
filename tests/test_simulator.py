"""Unit tests for the MarketSimulator."""

import asyncio
import multiprocessing
import pytest
from pathlib import Path

from chronosmatch.ipc.ring_buffer import RingBuffer
from chronosmatch.order import Order, OrderSide
from chronosmatch.order_codec import ORDER_RECORD_SIZE
from chronosmatch.simulator import MarketSimulator


def test_market_simulator_order_generator(tmp_path):
    lock = multiprocessing.Lock()
    rb = RingBuffer.create(
        filepath=tmp_path / "sim_test.bin",
        capacity=16,
        slot_size=ORDER_RECORD_SIZE,
        lock=lock,
    )
    sim = MarketSimulator(ring_buffer=rb, generation_interval=0)

    order1 = sim.order_generator()
    assert isinstance(order1, Order)
    assert order1.order_id == 1
    assert order1.side in (OrderSide.BUY, OrderSide.SELL)
    assert sim.minimun_price <= order1.price <= sim.maximum_price
    assert sim.minimum_quatity <= order1.quantity <= sim.maximum_quatity

    order2 = sim.order_generator()
    assert order2.order_id == 2
    rb.close()


def test_market_simulator_run_and_stop(tmp_path):
    lock = multiprocessing.Lock()
    rb = RingBuffer.create(
        filepath=tmp_path / "sim_test2.bin",
        capacity=16,
        slot_size=ORDER_RECORD_SIZE,
        lock=lock,
    )
    sim = MarketSimulator(ring_buffer=rb, generation_interval=0)

    async def run():
        await sim.run_simulator(max_order=5)

    asyncio.run(run())
    assert rb.count() == 5
    popped = rb.pop_order()
    assert popped is not None
    assert popped.order_id == 1
    rb.close()
