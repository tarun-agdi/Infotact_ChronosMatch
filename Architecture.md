# ChronosMatch — System Architecture

## Zero-Copy High-Frequency Trading Engine

**Document Version:** 1.0 — Proposed Architecture
**Project Type:** High-performance trading simulation
**Primary Technologies:** Python, asyncio, Cython, mmap, struct, SQLite

---

## 1. Introduction

ChronosMatch is a high-performance trading simulation project designed to explore how orders can be generated, transferred, processed, and monitored with minimal latency.

In a conventional Python application, transferring large numbers of orders between processes can introduce overhead through object creation, serialization, copying, and inter-process communication. These costs become important when the system must process a large volume of orders in a short period.

ChronosMatch addresses this challenge through a combination of asynchronous programming, shared memory, and compiled matching logic.

Python's asyncio framework is responsible for generating and coordinating simulated orders. A memory-mapped ring buffer transfers fixed-size order records between processes. The matching engine uses Cython to implement the limit order book and matching operations. A terminal dashboard displays performance statistics, while a separate persistence worker stores completed trades.

The primary objective is to build a system that is not only fast, but also correct, measurable, and understandable.

## 2. Project Objectives

The project has six principal objectives:

1. **Asynchronous order generation:** Simulate a continuous stream of BUY and SELL orders without unnecessarily blocking the event loop.
2. **Efficient inter-process communication:** Use shared memory and a ring buffer to reduce communication overhead.
3. **High-performance matching:** Implement a limit order book using Cython and apply price-time priority.
4. **Low-latency monitoring:** Measure order-processing time and display relevant metrics in a terminal interface.
5. **Trade persistence:** Store completed executions and audit information outside the critical matching path.
6. **Performance verification:** Validate correctness and measure throughput and latency under controlled workloads.

The performance targets in the project brief are objectives to benchmark, not results that can be assumed in advance.

## 3. Overall System Architecture

ChronosMatch is divided into five principal layers.

**Layer 1 — Order Generation:** Produces realistic simulated market activity.

**Layer 2 — Shared-Memory Communication:** Transfers order records between the producer and consumer.

**Layer 3 — Matching Engine:** Maintains the order book and determines whether incoming orders can execute.

**Layer 4 — Monitoring:** Collects performance statistics and presents the system's current state.

**Layer 5 — Persistence:** Stores execution records for later inspection and reconciliation.

### Architecture overview

The following diagram shows how these components interact.

```text
                 CHRONOSMATCH
          ZERO-COPY TRADING ENGINE

  ┌─────────────────────────────────────┐
  │       1. MARKET SIMULATOR            │
  │       Python + asyncio               │
  │                                      │
  │  Generates BUY and SELL orders       │
  │  Assigns IDs, prices and quantities  │
  └──────────────────┬──────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────┐
  │       2. ORDER ENCODER               │
  │       Python + struct                │
  │                                      │
  │  Validates and encodes fixed-size    │
  │  binary order records                │
  └──────────────────┬──────────────────┘
                     │
                     ▼
  ╔═════════════════════════════════════╗
  ║       SHARED-MEMORY IPC              ║
  ║       mmap + Ring Buffer             ║
  ║                                      ║
  ║  Producer publishes order records    ║
  ║  Consumer reads available records    ║
  ╚══════════════════╤══════════════════╝
                     │
                     ▼
  ┌─────────────────────────────────────┐
  │       3. MATCHING ENGINE             │
  │       Cython + Limit Order Book      │
  │                                      │
  │  Applies price-time priority         │
  │  Executes matches and partial fills  │
  └──────────────────┬──────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────┐
  │       EXECUTION EVENTS               │
  │                                      │
  │  Trade price, quantity and metadata  │
  └───────────────┬───────────┬─────────┘
                  │           │
                  ▼           ▼
        ┌────────────────┐  ┌────────────────┐
        │ 4. MONITORING   │  │ 5. PERSISTENCE │
        │ Python curses  │  │ SQLite worker  │
        │                │  │                │
        │ Latency, rates │  │ Trade records  │
        │ and book state │  │ and audit data │
        └────────────────┘  └────────────────┘
```

The order-processing path runs from the simulator through the encoder and shared-memory buffer to the matching engine. Monitoring and persistence operate as supporting functions and must not unnecessarily block this path.

## 4. Component 1 — Asynchronous Market Simulator

The market simulator is responsible for creating the workload consumed by the rest of the system.

It generates simulated BUY and SELL orders with attributes such as order ID, price, quantity, side, and creation timestamp.

Python's `asyncio` framework allows the simulator to cooperate with other asynchronous tasks. For example, it can pause briefly between batches of orders to allow other scheduled tasks to run.

This is important because the simulator may eventually need to coordinate order production, performance reporting, and shutdown handling.

The simulator must also ensure that generated orders follow the agreed data contract. Order IDs should increase consistently, quantities must be valid, and timestamps must be recorded using a clearly defined clock.

The simulator should support configurable workloads so that the team can compare performance under different order-generation rates.

**Expected output:** A stream of valid order records ready for encoding and publication to shared memory.

## 5. Component 2 — Order Encoding and Shared-Memory IPC

The communication layer transfers orders from the producer to the matching engine.

### 5.1 Why shared memory?

Passing ordinary Python objects directly between processes can require serialization and deserialization. Depending on the mechanism used, it can also involve additional memory allocations and data copying.

ChronosMatch uses a memory-mapped region, created using `mmap`, to provide a shared area that participating processes can access.

The `struct` module provides a way to encode order fields into a fixed binary representation. This makes each record's layout predictable and allows the consumer to interpret the fields without reconstructing a general-purpose serialized object.

The design aims to reduce copying and communication overhead. The exact implementation must still be benchmarked to determine its actual performance.

### 5.2 How the ring buffer works

A ring buffer is a bounded collection of slots arranged conceptually in a circle. Each slot holds one fixed-size order record.

The producer writes a record into an available slot and publishes it. The consumer reads the published record, processes it, and releases the slot so that it can be reused.

When the producer reaches the final slot, it wraps around to the beginning of the buffer.

The system must distinguish between an empty buffer, a full buffer, and a buffer containing unread records. It must never silently overwrite an order that the consumer has not yet processed.

### Ring-buffer operation

```text
                PRODUCER
                   │
                   ▼
           Prepare order record
                   │
                   ▼
            Find available slot
                   │
                   ▼
             Write the record
                   │
                   ▼
              Publish slot
                   │
                   ▼
        ┌────────────────────────┐
        │   SHARED RING BUFFER   │
        │                        │
        │  [0] [1] [2] ... [N-1] │
        └────────────┬───────────┘
                     │
                     ▼
             Consumer reads
                     │
                     ▼
             Process the order
                     │
                     ▼
              Release slot
                     │
                     └──────► Slot becomes reusable
```

### 5.3 Data contract

The initial order record is expected to contain:

| Field | Purpose |
|---|---|
| `order_id` | Identifies an order |
| `price` | Represents the order price using integer ticks or fixed-point units |
| `quantity` | Represents the number of units |
| `side` | Indicates BUY or SELL |
| `timestamp_ns` | Provides a monotonic timing reference |

Before implementation, the team must agree on the field widths, byte order, binary layout, buffer capacity, synchronization method, and behavior when the buffer is full.

The first implementation should preferably use a single producer and a single consumer. This keeps the initial synchronization model simpler.

**Expected output:** A reliable stream of fixed-size records available to the matching engine.

## 6. Component 3 — Cython Matching Engine

The matching engine is the core processing component of ChronosMatch.

Its responsibility is to receive an order, compare it with the current order book, execute eligible matches, update quantities, and record the resulting execution events.

Cython is used to compile performance-sensitive code and reduce the overhead associated with repeatedly executing Python-level operations. The benefit depends on how the engine is implemented; simply changing a file extension to `.pyx` does not automatically guarantee high performance.

### 6.1 What is a limit order book?

A limit order book stores outstanding BUY and SELL orders that have not yet been completely executed.

The BUY side is called the **bid side**, and the SELL side is called the **ask side**.

For example, the book might contain:

| Side | Price | Available quantity |
|---|---:|---:|
| BUY | 100 | 50 |
| BUY | 99 | 80 |
| SELL | 101 | 40 |
| SELL | 102 | 70 |

The highest BUY price is the best bid, and the lowest SELL price is the best ask.

In this example, the best bid is 100 and the best ask is 101. A BUY limit order at 100 would not cross the current best ask of 101, so it would normally rest in the book.

A BUY order priced at 101 or higher could cross the best ask, subject to the chosen execution-price rules.

### 6.2 Price-time priority

The matching engine follows price-time priority.

**Price priority** means that the most competitive available price is considered first. For BUY orders, higher bids have priority. For SELL orders, lower asks have priority.

**Time priority** means that when orders have the same price, the earlier eligible order is considered first.

When a new order crosses the opposite side of the book, the engine attempts to execute it against the best eligible resting order. If the incoming order has additional quantity remaining, the engine continues checking the next eligible order.

If the order cannot execute completely, the remaining quantity may be added to the book if the project's order rules permit it.

### Matching workflow

```text
             Incoming order
                    │
                    ▼
           Determine order side
                    │
                    ▼
          Inspect opposite book side
                    │
                    ▼
          Does the price cross?
              /           \
            YES            NO
             │              │
             ▼              ▼
      Execute eligible    Rest order
      quantity            if permitted
             │              │
             ▼              │
      Update quantities     │
             │              │
             ▼              │
      Quantity remaining?   │
          /       \         │
        YES        NO       │
         │          │       │
         └───►      ▼       │
               Complete     │
                 order      │
                   └────────┘
                        │
                        ▼
                Update book state
```

The implementation must define the execution-price rule, handling of partial fills, and behavior for unfilled quantities. These rules should be tested before performance optimization.

**Expected output:** An updated order book and, when applicable, execution events containing the details of completed trades.

## 7. Component 4 — Monitoring and Terminal Dashboard

ChronosMatch uses a terminal-based dashboard built with Python's `curses` library.

The dashboard provides visibility into both the system's current trading state and its performance. It should help the team determine whether orders are being processed correctly and whether the engine is meeting its performance targets.

The dashboard can display:

- Total orders generated and processed.
- Order-processing throughput.
- Number of completed trades.
- Best bid, best ask, and spread.
- Available quantity at selected price levels.
- Recent executions.
- Median, p95, p99, and maximum measured latency.
- Ring-buffer occupancy and rejected-order counts.

### Monitoring data flow

```text
        Matching Engine
               │
               ▼
        Metrics Collection
               │
               ▼
        Metrics Snapshot
               │
               ▼
        Terminal Dashboard
               │
               ▼
        Live Performance View
```

The dashboard should read lightweight metrics or snapshots rather than repeatedly inspecting internal engine state in a way that disrupts matching.

Latency measurements must also be defined carefully. For example, matching latency measures the time spent processing an order, while end-to-end latency includes the time taken from order creation through execution-event generation. These values are not interchangeable.

**Expected output:** A live terminal view that helps the team understand throughput, latency, and order-book behavior.

## 8. Component 5 — Persistence and Audit

The persistence component stores completed trade records for later inspection.

The matching engine should not wait for a database write every time a trade executes. Instead, execution events should be handed off to a separate worker, which can write records in batches.

SQLite is the initial persistence option because it is relatively simple to integrate into a local simulation. ClickHouse can be evaluated later if the project needs more extensive analytical storage.

The persisted records may include the execution identifier, participating order IDs, execution price, executed quantity, and relevant timestamps.

The persistence layer should also make it possible to reconcile stored trades with execution events produced by the matching engine.

### Persistence workflow

```text
        Matching Engine
               │
               ▼
        Execution Event
               │
               ▼
        Background Worker
               │
               ▼
        Batch Database Writes
               │
               ▼
        SQLite Trade Ledger
               │
               ▼
        Audit and Verification
```

The handoff mechanism must have a defined capacity and failure policy. The system must not silently lose execution events if the worker falls behind or the application shuts down.

**Expected output:** A persistent record of completed executions that can be used to verify the correctness of the simulation.

## 9. Performance Measurement and Optimization

Performance measurement is a central part of ChronosMatch. The project should demonstrate its results through repeatable benchmarks rather than relying on assumptions about the speed of Python, Cython, or shared memory.

The `time.perf_counter_ns()` function can be used to measure elapsed time at nanosecond resolution.

The team should distinguish between three measurements:

**Ingress-to-engine latency:** The elapsed time from the order's creation timestamp to the engine's consumption of that order.

**Matching latency:** The time taken by the matching engine to process an order.

**End-to-end execution latency:** The elapsed time from order creation until the resulting execution event is generated.

Throughput should be reported as the number of successfully processed orders per second over a defined measurement interval.

### Performance targets from the project brief

| Target | Intended validation |
|---|---|
| 100,000 mock orders per second | Measure simulator throughput |
| One million orders | Validate IPC integrity and correctness |
| Under 50 microseconds | Evaluate matching latency for the specified use case |
| Sub-millisecond execution | Evaluate the broader execution objective |

These are project goals, not guaranteed outcomes. Results should include the test environment, workload, warm-up procedure, and latency percentiles. The team should also verify that the measured workload is representative and that the reported numbers refer to the same latency definition.

Optimization should follow correctness testing. First establish that the ring buffer does not lose or corrupt records and that the matching engine produces correct results. Then profile the implementation and optimize the most expensive operations.

## 10. Proposed Repository Structure

The following structure represents a possible organization for the project. It should be adapted to the repository's existing files and the team's agreed implementation plan.

```text
chronosmatch/
├── README.md
├── ARCHITECTURE.md
├── pyproject.toml
├── requirements.txt
├── src/
│   └── chronosmatch/
│       ├── __init__.py
│       ├── order.py
│       ├── simulator.py
│       ├── ipc/
│       │   ├── __init__.py
│       │   ├── layout.py
│       │   └── ring_buffer.py
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── order_book.pyx
│       │   └── matching.py
│       ├── monitoring/
│       │   └── dashboard.py
│       ├── persistence/
│       │   └── writer.py
│       └── runtime.py
└── tests/
    ├── test_order.py
    ├── test_ring_buffer.py
    ├── test_matching.py
    └── test_performance_smoke.py
```

The existing `order.py`, tests, and other teammate-created files should not be moved or renamed until their imports, package configuration, and responsibilities have been reviewed.

## 11. Testing and Validation Strategy

Testing must establish that the system is correct before it is judged on speed.

### Order validation

Verify that order IDs, prices, quantities, sides, and timestamps conform to the agreed contract. Test both valid and invalid records.

### Ring-buffer validation

Verify that the producer and consumer exchange records correctly across process boundaries. Test empty and full buffers, wraparound, synchronization, and graceful shutdown. A large-volume test should confirm that every expected order is accounted for.

### Matching-engine validation

Test non-crossing orders, crossing orders, price priority, time priority, partial fills, and matching across multiple price levels. Check that executed quantities and remaining quantities are consistent.

### Monitoring validation

Verify that displayed counters and latency statistics agree with the underlying measurements. Confirm that dashboard refreshes do not significantly disrupt the processing path.

### Persistence validation

Verify that execution events are stored correctly, that records can be reconciled with engine output, and that shutdown does not silently discard pending events.

### Performance validation

Run repeatable tests under documented conditions. Compare the baseline implementation with optimized versions and report both throughput and latency distributions.

## 12. Development Roadmap

The project can be organized into five implementation phases.

**Phase 1 — Order Contract and Simulator**

Finalize the order representation, ensure order IDs increase correctly, generate valid mock orders, and establish a reliable workload.

**Phase 2 — Shared-Memory IPC**

Implement the memory-mapped ring buffer and binary record layout. Validate communication between processes and test high-volume data integrity.

**Phase 3 — Cython Matching Engine**

Implement the limit order book, apply price-time priority, and verify matching behavior through deterministic tests.

**Phase 4 — Monitoring and Performance Analysis**

Add the terminal dashboard, collect latency measurements, and expose throughput and order-book statistics.

**Phase 5 — Persistence and Integration**

Add the background persistence worker, integrate the complete pipeline, test graceful shutdown, and conduct end-to-end benchmarks.

The project should conclude with a correctness review, documented benchmark results, and a demonstration of the complete order-processing pipeline.

## 13. Architecture Decisions Requiring Team Approval

The following decisions should be finalized before the corresponding components are considered stable:

1. Whether the initial ring buffer will use a single producer and a single consumer.
2. The exact binary order layout and protocol version.
3. The synchronization and memory-visibility mechanism for shared-memory access.
4. The policy for handling a full ring buffer.
5. The limit order book's data structures and execution-price rule.
6. The mechanism used to transfer metrics and execution events.
7. The persistence failure policy and shutdown procedure.
8. The dashboard's refresh rate and required statistics.
9. The benchmark methodology and acceptance criteria.

These decisions affect correctness, performance, and integration between teammates' components.

## 14. Scope and Limitations

ChronosMatch is a trading-engine simulation intended for experimentation and performance evaluation.

The initial scope includes simulated orders, shared-memory communication, a Cython-based matching engine, terminal monitoring, and trade persistence.

The initial scope does not include connectivity to a live stock exchange, real-money trading, a web frontend, a REST API, or a production trading deployment.

The architecture describes the intended system design. Actual latency, throughput, and reliability must be established by implementation and testing.

## 15. Conclusion

ChronosMatch brings together asynchronous order generation, memory-mapped communication, compiled matching logic, performance monitoring, and persistent trade records in one integrated system.

Each component has a distinct responsibility, while the shared order contract and execution-event model allow the components to work together.

The project's success should be judged by two equally important outcomes: **correct order matching and measurable performance improvements**. A reliable implementation, supported by reproducible benchmarks and clear documentation, will provide a stronger demonstration of the architecture than speed claims alone.
