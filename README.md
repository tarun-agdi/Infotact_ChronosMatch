# ChronosMatch — High-Performance Trading Engine

ChronosMatch is a terminal-based trading engine designed to simulate market activity, process buy and sell orders, and match orders efficiently. The project explores asynchronous programming, shared-memory inter-process communication (IPC), binary serialization, and low-latency performance measurement in Python.

---

## 🎯 Project Objectives

- Simulate a high-frequency stream of mock buy and sell orders.
- Implement an in-memory order-matching engine using price-time priority (FIFO).
- Explore zero-copy and shared-memory communication using memory-mapped files (`mmap`).
- Use compact binary message serialization with Python's standard-library `struct` module.
- Measure throughput, latency, and synchronization overhead under concurrent multi-process workloads.
- Validate functionality and safety through automated testing.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.10+** (Tested on 3.13) | Core language runtime |
| `mmap` *(standard library)* | Shared-memory circular ring buffer |
| `struct` *(standard library)* | 33-byte binary order packing and unpacking |
| `multiprocessing` *(standard library)* | Inter-process synchronization via shared locks and worker processes |
| `asyncio` *(standard library)* | Asynchronous market simulation (in progress) |
| `pytest` / `unittest` | Automated test suite (unit, integration, and concurrency) |

*Note: The core engine and IPC layers require zero external dependencies.*

---

## 🏗️ Architecture & Completed Components (Person 1 — IPC & Ring Buffer)

The IPC pipeline connects order producers (market simulator / gateway) to order consumers (matching engine) using a high-throughput binary ring buffer:

```
Producer Process                                        Consumer Process
┌───────────────────────────┐                           ┌───────────────────────────┐
│       Order Object        │                           │       Order Object        │
│  (order_id, price, qty,   │                           │  (order_id, price, qty,   │
│   side, timestamp_ns)     │                           │   side, timestamp_ns)     │
└─────────────┬─────────────┘                           └─────────────▲─────────────┘
              │ encode_order()                                        │ decode_order()
              ▼                                                       │
┌───────────────────────────┐                           ┌─────────────┴─────────────┐
│ 33-Byte Binary Record     │                           │ 33-Byte Binary Record     │
│ (Big-Endian >QQQBQ)       │                           │ (Isolated bytes copy)     │
└─────────────┬─────────────┘                           └─────────────▲─────────────┘
              │ push_order() / write()                                │ pop_order() / read()
              ▼                                                       │
┌─────────────────────────────────────────────────────────────────────┴─────────────┐
│                      Shared Memory Ring Buffer (mmap)                             │
│ ┌────────────────────────────── Header (64 Bytes) ──────────────────────────────┐ │
│ │ Magic: b"CMRB" | Ver: 1 | Capacity: uint32 | SlotSize: uint32 | Sequences...  │ │
│ ├────────────────────────────── Data Region ────────────────────────────────────┤ │
│ │ Slot 0 (33B) │ Slot 1 (33B) │ ... │ Slot N-1 (33B)                            │ │
│ └───────────────────────────────────────────────────────────────────────────────┘ │
│                     Synchronized via shared multiprocessing.Lock                  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Order Data Model (`src/chronosmatch/order.py`)
- **Immutability & Slots**: `Order` is an immutable (`frozen=True`, `slots=True`) dataclass that eliminates `__dict__` overhead and prevents unintended in-flight state mutations.
- **Fixed-Point Pricing**: Prices are stored as positive integers (e.g., paise where 1 INR = 100 paise) to eliminate floating-point rounding errors and non-deterministic matching bugs.
- **Explicit Ingress Timestamps**: Nanosecond timestamps (`timestamp_ns`) decouple order creation from local clock sources, enabling deterministic backtesting and event replay.

### 2. Binary Order Codec (`src/chronosmatch/order_codec.py`)
- **Fixed 33-Byte Layout**: Packs and unpacks orders using the format string `>QQQBQ` (Big-Endian standard size without padding):
  - `order_id` (uint64, 8 bytes)
  - `price` (uint64, 8 bytes)
  - `quantity` (uint64, 8 bytes)
  - `side` (uint8, 1 byte — `1` for BUY, `2` for SELL)
  - `timestamp_ns` (uint64, 8 bytes)
- **Zero-Copy Friendly**: `decode_order` accepts `bytes`, `bytearray`, and `memoryview` objects.
- **Strict Boundary Validation**: Validates 64-bit and 8-bit unsigned integer limits prior to packing.

### 3. Shared-Memory Circular Ring Buffer (`src/chronosmatch/ipc/ring_buffer.py`)
- **Memory-Mapped Storage**: Backed by `mmap`, providing shared memory accessible across separate operating system processes.
- **64-Byte Header**:
  - `magic` (`b"CMRB"`) and `version` (`1`) for sanity validation.
  - `capacity` (number of slots) and `slot_size` (bytes per slot).
  - Monotonic 64-bit sequence counters (`write_seq` and `read_seq`) stored in the shared header.
- **Circular Modulo Indexing**:
  - Write slot: `write_seq % capacity`
  - Read slot: `read_seq % capacity`
  - Count: `write_seq - read_seq`
  - Distinguishes completely empty (`write_seq == read_seq`) from completely full (`count == capacity`) without sacrificing a slot.
- **Concurrency Contract (Lock-Based)**: All state checks, slot reads/writes, and sequence updates are synchronized using a caller-supplied, shared `multiprocessing.Lock`.
- **Data Isolation on Read**: Copies slot data to an immutable `bytes` object within the lock to prevent in-place overwrites by concurrent wraparound writes.
- **Overflow & Lifecycle Safeguards**: Validates sequences against `UINT64_MAX` before packing, validates headers on `open()`, and provides clean handle closure and `unlink()` cleanup.

---

## 📁 Repository Structure (Branch: `tarun`)

```
Infotact_ChronosMatch/
├── src/
│   └── chronosmatch/
│       ├── __init__.py
│       ├── order.py               # Order model and OrderSide enum
│       ├── order_codec.py         # 33-byte binary serialization codec
│       └── ipc/
│           ├── __init__.py        # IPC package entry point
│           └── ring_buffer.py     # mmap circular ring buffer implementation
├── tests/
│   ├── __init__.py
│   ├── test_order.py              # Order model unit tests
│   ├── test_order_codec.py        # Codec unit and boundary tests
│   └── test_ring_buffer.py        # Ring buffer, FIFO, wraparound, and IPC tests
├── benchmarks/
│   └── benchmark_ring_buffer.py   # Throughput and latency benchmark suite
├── pyproject.toml                 # Package configuration (Python >= 3.10)
├── README.md                      # Project documentation
└── .gitignore                     # Git ignore rules
```

---

## ⚙️ Getting Started

### Prerequisites
- Python 3.10 or later (tested on Python 3.13.5)
- Git

### Installation

1. **Clone the repository and switch to your working branch:**
   ```bash
   git clone <repository-url>
   cd ChronosMatch/Infotact_ChronosMatch
   git checkout tarun
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install the package in editable mode (or set PYTHONPATH):**
   ```powershell
   python -m pip install -e .
   # Alternatively without pip install:
   $env:PYTHONPATH="src"
   ```

---

## 🧪 Running Automated Tests

ChronosMatch includes 43 automated tests covering order validation, binary codec boundaries, memory mapping, FIFO order, circular wraparound, header validation, and cross-process concurrency.

**Run tests via `pytest`:**
```bash
python -m pytest -v
```

**Or run tests via `unittest`:**
```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

**Test Suite Coverage Summary:**
- [`tests/test_order.py`](file:///c:/Users/shara/OneDrive/Desktop/Chronos_Match/Infotact_ChronosMatch/tests/test_order.py): 12 tests (field validation, immutability, hashing, positive integer bounds).
- [`tests/test_order_codec.py`](file:///c:/Users/shara/OneDrive/Desktop/Chronos_Match/Infotact_ChronosMatch/tests/test_order_codec.py): 15 tests (33-byte packing, unpack validation, boundary values, endianness).
- [`tests/test_ring_buffer.py`](file:///c:/Users/shara/OneDrive/Desktop/Chronos_Match/Infotact_ChronosMatch/tests/test_ring_buffer.py): 16 tests (header sanity, corrupt headers, FIFO, wraparound cycles, 64-bit overflow check, lifecycle cleanup, multiprocess concurrency).

---

## 📊 Performance Benchmarks

A dedicated benchmark suite is implemented in [`benchmarks/benchmark_ring_buffer.py`](file:///c:/Users/shara/OneDrive/Desktop/Chronos_Match/Infotact_ChronosMatch/benchmarks/benchmark_ring_buffer.py) to measure real throughput and latency across three scenarios:

1. **Raw Buffer**: 100,000 write/read cycles using 33-byte payloads (pure pointer arithmetic, lock acquisition, and `mmap` read/write).
2. **Order-Level**: 100,000 orders serialized with `encode_order`, pushed, popped, and deserialized with `decode_order`.
3. **Multiprocess IPC**: 50,000 orders transferred concurrently between separate Producer and Consumer processes synchronized via `multiprocessing.Lock`.

### How to Run the Benchmark

```powershell
$env:PYTHONPATH="src"
python benchmarks/benchmark_ring_buffer.py
```

### Measured Performance Results

*Measured on Windows 11 (AMD64) with Python 3.13.5 (CPython), Buffer Capacity: 1,024 slots:*

| Benchmark Scenario | Workload | Measured Throughput | Average Latency | Description |
|---|---|---|---|---|
| **Raw Buffer** | 100,000 cycles | **393,968 ops/sec** | ~2.54 μs / op | Pure `mmap` slot writes and reads inside the lock |
| **Order-Level (Single Process)** | 100,000 orders | **79,242 orders/sec** | ~12.62 μs / order | End-to-end dataclass creation, codec encode/decode, and ring buffer operations |
| **Multiprocess IPC** | 50,000 orders | **162,599 orders/sec** | ~6.15 μs / order | Concurrent cross-process transfer (Producer $\rightarrow$ Consumer) |

*Methodology Highlights:*
- **Untimed Warm-Up**: 5,000 unmeasured warmup operations run before timing to ensure OS page allocation and Python cache warmup.
- **Accurate Scope**: File creation, header initialization, process startup, and file unlinking are strictly excluded from timing.
- **Full Verification**: Every single order ID is verified on the consumer side to ensure zero dropped, duplicated, or corrupted orders.

---

## 🚧 Development Roadmap

### Completed (Week 1 — Person 1: IPC & Ring Buffer)
- [x] Immutable `Order` model with strict validation.
- [x] 33-byte binary serialization codec (`order_codec.py`).
- [x] Shared-memory circular FIFO ring buffer with 64-byte header (`ring_buffer.py`).
- [x] Process-safe synchronization via caller-supplied `multiprocessing.Lock`.
- [x] Comprehensive test suite (43 passing tests).
- [x] Throughput and latency benchmark suite (`benchmark_ring_buffer.py`).

### Pending Integration & Team Roadmap
- [ ] Implement market simulator to generate realistic order streams (Person 2).
- [ ] Develop order book and matching engine core (Person 3).
- [ ] Connect Market Simulator $\rightarrow$ RingBuffer $\rightarrow$ Matching Engine gateway.
- [ ] Measure end-to-end matching engine latency and book depth.
- [ ] Final team branch merge into `main`.

---

## 👥 Collaboration Workflow

1. Each team member develops their assigned component on a dedicated branch (e.g., `tarun` for IPC & Ring Buffer).
2. Commit changes with clear, semantic commit messages.
3. Verify that all automated tests pass before opening a Pull Request (`python -m pytest -v`).
4. Review shared interfaces (`Order`, `order_codec`, `RingBuffer`) to prevent integration discrepancies.
5. Merge into `main` after review and verification.

---

## 📄 License

This project is developed for educational and research purposes under the ChronosMatch project terms.