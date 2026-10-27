"""
Market Simulator for ChronosMatch.

Generates realistic mock orders and pushes them into the shared-memory RingBuffer.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from chronosmatch.order import Order, OrderSide


class MarketSimulator:
    """
    Market simulator generating a stream of buy and sell orders.
    """

    def __init__(self, ring_buffer: Any, generation_interval: float = 0.1) -> None:
        self.next_order: int = 1
        self.minimum_price: int = 100
        self.maximum_price: int = 1000
        self.minimum_quantity: int = 1
        self.maximum_quantity: int = 1000
        self.running: bool = True
        self.generation_interval: float = generation_interval
        self.ring_buffer: Any = ring_buffer

        # Compatibility aliases for attributes in reference code
        self.minimun_price: int = self.minimum_price
        self.minimum_quatity: int = self.minimum_quantity
        self.maximum_quatity: int = self.maximum_quantity

    def order_generator(self) -> Order:
        """Generate a single random Order instance."""
        order = Order(
            order_id=self.next_order,
            side=random.choice(list(OrderSide)),
            price=random.randint(self.minimum_price, self.maximum_price),
            quantity=random.randint(self.minimum_quantity, self.maximum_quantity),
            timestamp_ns=time.time_ns(),
        )
        self.next_order += 1
        return order

    async def run_simulator(self, max_order: int | None = 5) -> None:
        """
        Continuously generate orders and publish them to the ring buffer.
        """
        generated = 0

        while self.running and (max_order is None or generated < max_order):
            order = self.order_generator()

            # Push the generated order into the ring buffer.
            # If the buffer is full, wait until space becomes available.
            while self.running and not self.ring_buffer.push_order(order):
                await asyncio.sleep(0.001)

            if not self.running:
                break

            print(order)
            generated += 1

            await asyncio.sleep(self.generation_interval)

        self.running = False
        print(f"Total orders published: {generated}")

    def stop(self) -> None:
        """Signal the simulator to stop producing orders."""
        self.running = False
