"""Conservative CPU scheduling and cooperative memory protection."""

from __future__ import annotations

import ctypes
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

MIB = 1024 * 1024
DEFAULT_MEMORY_LIMIT_MB = 2048


class ResourceLimitError(MemoryError):
    """Work was stopped before exhausting the configured memory allowance."""


@dataclass(frozen=True)
class MemorySnapshot:
    total: int
    available: int
    process: int
    commit_available: int | None = None


def memory_snapshot() -> MemorySnapshot:
    if sys.platform == 'win32':
        from ctypes import wintypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ('length', wintypes.DWORD), ('load', wintypes.DWORD),
                ('total_phys', ctypes.c_ulonglong), ('available_phys', ctypes.c_ulonglong),
                ('total_page', ctypes.c_ulonglong), ('available_page', ctypes.c_ulonglong),
                ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                ('available_extended', ctypes.c_ulonglong),
            ]

        class ProcessMemory(ctypes.Structure):
            _fields_ = [
                ('size', wintypes.DWORD), ('faults', wintypes.DWORD),
                ('peak_working_set', ctypes.c_size_t), ('working_set', ctypes.c_size_t),
                ('peak_paged', ctypes.c_size_t), ('paged', ctypes.c_size_t),
                ('peak_nonpaged', ctypes.c_size_t), ('nonpaged', ctypes.c_size_t),
                ('pagefile', ctypes.c_size_t), ('peak_pagefile', ctypes.c_size_t),
                ('private', ctypes.c_size_t),
            ]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatus)]
        kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise ctypes.WinError(ctypes.get_last_error())
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        process = ProcessMemory()
        process.size = ctypes.sizeof(process)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemory), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(process), process.size):
            raise ctypes.WinError(ctypes.get_last_error())
        return MemorySnapshot(status.total_phys, status.available_phys,
                              max(process.private, process.working_set), status.available_page)

    import resource

    page_size = os.sysconf('SC_PAGE_SIZE')
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    process_bytes = peak if sys.platform == 'darwin' else peak * 1024
    return MemorySnapshot(os.sysconf('SC_PHYS_PAGES') * page_size,
                          os.sysconf('SC_AVPHYS_PAGES') * page_size, process_bytes)


class ResourceGuard:
    def __init__(self, memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB):
        if memory_limit_mb < 256:
            raise ValueError('Memory limit must be at least 256 MiB.')
        self.limit = memory_limit_mb * MIB
        self.reserve = max(1024 * MIB, min(memory_snapshot().total // 10, 4096 * MIB))
        self.last_check = 0.0

    def check(self, additional_bytes: int = 0, force: bool = False,
              context: str = 'generation') -> MemorySnapshot | None:
        now = time.monotonic()
        if not force and not additional_bytes and now - self.last_check < 0.1:
            return None
        self.last_check = now
        snapshot = memory_snapshot()
        projected_process = snapshot.process + additional_bytes
        projected_available = snapshot.available - additional_bytes
        projected_commit = (snapshot.commit_available - additional_bytes
                            if snapshot.commit_available is not None else None)
        process_blocked = projected_process > self.limit
        ram_blocked = projected_available < self.reserve
        commit_blocked = projected_commit is not None and projected_commit < 512 * MIB
        if process_blocked or ram_blocked or commit_blocked:
            reasons = []
            if process_blocked:
                reasons.append('process memory budget')
            if ram_blocked:
                reasons.append('system RAM reserve')
            if commit_blocked:
                reasons.append('Windows commit headroom')
            next_step = ('Use compact expansion or select fewer variables. Increase the memory budget only '
                         'if the process memory budget is the limiting check; it cannot override the system RAM reserve.')
            if ram_blocked or commit_blocked:
                next_step += ' Close unused applications and try again when more system memory is available.'
            raise ResourceLimitError(
                f'Resource protection stopped during {context} before the next allocation. '
                f'Current process memory: {snapshot.process // MIB} MiB; '
                f'projected: {projected_process // MIB} MiB / {self.limit // MIB} MiB budget. '
                f'Available RAM: {snapshot.available // MIB} MiB; '
                f'projected headroom: {max(projected_available, 0) // MIB} MiB '
                f'(reserve: {self.reserve // MIB} MiB). '
                f'Protection triggered by: {", ".join(reasons)}. {next_step} '
                'No variables were silently omitted.'
            )
        return snapshot


@contextmanager
def background_priority() -> Iterator[None]:
    if sys.platform != 'win32':
        yield
        return
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetPriorityClass.argtypes = [wintypes.HANDLE]
    kernel.GetPriorityClass.restype = wintypes.DWORD
    kernel.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.SetPriorityClass.restype = wintypes.BOOL
    handle = kernel.GetCurrentProcess()
    original = kernel.GetPriorityClass(handle)
    changed = bool(original and kernel.SetPriorityClass(handle, 0x00004000))
    try:
        yield
    finally:
        if changed:
            kernel.SetPriorityClass(handle, original)
