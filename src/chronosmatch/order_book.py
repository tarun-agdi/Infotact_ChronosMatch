"""
Limit Order Book for ChronosMatch.

Stores buy and sell orders organized by price.
Matching logic will be implemented separately.
"""

from .order import Order, OrderSide


class OrderBook:
    """Stores buy and sell orders for the matching engine."""

    def __init__(self) -> None:
        self.bids: dict[int, list[Order]] = {}
        self.asks: dict[int, list[Order]] = {}

    def add_order(self, order: Order) -> None:
        """
        Add an order to the order book.

        Places BUY orders into bids and SELL orders into asks, keyed by price.
        If the price level does not exist, a new list is created for it.
        Orders at the same price level preserve FIFO (first-in, first-out) order.

        Args:
            order: The Order instance to add.

        Raises:
            TypeError: If order is not an instance of Order.
        """
        if not isinstance(order, Order):
            raise TypeError(
                f"order must be an instance of Order, got {type(order).__name__}"
            )

        target_book = self.bids if order.side == OrderSide.BUY else self.asks
        if order.price not in target_book:
            target_book[order.price] = []
        target_book[order.price].append(order)

    def best_bid(self) -> int | None:
        """
        Get the highest buy price in the order book.

        Returns:
            The highest price key in bids, or None if there are no bids.
        """
        if not self.bids:
            return None
        return max(self.bids)

    def best_ask(self) -> int | None:
        """
        Get the lowest sell price in the order book.

        Returns:
            The lowest price key in asks, or None if there are no asks.
        """
        if not self.asks:
            return None
        return min(self.asks)

    def remove_order(self, order_id: int) -> None:
        """
        Remove an order from the order book by its ID.

        Searches both the bids and asks sides for an order with the given ID
        and removes it without disturbing the FIFO order of other orders at
        the same price level. If the price level becomes empty after removal,
        that price level is cleaned up from the dictionary.
        If the order is not found, the method does nothing.

        Args:
            order_id: The unique identifier of the order to remove.

        Raises:
            TypeError: If order_id is not an integer.
            ValueError: If order_id is not a positive integer (> 0).
        """
        if isinstance(order_id, bool) or not isinstance(order_id, int):
            raise TypeError(
                f"order_id must be an integer, got {type(order_id).__name__}"
            )
        if order_id <= 0:
            raise ValueError(
                f"order_id must be a positive integer (> 0), got {order_id}"
            )

        for book in (self.bids, self.asks):
            for price, orders in list(book.items()):
                for i, order in enumerate(orders):
                    if order.order_id == order_id:
                        orders.pop(i)
                        if not orders:
                            del book[price]
                        return