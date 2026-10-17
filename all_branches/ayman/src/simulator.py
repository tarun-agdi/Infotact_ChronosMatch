import asyncio
import time 
import random 
from .order import Order,OrderSide 

class MarketSimulator():   
    #intialization of variables
    def __init__(self):
         
        self.next_order = 1 #this is intentionally kept 1 as the constriants in the order file mentions that

        self.minimun_price = 100 # this is the sample price taken for testing 
        self.maximum_price = 1000 

        self.minimum_quatity = 1 #this is also taken for sample also
        self.maximum_quatity = 1000
        
    

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



if __name__== "__main__":
    simulator = MarketSimulator()
    simulator.order_generator()
    for i in range(5): #this is taken for the testing purposes only it would be replaced by the asyncio function 
        order = simulator.order_generator()
        print(order)

