"""System memory management utilities for controlling video processing memory usage."""

from __future__ import annotations

import ctypes
import gc
import logging
import os

logger = logging.getLogger(__name__)


# ── System memory detection ──────────────────────────────────────────────

def _get_windows_memory() -> tuple[int, int]:
    """Get total and available physical memory on Windows (bytes)."""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_uint32),
            ("dwMemoryLoad", ctypes.c_uint32),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    kernel32 = ctypes.windll.kernel32
    mem_status = MEMORYSTATUSEX()
    mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))
    return int(mem_status.ullTotalPhys), int(mem_status.ullAvailPhys)


def _get_linux_memory() -> tuple[int, int]:
    """Get total and available physical memory on Linux (bytes)."""
    total = 0
    available = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) * 1024
                elif line.startswith("MemAvailable:"):
                    available = int(line.split()[1]) * 1024
                    break
    except (OSError, ValueError):
        pass
    return total, available


def _get_darwin_memory() -> tuple[int, int]:
    """Get total and available physical memory on macOS (bytes)."""
    total = 0
    available = 0
    try:
        import subprocess
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True
        )
        total = int(result.stdout.strip())

        result = subprocess.run(["vm_stat"], capture_output=True, text=True)
        page_size = 4096
        free_pages = 0
        inactive_pages = 0
        for line in result.stdout.strip().split("\n"):
            if "page size" in line.lower():
                page_size = int(line.split("page size of ")[1].split()[0])
            elif line.startswith("Pages free:"):
                free_pages = int(line.split(":")[1].strip().rstrip("."))
            elif line.startswith("Pages inactive:"):
                inactive_pages = int(line.split(":")[1].strip().rstrip("."))
        available = (free_pages + inactive_pages) * page_size
    except Exception:
        pass
    return total, available


def get_system_memory() -> tuple[int, int]:
    """Get total and available physical memory in bytes.

    Returns:
        (total_bytes, available_bytes)
    """
    system = os.name
    if system == "nt":
        return _get_windows_memory()
    elif system == "posix":
        if os.uname().sysname == "Darwin":
            return _get_darwin_memory()
        return _get_linux_memory()
    return 0, 0


# ── Process memory monitoring ────────────────────────────────────────────

def _get_windows_process_memory_ex() -> dict[str, int]:
    """Get detailed process memory counters on Windows."""
    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_uint32),
            ("PageFaultCount", ctypes.c_uint32),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010

    try:
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        pid = os.getpid()
        process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not process:
            return {}

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        ok = psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb)
        kernel32.CloseHandle(process)

        if ok:
            return {
                "WorkingSetSize": int(counters.WorkingSetSize),
                "PrivateUsage": int(counters.PrivateUsage),
                "PagefileUsage": int(counters.PagefileUsage),
                "PeakWorkingSetSize": int(counters.PeakWorkingSetSize),
            }
    except Exception:
        pass

    return {}


def _get_linux_process_memory() -> dict[str, int]:
    """Get process memory details on Linux."""
    try:
        result: dict[str, int] = {}
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    result["WorkingSetSize"] = int(line.split()[1]) * 1024
                elif line.startswith("VmData:"):
                    result["PrivateUsage"] = int(line.split()[1]) * 1024
                elif line.startswith("VmPeak:"):
                    result["PeakWorkingSetSize"] = int(line.split()[1]) * 1024
        return result
    except Exception:
        return {}


def _get_darwin_process_memory() -> dict[str, int]:
    """Get process memory details on macOS."""
    try:
        import subprocess
        pid = os.getpid()
        result = subprocess.run(
            ["ps", "-o", "rss=,vsize=", "-p", str(pid)],
            capture_output=True,
            text=True,
        )
        parts = result.stdout.strip().split()
        if len(parts) >= 2:
            return {
                "WorkingSetSize": int(parts[0]) * 1024,
                "PrivateUsage": int(parts[0]) * 1024,
                "PagefileUsage": int(parts[1]) * 1024,
            }
    except Exception:
        pass
    return {}


def get_current_process_memory_bytes() -> dict[str, int]:
    """Get current process memory usage details.

    Returns dict with:
        - PrivateUsage: private committed memory (most accurate)
        - WorkingSetSize: working set (includes shared pages)
        - PagefileUsage: total committed memory
        - PeakWorkingSetSize: peak working set
    """
    system = os.name
    if system == "nt":
        return _get_windows_process_memory_ex()
    elif system == "posix":
        if os.uname().sysname == "Darwin":
            return _get_darwin_process_memory()
        return _get_linux_process_memory()
    return {}


def get_peak_memory_from_counters(counters: dict[str, int]) -> int:
    """Extract the best available memory metric from counters.

    Priority: PrivateUsage > WorkingSetSize > 0
    """
    return counters.get("PrivateUsage") or counters.get("WorkingSetSize") or 0


def release_memory_pages() -> None:
    """Force the OS to reclaim unused memory pages from this process."""
    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            pid = os.getpid()
            process = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
            if process:
                psapi.EmptyWorkingSet(process)
                kernel32.CloseHandle(process)
                logger.debug("EmptyWorkingSet called")
        except Exception:
            pass
    elif os.name == "posix":
        try:
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
            logger.debug("malloc_trim(0) called")
        except Exception:
            pass

    gc.collect()


# ── GPU memory monitoring ────────────────────────────────────────────────

# ── GPU memory monitoring (NVML) ─────────────────────────────────────────

_NVML_INITIALIZED = False
_NVML_DLL = None


def _get_nvml_dll():
    """Get the NVML library handle (lazy init)."""
    global _NVML_DLL, _NVML_INITIALIZED
    if _NVML_INITIALIZED:
        return _NVML_DLL

    possible_paths = []
    if os.name == "nt":
        possible_paths = [
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvml.dll"),
            r"C:\Windows\System32\nvml.dll",
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll",
        ]
    else:
        possible_paths = [
            "libnvidia-ml.so.1",
            "/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1",
            "/usr/lib64/libnvidia-ml.so.1",
        ]

    for path in possible_paths:
        try:
            if os.name == "nt":
                dll = ctypes.WinDLL(path)
            else:
                dll = ctypes.CDLL(path)
            # Try init
            ret = dll.nvmlInit_v2() if hasattr(dll, "nvmlInit_v2") else dll.nvmlInit()
            if ret == 0:
                _NVML_DLL = dll
                _NVML_INITIALIZED = True
                return dll
        except Exception:
            continue

    _NVML_INITIALIZED = True  # Mark as tried even if failed
    return None


class _nvmlMemory_t(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_ulonglong),
        ("free", ctypes.c_ulonglong),
        ("used", ctypes.c_ulonglong),
    ]


def get_gpu_memory_info() -> dict[str, dict[str, int]]:
    """Get GPU memory info for all NVIDIA devices via NVML.

    Returns:
        Dict mapping device_id -> {"total": bytes, "used": bytes, "free": bytes}
        Empty dict if NVML not available.
    """
    nvml = _get_nvml_dll()
    if not nvml:
        return {}

    try:
        count = ctypes.c_uint()
        if nvml.nvmlDeviceGetCount(ctypes.byref(count)) != 0:
            return {}

        result = {}
        for i in range(count.value):
            handle = ctypes.c_void_p()
            if nvml.nvmlDeviceGetHandleByIndex(i, ctypes.byref(handle)) != 0:
                continue

            mem = _nvmlMemory_t()
            if nvml.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(mem)) != 0:
                continue

            result[str(i)] = {
                "total": int(mem.total),
                "used": int(mem.used),
                "free": int(mem.free),
            }
        return result
    except Exception:
        return {}


# ── Memory limit helpers ─────────────────────────────────────────────────

def get_video_processing_memory_limit(ratio: float = 0.80) -> int:
    """Get the memory limit for video processing.

    Args:
        ratio: Fraction of total memory to allow (default 80%).

    Returns:
        Maximum bytes allowed for video processing.
    """
    total, _ = get_system_memory()
    if total == 0:
        total = 8 * 1024 * 1024 * 1024
        logger.warning("Could not detect system memory, assuming 8GB")

    limit = int(total * ratio)
    logger.info(
        "Video processing memory limit: %s / %s (%.0f%%)",
        _format_bytes(limit),
        _format_bytes(total),
        ratio * 100,
    )
    return limit


def _format_bytes(b: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} PB"


# ── Memory estimation ────────────────────────────────────────────────────

def estimate_video_keyframe_memory(
    frame_count: int,
    width: int = 1920,
    height: int = 1080,
) -> int:
    """Estimate memory needed for keyframes of one video."""
    bytes_per_frame = width * height * 3
    return int(frame_count * bytes_per_frame * 1.05)


def estimate_feature_memory(
    feature_dim: int = 2048, video_count: int = 1, max_frames: int = 32
) -> int:
    """Estimate memory needed for feature vectors."""
    total_features = video_count * max_frames
    return total_features * feature_dim * 4


# ── Batch size calculation ───────────────────────────────────────────────

def calculate_batch_size(
    video_count: int,
    memory_limit: int,
    avg_frame_count: int = 16,
    avg_width: int = 1920,
    avg_height: int = 1080,
) -> int:
    """Calculate optimal batch size for video processing based on memory limit.

    The memory_limit parameter is already the intended upper bound (e.g. 80%
    of total system RAM).

    Args:
        video_count: Total number of videos to process.
        memory_limit: Maximum memory allowed for the whole operation (bytes).
        avg_frame_count: Average expected keyframes per video.
        avg_width: Average frame width.
        avg_height: Average frame height.

    Returns:
        Optimal number of videos per batch (at least 1).
    """
    if video_count <= 0:
        return 0

    keyframe_mem_per_video = estimate_video_keyframe_memory(
        avg_frame_count, avg_width, avg_height
    )

    batch_size = memory_limit // keyframe_mem_per_video
    batch_size = max(1, min(batch_size, video_count))

    peak_keyframe_mem = batch_size * keyframe_mem_per_video
    total_feature_mem = estimate_feature_memory(2048, video_count, avg_frame_count)
    estimated_peak = peak_keyframe_mem + total_feature_mem

    logger.info(
        "Batch size: %d videos/批 | "
        "每视频关键帧≈%s | 一批关键帧峰值≈%s | "
        "全部特征≈%s | 估算总峰值≈%s | 内存上限=%s",
        batch_size,
        _format_bytes(keyframe_mem_per_video),
        _format_bytes(peak_keyframe_mem),
        _format_bytes(total_feature_mem),
        _format_bytes(estimated_peak),
        _format_bytes(memory_limit),
    )

    return batch_size


# ── GPU memory limit helper ──────────────────────────────────────────────

def get_gpu_memory_limit(gpu_ratio: float = 0.90) -> dict[str, int]:
    """Get GPU memory limit per device.

    Args:
        gpu_ratio: Fraction of GPU memory to allow (default 90%).

    Returns:
        Dict mapping device_id -> limit_bytes.
        Empty dict if NVML not available.
    """
    info = get_gpu_memory_info()
    if not info:
        return {}

    result = {}
    for dev_id, mem in info.items():
        total = mem.get("total", 0)
        if total > 0:
            result[dev_id] = int(total * gpu_ratio)
            logger.info(
                "GPU %s 显存限制: %s / %s (%.0f%%)",
                dev_id, _format_bytes(result[dev_id]), _format_bytes(total), gpu_ratio * 100,
            )
    return result


# ── Adaptive batch sizer (runtime memory monitoring) ─────────────────────

class AdaptiveBatchSizer:
    """Lightweight runtime batch-size tuner.

    Monitors system RAM + GPU VRAM.  Memory reads are kept to a minimum
    (two API calls per cycle: process counters + system memory).

    If memory pressure is detected the batch size is shrunk; when pressure
    eases it grows back slowly.
    """

    def __init__(
        self,
        initial_batch_size: int,
        memory_limit: int,
        gpu_memory_limit: dict[str, int] | None = None,
    ):
        self.initial = max(1, initial_batch_size)
        self.current = self.initial
        self.memory_limit = max(1, memory_limit)
        self.gpu_limits = gpu_memory_limit or {}
        self.min_batch = 1

        self._has_reduced = False
        self._calibrated = False
        self._mem_per_video = 0

        # single baseline snapshot
        self._baseline_proc = 0
        self._baseline_system_avail = 0

    @property
    def batch_size(self) -> int:
        return self.current

    def _gpu_max_ratio(self) -> float:
        """Fast GPU ratio check (one NVML call)."""
        if not self.gpu_limits:
            return 0.0
        info = get_gpu_memory_info()
        max_r = 0.0
        for dev_id, limit in self.gpu_limits.items():
            if limit <= 0:
                continue
            used = info.get(dev_id, {}).get("used", 0)
            r = used / limit
            if r > max_r:
                max_r = r
        return max_r

    def pre_batch(self) -> None:
        """Record lightweight baselines before a batch."""
        self._baseline_proc = get_peak_memory_from_counters(get_current_process_memory_bytes())
        _, self._baseline_system_avail = get_system_memory()

    def post_batch(self, videos_in_batch: int) -> int:
        """Adjust next batch size.  Keep hot path minimal."""
        # 1. read current state
        proc_after = get_peak_memory_from_counters(get_current_process_memory_bytes())
        _, sys_avail_after = get_system_memory()

        proc_delta = max(0, proc_after - self._baseline_proc)
        sys_delta = max(0, self._baseline_system_avail - sys_avail_after)
        actual = max(proc_delta, sys_delta)

        # 2. first-batch calibration (once)
        if not self._calibrated and videos_in_batch > 0 and actual > 0:
            self._calibrated = True
            self._mem_per_video = actual // videos_in_batch
            logger.info(
                "[内存校准] 实际≈%s/视频 (%d视频 增量%s)",
                _format_bytes(self._mem_per_video),
                videos_in_batch,
                _format_bytes(actual),
            )

        # 3. controlling ratio (RAM vs GPU, pick the tighter one)
        ram_ratio = proc_after / self.memory_limit if self.memory_limit > 0 else 0.0
        gpu_ratio = self._gpu_max_ratio()
        ratio = ram_ratio if ram_ratio > gpu_ratio else gpu_ratio
        constrained = "显存" if gpu_ratio > ram_ratio else "内存"

        # 4. adjust
        old = self.current
        if ratio > 0.92:
            self.current = max(self.min_batch, int(self.current * 0.5))
            self._has_reduced = True
            logger.warning("[内存] %s %.0f%% 超限 → 批次 %d→%d", constrained, ratio * 100, old, self.current)
        elif ratio > 0.80:
            self.current = max(self.min_batch, int(self.current * 0.7))
            self._has_reduced = True
            logger.info("[内存] %s %.0f%% 偏高 → 批次 %d→%d", constrained, ratio * 100, old, self.current)
        elif ratio < 0.55 and self._has_reduced:
            self.current = min(self.initial, int(self.current * 1.25))
            if self.current >= self.initial:
                self._has_reduced = False
            logger.info("[内存] %.0f%% 充裕 → 批次 %d→%d", ratio * 100, old, self.current)
        else:
            logger.debug("[内存] %.0f%% 稳定 批次=%d", ratio * 100, self.current)

        return self.current

    def force_shrink(self, factor: float = 0.5) -> int:
        old = self.current
        self.current = max(self.min_batch, int(self.current * factor))
        self._has_reduced = True
        logger.warning("[内存] 紧急缩减 批次 %d→%d", old, self.current)
        return self.current
