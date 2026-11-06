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