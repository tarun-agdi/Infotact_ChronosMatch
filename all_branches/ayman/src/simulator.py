import asyncio
import time 
import random 
from .order import Order,OrderSide 

class MarketSimulator():   
    #intialization of variables
    def __init__(self,generation_interval=0.1):
         
        self.next_order = 1 #this is intentionally kept 1 as the constriants in the order file mentions that

        self.minimun_price = 100 # this is the sample price taken for testing 
        self.maximum_price = 1000 

        self.minimum_quatity = 1 #this is also taken for sample also
        self.maximum_quatity = 1000

        self.running = True
        self.generation_interval = generation_interval # this gives us the flexibility of making the time interval different according to the requirement 
        # else it will be with the interval of 0.1 only 
    

    def  order_generator(self):
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
        while max_order == 5: #this is the bugs which is needed to be fixed as the above commented loop is going for infinity 
            order = self.order_generator()
            print(order)
            await asyncio.sleep(self.generation_interval)


if __name__== "__main__":
    simulator = MarketSimulator()
    #simulator.run_simulator
    #for i in range(5): #this is taken for the testing purposes only it would be replaced by the asyncio function 
        #order = simulator.run_simulator()
        #print(order)
    asyncio.run(simulator.run_simulator(max_order=5))

