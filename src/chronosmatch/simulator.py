import asyncio
import time
import random
from .order import Order,OrderSide

class MarketSimulator():
    #intialization of variables
    def __init__(self, ring_buffer, generation_interval=0.1):

        self.next_order = 1 #this is intentionally kept 1 as the constriants in the order file mentions that

        self.minimun_price = 100 # this is the sample price taken for testing
        self.maximum_price = 1000

        self.minimum_quatity = 1 #this is also taken for sample also
        self.maximum_quatity = 1000

        self.running = True
        self.generation_interval = generation_interval # this gives us the flexibility of making the time interval different according to the requirement
        # else it will be with the interval of 0.1 only

        self.ring_buffer = ring_buffer # this stores the ring buffer object provided by the coordinator


    def order_generator(self):
        order=Order(
        order_id = self.next_order,
        side = random.choice(list(OrderSide)),
        price = random.randint(self.minimun_price,self.maximum_price),
        quantity = random.randint(self.minimum_quatity,self.maximum_quatity),
        timestamp_ns = time.time_ns()
        )
        self.next_order += 1
        return order

    async def run_simulator(self,max_order=5):
        generated = 0

        #while self.running and (max_order is None or generated < max_order ) :
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

    def stop(self):
        self.running = False


if __name__== "__main__":
    # The coordinator creates the shared lock and ring buffer.
    # from here we should make it in another file as its causing import clashes
    # which would be better for the overall structure of the project
    import multiprocessing
    from pathlib import Path
    from ayman.src import ring_buffer
    from ayman.src import order_codec
    from .ring_buffer import RingBuffer
    from .order_codec import ORDER_RECORD_SIZE

    lock = multiprocessing.Lock()

    ring_buffer = RingBuffer.create(
        filepath=Path("data/chronosmatch_buffer.bin"),
        capacity=1024,
        slot_size=ORDER_RECORD_SIZE,
        lock=lock,
    )

    simulator = MarketSimulator(
        ring_buffer=ring_buffer,
        generation_interval=0.1
    )

    #simulator.run_simulator
    #for i in range(5): #this is taken for the testing purposes only it would be replaced by the asyncio function
        #order = simulator.run_simulator()
        #print(order)

    try:
        asyncio.run(simulator.run_simulator(max_order=1000))
    except KeyboardInterrupt:
        simulator.stop()
        print(f"Market Simulator stopped.")
    finally:
        ring_buffer.close()
