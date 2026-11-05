'''# Trade Persistence

## Objective
Trade persistence ensures that all executed trades
are stored permanently for future reference.

## Workflow

1. Matching Engine generates executed trades.
2. Trades are passed to an asynchronous queue.
3. A background worker consumes trades from the queue.
4. The worker saves trades to persistent storage.
5. The matching engine continues processing orders
   without waiting for database operations.

## Key Components

- Trade Model: Stores trade information.
- Async Queue: Transfers trades between components.
- Persistence Worker: Processes trades in the background.
- Storage: Maintains executed trade history.

## Benefits

- Reduces database operations in the matching path.
- Maintains historical trade records.
- Separates matching logic from storage logic.
- Improves system responsiveness.'''

import asyncio
import sqlite3
from pathlib import Path


class TradePersistence:

    def __init__(self, db_path="data/trades.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(db_path)

        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buy_order_id INTEGER,
                sell_order_id INTEGER,
                price REAL,
                quantity INTEGER,
                timestamp REAL
            )
        """)

        self.connection.commit()

    def save_trade(self, trade):
        self.connection.execute("""
            INSERT INTO trades (
                buy_order_id,
                sell_order_id,
                price,
                quantity,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            trade.buy_order_id,
            trade.sell_order_id,
            trade.price,
            trade.quantity,
            trade.timestamp
        ))

    def save_trades(self, trades):
        for trade in trades:
            self.save_trade(trade)

        self.connection.commit()

    async def persist_trades(self, trades):
        await asyncio.to_thread(self.save_trades, trades)

    def close(self):
        self.connection.close()
