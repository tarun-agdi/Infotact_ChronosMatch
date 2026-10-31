import asyncio

from chronosmatch.order import Order, OrderSide
from chronosmatch.simulator import MarketSimulator


class FakeRingBuffer:
    """A lightweight ring buffer substitute for simulator unit tests."""

    def __init__(self, fail_attempts=0, always_full=False):
        self.orders = []
        self.fail_attempts = fail_attempts
        self.always_full = always_full
        self.push_attempts = 0

    def push_order(self, order):
        self.push_attempts += 1

        if self.always_full:
            return False

        if self.push_attempts <= self.fail_attempts:
            return False

        self.orders.append(order)
        return True


def test_order_generator_creates_valid_order():
    buffer = FakeRingBuffer()
    simulator = MarketSimulator(buffer)

    order = simulator.order_generator()

    assert isinstance(order, Order)
    assert order.order_id == 1
    assert 100 <= order.price <= 1000
    assert 1 <= order.quantity <= 1000
    assert order.side in (OrderSide.BUY, OrderSide.SELL)
    assert order.timestamp_ns >= 0


def test_order_ids_are_sequential():
    buffer = FakeRingBuffer()
    simulator = MarketSimulator(buffer)

    orders = [simulator.order_generator() for _ in range(5)]

    ids = [order.order_id for order in orders]

    assert ids == [1, 2, 3, 4, 5]


def test_simulator_publishes_exact_number_of_orders():
    buffer = FakeRingBuffer()
    simulator = MarketSimulator(
        ring_buffer=buffer,
        generation_interval=0,
    )

    asyncio.run(simulator.run_simulator(max_order=5))

    assert len(buffer.orders) == 5
    assert simulator.running is False


def test_simulator_retries_when_buffer_is_full():
    # First two push attempts fail; subsequent attempts succeed.
    buffer = FakeRingBuffer(fail_attempts=2)

    simulator = MarketSimulator(
        ring_buffer=buffer,
        generation_interval=0,
    )

    asyncio.run(simulator.run_simulator(max_order=3))

    assert len(buffer.orders) == 3
    assert buffer.push_attempts == 5


def test_simulator_stops_when_stop_is_called():
    buffer = FakeRingBuffer(always_full=True)

    simulator = MarketSimulator(
        ring_buffer=buffer,
        generation_interval=0,
    )

    async def scenario():
        task = asyncio.create_task(
            simulator.run_simulator(max_order=None)
        )

        await asyncio.sleep(0.01)
        simulator.stop()

        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())

    assert buffer.orders == []
    assert simulator.running is False


def test_simulator_handles_zero_orders():
    buffer = FakeRingBuffer()

    simulator = MarketSimulator(
        ring_buffer=buffer,
        generation_interval=0,
    )

    asyncio.run(simulator.run_simulator(max_order=0))

    assert len(buffer.orders) == 0
    assert simulator.running is False
