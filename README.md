# ChronosMatch — High-Performance Trading Engine

ChronosMatch is a zero-copy, high-frequency trading simulation engine designed to simulate market activity, transfer binary order records across process boundaries via shared memory, and execute orders with minimal latency. The system combines an asynchronous order generator, a memory-mapped circular ring buffer, a limit order book with compiled Cython acceleration, an interactive terminal dashboard, and an end-to-end processing pipeline.

---

## 🎯 Project Objectives

- **Asynchronous Order Generation**: Simulate high-frequency mock buy and sell order streams without blocking the event loop using `asyncio`.
- **Compact Binary Serialization**: Encode and decode fixed-size 33-byte binary order records using Python's standard-library `struct` module.
- **Zero-Copy Shared-Memory IPC**: Facilitate high-throughput inter-process communication between producers and consumers using memory-mapped files (`mmap`) with circular modulo indexing.
- **High-Performance Order Matching**: Maintain a limit order book using price-time priority (FIFO), implemented in pure Python with compiled Cython acceleration.
- **Deterministic Parity**: Guarantee 100% numerical and state parity between the pure Python reference implementation and the compiled Cython matching engine.
- **Real-Time Terminal Monitoring**: Visualize order throughput, executed trades, matching engine latency (μs), and live trade feeds via an interactive curses terminal dashboard.
- **Controlled Benchmarking**: Profile and measure throughput, latency, and speedups under controlled synthetic and multi-process workloads.
- **Automated Verification**: Ensure functional correctness, edge-case safety, and concurrency boundaries across all layers through automated testing.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.10+** (Tested on 3.13.5) | Primary runtime environment |
| `Cython >= 3.0` | C-extension compiler for native matching engine acceleration |
| `mmap` *(standard library)* | Shared-memory circular ring buffer for zero-copy IPC |
| `struct` *(standard library)* | Fixed 33-byte binary order encoding and decoding |
| `multiprocessing` *(standard library)* | Cross-process synchronization via shared locks and concurrent workers |
| `asyncio` *(standard library)* | Asynchronous market simulator and pipeline event loop |
| `curses` / `windows-curses` | Real-time terminal dashboard for execution monitoring |
| `pytest` / `unittest` | Automated test suite (unit, integration, parity, and concurrency) |
| `setuptools` / `wheel` | Build system and C-extension packaging |

*Note: The core data models, binary codec, ring buffer, and Python matching engine require zero external third-party dependencies.*

---

## 🏗️ System Architecture & Core Components

ChronosMatch connects order producers to consumers and monitors execution state through a coordinated multi-layer pipeline:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           1. Market Simulator                               │
│                         (Python + asyncio Tasks)                            │
│  Generates randomized BUY & SELL orders (order_id, price, qty, side, time)  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ encode_order()
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          2. Binary Order Codec                              │
│                    33-Byte Binary Record (>QQQBQ)                           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ push_order() / write()
                                       ▼
╔═════════════════════════════════════════════════════════════════════════════╗
║                  3. Shared-Memory Circular Ring Buffer                      ║
║                     Memory-Mapped Storage (mmap)                            ║
║ ┌────────────────────────── Header (64 Bytes) ────────────────────────────┐ ║
║ │ Magic: b"CMRB" | Ver: 1 | Capacity: uint32 | SlotSize: uint32 | Seqs... │ ║
║ ├────────────────────────── Data Region ──────────────────────────────────┤ ║
║ │ Slot 0 (33B) │ Slot 1 (33B) │ ... │ Slot N-1 (33B)                      │ ║
║ └─────────────────────────────────────────────────────────────────────────┘ ║
║               Synchronized via multiprocessing.Lock                         ║
╚═════════════════════════════════════════════════════════════════════════════╝
                                       │ pop_order() / read()
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         4. Order Decoder & Gateway                          │
│                    Decodes 33-byte binary payload into                      │
│                  immutable Order dataclass (zero-copy)                      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ process_order(order)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      5. Limit Order Book & Matching                         │
│             MatchingEngine (Python Fallback / Cython Native)                 │
│ ┌────────────────────────── OrderBook State ──────────────────────────────┐ │
│ │  Bids (Max-Price Priority)         │  Asks (Min-Price Priority)         │ │
│ │  Price Level -> FIFO Order Queue   │  Price Level -> FIFO Order Queue   │ │
│ └────────────────────────────────────┴────────────────────────────────────┘ │
│                     Produces Trade Execution Records                        │
└───────────────────────┬─────────────────────────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌─────────────────────────────┐ ┌─────────────────────────────────────────────┐
│     6. Terminal Dashboard   │ │      7. Trade Persistence (Planned)         │
│     (CursesDashboard)       │ │     Asynchronous SQLite Audit Worker        │
│ Real-time stats & trade log │ └─────────────────────────────────────────────┘
└─────────────────────────────┘
```

### 1. Order Data Model (`src/chronosmatch/order.py`)
- **Immutability & Slots**: `Order` is defined as an immutable (`frozen=True`, `slots=True`) dataclass that eliminates `__dict__` overhead and prevents unintended in-flight state mutations.
- **Fixed-Point Pricing**: Prices are represented as positive integers (e.g., paise where 1 INR = 100 paise) to eliminate floating-point rounding errors and non-deterministic matching behavior.
- **Ingress Timestamps**: Nanosecond timestamps (`timestamp_ns`) decouple order creation from local clock sources, supporting deterministic replay and latency profiling.
- **Side Representation**: Enumerated by `OrderSide` (`BUY = 1`, `SELL = 2`).

### 2. Binary Order Codec (`src/chronosmatch/order_codec.py`)
- **Fixed 33-Byte Layout**: Packs and unpacks orders using the format string `>QQQBQ` (Big-Endian standard layout without alignment padding):
  - `order_id` (uint64, 8 bytes)
  - `price` (uint64, 8 bytes)
  - `quantity` (uint64, 8 bytes)
  - `side` (uint8, 1 byte — `1` for BUY, `2` for SELL)
  - `timestamp_ns` (uint64, 8 bytes)
- **Zero-Copy Friendly**: `decode_order` accepts `bytes`, `bytearray`, and `memoryview` objects directly.
- **Boundary Validation**: Validates 64-bit and 8-bit unsigned integer ranges prior to packing and deserialization.

### 3. Shared-Memory Circular Ring Buffer (`src/chronosmatch/ipc/ring_buffer.py`)
- **Memory-Mapped IPC**: Backed by `mmap`, providing shared memory accessible across separate operating system processes.
- **64-Byte Binary Header**:
  - `magic` (`b"CMRB"`) and `version` (`1`) for integrity validation.
  - `capacity` (number of slots) and `slot_size` (bytes per slot).
  - Monotonic 64-bit sequence counters (`write_seq` and `read_seq`) stored directly in the shared header.
- **Circular Modulo Indexing**:
  - Write slot: `write_seq % capacity`
  - Read slot: `read_seq % capacity`
  - Available count: `write_seq - read_seq`
  - Distinguishes empty (`write_seq == read_seq`) from full (`count == capacity`) without sacrificing a buffer slot.
- **Concurrency & Isolation**: All state transitions, slot reads/writes, and pointer advances are synchronized using a shared `multiprocessing.Lock`. Slot data is copied to an immutable `bytes` slice inside the lock to protect consumers against concurrent wraparound overwrites.

### 4. Limit Order Book (`src/chronosmatch/order_book.py`)
- **Bid/Ask Isolation**: Maintains separate internal dictionaries for `bids` and `asks`.
- **Price-Time Priority (FIFO)**: Each price level contains a list of orders sequenced by arrival time.
- **Depth Queries**: Provides `best_bid()` (highest buy price) and `best_ask()` (lowest sell price).
- **Automatic Pruning**: Emptied price levels are automatically deleted from the dictionary to avoid memory leaks.

### 5. Matching Engine (`src/chronosmatch/matching_engine.py` & `.pyx`)
- **Price-Time Execution**: Matches crossing orders against resting liquidity:
  - BUY order crosses when `order.price >= best_ask`.
  - SELL order crosses when `order.price <= best_bid`.
- **Multi-Level Sweeps & Partial Fills**: Sweeps across price levels in price-time priority until the incoming order is filled or liquidity is exhausted. Supports partial fills on resting and incoming orders. Unfilled remainders rest in the book.
- **Compiled Cython Acceleration**: `src/chronosmatch/matching_engine.pyx` implements the matching core in compiled Cython, built via `setup.py` as `chronosmatch.matching_engine_cy`.
- **Hybrid Bridge & Fallback**: `src/chronosmatch/matching_engine.py` provides transparent dispatch to `matching_engine_cy` when available, while preserving an identical pure-Python fallback when `use_cython=False` or when running uncompiled.

### 6. Trade Execution Model (`src/chronosmatch/trade.py`)
- **Immutable Execution Record**: `Trade` is an immutable (`frozen=True`, `slots=True`) dataclass recording:
  - `buy_order_id` (int)
  - `sell_order_id` (int)
  - `price` (int, execution price from resting order)
  - `quantity` (int, matched volume)
  - `timestamp_ns` (int, nanosecond execution timestamp)

### 7. Market Simulator (`src/chronosmatch/simulator.py`)
- **Asynchronous Producer**: `MarketSimulator` generates synthetic BUY and SELL orders at configurable intervals (`generation_interval`) using `asyncio`.
- **Configurable Boundaries**: Parameterizes price ranges, quantity ranges, and maximum order limits.
- **Ring Buffer Ingress**: Pushes generated orders directly into the shared-memory ring buffer.

### 8. Terminal Dashboard (`src/chronosmatch/dashboard.py`)
- **Interactive Terminal UI**: `CursesDashboard` uses standard `curses` (and `windows-curses` on Windows) to display live system metrics:
  - Total orders processed and trades executed.
  - Real-time matching latency in microseconds (μs).
  - Current engine status (`INITIALIZING`, `RUNNING`, `STOPPING`, `COMPLETED`).
  - Scrolling table of recent trade executions with timestamp, order ID pair, price, and volume.

### 9. Integrated Pipeline Runner (`run_pipeline.py`)
- **End-to-End Orchestration**: Launches the shared ring buffer, asynchronous simulator task, matching engine consumer, and curses dashboard inside an `asyncio` event loop.

---

## 📁 Repository Structure

```
Infotact_ChronosMatch/
├── .gitignore                             # Git ignore rules (build, cache, pyd, and C artifacts)
├── Architecture.md                        # Architectural specification document
├── README.md                              # Project documentation
├── pyproject.toml                         # Build system and project metadata
├── requirements.txt                       # Development and test dependencies
├── run_pipeline.py                        # Integrated pipeline and dashboard entry point
├── setup.py                               # Cython build and C-extension configuration
├── benchmarks/
│   ├── benchmark_matching_engine.py       # Matching engine and order book profiling suite
│   ├── benchmark_ring_buffer.py           # Shared-memory IPC throughput and latency benchmark
│   └── run_controlled_benchmark.py        # Controlled Python vs. Cython comparative benchmark
├── src/
│   └── chronosmatch/
│       ├── __init__.py                    # Package exports
│       ├── dashboard.py                   # Curses-based terminal dashboard
│       ├── matching_engine.py             # Matching engine (Python fallback & Cython dispatch)
│       ├── matching_engine.pyx            # Compiled Cython matching core
│       ├── order.py                       # Immutable Order dataclass and OrderSide enum
│       ├── order_book.py                  # Limit order book with price-time priority
│       ├── order_codec.py                 # 33-byte binary serialization codec
│       ├── simulator.py                   # Asynchronous market simulator
│       ├── trade.py                       # Immutable Trade execution record
│       └── ipc/
│           ├── __init__.py                # IPC module exports
│           └── ring_buffer.py             # Memory-mapped circular FIFO ring buffer
└── tests/
    ├── __init__.py
    ├── test_matching_engine.py            # Matching logic, sweeps, partial fills, immutability
    ├── test_matching_parity.py            # Deterministic Python vs. Cython execution parity
    ├── test_monitor.py                    # Terminal dashboard updates, trade tables, rendering
    ├── test_order.py                      # Order model creation, boundaries, and validation
    ├── test_order_book.py                 # Order book priority, FIFO queues, and level cleanup
    ├── test_order_codec.py                # Binary codec roundtrip, endianness, boundary limits
    ├── test_pipeline.py                   # Simulator-to-matching end-to-end pipeline tests
    ├── test_ring_buffer.py                # Ring buffer FIFO, wraparound, header, and concurrency
    └── test_simulator.py                  # Simulator order generation and asyncio lifecycle
```

---

## ⚙️ Installation & Build Instructions

### Prerequisites
- Python 3.10 or later (tested on Python 3.13.5)
- C/C++ compiler toolchain (e.g., Microsoft Visual C++ Build Tools on Windows, GCC or Clang on Linux/macOS)
- Git

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tarun-agdi/Infotact_ChronosMatch.git
   cd Infotact_ChronosMatch
   git checkout tarun
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   ```bash
   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   python -m pip install "Cython>=3.0" setuptools wheel
   ```
   *Note for Windows users:* The dashboard requires `windows-curses` (`pip install windows-curses`).

4. **Compile the Cython matching engine extension:**
   ```bash
   python setup.py build_ext --inplace
   ```
   This compiles `src/chronosmatch/matching_engine.pyx` into the native extension module `chronosmatch.matching_engine_cy` (producing a `.pyd` on Windows or `.so` on Linux).

5. **Install the package in editable mode (or set `PYTHONPATH`):**
   ```bash
   python -m pip install -e .
   ```
   Or set the environment variable:
   ```powershell
   $env:PYTHONPATH="src"
   ```

6. **Run the integrated pipeline with the terminal dashboard:**
   ```bash
   python run_pipeline.py
   ```
   *(Press `q` or `Ctrl+C` in the terminal to exit the dashboard).*

---

## 🧪 Automated Testing

ChronosMatch includes an automated test suite verifying correctness, data model immutability, binary serialization, ring buffer boundaries, matching engine logic, execution parity, simulator generation, and dashboard rendering.

### Run Tests via `pytest`:
```bash
python -m pytest -v
```

### Verified Test Results:
```text
============================= 93 passed in 3.64s ==============================
```

### Test Suite Breakdown:

| Test File | Tests | Scope & Verified Invariants |
|---|---|---|
| [`tests/test_order.py`](tests/test_order.py) | **12** | Field validation, immutability, slot constraints, hashing, positive integer bounds, and timestamp zero support. |
| [`tests/test_order_codec.py`](tests/test_order_codec.py) | **15** | 33-byte `>QQQBQ` packing, binary layout verification, bytearray/memoryview decoding, 64-bit integer limits, and invalid side rejection. |
| [`tests/test_ring_buffer.py`](tests/test_ring_buffer.py) | **16** | 64-byte binary header sanity, corrupt header rejection, FIFO order across slots, multi-cycle circular wraparound, 64-bit sequence overflow handling, data isolation on read, and multi-process concurrency. |
| [`tests/test_order_book.py`](tests/test_order_book.py) | **19** | Bid and ask side isolation, price-time priority, FIFO ordering within price levels, level deletion upon complete fill, and non-mutating `best_bid()`/`best_ask()` queries. |
| [`tests/test_matching_engine.py`](tests/test_matching_engine.py) | **20** | Crossing detection, execution at resting order price, multi-level sweeps, partial fills, full fills, remaining order placement, Trade creation, immutability, and type safety. |
| [`tests/test_matching_parity.py`](tests/test_matching_parity.py) | **2** | Deterministic trade-by-trade and book state parity between Python and Cython across multi-order streams; verifies Python fallback integrity when Cython is disabled. |
| [`tests/test_simulator.py`](tests/test_simulator.py) | **2** | `MarketSimulator` parameter bounds, randomized order generation, and `asyncio` task start/stop lifecycle. |
| [`tests/test_monitor.py`](tests/test_monitor.py) | **3** | `CursesDashboard` initialization, trade log recording, metric state updates, and terminal screen rendering with mock screen objects. |
| [`tests/test_pipeline.py`](tests/test_pipeline.py) | **4** | Simulator $\rightarrow$ RingBuffer $\rightarrow$ MatchingEngine integration, pipeline draining, unmatched order retention, and trade execution. |

---

## 📊 Benchmark Suite

ChronosMatch provides three dedicated benchmark scripts to measure throughput, latency, and speedups across components:

### 1. Ring Buffer IPC Benchmark (`benchmarks/benchmark_ring_buffer.py`)
Measures throughput and latency for the shared-memory circular ring buffer across three workloads:
- **Raw Buffer**: 100,000 write/read cycles using 33-byte payloads (pure pointer arithmetic, lock acquisition, and `mmap` read/write).
- **Order-Level (Single Process)**: 100,000 orders serialized via `encode_order`, pushed to the buffer, popped, and deserialized via `decode_order`.
- **Multiprocess IPC**: 50,000 orders transferred concurrently between separate Producer and Consumer processes synchronized via a shared `multiprocessing.Lock`.

*Run the benchmark:*
```powershell
python benchmarks/benchmark_ring_buffer.py
```

### 2. Matching Engine & Order Book Profiler (`benchmarks/benchmark_matching_engine.py`)
Profiles the limit order book and matching engine across four representative trading scenarios:
- **Book Building**: 100,000 non-crossing orders testing resting order insertion and price-level creation.
- **Aggressive Matching**: 100,000 crossing orders executing against resting liquidity.
- **Mixed Market Workload**: 50,000 alternating realistic orders around a central mid-price.
- **End-to-End Pipeline**: 50,000 orders pushed through `RingBuffer` $\rightarrow$ popped $\rightarrow$ decoded $\rightarrow$ matched.

*Run the benchmark:*
```powershell
python benchmarks/benchmark_matching_engine.py
# Or with cProfile profiling:
python benchmarks/benchmark_matching_engine.py --profile
```

### 3. Controlled Python vs. Cython Benchmark (`benchmarks/run_controlled_benchmark.py`)
Executes a fair, controlled comparison between the pure-Python matching engine and the compiled Cython matching engine:
- **Pre-Run Parity Verification**: Runs an automated 10,000-order deterministic test ensuring identical trade counts, trade attributes, and final book states before benchmarking begins.
- **Multi-Round Measurement**: Executes 3 runs per scenario for each engine mode and reports median elapsed times, throughput (orders/sec), and average latency (μs/order).
- **Comparative Metrics**: Calculates throughput improvement (%) and latency reduction (%) achieved by Cython compilation.

*Run the controlled comparison:*
```powershell
python benchmarks/run_controlled_benchmark.py
```

---

## 🚧 Development Roadmap

### Week 1: Core IPC, Serialization & Data Model (Completed)
- [x] Immutable `Order` dataclass with integer pricing, strict bounds, and nanosecond timestamps.
- [x] Compact 33-byte binary serialization codec (`order_codec.py`).
- [x] Shared-memory circular FIFO ring buffer with 64-byte header (`ipc/ring_buffer.py`).
- [x] Process-safe synchronization via shared `multiprocessing.Lock`.
- [x] Shared-memory throughput and latency benchmark suite (`benchmark_ring_buffer.py`).
- [x] Core unit and concurrency tests (43 tests passing).

### Week 2: Limit Order Book, Matching Engine & Simulator (Completed)
- [x] Price-time priority limit order book (`order_book.py`).
- [x] In-memory matching engine in Python (`matching_engine.py`).
- [x] Immutable `Trade` execution model (`trade.py`).
- [x] Asynchronous mock market simulator (`simulator.py`).
- [x] Order book and matching engine unit tests.
- [x] Matching engine and pipeline profiling benchmark (`benchmark_matching_engine.py`).

### Week 3: Cython Acceleration, Parity & Dashboard Integration (Completed)
- [x] Cython matching engine implementation (`matching_engine.pyx`).
- [x] C-extension packaging and compilation pipeline via `setup.py` and `pyproject.toml`.
- [x] Hybrid Python dispatch and fallback architecture.
- [x] Deterministic Python vs. Cython parity verification test suite (`test_matching_parity.py`).
- [x] Controlled comparative benchmark runner (`run_controlled_benchmark.py`).
- [x] Terminal curses dashboard for real-time monitoring (`dashboard.py`).
- [x] Integrated pipeline runner linking simulator, ring buffer, engine, and dashboard (`run_pipeline.py`).
- [x] Full test suite expanded to 93 passing tests.

### Week 4: Trade Persistence, Stress Testing & Release (Pending)
- [ ] Asynchronous persistence worker (SQLite database logging for completed trades).
- [ ] Long-running stress and soak testing under bursty and saturated workloads.
- [ ] Final performance tuning, branch reconciliation, and release documentation.

---

## 👥 Collaboration & Contribution Workflow

1. **Branch Isolation**: Develop components on dedicated topic/person branches (e.g., `tarun`).
2. **Build Verification**: Compile Cython extensions cleanly using `python setup.py build_ext --inplace`.
3. **Automated Testing**: Ensure all tests pass prior to submitting changes:
   ```bash
   python -m pytest -v
   ```
4. **Formatting & Whitespace Check**: Verify clean formatting before committing:
   ```bash
   git diff --cached --check
   ```
5. **Shared Interfaces**: Maintain interface stability across `Order`, `OrderBook`, `Trade`, `order_codec`, and `RingBuffer`.

---

## 📄 License

This project is developed for educational and research purposes under the ChronosMatch project terms.
