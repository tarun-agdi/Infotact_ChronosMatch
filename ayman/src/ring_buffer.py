"""
Shared-memory ring buffer implementation using mmap for ChronosMatch.

This module provides a fixed-capacity circular FIFO ring buffer designed for
inter-process communication (IPC) between trading engine components
(such as the market simulator, order gateway, and matching engine).

Concurrency Contract:
---------------------
Version 1 of this ring buffer is explicitly lock-based, not lock-free.
Because standard Python mmap across processes does not expose cross-platform
hardware 64-bit atomic operations, all shared-state operations (header inspection,
sequence increments, and slot read/write operations) are synchronized using an
explicitly shared multiprocessing.Lock provided by the caller.

Callers must create this lock once in a parent coordinator process
(e.g., `lock = multiprocessing.Lock()`) and pass the SAME lock instance
to both the producer and consumer RingBuffer instances. Independent locks created
separately in different processes will NOT provide synchronization.

Memory Layout:
--------------
The memory-mapped file begins with a fixed 64-byte header followed immediately
by contiguous fixed-size data slots.

Offset | Field      | Struct Code | C Type   | Size (Bytes) | Description
-----------------------------------------------------------------------------------------
0..3   | magic      | 4s          | char[4]  | 4            | Identifier (b"CMRB")
4..7   | version    | I           | uint32   | 4            | Header version (1)
8..11  | capacity   | I           | uint32   | 4            | Maximum number of slots
12..15 | slot_size  | I           | uint32   | 4            | Size of each slot in bytes
16..23 | write_seq  | Q           | uint64   | 8            | Monotonic count of written items
24..31 | read_seq   | Q           | uint64   | 8            | Monotonic count of read items
32..63 | reserved   | 32s         | char[32] | 32           | Zero padding (64-byte alignment)
-----------------------------------------------------------------------------------------
Total Header Size: 64 bytes.

Slot Indexing:
--------------
- write_slot_index = write_seq % capacity
- read_slot_index  = read_seq % capacity
- slot_offset      = 64 + (slot_index * slot_size)
- count            = write_seq - read_seq
- full condition   : count >= capacity
- empty condition  : count == 0 (write_seq == read_seq)
"""

from __future__ import annotations

import io
import mmap
from pathlib import Path
import struct
from typing import Any, Final

from chronosmatch.order import Order
from ayman.src.order_codec import ORDER_RECORD_SIZE, decode_order, encode_order

# Header format: Big-Endian (>), 4s (magic), 3x uint32 (version, capacity, slot_size),
# 2x uint64 (write_seq, read_seq), 32s (reserved padding).
HEADER_FORMAT: Final[str] = ">4sIIIQQ32s"
HEADER_STRUCT: Final[struct.Struct] = struct.Struct(HEADER_FORMAT)
HEADER_SIZE: Final[int] = HEADER_STRUCT.size  # Exactly 64 bytes

# Fast pack/unpack struct for 64-bit unsigned sequence counters at offsets 16 and 24.
SEQ_STRUCT: Final[struct.Struct] = struct.Struct(">QQ")

# Magic constant identifying ChronosMatch Ring Buffer
MAGIC: Final[bytes] = b"CMRB"

# Layout version supported by this implementation
SUPPORTED_VERSION: Final[int] = 1

# Numeric bounds
UINT32_MAX: Final[int] = (1 << 32) - 1
UINT64_MAX: Final[int] = (1 << 64) - 1


class RingBuffer:
    """
    Fixed-capacity circular ring buffer backed by mmap and synchronized via
    a caller-supplied shared multiprocessing.Lock.
    """

    def __init__(
        self,
        mmap_obj: mmap.mmap,
        file_obj: io.BufferedRandom,
        capacity: int,
        slot_size: int,
        lock: Any,
        filepath: Path | None = None,
    ) -> None:
        """
        Direct constructor. Users should generally use `RingBuffer.create` or
        `RingBuffer.open` factory classmethods instead.

        Args:
            mmap_obj: The active memory-mapped file buffer.
            file_obj: The underlying open binary file object.
            capacity: Total number of data slots in the buffer.
            slot_size: Size of each data slot in bytes.
            lock: An explicitly shared multiprocessing.Lock (or compatible lock)
                  used to synchronize all cross-process operations.
            filepath: Optional path to the backing file (used for unlink/cleanup).
        """
        if lock is None:
            raise TypeError(
                "A shared multiprocessing.Lock is required for synchronization. "
                "Do not pass None."
            )

        self._mmap: mmap.mmap | None = mmap_obj
        self._file: io.BufferedRandom | None = file_obj
        self._capacity: int = capacity
        self._slot_size: int = slot_size
        self._lock: Any = lock
        self._filepath: Path | None = filepath
        self._closed: bool = False

    @property
    def capacity(self) -> int:
        """Maximum number of slots in the buffer."""
        return self._capacity

    @property
    def slot_size(self) -> int:
        """Size of each data slot in bytes."""
        return self._slot_size

    @property
    def filepath(self) -> Path | None:
        """Path to the backing file on disk, if known."""
        return self._filepath

    def _check_closed(self) -> None:
        """Ensure the buffer has not been closed."""
        if self._closed or self._mmap is None or self._file is None:
            raise ValueError("RingBuffer is closed")

    @classmethod
    def create(
        cls,
        filepath: str | Path,
        capacity: int,
        slot_size: int = ORDER_RECORD_SIZE,
        lock: Any = None,
    ) -> RingBuffer:
        """
        Create and initialize a new ring buffer backing file on disk.

        Args:
            filepath: Path to the backing file.
            capacity: Number of slots (must be a positive integer <= 2^32 - 1).
            slot_size: Byte size of each slot (defaults to 33 bytes for Order records).
            lock: Shared multiprocessing.Lock instance.

        Returns:
            A ready-to-use RingBuffer instance.

        Raises:
            TypeError: If lock is not provided or capacity/slot_size are not integers.
            ValueError: If capacity or slot_size are out of valid range.
        """
        if lock is None:
            raise TypeError(
                "A shared multiprocessing.Lock is required for synchronization. "
                "Create one in your coordinator process and pass it here."
            )
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError(f"capacity must be an integer, got {type(capacity).__name__}")
        if capacity <= 0 or capacity > UINT32_MAX:
            raise ValueError(
                f"capacity must be a positive integer in range [1, {UINT32_MAX}], got {capacity}"
            )

        if isinstance(slot_size, bool) or not isinstance(slot_size, int):
            raise TypeError(f"slot_size must be an integer, got {type(slot_size).__name__}")
        if slot_size <= 0 or slot_size > UINT32_MAX:
            raise ValueError(
                f"slot_size must be a positive integer in range [1, {UINT32_MAX}], got {slot_size}"
            )

        path = Path(filepath).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        total_size = HEADER_SIZE + (capacity * slot_size)

        # Create/truncate file and set exact size
        file_obj = open(path, "w+b")
        try:
            file_obj.truncate(total_size)
            # Ensure physical allocation on Windows/Unix
            file_obj.seek(total_size - 1)
            file_obj.write(b"\x00")
            file_obj.flush()

            # Map the file into memory
            mmap_obj = mmap.mmap(file_obj.fileno(), total_size)

            # Initialize 64-byte header
            HEADER_STRUCT.pack_into(
                mmap_obj,
                0,
                MAGIC,
                SUPPORTED_VERSION,
                capacity,
                slot_size,
                0,  # write_seq
                0,  # read_seq
                b"\x00" * 32,  # reserved padding
            )
            mmap_obj.flush()
        except Exception:
            file_obj.close()
            raise

        return cls(
            mmap_obj=mmap_obj,
            file_obj=file_obj,
            capacity=capacity,
            slot_size=slot_size,
            lock=lock,
            filepath=path,
        )

    @classmethod
    def open(
        cls,
        filepath: str | Path,
        lock: Any = None,
    ) -> RingBuffer:
        """
        Open and validate an existing ring buffer file from disk.

        Args:
            filepath: Path to the existing backing file.
            lock: Shared multiprocessing.Lock instance.

        Returns:
            A ready-to-use RingBuffer instance attached to the existing file.

        Raises:
            TypeError: If lock is not provided.
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the file header or size is invalid, corrupt, or unsupported.
        """
        if lock is None:
            raise TypeError(
                "A shared multiprocessing.Lock is required for synchronization. "
                "Create one in your coordinator process and pass it here."
            )

        path = Path(filepath).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Ring buffer backing file not found: {path}")

        file_size = path.stat().st_size
        if file_size < HEADER_SIZE:
            raise ValueError(
                f"Corrupt ring buffer: file size ({file_size} bytes) is smaller "
                f"than header size ({HEADER_SIZE} bytes)"
            )

        file_obj = open(path, "r+b")
        try:
            mmap_obj = mmap.mmap(file_obj.fileno(), 0)
        except Exception:
            file_obj.close()
            raise

        # Unpack and validate header
        magic, version, capacity, slot_size, write_seq, read_seq, _ = HEADER_STRUCT.unpack_from(
            mmap_obj, 0
        )

        def _cleanup_and_raise(msg: str) -> None:
            mmap_obj.close()
            file_obj.close()
            raise ValueError(msg)

        if magic != MAGIC:
            _cleanup_and_raise(
                f"Invalid ring buffer magic: expected {MAGIC!r}, got {magic!r}"
            )
        if version != SUPPORTED_VERSION:
            _cleanup_and_raise(
                f"Unsupported ring buffer version: expected {SUPPORTED_VERSION}, got {version}"
            )
        if capacity <= 0:
            _cleanup_and_raise(f"Corrupt header: capacity must be > 0, got {capacity}")
        if slot_size <= 0:
            _cleanup_and_raise(f"Corrupt header: slot_size must be > 0, got {slot_size}")

        expected_size = HEADER_SIZE + (capacity * slot_size)
        if file_size != expected_size:
            _cleanup_and_raise(
                f"File size mismatch: expected exactly {expected_size} bytes, got {file_size}"
            )

        if write_seq < read_seq:
            _cleanup_and_raise(
                f"Corrupt sequence counters: write_seq ({write_seq}) < read_seq ({read_seq})"
            )

        return cls(
            mmap_obj=mmap_obj,
            file_obj=file_obj,
            capacity=capacity,
            slot_size=slot_size,
            lock=lock,
            filepath=path,
        )

    # -------------------------------------------------------------------------
    # Synchronized State Inspectors
    # -------------------------------------------------------------------------

    def count(self) -> int:
        """
        Return the number of unread records currently in the buffer.
        """
        self._check_closed()
        assert self._mmap is not None
        with self._lock:
            write_seq, read_seq = SEQ_STRUCT.unpack_from(self._mmap, 16)
            return write_seq - read_seq

    def is_empty(self) -> bool:
        """Return True if the buffer contains no unread items, False otherwise."""
        return self.count() == 0

    def is_full(self) -> bool:
        """Return True if the buffer is completely full, False otherwise."""
        return self.count() >= self._capacity

    @property
    def write_seq(self) -> int:
        """Current monotonic count of written records."""
        self._check_closed()
        assert self._mmap is not None
        with self._lock:
            (w_seq,) = struct.unpack_from(">Q", self._mmap, 16)
            return w_seq

    @property
    def read_seq(self) -> int:
        """Current monotonic count of read records."""
        self._check_closed()
        assert self._mmap is not None
        with self._lock:
            (r_seq,) = struct.unpack_from(">Q", self._mmap, 24)
            return r_seq

    # -------------------------------------------------------------------------
    # Synchronized Raw Binary Operations
    # -------------------------------------------------------------------------

    def write(self, data: bytes | bytearray | memoryview) -> bool:
        """
        Write a binary record of length `slot_size` into the next available slot.

        Args:
            data: Bytes-like object of length exactly equal to `slot_size`.

        Returns:
            True if the record was successfully written; False if the buffer is full.

        Raises:
            ValueError: If RingBuffer is closed, or data length != slot_size.
            TypeError: If data is not a bytes-like object.
            OverflowError: If write_seq exceeds the 64-bit unsigned limit (UINT64_MAX).
        """
        self._check_closed()
        assert self._mmap is not None

        if isinstance(data, bool) or not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"data must be a bytes-like object (bytes, bytearray, memoryview), got {type(data).__name__}"
            )
        if len(data) != self._slot_size:
            raise ValueError(
                f"Data size {len(data)} does not match buffer slot size {self._slot_size}"
            )

        with self._lock:
            write_seq, read_seq = SEQ_STRUCT.unpack_from(self._mmap, 16)

            # Explicit check against 64-bit unsigned bounds
            if write_seq >= UINT64_MAX:
                raise OverflowError(
                    f"write_seq has reached maximum 64-bit unsigned limit: {UINT64_MAX}"
                )

            # Check full condition
            if (write_seq - read_seq) >= self._capacity:
                return False

            # Circular slot offset calculation
            slot_idx = write_seq % self._capacity
            slot_offset = HEADER_SIZE + (slot_idx * self._slot_size)

            # Copy data into slot
            self._mmap[slot_offset : slot_offset + self._slot_size] = data

            # Advance write_seq in header
            struct.pack_into(">Q", self._mmap, 16, write_seq + 1)
            return True

    def read(self) -> bytes | None:
        """
        Read the next available record from the buffer.

        To guarantee complete data isolation and avoid race conditions with
        subsequent writes, this method copies the slot contents into an immutable
        `bytes` object while holding the lock before returning.

        Returns:
            An isolated `bytes` object of length `slot_size`, or `None` if the buffer is empty.

        Raises:
            ValueError: If RingBuffer is closed.
            OverflowError: If read_seq exceeds the 64-bit unsigned limit (UINT64_MAX).
        """
        self._check_closed()
        assert self._mmap is not None

        with self._lock:
            write_seq, read_seq = SEQ_STRUCT.unpack_from(self._mmap, 16)

            # Explicit check against 64-bit unsigned bounds
            if read_seq >= UINT64_MAX:
                raise OverflowError(
                    f"read_seq has reached maximum 64-bit unsigned limit: {UINT64_MAX}"
                )

            # Check empty condition
            if write_seq <= read_seq:
                return None

            # Circular slot offset calculation
            slot_idx = read_seq % self._capacity
            slot_offset = HEADER_SIZE + (slot_idx * self._slot_size)

            # Extract an isolated copy of slot bytes while under the lock
            slot_bytes = bytes(self._mmap[slot_offset : slot_offset + self._slot_size])

            # Advance read_seq in header
            struct.pack_into(">Q", self._mmap, 24, read_seq + 1)
            return slot_bytes

    # -------------------------------------------------------------------------
    # High-Level Typed Order Integration
    # -------------------------------------------------------------------------

    def push_order(self, order: Order) -> bool:
        """
        Serialize an Order using `order_codec.encode_order` and write it to the buffer.

        Args:
            order: Order instance to encode and store.

        Returns:
            True if written successfully, False if the buffer is full.

        Raises:
            TypeError: If order is not an Order instance.
            ValueError: If slot_size != ORDER_RECORD_SIZE or numeric fields are invalid.
        """
        if not isinstance(order, Order):
            raise TypeError(f"order must be an instance of Order, got {type(order).__name__}")
        encoded = encode_order(order)
        return self.write(encoded)

    def pop_order(self) -> Order | None:
        """
        Read the next record from the buffer and deserialize it using `order_codec.decode_order`.

        Returns:
            The reconstructed Order object, or None if the buffer is empty.

        Raises:
            ValueError: If the slot data is corrupt or cannot be decoded.
        """
        data = self.read()
        if data is None:
            return None
        return decode_order(data)

    # -------------------------------------------------------------------------
    # Lifecycle & Cleanup
    # -------------------------------------------------------------------------

    def flush(self) -> None:
        """Flush changes to disk."""
        if not self._closed and self._mmap is not None:
            try:
                self._mmap.flush()
            except Exception:
                pass

    def close(self) -> None:
        """
        Flush and close the memory map and underlying file handle.
        Safe to call multiple times.
        """
        if self._closed:
            return
        self._closed = True

        if self._mmap is not None:
            try:
                self._mmap.flush()
            except Exception:
                pass
            try:
                self._mmap.close()
            except Exception:
                pass
            self._mmap = None

        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None

    def unlink(self) -> None:
        """
        Close the ring buffer and delete the backing file from disk.
        """
        filepath = self._filepath
        self.close()
        if filepath is not None and filepath.exists():
            try:
                filepath.unlink()
            except OSError:
                pass

    def __enter__(self) -> RingBuffer:
        self._check_closed()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
