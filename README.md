# ChronosMatch — High-Performance Trading Engine

ChronosMatch is a terminal-based high-performance trading engine designed to simulate financial market activity, process incoming buy and sell orders, and execute trades efficiently using price-time priority.

The project explores asynchronous programming, zero-copy inter-process communication (IPC), shared-memory management, optimized order matching using Python and Cython, and real-time performance monitoring.

The primary goal is to understand how high-performance trading systems handle large volumes of incoming orders while maintaining matching correctness, low latency, and efficient resource utilization.

---

## 🎯 Project Objectives

- Simulate a continuous stream of mock buy and sell orders.
- Implement a Limit Order Book (LOB) using price-time priority.
- Develop an efficient order-matching engine.
- Implement zero-copy IPC using `mmap`.
- Use binary message serialization with Python's `struct` module.
- Explore asynchronous market simulation using `asyncio`.
- Accelerate order matching using Cython.
- Monitor throughput, latency, and execution activity.
- Implement asynchronous trade persistence.
- Detect large incoming orders (Whale Orders).
- Validate functionality through automated testing and benchmarking.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core implementation |
| asyncio | Asynchronous market simulation |
| mmap | Shared-memory communication |
| struct | Binary message serialization |
| Cython | Matching-engine optimization |
| pytest | Automated testing |
| pytest-asyncio | Asynchronous testing |
| curses | Terminal dashboard |
| SQLite / Persistent Storage | Planned trade persistence |
| Git & GitHub | Version control and collaboration |

**Note:** `asyncio`, `mmap`, and `struct` are part of Python's standard library.

---

## 🏗️ System Architecture

ChronosMatch follows a modular architecture consisting of the following components:

### 1. Market Simulator

- Generates mock buy and sell orders.
- Uses asynchronous programming through `asyncio`.
- Produces a continuous stream of market activity.
- Integrates with the ring buffer for order communication.

### 2. Zero-Copy IPC

- Uses memory-mapped files through `mmap`.
- Implements binary serialization using `struct`.
- Uses a ring buffer to transfer order messages.
- Reduces unnecessary data copying between components.

### 3. Order Book

- Maintains separate BUY and SELL sides.
- Organizes orders according to their prices.
- Supports price-time priority.
- Maintains resting and partially filled orders.

### 4. Matching Engine

- Processes incoming orders.
- Checks whether incoming buy and sell orders can match.
- Executes trades when compatible orders are found.
- Generates trade records.
- Explores Cython-based optimization for performance-critical operations.

### 5. Monitoring and Dashboard

- Displays market activity in the terminal.
- Tracks processed orders and executed trades.
- Provides a real-time view of engine activity.
- Supports performance monitoring.

### 6. Trade Persistence (Week 4)

- Transfers executed trades to an asynchronous processing queue.
- Uses a background worker to handle storage operations.
- Maintains historical trade records.
- Keeps database operations outside the critical matching path.

---

## 📁 Project Structure

The following represents the organized target structure of the project, incorporating the modules developed during the implementation phases.

```text
ChronosMatch/
│
├── src/
│   └── chronosmatch/
│       ├── __init__.py
│       │
│       ├── order.py
│       ├── trade.py
│       ├── order_book.py
│       ├── matching_engine.py
│       ├── matching_engine_cy.pyx
│       │
│       ├── ring_buffer.py
│       ├── order_codec.py
│       ├── simulator.py
│       │
│       ├── dashboard.py
│       ├── run_pipeline.py
│       │
│       ├── trade_persistence.py
│       └── whale_detector.py
│
├── tests/
│   ├── test_order.py
│   ├── test_matching_engine.py
│   ├── test_ring_buffer.py
│   ├── test_order_codec.py
│   ├── test_simulator.py
│   ├── test_trade_persistence.py
│   └── test_whale_detector.py
│
├── benchmarks/
│   └── benchmark_matching_engine.py
│
├── data/
│   └── chronosmatch_buffer.bin
│
├── docs/
│   ├── architecture.md
│   └── trade_persistence.md
│
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── Dockerfile
└── README.md
```

**Note:** This is the consolidated target structure. Some Week 4 modules and tests are planned additions, and generated Cython files and runtime data should not be treated as required source files.

---

# 📅 Development Progress — Week by Week

## Week 1 — Foundation and Zero-Copy IPC

**Objective:** Establish the project foundation and implement efficient communication between the market simulator and processing components.

### Work Completed

1. Established the initial project structure.
2. Created the order representation using Python.
3. Implemented the ring buffer.
4. Explored memory-mapped files using `mmap`.
5. Implemented binary message encoding and decoding using `struct`.
6. Developed the asynchronous market simulator.
7. Integrated the simulator with the ring buffer.

### My Contributions

- Worked on the ring buffer implementation.
- Developed the order serialization and deserialization flow.
- Integrated the ring buffer with the market simulator.
- Worked on asynchronous order generation.
- Debugged module imports and project structure.

### Key Concepts Learned

- Memory-mapped files.
- Zero-copy communication.
- Binary serialization.
- Asynchronous programming.
- Producer-consumer architecture.

---

## Week 2 — Order Book and Matching Engine

**Objective:** Develop the core trading functionality and establish the order-matching architecture.

### Work Completed

1. Developed the Limit Order Book foundation.
2. Implemented separate BUY and SELL sides.
3. Established the matching-engine structure.
4. Implemented order-crossing checks.
5. Worked on price-time priority.
6. Implemented trade generation.
7. Started exploring Cython for matching-engine optimization.
8. Worked on matching-engine testing and latency monitoring.

### My Contributions

- Worked on the Python matching-engine implementation.
- Developed the order-book integration.
- Worked on buy and sell order processing.
- Implemented and debugged matching logic.
- Worked on trade record generation.
- Tested matching scenarios and corrected integration issues.

### Key Concepts Learned

- Limit Order Book.
- Price-time priority.
- Order matching.
- Trade execution.
- Bid and ask management.
- Matching-engine architecture.

---

## Week 3 — Optimization and Integration

**Objective:** Improve matching-engine performance and integrate the system components into a unified execution pipeline.

### Work Completed

1. Continued Cython-based matching-engine development.
2. Worked on separating matching responsibilities into independent components.
3. Improved matching-engine integration.
4. Developed the execution pipeline.
5. Worked on a terminal-based monitoring dashboard using `curses`.
6. Added dashboard metrics for order and trade activity.
7. Worked on integration and import-related debugging.
8. Prepared matching-engine testing and benchmarking components.

### My Contributions

**Matching Engine and Integration**

- Worked on the matching-engine execution flow.
- Integrated the order book, simulator, and matching components.
- Worked on order-crossing checks and trade generation.
- Debugged package imports and module dependencies.
- Worked on integrating the execution pipeline.

**Terminal Dashboard**

- Developed a terminal-based dashboard using Python's `curses` module.
- Created a structured terminal interface.
- Added order and trade activity indicators.
- Worked on displaying engine status and execution metrics.
- Worked on connecting dashboard functionality with the execution pipeline.

**Testing and Performance**

- Worked on matching-engine test cases.
- Prepared benchmarking components.
- Investigated integration and runtime issues.
- Worked on Cython setup and integration.

### Key Concepts Learned

- Cython optimization.
- Matching-engine integration.
- Terminal-based monitoring.
- Performance measurement.
- Modular software architecture.
- Debugging multi-module Python applications.

---

## Week 4 — Persistence and Final Refinement

**Objective:** Improve system reliability and refine the terminal dashboard.

Week 4 focuses on two major development areas.

### Task 1: Asynchronous Trade Persistence

- Develop an asynchronous trade-processing queue.
- Transfer executed trade records from the matching engine.
- Implement a background persistence worker.
- Save executed trades to persistent storage.
- Ensure storage operations do not block the matching engine.
- Test trade storage and retrieval.

### Task 2: Whale Order Detection

- Identify unusually large incoming orders.
- Establish a configurable order-size threshold.
- Develop a whale-order detection component.
- Integrate detection information with the terminal dashboard.
- Highlight large orders visually.

### Final Integration

- Integrate the persistence worker.
- Integrate whale-order detection.
- Refine terminal dashboard updates.
- Perform end-to-end testing.
- Evaluate performance and reliability.

**Status:** Week 4 implementation is in progress.

---

# ⚙️ Getting Started

## Prerequisites

- Python 3.11 or later
- Git
- Visual Studio Code or another Python-compatible editor
- Cython and a compatible C compiler for the compiled matching-engine component

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd ChronosMatch
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Build the Cython extension

Run the project's configured build command after setting up the Cython build configuration.

---

# ▶️ Running the Project

The execution pipeline coordinates the market simulator, ring buffer, and matching engine.

From the repository root, use the configured pipeline entry point:

```bash
python run_pipeline.py
```

The exact command should match the final location of the pipeline entry point.

---

# 🧪 Testing

Run the automated test suite:

```bash
python -m pytest -v
```

The tests should validate:

- Order creation and validation.
- Order-book operations.
- Price-time priority.
- Matching correctness.
- Ring buffer operations.
- Binary message encoding and decoding.
- Asynchronous simulator behavior.
- Trade persistence.
- Whale-order detection.

Only tests that have been implemented and executed should be reported as passing.

---

# 📊 Performance Evaluation

ChronosMatch evaluates performance using the following metrics:

| Metric | Description |
|---|---|
| Throughput | Number of orders processed per second |
| Latency | Time taken to process an order |
| Matching Correctness | Accuracy of price-time priority |
| IPC Efficiency | Communication overhead |
| Reliability | Consistent behavior under different order volumes |

Benchmarking should be performed using repeatable workloads.

Actual performance results should be recorded after execution. Estimated figures should never be reported as measured results.

---

# 🔄 Collaboration Workflow

The project uses Git and GitHub for collaborative development.

1. Each member works on an individual development branch.
2. Features are implemented independently.
3. Changes are committed with meaningful commit messages.
4. Branches are pushed to the remote repository.
5. Pull requests are reviewed before integration.
6. Integrated code is tested before merging into the main branch.

Shared interfaces and message formats must remain consistent to avoid integration conflicts.

---

# 🚧 Future Improvements

- Further optimize the Cython matching engine.
- Improve high-volume order processing.
- Refine asynchronous trade persistence.
- Improve dashboard visualization.
- Add more comprehensive integration tests.
- Evaluate matching performance under heavy workloads.
- Improve error handling and recovery mechanisms.

---

# 👥 Team Contributions

ChronosMatch is developed collaboratively, with responsibilities distributed across system components.

My primary areas of contribution include:

- Ring buffer and zero-copy IPC.
- Asynchronous market simulation.
- Order serialization and deserialization.
- Python matching-engine development.
- Limit Order Book integration.
- Trade generation and execution flow.
- Matching-engine integration and debugging.
- Terminal dashboard development.
- Testing and performance evaluation.

---

# 📄 License

An appropriate license will be added after confirming the project's distribution requirements.

---

**ChronosMatch — Exploring the Engineering Behind High-Performance Trading Systems.**