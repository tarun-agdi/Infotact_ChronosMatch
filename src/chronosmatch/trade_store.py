"""1. Algorithm for trade_store.py
Purpose: To store executed trades permanently in an SQLite database.
Class: TradeStore
Algorithm 1: __init__()
1. Accept the database file path.
2. Establish a connection with the SQLite database.
3. Create a cursor to execute SQL queries.
4. Call the _create_table() function.

Algorithm 2: _create_table()
1. Create a SQL query to create a table named trades.
2. Define the following columns:
   - id – Primary key.
   - buy_order_id – Buy order ID.
   - sell_order_id – Sell order ID.
   - price – Executed price.
   - quantity – Executed quantity.
   - timestamp_ns – Execution timestamp.
3. Execute the SQL query.
4. Commit the changes.

Algorithm 3: save_trades(trades)
1. Accept a list of executed trades.
2. Check whether the list is empty.
3. If empty, return.
4. Iterate through the list of trades.
5. Extract the required attributes from each Trade object.
6. Prepare the values for database insertion.
7. Execute a batch INSERT query using executemany().
8. Commit the transaction.
9. Return after successful insertion.

Algorithm 4: get_trades(limit=100)
1. Accept the maximum number of trades to retrieve.
2. Execute a SELECT query on the trades table.
3. Retrieve the latest trades, ordered by ID in descending order.
4. Return the retrieved records.

Algorithm 5: close()
1. Check whether the database connection is open.
2. Close the database connection.
3. Release the database resources."""

import sqlite3
from pathlib import Path


class TradeStore:

    def __init__(self, db_path="data/trades.db") -> None:

        # Ensure the database directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Establish database connection
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()

        # Create trades table
        self._create_table()

    def _create_table(self):

        query = """
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            buy_order_id INTEGER NOT NULL,
            sell_order_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            timestamp_ns INTEGER NOT NULL
        );
        """

        self.cursor.execute(query)
        self.connection.commit()

    def save_trades(self, trades):

        # Check whether the list is empty
        if not trades:
            return

        values = []

        # Extract trade information
        for trade in trades:

            exe_trade = (
                trade.buy_order_id,
                trade.sell_order_id,
                trade.price,
                trade.quantity,
                trade.timestamp_ns
            )

            values.append(exe_trade)

        query = """
        INSERT INTO trades (
            buy_order_id,
            sell_order_id,
            price,
            quantity,
            timestamp_ns
        )
        VALUES (?, ?, ?, ?, ?);
        """

        try:
            self.cursor.executemany(query, values)
            self.connection.commit()

        except sqlite3.Error:
            self.connection.rollback()
            raise

    def get_trades(self, limit=100):

        if limit <= 0:
            raise ValueError("Limit must be greater than zero")

        query = """
        SELECT * FROM trades
        ORDER BY trade_id DESC
        LIMIT ?;
        """

        self.cursor.execute(query, (limit,))

        return self.cursor.fetchall()

    def close(self):

        if self.connection:
            self.cursor.close()
            self.connection.close()
            self.connection = None
