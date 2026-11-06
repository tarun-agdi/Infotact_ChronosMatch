'''
2. Algorithm for trade_writer.py

Purpose: To asynchronously receive executed trades and send them to TradeStore for permanent storage.
Class: TradeWriter

Algorithm 1: __init__()
1. Accept a TradeStore object.
2. Initialize an asynchronous queue using asyncio.Queue.
3. Set the batch size (default 100).
4. Initialize a background task variable.
5. Initialize a flag to track whether the writer is running.

Algorithm 2: enqueue(trade)
1. Accept an executed Trade object.
2. Check whether the writer is accepting trades.
3. If it is not accepting trades, raise an error.
4. Add the trade to the asynchronous queue.
5. Return immediately without waiting for database writing.

Algorithm 3: start()
1. Check whether the writer is already running.
2. If already running, do not create another worker.
3. Mark the writer as running.
4. Create a background asyncio task.
5. Assign the task to the _run() function.

Algorithm 4: _run()
This is the main background worker.
1. Initialize an empty list to collect trades.
2. Continue running while the writer is active or pending trades remain.
3. Wait for a trade from the queue.
4. Add the received trade to the batch.
5. Check whether the batch size has reached the configured limit.
6. If the batch is full, call _flush().
7. If the batch is not full, continue collecting trades.
8. When shutdown is requested, flush all remaining trades.
9. Exit the worker.

Algorithm 5: _flush()
1. Check whether the batch contains trades.
2. If empty, return.
3. Send the batch to TradeStore.save_trades().
4. Execute the database operation using asyncio.to_thread() to avoid blocking the event loop.
5. Clear the batch after successful insertion.
6. Mark the corresponding queue items as completed using task_done().

Algorithm 6: stop()
1. Stop accepting new trades.
2. Wait for all queued trades to be processed.
3. Ensure the remaining partial batch is flushed.
4. Wait for the background task to finish.
5. Mark the writer as stopped.'''