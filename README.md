
# ChronosMatch — High-Performance Trading Engine

ChronosMatch is a terminal-based trading engine designed to simulate market activity, process buy and sell orders, and match orders efficiently. The project explores asynchronous programming, shared-memory communication, and performance measurement using Python.

## 🎯 Project Objectives

- Simulate a stream of mock buy and sell orders.
- Implement an order-matching engine using price-time priority.
- Explore inter-process communication (IPC) using shared memory.
- Use binary message serialization with Python's `struct` module.
- Measure throughput, latency, and matching performance.
- Validate functionality through automated testing.

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core implementation |
| `asyncio` | Asynchronous market simulation |
| `mmap` | Shared-memory communication |
| `struct` | Binary message packing and unpacking |
| `pytest` | Automated testing |
| `pytest-asyncio` | Testing asynchronous components |

*Note: `asyncio`, `mmap`, and `struct` are part of Python's standard library.*

## 📁 Project Structure

### 1. Ongoing Development Structure

During development, each team member works on a separate Git branch. The directory structure may evolve as features are implemented and integrated.


ChronosMatch/
├── src/                 # Core source code (evolving)
├── tests/               # Tests added during development
├── benchmarks/          # Performance testing (as developed)
├── requirements.txt     # Project dependencies
├── .gitignore           # Files excluded from Git
└── README.md            # Project documentation


Individual branches may contain additional files or different structures until changes are reviewed and merged.

### 2. Expected Final Project Structure

After implementation, testing, and integration, the main branch is expected to follow an organized structure similar to this:


ChronosMatch/
├── src/
│   ├── __init__.py
│   ├── simulator.py          # Generates mock market orders
│   ├── matching_engine.py    # Order book and matching logic
│   ├── order.py              # Order representation and validation
│   ├── ipc.py                # mmap-based shared-memory IPC
│   └── main.py               # Application entry point
├── tests/
│   ├── test_order.py
│   ├── test_matching.py
│   └── test_ipc.py
├── benchmarks/
│   └── benchmark.py          # Throughput and latency benchmarks
├── docs/
│   └── architecture.md       # Architecture and design decisions
├── requirements.txt
├── .gitignore
└── README.md


*This is the target structure, not a claim that all files have already been implemented. Adjust it to match the final codebase.*

## ⚙️ Getting Started

### Prerequisites

- Python 3.11 or later
- Git
- Visual Studio Code or another Python-compatible editor

### Installation

**1. Clone the repository**

```bash
git clone <repository-url>
cd ChronosMatch
```

2. Create and activate a virtual environment**

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**3. Install dependencies**

```bash
python -m pip install -r requirements.txt
```

## ▶️ Running the Project

Once the application entry point is implemented, run it from the repository root:

```bash
python -m src.main
```

The command assumes the final entry point is `src/main.py`.

## 🧪 Testing

Run the automated test suite:

```bash
python -m pytest -v
```

Tests should cover order validation, matching rules, shared-memory communication, and important edge cases.

## 📊 Performance Evaluation

The project will be evaluated using the following metrics:

- **Throughput:** Number of orders processed per second.
- **Latency:** Time taken to process an order.
- **Matching correctness:** Whether orders execute according to price-time priority.
- **IPC efficiency:** Communication overhead between processes.
- **Reliability:** Correct behavior under different order volumes.

Record actual benchmark results after testing; do not report estimated figures as measured performance.

## 🚧 Development Roadmap

- [ ] Implement the market simulator.
- [ ] Develop the order book and matching engine.
- [ ] Implement price-time priority.
- [ ] Develop shared-memory IPC using `mmap` and `struct`.
- [ ] Add unit and integration tests.
- [ ] Benchmark throughput and latency.
- [ ] Integrate team branches into the main branch.
- [ ] Finalize documentation and performance results.

## 👥 Collaboration Workflow

1. Each member develops features on their own branch.
2. Commit changes with clear, meaningful messages.
3. Push the branch to the remote repository.
4. Open a pull request for review and integration.
5. Test the integrated code before merging into `main`.

Keep shared interfaces and message formats consistent across branches to avoid integration issues.

## 📄 License

Add an appropriate license after confirming the project's distribution requirements.